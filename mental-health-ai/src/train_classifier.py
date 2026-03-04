from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm
from transformers import AutoModel, AutoTokenizer

from .feature_builder import FeatureConfig, build_video_features, pad_trunc_mcq
from .utils import LABELS, ensure_dir, label_to_id, load_json, normalize_label, save_json


@dataclass
class TrainConfig:
    base_model: str = "distilbert-base-uncased"
    max_length: int = 192
    mcq_len: int = 20
    text_emb_dim: int = 768  # inferred; kept for record
    mcq_emb_dim: int = 64
    video_emb_dim: int = 128
    fusion_dim: int = 128
    dropout: float = 0.2
    lr: float = 2e-5
    batch_size: int = 4
    epochs: int = 2
    val_size: float = 0.2
    seed: int = 42


class MultimodalClassifier(nn.Module):
    def __init__(
        self,
        base_model: str,
        num_mcq: int,
        video_dim: int,
        mcq_emb_dim: int = 64,
        video_emb_dim: int = 128,
        fusion_dim: int = 128,
        dropout: float = 0.2,
        num_labels: int = 4,
    ):
        super().__init__()
        self.text_encoder = AutoModel.from_pretrained(base_model)
        hidden = int(getattr(self.text_encoder.config, "hidden_size", 768))

        self.mcq_net = nn.Sequential(
            nn.Linear(num_mcq, mcq_emb_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(mcq_emb_dim, mcq_emb_dim),
            nn.ReLU(),
        )

        self.video_net = nn.Sequential(
            nn.Linear(video_dim, video_emb_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(video_emb_dim, video_emb_dim),
            nn.ReLU(),
        )

        self.fusion = nn.Sequential(
            nn.Linear(hidden + mcq_emb_dim + video_emb_dim, fusion_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        self.classifier = nn.Linear(fusion_dim, num_labels)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        mcq: torch.Tensor,
        video: torch.Tensor,
    ) -> torch.Tensor:
        out = self.text_encoder(input_ids=input_ids, attention_mask=attention_mask)
        # CLS token embedding
        cls = out.last_hidden_state[:, 0, :]
        mcq_emb = self.mcq_net(mcq)
        vid_emb = self.video_net(video)
        fused = torch.cat([cls, mcq_emb, vid_emb], dim=-1)
        z = self.fusion(fused)
        logits = self.classifier(z)
        return logits


class MHDDataset(Dataset):
    def __init__(self, samples: List[Dict[str, Any]], tokenizer, cfg: FeatureConfig, max_length: int):
        self.samples = samples
        self.tokenizer = tokenizer
        self.cfg = cfg
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        s = self.samples[idx]
        text = (s.get("subjective_text") or "").strip()
        mcq = pad_trunc_mcq(s.get("mcq_answers") or [], self.cfg)
        video_path = (s.get("video_path") or "").strip()
        video = build_video_features(video_path, self.cfg)

        enc = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        label = label_to_id(s.get("label") or "")
        return (
            enc["input_ids"].squeeze(0),
            enc["attention_mask"].squeeze(0),
            torch.tensor(mcq, dtype=torch.float32),
            torch.tensor(video, dtype=torch.float32),
            torch.tensor(label, dtype=torch.long),
        )


def _set_seed(seed: int) -> None:
    import random

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def train(
    dataset_path: str,
    output_dir: str = "models/classifier",
    cfg: TrainConfig = TrainConfig(),
) -> None:
    _set_seed(cfg.seed)

    samples = load_json(dataset_path)
    if not isinstance(samples, list) or not samples:
        raise ValueError("dataset.json must be a non-empty list of samples.")

    # normalize labels (and validate mapping)
    for s in samples:
        s["label"] = normalize_label(s.get("label") or "")

    train_s, val_s = train_test_split(samples, test_size=cfg.val_size, random_state=cfg.seed, stratify=[s["label"] for s in samples])

    feature_cfg = FeatureConfig(mcq_len=cfg.mcq_len)

    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model)
    ds_train = MHDDataset(train_s, tokenizer, feature_cfg, max_length=cfg.max_length)
    ds_val = MHDDataset(val_s, tokenizer, feature_cfg, max_length=cfg.max_length)

    dl_train = DataLoader(ds_train, batch_size=cfg.batch_size, shuffle=True, num_workers=0)
    dl_val = DataLoader(ds_val, batch_size=cfg.batch_size, shuffle=False, num_workers=0)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = MultimodalClassifier(
        base_model=cfg.base_model,
        num_mcq=feature_cfg.mcq_len,
        video_dim=feature_cfg.video_dim,
        mcq_emb_dim=cfg.mcq_emb_dim,
        video_emb_dim=cfg.video_emb_dim,
        fusion_dim=cfg.fusion_dim,
        dropout=cfg.dropout,
        num_labels=len(LABELS),
    ).to(device)

    optim = torch.optim.AdamW(model.parameters(), lr=cfg.lr)
    loss_fn = nn.CrossEntropyLoss()

    best_val = 0.0
    for epoch in range(cfg.epochs):
        model.train()
        train_loss = 0.0
        for batch in tqdm(dl_train, desc=f"train epoch {epoch+1}/{cfg.epochs}"):
            input_ids, attn, mcq, video, y = [b.to(device) for b in batch]
            optim.zero_grad(set_to_none=True)
            logits = model(input_ids=input_ids, attention_mask=attn, mcq=mcq, video=video)
            loss = loss_fn(logits, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optim.step()
            train_loss += float(loss.item())

        model.eval()
        correct = 0
        total = 0
        val_loss = 0.0
        with torch.no_grad():
            for batch in dl_val:
                input_ids, attn, mcq, video, y = [b.to(device) for b in batch]
                logits = model(input_ids=input_ids, attention_mask=attn, mcq=mcq, video=video)
                loss = loss_fn(logits, y)
                val_loss += float(loss.item())
                pred = torch.argmax(logits, dim=-1)
                correct += int((pred == y).sum().item())
                total += int(y.shape[0])

        acc = (correct / max(1, total)) * 100.0
        avg_train = train_loss / max(1, len(dl_train))
        avg_val = val_loss / max(1, len(dl_val))
        print(f"epoch={epoch+1} train_loss={avg_train:.4f} val_loss={avg_val:.4f} val_acc={acc:.2f}%")

        if acc >= best_val:
            best_val = acc
            out = Path(output_dir)
            ensure_dir(out)
            ensure_dir(out / "tokenizer")
            tokenizer.save_pretrained(str(out / "tokenizer"))

            meta = {
                "labels": LABELS,
                "base_model": cfg.base_model,
                "max_length": cfg.max_length,
                "feature_config": asdict(feature_cfg),
                "train_config": asdict(cfg),
            }
            save_json(out / "config.json", meta)
            torch.save(model.state_dict(), str(out / "model.pt"))

    print(f"Saved best model to {output_dir} (best_val_acc={best_val:.2f}%)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/dataset.json")
    ap.add_argument("--out", default="models/classifier")
    ap.add_argument("--base-model", default=TrainConfig.base_model)
    ap.add_argument("--epochs", type=int, default=TrainConfig.epochs)
    ap.add_argument("--batch-size", type=int, default=TrainConfig.batch_size)
    ap.add_argument("--lr", type=float, default=TrainConfig.lr)
    ap.add_argument("--max-length", type=int, default=TrainConfig.max_length)
    ap.add_argument("--mcq-len", type=int, default=TrainConfig.mcq_len)
    args = ap.parse_args()

    cfg = TrainConfig(
        base_model=args.base_model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        max_length=args.max_length,
        mcq_len=args.mcq_len,
    )
    train(dataset_path=args.dataset, output_dir=args.out, cfg=cfg)


if __name__ == "__main__":
    main()


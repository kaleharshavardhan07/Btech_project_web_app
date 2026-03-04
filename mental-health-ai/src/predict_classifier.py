from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer

from .feature_builder import FeatureConfig, build_video_features, pad_trunc_mcq
from .utils import LABELS, id_to_label, load_json, softmax_np


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
        cls = out.last_hidden_state[:, 0, :]
        mcq_emb = self.mcq_net(mcq)
        vid_emb = self.video_net(video)
        fused = torch.cat([cls, mcq_emb, vid_emb], dim=-1)
        z = self.fusion(fused)
        return self.classifier(z)


@dataclass
class LoadedClassifier:
    model: MultimodalClassifier
    tokenizer: Any
    feature_cfg: FeatureConfig
    max_length: int
    device: torch.device


_LOADED: Optional[LoadedClassifier] = None


def load_classifier(model_dir: str = "models/classifier") -> LoadedClassifier:
    global _LOADED
    if _LOADED is not None:
        return _LOADED

    md = Path(model_dir)
    cfg_path = md / "config.json"
    pt_path = md / "model.pt"
    tok_dir = md / "tokenizer"

    if not cfg_path.exists() or not pt_path.exists() or not tok_dir.exists():
        raise FileNotFoundError(
            f"Missing classifier artifacts in '{model_dir}'. Run training first to create config.json, model.pt, tokenizer/."
        )

    meta = load_json(cfg_path)
    base_model = meta.get("base_model", "distilbert-base-uncased")
    max_length = int(meta.get("max_length", 192))
    feature_cfg = FeatureConfig(**(meta.get("feature_config") or {}))
    train_cfg = meta.get("train_config") or {}

    mcq_emb_dim = int(train_cfg.get("mcq_emb_dim", 64))
    video_emb_dim = int(train_cfg.get("video_emb_dim", 128))
    fusion_dim = int(train_cfg.get("fusion_dim", 128))
    dropout = float(train_cfg.get("dropout", 0.2))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(tok_dir))
    model = MultimodalClassifier(
        base_model=base_model,
        num_mcq=feature_cfg.mcq_len,
        video_dim=feature_cfg.video_dim,
        mcq_emb_dim=mcq_emb_dim,
        video_emb_dim=video_emb_dim,
        fusion_dim=fusion_dim,
        dropout=dropout,
        num_labels=len(LABELS),
    )
    model.load_state_dict(torch.load(str(pt_path), map_location=device))
    model.to(device)
    model.eval()

    _LOADED = LoadedClassifier(
        model=model,
        tokenizer=tokenizer,
        feature_cfg=feature_cfg,
        max_length=max_length,
        device=device,
    )
    return _LOADED


def predict(mcq_answers, text: str, video_path: str, model_dir: str = "models/classifier") -> Dict[str, Any]:
    clf = load_classifier(model_dir=model_dir)

    mcq_vec = pad_trunc_mcq(mcq_answers or [], clf.feature_cfg)
    vid_vec = build_video_features(video_path, clf.feature_cfg)

    enc = clf.tokenizer(
        (text or "").strip(),
        truncation=True,
        max_length=clf.max_length,
        padding="max_length",
        return_tensors="pt",
    )

    input_ids = enc["input_ids"].to(clf.device)
    attn = enc["attention_mask"].to(clf.device)
    mcq_t = torch.tensor(mcq_vec, dtype=torch.float32, device=clf.device).unsqueeze(0)
    vid_t = torch.tensor(vid_vec, dtype=torch.float32, device=clf.device).unsqueeze(0)

    with torch.no_grad():
        logits = clf.model(input_ids=input_ids, attention_mask=attn, mcq=mcq_t, video=vid_t)
        probs = torch.softmax(logits, dim=-1).detach().cpu().numpy()[0].astype(np.float32)

    pred_id = int(np.argmax(probs))
    pred_label = id_to_label(pred_id)
    confidence = float(probs[pred_id])

    return {
        "prediction": pred_label,
        "confidence": confidence,
        "probabilities": {LABELS[i]: float(probs[i]) for i in range(len(LABELS))},
    }


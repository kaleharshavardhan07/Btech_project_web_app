from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .audio_features import extract_audio_features
from .utils import ensure_dir
from .video_features import extract_face_features


@dataclass
class FeatureConfig:
    mcq_len: int = 20  # padded/truncated length
    mcq_pad_value: float = 0.0
    mfcc_n: int = 20
    audio_extra: int = 6
    face_dim: int = 26

    @property
    def audio_dim(self) -> int:
        return self.mfcc_n + self.audio_extra

    @property
    def video_dim(self) -> int:
        return self.face_dim + self.audio_dim


def pad_trunc_mcq(mcq_answers: List[int] | List[float], cfg: FeatureConfig) -> np.ndarray:
    arr = np.array(mcq_answers or [], dtype=np.float32).reshape(-1)
    out = np.full((cfg.mcq_len,), cfg.mcq_pad_value, dtype=np.float32)
    n = min(cfg.mcq_len, arr.shape[0])
    if n > 0:
        out[:n] = arr[:n]
    return out


def build_video_features(video_path: str, cfg: FeatureConfig, cache_dir: str = "models/cache/video") -> np.ndarray:
    """
    Build video feature vector as required:
    - face features via MediaPipe (+ optional DeepFace) aggregated across frames
    - audio features via librosa aggregated over audio
    Returns fixed-size vector of length cfg.video_dim.
    """
    cache_dir_p = ensure_dir(cache_dir)
    # caching is handled in sub-extractors (face/audio), but we keep a stable join here
    face = extract_face_features(video_path=video_path)
    audio = extract_audio_features(video_path=video_path, mfcc_n=cfg.mfcc_n)
    feats = np.concatenate([face, audio], axis=0).astype(np.float32)
    if feats.shape[0] != cfg.video_dim:
        feats = np.resize(feats, (cfg.video_dim,)).astype(np.float32)
    return feats


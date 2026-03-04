from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

from .utils import ensure_dir, file_cache_key


def _safe_import_moviepy():
    try:
        from moviepy.editor import VideoFileClip  # type: ignore

        return VideoFileClip
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "moviepy is required for audio extraction. Install requirements.txt and ensure ffmpeg is available."
        ) from e


def _safe_import_librosa():
    try:
        import librosa  # type: ignore

        return librosa
    except Exception as e:  # pragma: no cover
        raise RuntimeError("librosa is required for audio features. Install requirements.txt.") from e


def extract_audio_to_wav(video_path: str, cache_dir: str, target_sr: int = 16000) -> Optional[str]:
    """
    Extracts audio from video into a cached wav file. Returns wav path, or None if no audio stream.
    """
    VideoFileClip = _safe_import_moviepy()
    cache_dir_p = ensure_dir(cache_dir)

    key = file_cache_key(video_path, extra=f"audio_wav_sr{target_sr}")
    wav_path = cache_dir_p / f"{key}.wav"
    if wav_path.exists():
        return str(wav_path)

    clip = VideoFileClip(video_path)
    try:
        if clip.audio is None:
            return None
        # moviepy writes at original sampling rate; librosa will resample.
        clip.audio.write_audiofile(str(wav_path), fps=target_sr, nbytes=2, logger=None)
        return str(wav_path)
    finally:
        try:
            clip.close()
        except Exception:
            pass


def extract_audio_features(
    video_path: str,
    cache_dir: str = "models/cache/audio",
    sr: int = 16000,
    mfcc_n: int = 20,
) -> np.ndarray:
    """
    Returns fixed-size audio feature vector:
    - MFCC mean (mfcc_n)
    - pitch mean/std (2)
    - energy mean/std (2)
    - speaking rate proxy (1)
    - pause ratio (1)
    Total: mfcc_n + 6
    """
    librosa = _safe_import_librosa()
    cache_dir_p = ensure_dir(cache_dir)
    key = file_cache_key(video_path, extra=f"audio_feat_sr{sr}_mfcc{mfcc_n}")
    feat_path = cache_dir_p / f"{key}.npy"
    if feat_path.exists():
        return np.load(str(feat_path))

    if not os.path.exists(video_path):
        feats = np.zeros((mfcc_n + 6,), dtype=np.float32)
        np.save(str(feat_path), feats)
        return feats

    wav_path = extract_audio_to_wav(video_path, cache_dir=str(cache_dir_p), target_sr=sr)
    if wav_path is None or not os.path.exists(wav_path):
        feats = np.zeros((mfcc_n + 6,), dtype=np.float32)
        np.save(str(feat_path), feats)
        return feats

    y, _sr = librosa.load(wav_path, sr=sr, mono=True)
    if y.size < sr // 4:  # <250ms
        feats = np.zeros((mfcc_n + 6,), dtype=np.float32)
        np.save(str(feat_path), feats)
        return feats

    # MFCC
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=mfcc_n)
    mfcc_mean = np.mean(mfcc, axis=1)

    # Pitch via YIN; ignore unvoiced frames (nan)
    try:
        f0 = librosa.yin(y, fmin=50, fmax=400, sr=sr)
        f0 = f0[np.isfinite(f0)]
        pitch_mean = float(np.mean(f0)) if f0.size else 0.0
        pitch_std = float(np.std(f0)) if f0.size else 0.0
    except Exception:
        pitch_mean, pitch_std = 0.0, 0.0

    # Energy (RMS)
    rms = librosa.feature.rms(y=y)[0]
    energy_mean = float(np.mean(rms)) if rms.size else 0.0
    energy_std = float(np.std(rms)) if rms.size else 0.0

    # Speaking rate proxy: onset events per second (rough proxy for syllabic activity)
    try:
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
        duration_s = max(1e-3, len(y) / sr)
        speaking_rate = float(len(onsets) / duration_s)
    except Exception:
        speaking_rate = 0.0

    # Pause ratio: proportion of frames below an energy threshold
    if rms.size:
        thr = max(1e-6, float(np.percentile(rms, 25)) * 0.8)
        pause_ratio = float(np.mean(rms < thr))
    else:
        pause_ratio = 0.0

    feats = np.concatenate(
        [
            mfcc_mean.astype(np.float32),
            np.array([pitch_mean, pitch_std, energy_mean, energy_std, speaking_rate, pause_ratio], dtype=np.float32),
        ],
        axis=0,
    ).astype(np.float32)

    np.save(str(feat_path), feats)
    return feats


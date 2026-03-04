from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from .utils import ensure_dir, file_cache_key, softmax_np


def _safe_import_cv2():
    try:
        import cv2  # type: ignore

        return cv2
    except Exception as e:  # pragma: no cover
        raise RuntimeError("opencv-python is required for video features. Install requirements.txt.") from e


def _safe_import_mediapipe():
    try:
        import mediapipe as mp  # type: ignore

        return mp
    except Exception as e:  # pragma: no cover
        raise RuntimeError("mediapipe is required for face landmark features. Install requirements.txt.") from e


def _try_import_deepface():
    try:
        from deepface import DeepFace  # type: ignore

        return DeepFace
    except Exception:
        return None


# FaceMesh landmark indices (MediaPipe)
LM_LEFT_EYE = [33, 160, 158, 133, 153, 144]  # p1..p6
LM_RIGHT_EYE = [362, 385, 387, 263, 373, 380]
LM_MOUTH = [13, 14, 78, 308]  # top, bottom, left, right
LM_NOSE_TIP = 1
LM_FOREHEAD = 10
LM_CHIN = 152
LM_LEFT_CHEEK = 234
LM_RIGHT_CHEEK = 454


def _landmark_to_xy(lm) -> np.ndarray:
    return np.array([lm.x, lm.y], dtype=np.float32)


def _eye_aspect_ratio(landmarks, idxs: List[int]) -> float:
    """
    EAR = (||p2-p6|| + ||p3-p5||) / (2*||p1-p4||)
    """
    p1 = _landmark_to_xy(landmarks[idxs[0]])
    p2 = _landmark_to_xy(landmarks[idxs[1]])
    p3 = _landmark_to_xy(landmarks[idxs[2]])
    p4 = _landmark_to_xy(landmarks[idxs[3]])
    p5 = _landmark_to_xy(landmarks[idxs[4]])
    p6 = _landmark_to_xy(landmarks[idxs[5]])
    num = np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)
    den = 2.0 * (np.linalg.norm(p1 - p4) + 1e-6)
    return float(num / den)


def _mouth_aspect_ratio(landmarks) -> float:
    top = _landmark_to_xy(landmarks[LM_MOUTH[0]])
    bottom = _landmark_to_xy(landmarks[LM_MOUTH[1]])
    left = _landmark_to_xy(landmarks[LM_MOUTH[2]])
    right = _landmark_to_xy(landmarks[LM_MOUTH[3]])
    vert = np.linalg.norm(top - bottom)
    horiz = np.linalg.norm(left - right) + 1e-6
    return float(vert / horiz)


def _head_pose_proxy(landmarks) -> Tuple[float, float, float]:
    """
    Lightweight head pose proxy from normalized landmark geometry.
    Returns (yaw, pitch, roll) proxies (not degrees).
    """
    nose = _landmark_to_xy(landmarks[LM_NOSE_TIP])
    chin = _landmark_to_xy(landmarks[LM_CHIN])
    forehead = _landmark_to_xy(landmarks[LM_FOREHEAD])
    lcheek = _landmark_to_xy(landmarks[LM_LEFT_CHEEK])
    rcheek = _landmark_to_xy(landmarks[LM_RIGHT_CHEEK])

    # yaw proxy: cheek imbalance vs nose center
    yaw = float((nose[0] - (lcheek[0] + rcheek[0]) / 2.0) / (np.linalg.norm(rcheek - lcheek) + 1e-6))
    # pitch proxy: nose vertical position between forehead and chin
    pitch = float((nose[1] - forehead[1]) / (np.linalg.norm(chin - forehead) + 1e-6) - 0.5)
    # roll proxy: line between cheeks slope
    roll = float((rcheek[1] - lcheek[1]) / (rcheek[0] - lcheek[0] + 1e-6))
    return yaw, pitch, roll


def _pseudo_emotion_probs(eye_l: float, eye_r: float, mouth_ar: float, yaw: float, pitch: float) -> np.ndarray:
    """
    MediaPipe doesn't provide emotions directly. We produce a *proxy* 7-class distribution
    (angry, disgust, fear, happy, sad, surprise, neutral) from simple facial measures.
    If DeepFace is available, we use real emotion predictions instead.
    """
    # Heuristics: more mouth open -> surprise; higher mouth_ar + stable gaze -> happy;
    # low energy (small mouth, low openness) -> neutral/sad.
    eye = (eye_l + eye_r) / 2.0
    surprise = max(0.0, mouth_ar - 0.35) + max(0.0, eye - 0.28)
    happy = max(0.0, mouth_ar - 0.25) * (1.0 - abs(pitch))
    sad = max(0.0, 0.18 - mouth_ar) + max(0.0, 0.22 - eye)
    fear = max(0.0, eye - 0.30) + max(0.0, abs(yaw) - 0.08)
    angry = max(0.0, abs(yaw) - 0.12) + max(0.0, -pitch)
    disgust = max(0.0, 0.20 - mouth_ar) * max(0.0, pitch)
    neutral = 0.5 + max(0.0, 0.25 - abs(yaw)) + max(0.0, 0.25 - abs(pitch))
    logits = np.array([angry, disgust, fear, happy, sad, surprise, neutral], dtype=np.float32)
    return softmax_np(logits, axis=0).astype(np.float32)


def _deepface_emotions_bgr(frame_bgr: np.ndarray) -> Optional[np.ndarray]:
    DeepFace = _try_import_deepface()
    if DeepFace is None:
        return None
    try:
        # enforce_detection=False so we can fall back gracefully
        out = DeepFace.analyze(frame_bgr, actions=["emotion"], enforce_detection=False, prog_bar=False)
        if isinstance(out, list):
            out = out[0]
        emo = out.get("emotion") or {}
        # DeepFace keys vary; standard: angry, disgust, fear, happy, sad, surprise, neutral
        keys = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
        vec = np.array([float(emo.get(k, 0.0)) for k in keys], dtype=np.float32)
        if np.sum(vec) <= 1e-6:
            return None
        vec = vec / (np.sum(vec) + 1e-8)
        return vec.astype(np.float32)
    except Exception:
        return None


def extract_face_features(
    video_path: str,
    cache_dir: str = "models/cache/face",
    sample_every_s: float = 1.0,
) -> np.ndarray:
    """
    Returns fixed-size face vector consisting of aggregated stats over sampled frames:
    - emotion probs mean/std (7*2 = 14)
    - eye openness (EAR) mean/std for left/right (4)
    - head pose proxy mean/std yaw/pitch/roll (6)
    - mouth aspect ratio mean/std (2)
    Total: 26
    """
    cache_dir_p = ensure_dir(cache_dir)
    key = file_cache_key(video_path, extra=f"face_feat_v2_step{sample_every_s}")
    feat_path = cache_dir_p / f"{key}.npy"
    if feat_path.exists():
        return np.load(str(feat_path))

    if not os.path.exists(video_path):
        feats = np.zeros((26,), dtype=np.float32)
        np.save(str(feat_path), feats)
        return feats

    cv2 = _safe_import_cv2()
    mp = _safe_import_mediapipe()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        feats = np.zeros((26,), dtype=np.float32)
        np.save(str(feat_path), feats)
        return feats

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 1e-3:
        fps = 25.0
    step = max(1, int(round(fps * sample_every_s)))

    emo_list: List[np.ndarray] = []
    eye_list: List[np.ndarray] = []
    pose_list: List[np.ndarray] = []
    mouth_list: List[float] = []

    with mp.solutions.face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as face_mesh:
        frame_idx = 0
        while True:
            ok, frame_bgr = cap.read()
            if not ok:
                break

            if frame_idx % step != 0:
                frame_idx += 1
                continue

            # FaceMesh expects RGB
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            res = face_mesh.process(frame_rgb)
            if not res.multi_face_landmarks:
                frame_idx += 1
                continue

            lms = res.multi_face_landmarks[0].landmark

            eye_l = _eye_aspect_ratio(lms, LM_LEFT_EYE)
            eye_r = _eye_aspect_ratio(lms, LM_RIGHT_EYE)
            mouth_ar = _mouth_aspect_ratio(lms)
            yaw, pitch, roll = _head_pose_proxy(lms)

            # Emotions: DeepFace if available, else proxy distribution
            emo = _deepface_emotions_bgr(frame_bgr)
            if emo is None:
                emo = _pseudo_emotion_probs(eye_l, eye_r, mouth_ar, yaw, pitch)

            emo_list.append(emo.astype(np.float32))
            eye_list.append(np.array([eye_l, eye_r], dtype=np.float32))
            pose_list.append(np.array([yaw, pitch, roll], dtype=np.float32))
            mouth_list.append(float(mouth_ar))

            frame_idx += 1

    cap.release()

    if not emo_list:
        feats = np.zeros((26,), dtype=np.float32)
        np.save(str(feat_path), feats)
        return feats

    emo_arr = np.stack(emo_list, axis=0)
    eye_arr = np.stack(eye_list, axis=0)
    pose_arr = np.stack(pose_list, axis=0)
    mouth_arr = np.array(mouth_list, dtype=np.float32)

    emo_mean = np.mean(emo_arr, axis=0)
    emo_std = np.std(emo_arr, axis=0)
    eye_mean = np.mean(eye_arr, axis=0)
    eye_std = np.std(eye_arr, axis=0)
    pose_mean = np.mean(pose_arr, axis=0)
    pose_std = np.std(pose_arr, axis=0)
    mouth_mean = float(np.mean(mouth_arr))
    mouth_std = float(np.std(mouth_arr))

    feats = np.concatenate(
        [
            emo_mean,
            emo_std,
            eye_mean,
            eye_std,
            pose_mean,
            pose_std,
            np.array([mouth_mean, mouth_std], dtype=np.float32),
        ],
        axis=0,
    ).astype(np.float32)

    # Safety: ensure length
    if feats.shape[0] != 26:
        feats = np.resize(feats, (26,)).astype(np.float32)

    np.save(str(feat_path), feats)
    return feats


def extract_video_features(
    video_path: str,
    cache_dir: str = "models/cache/video",
) -> np.ndarray:
    """
    Final video feature vector = [face_features (26) + audio_features (20+6 default = 26)] => 52 by default.
    This function is a convenience wrapper; use `feature_builder.build_video_features` for configured sizes.
    """
    cache_dir_p = ensure_dir(cache_dir)
    key = file_cache_key(video_path, extra="video_feat_v1")
    feat_path = cache_dir_p / f"{key}.npy"
    if feat_path.exists():
        return np.load(str(feat_path))

    from .audio_features import extract_audio_features

    face = extract_face_features(video_path=video_path)
    audio = extract_audio_features(video_path=video_path)
    feats = np.concatenate([face, audio], axis=0).astype(np.float32)
    np.save(str(feat_path), feats)
    return feats


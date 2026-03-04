from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

LABELS: List[str] = ["depression", "anxiety", "adhd", "ocd"]

# Existing test types map to final labels
TESTTYPE_TO_LABEL: Dict[str, str] = {
    "depression": "depression",
    "anxiety": "anxiety",
    "stress": "ocd",
    "ptsd": "adhd",
}


def normalize_label(raw_label: str) -> str:
    key = (raw_label or "").strip().lower()
    mapped = TESTTYPE_TO_LABEL.get(key, key)
    if mapped not in LABELS:
        raise ValueError(f"Unknown label '{raw_label}'. Expected one of {LABELS} (or {list(TESTTYPE_TO_LABEL.keys())}).")
    return mapped


def label_to_id(label: str) -> int:
    label = normalize_label(label)
    return LABELS.index(label)


def id_to_label(idx: int) -> str:
    return LABELS[int(idx)]


CRISIS_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(suicide|kill myself|end my life|take my life|self[- ]?harm)\b", re.I),
    re.compile(r"\b(i want to die|i'm going to die|no reason to live)\b", re.I),
    re.compile(r"\b(overdose|cut myself|hurt myself)\b", re.I),
    re.compile(r"\b(give up|can't go on)\b", re.I),
]


def detect_crisis_language(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    return any(p.search(t) for p in CRISIS_PATTERNS)


def crisis_safe_response() -> str:
    return (
        "I’m really sorry you’re feeling this way. You deserve support right now.\n\n"
        "If you’re in immediate danger or might hurt yourself, please call your local emergency number right now.\n"
        "If you can, reach out to someone you trust (a friend, family member, or counselor) and let them know what’s going on.\n\n"
        "If you tell me what country you’re in, I can suggest crisis resources in your area. "
        "For now, can you tell me whether you’re safe at this moment?"
    )


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def sha1_of_string(s: str) -> str:
    h = hashlib.sha1()
    h.update(s.encode("utf-8", errors="ignore"))
    return h.hexdigest()


def file_cache_key(path: str, extra: str = "") -> str:
    """
    Cache key that invalidates when file changes (mtime/size).
    """
    try:
        st = os.stat(path)
        sig = f"{os.path.abspath(path)}::{st.st_mtime_ns}::{st.st_size}::{extra}"
    except FileNotFoundError:
        sig = f"{os.path.abspath(path)}::missing::{extra}"
    return sha1_of_string(sig)


def save_json(path: str | Path, obj: Any) -> None:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@dataclass
class Timer:
    start: float = time.time()

    def elapsed_ms(self) -> float:
        return (time.time() - self.start) * 1000.0


def softmax_np(x: np.ndarray, axis: int = -1) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    x = x - np.max(x, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / (np.sum(e, axis=axis, keepdims=True) + 1e-8)


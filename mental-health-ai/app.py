from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.chat_engine import generate_supportive_reply, load_chatbot
from src.predict_classifier import load_classifier, predict


REPO_ROOT = Path(__file__).resolve().parent.parent
AI_ROOT = Path(__file__).resolve().parent


def resolve_video_path(video_path: str) -> str:
    """
    Node.js likely sends paths like 'uploads/videos/file.mp4' relative to the web app root.
    We resolve relative paths against repo root for compatibility without changing Node routes.
    """
    p = Path(video_path or "")
    if not str(p):
        return ""
    if p.is_absolute():
        return str(p)
    return str((REPO_ROOT / p).resolve())


class PredictRequest(BaseModel):
    mcq_answers: List[int] = Field(default_factory=list)
    subjective_text: str = ""
    video_path: str = ""


class PredictResponse(BaseModel):
    prediction: str
    confidence: float
    probabilities: Dict[str, float]


class ChatRequest(BaseModel):
    message: str
    predicted_label: str = ""


class ChatResponse(BaseModel):
    response: str
    safety: Dict[str, Any]


app = FastAPI(title="Mental Health AI Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    # Load once at startup for performance.
    classifier_dir = os.getenv("CLASSIFIER_DIR", str(AI_ROOT / "models" / "classifier"))
    try:
        load_classifier(model_dir=classifier_dir)
    except Exception:
        # It's valid to start the API before training; /predict will then error clearly.
        pass

    try:
        load_chatbot()
    except Exception:
        pass


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict_endpoint(req: PredictRequest) -> PredictResponse:
    classifier_dir = os.getenv("CLASSIFIER_DIR", str(AI_ROOT / "models" / "classifier"))
    try:
        out = predict(
            mcq_answers=req.mcq_answers,
            text=req.subjective_text,
            video_path=resolve_video_path(req.video_path),
            model_dir=classifier_dir,
        )
        return PredictResponse(**out)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Prediction failed: {e}")


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest) -> ChatResponse:
    try:
        out = generate_supportive_reply(message=req.message, predicted_label=req.predicted_label)
        return ChatResponse(**out)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Chat failed: {e}")


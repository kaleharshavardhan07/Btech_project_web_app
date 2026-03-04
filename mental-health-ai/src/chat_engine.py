from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .utils import LABELS, crisis_safe_response, detect_crisis_language


DEFAULT_CHAT_MODEL = "microsoft/DialoGPT-medium"


@dataclass
class LoadedChatbot:
    model: Any
    tokenizer: Any
    device: torch.device


_CHATBOT: Optional[LoadedChatbot] = None


def load_chatbot(model_name: str = DEFAULT_CHAT_MODEL) -> LoadedChatbot:
    global _CHATBOT
    if _CHATBOT is not None:
        return _CHATBOT

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = AutoTokenizer.from_pretrained(model_name)
    mdl = AutoModelForCausalLM.from_pretrained(model_name)
    mdl.to(device)
    mdl.eval()

    _CHATBOT = LoadedChatbot(model=mdl, tokenizer=tok, device=device)
    return _CHATBOT


def _build_prompt(user_message: str, predicted_label: str) -> str:
    label = (predicted_label or "").strip().lower()
    if label not in LABELS:
        label = "unknown"

    # DialoGPT doesn't support system messages; we prepend a compact instruction.
    return (
        "You are a supportive, empathetic mental health assistant. "
        "You must not diagnose or claim certainty, and you must not give medication advice. "
        "Offer gentle coping suggestions, ask one clarifying question, and encourage professional help when appropriate. "
        f"Context: user may be experiencing {label}.\n"
        f"User: {user_message.strip()}\n"
        "Assistant:"
    )


def generate_supportive_reply(message: str, predicted_label: str = "") -> Dict[str, Any]:
    if detect_crisis_language(message or ""):
        return {"response": crisis_safe_response(), "safety": {"crisis_detected": True}}

    bot = load_chatbot()
    prompt = _build_prompt(message or "", predicted_label or "")

    input_ids = bot.tokenizer.encode(prompt, return_tensors="pt").to(bot.device)
    # Keep generation deterministic-ish and safe
    with torch.no_grad():
        out_ids = bot.model.generate(
            input_ids,
            max_new_tokens=120,
            do_sample=True,
            top_p=0.9,
            top_k=50,
            temperature=0.8,
            pad_token_id=bot.tokenizer.eos_token_id,
            eos_token_id=bot.tokenizer.eos_token_id,
            repetition_penalty=1.1,
            no_repeat_ngram_size=3,
        )

    decoded = bot.tokenizer.decode(out_ids[0], skip_special_tokens=True)
    # Extract assistant part after "Assistant:"
    if "Assistant:" in decoded:
        reply = decoded.split("Assistant:", 1)[-1].strip()
    else:
        reply = decoded.strip()

    # Hard safety post-filter: remove any overly clinical language
    banned = ["diagnose", "medication", "prescribe", "dosage"]
    if any(b in reply.lower() for b in banned):
        reply = (
            "I’m here to support you, but I can’t provide medical advice or diagnoses. "
            "If you’d like, tell me more about what you’re experiencing recently—"
            "what’s been the hardest part of your day-to-day?"
        )

    return {"response": reply, "safety": {"crisis_detected": False}}


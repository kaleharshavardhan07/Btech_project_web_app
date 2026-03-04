## Mental Health AI Backend (FastAPI + Multimodal Transformer)

This folder contains a **separate AI backend** for the existing Node.js + MongoDB web app in this repo.

- **Node.js app (existing)**: auth, MCQ, text questions, video uploads, dashboard (unchanged)
- **Python AI backend (this folder)**: multimodal prediction + supportive chatbot

### Labels (4-way, not binary)

Final labels:

- `depression`
- `anxiety`
- `adhd`
- `ocd`

Existing test type mapping (IMPORTANT):

- `depression` → `depression`
- `anxiety` → `anxiety`
- `stress` → `ocd`
- `ptsd` → `adhd`

### Architecture

Node.js → HTTP → FastAPI (`localhost:8000`) → Multimodal Transformer Classifier + DialoGPT chatbot

### Project structure

```
mental-health-ai/
├── data/
│   └── dataset.json
├── models/
│   ├── classifier/
│   └── chatbot/
├── src/
│   ├── train_classifier.py
│   ├── predict_classifier.py
│   ├── feature_builder.py
│   ├── video_features.py
│   ├── audio_features.py
│   ├── chat_engine.py
│   └── utils.py
├── app.py
├── requirements.txt
└── README.md
```

### Setup

From repo root:

```bash
cd mental-health-ai
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

#### FFmpeg requirement (for audio extraction)

Audio features are extracted by writing a cached `.wav` from the uploaded `.mp4`. For this, **FFmpeg must be available**.

- If `moviepy` fails to read audio, install FFmpeg and ensure `ffmpeg` is on your PATH.

### How video processing works (mandatory multimodal)

For each sample, all three modalities are used:

1. **Text (Transformer)**: DistilBERT CLS embedding from `subjective_text`
2. **MCQ (numeric)**: padded/truncated vector → small MLP embedding
3. **Video**
   - **Face features** (`src/video_features.py`):
     - sample **1 frame per second**
     - MediaPipe FaceMesh landmarks → eye openness (EAR), mouth aspect ratio, head movement proxies
     - emotion probabilities:
       - if `deepface` is installed: uses DeepFace emotion predictor
       - otherwise: produces a lightweight proxy distribution (still fixed-size)
     - aggregate over time (mean/std) → fixed vector
   - **Audio features** (`src/audio_features.py`):
     - extract audio → cached wav
     - librosa MFCC mean, pitch mean/std, energy mean/std, speaking-rate proxy, pause ratio

To avoid repeated work, face/audio feature vectors are **cached** under `models/cache/`.

### Training the classifier

Your dataset format (list of samples):

```json
{
  "mcq_answers": [0,1,2,...],
  "subjective_text": "combined text answers",
  "video_path": "uploads/videos/file.mp4",
  "label": "depression"
}
```

Train (from `mental-health-ai/`):

```bash
python -m src.train_classifier --dataset data/dataset.json --out models/classifier --epochs 3
```

This saves:

- `models/classifier/model.pt`
- `models/classifier/config.json`
- `models/classifier/tokenizer/`

### Running the API

From `mental-health-ai/`:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

Optional: override classifier path:

```bash
set CLASSIFIER_DIR=.\models\classifier
uvicorn app:app --host 0.0.0.0 --port 8000
```

### Endpoints

#### POST `/predict`

Input:

```json
{
  "mcq_answers": [0,1,2],
  "subjective_text": "I feel stressed and can't focus.",
  "video_path": "uploads/videos/file.mp4"
}
```

Output:

```json
{
  "prediction": "anxiety",
  "confidence": 0.92,
  "probabilities": {
    "depression": 0.03,
    "anxiety": 0.92,
    "adhd": 0.02,
    "ocd": 0.03
  }
}
```

Curl:

```bash
curl -X POST "http://localhost:8000/predict" -H "Content-Type: application/json" -d "{\"mcq_answers\":[0,1,2],\"subjective_text\":\"I feel stressed.\",\"video_path\":\"uploads/videos/file.mp4\"}"
```

#### POST `/chat`

Input:

```json
{
  "message": "I'm feeling overwhelmed lately.",
  "predicted_label": "anxiety"
}
```

Output:

```json
{
  "response": "…supportive reply…",
  "safety": { "crisis_detected": false }
}
```

Curl:

```bash
curl -X POST "http://localhost:8000/chat" -H "Content-Type: application/json" -d "{\"message\":\"I'm feeling overwhelmed.\",\"predicted_label\":\"anxiety\"}"
```

### Safety filter (mandatory)

The chatbot checks for crisis language (self-harm/suicide/extreme distress). If detected, it returns a **safe response** encouraging immediate help and professional resources.

### Node.js integration (no route changes required)

Your Node app can call:

- `POST http://localhost:8000/predict`
- `POST http://localhost:8000/chat`

`video_path` is typically relative (e.g. `uploads/videos/...`) — the FastAPI server resolves it against the repo root to match your existing upload pipeline.


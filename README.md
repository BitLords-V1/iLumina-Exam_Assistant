# iLumina – Privacy‑Preserving Exam Reader (w/ AnythingLLM)

## **Problem Statement**

Students with dyslexia, visual impairments, or other reading difficulties face significant barriers during in-person exams. The strict, no-internet policy of exam rooms prevents them from using modern accessibility tools. This creates an unfair disadvantage, hindering their academic performance and independence. Our solution addresses this by providing a secure, on-device AI assistant.

## **Executive Summary**
iLumina is a fully offline Windows desktop application that converts exam papers into clear, navigable audio, built to support students with dyslexia and low vision during proctored exams. The system ingests a PDF of the exam (MVP), parses questions, and delivers a voice‑first exam experience with on‑device Whisper ASR for commands and offline TTS for playback. An embedded local LLM orchestrator (e.g., AnythingLLM) manages the exam flow (repeat, next, previous, slow, “ready to answer”) and no internet required.
Why it matters: Current mainstream tools either require the internet, aren’t tuned for exam conditions, or demand costly human readers. iLumina demonstrates how Edge AI unlocks privacy‑preserving accessibility with low latency on Snapdragon® X NPU using ONNX Runtime (QNN EP)

## **Impact**
Barrier: Students with dyslexia/visual impairments struggle to read printed exam text under time pressure.
Constraints: Internet access is typically disallowed in exam rooms and privacy is mandatory.
Status quo: Screen readers and OCR apps exist, but most are not purpose-built for exams or depend on the cloud.
Impact: iLumina enables independent, fair participation in assessments, potentially benefiting students who need text‑to‑speech, slower pacing, repetition, and voice navigation. The system keeps exam content on device for maximum privacy and compliance with exam rules.

## Solution Overview
- MVP Mode (Primary): PDF Upload → Parse/Segment → Voice‑guided exam

**Key Capabilities**
- Offline ASR (commands): Whisper ONNX running locally for command recognition (“repeat”, “slower”, “next”, “previous”, “ready to answer”).
- Offline TTS: Windows SAPI / pyttsx3 for clear, adjustable speech output (rate, pitch, volume).
- Local LLM Orchestrator: AnythingLLM (or equivalent) to segment PDF text into question blocks and manage dialog flow/state.
- Privacy: No network calls and all processing on device.
- Answer Capture: Voice‑dictated answers stored locally.
- Accessibility UX: Pace controls, repetition, high‑contrast UI, keyboard‑only (or hardware) operation.

**Edge AI Angle**
- ON‑device inference (ASR/LLM heuristics) via ONNX Runtime (QNN EP) on Snapdragon® X Elite.
- Low‑latency interactions for real‑time exam navigation.
- Energy‑aware pipelines intended to run efficiently on the NPU as appropriate.


In Short: **Desktop app for accessible, offline exam reading.**  
iLumina uses a **PDF ➜ on‑device processing ➜ offline TTS** pipeline so exam content never leaves the machine. It adds **voice‑only navigation** and an **AnythingLLM “reader‑only” integration** that identifies questions but never provides answers.

> **Why:** Support students with dyslexia or visual impairments while respecting strict exam rules (no internet, privacy by default, low‑latency, inclusive UX).

---
## Authors & Maintainers

| Name | GitHub | Affiliation |
|---|---|---|
| Rushali | [@rushalimoteria8](https://github.com/rushalimoteria8) | NYU |
| Rujuta | [@Rajoshi11](https://github.com/Rajoshi11) | NYU |
| Mahima |  [@mahi397](https://github.com/mahi397) | NYU |
| Gopala Krishna (GK) | [@igopalakrishna](https://github.com/igopalakrishna) | NYU |
| Sarang | [@SARANG1018](https://github.com/SARANG1018) | NYU |

---

## Highlights

- **Hands‑free exam mode:** Voice commands like “repeat”, “repeat slower”, “ready to answer”, “next/previous question”.
- **Offline Text‑to‑Speech:** `pyttsx3` + `pygame` with voice & rate controls.
- **PDF ingestion:** PyMuPDF text extraction.
- **Question detection via AnythingLLM:** Extracts questions/options from the PDF text and reads them aloud; **explicitly avoids giving hints/answers**.
- **Whisper‑based speech‑to‑text:** Live voice input with ONNX/Torch “standalone” Whisper; attempts **QNN (Snapdragon® NPU) ➜ CPU fallback**.
- **Clean API + Electron UI:** Flask backend at `127.0.0.1:5000` with an Electron front‑end.
- **Privacy‑first:** Entire flow runs locally; no exam data is uploaded.

---

## Repository Layout

```text
iLumina-anythingllm/
├─ backend/                     # Flask API (exam flow, PDF ingestion, TTS/STT, LLM glue)
├─ frontend/                    # Electron desktop UI (renderer assets, app bootstrap)
├─ src/                         # Standalone prototypes, utilities (Whisper/TTS/PDF tests)
├─ uploads/                     # User-provided PDFs and runtime artifacts
│  └─ .gitkeep                  # Keeps the empty folder tracked by Git
├─ .gitignore                   # Git ignore rules
├─ FINAL_REPORT.py              # Reporting/diagnostics script for runs & experiments
├─ LICENSE                      # Project license (MIT)
├─ README.md                    # Project documentation
├─ WhisperTranscriber.spec      # PyInstaller build spec for native packaging
├─ debug_anythingllm.py         # Local debug for AnythingLLM connectivity/workspace ops
├─ diagnose_executable.bat      # Windows helper to gather logs/env when EXE misbehaves
├─ extract_mel_filters.py       # Utility to generate mel filterbanks for Whisper
├─ mel_filters.npz              # Precomputed mel filterbank weights
├─ package.json                 # Electron/Node project manifest (scripts, deps)
└─ package-lock.json            # Locked dependency graph for reproducible builds
```

Key bits:
- **backend/**: Flask API, PDF processing, TTS, Whisper control, AnythingLLM client.
- **src/**: Standalone Whisper implementation (+ ONNX session fallback logic), test app, TTS.
- **frontend/**: Electron desktop shell and renderer (UI pages).
- **uploads/**: Sample PDFs for quick testing.
- **BUILD_EXECUTABLE.md**: PyInstaller packaging notes.

---

## Quickstart

### 1) System prerequisites
- **Python** 3.10+ (recommended)
- **Node.js** 18+ and **npm**
- **FFmpeg** (recommended for robust audio on some systems)
- **PortAudio** (macOS/Linux only) if you run microphone capture locally  
  - macOS: `brew install portaudio` then `pip install pyaudio`
- **Windows on Snapdragon (optional):** Qualcomm® QNN provider for ONNX Runtime (see _Acceleration_ below)

### 2) Clone & Python environment

```bash
git clone https://github.com/BitLords-V1/iLumina-Exam_Assistant.git
cd iLumina-anythingllm

# create and activate a venv
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# core deps (requirements.txt is UTF‑16 encoded)
python - <<'PY'
from pathlib import Path
txt = Path('requirements.txt').read_text(encoding='utf-16')
Path('requirements-utf8.txt').write_text(txt, encoding='utf-8')
print('Wrote requirements-utf8.txt')
PY
pip install -r requirements-utf8.txt

# backend extras (Flask API)
pip install -r backend/requirements.txt

# optional OCR & enhanced test app features
pip install -r test-app-requirements.txt
```

> If `onnxruntime-qnn` fails on pip (it’s not published on PyPI), you can **comment it out** and run on CPU. See **Acceleration** below for QNN install options.

### 3) Frontend (Electron)

```bash
cd frontend
npm install
npm run dev   # or: npm start
```

### 4) Backend (Flask API)

In another terminal:

```bash
cd backend
python app.py
```

Health check:

```bash
curl http://127.0.0.1:5000/api/health
# => {"status":"healthy","whisper":"available|unavailable","tts":"available","pdf":"available"}
```

---

## Configuration

### AnythingLLM (reader‑only)
Update `backend/anythingllm_config.yaml`:

```yaml
api_key: "<YOUR-ANYTHINGLLM-API-KEY>"
model_server_base_url: "http://localhost:3001/api"
workspace_slug: "ilumina"
stream: true
max_tokens: 500
temperature: 0.7

# Strictly “reader” persona
system_prompt: "You are an AI exam reading assistant... do not provide hints or answers."
exam_reader_prompt: "Read questions exactly as written. Slow, clear, numbered."
navigation_prompt: "Assist only with navigation (repeat, slower, next/prev)."
boundary_reminder: "I can only read questions and options; I cannot help solve them."
```

> **Security tip:** never commit real API keys. Use a private YAML or env‑subst during deploy.

### Accessibility defaults
The same YAML exposes **reading pace**, **option pauses**, and **question numbering** flags—tune them to your room policy.

---
## User Journey & Voice UX

- Setup: Invigilator loads the exam PDF into iLumina and starts Exam Mode.
Flow:
- Voice Instructions: The app explains commands: “repeat”, “repeat slower”, “proceed/next”, “previous”, “ready to answer”, “end exam”.
- Question 1 Playback: TTS reads the question and (if applicable) the options.

**Voice Commands**:
- repeat / repeat slower : re‑read current content proceed / next : move to next question and read it.
- previous : go back one question and read it.
- ready to answer : iLumina records the dictated answer and playback confirmation.

---

## How It Works

1. **Upload PDF** (`/api/exam/upload`) → text extracted via PyMuPDF (OCR optional).
2. **AnythingLLM pass**: splits text into questions/options with a “reader‑only” system prompt.
3. **Kick off exam** (`/api/agentic/start-exam`): TTS instructions + readiness check.
4. **Voice control** (`/api/agentic/voice-command`): Whisper transcribes your mic input.
5. **Answer capture**: When you say **“ready to answer”**, your next utterance is stored for the current question.
6. **Finish** (`/api/agentic/finish-exam`): Export the answer sheet JSON.

### Voice Commands (examples)
- `repeat` — re‑read the current question
- `repeat slower` — re‑read more slowly
- `next question` / `previous question`
- `ready to answer` — the next utterance is recorded as your answer
- `finish exam` — end session and return answer sheet

---

## REST API (selected)

Base URL: `http://127.0.0.1:5000`

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Service status (Whisper/TTS/PDF) |
| POST | `/api/exam/upload` | Form‑data PDF upload (`file`) |
| POST | `/api/agentic/start-exam` | Start agentic flow; returns first audio + status |
| POST | `/api/agentic/voice-command` | `{ "transcribed_text": "repeat slower" }` |
| POST | `/api/agentic/finish-exam` | Finish and return final answer sheet |
| GET | `/api/audio/voices` | List available TTS voices |
| GET | `/api/audio/file/<filename>` | Stream generated `.wav` |

Minimal cURL to test upload:

```bash
curl -F "file=@uploads/dc781842-3d1a-470d-8a1e-488f20208dd0_Undergrad_English_Sample_5MCQ.pdf" \
  http://127.0.0.1:5000/api/exam/upload
```

---

## Local Testing

Quick scripts in the repo:
- `test_exam.py` – creates a tiny PDF on the fly and drives the core endpoints
- `test_anythingllm_integration.py` – ping the A‑LLM workspace (requires config)
- `comprehensive_test.py` – end‑to‑end checks
- `src/TestApplication.py` – simple UI runner for the standalone pipeline
- `src/test_mic.py` – verify microphone capture

Example:

```bash
python test_exam.py
```

---

## System Architecture

**Components**
- Frontend (Windows App UI): Electron; large fonts, high‑contrast theme, simple controls.
- PDF Ingestion & Parsing: PDF text extraction (e.g., pypdf/pdfminer.six).
- Orchestrator (LLM Brain): AnythingLLM (local) to segment questions/options and manage dialogue rules & prompts.
- ASR (Voice Commands): Whisper ONNX model; and ONNX Runtime with QNN Execution Provider on Snapdragon® X for latency/efficiency.
- TTS: Windows SAPI / pyttsx3 for offline synthesis.
- Persistence: Local exam_session, logs (optional), and export artifacts.

---
## Languages & Frameworks

- Python (backend services), Node/Electron
- ONNX Runtime (QNN EP on Snapdragon® X Elite), Whisper ONNX
- pyttsx3 or Windows SAPI for TTS
- pypdf / pdfminer.six (text) 
- Local LLM orchestrator: AnythingLLM (or LM Studio) configured offline
---

## Acceleration (QNN on Snapdragon®)

The “standalone” Whisper can run with **ONNX Runtime**. The code will try loading the **QNN Execution Provider** first and gracefully fall back to CPU if unavailable:

- `src/standalone_model.py` → `get_onnx_session_with_fallback(...)`

If you’re on a **Copilot+ PC (Snapdragon X series)** and have access to Qualcomm’s ONNX Runtime QNN build, install it per vendor docs. If not, remove/comment `onnxruntime-qnn` in `requirements.txt` and run CPU.

> If you saw `ERROR: No matching distribution found for onnxruntime-qnn`, that’s expected on PyPI; use vendor wheels or keep CPU.

---

## Building an .exe / desktop bundle

### PyInstaller (Windows/macOS/Linux)

```bash
pip install -r build-requirements.txt
python build_executable.py
# or: pyinstaller WhisperTranscriber.spec
```

Artifacts land under `dist/`. See **BUILD_EXECUTABLE.md** for details.

### Electron app

```bash
cd frontend
npm run build     # use electron‑builder targets (nsis/dmg/AppImage)
```

---

## Troubleshooting

- **PyMuPDF not available:** install `PyMuPDF` (see `test-app-requirements.txt`). Without it, PDF extraction is limited.
- **PyAudio install errors (macOS):** `brew install portaudio && pip install pyaudio`.
- **QNN package not found:** comment `onnxruntime-qnn` or install the vendor wheel; CPU fallback will work.
- **Mic permissions (macOS/Windows):** grant microphone access to Python/Electron.
- **TTS not speaking:** on headless servers, `pyttsx3` may need an audio device; prefer running on a desktop OS.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Contributing

PRs that improve accessibility, add languages, or harden the offline story are especially welcome.

---

## Acknowledgments

- **Qualcomm Whisper and EverythingLLM** (speech‑to‑text)
- **Qualcomm AI assets** and QNN EP notes for NPU acceleration
- **PyMuPDF**, **EasyOCR**, **pyttsx3**, **pygame**, and the **Electron** community
- Qualcomm DevRel mentors and the Edge AI community
- NYU Tandon hosting team and volunteers

---
**THANK YOU**
**BUILT WITH ❤️by TEAM iLUMINA**  

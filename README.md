# 🏥 MedAnalyzer AI — Medical Report Analyzer & Patient Health Timeline Builder

> AI-powered medical report intelligence platform — upload medical reports, extract clinical data, track health trends, detect drug interactions, and generate doctor-ready AI summaries.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![React](https://img.shields.io/badge/React-18-61DAFB)
![Claude](https://img.shields.io/badge/Claude-Opus-blueviolet)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🚀 Quick Start (Windows)

### Prerequisites
- **Python 3.10+** — [Download](https://python.org/downloads/)
- **Node.js 18+** — [Download](https://nodejs.org/)
- **Git** (optional)

### One-Click Launch
```bash
# 1. Clone the repo
git clone <repo-url>
cd Medical-Report-Analyzer

# 2. Create your .env file
copy .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY (optional — demo mode works without it)

# 3. Run everything
start.bat
```

That's it! The app opens at `http://localhost:5173`

### Manual Setup

```bash
# Backend
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

---

## 🎮 Demo Mode

Click the **"🎮 Try Demo Mode"** button on the home page to instantly see:
- A diabetic patient (Rajesh Kumar) with 6 months of medical reports
- Rising HbA1c trend (6.1% → 7.8%) flagged as **CRITICAL**
- BP fluctuations crossing hypertensive threshold
- 4 drug interaction warnings (including Metformin ↔ Levothyroxine)
- Full AI-generated doctor summary
- Interactive health timeline with 40+ events

**No PDF upload or API key needed for demo mode!**

---

## 📋 Architecture

```
Upload PDF/Image
     ↓
┌─────────────────────────────────────────────┐
│  1. File Type Detection (digital/scanned)   │
│  2. Text Extraction (pdfplumber / Surya OCR)│
│  3. Language Detection (langdetect)         │
│  4. Biomedical NER (HuggingFace d4data)     │
│  5. Regex Extraction (labs, dates, drugs)    │
│  6. Entity Merging & Deduplication          │
│  7. Timeline Builder (chronological events) │
│  8. Trend Detector (linear regression)      │
│  9. Drug Interaction Check (OpenFDA API)    │
│ 10. AI Summary (Claude API)                 │
└─────────────────────────────────────────────┘
     ↓
  Dashboard: Timeline + Charts + Interactions + Summary
```

---

## 🧬 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18 · Vite · TailwindCSS · Radix UI · Recharts · Framer Motion · i18next |
| **Backend** | FastAPI · Python 3.10 · Uvicorn |
| **OCR** | Surya OCR (primary) · pdfplumber (digital PDFs) · PaddleOCR (fallback) |
| **NLP/NER** | HuggingFace `d4data/biomedical-ner-all` (local, no API) + regex extractors |
| **LLM** | Claude API (claude-opus-4-5) for doctor summaries |
| **Drug Data** | OpenFDA API (free, no key) — label cross-referencing |
| **Database** | SQLite + SQLAlchemy, Fernet encryption for PII |
| **PDF** | pdfplumber (digital) · PyMuPDF (PDF→image) |

---

## 🔧 Pre-Hackathon Checklist

### 1. Pre-download ML Models (avoid slow WiFi)
```bash
# Download and cache the NER model (~400MB)
python -c "from transformers import AutoTokenizer, AutoModelForTokenClassification; AutoTokenizer.from_pretrained('d4data/biomedical-ner-all', cache_dir='./model_cache'); AutoModelForTokenClassification.from_pretrained('d4data/biomedical-ner-all', cache_dir='./model_cache')"
```

### 2. Verify Claude API Key
- Go to [console.anthropic.com](https://console.anthropic.com)
- Create/verify your API key
- Add to `.env`: `ANTHROPIC_API_KEY=sk-ant-...`
- Current model string: `claude-opus-4-5`

### 3. Test Surya OCR (optional)
```bash
pip install surya-ocr
# Requires PyTorch — install separately if needed:
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### 4. Test Everything
```bash
# Start backend
python -m uvicorn backend.main:app --reload

# In browser, visit: http://localhost:8000/demo/data
# Should return full JSON with demo patient data
```

---

## 🌐 Multilingual Support

The app supports:
- 🇬🇧 **English** (default)
- 🇮🇳 **Hindi** (हिंदी)
- 🇮🇳 **Marathi** (मराठी)

All UI labels, buttons, and section headers are translated. The AI summary can also be generated in the detected report language.

---

## 📁 Project Structure

```
Medical-Report-Analyzer/
├── backend/
│   ├── main.py              # FastAPI app + all endpoints
│   ├── config.py             # Environment config
│   ├── database.py           # SQLAlchemy + encryption
│   ├── models.py             # ORM models
│   ├── ocr/
│   │   ├── preprocessor.py   # Image deskew/denoise/enhance
│   │   └── extractor.py      # Multi-engine OCR
│   ├── nlp/
│   │   ├── ner.py            # HuggingFace biomedical NER
│   │   └── regex_extractor.py # Lab values, dates, drugs
│   ├── timeline/
│   │   └── builder.py        # Chronological event builder
│   ├── trends/
│   │   └── detector.py       # Linear regression + thresholds
│   ├── drugs/
│   │   └── interaction.py    # OpenFDA label cross-check
│   └── summary/
│       └── generator.py      # Claude AI summary
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Upload.jsx
│   │   │   ├── Timeline.jsx
│   │   │   ├── TrendChart.jsx
│   │   │   ├── DrugInteractions.jsx
│   │   │   ├── AISummary.jsx
│   │   │   └── EntityExplorer.jsx
│   │   ├── pages/
│   │   │   ├── Home.jsx
│   │   │   └── Dashboard.jsx
│   │   ├── i18n/
│   │   │   ├── en.json
│   │   │   ├── hi.json
│   │   │   └── mr.json
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── requirements.txt
├── .env.example
├── start.bat
└── README.md
```

---

## 🏆 Top 5 Hackathon Talking Points

### 1. 🧠 Multi-Layer Medical NER Pipeline
"We use a two-layer NER approach — HuggingFace's biomedical-ner-all model running locally identifies diseases, drugs, and genes, then our regex layer extracts precise lab values with units, dates, and dosages. This hybrid approach catches what either layer alone would miss."

### 2. 📈 Predictive Health Trend Detection
"Our system doesn't just display data — it runs linear regression on every lab metric to detect RISING, FALLING, and CRITICAL trends. It knows that HbA1c > 6.5% means diabetic range, BP > 140 is hypertensive, and flags these with medical thresholds. Judges, watch the demo patient's HbA1c rise from 6.1 to 7.8 — the system catches this progression early."

### 3. 💊 Honest Drug Interaction Analysis
"We use OpenFDA's free API to cross-reference drug labels. If Drug A's label mentions Drug B in its warnings section, we flag it. This isn't a black-box — we show the exact FDA label text. In our demo, the Metformin-Levothyroxine interaction is flagged because Metformin can suppress TSH levels, directly relevant to this patient's hypothyroidism."

### 4. 🔐 Privacy-First Design
"All patient names and raw medical text are encrypted at rest using Fernet symmetric encryption. The encryption key is configurable. Even if someone accesses the SQLite database directly, they can't read patient PII. This is production-grade healthcare data handling."

### 5. 🌐 Multilingual + Graceful Degradation
"The entire UI works in English, Hindi, and Marathi. The AI summary can be generated in the patient's language. And critically — if the internet is down, if the HuggingFace model hasn't downloaded, if the Claude API key isn't set — the app STILL WORKS. Every component has a fallback: pdfplumber for OCR, regex for NER, rule-based for summaries. The demo mode proves the full pipeline without any external dependencies."

---

## 📝 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/analyze` | Upload and analyze a single report |
| `POST` | `/analyze-multiple` | Upload multiple reports |
| `POST` | `/patient/create` | Create a patient profile |
| `GET`  | `/patient/{id}` | Get patient details |
| `GET`  | `/patient/{id}/timeline` | Get full timeline |
| `GET`  | `/patient/{id}/summary` | Get AI summary |
| `GET`  | `/patients/recent` | List recent patients |
| `GET`  | `/demo/data` | Load demo mode data |
| `GET`  | `/docs` | Interactive API docs (Swagger) |

---

## ⚠️ Known Limitations

- **OpenFDA**: Provides drug label information, not true pairwise clinical interaction checks. We're transparent about this.
- **Surya OCR on Windows**: Requires PyTorch. Falls back to pdfplumber for digital PDFs if not installed.
- **NER Model**: ~400MB download on first run. Pre-download before hackathon day.
- **Trend Detection**: Needs ≥2 data points per metric. Shows "Insufficient Data" with only 1 reading.
- **Language Detection**: Can fail on short/abbreviated medical text. Defaults to English gracefully.

---

## 📄 License

MIT License — Built for hackathon excellence 🏆

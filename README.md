# MedAnalyzer AI — Medical Report Analyzer & Patient Health Timeline Builder

> AI-powered medical report intelligence platform — upload medical reports, extract clinical data, track health trends, detect drug interactions, and generate doctor-ready AI summaries.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![React](https://img.shields.io/badge/React-18-61DAFB)
![Gemini](https://img.shields.io/badge/Gemini-2.0_Flash-4285F4)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Quick Start (Windows)

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
# Edit .env and add your GEMINI_API_KEY (free — get at https://aistudio.google.com/apikey)

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

## Demo Mode

Click the **"Try Demo Mode"** button on the home page to instantly see:
- A diabetic patient (Rajesh Kumar) with 6 months of medical reports
- Rising HbA1c trend (6.1% → 7.8%) flagged as **CRITICAL**
- BP fluctuations crossing hypertensive threshold
- 4 drug interaction warnings (including Metformin ↔ Levothyroxine)
- Full AI-generated doctor summary
- Interactive health timeline with 40+ events

**No PDF upload or API key needed for demo mode! (AI summary will use fallback if no Gemini key is set)**

---

## Architecture

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
│ 10. AI Summary (Google Gemini API — free)   │
└─────────────────────────────────────────────┘
     ↓
  Dashboard: Timeline + Charts + Interactions + Summary
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18 · Vite · TailwindCSS · Radix UI · Recharts · Framer Motion · i18next |
| **Backend** | FastAPI · Python 3.10 · Uvicorn |
| **OCR** | Surya OCR (primary) · pdfplumber (digital PDFs) · PaddleOCR (fallback) |
| **NLP/NER** | HuggingFace `d4data/biomedical-ner-all` (local, no API) + regex extractors |
| **LLM** | Google Gemini API (gemini-2.0-flash) — **free tier**, 15 RPM, 1M tokens/day |
| **Drug Data** | OpenFDA API (free, no key) — label cross-referencing |
| **Database** | SQLite + SQLAlchemy, Fernet encryption for PII |
| **PDF** | pdfplumber (digital) · PyMuPDF (PDF→image) |

---

## Checklist

### 1. Pre-download ML Models (avoid slow WiFi)
```bash
# Download and cache the NER model (~400MB)
python -c "from transformers import AutoTokenizer, AutoModelForTokenClassification; AutoTokenizer.from_pretrained('d4data/biomedical-ner-all', cache_dir='./model_cache'); AutoModelForTokenClassification.from_pretrained('d4data/biomedical-ner-all', cache_dir='./model_cache')"
```

### 2. Get Gemini API Key (FREE)
- Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- Click "Create API Key" (requires Google account)
- Add to `.env`: `GEMINI_API_KEY=your_key_here`
- Free tier: 15 requests/min, 1M+ tokens/day

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

## Multilingual Support

The app supports:
- 🇬🇧 **English** (default)
- 🇮🇳 **Hindi** (हिंदी)
- 🇮🇳 **Marathi** (मराठी)

All UI labels, buttons, and section headers are translated. The AI summary can also be generated in the detected report language.

---

## Project Structure

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

## Known Limitations

- **OpenFDA**: Provides drug label information, not true pairwise clinical interaction checks. We're transparent about this.
- **Surya OCR on Windows**: Requires PyTorch. Falls back to pdfplumber for digital PDFs if not installed.
- **NER Model**: ~400MB download on first run. Pre-download before hackathon day.
- **Trend Detection**: Needs ≥2 data points per metric. Shows "Insufficient Data" with only 1 reading.
- **Language Detection**: Can fail on short/abbreviated medical text. Defaults to English gracefully.

---


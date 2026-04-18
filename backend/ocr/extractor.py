"""
Text extraction engine — multi-strategy OCR with graceful fallbacks.

Priority order:
  1. pdfplumber (for digital PDFs — fast, accurate)
  2. Surya OCR v0.17+ (for scanned/images — state-of-the-art)
  3. PaddleOCR (fallback for languages Surya struggles with)
  4. Raw text return if all OCR fails

Always returns text + confidence score + detected language.
"""

import io
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Check available OCR engines at import time
# ---------------------------------------------------------------------------
SURYA_AVAILABLE = False
PADDLE_AVAILABLE = False
PDFPLUMBER_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    logger.warning("pdfplumber not installed")

try:
    from surya.recognition import RecognitionPredictor
    from surya.detection import DetectionPredictor
    from surya.foundation import FoundationPredictor
    SURYA_AVAILABLE = True
    logger.info("Surya OCR v0.17+ loaded successfully")
except ImportError:
    logger.warning("Surya OCR not available — will use fallbacks")
except Exception as e:
    logger.warning(f"Surya OCR failed to load: {e}")

try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
    logger.info("PaddleOCR loaded successfully")
except ImportError:
    logger.warning("PaddleOCR not available")
except Exception as e:
    logger.warning(f"PaddleOCR failed to load: {e}")

# Language detection
try:
    from langdetect import detect as langdetect_detect
    from langdetect import DetectorFactory
    DetectorFactory.seed = 0  # Deterministic results
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False


# ---------------------------------------------------------------------------
# Cached model loaders (Surya v0.17+)
# ---------------------------------------------------------------------------
_surya_predictors = {}


def _get_surya_predictors():
    """Load and cache Surya OCR predictors (v0.17+ API)."""
    global _surya_predictors
    if not _surya_predictors and SURYA_AVAILABLE:
        try:
            logger.info("Loading Surya OCR models (first time may take a minute)...")
            foundation = FoundationPredictor()
            rec_predictor = RecognitionPredictor(foundation)
            det_predictor = DetectionPredictor()
            _surya_predictors = {
                "rec_predictor": rec_predictor,
                "det_predictor": det_predictor,
            }
            logger.info("Surya OCR models loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Surya models: {e}")
    return _surya_predictors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
class ExtractionResult:
    """Result of text extraction from a document."""

    def __init__(
        self,
        text: str,
        confidence: float = 0.0,
        language: str = "en",
        engine_used: str = "unknown",
        pages: int = 1,
    ):
        self.text = text
        self.confidence = confidence
        self.language = language
        self.engine_used = engine_used
        self.pages = pages

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "confidence": round(self.confidence, 3),
            "language": self.language,
            "engine_used": self.engine_used,
            "pages": self.pages,
        }


def extract_text(
    file_path: str | None = None,
    file_bytes: bytes | None = None,
    file_type: str = "auto",
    filename: str = "",
) -> ExtractionResult:
    """
    Extract text from a medical document.
    
    Automatically selects the best extraction strategy:
    - Digital PDFs → pdfplumber
    - Scanned PDFs → Surya/Paddle OCR
    - Images → Surya/Paddle OCR
    
    Falls back gracefully if engines are unavailable.
    """
    from backend.ocr.preprocessor import detect_file_type

    if file_type == "auto":
        if file_path:
            file_type = detect_file_type(file_path, file_bytes)
        elif filename:
            ext = Path(filename).suffix.lower()
            if ext == ".pdf":
                file_type = "digital_pdf"  # Assume digital, will verify
            else:
                file_type = "image"
        else:
            file_type = "image"

    logger.info(f"Extracting text — file_type={file_type}, engine preference order: pdfplumber → surya → paddle")

    # Strategy 1: Digital PDF — use pdfplumber
    if file_type == "digital_pdf":
        result = _extract_with_pdfplumber(file_path, file_bytes)
        if result and len(result.text.strip()) > 20:
            result.language = _detect_language(result.text)
            return result
        # If pdfplumber returned little text, it might be scanned
        logger.info("pdfplumber returned minimal text — trying OCR")
        file_type = "scanned_pdf"

    # Strategy 2: Scanned PDF or Image — try Surya
    if SURYA_AVAILABLE:
        result = _extract_with_surya(file_path, file_bytes, file_type)
        if result and len(result.text.strip()) > 10:
            result.language = _detect_language(result.text)
            return result
        logger.info("Surya OCR returned minimal text — trying PaddleOCR")

    # Strategy 3: PaddleOCR fallback
    if PADDLE_AVAILABLE:
        result = _extract_with_paddle(file_path, file_bytes, file_type)
        if result and len(result.text.strip()) > 10:
            result.language = _detect_language(result.text)
            return result
        logger.info("PaddleOCR returned minimal text")

    # Strategy 4: If scanned PDF still has some pdfplumber text, use that
    if file_type in ("scanned_pdf", "digital_pdf") and PDFPLUMBER_AVAILABLE:
        result = _extract_with_pdfplumber(file_path, file_bytes)
        if result:
            result.language = _detect_language(result.text)
            result.confidence = max(result.confidence, 0.3)
            return result

    # Final fallback: return empty result
    logger.error("All extraction methods failed")
    return ExtractionResult(
        text="[Text extraction failed — no OCR engine available]",
        confidence=0.0,
        language="en",
        engine_used="none",
    )


# ---------------------------------------------------------------------------
# Private extraction methods
# ---------------------------------------------------------------------------
def _extract_with_pdfplumber(
    file_path: str | None, file_bytes: bytes | None
) -> ExtractionResult | None:
    """Extract text from a digital PDF using pdfplumber."""
    if not PDFPLUMBER_AVAILABLE:
        return None
    try:
        if file_bytes:
            pdf = pdfplumber.open(io.BytesIO(file_bytes))
        elif file_path:
            pdf = pdfplumber.open(file_path)
        else:
            return None

        pages_text = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_text.append(text)

        pdf.close()
        full_text = "\n\n".join(pages_text)

        return ExtractionResult(
            text=full_text,
            confidence=0.95 if full_text.strip() else 0.0,
            engine_used="pdfplumber",
            pages=len(pages_text),
        )
    except Exception as e:
        logger.error(f"pdfplumber extraction failed: {e}")
        return None


def _extract_with_surya(
    file_path: str | None, file_bytes: bytes | None, file_type: str
) -> ExtractionResult | None:
    """Extract text using Surya OCR (v0.17+ API)."""
    if not SURYA_AVAILABLE:
        return None

    predictors = _get_surya_predictors()
    if not predictors:
        return None

    try:
        from PIL import Image
        from backend.ocr.preprocessor import pdf_page_to_image, get_pdf_page_count

        images = []

        if file_type in ("scanned_pdf",) and file_path:
            # Convert each PDF page to image
            page_count = get_pdf_page_count(file_path)
            for i in range(min(page_count, 20)):  # Cap at 20 pages
                img_array = pdf_page_to_image(file_path, i)
                if img_array is not None:
                    # Convert BGR (OpenCV) to RGB for PIL
                    import cv2
                    rgb_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(rgb_array)
                    images.append(pil_img)
        elif file_bytes:
            images.append(Image.open(io.BytesIO(file_bytes)).convert("RGB"))
        elif file_path:
            images.append(Image.open(file_path).convert("RGB"))

        if not images:
            return None

        rec_predictor = predictors["rec_predictor"]
        det_predictor = predictors["det_predictor"]

        # Run Surya OCR v0.17+ — RecognitionPredictor handles both
        # detection and recognition when given a det_predictor
        predictions = rec_predictor(
            images,
            det_predictor=det_predictor,
            sort_lines=True,
        )

        all_text = []
        total_confidence = 0.0
        line_count = 0

        for page_pred in predictions:
            page_lines = []
            for line in page_pred.text_lines:
                page_lines.append(line.text)
                total_confidence += line.confidence
                line_count += 1
            all_text.append("\n".join(page_lines))

        avg_confidence = total_confidence / max(line_count, 1)

        return ExtractionResult(
            text="\n\n".join(all_text),
            confidence=avg_confidence,
            engine_used="surya",
            pages=len(images),
        )

    except Exception as e:
        logger.error(f"Surya OCR failed: {e}", exc_info=True)
        return None


def _extract_with_paddle(
    file_path: str | None, file_bytes: bytes | None, file_type: str
) -> ExtractionResult | None:
    """Extract text using PaddleOCR (fallback)."""
    if not PADDLE_AVAILABLE:
        return None

    try:
        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)

        if file_bytes and not file_path:
            # PaddleOCR needs a file path; write to temp
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(file_bytes)
                file_path = tmp.name

        if not file_path:
            return None

        result = ocr.ocr(file_path, cls=True)

        all_text = []
        total_confidence = 0.0
        line_count = 0

        for page in result:
            if page is None:
                continue
            for line in page:
                text = line[1][0]
                conf = line[1][1]
                all_text.append(text)
                total_confidence += conf
                line_count += 1

        avg_confidence = total_confidence / max(line_count, 1)

        return ExtractionResult(
            text="\n".join(all_text),
            confidence=avg_confidence,
            engine_used="paddleocr",
            pages=1,
        )

    except Exception as e:
        logger.error(f"PaddleOCR failed: {e}")
        return None


def _detect_language(text: str) -> str:
    """Detect the language of extracted text. Defaults to English on failure."""
    if not LANGDETECT_AVAILABLE:
        return "en"

    try:
        # Need at least some text for reliable detection
        sample = text[:2000].strip()
        if len(sample) < 20:
            return "en"
        lang = langdetect_detect(sample)
        return lang
    except Exception:
        return "en"

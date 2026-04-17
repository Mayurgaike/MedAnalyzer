"""
Image preprocessing for OCR — deskew, denoise, contrast enhancement.
Uses OpenCV for image manipulation before passing to OCR engines.
"""

import io
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

try:
    import cv2

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not available — image preprocessing will be skipped.")


def detect_file_type(file_path: str, file_bytes: bytes | None = None) -> str:
    """
    Detect whether a file is a digital PDF, scanned PDF, or image.
    
    Returns: "digital_pdf", "scanned_pdf", or "image"
    """
    ext = Path(file_path).suffix.lower()

    if ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"):
        return "image"

    if ext == ".pdf":
        # Try to detect if PDF has extractable text
        try:
            import pdfplumber

            if file_bytes:
                pdf = pdfplumber.open(io.BytesIO(file_bytes))
            else:
                pdf = pdfplumber.open(file_path)

            total_text = ""
            for page in pdf.pages[:3]:  # Check first 3 pages
                text = page.extract_text() or ""
                total_text += text

            pdf.close()

            # If we got meaningful text, it's a digital PDF
            if len(total_text.strip()) > 50:
                return "digital_pdf"
            else:
                return "scanned_pdf"
        except Exception as e:
            logger.warning(f"PDF analysis failed: {e} — treating as scanned")
            return "scanned_pdf"

    return "image"  # Default fallback


def preprocess_image(image_input, enhance: bool = True) -> np.ndarray:
    """
    Preprocess an image for better OCR results.
    
    Args:
        image_input: file path (str/Path) or numpy array or bytes
        enhance: whether to apply contrast enhancement
    
    Returns:
        Preprocessed image as numpy array
    """
    if not CV2_AVAILABLE:
        logger.warning("OpenCV not available, returning raw image")
        if isinstance(image_input, np.ndarray):
            return image_input
        return None

    # Load image
    if isinstance(image_input, (str, Path)):
        img = cv2.imread(str(image_input))
    elif isinstance(image_input, bytes):
        nparr = np.frombuffer(image_input, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    elif isinstance(image_input, np.ndarray):
        img = image_input.copy()
    else:
        logger.error(f"Unsupported image input type: {type(image_input)}")
        return None

    if img is None:
        logger.error("Failed to load image")
        return None

    try:
        # Step 1: Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        if not enhance:
            return gray

        # Step 2: Denoise
        denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

        # Step 3: Contrast enhancement with CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        # Step 4: Deskew
        deskewed = _deskew(enhanced)

        # Step 5: Binarize with adaptive threshold
        binary = cv2.adaptiveThreshold(
            deskewed, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        return binary

    except Exception as e:
        logger.warning(f"Preprocessing failed: {e} — returning grayscale")
        if len(img.shape) == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img


def _deskew(image: np.ndarray, max_angle: float = 10.0) -> np.ndarray:
    """Deskew a grayscale image by detecting text lines angle."""
    try:
        # Use Hough line transform to find dominant angle
        edges = cv2.Canny(image, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10
        )

        if lines is None or len(lines) == 0:
            return image

        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if abs(angle) < max_angle:
                angles.append(angle)

        if not angles:
            return image

        median_angle = np.median(angles)

        # Only deskew if angle is significant
        if abs(median_angle) < 0.5:
            return image

        # Rotate image
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(
            image, rotation_matrix, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return rotated

    except Exception as e:
        logger.warning(f"Deskew failed: {e}")
        return image


def pdf_page_to_image(pdf_path: str, page_num: int = 0) -> np.ndarray | None:
    """Convert a PDF page to an image array for OCR."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        page = doc.load_page(page_num)
        # Render at 300 DPI for good OCR quality
        mat = fitz.Matrix(300 / 72, 300 / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        doc.close()

        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img

    except ImportError:
        logger.warning("PyMuPDF not installed — cannot convert PDF pages to images")
        return None
    except Exception as e:
        logger.error(f"PDF to image conversion failed: {e}")
        return None


def get_pdf_page_count(pdf_path: str) -> int:
    """Get the number of pages in a PDF."""
    try:
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            return len(pdf.pages)
    except Exception:
        return 1

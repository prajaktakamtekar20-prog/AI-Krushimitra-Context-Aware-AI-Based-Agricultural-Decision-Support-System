"""Lightweight image-quality gates for disease detection uploads."""
from __future__ import annotations

import io
from typing import Any, Dict, Tuple

try:
    from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError
    _PIL_AVAILABLE = True
except Exception:
    _PIL_AVAILABLE = False


def assess_image_quality(
    image_bytes: bytes,
    min_side: int = 64,
    min_laplacian_variance: float = 12.0,
    min_mean_brightness: float = 12.0,
    max_mean_brightness: float = 245.0,
    include_decoded_rgb: bool = False,
) -> Dict[str, Any]:
    if not image_bytes:
        return {
            "ok": False,
            "error_type": "invalid_image",
            "error_message": "Could not read the uploaded image. Please upload a valid JPG, PNG, or WebP file.",
        }
    if not _PIL_AVAILABLE:
        return {
            "ok": False,
            "error_type": "service_failure",
            "error_message": "Image processing libraries are not available on the server.",
        }
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError):
        return {
            "ok": False,
            "error_type": "invalid_image",
            "error_message": "The uploaded file is not a readable image. Please upload a valid JPG, PNG, or WebP of a leaf.",
        }

    width, height = img.size
    if width < min_side or height < min_side:
        return {
            "ok": False,
            "error_type": "low_quality",
            "error_message": (
                f"Image is too small ({width}x{height}). Please upload a clearer close-up "
                f"(at least {min_side}px on each side)."
            ),
            "width": width,
            "height": height,
        }

    rgb = img.convert("RGB")
    gray = rgb.convert("L")
    stats = ImageStat.Stat(gray)
    mean_brightness = float(stats.mean[0]) if stats.mean else 0.0
    if mean_brightness < min_mean_brightness:
        return {
            "ok": False,
            "error_type": "low_quality",
            "error_message": "Image is too dark to diagnose reliably. Please retake the photo in daylight.",
            "mean_brightness": round(mean_brightness, 1),
        }
    if mean_brightness > max_mean_brightness:
        return {
            "ok": False,
            "error_type": "low_quality",
            "error_message": "Image is overexposed. Please retake the photo without harsh glare.",
            "mean_brightness": round(mean_brightness, 1),
        }

    lap = gray.filter(ImageFilter.FIND_EDGES)
    lap_stats = ImageStat.Stat(lap)
    # Pillow Stat.var is variance of pixel values; FIND_EDGES approximates sharpness.
    sharpness = float(lap_stats.var[0]) if lap_stats.var else 0.0
    if sharpness < min_laplacian_variance:
        return {
            "ok": False,
            "error_type": "low_quality",
            "error_message": "Image is too blurry to diagnose reliably. Please hold the camera steady and focus on the leaf.",
            "sharpness": round(sharpness, 2),
        }

    result = {
        "ok": True,
        "width": width,
        "height": height,
        "format": img.format,
        "mean_brightness": round(mean_brightness, 1),
        "sharpness": round(sharpness, 2),
        "mode": img.mode,
    }
    if include_decoded_rgb:
        result["_decoded_rgb"] = rgb
    return result


def decode_rgb_array(image_bytes: bytes, size: Tuple[int, int]):
    from PIL import Image
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize(size, Image.BILINEAR)
    return img

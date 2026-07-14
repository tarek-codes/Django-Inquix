import os
import uuid
import hashlib
import re
import subprocess
import numpy as np
import aiofiles
from datetime import datetime
import fitz
from PIL import Image
import pytesseract

from app.config import settings


SOURCE_MIME_MAP = {
    "text/plain": "text",
    "text/markdown": "text",
    "text/x-python": "text",
    "text/html": "text",
    "text/css": "text",
    "text/javascript": "text",
    "text/csv": "text",
    "application/json": "text",
    "application/pdf": "pdf",
    "image/png": "image",
    "image/jpeg": "image",
    "image/jpg": "image",
    "image/gif": "image",
    "image/webp": "image",
    "image/bmp": "image",
    "audio/mpeg": "audio",
    "audio/mp3": "audio",
    "audio/wav": "audio",
    "audio/wave": "audio",
    "audio/x-wav": "audio",
    "audio/mp4": "audio",
    "audio/m4a": "audio",
    "audio/ogg": "audio",
    "audio/webm": "audio",
    "audio/x-m4a": "audio",
}


def detect_source_type(mime_type: str) -> str:
    if mime_type in SOURCE_MIME_MAP:
        return SOURCE_MIME_MAP[mime_type]
    if mime_type.startswith("text/"):
        return "text"
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("audio/"):
        return "audio"
    return "text"


async def save_upload(kb_id: str, file_content: bytes, filename: str) -> tuple[str, str]:
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(filename)[1] or ""
    safe_filename = f"{file_id}{ext}"
    kb_dir = os.path.join(settings.upload_dir, kb_id)
    os.makedirs(kb_dir, exist_ok=True)
    file_path = os.path.join(kb_dir, safe_filename)

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_content)

    return file_path, safe_filename


async def extract_text(file_path: str, source_type: str, filename: str) -> tuple[str, dict]:
    metadata = {"source_type": source_type, "filename": filename}

    if source_type == "text":
        text = await extract_from_text(file_path)
    elif source_type == "pdf":
        text, extra = await extract_from_pdf(file_path)
        metadata.update(extra)
    elif source_type == "image":
        text, extra = await extract_from_image(file_path)
        metadata.update(extra)
    elif source_type == "audio":
        text, extra = await extract_from_audio(file_path)
        metadata.update(extra)
    else:
        raise ValueError(f"Unsupported source type: {source_type}")

    return text.strip(), metadata


async def extract_from_text(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


async def extract_from_pdf(file_path: str) -> tuple[str, dict]:
    text_parts = []
    page_count = 0

    doc = fitz.open(file_path)
    for page_num, page in enumerate(doc):
        page_text = page.get_text()
        if page_text.strip():
            text_parts.append(page_text)
        page_count += 1
    doc.close()

    return "\n\n".join(text_parts), {"pages": page_count}


async def extract_from_image(file_path: str) -> tuple[str, dict]:
    ocr_text = _ocr_image(file_path)
    caption = await _describe_image(file_path)

    parts = []
    if ocr_text.strip():
        parts.append(f"[OCR Text]\n{ocr_text}")
    if caption.strip():
        parts.append(f"[Image Description]\n{caption}")

    return "\n\n".join(parts), {"ocr_text": ocr_text.strip(), "caption": caption.strip()}


def _ocr_image(file_path: str) -> str:
    try:
        image = Image.open(file_path)
        return pytesseract.image_to_string(image)
    except Exception:
        return ""


async def _describe_image(file_path: str) -> str:
    import base64
    import json
    import httpx

    try:
        with open(file_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.vision_model,
                    "prompt": "Describe this image in detail. What do you see?",
                    "images": [image_base64],
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json().get("response", "")
    except Exception as e:
        print(f"Vision model failed: {e}")
        return ""


_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        try:
            _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        except Exception:
            _whisper_model = WhisperModel("base", device="cpu", compute_type="float32")
    return _whisper_model


def _convert_to_wav(input_path: str, output_path: str) -> bool:
    try:
        subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", input_path],
            capture_output=True, timeout=10,
        )
    except Exception:
        return False

    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", input_path,
             "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
             "-f", "wav", output_path],
            capture_output=True, timeout=30,
        )
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception:
        return False


def _get_audio_duration(wav_path: str) -> float:
    try:
        import soundfile as sf
        data, sr = sf.read(wav_path)
        return len(data) / sr if sr > 0 else 0
    except Exception:
        return 0


def _is_silent(wav_path: str, threshold: float = 0.02) -> bool:
    try:
        import soundfile as sf
        data, _ = sf.read(wav_path)
        if len(data) == 0:
            return True
        rms = np.sqrt(np.mean(data ** 2))
        return rms < threshold
    except Exception:
        return False


async def extract_from_audio(file_path: str) -> tuple[str, dict]:
    wav_path = file_path + "_converted.wav"
    try:
        if not _convert_to_wav(file_path, wav_path):
            return "", {"segments": [], "language": "en", "error": "ffmpeg conversion failed"}

        duration = _get_audio_duration(wav_path)
        if duration < 0.5:
            return "", {"segments": [], "language": "en", "duration": duration, "error": "too short"}

        if _is_silent(wav_path):
            return "", {"segments": [], "language": "en", "duration": duration, "error": "silent audio"}

        model = _get_whisper_model()
        segments, info = model.transcribe(wav_path)

        text_parts = []
        segment_data = []

        for segment in segments:
            t = segment.text.strip()
            if t:
                text_parts.append(t)
                segment_data.append({
                    "start": round(segment.start, 2),
                    "end": round(segment.end, 2),
                    "text": t,
                })

        text = " ".join(text_parts)

        if len(text.split()) <= 1 and duration > 1.0:
            print(f"Whisper returned single-word result '{text}' for {duration:.1f}s audio — may be hallucination")
            text = ""

        return text, {"segments": segment_data, "language": info.language, "duration": duration}

    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

import io
import wave
import struct
import numpy as np


_kokoro_pipeline = None
_edge_tts_available = None


def _get_kokoro_pipeline():
    global _kokoro_pipeline
    if _kokoro_pipeline is None:
        try:
            from kokoro import KPipeline
            _kokoro_pipeline = KPipeline(lang_code='a')
        except Exception as e:
            print(f"Kokoro TTS init failed: {e}")
            return None
    return _kokoro_pipeline


def _check_edge_tts():
    global _edge_tts_available
    if _edge_tts_available is None:
        try:
            import edge_tts
            _edge_tts_available = True
        except ImportError:
            _edge_tts_available = False
    return _edge_tts_available


def _numpy_to_wav(audio: np.ndarray, sample_rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        scaled = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
        wf.writeframes(scaled.tobytes())
    return buf.getvalue()


async def synthesize_kokoro(text: str, voice: str = 'af_heart') -> bytes | None:
    pipeline = _get_kokoro_pipeline()
    if pipeline is None:
        return None

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        generator = pipeline(text, voice=voice, speed=1)

        all_audio = []
        for _, _, audio in generator:
            all_audio.append(audio)

        if not all_audio:
            return None

        combined = np.concatenate(all_audio)
        return _numpy_to_wav(combined)
    except Exception as e:
        print(f"Kokoro TTS failed: {e}")
        return None


async def synthesize_edge(text: str, voice: str = 'en-US-AriaNeural') -> bytes | None:
    if not _check_edge_tts():
        return None

    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        if not audio_chunks:
            return None

        return b"".join(audio_chunks)
    except Exception as e:
        print(f"Edge TTS failed: {e}")
        return None


async def text_to_speech(text: str) -> bytes | None:
    audio = await synthesize_kokoro(text)
    if audio:
        return audio

    audio = await synthesize_edge(text)
    if audio:
        return audio

    return _generate_sine_wave_fallback(text)


def _generate_sine_wave_fallback(text: str) -> bytes:
    duration = max(1.0, len(text) * 0.05)
    sample_rate = 24000
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    frequency = 440
    audio = 0.3 * np.sin(2 * np.pi * frequency * t)
    fade_len = min(4000, len(audio) // 4)
    audio[:fade_len] *= np.linspace(0, 1, fade_len)
    audio[-fade_len:] *= np.linspace(1, 0, fade_len)
    return _numpy_to_wav(audio)

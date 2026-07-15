import json
import base64
import os
import tempfile
import httpx
from typing import AsyncGenerator
from PIL import Image
import pytesseract
from app.config import settings


def build_messages(
    query: str, chunks: list[dict], chat_history: list[dict] | None = None,
    kb_documents: list[str] | None = None, images: list[str] | None = None,
) -> list[dict]:
    doc_chunks = [c for c in chunks if c.get("source_type") != "web"]
    web_chunks = [c for c in chunks if c.get("source_type") == "web"]

    context_parts = []

    if doc_chunks:
        context_parts.append("YOUR UPLOADED FILES:")
        for i, c in enumerate(doc_chunks):
            context_parts.append(
                f"[{i + 1}] {c.get('filename', f'Document {i + 1}')}\n{c['content']}"
            )

    if web_chunks:
        context_parts.append("WEB SEARCH RESULTS:")
        offset = len(doc_chunks)
        for i, c in enumerate(web_chunks):
            context_parts.append(
                f"[{offset + i + 1}] {c.get('filename', f'Web {i + 1}')}\n{c['content']}"
            )

    context = "\n\n---\n\n".join(context_parts)

    rules = [
        "Use your uploaded files ONLY if they contain the specific information requested.",
        "If your files lack the exact details needed, use your general knowledge to answer.",
        'When using general knowledge, start your response with "Based on my general knowledge:".',
        "Cite sources as [1], [2] when using file content.",
        "Be helpful and direct.",
    ]

    system_msg = (
        "You are a helpful assistant.\n\n"
        "RULES:\n" + "\n".join(f"{i+1}. {r}" for i, r in enumerate(rules)) + "\n\n"
        f"CONTEXT:\n{context}"
    )

    messages = [{"role": "system", "content": system_msg}]

    if chat_history:
        for msg in chat_history[-6:]:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["content"]})

    if images:
        content_parts = [{"type": "text", "text": query}]
        for img in images:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img}"},
            })
        messages.append({"role": "user", "content": content_parts})
    else:
        messages.append({"role": "user", "content": query})

    return messages


async def generate_stream(
    query: str, chunks: list[dict], chat_history: list[dict] | None = None,
    kb_documents: list[str] | None = None, images: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    import hashlib
    import json
    from app.services.cache import get_cached_val, set_cached_val

    provider = settings.llm_provider
    model = settings.llm_model

    # Generate a stable cache key
    image_hashes = []
    if images:
        for img in images:
            if isinstance(img, str):
                img_hash = hashlib.sha256(img.encode("utf-8")).hexdigest()
            else:
                img_hash = hashlib.sha256(img).hexdigest()
            image_hashes.append(img_hash)

    chunks_data = []
    if chunks:
        for c in chunks:
            chunks_data.append({
                "id": c.get("id"),
                "content": c.get("content"),
                "filename": c.get("filename"),
                "source_type": c.get("source_type"),
            })

    cache_data = {
        "provider": provider,
        "model": model,
        "query": query,
        "chunks": chunks_data,
        "chat_history": chat_history or [],
        "kb_documents": kb_documents or [],
        "image_hashes": image_hashes,
    }
    
    serialized = json.dumps(cache_data, sort_keys=True)
    hash_val = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    cache_key = f"inquix:llm_generation:{hash_val}"

    # Try to fetch from cache
    try:
        cached_response = await get_cached_val(cache_key)
        if cached_response:
            import asyncio
            chunk_size = 12
            for i in range(0, len(cached_response), chunk_size):
                yield cached_response[i:i+chunk_size]
                await asyncio.sleep(0.005) # 5ms delay between chunks to make it smooth
            return
    except Exception as e:
        print(f"Error reading LLM generation cache: {e}")

    # Cache miss - stream from the LLM
    full_response_parts = []
    if provider == "groq" and settings.groq_api_key:
        try:
            async for token in _generate_groq(query, chunks, chat_history, kb_documents, images):
                full_response_parts.append(token)
                yield token
            
            full_response = "".join(full_response_parts)
            if full_response.strip():
                try:
                    await set_cached_val(cache_key, full_response)
                except Exception as cache_err:
                    print(f"Error saving LLM generation cache: {cache_err}")
            return
        except Exception as e:
            print(f"Groq generation failed, falling back to Ollama: {e}")
            full_response_parts = [] # Reset on fallback

    # Fallback / Default Ollama generation
    async for token in _generate_ollama(query, chunks, chat_history, kb_documents, images):
        full_response_parts.append(token)
        yield token

    full_response = "".join(full_response_parts)
    if full_response.strip():
        try:
            await set_cached_val(cache_key, full_response)
        except Exception as cache_err:
            print(f"Error saving LLM generation cache: {cache_err}")


async def _generate_groq(
    query: str, chunks: list[dict], chat_history: list[dict] | None = None,
    kb_documents: list[str] | None = None, images: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    messages = build_messages(query, chunks, chat_history, kb_documents, images)

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "stream": True,
                "temperature": 0.3,
                "max_tokens": 2048,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    return
                try:
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue


async def _caption_image(image_base64: str) -> str:
    img_data = base64.b64decode(image_base64)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(img_data)
            tmp_path = tmp.name

        image = Image.open(tmp_path)
        print(f"[_caption_image] Image opened: {image.size}, mode={image.mode}")

        ocr_text = ""
        try:
            ocr_text = pytesseract.image_to_string(image, config="--psm 6 --oem 3")
            print(f"[_caption_image] OCR result length: {len(ocr_text.strip())}")
            if ocr_text.strip():
                print(f"[_caption_image] OCR text preview: {ocr_text.strip()[:200]}")
        except Exception as e:
            print(f"[_caption_image] Tesseract OCR failed: {e}")

        caption = ""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{settings.ollama_url}/api/generate",
                    json={
                        "model": settings.vision_model,
                        "prompt": "Describe this image briefly. What type of document or scene is it?",
                        "images": [image_base64],
                        "stream": False,
                        "options": {"num_predict": 80, "temperature": 0.1},
                    },
                )
                response.raise_for_status()
                caption = response.json().get("response", "")
                print(f"[_caption_image] Vision caption: {caption[:100]}")
        except Exception as e:
            print(f"[_caption_image] Vision model failed: {e}")

        parts = []
        if ocr_text.strip():
            parts.append(f"SHOPPING RECEIPT TEXT:\n{ocr_text.strip()}")
        if caption.strip():
            parts.append(f"VISUAL: {caption.strip()}")

        result = "\n\n".join(parts) if parts else ""
        print(f"[_caption_image] Final result length: {len(result)}")
        return result

    except Exception as e:
        print(f"[_caption_image] Image analysis failed: {e}")
        return ""
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def _generate_ollama(
    query: str, chunks: list[dict], chat_history: list[dict] | None = None,
    kb_documents: list[str] | None = None, images: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    messages = build_messages(query, chunks, chat_history, kb_documents)

    system_msg = ""
    for m in messages:
        if m["role"] == "system":
            system_msg = m["content"]

    chat_text = ""
    for m in messages:
        if m["role"] != "system":
            label = "User" if m["role"] == "user" else "Assistant"
            content = m["content"]
            text = content if isinstance(content, str) else ""
            chat_text += f"{label}: {text}\n"

    if images:
        captions = []
        for i, img in enumerate(images):
            caption = await _caption_image(img)
            if caption:
                captions.append(f"Image {i + 1}: {caption}")
            else:
                captions.append(f"Image {i + 1}: (image provided)")
        image_context = "The user provided the following image(s):\n" + "\n".join(captions)
        if system_msg:
            system_msg += "\n\n" + image_context
        else:
            system_msg = image_context

    prompt_parts = []
    if system_msg:
        prompt_parts.append(system_msg)
    prompt_parts.append("")
    prompt_parts.append(chat_text.strip())
    if not chat_text.strip().endswith(f"User: {query}"):
        prompt_parts.append(f"User: {query}")
    prompt_parts.append("Assistant:")

    prompt = "\n".join(prompt_parts)

    ollama_payload = {
        "model": settings.llm_model,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": 0.3, "num_predict": 2048},
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        async with client.stream(
            "POST",
            f"{settings.ollama_url}/api/generate",
            json=ollama_payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]
                except json.JSONDecodeError:
                    continue

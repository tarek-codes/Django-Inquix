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
    is_local: bool = False,
) -> list[dict]:
    doc_chunks = [c for c in chunks if c.get("source_type") != "web"]
    web_chunks = [c for c in chunks if c.get("source_type") == "web"]

    context_parts = []

    if is_local:
        # Conciser chunks and simplified system message to keep local models from hallucinating
        if doc_chunks:
            context_parts.append("UPLOADED FILES:")
            for i, c in enumerate(doc_chunks):
                context_parts.append(
                    f"{c.get('filename', f'Doc {i+1}')}:\n{c['content'][:4000]}"
                )
        if web_chunks:
            context_parts.append("WEB SEARCH RESULTS:")
            for i, c in enumerate(web_chunks):
                context_parts.append(
                    f"{c.get('filename', f'Web {i+1}')}:\n{c['content'][:4000]}"
                )
        context = "\n\n".join(context_parts)

        rules = [
            "Answer the query directly and naturally.",
            "Use the provided CONTEXT to answer the question if it contains relevant details.",
            "If the CONTEXT does not contain the answer, use your general knowledge.",
            "Do NOT include any citations, bracketed numbers (like [1], [2]), or source URLs.",
            "Never explain that the context is missing details or that you are using general knowledge."
        ]
    else:
        # Standard detailed prompt for powerful cloud APIs
        if doc_chunks:
            context_parts.append("YOUR UPLOADED FILES:")
            for i, c in enumerate(doc_chunks):
                context_parts.append(
                    f"[{i + 1}] {c.get('filename', f'Document {i + 1}')}\n{c['content'][:4000]}"
                )

        if web_chunks:
            context_parts.append("WEB SEARCH RESULTS:")
            offset = len(doc_chunks)
            for i, c in enumerate(web_chunks):
                context_parts.append(
                    f"[{offset + i + 1}] {c.get('filename', f'Web {i + 1}')}\n{c['content'][:2000]}"
                )

        context = "\n\n---\n\n".join(context_parts)

        rules = [
            "Answer the user's query directly and concisely.",
            "When WEB SEARCH RESULTS are provided, ALWAYS prioritize them over your pretrained knowledge — web results contain real-time, up-to-date information that your training may not have.",
            "Cross-reference all web results before answering. If multiple sources agree, state that clearly. If sources conflict, cite the most recent or most credible source and note the discrepancy briefly.",
            "For questions about current officeholders, recent events, or factual details that change over time, treat web results as ground truth. Do NOT rely on your pretrained knowledge for these.",
            "If you are uncertain because sources conflict or are unclear, say so honestly rather than guessing. For example: 'According to recent sources, X holds this position, though earlier sources mention Y.'",
            "Do NOT include any citations, bracketed numbers (like [1], [2]), or source URLs in your response.",
            "Do NOT start your answer with 'Based on the provided information', 'Based on my general knowledge', 'According to the context', or similar meta-phrases.",
        ]

    active_docs_str = ", ".join(kb_documents) if kb_documents else "None"

    system_msg = (
        "You are a helpful assistant.\n\n"
        f"ACTIVE DOCUMENTS IN KNOWLEDGE BASE: {active_docs_str}\n"
        "If a document is not listed above, it does not exist (or has been deleted). "
        "Do not answer questions using deleted files, even if they appear in the chat history.\n\n"
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

    # Auto-upgrade provider to a cloud API if Ollama is configured but disabled/cloud keys are available
    if provider == "ollama" and (settings.disable_ollama or settings.gemini_api_key or settings.openai_api_key or settings.groq_api_key):
        if settings.gemini_api_key:
            provider = "gemini"
        elif settings.openai_api_key:
            provider = "openai"
        elif settings.groq_api_key:
            provider = "groq"

    # Groq does NOT support vision/image inputs — if images are present, upgrade to a vision-capable provider
    if images and provider == "groq":
        if settings.gemini_api_key:
            provider = "gemini"
        elif settings.openai_api_key:
            provider = "openai"

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
    success = False

    # Define generators for each provider
    generators = {
        "gemini": _generate_gemini,
        "openai": _generate_openai,
        "groq": _generate_groq,
        "ollama": _generate_ollama,
    }

    # Helper function to check if a provider is configured
    def is_configured(p):
        if p == "gemini":
            return bool(settings.gemini_api_key)
        if p == "openai":
            return bool(settings.openai_api_key)
        if p == "groq":
            return bool(settings.groq_api_key)
        if p == "ollama":
            return not settings.disable_ollama
        return False

    # 1. Try the user-configured provider first
    if provider in generators and is_configured(provider):
        try:
            async for token in generators[provider](query, chunks, chat_history, kb_documents, images):
                full_response_parts.append(token)
                yield token
            success = True
        except Exception as e:
            print(f"Configured provider {provider} generation failed: {e}")
            full_response_parts = [] # reset partial outputs on failure

    # 2. If the configured provider failed or wasn't configured, fall back in priority order:
    if not success:
        # Groq doesn't support vision — exclude it from fallback when images are present
        fallback_order = ["gemini", "openai", "groq", "ollama"] if not images else ["gemini", "openai", "ollama"]
        for p in fallback_order:
            if p == provider:  # already tried
                continue
            if is_configured(p):
                try:
                    print(f"Trying fallback provider: {p}")
                    async for token in generators[p](query, chunks, chat_history, kb_documents, images):
                        full_response_parts.append(token)
                        yield token
                    success = True
                    break
                except Exception as e:
                    print(f"Fallback provider {p} failed: {e}")
                    full_response_parts = []

    # Save to cache if we succeeded
    if success:
        full_response = "".join(full_response_parts)
        if full_response.strip():
            try:
                await set_cached_val(cache_key, full_response)
            except Exception as cache_err:
                print(f"Error saving LLM generation cache: {cache_err}")
    else:
        # Extreme fallback to local Ollama if all configurations and fallbacks failed
        try:
            print("Extreme fallback to local Ollama (since all cloud options failed)")
            async for token in _generate_ollama(query, chunks, chat_history, kb_documents, images):
                full_response_parts.append(token)
                yield token
            
            full_response = "".join(full_response_parts)
            if full_response.strip():
                try:
                    await set_cached_val(cache_key, full_response)
                except Exception as cache_err:
                    print(f"Error saving LLM generation cache: {cache_err}")
        except Exception as ollama_err:
            print(f"All LLM generation paths (including Ollama fallback) failed: {ollama_err}")
            yield f"Error: All LLM generation paths failed (including local Ollama fallback). Details: {ollama_err}"


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


async def _generate_openai(
    query: str, chunks: list[dict], chat_history: list[dict] | None = None,
    kb_documents: list[str] | None = None, images: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    messages = build_messages(query, chunks, chat_history, kb_documents, images)
    
    # Model resolution
    model = settings.llm_model if settings.llm_model.startswith(("gpt-", "o1-")) else "gpt-4o-mini"
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
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
                data_str = line[6:].strip()
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


async def _generate_gemini(
    query: str, chunks: list[dict], chat_history: list[dict] | None = None,
    kb_documents: list[str] | None = None, images: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    messages = build_messages(query, chunks, chat_history, kb_documents, images)
    
    system_text = ""
    contents = []
    
    for m in messages:
        if m["role"] == "system":
            system_text = m["content"]
        else:
            role = "user" if m["role"] == "user" else "model"
            content = m["content"]
            
            parts = []
            if isinstance(content, list):
                for p in content:
                    if p.get("type") == "text":
                        parts.append({"text": p["text"]})
                    elif p.get("type") == "image_url":
                        url = p["image_url"]["url"]
                        if url.startswith("data:"):
                            header, base64_data = url.split(",", 1)
                            mime_type = header.split(";")[0].split(":")[1]
                            parts.append({
                                "inlineData": {
                                    "mimeType": mime_type,
                                    "data": base64_data
                                }
                            })
            else:
                parts.append({"text": content})
                
            contents.append({"role": role, "parts": parts})
            
    model = settings.llm_model if "gemini" in settings.llm_model else "gemini-3.5-flash"
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
        }
    }
    if system_text:
        payload["systemInstruction"] = {
            "parts": [{"text": system_text}]
        }
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={settings.gemini_api_key}"
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                try:
                    data = json.loads(data_str)
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for p in parts:
                            text = p.get("text", "")
                            if text:
                                yield text
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
        # 1. Try Gemini Vision if key is configured
        if settings.gemini_api_key:
            try:
                print("[_caption_image] Using Gemini Vision for captioning")
                model = settings.llm_model if "gemini" in settings.llm_model else "gemini-3.5-flash"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.gemini_api_key}"
                async with httpx.AsyncClient(timeout=60.0) as client:
                    payload = {
                        "contents": [{
                            "parts": [
                                {"text": "Describe this image briefly. What type of document or scene is it?"},
                                {
                                    "inlineData": {
                                        "mimeType": "image/jpeg",
                                        "data": image_base64
                                    }
                                }
                            ]
                        }]
                    }
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    caption = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    print(f"[_caption_image] Gemini caption: {caption[:100]}")
            except Exception as e:
                print(f"[_caption_image] Gemini Vision captioning failed: {e}")

        # 2. Try OpenAI Vision if key is configured
        if not caption and settings.openai_api_key:
            try:
                print("[_caption_image] Using OpenAI Vision for captioning")
                model = settings.llm_model if settings.llm_model.startswith(("gpt-", "o1-")) else "gpt-4o-mini"
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.openai_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": "Describe this image briefly. What type of document or scene is it?"},
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/jpeg;base64,{image_base64}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            "max_tokens": 150,
                        }
                    )
                    resp.raise_for_status()
                    caption = resp.json()["choices"][0]["message"]["content"].strip()
                    print(f"[_caption_image] OpenAI caption: {caption[:100]}")
            except Exception as e:
                print(f"[_caption_image] OpenAI Vision captioning failed: {e}")

        # 3. Fallback to local Ollama
        if not caption:
            try:
                print("[_caption_image] Falling back to Ollama Vision for captioning")
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
    messages = build_messages(query, chunks, chat_history, kb_documents, is_local=True)

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

    # Resolve local model
    local_model = settings.llm_model
    if images:
        local_model = settings.vision_model
    else:
        cloud_models_keywords = ("gpt", "claude", "gemini", "llama-3.3", "groq", "o1-", "deepseek")
        if any(kw in local_model.lower() for kw in cloud_models_keywords):
            local_model = "qwen2.5:3b"

    ollama_payload = {
        "model": local_model,
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


async def should_search_web(query: str) -> bool:
    q = query.strip().lower()
    
    # Greetings & simple chit-chat
    greetings = {"hello", "hi", "hey", "how are you", "good morning", "good afternoon", "good evening", "greetings"}
    if q in greetings or q.startswith(("hello ", "hi ", "hey ")):
        return False
        
    # Coding prompts, creative writing, general explanations
    creative_words = ("write a python", "write a code", "write a script", "create a function", "write a story", "write an essay", "generate a ", "explain the concept of", "can you write")
    if q.startswith(creative_words):
        return False
        
    # Math expressions
    import re
    if re.match(r'^[\d+\-*/\s().]+$', q):
        return False

    system_prompt = (
        "You are a query router. Decide if a query requires up-to-date information from the web, "
        "current events, specific real-time facts, or scraping a website.\n"
        "If the query is a general knowledge question, mathematical query, coding request, creative prompt, "
        "or general advice that can be answered accurately using standard pre-trained LLM knowledge, classify it as 'general'.\n"
        "If it requires current info, search engine queries, or specific details not present in standard knowledge, classify it as 'web'.\n"
        "Respond with exactly one word: 'web' or 'general'."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Query: {query}"}
    ]
    
    # Define routing functions for each provider
    async def _route_gemini():
        model = settings.llm_model if "gemini" in settings.llm_model else "gemini-3.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.gemini_api_key}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            contents = [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]} for m in messages if m["role"] != "system"]
            payload = {"contents": contents}
            system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
            if system_msg:
                payload["systemInstruction"] = {"parts": [{"text": system_msg}]}
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
            return "web" in text

    async def _route_openai():
        model = settings.llm_model if settings.llm_model.startswith(("gpt-", "o1-")) else "gpt-4o-mini"
        url = "https://api.openai.com/v1/chat/completions"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={"model": model, "messages": messages, "max_tokens": 5, "temperature": 0.0}
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip().lower()
            return "web" in text

    async def _route_groq():
        url = "https://api.groq.com/openai/v1/chat/completions"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json={"model": "llama-3.3-70b-versatile", "messages": messages, "max_tokens": 5, "temperature": 0.0}
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip().lower()
            return "web" in text

    async def _route_ollama():
        url = f"{settings.ollama_url}/api/generate"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json={"model": settings.llm_model, "prompt": f"{system_prompt}\n\nQuery: {query}\n\nClassification:", "stream": False}
            )
            resp.raise_for_status()
            text = resp.json().get("response", "").strip().lower()
            return "web" in text

    # Try providers in fallback order
    provider = settings.llm_provider
    if provider == "ollama" or settings.disable_ollama:
        if settings.gemini_api_key:
            provider = "gemini"
        elif settings.openai_api_key:
            provider = "openai"
        elif settings.groq_api_key:
            provider = "groq"

    providers = [
        ("gemini", _route_gemini, bool(settings.gemini_api_key)),
        ("openai", _route_openai, bool(settings.openai_api_key)),
        ("groq", _route_groq, bool(settings.groq_api_key)),
        ("ollama", _route_ollama, not settings.disable_ollama),
    ]

    # Reorder to try selected provider first
    try_order = []
    for name, func, configured in providers:
        if name == provider and configured:
            try_order.append((name, func))
            break
            
    for name, func, configured in providers:
        if name != provider and configured:
            try_order.append((name, func))

    for name, func in try_order:
        try:
            res = await func()
            print(f"[Router] {name} classified query as web={res}")
            return res
        except Exception as e:
            print(f"[Router] {name} failed: {e}")

    # Default fallback: search web to be safe
    return True

import json
import base64
import httpx
from typing import AsyncGenerator
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
    provider = settings.llm_provider
    if provider == "groq" and settings.groq_api_key:
        try:
            async for token in _generate_groq(query, chunks, chat_history, kb_documents, images):
                yield token
            return
        except Exception as e:
            print(f"Groq generation failed, falling back to Ollama: {e}")

    async for token in _generate_ollama(query, chunks, chat_history, kb_documents, images):
        yield token


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
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.vision_model,
                    "prompt": "Describe this image in detail. What do you see?",
                    "images": [image_base64],
                    "stream": False,
                    "options": {"num_predict": 150, "temperature": 0.2},
                },
            )
            response.raise_for_status()
            return response.json().get("response", "")
    except Exception as e:
        print(f"Image captioning failed: {e}")
        return ""


async def _generate_ollama(
    query: str, chunks: list[dict], chat_history: list[dict] | None = None,
    kb_documents: list[str] | None = None, images: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    messages = build_messages(query, chunks, chat_history, kb_documents)

    system_msg = ""
    context_messages = []
    for m in messages:
        if m["role"] == "system":
            system_msg = m["content"]
        else:
            context_messages.append(m)

    prompt_parts = []
    if system_msg:
        prompt_parts.append(system_msg)
    prompt_parts.append("")
    for m in context_messages:
        role = "User" if m["role"] == "user" else "Assistant"
        content = m["content"]
        text = content if isinstance(content, str) else ""
        prompt_parts.append(f"{role}: {text}")

    prompt = "\n".join(prompt_parts)

    if images:
        captions = []
        for i, img in enumerate(images):
            caption = await _caption_image(img)
            if caption:
                captions.append(f"Image {i + 1}: {caption}")
        if captions:
            prompt += "\n\nThe user uploaded the following image(s):\n" + "\n".join(captions) + "\n\nPlease answer the user's question based on the image content above."

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

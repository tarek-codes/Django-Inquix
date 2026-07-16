import httpx
from app.config import settings


async def get_embedding(text: str) -> list[float]:
    import hashlib
    import json
    from app.services.cache import get_cached_val, set_cached_val

    provider = settings.embed_provider
    model = settings.embedding_model

    # If Ollama is disabled or configured to use Ollama, auto-upgrade to available cloud APIs
    if provider == "ollama" and (settings.disable_ollama or settings.openai_api_key or settings.gemini_api_key or settings.jina_api_key):
        if settings.openai_api_key:
            provider = "openai"
            if not model or model == "nomic-embed-text":
                model = "text-embedding-3-small"
        elif settings.gemini_api_key:
            provider = "gemini"
            if not model or model == "nomic-embed-text":
                model = "gemini-embedding-2"
        elif settings.jina_api_key:
            provider = "jina"
            if not model or model == "nomic-embed-text":
                model = "jina-embeddings-v2-base-en"

    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    cache_key = f"inquix:embedding:{provider}:{model}:{text_hash}"

    try:
        cached_val = await get_cached_val(cache_key)
        if cached_val:
            return json.loads(cached_val)
    except Exception as e:
        print(f"Error reading embedding cache: {e}")

    # Map providers to implementation functions
    generators = {
        "jina": lambda t, m: _embed_jina(t),
        "openai": _embed_openai,
        "gemini": _embed_gemini,
        "ollama": lambda t, m: _embed_ollama(t),
    }

    # Verify if a provider is configured and not disabled
    def is_configured(p):
        if p == "ollama":
            return not settings.disable_ollama
        if p == "openai":
            return bool(settings.openai_api_key)
        if p == "gemini":
            return bool(settings.gemini_api_key)
        if p == "jina":
            return bool(settings.jina_api_key)
        return False

    success = False
    embedding = None
    errors = {}

    # Try primary provider
    if provider in generators and is_configured(provider):
        try:
            embedding = await generators[provider](text, model)
            success = True
        except Exception as e:
            errors[provider] = str(e)
            print(f"Embedding provider {provider} failed: {e}")

    # Fallback to alternative providers
    if not success:
        fallback_order = ["openai", "gemini", "jina", "ollama"]
        for p in fallback_order:
            if p == provider:
                continue
            if is_configured(p):
                try:
                    print(f"Trying fallback embedding provider: {p}")
                    fallback_model = model
                    if p == "openai":
                        fallback_model = "text-embedding-3-small"
                    elif p == "gemini":
                        fallback_model = "gemini-embedding-2"
                    elif p == "jina":
                        fallback_model = "jina-embeddings-v2-base-en"
                    elif p == "ollama":
                        fallback_model = settings.embedding_model

                    embedding = await generators[p](text, fallback_model)
                    success = True
                    break
                except Exception as e:
                    errors[p] = str(e)
                    print(f"Fallback embedding provider {p} failed: {e}")

    if not success:
        err_msg = "All embedding generation paths failed. Details: " + ", ".join(f"{k}: {v}" for k, v in errors.items())
        if not errors:
            err_msg += "No available or functioning embedding provider was configured."
        raise ValueError(err_msg)

    # Ensure the embedding vector matches the pgvector schema dimension (exactly 3072)
    if embedding and len(embedding) != 3072:
        print(f"[get_embedding] Adjusting vector size from {len(embedding)} to 3072 dimensions")
        if len(embedding) < 3072:
            embedding = embedding + [0.0] * (3072 - len(embedding))
        else:
            embedding = embedding[:3072]

    try:
        await set_cached_val(cache_key, json.dumps(embedding))
    except Exception as e:
        print(f"Error saving embedding cache: {e}")

    return embedding


async def _embed_jina(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.jina.ai/v1/embeddings",
            headers={
                "Authorization": f"Bearer {settings.jina_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "jina-embeddings-v2-base-en",
                "input": [text[:8000]],
            },
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]


async def _embed_openai(text: str, model: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": text[:8000],
            },
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]


async def _embed_gemini(text: str, model: str) -> list[float]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent?key={settings.gemini_api_key}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "model": f"models/{model}",
                "content": {
                    "parts": [{"text": text[:8000]}]
                }
            },
        )
        response.raise_for_status()
        return response.json()["embedding"]["values"]


async def _embed_ollama(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ollama_url}/api/embeddings",
            json={"model": settings.embedding_model, "prompt": text[:8000]},
        )
        response.raise_for_status()
        return response.json()["embedding"]


async def ensure_models():
    import asyncio

    if settings.disable_ollama or (settings.llm_provider != "ollama" and settings.embed_provider != "ollama"):
        print("Cloud providers configured or Ollama disabled, skipping Ollama model checks")
        return

    for attempt in range(12):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{settings.ollama_url}/api/tags")
                response.raise_for_status()
                available = {m["name"] for m in response.json().get("models", [])}

            needed = set()
            if settings.embed_provider == "ollama":
                needed.add(settings.embedding_model)
            if settings.llm_provider == "ollama":
                needed.add(settings.llm_model)
                needed.add(settings.vision_model)
            missing = needed - available

            if missing:
                print(f"Pulling models: {missing}")
                async with httpx.AsyncClient(timeout=600.0) as client:
                    for model in missing:
                        print(f"Pulling {model}...")
                        await client.post(
                            f"{settings.ollama_url}/api/pull",
                            json={"name": model, "stream": False},
                        )
                        print(f"{model} ready.")
            return
        except Exception as e:
            if attempt < 11:
                print(f"Waiting for Ollama ({attempt + 1}/12): {e}")
                await asyncio.sleep(5)
            else:
                print(f"Warning: Could not connect to Ollama: {e}")

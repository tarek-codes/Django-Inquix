import asyncio
import httpx
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from app.config import settings


async def search_web(query: str, max_results: int = 3) -> list[dict]:
    import hashlib
    import json
    import re
    from app.services.cache import get_cached_val, set_cached_val

    # Normalize query to improve cache hit rates across variations (case, spacing, punctuation)
    normalized = re.sub(r'[^\w\s]', '', query.strip().lower())
    normalized = re.sub(r'\s+', ' ', normalized)
    query_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    cache_key = f"inquix:web_search:{max_results}:{query_hash}"

    try:
        cached_val = await get_cached_val(cache_key)
        if cached_val:
            return json.loads(cached_val)
    except Exception as e:
        print(f"Error reading web search cache: {e}")

    results = []
    try:
        results = await _crawl4ai_search(query, max_results)
    except Exception as e:
        print(f"Crawl4AI search failed: {e}")

    if not results:
        try:
            results = await _duckduckgo_search(query, max_results)
        except Exception as e:
            print(f"DuckDuckGo search failed: {e}")

    if not results:
        try:
            if settings.gemini_api_key:
                results = await _gemini_search(query)
        except Exception as e:
            print(f"Gemini search failed: {e}")

    if not results:
        try:
            results = await _search_wikipedia_api(query, max_results)
        except Exception as e:
            print(f"Wikipedia search failed: {e}")

    if results:
        try:
            await set_cached_val(cache_key, json.dumps(results))
        except Exception as e:
            print(f"Error saving web search cache: {e}")

    return results


async def _crawl4ai_search(query: str, max_results: int) -> list[dict]:
    search_urls = await _search_wikipedia_for_urls(query, max_results)
    if not search_urls:
        return []

    chunks = []
    async with AsyncWebCrawler() as crawler:
        for i, info in enumerate(search_urls):
            try:
                config = CrawlerRunConfig(
                    cache_mode=CacheMode.ENABLED,
                    word_count_threshold=10,
                )
                result = await crawler.arun(url=info["url"], config=config)
                if result and result.markdown:
                    text = result.markdown[:2000].strip()
                    if text:
                        chunks.append({
                            "id": f"crawl-{i}",
                            "content": text,
                            "chunk_index": 0,
                            "metadata": {"url": info["url"], "title": info["title"]},
                            "filename": info["title"],
                            "source_type": "web",
                            "similarity": 1.0,
                        })
            except Exception as e:
                print(f"Crawl4AI error for {info['url']}: {e}")
    return chunks


async def _duckduckgo_search(query: str, max_results: int) -> list[dict]:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return []

    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "url": r.get("href", ""),
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                })
                if len(results) >= max_results:
                    break

        if not results:
            return []

        chunks = []
        async with AsyncWebCrawler() as crawler:
            for i, r in enumerate(results):
                url = r["url"]
                title = r["title"]
                snippet = r.get("body", "")
                full_text = snippet

                try:
                    config = CrawlerRunConfig(cache_mode=CacheMode.ENABLED, word_count_threshold=10)
                    crawl_result = await crawler.arun(url=url, config=config)
                    if crawl_result and crawl_result.markdown:
                        full_text = crawl_result.markdown[:2000].strip() or snippet
                except Exception:
                    pass

                if full_text:
                    chunks.append({
                        "id": f"ddg-{i}",
                        "content": full_text,
                        "chunk_index": 0,
                        "metadata": {"url": url, "title": title, "snippet": snippet},
                        "filename": title or f"DuckDuckGo {i + 1}",
                        "source_type": "web",
                        "similarity": 1.0,
                    })
        return chunks
    except Exception as e:
        print(f"DuckDuckGo search failed: {e}")
        return []


async def _search_wikipedia_for_urls(query: str, max_results: int) -> list[dict]:
    urls = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query", "list": "search",
                    "srsearch": query, "format": "json", "srlimit": max_results,
                },
                headers={"User-Agent": "InquixBot/1.0 (RAG)"},
            )
            if resp.status_code == 429:
                return urls
            resp.raise_for_status()
            results = resp.json().get("query", {}).get("search", [])

            for r in results:
                title = r["title"]
                url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                urls.append({"url": url, "title": f"Wikipedia: {title}"})
    except Exception as e:
        print(f"Wikipedia URL search failed: {e}")
    return urls


async def _gemini_search(query: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}",
                json={
                    "contents": [{"parts": [{"text": query}]}],
                    "tools": [{"google_search": {}}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return []

            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            metadata = candidates[0].get("groundingMetadata", {})

            if not text.strip():
                return []

            chunks = [{
                "id": "gemini-web-0",
                "content": text[:2000],
                "chunk_index": 0,
                "metadata": {"source": "google_search", "chunks": metadata.get("groundingChunks", [])[:5]},
                "filename": "Google Search",
                "source_type": "web",
                "similarity": 1.0,
            }]

            for i, gc in enumerate(metadata.get("groundingChunks", [])[:5]):
                web_info = gc.get("web", {})
                chunks.append({
                    "id": f"gemini-src-{i}",
                    "content": f"Source: {web_info.get('name', '')}\n{web_info.get('snippet', '')}"[:1000],
                    "chunk_index": i + 1,
                    "metadata": {"url": web_info.get("uri", ""), "title": web_info.get("name", "")},
                    "filename": web_info.get("name", "Web Source"),
                    "source_type": "web",
                    "similarity": 1.0,
                })

            return chunks
    except Exception as e:
        print(f"Gemini search failed: {e}")
        return []


async def _search_wikipedia_api(query: str, max_results: int) -> list[dict]:
    chunks = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query", "list": "search",
                    "srsearch": query, "format": "json", "srlimit": max_results,
                },
                headers={"User-Agent": "InquixBot/1.0 (RAG)"},
            )
            if resp.status_code == 429:
                return []
            resp.raise_for_status()
            results = resp.json().get("query", {}).get("search", [])

            for r in results:
                await asyncio.sleep(0.3)
                er = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query", "prop": "extracts",
                        "explaintext": 1, "pageids": r["pageid"], "format": "json",
                    },
                    headers={"User-Agent": "InquixBot/1.0 (RAG)"},
                )
                if er.status_code == 429:
                    continue
                er.raise_for_status()
                pages = er.json().get("query", {}).get("pages", {})
                page = pages.get(str(r["pageid"]), {})
                text = page.get("extract", "")

                if text.strip():
                    chunks.append({
                        "id": f"wiki-{r['pageid']}",
                        "content": text[:2000],
                        "chunk_index": 0,
                        "metadata": {"url": f"https://en.wikipedia.org/wiki/{r['title'].replace(' ', '_')}"},
                        "filename": f"Wikipedia: {r['title']}",
                        "source_type": "web",
                        "similarity": 1.0,
                    })
    except Exception as e:
        print(f"Wikipedia API failed: {e}")
    return chunks

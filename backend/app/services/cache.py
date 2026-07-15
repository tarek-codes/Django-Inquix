import json
import logging
from typing import Optional
import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[aioredis.Redis] = None

def get_redis_client() -> Optional[aioredis.Redis]:
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    redis_url = getattr(settings, "redis_url", None)
    if not redis_url:
        logger.warning("redis_url is not configured. Caching is disabled.")
        return None

    try:
        # We set decode_responses=True so we receive strings instead of bytes
        _redis_client = aioredis.from_url(redis_url, decode_responses=True)
        logger.info(f"Redis client initialized with URL: {redis_url}")
        return _redis_client
    except Exception as e:
        logger.error(f"Failed to connect to Redis at {redis_url}: {e}")
        return None

async def get_cached_val(key: str) -> Optional[str]:
    client = get_redis_client()
    if client is None:
        return None
    try:
        val = await client.get(key)
        if val is not None:
            logger.info(f"[Redis Cache Hit] Key: {key}")
        else:
            logger.info(f"[Redis Cache Miss] Key: {key}")
        return val
    except Exception as e:
        logger.error(f"Error reading from Redis cache: {e}")
        return None

async def set_cached_val(key: str, value: str, ttl_seconds: int = 86400) -> bool:
    client = get_redis_client()
    if client is None:
        return False
    try:
        await client.set(key, value, ex=ttl_seconds)
        logger.info(f"[Redis Cache Save] Key: {key} (TTL: {ttl_seconds}s)")
        return True
    except Exception as e:
        logger.error(f"Error writing to Redis cache: {e}")
        return False

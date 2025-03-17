import aioredis
import os

# 讀取 Redis 連接資訊
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

async def get_redis_client():
    return await aioredis.from_url(REDIS_URL, decode_responses=True)

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json
from shared.models import WebsiteStats
from backend.app.cache.redis_client import get_redis_client

CACHE_EXPIRATION = 15  # 快取 1 小時

async def track_visitor(db: AsyncSession):
    """紀錄訪客數據，並更新 Redis 快取"""
    today = datetime.utcnow().date()
    redis = await get_redis_client()
    cache_key = f"visitor_stats:{today}"

    # 查詢當日訪客記錄
    result = await db.execute(select(WebsiteStats).where(WebsiteStats.date == today))
    stats = result.scalars().first()

    if stats:
        stats.total_visitors += 1
        stats.daily_visitors += 1
    else:
        stats = WebsiteStats(date=today, total_visitors=1, daily_visitors=1)
        db.add(stats)

    await db.commit()

    # 更新 Redis 快取
    visitor_data = {"total_visitors": stats.total_visitors, "daily_visitors": stats.daily_visitors}
    await redis.setex(cache_key, CACHE_EXPIRATION, json.dumps(visitor_data))

async def get_visitor_stats(db: AsyncSession):
    """取得訪客統計數據，使用 Redis 快取"""
    today = datetime.utcnow().date()
    redis = await get_redis_client()
    cache_key = f"visitor_stats:{today}"

    # 嘗試從 Redis 讀取快取
    cached_data = await redis.get(cache_key)
    if cached_data:
        return json.loads(cached_data)

    # 查詢最新的統計資料
    result = await db.execute(select(WebsiteStats).where(WebsiteStats.date == today))
    stats = result.scalars().first()

    total_visitors = stats.total_visitors if stats else 0
    daily_visitors = stats.daily_visitors if stats else 0

    visitor_data = {"total_visitors": total_visitors, "daily_visitors": daily_visitors}

    # 更新 Redis 快取
    await redis.setex(cache_key, CACHE_EXPIRATION, json.dumps(visitor_data))

    return visitor_data

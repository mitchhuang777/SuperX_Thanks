from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import func
import json
import aioredis  # Redis 非同步套件
from typing import List, Dict
from shared.models import YoutubeSuperThanks, ExchangeRates, YoutubeUsers, YoutubeVideos
from backend.app.cache.redis_client import get_redis_client  # Redis 快取
from decimal import Decimal
from datetime import datetime
from typing import Dict, Optional

# Redis 快取時間 (秒)
CACHE_EXPIRATION = 15  # 5 分鐘

def json_serializable(obj):
    if isinstance(obj, Decimal):
        return float(obj)  # Decimal 轉 float
    elif isinstance(obj, datetime):
        return obj.isoformat()  # datetime 轉 ISO 格式字符串
    raise TypeError(f"Type {obj.__class__.__name__} not serializable")

async def get_video_super_thanks_summary(video_id: Optional[str], db: AsyncSession) -> Dict:
    """
    查詢某個影片的 Super Thanks 統計資訊，如果 video_id 為 None，則查詢所有影片的統計資訊。
    """

    # 連接 Redis
    redis = await get_redis_client()
    cache_key = f"video_super_thanks:{video_id}" if video_id else "video_super_thanks:all"

    # 檢查 Redis 快取
    cached_data = await redis.get(cache_key)
    if cached_data:
        return json.loads(cached_data)

    # 1. 先查詢總筆數
    count_stmt = select(func.count()).select_from(YoutubeSuperThanks)
    if video_id:
        count_stmt = count_stmt.join(YoutubeVideos, YoutubeSuperThanks.video_id == YoutubeVideos.video_id)
        count_stmt = count_stmt.where(YoutubeVideos.youtube_video_id == video_id)

    count_result = await db.execute(count_stmt)
    total_records = count_result.scalar()  # 獲取總筆數

    # 2. 查詢詳細資料
    stmt = (
        select(
            YoutubeSuperThanks.currency_code,
            YoutubeSuperThanks.amount,
            func.count().label("occurrence_count"),
            func.sum(YoutubeSuperThanks.amount).label("total_amount"),
            ExchangeRates.exchange_rate,
            (func.sum(YoutubeSuperThanks.amount) * ExchangeRates.exchange_rate).label("total_amount_twd")
        )
        .join(ExchangeRates, YoutubeSuperThanks.currency_code == ExchangeRates.currency_code)
        .group_by(YoutubeSuperThanks.currency_code, YoutubeSuperThanks.amount, ExchangeRates.exchange_rate)
        .order_by(YoutubeSuperThanks.currency_code.asc(), YoutubeSuperThanks.amount.desc())
    )

    # 如果 video_id 有值，則加上 where 條件
    if video_id:
        stmt = stmt.join(YoutubeVideos, YoutubeSuperThanks.video_id == YoutubeVideos.video_id)
        stmt = stmt.where(YoutubeVideos.youtube_video_id == video_id)

    result = await db.execute(stmt)
    data = result.mappings().all()

    # 轉換結果為字典列表
    summary_list = [
        {
            "currency_code": row["currency_code"],
            "amount": float(row["amount"]),  # 轉換 Decimal 為 float
            "occurrence_count": row["occurrence_count"],
            "total_amount": float(row["total_amount"]),  # 轉換 Decimal 為 float
            "exchange_rate": float(row["exchange_rate"]),  # 轉換 Decimal 為 float
            "total_amount_twd": float(row["total_amount_twd"]),  # 轉換 Decimal 為 float
        }
        for row in data
    ]

    # 最終返回的結果 (包含總筆數 & 詳細資料)
    final_result = {
        "total_records": total_records,
        "summary": summary_list
    }

    # 存入 Redis
    await redis.setex(cache_key, CACHE_EXPIRATION, json.dumps(final_result, default=json_serializable))

    return final_result

async def get_currency_amounts(video_id: Optional[str], db: AsyncSession):
    """
    查詢某個影片的所有 currency_code 和 amount，若 video_id 為 None，則查詢所有影片的數據 (使用 Redis 快取)。
    """
    redis = await get_redis_client()
    cache_key = f"currency_amounts:{video_id}" if video_id else "currency_amounts:all"

    # 檢查 Redis 快取
    cached_data = await redis.get(cache_key)
    if cached_data:
        return json.loads(cached_data)

    # 查詢 DB
    stmt = (
        select(
            YoutubeSuperThanks.currency_code,
            YoutubeSuperThanks.amount,
            func.count().label("occurrence_count")
        )
        .where(YoutubeSuperThanks.rate_id.isnot(None))  # 確保 rate_id 存在
        .group_by(YoutubeSuperThanks.currency_code, YoutubeSuperThanks.amount)
        .order_by(YoutubeSuperThanks.currency_code, YoutubeSuperThanks.amount.desc())
    )

    # 如果有指定 `video_id`，則加上 where 條件
    if video_id:
        stmt = stmt.join(YoutubeVideos, YoutubeSuperThanks.video_id == YoutubeVideos.video_id)
        stmt = stmt.where(YoutubeVideos.youtube_video_id == video_id)

    result = await db.execute(stmt)
    rows = result.mappings().all()

    # 轉換 RowMapping 為標準 Python 字典
    data = [dict(row) for row in rows]

    # 存入 Redis 快取
    await redis.setex(cache_key, CACHE_EXPIRATION, json.dumps(data, default=json_serializable))

    return data

async def get_super_thanks_messages(
    video_id: Optional[str], currency_code: str, amount: float, db: AsyncSession
):
    """
    查詢 `video_id` (可選) 中特定 `currency_code` 和 `amount` 的 Super Thanks 訊息 (使用 Redis 快取)。
    若 `video_id` 為 None，則查詢所有影片的相關訊息。
    """
    redis = await get_redis_client()
    cache_key = f"super_thanks_messages:{video_id or 'all'}:{currency_code}:{amount}"

    # 檢查 Redis 快取
    cached_data = await redis.get(cache_key)
    if cached_data:
        return json.loads(cached_data)

    # 查詢 DB
    stmt = (
        select(
            YoutubeUsers.username,
            YoutubeSuperThanks.message,
            YoutubeSuperThanks.currency_code,
            YoutubeSuperThanks.amount,
            YoutubeSuperThanks.recorded_at
        )
        .join(YoutubeUsers, YoutubeSuperThanks.user_id == YoutubeUsers.user_id)
        .where(YoutubeSuperThanks.currency_code == currency_code)
        .where(YoutubeSuperThanks.amount == amount)
        .where(YoutubeSuperThanks.rate_id.isnot(None))
        .order_by(YoutubeSuperThanks.recorded_at.asc())
    )

    # 如果 `video_id` 存在，則加上 `where` 條件
    if video_id:
        stmt = stmt.join(YoutubeVideos, YoutubeSuperThanks.video_id == YoutubeVideos.video_id)
        stmt = stmt.where(YoutubeVideos.youtube_video_id == video_id)

    result = await db.execute(stmt)
    rows = result.mappings().all()

    # 轉換為 JSON 可序列化格式
    data = [dict(row) for row in rows]

    # 存入 Redis 快取
    await redis.setex(cache_key, CACHE_EXPIRATION, json.dumps(data, default=json_serializable))

    return data

async def get_total_donate(video_id: str | None, db: AsyncSession):
    """
    計算某個影片或所有影片的總贊助金額 (TWD) 及捐款總筆數，並使用 Redis 快取
    """
    redis = await get_redis_client()
    cache_key = f"total_donate:{video_id if video_id else 'all'}"

    # 檢查 Redis 快取
    cached_data = await redis.get(cache_key)
    if cached_data:
        return json.loads(cached_data)

    # 建立 SQL 查詢，計算總捐款金額 (TWD) 和總筆數
    stmt = (
        select(
            func.coalesce(func.sum(YoutubeSuperThanks.amount * ExchangeRates.exchange_rate), 0).label("total_donate_twd"),
            func.count().label("total_donations")
        )
        .join(ExchangeRates, YoutubeSuperThanks.currency_code == ExchangeRates.currency_code)
        .where(YoutubeSuperThanks.rate_id.isnot(None))  # 確保有匯率
    )

    # 如果有指定 video_id，則加上篩選條件
    if video_id:
        stmt = stmt.join(YoutubeVideos, YoutubeSuperThanks.video_id == YoutubeVideos.video_id)
        stmt = stmt.where(YoutubeVideos.youtube_video_id == video_id)

    result = await db.execute(stmt)
    total_donate_twd, total_donations = result.first()

    # 存入 Redis 快取
    response_data = {
        "total_donate_twd": float(total_donate_twd),
        "total_donations": total_donations
    }
    await redis.setex(cache_key, CACHE_EXPIRATION, json.dumps(response_data, default=json_serializable))

    return response_data  # 回傳包含「總捐款金額」及「統計筆數」


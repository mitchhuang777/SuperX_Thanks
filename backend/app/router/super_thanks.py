from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.dependencies import get_db
from backend.app.crud.super_thanks import get_video_super_thanks_summary, get_currency_amounts, get_super_thanks_messages, get_total_donate
from typing import Optional

super_thanks_router = APIRouter()

@super_thanks_router.get("/super_thanks_summary")
async def super_thanks_summary(video_id: str | None = None, db: AsyncSession = Depends(get_db)):
    """
    取得某個影片的 Super Thanks 統計資訊 (支援 Redis 快取)
    """
    return await get_video_super_thanks_summary(video_id, db)


@super_thanks_router.get("/super_thanks/amounts")
async def currency_amounts(video_id: str | None = None, db: AsyncSession = Depends(get_db)):
    """
    查詢某個影片的所有 currency_code 和 amount，並回傳出現次數
    """
    return await get_currency_amounts(video_id, db)

@super_thanks_router.get("/super_thanks/messages")
async def get_super_thanks_messages_api(
    video_id: Optional[str] = Query(None, description="影片 ID，可選填"),
    currency_code: str = Query(..., description="貨幣代碼"),
    amount: float = Query(..., description="金額"),
    db: AsyncSession = Depends(get_db)
):
    """
    取得某個 `video_id` (可選) 中特定 `currency_code` 和 `amount` 的 Super Thanks 訊息。
    若 `video_id` 未填，則查詢所有影片的相關訊息。
    """
    return await get_super_thanks_messages(video_id, currency_code, amount, db)

@super_thanks_router.get("/total_donate")
async def total_donate(video_id: str | None = None, db: AsyncSession = Depends(get_db)):
    """
    取得某個影片或所有影片的總贊助金額 (TWD)
    """
    return await get_total_donate(video_id, db)
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from backend.app.dependencies import get_db
from backend.app.crud.visitor import track_visitor, get_visitor_stats

visitor_router = APIRouter()

@visitor_router.post("/track_visit", summary="紀錄訪客數據")
async def track_visit(db: AsyncSession = Depends(get_db)):
    await track_visitor(db)
    return {"message": "Visit tracked"}

@visitor_router.get("/visitor_stats", summary="取得訪客統計數據")
async def visitor_stats(db: AsyncSession = Depends(get_db)):
    stats = await get_visitor_stats(db)
    return stats
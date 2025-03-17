from sqlalchemy.ext.asyncio import AsyncSession
from shared.database import AsyncSessionLocal

async def get_db() -> AsyncSession:
    """
    FastAPI 依賴注入 - 提供異步資料庫連接
    """
    async with AsyncSessionLocal() as session:
        yield session

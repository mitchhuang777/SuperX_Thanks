from fastapi import FastAPI
from backend.app.router import super_thanks_router, visitor_router
from backend.app.middleware.security_middleware import SecurityMiddleware
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允許前端請求
    allow_credentials=False,
    allow_methods=["*"],  # 允許所有請求方法
    allow_headers=["*"],  # 允許所有請求標頭
)

# 加入安全性 Middleware
# app.add_middleware(SecurityMiddleware)

# 註冊 API
app.include_router(super_thanks_router, prefix="/api", tags=["Super Thanks"])
app.include_router(visitor_router, prefix="/api", tags=["Visitor Tracking"])

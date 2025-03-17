import os
import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict

# 允許的 Referer & IP
ALLOWED_REFERER = os.getenv("ALLOWED_REFERER", "http://localhost:5173")
ALLOWED_IPS = ["192.168.18.6", "backend.example.com", "127.0.0.1", "localhost"]

# 速率限制：每個 IP 每分鐘最多請求 30 次
RATE_LIMIT = 30
TIME_WINDOW = 60  # 單位：秒 (60s = 1分鐘)

# 封鎖時長：4 小時 (14400 秒)
BAN_DURATION = 4 * 60 * 60  

# 記錄 IP 請求次數
request_counts = defaultdict(list)

# 記錄被封鎖的 IP (key: IP, value: 解封時間)
banned_ips = {}

class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        referer = request.headers.get("referer")
        client_ip = request.client.host

        # ✅ 允許 OPTIONS/GET/POST 無限制
        if request.method in ["OPTIONS", "GET", "POST"]:
            return await call_next(request)

        # ✅ 允許白名單 IP 不受限制
        if client_ip in ALLOWED_IPS:
            return await call_next(request)

        # ✅ 被 Ban 的 IP 無法訪問
        current_time = time.time()
        if client_ip in banned_ips:
            if current_time < banned_ips[client_ip]:  # 還沒解封
                raise HTTPException(status_code=403, detail="Forbidden: Your IP is temporarily banned.")
            else:
                del banned_ips[client_ip]  # 解封

        # ✅ Referer 限制 (確保來源合法)
        if referer and not referer.startswith(ALLOWED_REFERER):
            raise HTTPException(status_code=403, detail="Forbidden: Invalid Referer")

        # 🚀 **Rate Limiting (非 ALLOWED_IPS 的限制)**
        request_times = request_counts[client_ip]

        # 移除過期請求
        request_counts[client_ip] = [t for t in request_times if current_time - t < TIME_WINDOW]

        # 若超過限制則 Ban 4 小時 & 返回 429
        if len(request_counts[client_ip]) >= RATE_LIMIT:
            banned_ips[client_ip] = current_time + BAN_DURATION  # 設定封鎖時間
            raise HTTPException(status_code=429, detail="Too Many Requests. server cry cry.")

        # 記錄當前請求
        request_counts[client_ip].append(current_time)

        # 繼續處理請求
        return await call_next(request)

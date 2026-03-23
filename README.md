# SuperX Thanks

收錄 **Threads 友**想知道的 YouTube 影片 Super Thanks（超級感謝）捐款數據的分析儀表板。

**追蹤影片：**
- [10年了！227萬訂閱眾量級CROWD「原來不是我的？！」【Andy老師】](https://www.youtube.com/watch?v=kOZWQgtqps4)
- [直球對決張家人聲明！【Andy老師】](https://www.youtube.com/watch?v=hjcTwe5BHYI)
- [財務危機後能去哪？【鍾明軒】](https://www.youtube.com/watch?v=gyDbjv_tChE)

## 功能

- 追蹤 YouTube 影片的 Super Thanks 捐款紀錄
- 多幣別支援（22+ 種貨幣），自動換算為台幣（TWD）
- 互動式捐款統計表格，可展開查看捐款留言
- 按影片篩選或查看全部統計
- 訪客人數追蹤（每日 / 總計）
- Redis 快取加速 API 回應

## Tech Stack

| 層級 | 技術 |
|------|------|
| Frontend | React 19, Vite, Tailwind CSS, Recharts |
| Backend | FastAPI, Python 3.10, Uvicorn |
| Database | MySQL (async via aiomysql) |
| Cache | Redis (aioredis) |
| ORM | SQLAlchemy 2.0 async |
| Scraper | youtube-comment-downloader |
| Deployment | Zeabur (backend + DB + Redis), Cloudflare Pages (frontend) |
| CI/CD | GitHub Actions |

## 專案結構

```
SuperX_Thanks/
├── .github/
│   └── workflows/
│       ├── deploy-frontend.yml   # 前端自動部署到 Cloudflare Pages
│       └── scraper.yml           # 每日定時執行爬蟲
├── backend/
│   └── app/
│       ├── cache/
│       │   └── redis_client.py   # Redis 連線管理
│       ├── crud/
│       │   ├── super_thanks.py   # Super Thanks 資料庫操作
│       │   └── visitor.py        # 訪客追蹤資料庫操作
│       ├── middleware/
│       │   └── security_middleware.py
│       ├── router/
│       │   ├── super_thanks.py   # Super Thanks API 路由
│       │   └── visitor.py        # 訪客追蹤 API 路由
│       ├── dependencies.py       # 依賴注入
│       └── main.py               # FastAPI 應用程式入口
├── frontend/
│   └── super-thanks/
│       ├── src/
│       │   ├── App.jsx           # 主要儀表板元件
│       │   └── main.jsx          # React 入口點
│       ├── config.js             # API URL 設定
│       └── package.json
├── shared/
│   ├── database.py               # 資料庫連線設定
│   ├── models.py                 # SQLAlchemy ORM models
│   ├── log_manager.py            # 日誌管理
│   ├── utils.py                  # 共用工具函數
│   └── .env.example              # 環境變數範例
├── scraper/
│   ├── youtube_scraper.py        # YouTube 爬蟲主程式
│   └── crud.py                   # 爬蟲資料庫操作
├── scripts/
│   └── init_db.py                # 資料庫初始化腳本
├── requirements.txt              # 後端依賴
├── requirements-scraper.txt      # 爬蟲依賴
└── zbpack.json                   # Zeabur 部署設定
```

## 本機開發

### 環境需求

- Python 3.10+
- Node.js 20+
- MySQL
- Redis

### 後端

```bash
# 安裝依賴
pip install -r requirements.txt

# 複製環境變數設定
cp shared/.env.example shared/.env.dev
# 編輯 shared/.env.dev 填入你的資料庫資訊

# 初始化資料庫（建立 tables）
python -m scripts.init_db

# 啟動後端
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端

```bash
cd frontend/super-thanks

# 安裝依賴
npm install

# 複製環境變數設定
cp .env.example .env

# 啟動開發伺服器
npm run dev
```

### 執行爬蟲

```bash
pip install -r requirements-scraper.txt
python -m scraper.youtube_scraper
```

## 環境變數

### 後端 (`shared/.env.dev`)

參考 [`shared/.env.example`](shared/.env.example)

| 變數 | 說明 |
|------|------|
| `ENV` | 環境標識（`dev` / `prod`） |
| `DB_HOST` | MySQL 主機位址 |
| `DB_USER` | MySQL 使用者名稱 |
| `DB_PASS` | MySQL 密碼 |
| `DB_PORT` | MySQL 連接埠 |
| `DB_NAME` | 資料庫名稱 |
| `REDIS_URL` | Redis 連線 URL |
| `DEBUG` | 是否開啟 SQL 日誌 |

### 前端 (`frontend/super-thanks/.env`)

| 變數 | 說明 |
|------|------|
| `VITE_API_BASE_URL` | 後端 API 網址 |

## API 端點

Base URL: `/api`

| Method | Endpoint | Query Params | 說明 |
|--------|----------|-------------|------|
| GET | `/super_thanks_summary` | `video_id` (optional) | Super Thanks 統計摘要 |
| GET | `/super_thanks/amounts` | `video_id` (optional) | 各幣別金額分布 |
| GET | `/super_thanks/messages` | `video_id`, `currency_code`, `amount` | 捐款留言列表 |
| GET | `/total_donate` | `video_id` (optional) | 總捐款金額（TWD）及筆數 |
| POST | `/track_visit` | - | 記錄訪客 |
| GET | `/visitor_stats` | - | 訪客統計 |

API 文件：`http://localhost:8000/docs`

## 部署

### 後端（Zeabur）

1. 連結 GitHub repo 到 Zeabur
2. 在 Zeabur 新增 MySQL 和 Redis 服務
3. 設定後端環境變數（參考 `shared/.env.example`）
4. 初始化資料庫：`python -m scripts.init_db`

### 前端（Cloudflare Pages）

透過 GitHub Actions 自動部署，需在 GitHub Secrets 設定：

| Secret | 說明 |
|--------|------|
| `VITE_API_BASE_URL` | 後端 API 網址 |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API Token |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare 帳號 ID |
| `CLOUDFLARE_PAGES_PROJECT_NAME` | Cloudflare Pages 專案名稱 |

### 爬蟲（GitHub Actions 排程）

每天 UTC 18:00（台灣時間凌晨 2:00）自動執行，需在 GitHub Secrets 設定：

| Secret | 說明 |
|--------|------|
| `DB_HOST` | 資料庫主機 |
| `DB_USER` | 資料庫使用者 |
| `DB_PASS` | 資料庫密碼 |
| `DB_PORT` | 資料庫連接埠 |
| `DB_NAME` | 資料庫名稱 |

---

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-支持開發者-yellow?style=for-the-badge&logo=buy-me-a-coffee)](https://buymeacoffee.com/huangmitch)

import asyncio
import time
from playwright.async_api import async_playwright
from shared.utils import detect_new_comments, scroll_down, scroll_to_element, wait_and_click, wait_for_text_and_click
from shared.log_manager import log_manager
from scraper.crud import create_super_thanks_bulk
from shared.database import get_db
import re
import decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from youtube_comment_downloader import YoutubeCommentDownloader, SORT_BY_RECENT
import requests
import uuid
from shared.models import YoutubeSuperThanks
from sqlalchemy.ext.asyncio import AsyncSession


# ✅ 取得即時匯率
def get_exchange_rates():
    api_url = "https://api.exchangerate-api.com/v4/latest/TWD"
    try:
        response = requests.get(api_url)
        data = response.json()
        return data.get("rates", {})
    except Exception as e:
        print(f"⚠️ 無法獲取即時匯率: {e}")
        return {}

exchange_rates = get_exchange_rates()

# ✅ 貨幣對應表
currency_map = {
    "HK": "HKD", "SG": "SGD", "NT": "TWD", "US": "USD",
    "MY": "MYR", "JP": "JPY", "KR": "KRW", "CN": "CNY",
    "EU": "EUR", "ID": "IDR", "TH": "THB", "PH": "PHP",
    "AU": "AUD", "CAD": "CAD", "CHF": "CHF", "NZ": "NZD",
    "IN": "INR", "MX": "MXN", "BR": "BRL", "SEK": "SEK",
    "NOK": "NOK", "ZAR": "ZAR", "RUB": "RUB", "TRY": "TRY",
    "SAR": "SAR", "AED": "AED"
}

symbol_to_currency = {
    "£": "GBP", "€": "EUR", "¥": "JPY", "₩": "KRW",
    "₹": "INR", "₽": "RUB", "₺": "TRY", "₴": "UAH",
    "₱": "PHP", "₦": "NGN", "₡": "CRC", "₪": "ILS",
    "₫": "VND", "฿": "THB", "₭": "LAK", "₲": "PYG",
    "₵": "GHS"
}

# ✅ 初始化 YouTube 留言下載器
downloader = YoutubeCommentDownloader()

async def fetch_super_thanks(video_url: str, db: AsyncSession):
    """ 爬取影片的 Super Thanks 留言並寫入資料庫 """
    
    print("\n🔄 正在爬取超級留言...")
    start_time = time.perf_counter()
    
    # ✅ 影片 ID
    match = re.search(r"v=([\w-]+)", video_url)
    if not match:
        print(f"❌ 無效的 YouTube 影片 URL: {video_url}")
        return
    youtube_video_id = match.group(1)

    # ✅ **獲取留言 (非同步爬取)**
    comment_generator = downloader.get_comments_from_url(video_url, sort_by=SORT_BY_RECENT)
    comments = []

    for index, comment in enumerate(comment_generator, 1):
        elapsed_time = int(time.perf_counter() - start_time)
        print(f"\r⏳ 已執行 {elapsed_time} 秒，已抓取 {index} 筆留言", end="", flush=True)
        comments.append(comment)

    print("\n✅ 留言抓取完成，開始處理...")

    # ✅ **多線程解析留言**
    processed_comments = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_comment, comment, youtube_video_id) for comment in comments]
        for future in as_completed(futures):
            result = future.result()
            if result:
                processed_comments.append(result)

    # ✅ **將 Super Thanks 留言存入資料庫**
    await create_super_thanks_bulk(db, processed_comments)

    elapsed_time = int(time.perf_counter() - start_time)
    print(f"\n✅ 資料處理完成！總共用時 {elapsed_time} 秒，已存入 {len(processed_comments)} 筆留言")

def process_comment(comment, youtube_video_id):
    """ 處理單條留言，解析捐款金額、貨幣與使用者資訊 """

    if "paid" in comment and comment["paid"]:
        return {
            "cid": comment["cid"],  # 留言 ID
            "username": comment["author"],
            "user_avatar": comment.get("photo", None),
            "youtube_video_id": youtube_video_id,
            "full_amount_text": comment["paid"],
            "message": comment.get("text", ""),
            "currency_code": extract_currency_and_amount(comment["paid"])[0],
            "amount": decimal.Decimal(extract_currency_and_amount(comment["paid"])[1].replace(",", "")),
        }
    return None

def extract_currency_and_amount(amount_text: str):
    """ 解析金額與貨幣代碼 """
    match = re.match(r"([^\d]+)?([\d,.]+)", amount_text.strip())
    if match:
        symbol = match.group(1) or ""
        amount_value = match.group(2) or "0"

        # 先從 `symbol_to_currency` 轉換
        currency_code = symbol_to_currency.get(symbol.strip(), None)
        if not currency_code:
            currency_code = currency_map.get(symbol.strip(), None)
        if not currency_code:
            currency_code = symbol.strip()  # 直接使用原符號

        return currency_code, amount_value
    return "", "0"

# ✅ **主函數**
async def main():
    video_urls = [
        "https://www.youtube.com/watch?v=hjcTwe5BHYI",
        "https://www.youtube.com/watch?v=kOZWQgtqps4"
    ]
    
    async for db in get_db():  # 只建立一次 DB 連線
        for video_url in video_urls:
            await fetch_super_thanks(video_url, db)

# ✅ **啟動爬蟲**
if __name__ == "__main__":
    asyncio.run(main())


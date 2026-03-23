import asyncio
import time
from scraper.crud import create_super_thanks_bulk
from shared.database import get_db
import re
import decimal
from youtube_comment_downloader import YoutubeCommentDownloader, SORT_BY_RECENT
import requests


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
    "HK": "HKD", "HK$": "HKD",
    "SG": "SGD", "SG$": "SGD",
    "NT": "TWD", "NT$": "TWD",
    "US": "USD", "US$": "USD",
    "CA": "CAD", "CA$": "CAD",
    "AU": "AUD", "AU$": "AUD",
    "NZ": "NZD", "NZ$": "NZD",
    "MY": "MYR", "JP": "JPY", "KR": "KRW", "CN": "CNY",
    "EU": "EUR", "ID": "IDR", "TH": "THB", "PH": "PHP",
    "CAD": "CAD", "CHF": "CHF",
    "IN": "INR", "MX": "MXN", "BR": "BRL", "SEK": "SEK",
    "NOK": "NOK", "ZAR": "ZAR", "RUB": "RUB", "TRY": "TRY",
    "SAR": "SAR", "AED": "AED"
}

symbol_to_currency = {
    "£": "GBP", "€": "EUR", "¥": "JPY", "₩": "KRW", "￦": "KRW",
    "₹": "INR", "₽": "RUB", "₺": "TRY", "₴": "UAH",
    "₱": "PHP", "₦": "NGN", "₡": "CRC", "₪": "ILS",
    "₫": "VND", "฿": "THB", "₭": "LAK", "₲": "PYG",
    "₵": "GHS", "$": "TWD",  # 單純 $ 視為台幣
}

# ✅ 初始化 YouTube 留言下載器
downloader = YoutubeCommentDownloader()

BATCH_SIZE = 500  # 每批寫入筆數
LOG_INTERVAL = 100  # 每抓取幾筆印一次進度

async def fetch_super_thanks(video_url: str):
    """ 爬取影片的 Super Thanks 留言並分批寫入資料庫 """

    print(f"\n🔄 正在爬取超級留言: {video_url}")
    start_time = time.perf_counter()

    # ✅ 影片 ID
    match = re.search(r"v=([\w-]+)", video_url)
    if not match:
        print(f"❌ 無效的 YouTube 影片 URL: {video_url}")
        return
    youtube_video_id = match.group(1)

    comment_generator = downloader.get_comments_from_url(video_url, sort_by=SORT_BY_RECENT)
    batch = []
    total_saved = 0

    for index, comment in enumerate(comment_generator, 1):
        batch.append(comment)

        if index % LOG_INTERVAL == 0:
            elapsed_time = int(time.perf_counter() - start_time)
            print(f"⏳ 已執行 {elapsed_time} 秒，已抓取 {index} 筆留言（已存入 {total_saved} 筆）", flush=True)

        if len(batch) >= BATCH_SIZE:
            processed = [r for r in (process_comment(c, youtube_video_id) for c in batch) if r]
            if processed:
                async for db in get_db():
                    await create_super_thanks_bulk(db, processed)
                total_saved += len(processed)
            elapsed_time = int(time.perf_counter() - start_time)
            print(f"💾 批次寫入完成：已存入 {total_saved} 筆（{elapsed_time} 秒）", flush=True)
            batch = []

    # ✅ 處理最後一批
    if batch:
        processed = [r for r in (process_comment(c, youtube_video_id) for c in batch) if r]
        if processed:
            async for db in get_db():
                await create_super_thanks_bulk(db, processed)
            total_saved += len(processed)

    elapsed_time = int(time.perf_counter() - start_time)
    print(f"\n✅ 完成！總共用時 {elapsed_time} 秒，已存入 {total_saved} 筆 Super Thanks")

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

    for video_url in video_urls:
        await fetch_super_thanks(video_url)

# ✅ **啟動爬蟲**
if __name__ == "__main__":
    asyncio.run(main())

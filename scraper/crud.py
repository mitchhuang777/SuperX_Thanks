from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
import decimal
import datetime
import uuid
import re
from shared.models import YoutubeSuperThanks, YoutubeUsers, ExchangeRates, YoutubeVideos
from shared.log_manager import log_manager
from pytz import timezone
import requests
from sqlalchemy.sql import insert
from sqlalchemy.dialects.mysql import insert as mysql_insert

# 設定台灣時區
taiwan_tz = timezone("Asia/Taipei")

# 設定台灣時區的 `recorded_at`
recorded_at_taiwan = datetime.datetime.utcnow().replace(tzinfo=timezone("UTC")).astimezone(taiwan_tz)

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

# ✅ 取得即時匯率（回傳 1 外幣 = N TWD）
def get_exchange_rates():
    api_url = "https://api.exchangerate-api.com/v4/latest/TWD"
    try:
        response = requests.get(api_url)
        data = response.json()
        rates_twd_base = data.get("rates", {})  # 1 TWD = X 外幣
        return {code: 1 / rate for code, rate in rates_twd_base.items() if rate > 0}
    except Exception as e:
        print(f"⚠️ 無法獲取即時匯率: {e}")
        return {}

# DB 裡的符號型 currency_code → ISO code 對應（用於查匯率 API）
symbol_code_to_iso = {
    "AU$": "AUD",
    "HK$": "HKD",
    "US$": "USD",
    "CA$": "CAD",
    "NZ$": "NZD",
    "SG$": "SGD",
    "NT$": "TWD",
    "￦": "KRW",
    # "$" 視為台幣，保持 1.000
}

async def upsert_exchange_rates(db: AsyncSession, required_currency_codes: set):
    """
    更新 `exchange_rates` 資料表，確保 `required_currency_codes` 都有對應的 `exchange_rate`。
    - 如果 `currency_code` 不存在，則新增並寫入即時匯率
    - 如果 `currency_code` 已存在，則更新即時匯率
    """
    # 取得 API 匯率（1 外幣 = N TWD）
    exchange_rates = get_exchange_rates()

    # 查詢已存在的匯率資料
    existing_rates_query = await db.execute(
        select(ExchangeRates).where(ExchangeRates.currency_code.in_(required_currency_codes))
    )
    existing_rates = {r.currency_code: r for r in existing_rates_query.scalars().all()}

    new_rates = []
    for currency_code in required_currency_codes:
        iso_code = symbol_code_to_iso.get(currency_code, currency_code)
        rate_value = decimal.Decimal(str(round(exchange_rates[iso_code], 6))) if iso_code in exchange_rates else decimal.Decimal("1.000")

        if currency_code not in existing_rates:
            # 新增
            new_rates.append(ExchangeRates(
                rate_id=str(uuid.uuid4()),
                currency_code=currency_code,
                currency_name=currency_code,
                currency_symbol=currency_code,
                exchange_rate=rate_value,
                created_at=recorded_at_taiwan,
                updated_at=recorded_at_taiwan
            ))
        else:
            # 更新既有匯率
            existing_rates[currency_code].exchange_rate = rate_value
            existing_rates[currency_code].updated_at = recorded_at_taiwan

    if new_rates:
        db.add_all(new_rates)
        await db.flush()

    print(f"✅ `exchange_rates` 更新完成！")

async def update_all_exchange_rates(db: AsyncSession):
    """爬蟲啟動時，更新 DB 裡所有已存在的匯率"""
    exchange_rates = get_exchange_rates()
    result = await db.execute(select(ExchangeRates))
    all_rates = result.scalars().all()

    for r in all_rates:
        iso_code = symbol_code_to_iso.get(r.currency_code, r.currency_code)
        if iso_code in exchange_rates:
            r.exchange_rate = decimal.Decimal(str(round(exchange_rates[iso_code], 6)))
            r.updated_at = recorded_at_taiwan

    await db.commit()
    print(f"✅ 所有匯率更新完成（共 {len(all_rates)} 筆）")

async def create_super_thanks_bulk(db: AsyncSession, comments_data: list):
    """批量 UPSERT Super Thanks 留言，確保相關外鍵數據存在，並避免重複儲存"""

    await upsert_exchange_rates(db, set([c["currency_code"] for c in comments_data]))

    if not comments_data:
        return  # 沒有數據時，直接返回

    # **準備 UPSERT `YoutubeUsers`**
    for comment in comments_data:
        username = comment["username"]
        user_avatar = comment.get("user_avatar", None)
        user_id = str(uuid.uuid4())  # 生成 `VARCHAR(36)`

        stmt_user = mysql_insert(YoutubeUsers).values(
            user_id=user_id,
            username=username,
            user_avatar=user_avatar,
            updated_at=recorded_at_taiwan,
        ).on_duplicate_key_update(
            user_avatar=user_avatar,
            updated_at=recorded_at_taiwan
        )
        await db.execute(stmt_user)

    # **準備 UPSERT `YoutubeSuperThanks`**
    for comment in comments_data:
        thanks_id = str(uuid.uuid4())  # 保留原本的 `thanks_id`
        cid = comment["cid"]  # 新增 `cid` 欄位
        username = comment["username"]
        youtube_video_id = comment["youtube_video_id"]
        currency_code = comment["currency_code"]  # 已經拆好的貨幣
        amount = decimal.Decimal(comment["amount"])  # 已經拆好的金額
        full_amount_text = comment["full_amount_text"]
        message = comment.get("message", None)

        # 查找關聯 `user_id`
        user_query = await db.execute(select(YoutubeUsers).where(YoutubeUsers.username == username))
        user = user_query.scalars().first()

        # 查找關聯 `video_id`
        video_query = await db.execute(select(YoutubeVideos).where(YoutubeVideos.youtube_video_id == youtube_video_id))
        video = video_query.scalars().first()

        # 2. 如果找不到，建立新的一筆
        if not video:
            new_video = YoutubeVideos(
                video_id=str(uuid.uuid4()),   # 用 UUID 做 PK
                youtube_video_id=youtube_video_id,
                video_title="Unknown Title",  # 預設值
                video_url=f"https://www.youtube.com/watch?v={youtube_video_id}",
                created_at=recorded_at_taiwan,
                updated_at=recorded_at_taiwan
            )
            db.add(new_video)
            # 使用 flush() 可以取得新物件的 PK （video_id)）
            await db.flush()
            # flush 之後 new_video.video_id 就可以被拿來用
            video = new_video
        
        # 4️⃣ 查找或建立 `rate_id`
        rate_query = await db.execute(select(ExchangeRates).where(ExchangeRates.currency_code == currency_code))
        rate = rate_query.scalars().first()

        # **UPSERT Super Thanks**
        stmt_thanks = mysql_insert(YoutubeSuperThanks).values(
            thanks_id=thanks_id,
            cid=cid,
            user_id=user.user_id,
            video_id=video.video_id,
            rate_id=rate.rate_id,
            amount=amount,
            currency_code=currency_code,
            full_amount_text=full_amount_text,
            message=message,
            recorded_at=recorded_at_taiwan,
            created_at=recorded_at_taiwan,
            updated_at=recorded_at_taiwan
        ).on_duplicate_key_update(
            amount=amount,
            message=message,
            recorded_at=recorded_at_taiwan,
            updated_at=recorded_at_taiwan
        )
        await db.execute(stmt_thanks)

    # **提交變更**
    await db.commit()

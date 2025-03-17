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

# 設定台灣時區
taiwan_tz = timezone("Asia/Taipei")

# 設定台灣時區的 `recorded_at`
recorded_at_taiwan = datetime.datetime.utcnow().replace(tzinfo=timezone("UTC")).astimezone(taiwan_tz)

async def create_super_thanks_bulk(db: AsyncSession, comments_data: list):
    """批量寫入 Super Thanks 留言，確保相關外鍵數據存在，並避免重複儲存 `currency_code`"""
    
    if not comments_data:
        return  # 沒有數據時，直接返回

    video_ids = {c["youtube_video_id"] for c in comments_data}
    usernames = {c["username"] for c in comments_data}
    full_amount_texts = {c["full_amount_text"] for c in comments_data if c["full_amount_text"]}

    # **解析所有貨幣並存入集合**
    parsed_currencies = set()
    for text in full_amount_texts:
        currency_code, _ = extract_currency_and_amount(text)
        if currency_code:
            parsed_currencies.add(currency_code)

    # **查詢已存在的影片**
    existing_videos = await db.execute(select(YoutubeVideos).filter(YoutubeVideos.youtube_video_id.in_(video_ids)))
    video_map = {v.youtube_video_id: v for v in existing_videos.scalars().all()}

    # **查詢已存在的使用者**
    existing_users = await db.execute(select(YoutubeUsers).filter(YoutubeUsers.username.in_(usernames)))
    user_map = {u.username: u for u in existing_users.scalars().all()}

    # **查詢已存在的貨幣**
    existing_rates = await db.execute(select(ExchangeRates).filter(ExchangeRates.currency_code.in_(parsed_currencies)))
    rate_map = {r.currency_code: r for r in existing_rates.scalars().all()}

    # **批量建立缺失的影片**
    new_videos = []
    for youtube_video_id in video_ids:
        if youtube_video_id not in video_map:
            new_video = YoutubeVideos(
                video_id=str(uuid.uuid4()),
                youtube_video_id=youtube_video_id,
                video_title="Unknown Video",
                video_url=f"https://www.youtube.com/watch?v={youtube_video_id}",
                created_at=recorded_at_taiwan,
                updated_at=recorded_at_taiwan
            )
            new_videos.append(new_video)
            video_map[youtube_video_id] = new_video
    
    if new_videos:
        db.add_all(new_videos)
        await db.commit()
    
    # **批量建立缺失的使用者**
    new_users = []
    for username in usernames:
        if username not in user_map:
            new_user = YoutubeUsers(
                user_id=str(uuid.uuid4()),
                username=username
            )
            new_users.append(new_user)
            user_map[username] = new_user
    
    if new_users:
        db.add_all(new_users)
        await db.commit()
    
    # **批量建立缺失的貨幣**
    new_rates = []
    for currency_code in parsed_currencies:
        if currency_code not in rate_map:
            new_rate = ExchangeRates(
                rate_id=str(uuid.uuid4()),
                currency_code=currency_code,
                currency_name="Unknown Currency",
                currency_symbol=currency_code,  # 直接存完整貨幣代碼
                exchange_rate=decimal.Decimal("1.00"),
                created_at=recorded_at_taiwan,
                updated_at=recorded_at_taiwan
            )
            new_rates.append(new_rate)
            rate_map[currency_code] = new_rate
    
    if new_rates:
        db.add_all(new_rates)
        await db.commit()

    # **準備批量插入 Super Thanks**
    new_thanks_records = []
    for comment in comments_data:
        username = comment["username"]
        youtube_video_id = comment["youtube_video_id"]
        full_amount_text = comment["full_amount_text"]
        message = comment["message"]

        # 解析金額與貨幣
        currency_code, amount_value = extract_currency_and_amount(full_amount_text)

        try:
            amount = decimal.Decimal(amount_value.replace(",", "")) if amount_value else decimal.Decimal("0.00")
        except Exception:
            amount = decimal.Decimal("0.00")

        # 設定 `rate_id`
        rate_id = rate_map.get(currency_code, None).rate_id if currency_code in rate_map else None

        # **建立 Super Thanks 記錄**
        new_thanks = YoutubeSuperThanks(
            thanks_id=str(uuid.uuid4()),
            user_id=user_map[username].user_id,
            video_id=video_map[youtube_video_id].video_id,
            rate_id=rate_id,  # 若無捐款則為 `None`
            amount=amount,
            currency_code=currency_code,
            full_amount_text=full_amount_text,  # 儲存完整金額字串
            message=message,
            recorded_at=recorded_at_taiwan,
            created_at=recorded_at_taiwan,
            updated_at=recorded_at_taiwan
        )
        new_thanks_records.append(new_thanks)

    # **批量寫入 Super Thanks**
    if new_thanks_records:
        db.add_all(new_thanks_records)
        await db.commit()

def extract_currency_and_amount(amount_text: str):
    """
    從 `amount_text` 解析貨幣符號與金額
    例如：
        - "HK$78.00" => ("HK$", "78.00")
        - "AU$7.99" => ("AU$", "7.99")
        - "$5.00" => ("$", "5.00")
    """

    match = re.match(r"([^\d]+)?([\d,.]+)", amount_text.strip())
    if match:
        symbol = match.group(1) or ""  # 取得貨幣符號
        amount_value = match.group(2) or "0"  # 取得金額

        return symbol.strip(), amount_value  # 直接回傳貨幣符號
    else:
        return "", "0"

async def create_super_thanks(
    db: AsyncSession, 
    username: str, 
    youtube_video_id: str, 
    amount_text: str, 
    message: str
):
    """
    新增一筆 Super Thanks 記錄到 `youtube_super_thanks` 資料表。
    """

    # Step 1: 確保 `youtube_videos` 表有該 `video_id`
    result = await db.execute(select(YoutubeVideos).filter(YoutubeVideos.youtube_video_id == youtube_video_id))
    video = result.scalars().first()

    if not video:
        video = YoutubeVideos(
            video_id=str(uuid.uuid4()),  # UUID
            youtube_video_id=youtube_video_id,
            video_title="Unknown Video",
            video_url=f"https://www.youtube.com/watch?v={youtube_video_id}",
            created_at=recorded_at_taiwan,
            updated_at=recorded_at_taiwan
        )
        db.add(video)
        await db.commit()
        await db.refresh(video)

    # Step 2: 確保 `youtube_users` 表有該使用者
    result = await db.execute(select(YoutubeUsers).filter(YoutubeUsers.username == username))
    user = result.scalars().first()
    
    if not user:
        user = YoutubeUsers(user_id=str(uuid.uuid4()), username=username)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    user_id = user.user_id

    # Step 3: **解析 `amount_text`，提取 `currency_code` 和 `amount`**
    full_amount_text = amount_text.strip()  # ✅ 存完整的金額資訊
    currency_symbol = ""
    amount_value = "0"

    # 正則表達式：解析貨幣符號與數值（允許不同格式）
    match = re.match(r"^([^\d]+)?\s?([\d,]+\.?\d*)$", full_amount_text)
    if match:
        currency_symbol = match.group(1).strip() if match.group(1) else ""  # 取得貨幣符號
        amount_value = match.group(2).strip() if match.group(2) else "0"  # 取得數值

    # 移除 `,` 並轉換為 `decimal.Decimal`
    try:
        amount = decimal.Decimal(amount_value.replace(",", ""))
    except Exception:
        amount = decimal.Decimal("0.00")

    # Step 4: 檢查 `exchange_rates` 表是否有該 `currency_symbol`
    rate_id = None  
    currency_code = None

    if currency_symbol and amount > 0:  # 只有捐款才記錄貨幣
        result = await db.execute(select(ExchangeRates).filter(ExchangeRates.currency_symbol == currency_symbol))
        rate = result.scalars().first()
        
        if not rate:
            # 若找不到匯率，新增預設匯率（1:1）
            rate = ExchangeRates(
                rate_id=uuid.uuid4(),
                currency_code=currency_symbol,  # 直接使用貨幣代碼
                currency_name="Unknown Currency",
                currency_symbol=currency_symbol,
                exchange_rate=decimal.Decimal("1.00"),
                created_at=recorded_at_taiwan,
                updated_at=recorded_at_taiwan
            )
            db.add(rate)
            await db.commit()
            await db.refresh(rate)

        rate_id = rate.rate_id
        currency_code = rate.currency_code

    # Step 5: **新增 Super Thanks 資料**
    new_thanks = YoutubeSuperThanks(
        thanks_id=uuid.uuid4(),
        user_id=user_id,
        video_id=video.video_id,  # 使用 UUID
        rate_id=rate_id,  # 若無捐款則為 `None`
        amount=amount,
        currency_code=currency_code,  # 若無捐款則為 `None`
        full_amount_text=full_amount_text,  # ✅ 儲存原始金額資訊
        message=message,
        recorded_at=recorded_at_taiwan,  
        created_at=recorded_at_taiwan,
        updated_at=recorded_at_taiwan,
    )

    db.add(new_thanks)
    await db.commit()
    await db.refresh(new_thanks)

    return new_thanks

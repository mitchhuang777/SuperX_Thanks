import asyncio
import time
from playwright.async_api import async_playwright
from shared.utils import detect_new_comments, scroll_down, scroll_to_element, wait_and_click, wait_for_text_and_click
from shared.log_manager import log_manager
from scraper.crud import create_super_thanks, create_super_thanks_bulk
from shared.database import get_db
import re
import decimal

YOUTUBE_VIDEO_URL = "https://www.youtube.com/watch?v={youtube_video_id}"
BATCH_SIZE = 500
TIMEOUT_SECONDS = 600

async def scroll_continuously(page):
    """持續向下滾動直到 out of memory 或程式手動停止"""
    try:
        while True:
            await scroll_down(page, pixels=2000)
            await asyncio.sleep(0.1)  # 稍微等待，避免過快滾動
    except Exception as e:
        log_manager.log(f"滾動時發生錯誤: {e}")

async def fetch_comments(page, db, youtube_video_id):
    """擷取所有 Super Thanks 留言，直到 600 秒內留言數量無變化"""

    comments_batch = []
    # 拆開兩個計數器
    processed_comment_count = 0      # 專門用來追蹤已處理的留言 (ytd-comment-thread-renderer)
    processed_total_count = 0        # 總處理數 (留言 + xx 則回覆按鈕等)
    
    last_comment_count = 0
    last_update_time = time.time()

    log_manager.log("開始擷取留言...")

    try:
        while True:
            # 取得當前所有留言 (ytd-comment-thread-renderer)
            comment_threads = await page.query_selector_all("ytd-comment-thread-renderer")
            current_comment_count = len(comment_threads)

            # 用 processed_comment_count 來「切片」取得新留言
            new_comments = comment_threads[processed_comment_count:]
            log_manager.log(f"總共 {current_comment_count} 筆留言，其中新留言 {len(new_comments)} 筆")

            # 若留言數量無變化超過 TIMEOUT_SECONDS，則停止爬取
            if current_comment_count == last_comment_count:
                elapsed_time = time.time() - last_update_time
                if elapsed_time > TIMEOUT_SECONDS:
                    log_manager.log(f"{TIMEOUT_SECONDS} 秒內無新留言，爬取結束。")
                    break
            else:
                last_comment_count = current_comment_count
                last_update_time = time.time()  # 重置計時器

            # (1) 先處理「新留言」
            for comment_thread in new_comments:
                try:
                    author_element = await comment_thread.query_selector('#author-text span')
                    author = await author_element.inner_text() if author_element else None

                    # (a) 展開完整留言內容（若有「顯示完整內容」按鈕）
                    show_more_button = await comment_thread.query_selector('tp-yt-paper-button#more')
                    if show_more_button and await show_more_button.is_visible():
                        await show_more_button.click()
                        await asyncio.sleep(0.1)

                    # (b) 抓取留言內容
                    comment_text_element = await comment_thread.query_selector('yt-attributed-string#content-text')
                    comment_text = await comment_text_element.inner_text() if comment_text_element else None

                    # (c) 抓取 Super Thanks 金額
                    super_thanks_chip = await comment_thread.query_selector('yt-pdg-comment-chip-renderer#paid-comment-chip')
                    amount_text_element = await super_thanks_chip.query_selector('#comment-chip-price') if super_thanks_chip else None
                    full_amount_text = await amount_text_element.inner_text() if amount_text_element else ""
                    full_amount_text = full_amount_text.strip() if full_amount_text else ""

                    # 解析金額
                    currency_symbol, amount_value = "", "0"
                    match = re.match(r"^([^\d]+)?\s?([\d,]+\.?\d*)$", full_amount_text)
                    if match:
                        currency_symbol = (match.group(1).strip() if match.group(1) else "")
                        amount_value = (match.group(2).strip() if match.group(2) else "0")
                    try:
                        amount = decimal.Decimal(amount_value.replace(",", ""))
                    except:
                        amount = decimal.Decimal("0.00")

                    # 加到批量清單
                    comments_batch.append({
                        "username": author,
                        "youtube_video_id": youtube_video_id,
                        "currency_code": currency_symbol,
                        "amount": amount,
                        "full_amount_text": full_amount_text,
                        "message": comment_text
                    })

                    # 更新計數器
                    processed_comment_count += 1   # 已處理的留言 +1
                    processed_total_count += 1     # 總處理數量(含回覆按鈕) 也 +1

                    log_message = (
                        f"留言 #{processed_comment_count} (Total={processed_total_count}): "
                        f"{author} | {full_amount_text} | {comment_text[:50] if comment_text else ''}"
                    )
                    print(log_message)
                    log_manager.log(log_message)

                except Exception as e:
                    log_manager.log(f"擷取留言失敗: {e}")

            # (2) **處理「xx 則回覆」按鈕**
            total_replies = 0

            for thread in new_comments:
                try:
                    # 找到這條留言底下的「則回覆」按鈕
                    reply_button = await thread.query_selector("ytd-button-renderer#more-replies")

                    if reply_button:
                        text = await reply_button.inner_text() or ""

                        # 提取 "2 則回覆" 這種數字
                        match = re.search(r"(\d+)", text)
                        if match:
                            reply_count = int(match.group(1))
                            total_replies += reply_count  # 累加回覆數量

                        # 刪除回覆按鈕
                        await reply_button.evaluate("node => node.remove()")

                except Exception as e:
                    log_manager.log(f"⚠️ 無法處理回覆按鈕: {e}")

            # 更新總處理數量
            processed_total_count += total_replies
            log_manager.log(f"回覆按鈕 (Total={processed_total_count}): {total_replies} 條回覆")

            for thread in new_comments:
                await thread.evaluate("""
                    (node) => {
                        let header = node.querySelector("#header-author");
                        if (header) {
                            while (node.firstChild) {
                                node.removeChild(node.firstChild);
                            }
                            node.appendChild(header);
                        } else {
                            node.remove();
                        }
                    }
                """)

            # (5) 滾動頁面，等待更多留言載入
            await scroll_down(page, pixels=6000)

            # (6) 批量寫入資料庫
            if len(comments_batch) >= BATCH_SIZE:
                await create_super_thanks_bulk(db, comments_batch)
                log_manager.log(f"已批量寫入 {len(comments_batch)} 筆留言到資料庫")
                comments_batch = []

        # 迴圈跳出後，確保剩餘的留言寫入資料庫
        if comments_batch:
            await create_super_thanks_bulk(db, comments_batch)
            log_manager.log(f"已寫入最後 {len(comments_batch)} 筆留言到資料庫")

    except Exception as e:
        log_manager.log(f"⚠️ 擷取留言時發生錯誤: {e}")
        log_manager.log(f"當前已處理 {processed_comment_count} 筆留言 (含SuperThanks)，"
                        f"總處理數量(含回覆按鈕)={processed_total_count}，"
                        f"尚有 {len(comments_batch)} 筆尚未寫入DB")
    finally:
        # 最後保險寫一次
        if comments_batch:
            await create_super_thanks_bulk(db, comments_batch)
            log_manager.log(f"結束前已寫入最後 {len(comments_batch)} 筆留言到資料庫")

        log_manager.log(f"擷取留言結束，"
                        f"共處理 {processed_comment_count} 則留言，"
                        f"總處理數量(含回覆按鈕)={processed_total_count}")

async def fetch_super_thanks(youtube_video_id: str):
    """爬取 YouTube 影片的 Super Thanks 捐贈資訊，並將結果寫入 log"""
    start_time = time.time()  # 記錄開始時間

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,  # 開啟無頭模式
            args=[
                "--disable-dev-shm-usage",   # 減少共享記憶體使用
                "--disable-gpu",
                "--no-sandbox",              # 避免權限問題
                "--disable-background-networking",  # 減少後台資源消耗s
                "--disk-cache-size=0",       # 禁用硬碟快取，減少記憶體使用
                "--disable-software-rasterizer",  # 減少 CPU/GPU 渲染開銷
                "--disable-features=site-per-process",  # 減少多重處理負擔
                "--js-flags=--max-old-space-size=16384"  # 增加 V8 記憶體至 4GB
            ]

        )
        page = await browser.new_page()

        video_url = YOUTUBE_VIDEO_URL.format(youtube_video_id=youtube_video_id)
        await page.goto(video_url, wait_until="networkidle")

        print(f"正在爬取影片: {video_url}")
        log_manager.log(f"正在爬取影片: {video_url}")  # 寫入日誌  

        async for db in get_db():
            await asyncio.sleep(5)

            await page.evaluate(
                """
                () => {
                    const secondary = document.querySelector('#secondary');
                    if (secondary) {
                        secondary.remove();
                    }
                }
                """
            )

            await page.evaluate('''
                document.getElementById("ytd-player").remove();
            ''')
            
            # 1. 先讓頁面向下滾動 500 像素
            await scroll_down(page, pixels=500)

            # 2. 再滾動到「排序」按鈕
            sort_button_selector = 'tp-yt-paper-button[aria-label="排列留言順序"]'
            await scroll_to_element(page, sort_button_selector)

            
            # 3. 點擊「排序」按鈕
            await wait_and_click(page, sort_button_selector, sleep_time=1)

            # 4. 選擇「由新到舊」排序
            new_to_old_selector = 'div.item.style-scope.yt-dropdown-menu'
            await wait_for_text_and_click(page, new_to_old_selector, "由新到舊")
            

            # 5. 等待評論區加載完成
            await page.wait_for_selector("ytd-comments", timeout=3000)
            await asyncio.sleep(2)  # 稍微等候確保內容刷新

            print("已完成排序留言，開始擷取留言...")

            # **使用優化後的滾動函數**
            await fetch_comments(page, db, youtube_video_id)

            # **擷取留言完成後，關閉瀏覽器**
            await browser.close()

            total_elapsed_time = time.time() - start_time
            log_manager.log(f"完成擷取所有 Super Thanks 及留言，總執行時間: {total_elapsed_time:.2f} 秒")

if __name__ == "__main__":
    youtube_video_ids = ["kOZWQgtqps4"]  # 測試影片 ID
    # youtube_video_ids = ["hjcTwe5BHYI"]
    # youtube_video_ids = ["9vcPYm5fSSM"]
    asyncio.run(fetch_super_thanks(youtube_video_ids[0]))


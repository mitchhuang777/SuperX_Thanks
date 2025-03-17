import asyncio
import time
from playwright.async_api import Page

async def detect_new_comments(page: Page, comment_selector: str, interval: int = 30) -> bool:
    """
    檢測在給定時間內，YouTube 頁面中的留言是否有增加。
    如果沒有發現新留言，會向下滑動，並重新檢查新留言。
    :param page: Playwright 的 Page 物件
    :param comment_selector: 標記留言的 CSS selector
    :param interval: 偵測新留言的時間間隔 (秒)，預設 30 秒
    :return: 是否有新增留言
    """
    previous_comment_count = await page.query_selector_all(comment_selector)
    previous_count = len(previous_comment_count)

    print(f"初始留言數量: {previous_count}")

    start_time = time.time()
    while time.time() - start_time < interval:

        # 重新獲取留言數量
        current_comment_count = await page.query_selector_all(comment_selector)
        current_count = len(current_comment_count)

        # 偵測是否有新留言
        if current_count > previous_count:
            print(f"發現新留言！當前留言數量: {current_count}")
            return True  # 表示有新留言
    
        await page.evaluate("window.scrollBy(0, window.innerHeight)")  # 滾動頁面
        await asyncio.sleep(0.5)  # 等待新留言載入

        # 更新前後留言數量
        previous_count = current_count

    print(f"在 {interval} 秒內沒有偵測到新留言")
    return False  # 沒有新留言

async def scroll_down(page: Page, pixels: int = 500):
    """
    讓整個頁面往下滾動一定距離
    :param page: Playwright 的 Page 物件
    :param pixels: 要滾動的像素數量 (預設 500)
    """
    try:
        await page.evaluate(f"window.scrollBy(0, {pixels});")
        await asyncio.sleep(1)  # 等待滾動完成
        print(f"頁面已向下滾動 {pixels} 像素")
    except Exception as e:
        print(f"無法滾動頁面: {e}")

async def scroll_to_element(page: Page, selector: str):
    """
    滾動到指定元素
    :param page: Playwright 的 Page 物件
    :param selector: 目標 CSS 選擇器
    """
    try:
        await page.wait_for_selector(selector, timeout=5000)
        element = await page.query_selector(selector)
        if element:
            await element.scroll_into_view_if_needed()
            print(f"成功滾動至 {selector}")
    except Exception as e:
        pass

async def wait_and_click(page: Page, selector: str, timeout: int = 5000, sleep_time: float = 0):
    """
    等待元素出現後再點擊，確保元素存在
    :param page: Playwright 的 Page 物件
    :param selector: 要等待和點擊的 CSS 選擇器
    :param timeout: 等待的最大時間 (預設 5 秒)
    :param sleep_time: 點擊前額外等待時間 (預設 0 秒)
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)  # 可選，確保 UI 穩定
        await page.click(selector)
        print(f"成功點擊元素: {selector}")
    except Exception as e:
        print(f"無法點擊 {selector}: {e}")

async def wait_for_text_and_click(page: Page, selector: str, target_text: str, timeout: int = 5000):
    """
    在給定的選擇器內尋找包含特定文字的元素並點擊
    :param page: Playwright 的 Page 物件
    :param selector: 要搜尋的 CSS 選擇器 (會找出多個)
    :param target_text: 目標文字 (例: "由新到舊")
    :param timeout: 等待的最大時間 (預設 5 秒)
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        elements = await page.query_selector_all(selector)

        for element in elements:
            text = await element.inner_text()
            if target_text in text:
                await element.click()
                print(f"成功點擊選項: {target_text}")
                return
        
        print(f"找不到符合的選項: {target_text}")
    except Exception as e:
        print(f"點擊 {target_text} 失敗: {e}")

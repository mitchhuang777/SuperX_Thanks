import logging
import os

class LogManager:
    def __init__(self, log_file="scraper_log.txt"):
        self.log_file = log_file
        self._setup_logger()

    def _setup_logger(self):
        """設置日誌配置"""
        if not os.path.exists('logs'):
            os.makedirs('logs')

        self.logger = logging.getLogger(__name__)
        handler = logging.FileHandler(os.path.join('logs', self.log_file), encoding='utf-8')  # 設置 UTF-8 編碼
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def log(self, message):
        """寫入日誌"""
        self.logger.info(message)

log_manager = LogManager()

# src/logger.py
"""集中式日志：控制台 + 滚动文件，全项目复用。

日志文件位于项目根 logs/app.log，单文件 2MB，保留 5 个备份。
所有模块通过 ``get_logger(name)`` 获取 logger，避免重复配置。
"""
import logging
import os
from logging.handlers import RotatingFileHandler

# 项目根目录（src/ 的上一级）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: 日志目录绝对路径，供 cleanup 等模块复用
LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")

#: 日志主文件
LOG_FILE = os.path.join(LOG_DIR, "app.log")

#: 统一格式：时间 | 级别 | 模块 | 消息
_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_root() -> None:
    """配置 root logger（仅执行一次）。"""
    global _configured
    if _configured:
        return
    _configured = True

    os.makedirs(LOG_DIR, exist_ok=True)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

    # 文件：DEBUG 级，滚动写入
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # 控制台：INFO 级
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """获取模块 logger。首次调用会自动完成全局配置。"""
    _configure_root()
    return logging.getLogger(name)

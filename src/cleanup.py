# src/cleanup.py
"""启动时清理 tmp/ 下过多的历史截图，避免无限堆积。

保留最近 ``keep`` 个按修改时间排序的截图，其余删除。
"""
import os
import glob

from logger import get_logger

logger = get_logger("cleanup")

#: 默认保留的截图数量
DEFAULT_KEEP = 20

#: 截图文件名前缀（与 screenshot.py 保持一致）
_PREFIX = "screenshot_"


def cleanup_screenshots(save_path: str, keep: int = DEFAULT_KEEP) -> int:
    """清理截图目录，保留最近 ``keep`` 个。

    Args:
        save_path: 截图保存目录（可为相对路径）。
        keep: 保留的截图数量。

    Returns:
        被删除的文件数量。
    """
    if not os.path.isdir(save_path):
        return 0

    pattern = os.path.join(save_path, f"{_PREFIX}*.png")
    files = glob.glob(pattern)
    if len(files) <= keep:
        return 0

    # 按修改时间升序，删除最早的 (len - keep) 个
    files.sort(key=lambda p: os.path.getmtime(p))
    to_delete = files[: len(files) - keep]

    deleted = 0
    for path in to_delete:
        try:
            os.remove(path)
            deleted += 1
        except OSError:
            logger.exception("删除截图失败: %s", path)

    if deleted:
        logger.info("清理旧截图: 删除 %d 个，保留 %d 个", deleted, keep)
    return deleted

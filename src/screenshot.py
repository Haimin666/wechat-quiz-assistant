# src/screenshot.py
import os
import sys
import json
import time
import platform
from datetime import datetime
import subprocess

from logger import get_logger

logger = get_logger("screenshot")

# 项目根目录（用于加载根目录下的 region_select.py）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def setup_region(config_path="config.json"):
    """交互式选择截图区域并保存到配置。

    复用项目根的 ``region_select.py`` 中的 ``RegionSelector``。
    返回选中的 (x, y, w, h)，用户取消则返回 None。
    """
    try:
        from PyQt5.QtWidgets import QApplication
        from region_select import RegionSelector
    except Exception:
        logger.exception("加载区域选择器失败（需 PyQt5）")
        return None

    app = QApplication.instance() or QApplication(sys.argv)
    selector = RegionSelector()
    selector.show()

    # 事件循环，直到选择窗口关闭
    while selector.isVisible():
        app.processEvents()
        time.sleep(0.01)

    if selector.result_region:
        region = list(selector.result_region)
        save_region_to_config(region, config_path)
        logger.info("已保存截图区域: %s", region)
        return region

    logger.info("用户取消区域选择")
    return None


def load_region_from_config(config_path="config.json"):
    """从配置文件加载截图区域"""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("auto_detection", {}).get("screenshot_region", None)
    except FileNotFoundError:
        logger.warning("配置文件不存在: %s", config_path)
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("配置文件解析失败，忽略截图区域: %s (%s)", config_path, e)
        return None


def save_region_to_config(region, config_path="config.json"):
    """保存截图区域到配置文件"""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        if "auto_detection" not in config:
            config["auto_detection"] = {}
        config["auto_detection"]["screenshot_region"] = region
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        logger.exception("保存截图区域失败: %s", config_path)
        return False


def capture_screen(region=None, save_path="./tmp/", config_path="config.json"):
    """
    截取屏幕截图（支持Retina屏幕）
    
    Args:
        region: 截图区域 (x, y, width, height)，None表示全屏
        save_path: 保存路径
        config_path: 配置文件路径
    
    Returns:
        截图文件路径
    """
    os.makedirs(save_path, exist_ok=True)
    
    # 如果没有指定区域，从配置文件加载
    if region is None:
        region = load_region_from_config(config_path)
    
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"screenshot_{timestamp}.png"
    filepath = os.path.join(save_path, filename)
    
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            # 使用 -r 参数获取完整分辨率
            if region:
                x, y, width, height = region
                cmd = ["screencapture", "-x", "-r", "-R", f"{x},{y},{width},{height}", filepath]
            else:
                cmd = ["screencapture", "-x", "-r", filepath]
            subprocess.run(cmd, check=True, capture_output=True)

        elif system == "Windows":
            import pyautogui
            if region:
                x, y, width, height = region
                screenshot = pyautogui.screenshot(region=(x, y, width, height))
            else:
                screenshot = pyautogui.screenshot()
            screenshot.save(filepath)

        else:
            raise OSError(f"不支持的操作系统: {system}")
    except Exception:
        # 清理半成品文件，避免后续读取空文件
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        logger.exception("截图失败 region=%s cmd=%s", region, locals().get("cmd"))
        raise

    logger.debug("截图完成: %s (region=%s)", filepath, region)
    return filepath


if __name__ == "__main__":
    path = capture_screen()
    print(f"截图已保存: {path}")

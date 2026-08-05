# src/auto_clicker.py
"""自动点击选项功能：通过 OCR 定位选项位置，自动点击正确答案。"""
import re
import time

from logger import get_logger

logger = get_logger("auto_clicker")


class OptionDetector:
    """通过 OCR 识别 A/B/C/D 选项文字，返回其坐标位置。"""

    # 选项文字的正则模式
    OPTION_PATTERNS = [
        re.compile(r"^A[.、。\s]"),
        re.compile(r"^B[.、。\s]"),
        re.compile(r"^C[.、。\s]"),
        re.compile(r"^D[.、。\s]"),
    ]

    @staticmethod
    def detect(boxes):
        """从 OCR 结果中检测选项位置。

        Args:
            boxes: OCR 返回的文字块列表 [{"text": str, "box": [[x1,y1],...], "score": float}]

        Returns:
            {"A": (center_x, center_y), "B": (center_x, center_y), ...}
            只返回识别到的选项
        """
        result = {}

        for item in boxes:
            text = item["text"].strip()
            box = item["box"]

            # 计算文字块的中心 Y 坐标（box 是4个角点）
            center_y = sum(p[1] for p in box) / 4
            center_x = sum(p[0] for p in box) / 4

            # 检查是否匹配选项模式
            for i, pattern in enumerate(OptionDetector.OPTION_PATTERNS):
                if pattern.match(text):
                    letter = chr(ord("A") + i)
                    result[letter] = (int(center_x), int(center_y))
                    logger.debug("检测到选项 %s: (%d, %d), 文字='%s'", letter, center_x, center_y, text)
                    break

        logger.info("检测到 %d 个选项: %s", len(result), list(result.keys()))
        return result


class AutoClicker:
    """自动点击选项。"""

    def __init__(self, region):
        """
        Args:
            region: 截图区域 (x, y, width, height)，用于计算屏幕绝对坐标
        """
        self.region = region

    def click_option(self, letter, options):
        """点击指定选项。

        Args:
            letter: 选项字母，如 "A"
            options: OptionDetector.detect() 返回的坐标字典
        """
        if letter not in options:
            logger.warning("选项 %s 未找到，跳过点击", letter)
            return False

        import pyautogui

        local_x, local_y = options[letter]
        screen_x = self.region[0] + local_x
        screen_y = self.region[1] + local_y

        logger.info("点击选项 %s: 局部坐标(%d,%d) -> 屏幕坐标(%d,%d)",
                     letter, local_x, local_y, screen_x, screen_y)

        pyautogui.click(screen_x, screen_y)
        return True

    def click_answer(self, answer, options, interval=0.2):
        """点击答案（支持多选）。

        Args:
            answer: 答案字符串，如 "A" 或 "AB"
            options: OptionDetector.detect() 返回的坐标字典
            interval: 多选时每个选项之间的间隔（秒）

        Returns:
            成功点击的选项列表
        """
        clicked = []
        for letter in answer:
            if letter.isalpha():
                letter = letter.upper()
                if self.click_option(letter, options):
                    clicked.append(letter)
                    if len(clicked) < len(answer):
                        time.sleep(interval)

        logger.info("答案 '%s' 点击完成: %s", answer, clicked)
        return clicked

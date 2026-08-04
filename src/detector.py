# src/detector.py
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

from logger import get_logger

logger = get_logger("detector")


def detect_change(old_image_path, new_image_path, threshold=0.3):
    """
    检测两张图片是否有显著变化

    Args:
        old_image_path: 旧截图路径
        new_image_path: 新截图路径
        threshold: 变化阈值（0-1），默认30%

    Returns:
        是否有显著变化（True表示有变化）
    """
    # 校验阈值范围，越界则 clamp 并告警
    if threshold < 0 or threshold > 1:
        logger.warning("change_threshold=%s 越界 [0,1]，已 clamp", threshold)
        threshold = max(0.0, min(1.0, threshold))

    # 读取图片
    old_img = cv2.imread(old_image_path)
    new_img = cv2.imread(new_image_path)

    if old_img is None or new_img is None:
        raise ValueError(f"无法读取图片文件: old={old_image_path}, new={new_image_path}")

    # 确保图片尺寸相同
    if old_img.shape != new_img.shape:
        new_img = cv2.resize(new_img, (old_img.shape[1], old_img.shape[0]))

    # 转换为灰度图
    old_gray = cv2.cvtColor(old_img, cv2.COLOR_BGR2GRAY)
    new_gray = cv2.cvtColor(new_img, cv2.COLOR_BGR2GRAY)

    # 计算 SSIM（structural similarity index）
    # score ∈ [-1, 1]，越接近 1 表示两图越相似，越低表示差异越大
    score, _ = ssim(old_gray, new_gray, full=True)

    # 若 score < (1 - threshold)，说明差异超过阈值，判定为有变化
    has_change = score < (1 - threshold)

    logger.debug(
        "SSIM score=%.4f threshold=%.2f has_change=%s (%s vs %s)",
        score, threshold, has_change, old_image_path, new_image_path,
    )
    if has_change:
        logger.info("检测到题目变化: score=%.4f < %.2f", score, 1 - threshold)

    return has_change


if __name__ == "__main__":
    # 测试
    import sys
    if len(sys.argv) == 3:
        result = detect_change(sys.argv[1], sys.argv[2])
        print(f"检测结果: {'有变化' if result else '无变化'}")

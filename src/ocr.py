# src/ocr.py
from rapidocr_onnxruntime import RapidOCR

from logger import get_logger

logger = get_logger("ocr")

_ocr_instance = None


def get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        logger.info("初始化 RapidOCR 引擎")
        _ocr_instance = RapidOCR()
    return _ocr_instance


def image_to_text(image_path):
    """识别图片文字，返回按行拼接的文本。"""
    try:
        ocr = get_ocr()
        result, _ = ocr(image_path)

        # RapidOCR 返回 (result, elapse)；result 为 [box, text, score] 列表或 None
        if not result:
            logger.debug("OCR 未识别到文字: %s", image_path)
            return ""

        # 防御：result 可能是非 list 形状（旧/新版本差异），记录并降级
        if not isinstance(result, (list, tuple)):
            logger.warning(
                "OCR 返回非预期结构: %s (type=%s)，已跳过: %s",
                result, type(result).__name__, image_path,
            )
            return ""

        texts = [item[1] for item in result if len(item) > 1]
        text = "\n".join(texts)
        logger.debug("OCR 识别 %d 行: %s", len(texts), image_path)
        return text
    except Exception:
        logger.exception("OCR 识别失败: %s", image_path)
        raise RuntimeError(f"OCR识别失败: {image_path}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 2:
        print(image_to_text(sys.argv[1]))

# src/main.py
import os
import sys
import json
import time
import argparse
from datetime import datetime

# 添加src目录到sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger import get_logger
from screenshot import capture_screen, setup_region, load_region_from_config
from detector import detect_change
from ocr import image_to_text
from ai_analyzer import analyze_question
from cleanup import cleanup_screenshots

logger = get_logger("main")


def load_config(config_path="config.json"):
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_time():
    """格式化当前时间"""
    return datetime.now().strftime("%H:%M:%S")


def print_banner():
    """打印程序标题"""
    print("\n" + "=" * 60)
    print("              微信小程序自动答题助手")
    print("=" * 60)


def print_question(result):
    """打印题目和答案"""
    print("\n" + "━" * 60)

    # 提取题目第一行
    question_lines = result["question"].strip().split("\n")
    first_line = question_lines[0] if question_lines else ""
    print(f"\n题目：{first_line}")

    if result["options"]:
        print("\n选项：")
        for opt in result["options"]:
            print(f"  {opt}")

    print("\n" + "━" * 60)
    print(f"\n✓ 答案：{result['answer']}")
    print(f"\n解析：{result['explanation']}")
    print("\n" + "━" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="微信小程序自动答题助手")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--once", action="store_true", help="单次模式")
    parser.add_argument("--setup", action="store_true", help="设置截图区域")
    parser.add_argument("--type", choices=["single", "multiple"], default="single", help="题目类型")
    args = parser.parse_args()
    
    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, args.config)
    
    # 设置截图区域
    if args.setup:
        setup_region(config_path)
        return
    
    # 加载配置
    config = load_config(config_path)

    print_banner()

    # 检查是否已设置截图区域
    region = load_region_from_config(config_path)
    if region is None:
        print("\n[提示] 首次运行，请先设置截图区域")
        print("[提示] 运行: python -m src.main --setup")
        print("[提示] 或者手动编辑 config.json 添加 screenshot_region")

        # 尝试交互式设置
        try:
            choice = input("\n是否现在设置截图区域？(y/n): ").strip().lower()
            if choice == 'y':
                setup_region(config_path)
                region = load_region_from_config(config_path)
        except EOFError:
            pass

        if region is None:
            print("\n[提示] 使用全屏模式（不推荐）")

    # 创建临时目录
    save_path = config.get("screenshot", {}).get("save_path", "./tmp/")
    if not os.path.isabs(save_path):
        save_path = os.path.join(project_root, save_path)
    os.makedirs(save_path, exist_ok=True)

    # 启动时清理历史截图，避免无限堆积
    cleanup_screenshots(save_path)

    # 检查API密钥
    api_key = config.get("ai", {}).get("api_key", "")
    if not api_key:
        logger.error("未配置API密钥，配置文件: %s", config_path)
        print("\n[错误] 请在config.json中配置API密钥")
        print(f"[提示] 配置文件位置: {config_path}")
        sys.exit(1)

    # 获取配置
    interval = config.get("auto_detection", {}).get("interval", 0.5)
    threshold = config.get("auto_detection", {}).get("change_threshold", 0.3)
    max_tokens = config.get("ai", {}).get("max_tokens", 2048)
    enable_thinking = config.get("ai", {}).get("enable_thinking", False)

    if region:
        logger.info("截图区域: %s", region)
    else:
        logger.info("截图区域: 全屏")

    logger.info("启动自动检测模式: interval=%ss, threshold=%s, model=%s",
                interval, threshold, config.get("ai", {}).get("model", "step-3.7-flash"))
    print(f"[{format_time()}] 按 Ctrl+C 停止\n")

    last_image = None
    question_count = 0

    try:
        while True:
            # 截图
            current_image = capture_screen(region=region, save_path=save_path, config_path=config_path)

            # 检测变化
            if last_image is not None:
                try:
                    has_change = detect_change(last_image, current_image, threshold)
                except Exception:
                    logger.exception("检测出错")
                    last_image = current_image
                    time.sleep(interval)
                    continue

                if has_change:
                    question_count += 1
                    logger.info("检测到题目变化（第%d题）", question_count)

                    # OCR识别
                    logger.info("OCR识别中: %s", current_image)
                    try:
                        question_text = image_to_text(current_image)
                        if not question_text.strip():
                            logger.warning("未识别到文字，跳过: %s", current_image)
                            last_image = current_image
                            time.sleep(interval)
                            continue
                    except Exception:
                        logger.exception("OCR识别失败")
                        last_image = current_image
                        time.sleep(interval)
                        continue

                    # AI分析
                    logger.info("AI分析中...")
                    try:
                        result = analyze_question(
                            question_text,
                            question_type=args.type,
                            api_key=api_key,
                            model=config.get("ai", {}).get("model", "step-3.7-flash"),
                            base_url=config.get("ai", {}).get("base_url", "https://api.stepfun.com/v1"),
                            max_tokens=max_tokens,
                            enable_thinking=enable_thinking,
                        )
                        print_question(result)
                        logger.info("等待用户答题...")
                    except Exception:
                        logger.exception("AI分析失败")
            else:
                logger.info("首次截图，开始监听: %s", current_image)

            # 保存当前截图作为下次对比
            last_image = current_image

            # 单次模式
            if args.once:
                break

            # 等待
            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("用户中断，停止监听")

    logger.info("本次共识别 %d 道题目", question_count)


if __name__ == "__main__":
    main()

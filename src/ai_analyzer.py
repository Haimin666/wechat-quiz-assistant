# src/ai_analyzer.py
import re
import base64

from openai import OpenAI

from logger import get_logger

logger = get_logger("ai_analyzer")


def _parse_value(line: str) -> str:
    """从「答案：xxx」/「解析：xxx」行提取冒号后的内容。

    只在首个全角/半角冒号处切一次，避免内容里再含冒号时被截断
    （如「解析：选项D：土地使用权」之前会被切成只剩「土地使用权」）。
    """
    # 兼容全角：与半角:
    for sep in ("：", ":"):
        idx = line.find(sep)
        if idx >= 0:
            return line[idx + len(sep):].strip()
    return ""


def _clean_answer(raw: str) -> str:
    """从答案行提取选项字母组，如「D」或「AB」。

    输入可能是「D」「AB」「D. 土地使用权」「AB、选项」等，
    只取开头的连续大写字母（最多4个 A-D）。
    """
    if not raw:
        return ""
    m = re.match(r"\s*([A-D]{1,4})\b", raw)
    return m.group(1) if m else raw.strip()[:4]


def analyze_question(
    question_text,
    question_type="single",
    api_key="",
    model="step-3.7-flash",
    base_url="https://api.stepfun.com/v1",
    max_tokens=2048,
    enable_thinking=False,
    reasoning_effort="low",
):
    """
    分析题目并给出答案

    Args:
        question_text: 题目文字
        question_type: 题目类型 ("single" 或 "multiple")
        api_key: API密钥
        model: 使用的模型
        base_url: API地址
        max_tokens: 最大生成 token 数
        enable_thinking: 是否开启推理模式
        reasoning_effort: 推理强度 ("low"/"medium"/"high")，默认 low

    Returns:
        {
            "question": "题目内容",
            "options": ["A. 选项1", "B. 选项2", ...],
            "answer": "A" 或 "AB" 等,
            "explanation": "解析说明"
        }
    """
    if not api_key:
        raise ValueError("请提供API密钥")

    # 构建提示词
    type_hint = "单选题" if question_type == "single" else "多选题"

    prompt = f"""你是一个专业的答题助手。请分析以下{type_hint}并给出答案。

题目内容：
{question_text}

请按以下格式返回（不要添加其他内容）：
答案：[选项字母，如 D 或 AB]
解析：[选项内容，如：土地使用权属于无形资产]"""

    # 调用API（注意：日志中绝不打印 api_key）
    client = OpenAI(api_key=api_key, base_url=base_url)
    logger.info("调用 AI 模型: model=%s, max_tokens=%s, enable_thinking=%s, reasoning_effort=%s, 题目长度=%d",
                model, max_tokens, enable_thinking, reasoning_effort or "(默认)", len(question_text))

    extra = {"enable_thinking": enable_thinking}
    if reasoning_effort:
        extra["reasoning_effort"] = reasoning_effort

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个专业的答题助手，擅长分析选择题并给出准确答案。"},
            {"role": "user", "content": prompt}
        ],
        max_tokens=max_tokens,
        temperature=0.3,
        extra_body=extra,
        timeout=30,
    )

    # 解析响应
    choice = response.choices[0]
    finish_reason = getattr(choice, "finish_reason", None)
    usage = getattr(response, "usage", None)
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
    logger.debug(
        "AI 完成: finish_reason=%s, completion_tokens=%s, max_tokens=%s",
        finish_reason, completion_tokens, max_tokens,
    )

    content = (choice.message.content or "").strip()
    logger.info("AI 响应: %s", content[:200])

    result = {
        "question": question_text,
        "options": [],
        "answer": "",
        "explanation": ""
    }

    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("答案：") or stripped.startswith("答案:"):
            result["answer"] = _clean_answer(_parse_value(stripped))
        elif stripped.startswith("解析：") or stripped.startswith("解析:"):
            result["explanation"] = _parse_value(stripped)

    if not result["answer"]:
        # 推理模型常见症状：max_tokens 不足导致 finish_reason=length、content 为空
        if finish_reason == "length":
            logger.error(
                "AI 响应被 max_tokens=%s 截断（completion_tokens=%s），"
                "推理未结束、content 为空。请在 config.json 调大 ai.max_tokens（建议 ≥2048）",
                max_tokens, completion_tokens,
            )
        else:
            logger.warning("未能从响应中提取答案 (finish_reason=%s)，原始内容: %s",
                           finish_reason, content[:200])

    # 提取选项（用于展示）
    for line in question_text.split("\n"):
        line = line.strip()
        if line and len(line) > 2 and line[0] in "ABCD" and line[1] in ".、":
            result["options"].append(line)

    return result


def analyze_question_with_image(
    image_path,
    question_type="single",
    api_key="",
    model="step-3.7-flash",
    base_url="https://api.stepfun.com/v1",
    max_tokens=2048,
    enable_thinking=False,
    reasoning_effort="low",
):
    """
    直接用图片分析题目（跳过OCR）

    Args:
        image_path: 截图文件路径
        question_type: 题目类型 ("single" 或 "multiple")
        api_key: API密钥
        model: 使用的模型
        base_url: API地址
        max_tokens: 最大生成 token 数
        enable_thinking: 是否开启推理模式
        reasoning_effort: 推理强度 ("low"/"medium"/"high")，默认 low

    Returns:
        {
            "question": "题目内容（从图片识别）",
            "options": ["A. 选项1", "B. 选项2", ...],
            "answer": "A" 或 "AB" 等,
            "explanation": "解析说明"
        }
    """
    if not api_key:
        raise ValueError("请提供API密钥")

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    type_hint = "单选题" if question_type == "single" else "多选题"

    prompt = f"""请识别这张截图中的{type_hint}，分析并给出答案。

要求：
1. 先提取题目内容和选项
2. 分析正确答案
3. 给出解析

请严格按以下格式返回（不要添加其他内容）：
答案：[选项字母，如 D 或 AB]
解析：[选项内容，如：土地使用权属于无形资产]"""

    client = OpenAI(api_key=api_key, base_url=base_url)
    logger.info("调用 AI 视觉模型: model=%s, max_tokens=%s, reasoning_effort=%s, image=%s",
                model, max_tokens, reasoning_effort or "(默认)", image_path)

    extra = {"enable_thinking": enable_thinking}
    if reasoning_effort:
        extra["reasoning_effort"] = reasoning_effort

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个专业的答题助手，擅长从截图中识别题目并给出准确答案。"},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
                {"type": "text", "text": prompt}
            ]}
        ],
        max_tokens=max_tokens,
        temperature=0.3,
        extra_body=extra,
        timeout=30,
    )

    choice = response.choices[0]
    finish_reason = getattr(choice, "finish_reason", None)
    usage = getattr(response, "usage", None)
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
    logger.debug(
        "AI 视觉完成: finish_reason=%s, completion_tokens=%s, max_tokens=%s",
        finish_reason, completion_tokens, max_tokens,
    )

    content = (choice.message.content or "").strip()
    logger.info("AI 视觉响应: %s", content[:300])

    result = {
        "question": "",
        "options": [],
        "answer": "",
        "explanation": ""
    }

    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("答案：") or stripped.startswith("答案:"):
            result["answer"] = _clean_answer(_parse_value(stripped))
        elif stripped.startswith("解析：") or stripped.startswith("解析:"):
            result["explanation"] = _parse_value(stripped)

    if not result["answer"]:
        if finish_reason == "length":
            logger.error(
                "AI 视觉响应被 max_tokens=%s 截断（completion_tokens=%s），"
                "请在 config.json 调大 ai.max_tokens",
                max_tokens, completion_tokens,
            )
        else:
            logger.warning("未能从视觉响应中提取答案 (finish_reason=%s)，原始内容: %s",
                           finish_reason, content[:300])

    # 从响应中提取题目和选项
    result["question"] = content
    for line in content.split("\n"):
        line = line.strip()
        if line and len(line) > 2 and line[0] in "ABCD" and line[1] in ".、":
            result["options"].append(line)

    return result


if __name__ == "__main__":
    # 测试
    import sys
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        result = analyze_question(question, api_key="your-api-key")
        print(f"答案: {result['answer']}")
        print(f"解析: {result['explanation']}")

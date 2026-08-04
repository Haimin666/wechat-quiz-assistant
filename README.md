# 微信小程序自动答题助手

自动检测微信小程序题目变化，OCR识别题目，AI分析给出答案。

## 功能特点

- 自动检测题目变化（SSIM图片对比）
- OCR识别题目文字（PaddleOCR本地识别）
- AI分析给出答案（阶跃星辰API）
- 支持Mac和Windows

## 快速开始

### 1. 安装依赖

```bash
cd wechat-quiz-assistant
pip install -r requirements.txt
```

### 2. 配置API密钥

编辑 `config.json`，填入API密钥：

```json
{
    "ai": {
        "api_key": "your-api-key-here",
        "base_url": "https://api.stepfun.com/v1",
        "model": "step-3.7-flash"
    }
}
```

### 3. 运行程序

```bash
# GUI模式（推荐）
python run_gui.py

# 命令行模式
python -m src.main

# 单次识别
python -m src.main --once

# 指定题目类型
python -m src.main --type multiple
```

## 使用流程

1. 打开微信小程序答题页面
2. 运行程序
3. 程序自动截图识别题目
4. 显示答案和解析
5. 手动点击答案
6. 程序自动检测下一题

## 配置说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| auto_detection.interval | 截图间隔（秒） | 0.5 |
| auto_detection.change_threshold | 变化阈值 | 0.3 |
| ai.api_key | API密钥 | - |
| ai.base_url | API地址 | https://api.stepfun.com/v1 |
| ai.model | AI模型 | step-3.7-flash |

## 常见问题

### Q: 截图失败？
A: Mac需要在系统偏好设置 > 安全性与隐私 > 隐私 > 屏幕录制中授权终端应用。

### Q: AI分析失败？
A: 请检查config.json中的API密钥是否正确。

### Q: 无法检测到题目变化？
A: 可以调整change_threshold参数，降低阈值（如0.2）。

### Q: OCR识别不准确？
A: PaddleOCR对中文识别效果较好，确保题目文字清晰可见。

## 项目结构

```
wechat-quiz-assistant/
├── README.md
├── requirements.txt
├── config.json
├── run_gui.py           # GUI启动脚本
├── src/
│   ├── main.py          # 命令行入口
│   ├── gui.py           # GUI界面
│   ├── screenshot.py    # 截图模块
│   ├── detector.py      # 变化检测模块
│   ├── ocr.py           # OCR模块（PaddleOCR）
│   └── ai_analyzer.py   # AI分析模块
└── tests/
```

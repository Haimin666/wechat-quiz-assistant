# 微信小程序自动答题助手 - 设计文档

## 1. 项目概述

### 1.1 项目名称
wechat-quiz-assistant（微信小程序自动答题助手）

### 1.2 项目目标
开发一个能够自动识别微信小程序中的选择题（单选/多选），并通过AI分析给出答案的工具。

### 1.3 核心特性
- **自动检测**：定时截图对比，自动检测题目变化
- **OCR识别**：使用Umi-OCR将屏幕截图转换为文字
- **AI分析**：使用OpenAI GPT-3.5-turbo分析题目并给出答案
- **实时响应**：检测到新题目后1-2秒内给出答案
- **跨平台**：支持Mac和Windows系统
- **CLI界面**：命令行操作，简单直接

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    wechat-quiz-assistant                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │  定时截图    │ ──→│  图片对比    │ ──→│  检测变化    │      │
│  │  (每0.5秒)  │    │  (SSIM算法) │    │  (差异>30%) │      │
│  └─────────────┘    └─────────────┘    └──────┬──────┘      │
│                                               │             │
│                                               ↓ 有变化      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │  用户答题    │ ←──│  显示答案    │ ←──│  OCR+AI分析 │      │
│  │  (手动点击)  │    │             │    │  (1-2秒)    │      │
│  └──────┬──────┘    └─────────────┘    └─────────────┘      │
│         │                                                   │
│         └───────────────────────────────────────────────────┘
│                          自动循环
└─────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| 主语言 | Python 3.9+ | 核心逻辑 |
| OCR引擎 | Umi-OCR | 图片转文字 |
| AI模型 | OpenAI GPT-3.5-turbo | 题目分析 |
| 系统自动化 | AppleScript (Mac) / AutoHotkey (Windows) | 模拟点击（预留） |
| 界面 | CLI命令行 | 用户交互 |

### 2.3 目录结构

```
wechat-quiz-assistant/
├── README.md                    # 项目说明
├── requirements.txt             # 依赖库
├── config.json                  # 配置文件
├── src/
│   ├── __init__.py
│   ├── main.py                  # 主程序入口
│   ├── screenshot.py            # 截图模块
│   ├── detector.py              # 变化检测模块（SSIM对比）
│   ├── ocr.py                   # OCR识别模块
│   ├── ai_analyzer.py           # AI分析模块
│   ├── automation.py            # 自动化操作模块（预留）
│   └── utils.py                 # 工具函数
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-08-03-wechat-quiz-assistant-design.md
└── tests/
    └── test_basic.py            # 基础测试
```

## 3. 模块设计

### 3.1 截图模块 (screenshot.py)

**功能**：截取当前屏幕指定区域的截图

**接口**：
```python
def capture_screen(region=None) -> str:
    """
    截取屏幕截图
    
    Args:
        region: 截图区域 (x, y, width, height)
                None表示使用默认区域（微信小程序题目区域）
                可通过配置文件设置
    
    Returns:
        截图文件路径
    """
```

**实现**：
- Mac：使用 `screencapture` 命令
- Windows：使用 `pyautogui.screenshot()`

**默认截图区域**：
- 用户首次运行时，程序会提示用户框选微信小程序题目区域
- 该区域会保存到config.json，后续运行自动使用
- 用户也可以通过命令行参数重新设置区域

### 3.2 变化检测模块 (detector.py)

**功能**：对比前后两张截图，检测题目是否变化

**接口**：
```python
def detect_change(old_image_path: str, new_image_path: str, threshold: float = 0.3) -> bool:
    """
    检测两张图片是否有显著变化
    
    Args:
        old_image_path: 旧截图路径
        new_image_path: 新截图路径
        threshold: 变化阈值（0-1），默认30%
    
    Returns:
        是否有显著变化
    """
```

**实现**：
- 使用SSIM（结构相似性）算法
- 依赖：scikit-image, opencv-python
- 速度：约0.05秒

### 3.3 OCR模块 (ocr.py)

**功能**：调用Umi-OCR将图片转换为文字

**接口**：
```python
def image_to_text(image_path: str) -> str:
    """
    将图片转换为文字
    
    Args:
        image_path: 图片文件路径
    
    Returns:
        识别出的文字
    """
```

**实现**：
- 优先使用HTTP接口调用Umi-OCR（需要Umi-OCR运行HTTP服务）
- 备选：通过命令行调用Umi-OCR CLI

### 3.3 AI分析模块 (ai_analyzer.py)

**功能**：使用GPT-3.5-turbo分析题目并给出答案

**接口**：
```python
def analyze_question(question_text: str, question_type: str = "single") -> dict:
    """
    分析题目并给出答案
    
    Args:
        question_text: 题目文字
        question_type: 题目类型 ("single" 或 "multiple")
    
    Returns:
        {
            "question": "题目内容",
            "options": ["A. 选项1", "B. 选项2", ...],
            "answer": "A" 或 "AB" 等,
            "explanation": "解析说明"
        }
    """
```

**实现**：
- 使用OpenAI API
- 模型：gpt-3.5-turbo（快速、便宜）
- 提示词设计：专门针对选择题优化

### 3.4 自动化模块 (automation.py) - 预留

**功能**：模拟鼠标点击答案选项

**接口**：
```python
def click_answer(answer: str, options_position: dict) -> None:
    """
    点击答案选项
    
    Args:
        answer: 答案选项（如"A"、"AB"）
        options_position: 各选项的坐标位置
    """
```

**实现**：
- Mac：使用AppleScript
- Windows：使用AutoHotkey

## 4. 工作流程

### 4.1 主流程

```
1. 用户启动程序
2. 用户框选微信小程序题目区域（首次运行）
3. 进入自动检测循环：
   a. 每0.5秒截图一次
   b. 对比前后截图差异（SSIM算法）
   c. 如果差异>30%，判定为题目变化
   d. 调用Umi-OCR识别新题目
   e. 调用GPT-3.5-turbo分析答案
   f. 显示答案选项和解析
4. 用户手动点击答案
5. 回到步骤3
```

### 4.2 配置文件

```json
{
    "auto_detection": {
        "enabled": true,
        "interval": 0.5,
        "change_threshold": 0.3,
        "screenshot_region": null
    },
    "ocr": {
        "engine": "umi-ocr",
        "api_url": "http://localhost:12345"
    },
    "ai": {
        "provider": "openai",
        "model": "gpt-3.5-turbo",
        "api_key": "",
        "max_tokens": 500
    },
    "screenshot": {
        "save_path": "./tmp/"
    },
    "question": {
        "default_type": "single",
        "auto_detect_type": true
    }
}
```

## 5. 用户界面

### 5.1 工作模式

| 模式 | 说明 | 触发方式 |
|------|------|----------|
| **自动模式** | 定时截图，检测到变化自动分析 | 默认模式 |
| **手动模式** | 按空格键触发截图分析 | `--manual` 参数 |
| **单次模式** | 只运行一次，不循环 | `--once` 参数 |

### 5.2 CLI命令

```bash
# 启动自动模式（默认）
python -m src.main

# 启动手动模式
python -m src.main --manual

# 单次识别
python -m src.main --once

# 指定配置文件
python -m src.main --config config.json

# 指定题目类型
python -m src.main --type single  # 单选题
python -m src.main --type multiple  # 多选题
```

### 5.3 输出格式

```
╔════════════════════════════════════════════════════════════╗
║                    微信小程序自动答题助手                    ║
║                    [自动模式] 监听中...                     ║
╚════════════════════════════════════════════════════════════╝

[00:00:01] 截图对比中...
[00:00:01] 检测到题目变化！
[00:00:01] OCR识别中...
[00:00:02] AI分析中...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

题目：以下哪个是Python的特点？

选项：
  A. 编译型语言
  B. 动态类型语言
  C. 强类型语言
  D. 静态类型语言

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ 答案：B

解析：Python是动态类型语言，变量类型在运行时确定，不需要预先声明类型。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[00:00:02] 等待用户答题...
[00:00:15] 检测到题目变化（用户已答题）
[00:00:15] 继续分析下一题...
```

## 6. 错误处理

### 6.1 OCR识别失败

```
[错误] OCR识别失败，请检查Umi-OCR是否运行
[提示] 请启动Umi-OCR并确保HTTP接口可用
```

### 6.2 AI分析失败

```
[错误] AI分析失败，请检查API密钥
[提示] 请在config.json中配置有效的OpenAI API密钥
```

### 6.3 截图失败

```
[错误] 截图失败，请检查屏幕权限
[提示] Mac需要在系统偏好设置中授予屏幕录制权限
```

## 7. 部署要求

### 7.1 环境要求

- Python 3.9+
- Umi-OCR（需要单独安装并运行）
- OpenAI API密钥

### 7.2 安装步骤

```bash
# 1. 克隆项目
git clone <repo-url>
cd wechat-quiz-assistant

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Mac/Linux
# 或
venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置API密钥
# 编辑 config.json，填入OpenAI API密钥

# 5. 启动Umi-OCR（需要单独下载）

# 6. 运行程序
python -m src.main
```

## 8. 后续扩展

### 8.1 短期扩展

- [ ] 支持更多题目类型（判断题、填空题）
- [ ] 支持题库缓存
- [ ] 支持批量识别

### 8.2 长期扩展

- [ ] 自动点击功能
- [ ] 支持更多OCR引擎
- [ ] GUI界面
- [ ] 支持手机端（ADB控制）

## 9. 设计决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| OCR引擎 | Umi-OCR | 成熟稳定，支持命令行和HTTP调用 |
| AI模型 | GPT-3.5-turbo | 快速、便宜、效果好 |
| 界面 | CLI | 简单直接，符合需求 |
| 自动化 | 预留接口 | 先输出答案，用户确认后再执行 |
| 跨平台 | Python | Mac和Windows都支持 |
| 变化检测 | 纯图片对比（SSIM） | 速度快，实现简单，先跑起来再优化 |
| 检测阈值 | 30% | 平衡灵敏度和误判率 |

---

**文档版本**：v1.0  
**创建日期**：2026-08-03  
**作者**：AI Assistant

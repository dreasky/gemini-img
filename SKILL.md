---
name: gemini-img
description: 通过 Playwright 无头浏览器自动化，后台调用 Google Gemini 生成图片并保存到本地。当用户说"生成图片"、"画一张"、"用Gemini生成"或 /gemini-img 时激活。全程无头后台运行，图片自动保存到桌面。
---

# Gemini 图片生成 Skill

通过 Playwright 无头浏览器自动化，在完全后台调用 Google Gemini 生成高分辨率图片（通常 1.5~3MB），自动保存到本地，无需手动操作浏览器。

## 触发条件

以下情况激活本 skill：

| 触发方式 | 示例 |
|---------|------|
| 斜杠命令 | `/gemini-img 一只猫坐在屋顶上` |
| 明确指令 | "用 Gemini 生成图片"、"帮我画一张 XXX" |
| 意图识别 | "生成/画/制作 + 图片/图像/插图" |
| 中文触发 | "生成一张 XXX 的图片"、"给我画一张" |

## 执行入口

所有命令通过统一入口执行（自动管理 venv 和依赖）：

```
python C:/Users/w8466/.claude/skills/gemini-img/scripts/run.py <command> [args]
```

---

## 首次使用：登录

**必须先执行一次，保存 Google 账号 session：**

```bash
python C:/Users/w8466/.claude/skills/gemini-img/scripts/run.py login
```

流程：
1. 自动打开有头 Chromium 浏览器
2. 用户在浏览器中完成 Google 账号登录
3. 登录后在终端按 ENTER 确认
4. Session 自动保存到 `storage_state.json`（后续无需再次登录）

---

## 生成图片

### 基本用法（自动保存到桌面）

```bash
python C:/Users/w8466/.claude/skills/gemini-img/scripts/run.py generate "图片描述提示词"
```

### 指定保存路径

```bash
python C:/Users/w8466/.claude/skills/gemini-img/scripts/run.py generate "图片描述" -o "C:/Users/w8466/Desktop/output.png"
```

### 生成多张

```bash
python C:/Users/w8466/.claude/skills/gemini-img/scripts/run.py generate "图片描述" --count 4
```

### 调试模式（显示浏览器窗口）

```bash
python C:/Users/w8466/.claude/skills/gemini-img/scripts/run.py generate "图片描述" --headed
```

---

## 内部执行流程

生成时按以下步骤自动执行：

1. **启动无头浏览器** — 加载 `storage_state.json` 恢复 Google session
2. **打开 Gemini** — 等待 Angular 应用完全初始化（`div[contenteditable][role="textbox"]`）
3. **提交提示词** — 清空输入框，输入提示词，按 Enter 提交
4. **等待生成完成** — 最多等 180s，检测 `button[data-test-id="download-generated-image-button"]` 出现
5. **等待图片渲染** — 再等待 `button.image-button img.image` 出现在 DOM 中（最多 20s）
6. **点击「更多」** — 点击 `button[data-test-id="more-menu-button"]`
7. **点击「下载图片」** — 点击 `button[data-test-id="image-download-button"]`
8. **网络拦截保存** — 捕获 ≥200KB 的图片响应（全尺寸 PNG，通常 1.5~3MB）
9. **回退方案** — 若网络拦截失败，使用 canvas 导出

---

## 输出格式

成功时输出 JSON（打印到 stdout）：

```json
{
  "success": true,
  "files": ["C:/Users/w8466/Desktop/zen_garden_20260415_151358.png"],
  "prompt": "原始提示词",
  "count": 1
}
```

默认文件名格式：`{提示词前30字符}_{YYYYMMDD_HHMMSS}.png`

---

## 提示词优化规则

调用时自动在用户原始描述上增强质量：

- 添加 `photorealistic`、`ultra high resolution` 等质量词
- 添加 `8K`、`hyperdetailed` 等分辨率标识
- 添加构图、光线、风格描述词
- 保持用户原始意图不变

示例：
- 用户说："画一只猫"
- 实际提示词："a cat sitting gracefully, photorealistic, ultra high resolution, 8K, soft natural lighting"

---

## 执行规则

**无需确认，直接执行：**
- `login` — 首次登录设置
- `generate` — 生成图片（核心功能）

**执行前告知用户：**
- 生成通常需要 30~90 秒
- 首次运行会自动安装 Playwright 依赖（约 1 分钟）
- 执行完成后告知保存路径和文件大小

---

## 错误处理

| 错误情形 | 处理方式 |
|---------|---------|
| 未登录 / session 过期 | 提示用户执行 `login` 命令 |
| 生成超时（>180s） | 保存 debug 截图，建议切换 `--headed` 调试 |
| 下载按钮未找到 | 尝试备用 aria-label 选择器 |
| 网络拦截未捕获图片 | 自动回退到 canvas 导出 |
| 依赖未安装 | `run.py` 自动创建 venv 并安装 |

Debug 截图路径：`C:/Users/w8466/.claude/skills/gemini-img/debug_screenshot.png`

---

## 文件结构

```
gemini-img/
├── SKILL.md                 # 本文件（skill 定义）
├── storage_state.json       # Google session（登录后自动生成，勿删）
├── .venv/                   # Python 虚拟环境（自动创建）
├── downloads/               # 临时下载目录
└── scripts/
    ├── run.py               # 统一入口（管理 venv + 依赖）
    └── gemini_img.py        # 核心 Playwright 自动化逻辑
```

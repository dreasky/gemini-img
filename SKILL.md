---
name: gemini-img
description: 当需要根据生图提示词，生成具体图片时使用。当用户说"生成图片"、"画一张"、"用Gemini生成"时激活。当需要清理Gemini生成图像的水印时使用。
---

# Gemini 图片生成 Skill

通过 Playwright 无头浏览器调用 Google Gemini 生成图片，支持单张生成、批量任务管理和失败重试。

**架构**: 使用 `browser_scheduler` 通用框架，支持任务持久化和断点续跑。

## 执行入口

```
python scripts/run.py gemini.py [--headed] <command> [args]
```

`--headed`：以有头模式运行浏览器（可见窗口，用于调试）。

---

## 可用命令

### `login` — 登录 Google 账号

保存 Google session 到本地，后续生成无需再次登录。**首次使用必须执行**。

```bash
python scripts/run.py gemini.py login
```

---

### `generate` — 单次生成图片

根据提示词直接生成图片，结果以 JSON 输出（含文件路径）。

```bash
python scripts/run.py gemini.py generate "a futuristic city at night"
python scripts/run.py gemini.py generate "a red cat" -o ./cat.png --count 3
```

默认保存到桌面，文件名格式：`{提示词}_{时间戳}.png`。

---

### `batch` — 批量生成（推荐）

扫描目录下所有 `.md` 文件，每个文件作为一个任务批量生成图片，任务状态持久化。

```bash
python scripts/run.py gemini.py batch ./prompts/
python scripts/run.py gemini.py batch ./prompts/ -o ./output/
```

**特点**：

- 支持断点续跑（已完成的任务自动跳过）
- 失败任务可重试
- 任务状态自动保存到 `.gemini_tasks.json`

---

### `run` — 生成单个任务

从任务目录中生成指定 ID 的任务（对应 `.md` 文件名，不含后缀）。

```bash
python scripts/run.py gemini.py run ./prompts/ my_prompt
python scripts/run.py gemini.py run ./prompts/ my_prompt -o ./output/
```

---

### `status` — 查看任务状态汇总

显示任务目录的整体进度统计（待处理、进行中、已完成、失败数量）。

```bash
python scripts/run.py gemini.py status ./prompts/
```

---

### `tasks` — 列出任务详情

列出所有任务或查看特定任务的详细信息（状态、重试次数、错误信息）。

```bash
python scripts/run.py gemini.py tasks ./prompts/
python scripts/run.py gemini.py tasks ./prompts/ -t my_prompt
```

---

### `retry` — 重试失败/待处理任务

重试任务目录中所有待处理任务，或仅重试失败的任务。

```bash
python scripts/run.py gemini.py retry ./prompts/       # 重试所有 pending 任务
python scripts/run.py gemini.py retry ./prompts/ -f    # 仅重试失败任务
```

---

### `report` — 导出任务报告

将任务状态和统计信息导出为 JSON 报告文件。

```bash
python scripts/run.py gemini.py report ./prompts/
python scripts/run.py gemini.py report ./prompts/ -o ./report.json
```

---

### `clear` — 清除已完成记录

清除任务跟踪记录中已完成的条目（不删除生成的图片文件）。

```bash
python scripts/run.py gemini.py clear ./prompts/
```

---

## 水印清理（cleaner.py）

移除 Gemini 生成图片中的可见水印。

```bash
python scripts/run.py cleaner.py [命令] [参数]
```

### `remove` — 移除单张或多张图片水印

```bash
python scripts/run.py cleaner.py remove image.png
python scripts/run.py cleaner.py remove a.png b.png c.png
```

### `batch` — 批量处理目录下所有 PNG

```bash
python scripts/run.py cleaner.py batch ./output/                # 处理当前目录
python scripts/run.py cleaner.py batch ./output/ -r             # 递归处理子目录
python scripts/run.py cleaner.py batch ./output/ -r --dry-run   # 预览，不执行
```

| 选项             | 说明                         |
| ---------------- | ---------------------------- |
| `-r/--recursive` | 递归搜索子目录中的 PNG 文件  |
| `--dry-run`      | 仅列出待处理文件，不实际执行 |

---

## 错误处理

| 情形                  | 处理方式                  |
| --------------------- | ------------------------- |
| 未登录 / session 过期 | 执行 `login` 命令重新登录 |
| 生成超时              | 加 `--headed` 参数调试    |
| 有失败任务            | 执行 `retry -f` 重试      |
| 换行导致消息发送      | 已修复：使用 JS 注入文本  |

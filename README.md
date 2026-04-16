# gemini-img

基于 Playwright 的 Google Gemini 图片生成自动化工具。

## Skill安装

```bash
npx skills add https://github.com/dreasky/gemini-img --skill gemini-img
```

## 首次使用

```bash
# 登录 Google 账号，保存浏览器会话
python scripts/run.py gemini.py login
```

> 所有命令通过 `python scripts/run.py` 运行，自动管理虚拟环境和依赖安装，无需手动配置。

## CLI 命令

```bash
# 单次生成
python scripts/run.py gemini.py generate "一只在月球上的猫" -o output.png

# 批量生成（从 .md 文件）
python scripts/run.py gemini.py batch ./prompts
python scripts/run.py gemini.py batch ./prompts -o ./output

# 运行单个任务
python scripts/run.py gemini.py run ./prompts 任务ID
python scripts/run.py gemini.py run ./prompts 任务ID -o ./output

# 查看任务状态
python scripts/run.py gemini.py status ./prompts

# 列出所有任务
python scripts/run.py gemini.py tasks ./prompts

# 重试失败任务
python scripts/run.py gemini.py retry ./prompts --failed-only

# 导出报告
python scripts/run.py gemini.py report ./prompts -o report.json

# 清理已完成任务
python scripts/run.py gemini.py clear ./prompts
```

所有命令加 `--headed` 显示浏览器窗口（默认无头模式）。

> **目录说明**：所有命令的 `INPUT` 参数指向 prompt `.md` 文件所在目录。生成的图片和任务状态 JSON 默认保存在该目录下的 `output/` 子目录，可通过 `-o` 指定其他位置。

## 批量生成流程

1. 将 prompt 写入 `.md` 文件，文件名即任务 ID
2. `batch` 命令扫描目录，自动创建任务并执行
3. 生成结果保存为 PNG，自动去除 Gemini 水印
4. 失败任务记录 `conversation_url`，重试时直接打开对话页面，若图片已生成则直接下载

## 项目结构

```
scripts/
├── gemini.py                    # CLI 入口
├── gemini/
│   ├── client.py                # 单次生成客户端
│   ├── executor.py              # 批量执行器
│   ├── handlers.py              # 浏览器交互逻辑（导航/点击/输入/下载）
│   ├── config.py                # 选择器常量
│   └── watermark.py             # 水印去除
└── browser_scheduler/           # 可复用的浏览器任务调度框架
    ├── models.py                # Task / TaskStore
    ├── handlers.py              # Handler / Context / Result
    ├── executor.py              # BaseExecutor
    ├── browser.py               # BrowserManager
    ├── utils.py                 # insert_text_with_newlines 等
    └── retry.py                 # 重试工具
```

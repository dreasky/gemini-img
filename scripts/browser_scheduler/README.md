# browser_scheduler

基于 Playwright 的浏览器自动化任务调度框架。

## 特性

- **任务管理**：定义、存储、追踪自动化任务
- **文件扫描**：自动从文件创建任务（如 .md、.txt）
- **浏览器管理**：会话管理、登录处理、资源清理
- **批量执行**：多任务批量执行，支持进度回调
- **自动重试**：指数退避重试机制

## 安装

```bash
pip install playwright
playwright install chromium
```

## 快速入门

### 1. 基础使用

```python
import asyncio
from browser_scheduler import Task, Handler, Context, Result, JsonStore

# 定义处理器
class MyHandler(Handler):
    async def execute(self, ctx: Context) -> Result:
        page = ctx.page
        task = ctx.task
        
        await page.goto("https://example.com")
        await page.fill("input", task.data)
        await page.click("button")
        
        return Result(success=True)

# 创建并执行任务
async def main():
    # 创建任务
    store = JsonStore("tasks.json")
    store.add(Task(id="1", data="搜索内容"))
    store.save()
    
    # 执行
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        handler = MyHandler()
        task = store.get("1")
        result = await handler.execute(Context(task=task, page=page))
        
        await browser.close()

asyncio.run(main())
```

### 2. 文件扫描创建任务

```python
from browser_scheduler import FileScanningStore

# 扫描 .md 文件创建任务
store = FileScanningStore(
    state_path="tasks.json",
    tasks_dir="./prompts",
    output_dir="./output"
)

# 创建任务
count = store.scan_files("*.md")
print(f"创建了 {count} 个任务")

# 查看待处理任务
print(f"待处理: {len(store.pending)}")
```

### 3. 批量执行

```python
import asyncio
from browser_scheduler import (
    BrowserManager, FileScanningStore, BaseExecutor,
    Task, TaskStatus
)

# 自定义执行器
class MyExecutor(BaseExecutor):
    async def run_single_task(self, task: Task, page) -> Task:
        try:
            await page.goto("https://example.com")
            await page.fill("#input", task.data)
            await page.click("#submit")
            
            task.status = TaskStatus.COMPLETED
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
        
        return task

async def main():
    # 初始化
    store = FileScanningStore("tasks.json", "./prompts")
    store.scan_files("*.md")
    
    browser = BrowserManager(
        storage_path=".data/session.json",
        headless=True
    )
    
    executor = MyExecutor(store, browser)
    
    # 执行（带进度回调）
    def on_progress(task, done, total):
        print(f"[{done}/{total}] {task.id}: {task.status.value}")
    
    result = await executor.run_all(on_progress=on_progress)
    
    print(f"\n完成: {result.completed}/{result.total}")
    print(f"失败: {result.failed}")
    print(f"耗时: {result.duration_seconds:.1f}秒")

asyncio.run(main())
```

### 4. 登录保存会话

```python
from browser_scheduler import BrowserManager

# 交互式登录，保存会话
browser = BrowserManager(".data/session.json")
browser.login_sync(
    login_url="https://example.com/login",
    success_url_hint="dashboard"
)

# 后续使用保存的会话
browser = BrowserManager(".data/session.json", headless=True)
await browser.launch()
page = await browser.new_page()
```

## 核心组件

### Task - 任务

```python
from browser_scheduler import Task, TaskStatus

task = Task(
    id="唯一标识",
    data="任务内容",
    output_path="输出路径",
    status=TaskStatus.PENDING,
    extra={"自定义": "数据"}
)
```

**状态流转：**

```
PENDING → RUNNING → COMPLETED
   ↓                ↑
FAILED ←── RETRYING
```

### JsonStore - JSON存储

```python
from browser_scheduler import JsonStore, TaskStatus

store = JsonStore("tasks.json")

# 增删改查
store.add(task)
task = store.get("task-id")
store.remove("task-id")

# 查询
all_tasks = store.all()
pending = store.pending
completed = store.completed
failed = store.failed

# 按状态筛选
running = store.filter(TaskStatus.RUNNING)

# 统计
print(store.stats)  # {"pending": 5, "completed": 10, "failed": 2}

# 重置失败任务
count = store.reset_failed()

# 保存
store.save()
```

### FileScanningStore - 文件扫描存储

```python
from browser_scheduler import FileScanningStore

store = FileScanningStore(
    state_path="tasks.json",
    tasks_dir="./prompts",
    output_dir="./output"
)

# 扫描文件
count = store.scan_files("*.md")

# 自定义提取器
def extract_json(path):
    import json
    data = json.loads(path.read_text())
    return {
        "data": data["prompt"],
        "output_path": f"output/{path.stem}.png"
    }

store.scan_files("*.json", extractor=extract_json)
```

### BrowserManager - 浏览器管理

```python
from browser_scheduler import BrowserManager

browser = BrowserManager(
    storage_path=".data/session.json",
    headless=True,
    viewport={"width": 1280, "height": 800}
)

# 启动
await browser.launch()

# 获取页面
page = await browser.new_page()

# 关闭
await browser.close()

# 交互式登录（同步）
browser.login_sync("https://site.com/login")
```

### Handler - 处理器

```python
from browser_scheduler import Handler, Context, Result

class MyHandler(Handler):
    async def execute(self, ctx: Context) -> Result:
        task = ctx.task      # Task 对象
        page = ctx.page      # Playwright page
        
        try:
            # 你的逻辑
            return Result(success=True)
        except Exception as e:
            return Result(success=False, error=str(e))
```

### BaseExecutor - 执行器基类

```python
from browser_scheduler import BaseExecutor, Task

class MyExecutor(BaseExecutor):
    async def run_single_task(self, task: Task, page) -> Task:
        # 必须实现此方法
        task.status = TaskStatus.COMPLETED
        return task

# 使用
executor = MyExecutor(store, browser)

# 执行所有待处理任务
result = await executor.run_all()

# 执行单个任务
task = await executor.run_task("task-id")

# 带进度回调
result = await executor.run_all(
    on_progress=lambda task, done, total: print(f"{done}/{total}")
)
```

### retry - 重试

```python
from browser_scheduler import retry, retry_sync

# 异步
async def fetch():
    return await api.get()

result = await retry(fetch, max_attempts=3, delay=1.0)

if result.success:
    print(result.result)
else:
    print(f"失败: {result.error}")

# 同步
result = retry_sync(fetch_sync, max_attempts=3)
```

### 浏览器工具函数

```python
from browser_scheduler import (
    insert_text_with_newlines,
    clear_contenteditable
)

# 插入文本（保留换行，不会触发Enter）
await insert_text_with_newlines(
    page,
    'div[contenteditable="true"]',
    "第一行\n第二行\n第三行"
)

# 清空内容编辑区域
await clear_contenteditable(page, "#editor")
```

## 常见模式

### 模式1：网页抓取

```python
class ScrapingExecutor(BaseExecutor):
    async def run_single_task(self, task: Task, page) -> Task:
        try:
            await page.goto(task.extra["url"])
            
            title = await page.title()
            content = await page.text_content(".content")
            
            Path(task.output_path).write_text(f"{title}\n\n{content}")
            task.status = TaskStatus.COMPLETED
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
        
        return task
```

### 模式2：表单提交

```python
class FormExecutor(BaseExecutor):
    async def run_single_task(self, task: Task, page) -> Task:
        try:
            await page.goto("https://example.com/form")
            
            data = json.loads(task.data)
            await page.fill("#name", data["name"])
            await page.fill("#email", data["email"])
            await page.click("#submit")
            
            await page.wait_for_selector(".success")
            task.status = TaskStatus.COMPLETED
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
        
        return task
```

### 模式3：图片生成

```python
class ImageExecutor(BaseExecutor):
    async def run_single_task(self, task: Task, page) -> Task:
        try:
            await page.goto("https://ai-generator.com")
            
            # 输入提示词
            await insert_text_with_newlines(
                page, "#prompt", task.data
            )
            await page.keyboard.press("Enter")
            
            # 等待生成
            await page.wait_for_selector(".image", timeout=120000)
            
            # 截图保存
            await page.screenshot(path=task.output_path)
            
            task.status = TaskStatus.COMPLETED
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
        
        return task
```

## 最佳实践

1. **及时保存**：修改任务后调用 `store.save()`
2. **异常处理**：用 try-except 包裹任务逻辑，设置正确状态
3. **使用 output_path**：统一在 task.output_path 保存结果
4. **资源清理**：完成后调用 `browser.close()`
5. **会话复用**：用 `login_sync()` 保存登录，后续复用
6. **进度跟踪**：长任务使用 `on_progress` 回调

## 文件结构

```
browser_scheduler/
├── __init__.py       # 导出全部组件
├── models.py         # Task, TaskStatus
├── handlers.py       # Handler, Context, Result, JsonStore
├── retry.py          # retry(), retry_sync()
├── utils.py          # 浏览器工具函数
├── browser.py        # BrowserManager
├── file_store.py     # FileScanningStore
├── executor.py       # BaseExecutor
├── README.md         # 本文档
└── ARCHITECTURE.md   # 架构图
```

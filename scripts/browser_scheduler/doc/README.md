# Browser Scheduler

简洁的浏览器自动化任务调度框架。

## 特性

- **TaskStore** - JSON文件存储，支持从目录扫描文件创建任务
- **BrowserManager** - 浏览器生命周期管理，支持会话持久化
- **BaseExecutor** - 批量任务执行框架
- **Retry** - 指数退避重试机制

## 安装

```bash
pip install playwright
playwright install chromium
```

## 快速开始

### 1. 基础使用

```python
from browser_scheduler import Task, TaskStore, Handler, Context, Result

# 创建任务存储
store = TaskStore(
    input_dir="./prompts",      # 输入文件目录
    output_dir="./output",      # 输出目录（默认input_dir/output）
    store_name="tasks.json"     # 状态文件名
)

# 添加任务
store.add(Task(id="task1", data="prompt content"))
store.add(Task(id="task2", data="another prompt"))

# 查看状态
print(store.stats)  # {'pending': 2, 'completed': 0, 'failed': 0}
```

### 2. 从文件扫描创建任务

```python
# 自动扫描 .md 文件创建任务
store = TaskStore("./prompts", "./output")
count = store.scan_files("*.md")  # 返回创建的任务数
print(f"创建了 {count} 个任务")

# 自定义提取器
def extract_json(file_path):
    import json
    data = json.loads(file_path.read_text())
    return {
        "data": data["prompt"],
        "extra": {"category": data.get("category")}
    }

store.scan_files("*.json", extractor=extract_json)
```

### 3. 批量执行

```python
from browser_scheduler import BrowserManager, BaseExecutor, TaskStatus

class MyExecutor(BaseExecutor):
    """自定义执行器"""
    
    async def run_single_task(self, task, page):
        # 打开页面
        await page.goto("https://example.com")
        
        # 输入内容
        await page.fill("input[name='q']", task.data)
        await page.click("button[type='submit']")
        
        # 等待结果并保存
        await page.wait_for_selector(".result")
        await page.screenshot(path=task.output_path)
        
        task.status = TaskStatus.COMPLETED
        return task

# 执行
store = TaskStore("./prompts", "./output")
store.scan_files("*.md")

browser = BrowserManager(".data/storage.json", headless=True)
executor = MyExecutor(store, browser)

result = await executor.run_all(
    on_progress=lambda task, done, total: print(f"{done}/{total}")
)

print(f"完成: {result.completed}, 失败: {result.failed}")
```

### 4. 登录保存会话

```python
from browser_scheduler import BrowserManager

browser = BrowserManager(".data/storage.json")

# 交互式登录（会打开可视化浏览器）
browser.login_sync(
    login_url="https://example.com/login",
    success_url_hint="/dashboard"  # 可选：登录成功后URL应包含的字符串
)

# 后续使用保存的会话
await browser.launch()
page = await browser.new_page()
# 已登录状态
```

## 核心组件

### TaskStore - 任务存储

```python
from browser_scheduler import TaskStore, TaskStatus

store = TaskStore("./input", "./output", "tasks.json")

# 添加/获取
store.add(task)
task = store.get("task_id")

# 查询
pending = store.pending        # 待处理任务列表
completed = store.completed    # 已完成
failed = store.failed          # 失败
all_tasks = store.all()        # 全部

# 过滤
pending_list = store.filter(TaskStatus.PENDING)

# 状态
stats = store.stats  # {'pending': 1, 'completed': 2, 'failed': 0}

# 重置失败任务
store.reset_failed()

# 扫描文件创建任务
count = store.scan_files("*.md")
count = store.scan_files("*.txt", output_ext=".pdf")
```

### BrowserManager - 浏览器管理

```python
from browser_scheduler import BrowserManager

browser = BrowserManager(
    storage_path=".data/session.json",  # 会话存储路径
    headless=True,                      # 是否无头
)

# 启动
await browser.launch()

# 创建页面
page = await browser.new_page()

# 关闭
await browser.close()

# 检查状态
if browser.is_launched:
    ...

# 交互式登录（同步方法）
browser.login_sync("https://example.com/login")
```

### Handler - 任务处理器

```python
from browser_scheduler import Handler, Context, Result

class MyHandler(Handler):
    async def execute(self, ctx: Context) -> Result:
        try:
            await ctx.page.fill("input", ctx.task.data)
            await ctx.page.click("button")
            return Result(success=True)
        except Exception as e:
            return Result(success=False, error=str(e))

# 使用
handler = MyHandler()
result = await handler.execute(Context(task=task, page=page))
```

### Retry - 重试机制

```python
from browser_scheduler import retry, retry_sync

# 异步
result = await retry(
    lambda: some_async_operation(),
    max_attempts=3,
    delay=1.0,
    backoff=2.0
)

if result.success:
    print(result.result)
else:
    print(f"失败，尝试了{result.attempts}次: {result.error}")

# 同步
result = retry_sync(lambda: some_sync_operation())
```

### 浏览器工具函数

```python
from browser_scheduler import insert_text_with_newlines, clear_contenteditable

# 输入带换行的文本（不会触发Enter）
await insert_text_with_newlines(
    page,
    'div[contenteditable="true"]',
    "第一行\n第二行\n第三行"
)

# 清空富文本编辑器
await clear_contenteditable(page, 'div[contenteditable="true"]')
```

## 最佳实践

1. **目录结构**
   ```
   project/
   ├── prompts/          # 输入文件
   ├── output/           # 输出文件 + task_store.json
   └── .data/            # 会话存储
   ```

2. **Task 扩展字段**
   ```python
   # 使用 extra 字典添加自定义字段
   task = Task(id="x", data="y")
   task.extra["image_url"] = "..."
   task.extra["metadata"] = {...}
   ```

3. **错误处理**
   ```python
   async def run_single_task(self, task, page):
       try:
           # 执行逻辑
           task.status = TaskStatus.COMPLETED
       except Exception as e:
           task.status = TaskStatus.FAILED
           task.error = str(e)
       return task
   ```

4. **进度回调**
   ```python
   def on_progress(task, done, total):
       percent = done / total * 100
       print(f"[{percent:.0f}%] {task.id}")
   
   result = await executor.run_all(on_progress=on_progress)
   ```

## 文件结构

```
browser_scheduler/
├── __init__.py      # 包入口
├── models.py        # Task, TaskStatus, TaskStore
├── handlers.py      # Handler, Context, Result
├── browser.py       # BrowserManager
├── executor.py      # BaseExecutor, ExecutionResult
├── retry.py         # retry, retry_sync, RetryResult
└── utils.py         # insert_text_with_newlines, clear_contenteditable
```

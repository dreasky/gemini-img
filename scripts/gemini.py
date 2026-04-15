#!/usr/bin/env python3
"""Gemini Image Generator — Click CLI entry point."""

import asyncio
import functools
import json
import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent))
from gemini import (
    BrowserConfig,
    BrowserGenerationError,
    BrowserImageGenerator,
    GeminiImageGenerator,
    TaskManager,
    TaskStatus,
)
from gemini.utils import export_task_report, print_status, print_task_details


def run_async(func):
    """Decorator: run an async Click command in the default event loop."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        return asyncio.run(func(*args, **kwargs))
    return wrapper


# ── CLI group ─────────────────────────────────────────────────────────────────

@click.group()
@click.option(
    "--headed",
    is_flag=True,
    default=False,
    help="Run browser in headed (visible) mode.",
)
@click.pass_context
def cli(ctx, headed: bool):
    """Gemini 图片生成工具

    通过无头浏览器调用 Gemini 生成图片，支持单张生成、批量任务管理和重试机制。
    """
    ctx.ensure_object(dict)
    ctx.obj["config"] = BrowserConfig(headless=not headed)


# ── login ─────────────────────────────────────────────────────────────────────

@cli.command()
def login():
    """一次性登录 Google 账号，保存 Cookie 到 storage_state.json。"""
    GeminiImageGenerator().login()


# ── generate (direct prompt) ──────────────────────────────────────────────────

@cli.command("generate")
@click.argument("prompt")
@click.option(
    "-o", "--output",
    default=None,
    help="输出文件路径（默认：~/Desktop/<提示词>_<时间戳>.png）",
)
@click.option(
    "--count",
    default=1,
    show_default=True,
    help="生成图片数量。",
)
@click.pass_context
def generate(ctx, prompt: str, output: str | None, count: int):
    """根据 PROMPT 直接生成图片（使用已保存的会话）。

    示例:

        gemini-img generate "a futuristic city at night"

        gemini-img generate "a red cat" -o ./cat.png --count 3
    """
    config = ctx.obj["config"]
    gen    = GeminiImageGenerator(headless=config.headless)
    try:
        results = gen.generate(prompt, output, count)
    except BrowserGenerationError as e:
        click.echo(f"错误: {e}", err=True)
        raise SystemExit(1)
    click.echo(
        json.dumps(
            {"success": True, "files": results, "prompt": prompt, "count": len(results)},
            ensure_ascii=False,
        )
    )


# ── batch (from .md files) ────────────────────────────────────────────────────

@cli.command("generate-batch")
@click.argument("input_dir", type=click.Path(exists=True))
@click.option(
    "-o", "--output-dir",
    default=None,
    help="输出目录（默认：INPUT_DIR/generated）",
)
@click.pass_context
@run_async
async def generate_batch(ctx, input_dir: str, output_dir: str | None):
    """扫描 INPUT_DIR 下的 .md 文件并批量生成图片。

    每个 .md 文件对应一个任务，文件内容作为提示词，
    生成结果保存到输出目录，任务状态持久化到 .task_state.json。

    示例:

        gemini-img generate-batch ./prompts/

        gemini-img generate-batch ./prompts/ -o ./output/
    """
    config       = ctx.obj["config"]
    task_manager = TaskManager(input_dir=input_dir, output_dir=output_dir,
                               output_subdir=config.output_subdir)
    task_manager.scan_prompts()
    task_manager.load_tasks()

    pending = task_manager.get_pending_tasks()
    if not pending:
        click.echo("没有待处理的任务。")
        print_status(task_manager)
        return

    click.echo(f"发现 {len(pending)} 个待处理任务，开始生成...")

    def on_progress(task, processed, total):
        icon = "✓" if task.status == TaskStatus.COMPLETED.value else "✗"
        click.echo(f"[{processed}/{total}] {icon} {task.id}: {task.status}")
        if task.error:
            click.echo(f"    错误: {task.error}")

    gen    = BrowserImageGenerator(config, task_manager)
    result = await gen.generate_batch(pending, on_progress=on_progress)

    click.echo("\n" + "=" * 50)
    click.echo("处理完成!")
    click.echo(f"  - 总任务数: {result.total}")
    click.echo(f"  - 成功:     {result.completed}")
    click.echo(f"  - 失败:     {result.failed}")
    click.echo("=" * 50)
    print_status(task_manager)


# ── generate-single ───────────────────────────────────────────────────────────

@cli.command("generate-single")
@click.argument("input_dir", type=click.Path(exists=True))
@click.argument("task_id")
@click.option(
    "-o", "--output-dir",
    default=None,
    help="输出目录（默认：INPUT_DIR/generated）",
)
@click.pass_context
@run_async
async def generate_single(ctx, input_dir: str, task_id: str, output_dir: str | None):
    """生成单个任务的图片。

    INPUT_DIR: 包含 .md 提示词文件的目录

    TASK_ID: 任务 ID（对应 .md 文件名，不含扩展名）

    示例:

        gemini-img generate-single ./prompts/ my_prompt
    """
    config       = ctx.obj["config"]
    task_manager = TaskManager(input_dir=input_dir, output_dir=output_dir,
                               output_subdir=config.output_subdir)
    task_manager.load_tasks()

    task = task_manager.get_task(task_id)
    if not task:
        md_file = Path(input_dir) / f"{task_id}.md"
        if not md_file.exists():
            click.echo(f"错误: 找不到任务 '{task_id}' 或对应的 .md 文件", err=True)
            raise SystemExit(1)
        task = task_manager.create_task(md_file)

    click.echo(f"生成任务: {task_id}")
    gen    = BrowserImageGenerator(config, task_manager)
    result = await gen.generate_single(task)

    if result.status == TaskStatus.COMPLETED.value:
        click.echo(f"✓ 成功生成图片: {result.output_path}")
    else:
        click.echo(f"✗ 生成失败: {result.error}", err=True)
        raise SystemExit(1)


# ── status ────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("input_dir", type=click.Path(exists=True))
def status(input_dir: str):
    """查看任务状态汇总。

    示例:

        gemini-img status ./prompts/
    """
    tm = TaskManager(input_dir=input_dir)
    tm.load_tasks()
    print_status(tm)


# ── tasks ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("input_dir", type=click.Path(exists=True))
@click.option("--task-id", "-t", default=None, help="查看特定任务的详细信息。")
def tasks(input_dir: str, task_id: str | None):
    """列出所有任务或查看特定任务的详情。

    示例:

        gemini-img tasks ./prompts/

        gemini-img tasks ./prompts/ -t my_prompt
    """
    tm = TaskManager(input_dir=input_dir)
    tm.load_tasks()

    if task_id:
        task = tm.get_task(task_id)
        if task:
            print_task_details(task)
        else:
            click.echo(f"找不到任务: {task_id}", err=True)
            raise SystemExit(1)
        return

    stats = tm.get_stats()
    click.echo("\n任务列表:")
    click.echo("-" * 60)

    icons = {
        TaskStatus.PENDING.value:   "○",
        TaskStatus.RUNNING.value:   "◐",
        TaskStatus.RETRYING.value:  "↻",
        TaskStatus.COMPLETED.value: "●",
        TaskStatus.FAILED.value:    "✗",
    }
    for task in tm.tasks.values():
        icon = icons.get(task.status, "?")
        click.echo(
            f"{icon} {task.id:30} [{task.status:10}] retries: {task.retry_count}"
        )
        if task.error:
            click.echo(f"    错误: {task.error[:60]}...")

    click.echo("-" * 60)
    click.echo(
        f"\n统计: 总计 {stats['total']} | 待处理 {stats['pending']} | "
        f"进行中 {stats['running']} | 已完成 {stats['completed']} | 失败 {stats['failed']}"
    )


# ── retry ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("input_dir", type=click.Path(exists=True))
@click.option(
    "--failed-only", "-f",
    is_flag=True,
    help="仅重试失败的任务（跳过 pending）。",
)
@click.pass_context
@run_async
async def retry(ctx, input_dir: str, failed_only: bool):
    """重试待处理或失败的任务。

    示例:

        gemini-img retry ./prompts/          # 重试所有 pending 任务

        gemini-img retry ./prompts/ -f       # 仅重置并重试失败任务
    """
    config = ctx.obj["config"]
    tm     = TaskManager(input_dir=input_dir)
    tm.load_tasks()

    if failed_only:
        count = tm.retry_failed()
        if count == 0:
            click.echo("没有失败的任务需要重试。")
            return
        click.echo(f"已将 {count} 个失败任务重置为待处理。")

    pending = tm.get_pending_tasks()
    if not pending:
        click.echo("没有待处理的任务。")
        return

    click.echo(f"开始重试 {len(pending)} 个任务...")

    def on_progress(task, processed, total):
        icon = "✓" if task.status == TaskStatus.COMPLETED.value else "✗"
        click.echo(f"[{processed}/{total}] {icon} {task.id}: {task.status}")

    gen    = BrowserImageGenerator(config, tm)
    result = await gen.generate_batch(pending, on_progress=on_progress)
    click.echo(f"\n重试完成: 成功 {result.completed}，失败 {result.failed}")


# ── report ────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("input_dir", type=click.Path(exists=True))
@click.option(
    "-o", "--output-file",
    default=None,
    help="报告输出路径（默认：INPUT_DIR/generation_report.json）",
)
def report(input_dir: str, output_file: str | None):
    """导出任务报告为 JSON 文件。

    示例:

        gemini-img report ./prompts/

        gemini-img report ./prompts/ -o ./report.json
    """
    tm = TaskManager(input_dir=input_dir)
    tm.load_tasks()

    out = output_file or str(Path(input_dir) / "generation_report.json")
    export_task_report(tm, out)

    stats = tm.get_stats()
    click.echo(f"报告已生成: {out}")
    click.echo(
        f"统计: 总计 {stats['total']} | 已完成 {stats['completed']} | 失败 {stats['failed']}"
    )


# ── clear ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("input_dir", type=click.Path(exists=True))
@click.confirmation_option(prompt="确定要清除已完成任务的记录吗？（生成的图片不会被删除）")
def clear(input_dir: str):
    """清除已完成任务的跟踪记录（不删除生成的图片）。

    示例:

        gemini-img clear ./prompts/
    """
    tm = TaskManager(input_dir=input_dir)
    tm.load_tasks()
    count = tm.clear_completed()
    click.echo(f"已清除 {count} 个已完成任务的记录。")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    cli()


if __name__ == "__main__":
    main()

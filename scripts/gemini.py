#!/usr/bin/env python3
"""Gemini Image Generator CLI."""

import asyncio
import functools
import json
import sys
from datetime import datetime
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent))
from browser_scheduler import TaskStatus
from gemini import (
    BrowserGenerationError,
    GeminiClient,
    GeminiExecutor,
)


def run_async(func):
    """Run async function."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        return asyncio.run(func(*args, **kwargs))

    return wrapper


@click.group()
@click.option("--headed", is_flag=True, default=False, help="Show browser window.")
@click.pass_context
def cli(ctx, headed: bool):
    """Gemini image generator."""
    ctx.ensure_object(dict)
    ctx.obj["headless"] = not headed


@cli.command()
def login():
    """Login to Google and save session."""
    GeminiClient().login()


@cli.command()
@click.argument("prompt")
@click.option("-o", "--output", default=None, help="Output path.")
@click.option("--count", default=1, help="Number of images.")
@click.pass_context
def generate(ctx, prompt: str, output: str | None, count: int):
    """Generate single image."""
    client = GeminiClient(headless=ctx.obj["headless"])
    output_path = Path(output) if output else None
    try:
        paths = client.generate(prompt, output_path, count)
        click.echo(json.dumps({"success": True, "files": paths}, ensure_ascii=False))
    except BrowserGenerationError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("input", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Output directory.")
@click.pass_context
@run_async
async def batch(ctx, input: str, output: str | None):
    """Batch generate from .md files."""
    output_path = Path(output) if output else None
    executor = GeminiExecutor(
        input_dir=Path(input),
        output_dir=output_path,
        headless=ctx.obj["headless"],
    )

    count = executor.scan_prompts()
    click.echo(f"Found {count} tasks")

    pending = executor.store.pending
    if not pending:
        click.echo("No pending tasks.")
        return

    click.echo(f"Processing {len(pending)} tasks...")

    def on_progress(task, done, total):
        icon = "✓" if task.status == TaskStatus.COMPLETED else "✗"
        click.echo(f"[{done}/{total}] {icon} {task.id}: {task.status.value}")

    result = await executor.run_all(on_progress=on_progress)

    click.echo(f"\nDone: {result.completed} success, {result.failed} failed")


@cli.command()
@click.argument("input", type=click.Path(exists=True))
@click.argument("task_id")
@click.option("-o", "--output", default=None, help="Output directory.")
@click.pass_context
@run_async
async def run(ctx, input: str, task_id: str, output: str | None):
    """Run single task."""
    output_path = Path(output) if output else None
    executor = GeminiExecutor(
        input_dir=Path(input),
        output_dir=output_path,
        headless=ctx.obj["headless"],
    )

    task = await executor.run_task(task_id)
    if not task:
        click.echo(f"Task not found: {task_id}", err=True)
        sys.exit(1)

    if task.status == TaskStatus.COMPLETED:
        click.echo(f"✓ {task.output_path}")
    else:
        click.echo(f"✗ {task.error}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("input", type=click.Path(exists=True))
def status(input: str):
    """Show task status."""
    executor = GeminiExecutor(Path(input))
    # Scan for new .md files
    executor.scan_prompts()

    s = executor.store.stats
    total = sum(s.values())

    click.echo(f"\nTasks: {total} total")
    click.echo(f"  Pending:   {s.get('pending', 0)}")
    click.echo(f"  Completed: {s.get('completed', 0)}")
    click.echo(f"  Failed:    {s.get('failed', 0)}")

    failed = executor.store.failed
    if failed:
        click.echo("\nFailed:")
        for t in failed:
            click.echo(f"  - {t.id}: {t.error}")


@cli.command()
@click.argument("input", type=click.Path(exists=True))
@click.option("-t", "--task-id", default=None, help="Show task details.")
def tasks(input: str, task_id: str | None):
    """List tasks."""
    executor = GeminiExecutor(Path(input))
    # Scan for new .md files
    executor.scan_prompts()

    if task_id:
        task = executor.store.get(task_id)
        if not task:
            click.echo(f"Not found: {task_id}", err=True)
            return
        click.echo(f"\nTask: {task.id}")
        click.echo(f"Status: {task.status.value}")
        click.echo(f"Output: {task.output_path}")
        click.echo(f"Error:  {task.error or 'None'}")
        click.echo(f"\nData:\n{task.data[:200]}...")
        return

    for task in executor.store.all():
        click.echo(f"{task.id:30} [{task.status.value:10}]")


@cli.command()
@click.argument("input", type=click.Path(exists=True))
@click.option("-f", "--failed-only", is_flag=True, help="Reset only failed tasks.")
def retry(input: str, failed_only: bool):
    """Reset tasks for retry."""
    executor = GeminiExecutor(Path(input))

    if failed_only:
        count = executor.store.reset_failed()
    else:
        count = 0
        for task in executor.store.all():
            if task.status in (TaskStatus.PENDING, TaskStatus.FAILED):
                task.status = TaskStatus.PENDING
                count += 1
        executor.store.save()

    click.echo(f"Reset {count} tasks. Run 'batch' to execute.")


@cli.command()
@click.argument("input", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Report file path.")
def report(input: str, output: str | None):
    """Export task report."""
    executor = GeminiExecutor(Path(input))

    report_path = output or str(Path(input) / "report.json")

    data = {
        "generated_at": datetime.now().isoformat(),
        "stats": executor.store.stats,
        "tasks": [t.to_dict() for t in executor.store.all()],
    }

    Path(report_path).write_text(json.dumps(data, indent=2, ensure_ascii=False))
    click.echo(f"Report saved: {report_path}")


@cli.command()
@click.argument("input", type=click.Path(exists=True))
@click.confirmation_option(prompt="Clear completed tasks?")
def clear(input: str):
    """Clear completed task records."""
    executor = GeminiExecutor(Path(input))

    completed = executor.store.completed
    for task in completed:
        executor.store.remove(task.id)
    executor.store.save()

    click.echo(f"Cleared {len(completed)} tasks.")


def main():
    cli()


if __name__ == "__main__":
    main()

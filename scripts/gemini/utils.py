"""Display helpers and report export for the task manager."""

import json
from datetime import datetime
from pathlib import Path

from .task_manager import Task, TaskManager, TaskStatus


# ── display ───────────────────────────────────────────────────────────────────


def print_status(task_manager: TaskManager) -> None:
    """Print a summary table of task counts to stdout."""
    s = task_manager.get_stats()
    print("\n" + "=" * 50)
    print("Task Status Summary")
    print("=" * 50)
    print(f"Input Directory:  {task_manager.input_dir}")
    print(f"Output Directory: {task_manager.output_dir}")
    print(f"Total Tasks:      {s['total']}")
    print(f"  - Pending:      {s['pending']}")
    print(f"  - Running:      {s['running']}")
    print(f"  - Completed:    {s['completed']}")
    print(f"  - Failed:       {s['failed']}")
    print("=" * 50 + "\n")

    failed = task_manager.get_failed_tasks()
    if failed:
        print("Failed Tasks:")
        for t in failed:
            print(f"  - {t.id}: {t.error}")


def print_task_details(task: Task) -> None:
    """Print detailed info for a single task."""
    print("\n" + "-" * 50)
    print(f"Task: {task.id}")
    print("-" * 50)
    print(f"Status:       {task.status}")
    print(f"Prompt File:  {task.prompt_file}")
    print(f"Output Path:  {task.output_path}")
    print(f"Retry Count:  {task.retry_count}")
    print(f"Created At:   {task.created_at}")
    if task.completed_at:
        print(f"Completed At: {task.completed_at}")
    if task.error:
        print(f"Error:        {task.error}")
    print(f"\nPrompt Content:")
    print("-" * 50)
    snippet = task.prompt_content
    print(snippet[:500] + ("..." if len(snippet) > 500 else ""))
    print("-" * 50 + "\n")


# ── report export ─────────────────────────────────────────────────────────────


def export_task_report(task_manager: TaskManager, output_file: str) -> None:
    """Write a JSON report of all tasks to *output_file*."""
    report = {
        "generated_at": datetime.now().isoformat(),
        "input_dir": str(task_manager.input_dir),
        "output_dir": str(task_manager.output_dir),
        "stats": task_manager.get_stats(),
        "tasks": [
            {
                "id": t.id,
                "prompt_file": t.prompt_file,
                "output_path": t.output_path,
                "status": t.status,
                "retry_count": t.retry_count,
                "error": t.error,
                "created_at": t.created_at,
                "completed_at": t.completed_at,
            }
            for t in task_manager.tasks.values()
        ],
    }
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

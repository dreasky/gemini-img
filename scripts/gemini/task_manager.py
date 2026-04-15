"""Task manager for tracking image generation tasks with JSON persistence."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class TaskStatus(Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    RETRYING  = "retrying"
    COMPLETED = "completed"
    FAILED    = "failed"


@dataclass
class Task:
    id:              str
    prompt_file:     str
    prompt_content:  str
    output_path:     str
    status:          str = TaskStatus.PENDING.value
    retry_count:     int = 0
    error:           Optional[str] = None
    created_at:      str = ""
    completed_at:    Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(**data)


class TaskManager:
    """Manages image generation tasks with persistence to .task_state.json."""

    STATE_FILE = ".task_state.json"

    def __init__(
        self,
        input_dir: str,
        output_dir: Optional[str] = None,
        output_subdir: str = "generated",
    ) -> None:
        self.input_dir  = Path(input_dir).resolve()
        self.output_dir = (
            Path(output_dir).resolve() if output_dir
            else self.input_dir / output_subdir
        )
        self.state_file = self.input_dir / self.STATE_FILE
        self.tasks: Dict[str, Task] = {}
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── persistence ────────────────────────────────────────────────────────────

    def load_tasks(self) -> Dict[str, Task]:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.tasks = {
                    tid: Task.from_dict(td)
                    for tid, td in data.get("tasks", {}).items()
                }
            except (json.JSONDecodeError, KeyError, TypeError):
                self.tasks = {}
        return self.tasks

    def save_tasks(self) -> None:
        data = {
            "version":    "1.0",
            "updated_at": datetime.now().isoformat(),
            "input_dir":  str(self.input_dir),
            "output_dir": str(self.output_dir),
            "tasks":      {tid: t.to_dict() for tid, t in self.tasks.items()},
            "stats":      self.get_stats(),
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── task CRUD ──────────────────────────────────────────────────────────────

    def scan_prompts(self) -> List[Task]:
        """Scan input_dir for *.md files and create tasks for new ones."""
        self.load_tasks()
        new_tasks: List[Task] = []

        for md_file in sorted(self.input_dir.glob("*.md")):
            task_id = md_file.stem
            if task_id in self.tasks:
                continue
            try:
                content = md_file.read_text(encoding="utf-8").strip()
            except Exception:
                continue
            task = Task(
                id             = task_id,
                prompt_file    = md_file.name,
                prompt_content = content,
                output_path    = str(self.output_dir / f"{task_id}.png"),
            )
            self.tasks[task_id] = task
            new_tasks.append(task)

        if new_tasks:
            self.save_tasks()
        return new_tasks

    def create_task(self, md_file: Path) -> Task:
        """Create (or overwrite) a task from a single markdown file."""
        task_id = md_file.stem
        content = md_file.read_text(encoding="utf-8").strip()
        task = Task(
            id             = task_id,
            prompt_file    = md_file.name,
            prompt_content = content,
            output_path    = str(self.output_dir / f"{task_id}.png"),
        )
        self.tasks[task_id] = task
        self.save_tasks()
        return task

    def update_task(self, task: Task, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        self.save_tasks()

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    # ── queries ────────────────────────────────────────────────────────────────

    def get_pending_tasks(self) -> List[Task]:
        return [
            t for t in self.tasks.values()
            if t.status in (TaskStatus.PENDING.value, TaskStatus.RETRYING.value)
        ]

    def get_running_tasks(self) -> List[Task]:
        return [t for t in self.tasks.values() if t.status == TaskStatus.RUNNING.value]

    def get_completed_tasks(self) -> List[Task]:
        return [t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED.value]

    def get_failed_tasks(self) -> List[Task]:
        return [t for t in self.tasks.values() if t.status == TaskStatus.FAILED.value]

    def get_stats(self) -> dict:
        return {
            "total":     len(self.tasks),
            "pending":   len(self.get_pending_tasks()),
            "running":   len(self.get_running_tasks()),
            "completed": len(self.get_completed_tasks()),
            "failed":    len(self.get_failed_tasks()),
        }

    # ── bulk operations ────────────────────────────────────────────────────────

    def retry_failed(self) -> int:
        """Reset all failed tasks to pending; return count reset."""
        count = 0
        for task in self.get_failed_tasks():
            task.status      = TaskStatus.PENDING.value
            task.retry_count = 0
            task.error       = None
            count += 1
        if count:
            self.save_tasks()
        return count

    def clear_completed(self) -> int:
        """Remove completed tasks from tracking (images are kept); return count."""
        ids = [t.id for t in self.get_completed_tasks()]
        for tid in ids:
            del self.tasks[tid]
        if ids:
            self.save_tasks()
        return len(ids)

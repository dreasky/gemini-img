"""Simple task model for browser automation."""

import json
import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Callable


class TaskStatus(Enum):
    """Task status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """
    Browser automation task.

    Add fields by subclassing or just use extra dict:

        # Subclass for typed fields
        @dataclass
        class MyTask(Task):
            image_url: str = ""

        # Or use extra dict for dynamic fields
        task = Task(id="x", prompt_content="y")
        task.extra["image_url"] = "..."
    """

    id: str
    data: str
    status: TaskStatus = TaskStatus.PENDING
    output_path: Optional[Path] = None
    error: Optional[str] = None
    retry_count: int = 0
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        """
        Post-initialization processing.

        Automatically cleans the 'data' field upon instantiation.
        """
        if isinstance(self.data, str):
            self.data = self._clean_content(self.data)

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        result = asdict(self)
        result["status"] = self.status.value
        # Convert Path to string for JSON serialization
        if self.output_path is not None:
            result["output_path"] = str(self.output_path)
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Create from dict. Ignores unknown fields for forward compatibility."""
        data = dict(data)  # copy
        data["status"] = TaskStatus(data.pop("status"))
        extra = data.pop("extra", {})
        # Convert string back to Path for output_path
        if data.get("output_path"):
            data["output_path"] = Path(data["output_path"])
        # Ignore unknown fields (e.g. legacy created_at/updated_at/completed_at)
        known = {f.name for f in cls.__dataclass_fields__.values()}
        data = {k: v for k, v in data.items() if k in known}
        task = cls(**data)
        task.extra = extra
        return task

    @staticmethod
    def _clean_content(text: str) -> str:
        """
        Clean content by removing common formatting.

        Removes:
        - Markdown bold/italic (*text*, **text**)
        - Inline code (`code`)
        - Excessive newlines (converts \n\n+ to single \n)
        - Excessive whitespace
        """
        if not text:
            return ""

        # Remove markdown bold/italic
        text = re.sub(r"\*\*?(.+?)\*\*?", r"\1", text)
        # Remove inline code
        text = re.sub(r"`{1,3}(.+?)`{1,3}", r"\1", text, flags=re.DOTALL)
        # Remove excessive newlines
        text = re.sub(r"\n{2,}", "\n", text)
        # Clean up whitespace
        return text.strip()



class TaskStore:
    """
    JSON file store for tasks.

    Specialized for JSON persistence with UTF-8 encoding.

    Usage:
        store = JsonStore("tasks.json")
        store.add(task)
        store.save()

        pending = store.filter(TaskStatus.PENDING)
    """

    def __init__(
        self,
        input_dir: Path,
        output_dir: Optional[Path] = None,
        store_name: Optional[str] = None,
    ) -> None:
        self.input_dir = input_dir

        # 输出目录，默认输入目录下
        self.output_dir = output_dir if output_dir else self.input_dir / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 状态储存路径，输出目录下
        store_name = store_name or "task_store.json"
        if not store_name.endswith(".json"):
            store_name += ".json"
        self.json_file = self.output_dir / store_name

        self._tasks: Dict[str, Task] = {}
        self._load()

    def _load(self) -> None:
        """Load from JSON."""
        if self.json_file.exists() and self.json_file.stat().st_size > 0:
            data = json.loads(self.json_file.read_text(encoding="utf-8"))
            self._tasks = {k: Task.from_dict(v) for k, v in data.items()}

    def save(self) -> None:
        """Save to JSON."""
        self.json_file.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.to_dict() for k, v in self._tasks.items()}
        self.json_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def add(self, task: Task) -> None:
        """Add or update a task."""
        self._tasks[task.id] = task

    def get(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self._tasks.get(task_id)

    def remove(self, task_id: str) -> bool:
        """Remove task by ID. Returns True if existed."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    def all(self) -> List[Task]:
        """Get all tasks."""
        return list(self._tasks.values())

    def filter(self, status: TaskStatus) -> List[Task]:
        """Filter by status."""
        return [t for t in self._tasks.values() if t.status == status]

    @property
    def pending(self) -> List[Task]:
        """Get pending tasks."""
        return self.filter(TaskStatus.PENDING)

    @property
    def completed(self) -> List[Task]:
        """Get completed tasks."""
        return self.filter(TaskStatus.COMPLETED)

    @property
    def failed(self) -> List[Task]:
        """Get failed tasks."""
        return self.filter(TaskStatus.FAILED)

    def reset_failed(self) -> int:
        """Reset failed tasks to pending. Returns count."""
        count = 0
        for task in self._tasks.values():
            if task.status == TaskStatus.FAILED:
                task.status = TaskStatus.PENDING
                task.retry_count = 0
                task.error = None
                count += 1
        return count

    @property
    def stats(self) -> dict:
        """Get task statistics."""
        return {
            "pending": len(self.pending),
            "completed": len(self.completed),
            "failed": len(self.failed),
        }

    def scan_files(
        self,
        pattern: str = "*.md",
        extractor: Optional[Callable[[Path], Dict]] = None,
        output_ext: str = ".png",
    ) -> int:
        """
        Scan files and create tasks.

        Args:
            pattern: Glob pattern for files (e.g., "*.md", "*.txt")
            extractor: Function to extract task data from file.
                      Should return dict with at least "data" key.
                      Can also include "output_path", "extra", etc.
            output_ext: Extension for output files

        Returns:
            Number of new tasks created
        """
        count = 0

        for file_path in self.input_dir.glob(pattern):
            task_id = file_path.stem
            existing = self._tasks.get(task_id)

            # Completed tasks are never overwritten
            if existing and existing.status == TaskStatus.COMPLETED:
                continue

            # For pending/failed tasks: preserve existing extra dict
            # (may contain conversation_url etc. from prior attempts)
            preserve_extra = existing.extra if existing else {}

            # Default output path
            output_path = self.output_dir / f"{task_id}{output_ext}"

            if extractor:
                # Use custom extractor
                extracted = extractor(file_path)
                task = Task(
                    id=task_id,
                    data=extracted.get("data", file_path.read_text(encoding="utf-8")),
                    output_path=extracted.get("output_path", str(output_path)),
                    extra={**preserve_extra, **extracted.get("extra", {})},
                )
            else:
                # Default: read text content
                content = file_path.read_text(encoding="utf-8")
                task = Task(
                    id=task_id,
                    data=self._clean_content(content),
                    output_path=output_path,
                    extra=preserve_extra,
                )
            self.add(task)
            count += 1

        if count > 0:
            self.save()

        return count

    def get_output_path(self, task_id: str, ext: str = ".png") -> str:
        """Get default output path for task."""
        return str(self.output_dir / f"{task_id}{ext}")

    def list_source_files(self, pattern: str = "*.md") -> List[Path]:
        """List all source files matching pattern."""
        return sorted(self.input_dir.glob(pattern))

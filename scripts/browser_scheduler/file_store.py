"""Store extension for file scanning tasks."""

import re
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .models import Task, TaskStore


class FileScanningStore:
    """
    Store that can scan files to create tasks.

    Usage:
        store = FileScanningStore("tasks.json", "./prompts")
        count = store.scan_files("*.md")
        print(f"Created {count} tasks from .md files")

        # With custom extractor
        def extract_json(path: Path) -> dict:
            import json
            data = json.loads(path.read_text())
            return {"data": data["prompt"], "extra": {"category": data["category"]}}

        store.scan_files("*.json", extractor=extract_json)
    """

    def __init__(
        self,
        state_path: str | Path,
        tasks_dir: str | Path,
        output_dir: Optional[str | Path] = None,
    ):
        self.task_store = TaskStore(state_path)
        self.tasks_dir = Path(tasks_dir)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)

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

        for file_path in self.tasks_dir.glob(pattern):
            task_id = file_path.stem
            if task_id in self._tasks:
                continue

            # Default output path
            output_path = self.output_dir / f"{task_id}{output_ext}"

            if extractor:
                # Use custom extractor
                extracted = extractor(file_path)
                task = Task(
                    id=task_id,
                    data=extracted.get("data", file_path.read_text(encoding="utf-8")),
                    output_path=extracted.get("output_path", str(output_path)),
                    extra=extracted.get("extra", {}),
                )
            else:
                # Default: read text content
                content = file_path.read_text(encoding="utf-8")
                task = Task(
                    id=task_id,
                    data=self._clean_content(content),
                    output_path=output_path,
                )
            self.add(task)
            count += 1

        if count > 0:
            self._save()

        return count

    @staticmethod
    def _clean_content(text: str) -> str:
        """
        Clean content by removing common formatting.

        Removes:
        - Markdown bold/italic (*text*, **text**)
        - Inline code (`code`)
        - Excessive whitespace
        """
        # Remove markdown bold/italic
        text = re.sub(r"\*\*?(.+?)\*\*?", r"\1", text)
        # Remove inline code
        text = re.sub(r"`{1,3}(.+?)`{1,3}", r"\1", text, flags=re.DOTALL)
        # Clean up whitespace
        return text.strip()

    def get_output_path(self, task_id: str, ext: str = ".png") -> str:
        """Get default output path for task."""
        return str(self.output_dir / f"{task_id}{ext}")

    def list_source_files(self, pattern: str = "*.md") -> List[Path]:
        """List all source files matching pattern."""
        return sorted(self.tasks_dir.glob(pattern))

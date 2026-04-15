"""Gemini visible watermark remover — thin Python wrapper around the gwr Node CLI."""

import json
import subprocess
import sys
from pathlib import Path

# skill root: scripts/gemini/watermark.py → scripts/gemini/ → scripts/ → skill/
_SKILL_DIR = Path(__file__).parent.parent.parent
_GWR_BIN = _SKILL_DIR / "node_modules/@pilio/gemini-watermark-remover/bin/gwr.mjs"


def _log(msg: str) -> None:
    print(f"[gemini-img] {msg}", file=sys.stderr)


def remove_gemini_watermark(image_path: str) -> bool:
    """Remove the Gemini sparkle watermark from an image in-place.

    Returns True if the watermark was found and removed, False otherwise.
    Silently skips if the gwr binary is not installed.
    """
    if not _GWR_BIN.exists():
        _log(f"gwr not found at {_GWR_BIN}, skipping watermark removal")
        return False

    path = Path(image_path)
    if not path.exists():
        _log(f"Image not found: {path}")
        return False

    try:
        result = subprocess.run(
            [
                "node",
                str(_GWR_BIN),
                "remove",
                str(path),
                "--output",
                str(path),
                "--overwrite",
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            _log(f"gwr failed: {result.stderr.strip()[:200]}")
            return False

        try:
            meta = json.loads(result.stdout.strip())
            applied = meta.get("meta", {}).get("applied", False)
            pos = meta.get("meta", {}).get("position", {})
            if applied:
                _log(
                    f"Watermark removed: pos=({pos.get('x')},{pos.get('y')}) "
                    f"size={pos.get('width')}x{pos.get('height')}"
                )
            else:
                skip = meta.get("meta", {}).get("skipReason", "unknown")
                _log(f"Watermark not detected (skipReason={skip})")
            return applied
        except Exception:
            _log("Watermark removal ran (could not parse JSON output)")
            return True

    except subprocess.TimeoutExpired:
        _log("gwr timed out after 60s")
        return False
    except Exception as e:
        _log(f"gwr error: {e}")
        return False

"""
Gemini visible watermark remover using @pilio/gemini-watermark-remover.
Calls the gwr CLI via Node.js — reverse alpha blending, lossless.
"""

import json
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent.parent
GWR_BIN = SKILL_DIR / "node_modules/@pilio/gemini-watermark-remover/bin/gwr.mjs"


def remove_gemini_watermark(image_path) -> bool:
    """
    Remove the Gemini sparkle watermark from an image in-place.

    Uses the locally installed @pilio/gemini-watermark-remover npm package.
    Calls gwr.mjs directly via Node.js (no npx, no shell — cross-platform).

    Args:
        image_path: Path to image file (str or Path)

    Returns:
        True if watermark was found and removed, False otherwise
    """
    if not GWR_BIN.exists():
        print(f"[watermark] gwr not found at {GWR_BIN}", file=sys.stderr)
        return False

    path = Path(image_path) if not isinstance(image_path, Path) else image_path
    if not path.exists():
        print(f"[watermark] image not found: {path}", file=sys.stderr)
        return False

    try:
        result = subprocess.run(
            ["node", str(GWR_BIN), "remove", str(path),
             "--output", str(path), "--overwrite", "--json"],
            capture_output=True, text=True, timeout=60,
        )

        if result.returncode != 0:
            print(f"[watermark] gwr failed: {result.stderr.strip()[:200]}", file=sys.stderr)
            return False

        # Parse JSON output
        try:
            meta = json.loads(result.stdout.strip())
            applied = meta.get("meta", {}).get("applied", False)
            if applied:
                pos = meta.get("meta", {}).get("position", {})
                print(f"[watermark] removed: pos=({pos.get('x')},{pos.get('y')}) "
                      f"size={pos.get('width')}x{pos.get('height')}", file=sys.stderr)
            else:
                reason = meta.get("meta", {}).get("skipReason", "unknown")
                print(f"[watermark] not detected (skipReason={reason})", file=sys.stderr)
            return applied
        except Exception as e:
            print(f"[watermark] JSON parse error: {e}", file=sys.stderr)
            return True

    except subprocess.TimeoutExpired:
        print("[watermark] timed out after 60s", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[watermark] error: {e}", file=sys.stderr)
        return False

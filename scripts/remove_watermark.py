"""
Gemini visible watermark remover using @pilio/gemini-watermark-remover.
Calls the gwr CLI via Node.js — reverse alpha blending, lossless.
"""

import sys
import subprocess
import json
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
GWR_BIN   = SKILL_DIR / "node_modules/@pilio/gemini-watermark-remover/bin/gwr.mjs"


def log(msg: str):
    print(f"[gemini-img] {msg}", file=sys.stderr)


def remove_gemini_watermark(image_path: str) -> bool:
    """
    Remove the Gemini sparkle watermark from an image in-place.
    Returns True if watermark was found and removed, False otherwise.
    """
    if not GWR_BIN.exists():
        log(f"gwr not found at {GWR_BIN}, skipping watermark removal")
        return False

    path = Path(image_path)
    if not path.exists():
        log(f"Image not found: {path}")
        return False

    try:
        result = subprocess.run(
            ["node", str(GWR_BIN), "remove", str(path),
             "--output", str(path), "--overwrite", "--json"],
            capture_output=True, text=True, timeout=60,
        )

        if result.returncode != 0:
            log(f"gwr failed: {result.stderr.strip()[:200]}")
            return False

        # Parse JSON output for logging
        try:
            meta = json.loads(result.stdout.strip())
            applied = meta.get("meta", {}).get("applied", False)
            pos     = meta.get("meta", {}).get("position", {})
            if applied:
                log(f"Watermark removed: pos=({pos.get('x')},{pos.get('y')}) "
                    f"size={pos.get('width')}x{pos.get('height')}")
            else:
                skip = meta.get("meta", {}).get("skipReason", "unknown")
                log(f"Watermark not detected (skipReason={skip})")
            return applied
        except Exception:
            log("Watermark removal ran (could not parse JSON output)")
            return True

    except subprocess.TimeoutExpired:
        log("gwr timed out after 60s")
        return False
    except Exception as e:
        log(f"gwr error: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: remove_watermark.py <image_path>")
        sys.exit(1)
    success = remove_gemini_watermark(sys.argv[1])
    sys.exit(0 if success else 1)

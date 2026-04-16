"""Remove Gemini watermark from images."""

import subprocess
from pathlib import Path


def remove_gemini_watermark(image_path) -> bool:
    """
    Remove Gemini sparkle watermark from image.

    Uses @pilio/gemini-watermark-remover npm package.

    Args:
        image_path: Path to image file

    Returns:
        True if successful, False otherwise
    """
    if isinstance(image_path, str):
        image_path = Path(image_path)

    if not image_path.exists():
        return False

    try:
        result = subprocess.run(
            ["npx", "@pilio/gemini-watermark-remover", str(image_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception as e:
        print(e)
        return False


def batch_remove_watermark(directory: Path, recursive: bool = False) -> tuple[int, int]:
    """
    Remove watermarks from all PNG images in directory.

    Args:
        directory: Directory to scan
        recursive: Whether to scan subdirectories

    Returns:
        (success_count, fail_count)
    """
    pattern = "**/*.png" if recursive else "*.png"
    files = sorted(directory.glob(pattern))

    success = fail = 0
    for f in files:
        if remove_gemini_watermark(f):
            success += 1
        else:
            fail += 1

    return success, fail

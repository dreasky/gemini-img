"""
Remove the Gemini sparkle watermark from PNG images.

Usage:
    python remove_watermark.py FILE [FILE ...]
    python remove_watermark.py batch DIR [--recursive]
"""

import sys
from pathlib import Path

import click

from gemini.watermark import remove_gemini_watermark


@click.group()
def cli():
    """Gemini watermark remover."""


@cli.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
def remove(files):
    """Remove watermark from one or more image files."""
    ok = fail = 0
    for f in files:
        if remove_gemini_watermark(f):
            ok += 1
        else:
            fail += 1
    click.echo(f"Done: {ok} removed, {fail} skipped/failed.")
    sys.exit(0 if fail == 0 else 1)


@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("-r", "--recursive", is_flag=True, help="搜索子目录中的 PNG 文件")
@click.option("--dry-run", is_flag=True, help="仅列出待处理文件，不执行操作")
def batch(directory, recursive, dry_run):
    """批量处理目录中所有 PNG 文件。"""
    base = Path(directory)
    pattern = "**/*.png" if recursive else "*.png"
    files = sorted(base.glob(pattern))

    if not files:
        click.echo(f"未在 {base} 中找到 PNG 文件。")
        sys.exit(0)

    click.echo(f"找到 {len(files)} 个 PNG 文件。")

    if dry_run:
        for f in files:
            click.echo(f"  {f}")
        sys.exit(0)

    ok = fail = 0
    for f in files:
        click.echo(f"处理: {f}", nl=False)
        if remove_gemini_watermark(str(f)):
            click.echo(" [已移除]")
            ok += 1
        else:
            click.echo(" [跳过]")
            fail += 1

    click.echo(f"\n完成: {ok} 个已移除水印，{fail} 个跳过/失败。")
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    cli()

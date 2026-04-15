#!/usr/bin/env python3
"""Gemini Image Generator — Click CLI entry point."""

import json
import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent))
from gemini import GeminiImageGenerator


@click.group()
def cli():
    """Generate images with Gemini via a headless browser."""


@cli.command()
def login():
    """One-time login — saves cookies to storage_state.json."""
    GeminiImageGenerator().login()


@cli.command()
@click.argument("prompt")
@click.option(
    "-o", "--output",
    default=None,
    help="Output file path (default: ~/Desktop/<prompt>_<timestamp>.png)",
)
@click.option(
    "--count",
    default=1,
    show_default=True,
    help="Number of images to generate.",
)
@click.option(
    "--headed",
    is_flag=True,
    default=False,
    help="Run browser in headed (visible) mode.",
)
def generate(prompt: str, output: str | None, count: int, headed: bool):
    """Generate an image for PROMPT using the saved session."""
    gen     = GeminiImageGenerator(headless=not headed)
    results = gen.generate(prompt, output, count)
    click.echo(
        json.dumps(
            {"success": True, "files": results, "prompt": prompt, "count": len(results)},
            ensure_ascii=False,
        )
    )


def main():
    cli()


if __name__ == "__main__":
    main()

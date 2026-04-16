"""
Utility functions for browser automation.

Provides both sync and async versions of common operations.
"""

from typing import Awaitable, Callable


def insert_text_with_newlines(
    page,
    selector: str,
    text: str,
) -> Awaitable:
    """
    Insert text into a contenteditable element, preserving newlines.

    This is the preferred method over keyboard.type() because:
    - keyboard.type() treats \\n as Enter key presses, triggering submission
    - This method uses JS to insert text directly with <br> for newlines

    Args:
        page: Playwright page object (sync or async)
        selector: CSS selector for the contenteditable element
        text: Text to insert (can contain \\n for newlines)

    Returns:
        Awaitable if page is async, or direct result if sync
    """
    return page.evaluate(
        """(args) => {
            const [selector, text] = args;
            const editor = document.querySelector(selector);
            if (!editor) throw new Error(`Element not found: ${selector}`);
            editor.focus();

            // Clear existing content
            editor.innerHTML = '';

            // Split by newlines and insert
            const lines = text.split('\\n');
            lines.forEach((line, i) => {
                if (i > 0) {
                    editor.appendChild(document.createElement('br'));
                }
                if (line) {
                    editor.appendChild(document.createTextNode(line));
                }
            });
        }""",
        [selector, text],
    )


def clear_contenteditable(
    page,
    selector: str,
) -> Awaitable:
    """
    Clear a contenteditable element.

    Args:
        page: Playwright page object
        selector: CSS selector for the element

    Returns:
        Awaitable if page is async, or direct result if sync
    """
    return page.evaluate(
        """(selector) => {
            const el = document.querySelector(selector);
            if (el) {
                el.innerHTML = '';
                // Also clear using execCommand for compatibility
                document.execCommand('selectAll', false, null);
                document.execCommand('delete', false, null);
            }
        }""",
        selector,
    )

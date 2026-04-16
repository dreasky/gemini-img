"""
Utility functions for browser automation.

Provides both sync and async versions of common operations.
"""

import re
from typing import Awaitable, Callable


def _normalize_text(text: str) -> str:
    """Normalize text for input: collapse multiple blank lines into one."""
    # Replace 2+ consecutive blank lines with a single blank line
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text


def insert_text_with_newlines(
    page,
    selector: str,
    text: str,
) -> Awaitable:
    """
    Insert text into a contenteditable element, preserving newlines.

    Strategy (ordered by reliability):
    1. Quill API — if Quill instance is found, uses quill.clipboard.dangerouslyPasteHTML
       which properly updates Quill's internal model AND the DOM.
    2. DOM API fallback — for non-Quill editors, builds nodes with createElement.

    Text normalization:
    - Collapses 3+ consecutive newlines into 2 (one blank line)
    - Strips leading/trailing whitespace

    IMPORTANT: Does NOT use innerHTML directly (Trusted Types CSP violation).
    IMPORTANT: Does NOT use busy-wait in JS (blocks browser main thread).

    Args:
        page: Playwright page object (sync or async)
        selector: CSS selector for the contenteditable element
        text: Text to insert (can contain \\n for newlines)

    Returns:
        Awaitable if page is async, or direct result if sync
    """
    text = _normalize_text(text)

    js_code = """
    (args) => {
        const [selector, text] = args;

        function findEditor() {
            const bySelector = document.querySelector(selector);
            if (bySelector && bySelector.isContentEditable) {
                return bySelector;
            }
            const candidates = [
                '.ql-editor',
                '.ql-editor[contenteditable="true"]',
                'div[contenteditable="true"]',
                'div[contenteditable="plaintext-only"]',
                '[data-test-id*="input"]',
                'div[role="textbox"]',
            ];
            for (let i = 0; i < candidates.length; i++) {
                const el = document.querySelector(candidates[i]);
                if (el && el.isContentEditable) return el;
            }
            const all = document.querySelectorAll('[contenteditable]');
            for (let i = 0; i < all.length; i++) {
                if (all[i].isContentEditable) return all[i];
            }
            return null;
        }

        const editor = findEditor();
        if (!editor) {
            throw new Error('No contenteditable element found.');
        }

        editor.focus();

        // ---- Strategy 1: Quill API ----
        // Quill stores its instance on the .ql-container parent element
        const qlContainer = editor.closest('.ql-container') || editor.parentElement;
        if (qlContainer) {
            // Quill attaches __quill on the .ql-container or .ql-editor depending on version
            const quill = qlContainer.__quill
                || (qlContainer.querySelector('.ql-editor') || {}).__quill
                || editor.__quill;
            if (quill && quill.clipboard && quill.clipboard.dangerouslyPasteHTML) {
                // Build HTML string for Quill — dangerouslyPasteHTML bypasses
                // innerHTML assignment (it uses its own parser that satisfies Trusted Types)
                const lines = text.split('\\n');
                let html = '';
                for (let i = 0; i < lines.length; i++) {
                    if (lines[i]) {
                        html += '<p>' + lines[i] + '</p>';
                    } else {
                        html += '<p><br></p>';
                    }
                }
                quill.clipboard.dangerouslyPasteHTML(html);
                quill.setSelection(quill.getLength(), 0);
                return;
            }
        }

        // ---- Strategy 2: DOM API fallback (non-Quill) ----
        while (editor.firstChild) {
            editor.removeChild(editor.firstChild);
        }
        const lines = text.split('\\n');
        for (let i = 0; i < lines.length; i++) {
            const p = document.createElement('p');
            if (lines[i]) {
                p.appendChild(document.createTextNode(lines[i]));
            } else {
                p.appendChild(document.createElement('br'));
            }
            editor.appendChild(p);
        }
        editor.dispatchEvent(new Event('input', { bubbles: true }));
    }
    """
    return page.evaluate(js_code, [selector, text])


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
    js_code = """
    (selector) => {
        const el = document.querySelector(selector);
        if (el) {
            // Clear using DOM API only (avoids TrustedHTML violation)
            while (el.firstChild) {
                el.removeChild(el.firstChild);
            }

            // Quill editor expects at least <p><br></p>
            if (el.classList.contains('ql-editor')) {
                const p = document.createElement('p');
                p.appendChild(document.createElement('br'));
                el.appendChild(p);
            }

            // Dispatch input event
            el.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }
    """
    return page.evaluate(js_code, selector)

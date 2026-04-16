"""
Utility functions for browser automation.
"""

import re
from typing import Awaitable


def _normalize_text(text: str) -> str:
    """Normalize text for input: collapse multiple blank lines into one."""
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def insert_text_with_newlines(
    page,
    selector: str,
    text: str,
) -> Awaitable:
    """
    Insert text into a contenteditable element, preserving newlines.

    Strategy (ordered by reliability):
    1. Quill Delta API — uses quill.setContents() with Delta objects.
       Bypasses innerHTML entirely (no Trusted Types violation)
       and correctly updates Quill's internal model.
    2. DOM API fallback — for non-Quill editors.

    Text normalization:
    - Collapses 3+ consecutive newlines into 2 (one blank line)
    - Strips leading/trailing whitespace
    """
    text = _normalize_text(text)

    js_code = """
    (args) => {
        const [selector, text] = args;

        function findEditor() {
            const bySelector = document.querySelector(selector);
            if (bySelector && bySelector.isContentEditable) return bySelector;
            const candidates = [
                '.ql-editor',
                'div[contenteditable="true"]',
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

        function findQuill(editor) {
            const qlContainer = editor.closest('.ql-container') || editor.parentElement;
            if (qlContainer && qlContainer.__quill) return qlContainer.__quill;
            if (editor.__quill) return editor.__quill;
            return null;
        }

        const editor = findEditor();
        if (!editor) throw new Error('No contenteditable element found.');
        editor.focus();

        const quill = findQuill(editor);
        if (quill && quill.setContents) {
            const lines = text.split('\\n');
            var ops = [];
            for (var i = 0; i < lines.length; i++) {
                if (lines[i]) ops.push({ insert: lines[i] });
                if (i < lines.length - 1) ops.push({ insert: '\\n' });
            }
            if (ops.length === 0) ops.push({ insert: '\\n' });
            quill.setContents({ ops: ops });
            quill.setSelection(quill.getLength(), 0);
            return;
        }

        // DOM API fallback
        while (editor.firstChild) editor.removeChild(editor.firstChild);
        const lines = text.split('\\n');
        for (var i = 0; i < lines.length; i++) {
            var p = document.createElement('p');
            p.appendChild(lines[i] ? document.createTextNode(lines[i]) : document.createElement('br'));
            editor.appendChild(p);
        }
        editor.dispatchEvent(new Event('input', { bubbles: true }));
    }
    """
    return page.evaluate(js_code, [selector, text])


def clear_contenteditable(page, selector: str) -> Awaitable:
    """Clear a contenteditable element. Uses Quill Delta API or DOM API."""
    js_code = """
    (selector) => {
        var el = document.querySelector(selector);
        if (!el) return;
        var qlContainer = el.closest('.ql-container') || el.parentElement;
        var quill = (qlContainer && qlContainer.__quill) || el.__quill || null;
        if (quill && quill.setContents) {
            quill.setContents({ ops: [{ insert: '\\n' }] });
            quill.setSelection(0, 0);
            return;
        }
        while (el.firstChild) el.removeChild(el.firstChild);
        if (el.classList.contains('ql-editor')) {
            var p = document.createElement('p');
            p.appendChild(document.createElement('br'));
            el.appendChild(p);
        }
        el.dispatchEvent(new Event('input', { bubbles: true }));
    }
    """
    return page.evaluate(js_code, selector)

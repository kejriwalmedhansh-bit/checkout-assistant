"""Does the extension's wiring actually connect?

Not behaviour — wiring. Every name one file calls on another must exist in it.

This file exists because of a bug shipped on 2026-09-07. Rewriting one screen,
a text edit sliced from the start of one function to a comment further down the
file and replaced the lot, silently deleting `renderBackAtStore` and
`renderPlaceOrder`. `node --check` passed, because the result is perfectly
valid JavaScript — the names are simply gone. The extension then failed at the
one moment that matters most, back at the shop holding a voucher code, with
"Uncaught ReferenceError: renderBackAtStore is not defined".

Nothing would have caught it. The routing checks cover the backend; the
extension had no checks at all. These are cheap and would have caught it in
seconds, along with the earlier bug where the panel counted vouchers while the
state machine counted checkouts.

Run:  .venv/bin/python tests/test_extension_wiring.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "extension" / "src"
POPUP = (SRC / "popup.js").read_text()
CONTENT = (SRC / "content.js").read_text()
BACKGROUND = (SRC / "background.js").read_text()


def _exported_popup_names() -> set[str]:
    """The names popup.js hands out on window.__dealoPopup."""
    tail = POPUP[POPUP.rfind("return {"):]
    tail = tail[: tail.index("}")]
    return {n.strip() for n in tail.replace("return {", "").split(",") if n.strip()}


def test_every_name_popup_exports_is_defined():
    missing = [
        name for name in _exported_popup_names()
        if not re.search(rf"function\s+{re.escape(name)}\b|(?:const|let)\s+{re.escape(name)}\s*=", POPUP)
    ]
    assert not missing, f"popup.js exports names it does not define: {missing}"


def test_content_only_calls_popup_functions_that_exist():
    called = set(re.findall(r"window\.__dealoPopup\.(\w+)\s*\(", CONTENT))
    exported = _exported_popup_names()
    missing = sorted(called - exported)
    assert not missing, f"content.js calls popup functions that don't exist: {missing}"


def test_every_message_content_sends_has_a_handler():
    """content.js asks the worker for things by name. A typo here is silent:
    the worker answers nothing and Dealo just stops, which is exactly how a
    trip used to strand someone mid-purchase."""
    sent = set(re.findall(r'ask\(\{\s*type:\s*"(\w+)"', CONTENT))
    sent |= set(re.findall(r'type:\s*"(\w+)"[^}]*\}\s*\)\s*;?\s*//\s*message', CONTENT))
    handlers_block = BACKGROUND[BACKGROUND.index("const HANDLERS"):]
    handlers_block = handlers_block[: handlers_block.index("\n};")]
    handled = set(re.findall(r"^\s*(\w+):", handlers_block, re.M))
    missing = sorted(sent - handled)
    assert not missing, f"content.js sends messages the worker has no handler for: {missing}"


def test_every_file_parses():
    for name in ("config.js", "popup.js", "content.js", "background.js", "welcome.js"):
        r = subprocess.run(["node", "--check", str(SRC / name)], capture_output=True, text=True)
        assert r.returncode == 0, f"{name} does not parse:\n{r.stderr}"


if __name__ == "__main__":
    checks = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for check in checks:
        try:
            check()
            print(f"  ok    {check.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {check.__name__}\n        {e}")
    print(f"\n{len(checks) - failed}/{len(checks)} passed")
    sys.exit(1 if failed else 0)

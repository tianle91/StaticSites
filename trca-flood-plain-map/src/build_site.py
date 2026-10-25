#!/usr/bin/env python3
"""Build the single-file map offline from the committed snapshot and template."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"


def render(data):
    # Escape HTML script terminators even when they appear in upstream text.
    payload = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return (ROOT / "src/page.html").read_text(encoding="utf-8").replace("__PAYLOAD__", payload)


def main():
    data = json.loads((DATA_DIR / "floodplain.json").read_text(encoding="utf-8"))
    html = render(data)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "trca-flood-plain-map.html"
    if not path.exists() or path.read_text(encoding="utf-8") != html:
        path.write_text(html, encoding="utf-8")
    print("Built " + str(path))


if __name__ == "__main__":
    main()

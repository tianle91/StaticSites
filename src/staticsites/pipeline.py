"""Content-aware publication and caches. Source-specific validation stays local."""
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import tempfile


def write_if_changed(path, content):
    path = Path(path)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def write_snapshot(path, substantive):
    """Timestamp changes in validated, normalized records, not refresh attempts."""
    path = Path(path)
    existing = json.loads(path.read_text()) if path.exists() else {}
    if {k: v for k, v in existing.items() if k != "retrieved_at"} == substantive:
        return False
    payload = {"retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **substantive}
    # Encode before touching the target; nonfinite values must fail publication.
    return write_if_changed(path, json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def record_pull_date(root, stamp, changed, *, today=date.today):
    if not changed and stamp.exists():
        return
    value = today().isoformat()
    rendered = root / "output" / (root.name + ".html")
    if not changed and rendered.exists():
        match = re.search(r"Data pulled (\d{4}-\d{2}-\d{2})", rendered.read_text(encoding="utf-8"))
        if match:
            try:
                value = date.fromisoformat(match[1]).isoformat()
            except ValueError:
                pass
    write_if_changed(stamp, value + "\n")


def cached_lookup(cache, key, lookup, persist):
    """Cache genuine misses, never service exceptions; keep each project's cache."""
    if key in cache:
        return cache[key]
    value = lookup()
    cache[key] = value
    try:
        persist()
    except BaseException:
        del cache[key]
        raise
    return value

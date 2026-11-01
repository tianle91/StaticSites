"""Publication failures must not leave half of the reviewed image pair updated."""
import pytest

import snapshot_site


def test_failed_mobile_capture_preserves_both_images(tmp_path, monkeypatch):
    for name in snapshot_site.VIEWS:
        (tmp_path / f"{name}.jpg").write_bytes(b"reviewed " + name.encode())

    def capture(_browser, _url, name, _size):
        if name == "mobile":
            raise RuntimeError("tiles did not load")
        return b"new desktop"

    monkeypatch.setattr(snapshot_site, "capture", capture)
    with pytest.raises(RuntimeError, match="tiles did not load"):
        snapshot_site.generate(None, "unused", tmp_path)
    for name in snapshot_site.VIEWS:
        assert (tmp_path / f"{name}.jpg").read_bytes() == b"reviewed " + name.encode()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["desktop.jpg", "mobile.jpg"]


def test_unchanged_images_keep_their_mtime(tmp_path):
    captures = {name: name.encode() for name in snapshot_site.VIEWS}
    snapshot_site.publish(captures, tmp_path)
    before = {path.name: path.stat().st_mtime_ns for path in tmp_path.iterdir()}
    snapshot_site.publish(captures, tmp_path)
    assert before == {path.name: path.stat().st_mtime_ns for path in tmp_path.iterdir()}

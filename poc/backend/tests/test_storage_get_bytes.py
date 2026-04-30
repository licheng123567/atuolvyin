import os
import pytest


def test_local_file_storage_get_bytes():
    from app.core.storage import LocalFileStorage

    ls = LocalFileStorage()
    expected = b"sprint3b test audio bytes"
    key = "test_get_bytes/unique_sample.mp3"
    ls.put_object(key, expected, "audio/mpeg")
    try:
        result = ls.get_bytes(key)
        assert result == expected
    finally:
        path = ls.local_path(key)
        if os.path.exists(path):
            os.unlink(path)


def test_local_file_storage_get_bytes_missing_key_raises():
    from app.core.storage import LocalFileStorage

    ls = LocalFileStorage()
    with pytest.raises(FileNotFoundError):
        ls.get_bytes("nonexistent/file.mp3")

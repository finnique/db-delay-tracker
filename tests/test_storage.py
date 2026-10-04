import pytest

from db_delay_tracker.storage import LocalStorage, S3Storage

KEY = "raw/rchg/station=8000261/date=2026-10-04/140130.xml.gz"


def test_local_put_creates_nested_dirs_and_writes_bytes(tmp_path):
    LocalStorage(tmp_path).put(KEY, b"hello")
    assert (tmp_path / KEY).read_bytes() == b"hello"


def test_local_put_overwrites_same_key(tmp_path):
    storage = LocalStorage(tmp_path)
    storage.put(KEY, b"first")
    storage.put(KEY, b"second")
    assert (tmp_path / KEY).read_bytes() == b"second"


def test_local_put_leaves_no_temp_files(tmp_path):
    LocalStorage(tmp_path).put(KEY, b"hello")
    files = [p.name for p in (tmp_path / KEY).parent.iterdir()]
    assert files == ["140130.xml.gz"]


def test_local_put_rejects_key_escaping_root(tmp_path):
    with pytest.raises(ValueError, match="escapes"):
        LocalStorage(tmp_path / "root").put("../outside.gz", b"x")
    assert not (tmp_path / "outside.gz").exists()


class StubS3Client:
    def __init__(self):
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)


def test_s3_put_calls_put_object_with_bucket_key_and_body():
    client = StubS3Client()
    S3Storage("my-bucket", client=client).put(KEY, b"hello")
    assert client.calls == [
        {
            "Bucket": "my-bucket",
            "Key": KEY,
            "Body": b"hello",
            "ContentType": "application/gzip",
        }
    ]

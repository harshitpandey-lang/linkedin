from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from src.database.repository import PostRepository
from src.database.storage import ImageStorage
from src.social.instagram import InstagramPublisher
from src.social.linkedin import LinkedInPublisher


class StorageBucket:
    def __init__(self):
        self.uploaded = None

    def upload(self, path, file, options):
        self.uploaded = (path, file.read(), options)

    def get_public_url(self, path):
        return f"https://cdn.example/{path}"

    def download(self, path):
        return b"image"


class StorageClient:
    def __init__(self):
        self.bucket = StorageBucket()
        self.storage = self

    def from_(self, _bucket):
        return self.bucket


def test_storage_path_and_upload(tmp_path: Path):
    client = StorageClient()
    image = tmp_path / "source.png"
    image.write_bytes(b"image")
    storage = ImageStorage(client)
    key = storage.storage_path_for("run-1", datetime(2026, 9, 6, tzinfo=timezone.utc))
    assert key == "2026/09/06/run-1.png"
    assert storage.upload(image, key) == "https://cdn.example/2026/09/06/run-1.png"
    assert client.bucket.uploaded[0] == key


def test_instagram_receives_post_specific_public_url(monkeypatch, tmp_path: Path):
    requests = []
    monkeypatch.setattr("src.social.instagram.httpx.post", lambda *args, **kwargs: requests.append((args, kwargs)) or SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"id": "post" if "media_publish" in args[0] else "container"}))
    result = InstagramPublisher("token", "account").publish("caption", tmp_path / "unused.png", "https://cdn.example/generated.png")
    assert result.success
    assert requests[0][1]["params"]["image_url"] == "https://cdn.example/generated.png"


class FakeResponse:
    def __init__(self, data=None, headers=None):
        self._data, self.headers = data or {}, headers or {}

    def raise_for_status(self): pass

    def json(self): return self._data


class LinkedInClient:
    def __init__(self):
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append(("get", args, kwargs))
        return FakeResponse({"sub": "member-1"})
    def post(self, *args, **kwargs):
        self.calls.append(("post", args, kwargs))
        return FakeResponse({"value": {"uploadUrl": "https://upload.example", "image": "urn:li:image:1"}} if "images" in args[0] else {}, {"x-restli-id": "urn:li:share:1"})
    def put(self, *args, **kwargs):
        self.calls.append(("put", args, kwargs))
        return FakeResponse()


def test_linkedin_constructs_image_upload_and_post(tmp_path: Path):
    image = tmp_path / "image.png"
    image.write_bytes(b"png")
    client = LinkedInClient()
    result = LinkedInPublisher(token="token", client=client).publish("caption", image)
    assert result.post_id == "urn:li:share:1"
    posts = [call for call in client.calls if call[0] == "post"]
    assert posts[0][1][0].endswith("rest/images?action=initializeUpload")
    assert posts[1][2]["json"]["content"]["media"]["id"] == "urn:li:image:1"


def test_recent_posts_applies_duplicate_window():
    calls = []
    query = SimpleNamespace(select=lambda *_: query, gte=lambda *args: calls.append(args) or query, limit=lambda *_: query, execute=lambda: SimpleNamespace(data=[]))
    PostRepository(SimpleNamespace(table=lambda _: query)).recent_posts(7)
    assert calls[0][0] == "created_at"

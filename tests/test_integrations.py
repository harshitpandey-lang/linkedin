from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from src.database.repository import PostRepository
from src.database.storage import ImageStorage
from src.config.loader import Settings
from src.database import supabase_client
from src.pipeline.orchestrator import _publish_record
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
    assert storage.download(key) == b"image"


def test_empty_auto_publish_defaults_to_false(monkeypatch):
    monkeypatch.setenv("AUTO_PUBLISH", "")
    settings = Settings(Path("."), {"auto_publish": False}, {}, {}, {}, {}, [])
    assert settings.auto_publish is False


def test_supabase_client_accepts_modern_secret_key(monkeypatch):
    captured = {}

    class FakeOptions:
        headers = {}

    class FakeClient:
        options = FakeOptions()
        supabase_key = ""

    def fake_create_client(url, key):
        captured["url"], captured["key"] = url, key
        return FakeClient()

    monkeypatch.setattr(supabase_client, "create_client", fake_create_client)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sb_secret_test_only")
    client = supabase_client.get_client()
    assert captured == {"url": "https://example.supabase.co", "key": supabase_client._BOOTSTRAP_KEY}
    assert client.supabase_key == "sb_secret_test_only"
    assert client.options.headers["apiKey"] == "sb_secret_test_only"


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
        if "images" in args[0]:
            return FakeResponse({"value": {"uploadUrl": "https://upload.example", "image": "urn:li:image:1"}})
        return FakeResponse({}, {"x-restli-id": "urn:li:share:1"})
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


def test_empty_linkedin_author_type_defaults_to_person(monkeypatch):
    monkeypatch.setenv("LINKEDIN_AUTHOR_TYPE", "")
    publisher = LinkedInPublisher(token="token", client=LinkedInClient())
    assert publisher.author_type == "person"


def test_linkedin_accepts_case_insensitive_restli_id_header(tmp_path: Path):
    image = tmp_path / "image.png"
    image.write_bytes(b"png")
    client = LinkedInClient()
    original_post = client.post

    def post_with_title_case_header(*args, **kwargs):
        response = original_post(*args, **kwargs)
        if args[0].endswith("/rest/posts"):
            response.headers = {"X-RestLi-Id": "urn:li:share:1"}
        return response

    client.post = post_with_title_case_header
    result = LinkedInPublisher(token="token", client=client).publish("caption", image)
    assert result.success
    assert result.post_id == "urn:li:share:1"


def test_linkedin_resolves_organization_and_page_authors():
    assert LinkedInPublisher(token="token", author_type="organization", organization_id="42").resolve_author() == "urn:li:organization:42"
    assert LinkedInPublisher(token="token", author_type="page", organization_id="42").resolve_author() == "urn:li:organization:42"


def test_linkedin_validates_configured_author_urn():
    publisher = LinkedInPublisher(token="token", author_type="person", author_urn="urn:li:organization:42")
    try:
        publisher.resolve_author()
    except ValueError as error:
        assert "urn:li:person:" in str(error)
    else:
        raise AssertionError("invalid person author URN was accepted")


def test_publish_record_does_not_retry_successful_platform():
    class Publisher:
        def __init__(self):
            self.calls = 0

        def publish(self, *_args):
            self.calls += 1
            return SimpleNamespace(success=True, post_id="instagram-1", error="")

    class Repository:
        def __init__(self):
            self.updates = []

        def update(self, post_id, values):
            self.updates.append((post_id, values))

    linkedin = Publisher()
    instagram = Publisher()
    record = {"id": "post-1", "linkedin_status": "PUBLISHED", "linkedin_caption": "already done", "instagram_caption": "new caption"}
    repository = Repository()
    _publish_record(repository, record, {"linkedin": linkedin, "instagram": instagram}, Path("image.png"), "https://cdn.example/image.png")
    assert linkedin.calls == 0
    assert instagram.calls == 1
    assert repository.updates[0][1]["instagram_status"] == "PUBLISHED"


def test_recent_posts_applies_duplicate_window():
    calls = []
    query = SimpleNamespace(select=lambda *_: query, gte=lambda *args: calls.append(args) or query, limit=lambda *_: query, execute=lambda: SimpleNamespace(data=[]))
    PostRepository(SimpleNamespace(table=lambda _: query)).recent_posts(7)
    assert calls[0][0] == "created_at"
    assert calls[0][1].endswith("+00:00")

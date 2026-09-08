from types import SimpleNamespace
from datetime import datetime, timezone
import httpx

from src.news.duplicate_detection import detect_duplicate
from src.news.models import GeneratedContent, NewsStory
from src.news.normalization import normalize_entry
from src.news.verification import verify_story
from src.news.discovery import discover_sources
from src.ai.gemini_provider import DEFAULT_GEMINI_MODEL, GeminiProvider
from src.pipeline.orchestrator import run_pipeline


def test_normalize_rss_entry():
    story = normalize_entry({"title": "New model", "link": "https://example.com/a", "published": "Tue, 01 Jan 2030 12:00:00 GMT"}, {"name": "Example", "url": "https://example.com", "reliability": 0.9})
    assert story.title == "New model"
    assert story.source_name == "Example"
    assert story.reliability == 0.9


def test_duplicate_url_and_title():
    story = NewsStory(title="Open model launch", source_name="A", source_url="https://example.com/a")
    existing = [SimpleNamespace(news_url="https://example.com/a", news_title="Different")]
    assert detect_duplicate(story, existing).duplicate


def test_generated_content_contract():
    content = GeneratedContent(headline="A useful headline", short_explanation="A sufficiently long explanation.", why_it_matters="This matters to builders.", key_takeaway="Build with evidence.", linkedin_caption="A professional caption that is long enough.", instagram_caption="A concise caption that is long enough.", hashtags=["#AI"], image_text="New model", image_prompt="Editorial technology illustration")
    assert content.hashtags == ["#AI"]


def test_story_verification_requires_source_evidence():
    story = NewsStory(title="Verified news", source_name="Example", source_url="https://example.com/news", reliability=0.9)
    assert not verify_story(story, provider=object(), evidence="").verified


def test_source_evidence_skips_unreadable_response(monkeypatch):
    story = NewsStory(title="Unreadable news", source_name="Example", source_url="https://example.com/news")
    monkeypatch.setattr("src.news.verification.httpx.get", lambda *_args, **_kwargs: (_ for _ in ()).throw(UnicodeError("invalid response")))
    from src.news.verification import obtain_evidence

    assert obtain_evidence(story) == ""


def test_discovery_skips_unavailable_source(monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("unavailable")

    monkeypatch.setattr("src.news.discovery.httpx.get", fail)
    assert discover_sources([{"name": "Broken", "url": "https://example.com/rss", "source_type": "rss"}]) == []


def test_gemini_reports_malformed_json(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "not-json"}]}}]}

    monkeypatch.setattr("src.ai.gemini_provider.httpx.post", lambda *_args, **_kwargs: Response())
    try:
        GeminiProvider("test-key")._json("prompt")
    except RuntimeError as error:
        assert "Gemini response could not be validated" in str(error)
    else:
        raise AssertionError("malformed Gemini JSON was accepted")


def test_gemini_uses_current_model_and_api_key_header(monkeypatch):
    requests = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}

    monkeypatch.setattr("src.ai.gemini_provider.httpx.post", lambda *args, **kwargs: requests.append((args, kwargs)) or Response())
    provider = GeminiProvider("test-key")
    assert provider.model == DEFAULT_GEMINI_MODEL == "gemini-2.5-flash"
    assert provider._json("prompt") == {}
    assert requests[0][0][0].endswith("/models/gemini-2.5-flash:generateContent")
    assert requests[0][1]["headers"]["x-goog-api-key"] == "test-key"


def test_gemini_model_resource_names_build_one_models_prefix(monkeypatch):
    requests = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}

    monkeypatch.setattr("src.ai.gemini_provider.httpx.post", lambda *args, **kwargs: requests.append(args[0]) or Response())
    GeminiProvider("test-key", model="models/gemini-2.5-flash")._json("prompt")
    GeminiProvider("test-key", model="gemini-2.5-flash")._json("prompt")
    assert requests == [
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
    ]


def test_main_prefers_gemini_model_environment(monkeypatch):
    captured = {}
    settings = SimpleNamespace(auto_publish=False, app={"enabled_platforms": [], "retry_attempts": 1}, ai={"model": "yaml-model"}, storage={})
    monkeypatch.setattr("src.main.load_settings", lambda: settings)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "env-model")

    def provider(*args, **kwargs):
        captured["model"] = args[1]
        return object()

    monkeypatch.setattr("src.main.GeminiProvider", provider)
    monkeypatch.setattr("src.main.get_client", lambda: object())
    monkeypatch.setattr("src.main.ImageStorage", lambda *_args: object())
    monkeypatch.setattr("src.main.PostRepository", lambda *_args: object())
    monkeypatch.setattr("src.main.run_pipeline", lambda *_args: "post-1")
    from src.main import main
    main()
    assert captured["model"] == "env-model"


def test_gemini_discovers_generate_content_models(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "models/gemini-2.5-flash", "displayName": "Gemini 2.5 Flash", "supportedGenerationMethods": ["generateContent"]}, {"name": "gemini-2.5-flash-preview-tts", "displayName": "TTS", "supportedGenerationMethods": ["generateContent"]}, {"name": "models/embedding", "displayName": "Embedding", "supportedGenerationMethods": ["embedContent"]}]}

    monkeypatch.setattr("src.ai.gemini_provider.httpx.get", lambda *args, **kwargs: Response())
    assert GeminiProvider("test-key").available_models() == ["models/gemini-2.5-flash", "models/gemini-2.5-flash-preview-tts"]


def test_gemini_fallback_selects_stable_text_model():
    models = [
        {"name": "models/gemini-2.5-flash-preview-tts", "displayName": "TTS", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-2.5-flash", "displayName": "Gemini 2.5 Flash", "supportedGenerationMethods": ["generateContent"]},
    ]
    assert GeminiProvider._select_fallback(models) == "models/gemini-2.5-flash"


def test_gemini_404_falls_back_to_untried_latest_flash(monkeypatch):
    requests = []

    class Response:
        def __init__(self, status=200):
            self.status = status

        def raise_for_status(self):
            if self.status == 404:
                raise httpx.HTTPStatusError("not found", request=httpx.Request("POST", "https://example.com"), response=httpx.Response(404))

        def json(self):
            if self.status == 404:
                return {}
            return {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}

    def post(url, **_kwargs):
        requests.append(url)
        return Response(404 if len(requests) == 1 else 200)

    monkeypatch.setattr("src.ai.gemini_provider.httpx.post", post)
    monkeypatch.setattr("src.ai.gemini_provider.GeminiProvider.available_model_details", lambda _provider: [{"name": "models/gemini-2.5-flash", "displayName": "Gemini 2.5 Flash", "supportedGenerationMethods": ["generateContent"]}, {"name": "models/gemini-flash-latest", "displayName": "Gemini Flash Latest", "supportedGenerationMethods": ["generateContent"]}])

    assert GeminiProvider("test-key", model="models/gemini-2.5-flash")._json("prompt") == {}
    assert requests == [
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent",
    ]


def test_gemini_fallback_never_selects_failed_resource():
    models = [{"name": "models/gemini-2.5-flash", "displayName": "Gemini 2.5 Flash", "supportedGenerationMethods": ["generateContent"]}, {"name": "models/gemini-flash-latest", "displayName": "Gemini Flash Latest", "supportedGenerationMethods": ["generateContent"]}]
    assert GeminiProvider._select_fallback(models, {"models/gemini-2.5-flash"}) == "models/gemini-flash-latest"


def test_gemini_multiple_404s_advance_through_distinct_resources(monkeypatch):
    requests = []

    class Response:
        def __init__(self, status):
            self.status = status

        def raise_for_status(self):
            if self.status == 404:
                raise httpx.HTTPStatusError("not found", request=httpx.Request("POST", "https://example.com"), response=httpx.Response(404))

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}

    def post(url, **_kwargs):
        requests.append(url)
        return Response(404 if len(requests) < 3 else 200)

    details = [{"name": name, "displayName": name, "supportedGenerationMethods": ["generateContent"]} for name in ("models/gemini-2.5-flash", "models/gemini-flash-latest", "models/gemini-2.5-flash-lite")]
    monkeypatch.setattr("src.ai.gemini_provider.httpx.post", post)
    monkeypatch.setattr("src.ai.gemini_provider.GeminiProvider.available_model_details", lambda _provider: details)

    assert GeminiProvider("test-key")._json("prompt") == {}
    assert [url.split("/v1beta/")[1].split(":")[0] for url in requests] == ["models/gemini-2.5-flash", "models/gemini-flash-latest", "models/gemini-2.5-flash-lite"]


def test_gemini_fallback_excludes_unsuitable_resources():
    models = [{"name": f"models/{name}", "displayName": name, "supportedGenerationMethods": ["generateContent"]} for name in ("gemini-preview-tts", "gemini-image", "gemini-audio", "gemini-live", "gemini-embedding", "gemini-flash-latest")]
    assert GeminiProvider._select_fallback(models) == "models/gemini-flash-latest"


def test_gemini_fallback_exhaustion_reports_attempts_and_compatible_models(monkeypatch):
    class Response:
        def raise_for_status(self):
            raise httpx.HTTPStatusError("not found", request=httpx.Request("POST", "https://example.com"), response=httpx.Response(404))

    monkeypatch.setattr("src.ai.gemini_provider.httpx.post", lambda *_args, **_kwargs: Response())
    monkeypatch.setattr("src.ai.gemini_provider.GeminiProvider.available_model_details", lambda _provider: [{"name": "models/gemini-2.5-flash", "displayName": "Gemini 2.5 Flash", "supportedGenerationMethods": ["generateContent"]}, {"name": "models/gemini-flash-latest", "displayName": "Gemini Flash Latest", "supportedGenerationMethods": ["generateContent"]}])
    try:
        GeminiProvider("test-key", model="configured-model")._json("prompt")
    except RuntimeError as error:
        message = str(error)
        assert "models/configured-model" in message
        assert "attempted resources:" in message
        assert "models/gemini-2.5-flash" in message
        assert "models/gemini-flash-latest" in message
        assert "compatible resources discovered:" in message
    else:
        raise AssertionError("fallback exhaustion was not reported")


def test_gemini_404_reports_model_availability(monkeypatch):
    class NotFound:
        status_code = 404

    class Response:
        def raise_for_status(self):
            raise httpx.HTTPStatusError("not found", request=httpx.Request("POST", "https://example.com"), response=NotFound())

    monkeypatch.setattr("src.ai.gemini_provider.httpx.post", lambda *args, **kwargs: Response())
    monkeypatch.setattr("src.ai.gemini_provider.GeminiProvider.available_model_details", lambda _provider: [{"name": "models/gemini-2.5-flash", "displayName": "Gemini 2.5 Flash", "supportedGenerationMethods": ["generateContent"]}])
    try:
        GeminiProvider("test-key", model="retired-model")._json("prompt")
    except RuntimeError as error:
        assert "models/retired-model" in str(error)
        assert "models/gemini-2.5-flash" in str(error)
    else:
        raise AssertionError("404 model failure was not reported")


def test_gemini_retries_rate_limit(monkeypatch):
    attempts = []

    class Response:
        def raise_for_status(self):
            if len(attempts) == 1:
                raise httpx.HTTPStatusError("rate limited", request=httpx.Request("POST", "https://example.com"), response=httpx.Response(429))

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}

    def post(*_args, **_kwargs):
        attempts.append(True)
        return Response()

    monkeypatch.setattr("src.ai.gemini_provider.httpx.post", post)
    monkeypatch.setattr("src.ai.gemini_provider.time.sleep", lambda _seconds: None)
    assert GeminiProvider("test-key", retries=2)._json("prompt") == {}
    assert len(attempts) == 2


def test_pipeline_stores_verified_pending_record(tmp_path, monkeypatch):
    story = NewsStory(title="A verified AI story", summary="Source summary", source_name="Example", source_url="https://example.com/story", reliability=0.9, published_at=datetime.now(timezone.utc))
    evaluation = SimpleNamespace(total=90, credibility=90, usefulness=80, novelty=85)
    content = GeneratedContent(headline="Verified headline", short_explanation="A factual explanation.", why_it_matters="This matters to builders.", key_takeaway="Check the source.", linkedin_caption="A factual LinkedIn caption with evidence.", instagram_caption="A factual Instagram caption with evidence.", hashtags=["#AI"], image_text="Verified story", image_prompt="Editorial technology graphic")

    class Provider:
        def evaluate(self, _story):
            return evaluation

        def generate_content(self, _story, evidence):
            assert evidence == "source evidence"
            return content

        def verify_evidence(self, _story, evidence, claims=""):
            assert evidence == "source evidence"
            return SimpleNamespace(verified=True, reason="Supported by source")

    class Repository:
        def __init__(self):
            self.record = None

        def recent_posts(self, _days):
            return []

        def create(self, values):
            self.record = {"id": "post-1", **values}
            return self.record

    class Storage:
        def storage_path_for(self, run_id):
            return f"{run_id}.png"

        def upload(self, _path, storage_path):
            return f"https://cdn.example/{storage_path}"

    monkeypatch.setattr("src.pipeline.orchestrator.obtain_evidence", lambda *_args: "source evidence")
    monkeypatch.setattr("src.pipeline.orchestrator.verify_story", lambda *_args: SimpleNamespace(verified=True, reason="verified"))
    monkeypatch.setattr("src.pipeline.orchestrator.detect_duplicate", lambda *_args: SimpleNamespace(duplicate=False))
    def create_image(_content, path, *_args):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png")
        return path

    monkeypatch.setattr("src.pipeline.orchestrator.generate_image", create_image)
    monkeypatch.setattr("src.pipeline.orchestrator.validate_image", lambda *_args: (True, ""))
    settings = SimpleNamespace(root=tmp_path, auto_publish=False, news_sources=[], app={"max_article_age_hours": 48, "max_candidates": 1, "duplicate_window_days": 30, "request_timeout_seconds": 1}, image={}, brand={}, storage={})
    repository = Repository()
    post_id = run_pipeline(settings, Provider(), repository, lambda *_args: [story], storage=Storage())
    assert post_id == "post-1"
    assert repository.record["status"] == "PENDING_APPROVAL"
    assert repository.record["approval_status"] == "PENDING"
    assert repository.record["evidence_verified"] is True
    assert repository.record["image_storage_path"].endswith(".png")

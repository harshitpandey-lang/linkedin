from __future__ import annotations

import uuid
import tempfile
from datetime import datetime, timezone

from src.ai.base import AIProvider
from src.database.repository import PostRepository
from src.database.storage import ImageStorage
from src.image.generator import generate_image
from src.image.validator import validate_image
from src.news.duplicate_detection import detect_duplicate
from src.news.filtering import filter_recent
from src.news.models import NewsStory
from src.news.ranking import rank_evaluations
from src.news.verification import obtain_evidence, verify_story
from src.social.base import Publisher


def _publish_record(repository, record, publishers, image_path, image_public_url):
    results = {}
    for name, publisher in publishers.items():
        if record.get(f"{name}_status") != "PUBLISHED":
            results[name] = publisher.publish(record[f"{name}_caption"], image_path, image_public_url)
    if not results:
        return
    updates = {"published_at": datetime.now(timezone.utc).isoformat()}
    for name, result in results.items():
        updates.update({f"{name}_status": "PUBLISHED" if result.success else "FAILED", f"{name}_post_id": result.post_id, f"{name}_error": result.error})
    updates["status"] = "PUBLISHED" if all(result.success for result in results.values()) else "PARTIALLY_PUBLISHED"
    repository.update(record["id"], updates)


def run_pipeline(settings, provider: AIProvider, repository: PostRepository, discover, publishers: dict[str, Publisher] | None = None, storage: ImageStorage | None = None) -> str:
    run_id = str(uuid.uuid4())
    stories = filter_recent(discover(settings.news_sources, settings.app.get("request_timeout_seconds", 20)), settings.app.get("max_article_age_hours", 48))
    if settings.auto_publish and storage:
        active = {name: value for name, value in (publishers or {}).items() if name in settings.app.get("enabled_platforms", [])}
        for story in stories:
            existing_record = repository.find_by_news_url(str(story.source_url))
            if existing_record and existing_record.get("status") != "PUBLISHED" and existing_record.get("image_storage_path"):
                with tempfile.NamedTemporaryFile(suffix=".png") as image:
                    image.write(storage.download(existing_record["image_storage_path"]))
                    image.flush()
                    _publish_record(repository, existing_record, active, image.name, existing_record.get("image_public_url", ""))
                return existing_record["id"]
    evaluated = rank_evaluations([(story, provider.evaluate(story)) for story in stories[: settings.app.get("max_candidates", 20)]])
    existing = repository.recent_posts(settings.app.get("duplicate_window_days", 30))
    selected: tuple[NewsStory, object] | None = None
    for story, evaluation in evaluated:
        evidence = obtain_evidence(story, settings.app.get("request_timeout_seconds", 20))
        if verify_story(story, provider, evidence).verified and not detect_duplicate(story, existing).duplicate:
            selected = (story, evaluation)
            break
    if selected is None:
        raise RuntimeError("No verified, non-duplicate story available")
    story, evaluation = selected
    content = provider.generate_content(story)
    claims = "\n".join([content.headline, content.short_explanation, content.why_it_matters, content.key_takeaway, content.linkedin_caption, content.instagram_caption])
    if not provider.verify_evidence(story, evidence, claims).verified:
        raise RuntimeError("Generated content contains unsupported claims")
    image_path = generate_image(content, settings.root / "artifacts" / f"{run_id}.png", settings.image, settings.brand)
    valid, reason = validate_image(image_path, settings.image.get("width", 1080), settings.image.get("height", 1080))
    if not valid:
        raise RuntimeError(reason)
    if storage is None:
        raise RuntimeError("ImageStorage is required; local artifacts are not permanent media")
    storage_path = storage.storage_path_for(run_id)
    public_url = storage.upload(image_path, storage_path)
    record = repository.create({"run_id": run_id, "news_title": story.title, "news_summary": story.summary, "news_url": str(story.source_url), "news_source": story.source_name, "news_published_at": story.published_at.isoformat() if story.published_at else None, "ai_score": evaluation.total, "credibility_score": evaluation.credibility, "usefulness_score": evaluation.usefulness, "novelty_score": evaluation.novelty, "headline": content.headline, "short_explanation": content.short_explanation, "why_it_matters": content.why_it_matters, "key_takeaway": content.key_takeaway, "linkedin_caption": content.linkedin_caption, "instagram_caption": content.instagram_caption, "hashtags": content.hashtags, "status": "PENDING_APPROVAL" if not settings.auto_publish else "STORED", "approval_status": "APPROVED" if settings.auto_publish else "PENDING", "image_storage_path": storage_path, "image_public_url": public_url, "created_at": datetime.now(timezone.utc).isoformat()})
    if not settings.auto_publish:
        return record["id"]
    active = {name: value for name, value in (publishers or {}).items() if name in settings.app.get("enabled_platforms", [])}
    _publish_record(repository, record, active, image_path, public_url)
    return record["id"]

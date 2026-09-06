from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.ai.base import AIProvider
from src.database.repository import PostRepository
from src.image.generator import generate_image
from src.image.validator import validate_image
from src.news.duplicate_detection import detect_duplicate
from src.news.filtering import filter_recent
from src.news.models import NewsStory
from src.news.ranking import rank_evaluations
from src.news.verification import verify_story
from src.social.base import Publisher


def run_pipeline(settings, provider: AIProvider, repository: PostRepository, discover, publishers: dict[str, Publisher] | None = None) -> str:
    run_id = str(uuid.uuid4())
    stories = filter_recent(discover(settings.news_sources, settings.app.get("request_timeout_seconds", 20)), settings.app.get("max_article_age_hours", 48))
    evaluated = rank_evaluations([(story, provider.evaluate(story)) for story in stories[: settings.app.get("max_candidates", 20)]])
    existing = repository.recent_posts(settings.app.get("duplicate_window_days", 30))
    selected: tuple[NewsStory, object] | None = None
    for story, evaluation in evaluated:
        if verify_story(story).verified and not detect_duplicate(story, existing).duplicate:
            selected = (story, evaluation)
            break
    if selected is None:
        raise RuntimeError("No verified, non-duplicate story available")
    story, evaluation = selected
    content = provider.generate_content(story)
    image_path = generate_image(content, settings.root / "artifacts" / f"{run_id}.png", settings.image, settings.brand)
    valid, reason = validate_image(image_path, settings.image.get("width", 1080), settings.image.get("height", 1080))
    if not valid:
        raise RuntimeError(reason)
    record = repository.create({"run_id": run_id, "news_title": story.title, "news_summary": story.summary, "news_url": str(story.source_url), "news_source": story.source_name, "news_published_at": story.published_at.isoformat() if story.published_at else None, "ai_score": evaluation.total, "credibility_score": evaluation.credibility, "usefulness_score": evaluation.usefulness, "novelty_score": evaluation.novelty, "headline": content.headline, "short_explanation": content.short_explanation, "why_it_matters": content.why_it_matters, "key_takeaway": content.key_takeaway, "linkedin_caption": content.linkedin_caption, "instagram_caption": content.instagram_caption, "hashtags": content.hashtags, "status": "PENDING_APPROVAL" if not settings.auto_publish else "STORED", "approval_status": "APPROVED" if settings.auto_publish else "PENDING", "image_storage_path": str(image_path), "created_at": datetime.now(timezone.utc).isoformat()})
    if not settings.auto_publish:
        return record["id"]
    results = {}
    for name in settings.app.get("enabled_platforms", []):
        publisher = (publishers or {}).get(name)
        if publisher:
            results[name] = publisher.publish(getattr(content, f"{name}_caption"), image_path)
    updates = {"status": "PUBLISHED" if all(result.success for result in results.values()) else "PARTIALLY_PUBLISHED", "published_at": datetime.now(timezone.utc).isoformat()}
    for name, result in results.items():
        updates[f"{name}_status"] = "PUBLISHED" if result.success else "FAILED"
        updates[f"{name}_post_id"] = result.post_id
        updates[f"{name}_error"] = result.error
    repository.update(record["id"], updates)
    return record["id"]

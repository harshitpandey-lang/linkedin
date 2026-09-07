from __future__ import annotations

from pathlib import Path
import tempfile
import logging

from src.database.repository import PostRepository
from src.database.storage import ImageStorage
from src.database.supabase_client import get_client
from src.social.base import PublishResult
from src.social.instagram import InstagramPublisher
from src.social.linkedin import LinkedInPublisher

logger = logging.getLogger(__name__)


def publish_approved_posts(repository, storage, publishers) -> None:
    for post in repository.approved_unpublished():
        if not post.get("image_storage_path"):
            repository.update(post["id"], {"status": "FAILED", "error_message": "Stored image path is required"})
            continue
        try:
            image_bytes = storage.download(post["image_storage_path"])
        except Exception as exc:
            logger.error("Could not download image for post %s: %s", post["id"], exc)
            repository.update(post["id"], {"status": "FAILED", "error_message": f"Image download failed: {exc}"})
            continue
        local_image_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as local_image:
                local_image.write(image_bytes)
                local_image_path = Path(local_image.name)
            results = []
            for name, publisher in publishers.items():
                if post.get(f"{name}_status") == "PUBLISHED":
                    continue
                try:
                    result = publisher.publish(post[f"{name}_caption"], local_image_path, post.get("image_public_url", ""))
                except Exception as exc:
                    logger.error("Publisher %s failed for post %s: %s", name, post["id"], exc)
                    result = PublishResult(False, error=str(exc))
                results.append(result)
                repository.update(post["id"], {f"{name}_status": "PUBLISHED" if result.success else "FAILED", f"{name}_post_id": result.post_id, f"{name}_error": result.error})
            if results:
                repository.update(post["id"], {"status": "PUBLISHED" if all(result.success for result in results) else "PARTIALLY_PUBLISHED"})
        finally:
            if local_image_path:
                local_image_path.unlink(missing_ok=True)


def main() -> None:
    client = get_client()
    repository = PostRepository(client)
    storage = ImageStorage(client)
    publishers = {"linkedin": LinkedInPublisher(), "instagram": InstagramPublisher()}
    publish_approved_posts(repository, storage, publishers)


if __name__ == "__main__":
    main()

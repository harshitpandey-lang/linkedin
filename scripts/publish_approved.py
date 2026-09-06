from __future__ import annotations

from pathlib import Path

from src.database.repository import PostRepository
from src.database.supabase_client import get_client
from src.social.instagram import InstagramPublisher
from src.social.linkedin import LinkedInPublisher


def main() -> None:
    repository = PostRepository(get_client())
    publishers = {"linkedin": LinkedInPublisher(), "instagram": InstagramPublisher()}
    for post in repository.approved_unpublished():
        for name, publisher in publishers.items():
            if post.get(f"{name}_status") == "PUBLISHED":
                continue
            result = publisher.publish(post[f"{name}_caption"], Path(post["image_storage_path"]))
            repository.update(post["id"], {f"{name}_status": "PUBLISHED" if result.success else "FAILED", f"{name}_post_id": result.post_id, f"{name}_error": result.error})


if __name__ == "__main__":
    main()

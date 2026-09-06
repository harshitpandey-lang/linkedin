from __future__ import annotations

from pathlib import Path
import tempfile

from src.database.repository import PostRepository
from src.database.storage import ImageStorage
from src.database.supabase_client import get_client
from src.social.instagram import InstagramPublisher
from src.social.linkedin import LinkedInPublisher


def main() -> None:
    client = get_client()
    repository = PostRepository(client)
    storage = ImageStorage(client)
    publishers = {"linkedin": LinkedInPublisher(), "instagram": InstagramPublisher()}
    for post in repository.approved_unpublished():
        if not post.get("image_storage_path") or not post.get("image_public_url"):
            repository.update(post["id"], {"status": "FAILED", "error_message": "Stored image path and public URL are required"})
            continue
        with tempfile.NamedTemporaryFile(suffix=".png") as local_image:
            local_image.write(storage.download(post["image_storage_path"]))
            local_image.flush()
            results = []
            for name, publisher in publishers.items():
                if post.get(f"{name}_status") == "PUBLISHED":
                    continue
                result = publisher.publish(post[f"{name}_caption"], Path(local_image.name), post["image_public_url"])
                results.append(result)
                repository.update(post["id"], {f"{name}_status": "PUBLISHED" if result.success else "FAILED", f"{name}_post_id": result.post_id, f"{name}_error": result.error})
            if results:
                repository.update(post["id"], {"status": "PUBLISHED" if all(result.success for result in results) else "PARTIALLY_PUBLISHED"})


if __name__ == "__main__":
    main()

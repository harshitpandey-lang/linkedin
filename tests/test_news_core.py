from types import SimpleNamespace

from src.news.duplicate_detection import detect_duplicate
from src.news.models import GeneratedContent, NewsStory
from src.news.normalization import normalize_entry
from src.news.verification import verify_story


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

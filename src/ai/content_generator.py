from .base import AIProvider
from src.news.models import GeneratedContent, NewsStory


def generate_content(provider: AIProvider, story: NewsStory) -> GeneratedContent:
    return provider.generate_content(story)

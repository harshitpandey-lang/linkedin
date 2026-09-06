from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, Field, HttpUrl


class NewsStory(BaseModel):
    title: str = Field(min_length=3)
    summary: str = ""
    source_name: str
    source_url: HttpUrl
    published_at: datetime | None = None
    author: str = ""
    category: str = "AI"
    raw_content: str = ""
    reliability: float = Field(default=0.5, ge=0, le=1)

    @property
    def age_hours(self) -> float | None:
        if self.published_at is None:
            return None
        published = self.published_at if self.published_at.tzinfo else self.published_at.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - published).total_seconds() / 3600)


class Evaluation(BaseModel):
    significance: int = Field(ge=0, le=100)
    usefulness: int = Field(ge=0, le=100)
    credibility: int = Field(ge=0, le=100)
    novelty: int = Field(ge=0, le=100)
    educational_value: int = Field(ge=0, le=100)
    audience_relevance: int = Field(ge=0, le=100)
    visual_potential: int = Field(ge=0, le=100)
    reasoning: str = ""

    @property
    def total(self) -> int:
        fields = ("significance", "usefulness", "credibility", "novelty", "educational_value", "audience_relevance", "visual_potential")
        return round(sum(getattr(self, field) for field in fields) / len(fields))


class GeneratedContent(BaseModel):
    headline: str = Field(min_length=3)
    short_explanation: str = Field(min_length=10)
    why_it_matters: str = Field(min_length=10)
    key_takeaway: str = Field(min_length=5)
    linkedin_caption: str = Field(min_length=20)
    instagram_caption: str = Field(min_length=20)
    hashtags: list[str] = Field(min_length=1)
    image_text: str = Field(min_length=3)
    image_prompt: str = Field(min_length=10)

from __future__ import annotations

from .models import Evaluation, NewsStory


def rank_evaluations(items: list[tuple[NewsStory, Evaluation]]) -> list[tuple[NewsStory, Evaluation]]:
    return sorted(items, key=lambda item: (item[1].total, item[0].reliability), reverse=True)

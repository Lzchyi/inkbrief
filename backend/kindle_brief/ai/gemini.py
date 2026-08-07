from __future__ import annotations

import json
from typing import Any

import httpx

from kindle_brief.models import BriefStory
from kindle_brief.news.dedupe import StoryCluster

from .base import AIProvider, AIProviderError
from .prompts import RANK_SYSTEM, SUMMARY_SYSTEM, source_payload
from .schemas import BRIEF_SCHEMA, RANKING_SCHEMA, validate_brief_stories, validate_ranked_ids


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, *, api_key: str, model: str, client: httpx.Client | None = None) -> None:
        if not api_key:
            raise ValueError("Gemini API key is missing")
        self.api_key = api_key
        self.model = model
        self.client = client or httpx.Client(timeout=45)

    def _json_call(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseFormat": {
                    "text": {
                        "mimeType": "application/json",
                        "schema": schema,
                    }
                },
            },
        }
        try:
            response = self.client.post(
                url,
                headers={"x-goog-api-key": self.api_key},
                json=body,
            )
            response.raise_for_status()
            content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(content)
            if not isinstance(result, dict):
                raise TypeError("model JSON response must be an object")
            return result
        except Exception as error:
            raise AIProviderError(f"Gemini request failed: {error}") from error

    def rank_articles(
        self,
        clusters: tuple[StoryCluster, ...],
        *,
        max_stories: int,
    ) -> tuple[StoryCluster, ...]:
        payload = self._json_call(
            system=RANK_SYSTEM,
            prompt=(
                f"Select and order at most {max_stories} stories. "
                f"Records:\n{source_payload(clusters)}"
            ),
            schema=RANKING_SCHEMA,
        )
        try:
            return validate_ranked_ids(payload, clusters, max_stories=max_stories)
        except ValueError as error:
            raise AIProviderError(str(error)) from error

    def summarize_articles(
        self,
        clusters: tuple[StoryCluster, ...],
    ) -> tuple[BriefStory, ...]:
        payload = self._json_call(
            system=SUMMARY_SYSTEM,
            prompt=(
                "Summarize every selected story once, preserving this order. "
                f"Records:\n{source_payload(clusters)}"
            ),
            schema=BRIEF_SCHEMA,
        )
        allowed = [article.article_id for cluster in clusters for article in cluster.articles]
        try:
            return validate_brief_stories(payload, allowed, expected_max=len(clusters))
        except ValueError as error:
            raise AIProviderError(str(error)) from error

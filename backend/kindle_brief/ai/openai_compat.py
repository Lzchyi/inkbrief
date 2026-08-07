from __future__ import annotations

import json
from typing import Any

import httpx

from kindle_brief.models import BriefStory
from kindle_brief.news.dedupe import StoryCluster

from .base import AIProvider, AIProviderError
from .prompts import RANK_SYSTEM, SUMMARY_SYSTEM, source_payload
from .schemas import BRIEF_SCHEMA, RANKING_SCHEMA, validate_brief_stories, validate_ranked_ids


class OpenAICompatibleProvider(AIProvider):
    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        model: str,
        base_url: str,
        client: httpx.Client | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError(f"{name} API key is missing")
        self.name = name
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=45)
        self.extra_headers = extra_headers or {}

    def _json_call(
        self, *, system: str, prompt: str, schema: dict[str, Any], name: str
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": name, "strict": True, "schema": schema},
            },
        }
        try:
            response = self.client.post(
                f"{self.base_url}/chat/completions", headers=headers, json=body
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            result = json.loads(content)
            if not isinstance(result, dict):
                raise TypeError("model JSON response must be an object")
            return result
        except Exception as error:
            raise AIProviderError(f"{self.name} request failed: {error}") from error

    def rank_articles(
        self,
        clusters: tuple[StoryCluster, ...],
        *,
        max_stories: int,
    ) -> tuple[StoryCluster, ...]:
        prompt = (
            f"Select and order at most {max_stories} stories. Records:\n{source_payload(clusters)}"
        )
        payload = self._json_call(
            system=RANK_SYSTEM, prompt=prompt, schema=RANKING_SCHEMA, name="kindle_brief_ranking"
        )
        try:
            return validate_ranked_ids(payload, clusters, max_stories=max_stories)
        except ValueError as error:
            raise AIProviderError(str(error)) from error

    def summarize_articles(
        self,
        clusters: tuple[StoryCluster, ...],
    ) -> tuple[BriefStory, ...]:
        prompt = (
            "Summarize every selected story once, preserving this order. "
            f"Records:\n{source_payload(clusters)}"
        )
        payload = self._json_call(
            system=SUMMARY_SYSTEM, prompt=prompt, schema=BRIEF_SCHEMA, name="kindle_brief_stories"
        )
        allowed = [article.article_id for cluster in clusters for article in cluster.articles]
        try:
            return validate_brief_stories(payload, allowed, expected_max=len(clusters))
        except ValueError as error:
            raise AIProviderError(str(error)) from error

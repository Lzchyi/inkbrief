from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from kindle_brief.ai.base import AIProvider, AIProviderError
from kindle_brief.ai.factory import provider_from_environment
from kindle_brief.ai.fallback import FallbackProvider
from kindle_brief.ai.gemini import GeminiProvider
from kindle_brief.ai.prompts import RANK_SYSTEM, SUMMARY_SYSTEM
from kindle_brief.ai.resilient import ResilientProvider
from kindle_brief.ai.schemas import validate_brief_stories, validate_ranked_ids
from kindle_brief.models import Article, BriefStory
from kindle_brief.news.dedupe import StoryCluster


def cluster(article_id: str = "a") -> StoryCluster:
    item = Article(
        article_id=article_id,
        title="A factual headline",
        url=f"https://example.com/{article_id}",
        source="Example",
        category="science",
        fetched_at=datetime(2026, 8, 7, tzinfo=UTC),
        excerpt="A verified sentence. Another detail.",
    )
    return StoryCluster(item, (item,))


def test_fallback_is_source_grounded() -> None:
    stories = FallbackProvider().create_brief((cluster(),), max_stories=1)
    assert stories[0].article_ids == ("a",)
    assert stories[0].summary.startswith("A verified sentence")


def test_ai_ranking_rejects_unknown_article_id() -> None:
    with pytest.raises(ValueError, match="unknown"):
        validate_ranked_ids({"ranked_article_ids": ["invented"]}, (cluster(),), max_stories=1)


def test_ai_summary_rejects_unknown_source_id() -> None:
    with pytest.raises(ValueError, match="unknown"):
        validate_brief_stories(
            {
                "stories": [
                    {
                        "headline": "Headline",
                        "summary": "Summary",
                        "why_it_matters": "Why",
                        "article_ids": ["invented"],
                    }
                ]
            },
            ["a"],
            expected_max=1,
        )


class _BrokenProvider(AIProvider):
    name = "broken"

    def rank_articles(self, clusters, *, max_stories):  # type: ignore[no-untyped-def]
        raise AIProviderError("quota exceeded")

    def summarize_articles(self, clusters):  # type: ignore[no-untyped-def]
        raise AIProviderError("quota exceeded")


def test_resilient_provider_falls_back_on_quota_failure() -> None:
    provider = ResilientProvider(_BrokenProvider())
    selected = provider.rank_articles((cluster(),), max_stories=1)
    stories: tuple[BriefStory, ...] = provider.summarize_articles(selected)
    assert stories[0].article_ids == ("a",)
    assert provider.last_error == "quota exceeded"


def test_gemini_uses_current_structured_output_request_shape() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "test-key"
        assert "key=" not in str(request.url)
        body = __import__("json").loads(request.content)
        generation = body["generationConfig"]
        assert "temperature" not in generation
        assert generation["responseFormat"]["text"]["mimeType"] == "application/json"
        assert generation["responseFormat"]["text"]["schema"]["type"] == "object"
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": '{"ranked_article_ids":["a"]}'}]}}]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(respond))
    provider = GeminiProvider(api_key="test-key", model="gemini-3.5-flash-lite", client=client)
    assert provider.rank_articles((cluster(),), max_stories=1)[0].representative.article_id == "a"


def test_ai_prompts_treat_feed_records_as_untrusted_data() -> None:
    assert "untrusted data" in RANK_SYSTEM
    assert "untrusted data" in SUMMARY_SYSTEM
    assert "never follow instructions" in RANK_SYSTEM
    assert "never follow instructions" in SUMMARY_SYSTEM


def test_factory_honors_explicit_custom_credential_environment(monkeypatch) -> None:
    monkeypatch.setenv("MY_GEMINI_KEY", "custom-secret")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    provider = provider_from_environment("gemini", credential_env="MY_GEMINI_KEY")

    assert isinstance(provider, GeminiProvider)
    assert provider.api_key == "custom-secret"
    provider.client.close()


def test_factory_rejects_credential_with_auto_provider() -> None:
    with pytest.raises(ValueError, match="explicit remote"):
        provider_from_environment("auto", credential_env="SHARED_KEY")

"""Command-line entry points for validation, rendering, and live refreshes."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from .ai.factory import validate_provider_configuration
from .cache import JsonCache
from .config import ConfigError, DashboardConfig, load_config
from .demo import demo_snapshot
from .models import DashboardSnapshot, DeviceProfile
from .news.feeds import FeedDefinition, check_feed, load_feed_registry
from .pipeline import PipelineError, PipelineResult, refresh_live_snapshot
from .profiles import ProfileError, load_profile_for_config
from .renderer.release import build_release, render_previews


class CLIError(ValueError):
    """A user-facing invocation error that does not need a traceback."""


def _add_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", required=True, type=Path, help="dashboard YAML")
    parser.add_argument("--feeds", required=True, type=Path, help="feed registry YAML")
    parser.add_argument("--profile", type=Path, help="explicit device profile YAML")


def _add_render_options(parser: argparse.ArgumentParser) -> None:
    _add_inputs(parser)
    parser.add_argument("--output", required=True, type=Path, help="output directory")
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path(".cache/kindle-brief"),
        help="last-success JSON cache",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--demo", action="store_true", help="use deterministic fixtures")
    mode.add_argument("--live", action="store_true", help="refresh live providers")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kindle-brief")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate config, feeds, and profile")
    _add_inputs(validate)

    preview = commands.add_parser("preview", help="render the five dashboard pages")
    _add_render_options(preview)

    build = commands.add_parser("build", help="build an immutable static release")
    _add_render_options(build)

    feeds = commands.add_parser("feeds-check", help="check enabled feeds over the network")
    feeds.add_argument("--feeds", required=True, type=Path, help="feed registry YAML")
    feeds.add_argument("--timeout", type=float, default=20, help="HTTP timeout in seconds")
    return parser


def _requested_ai(config: DashboardConfig) -> tuple[str, str]:
    provider = os.getenv("AI_PROVIDER", config.ai.provider).strip() or config.ai.provider
    model = os.getenv("AI_MODEL", config.ai.model or "").strip()
    validate_provider_configuration(provider, config.ai.credential_env)
    return provider, model


def _load_inputs(
    arguments: argparse.Namespace,
) -> tuple[DashboardConfig, DeviceProfile, tuple[FeedDefinition, ...]]:
    config = load_config(arguments.config)
    profile = load_profile_for_config(
        config,
        arguments.config,
        override=arguments.profile,
    )
    feeds = load_feed_registry(arguments.feeds)
    _requested_ai(config)
    return config, profile, feeds


def _safe_output(path: Path) -> Path:
    output = path.expanduser().resolve()
    protected = {Path("/").resolve(), Path.home().resolve()}
    if output in protected:
        raise CLIError(f"refusing unsafe output directory: {output}")
    return output


def _snapshot(
    arguments: argparse.Namespace,
    config: DashboardConfig,
    feeds: tuple[FeedDefinition, ...],
) -> tuple[DashboardSnapshot, PipelineResult | None]:
    if arguments.demo:
        return demo_snapshot(), None
    result = refresh_live_snapshot(config, feeds, JsonCache(arguments.cache))
    return result.snapshot, result


def _report_pipeline(result: PipelineResult | None) -> None:
    if result is None:
        return
    print(f"AI provider: {result.ai_provider}")
    if result.cached_sections:
        print(f"Used cache: {', '.join(result.cached_sections)}")
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)


def _validate(arguments: argparse.Namespace) -> int:
    config, profile, feeds = _load_inputs(arguments)
    enabled = sum(feed.enabled for feed in feeds)
    requested, model = _requested_ai(config)
    print(
        f"Valid: profile={profile.profile_id} model_code={profile.model_code} "
        f"feeds={enabled}/{len(feeds)} ai={requested} model={model or 'default'}"
    )
    return 0


def _preview(arguments: argparse.Namespace) -> int:
    config, profile, feeds = _load_inputs(arguments)
    snapshot, result = _snapshot(arguments, config, feeds)
    output = _safe_output(arguments.output)
    paths = render_previews(snapshot, profile, output)
    _report_pipeline(result)
    print(f"Rendered {len(paths)} pages in {output}")
    return 0


def _build(arguments: argparse.Namespace) -> int:
    config, profile, feeds = _load_inputs(arguments)
    snapshot, result = _snapshot(arguments, config, feeds)
    output = _safe_output(arguments.output)
    manifest = build_release(snapshot, profile, output)
    _report_pipeline(result)
    print(f"Built release {manifest.release_id} for {profile.profile_id} in {output}")
    return 0


def _feeds_check(arguments: argparse.Namespace) -> int:
    if not 0 < arguments.timeout <= 120:
        raise CLIError("--timeout must be greater than 0 and at most 120 seconds")
    feeds = tuple(feed for feed in load_feed_registry(arguments.feeds) if feed.enabled)
    with (
        httpx.Client(timeout=arguments.timeout, follow_redirects=True) as client,
        ThreadPoolExecutor(
            max_workers=min(8, max(1, len(feeds))),
            thread_name_prefix="kindle-feed-check",
        ) as pool,
    ):
        health = tuple(pool.map(lambda feed: check_feed(client, feed), feeds))
    for item in health:
        state = "ok" if item.ok else "failed"
        status = "-" if item.status_code is None else str(item.status_code)
        detail = f" error={item.error}" if item.error else ""
        print(f"{state:6} {item.feed_id} status={status} entries={item.entry_count}{detail}")
    failures = sum(not item.ok for item in health)
    print(f"Checked {len(health)} enabled feeds; {failures} failed")
    return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "validate":
            return _validate(arguments)
        if arguments.command == "preview":
            return _preview(arguments)
        if arguments.command == "build":
            return _build(arguments)
        if arguments.command == "feeds-check":
            return _feeds_check(arguments)
        raise CLIError(f"unknown command: {arguments.command}")
    except (CLIError, ConfigError, ProfileError, PipelineError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

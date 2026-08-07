from __future__ import annotations

from kindle_brief.models import BriefStory, DashboardSnapshot
from kindle_brief.renderer.theme import DIVIDER, INK, MUTED, SECONDARY, font, scaled

from .common import footer, label, page_canvas


def _source_label(snapshot: DashboardSnapshot, story: BriefStory) -> str:
    sources = story.sources
    if not sources:
        sources_by_id = {article.article_id: article.source for article in snapshot.headlines}
        sources = tuple(
            dict.fromkeys(
                sources_by_id[article_id]
                for article_id in story.article_ids
                if article_id in sources_by_id
            )
        )
    if not sources:
        return ""
    prefix = "Source" if len(sources) == 1 else "Sources"
    return f"{prefix} · {', '.join(sources)}"


def render(snapshot: DashboardSnapshot, width: int, height: int):  # type: ignore[no-untyped-def]
    canvas, y = page_canvas(snapshot, width, height)
    margin = scaled(58, width)
    label(canvas, margin, y, "Morning brief")
    canvas.text(
        (width - margin, y),
        f"{len(snapshot.morning_brief)} stories",
        size=16,
        fill=MUTED,
        anchor="ra",
    )
    cursor = y + scaled(38, width)
    available_bottom = height - scaled(115, width)
    stories = snapshot.morning_brief[:8]
    rendered_sources: list[str] = []
    if not stories:
        canvas.text(
            (width // 2, cursor + scaled(150, width)),
            "No morning brief yet",
            size=39,
            anchor="ma",
        )
    for index, story in enumerate(stories, start=1):
        remaining = max(1, len(stories) - index + 1)
        remaining_space = available_bottom - cursor
        block = min(scaled(170, width), remaining_space // remaining)
        canvas.text((margin, cursor + scaled(3, width)), f"{index:02}", size=18, fill=MUTED)
        text_x = margin + scaled(48, width)
        max_text_width = width - margin - text_x
        headline, headline_size = canvas.fit_text(
            story.headline,
            max_text_width,
            size=24,
            minimum=20,
        )
        canvas.draw.text((text_x, cursor), headline, fill=INK, font=font(headline_size))
        summary_lines = canvas.wrapped_lines(
            story.summary,
            max_text_width,
            size=18,
            max_lines=2 if block >= scaled(145, width) else 1,
        )
        summary_y = cursor + scaled(39, width)
        canvas.draw_lines(
            summary_lines,
            x=text_x,
            y=summary_y,
            size=18,
            line_height=27,
            fill=SECONDARY,
        )
        why_y = summary_y + scaled(29 * len(summary_lines), width)
        why, why_size = canvas.fit_text(
            f"Why it matters · {story.why_it_matters}",
            max_text_width,
            size=15,
            minimum=13,
        )
        canvas.draw.text((text_x, why_y), why, fill=MUTED, font=font(why_size))
        source_label = _source_label(snapshot, story)
        if source_label:
            source, source_size = canvas.fit_text(
                source_label,
                max_text_width,
                size=14,
                minimum=12,
            )
            canvas.draw.text(
                (text_x, why_y + scaled(26, width)),
                source,
                fill=MUTED,
                font=font(source_size),
            )
            rendered_sources.append(source_label)
        cursor += block
        if cursor < available_bottom:
            canvas.draw.line(
                (text_x, cursor - scaled(12, width), width - margin, cursor - scaled(12, width)),
                fill=DIVIDER,
                width=1,
            )

    canvas.layout["morning_brief_sources"] = rendered_sources
    footer(canvas, snapshot, page_index=3)
    return canvas

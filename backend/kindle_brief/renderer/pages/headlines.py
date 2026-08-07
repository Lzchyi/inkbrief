from __future__ import annotations

from kindle_brief.models import Article, DashboardSnapshot
from kindle_brief.renderer import icons
from kindle_brief.renderer.theme import DIVIDER, INK, MUTED, SECONDARY, font, scaled

from .common import footer, label, page_canvas

_CATEGORY_LABELS = {
    "malaysia": "Malaysia",
    "ai_tech": "AI / Tech",
    "apple_dev": "Apple / Dev",
    "business": "Business",
    "insurance": "Insurance",
    "f1": "Formula 1",
    "science": "Science",
    "travel": "Travel / Useful Tech",
}
_CATEGORY_ORDER = tuple(_CATEGORY_LABELS)


def render(snapshot: DashboardSnapshot, width: int, height: int):  # type: ignore[no-untyped-def]
    canvas, y = page_canvas(snapshot, width, height)
    margin = scaled(58, width)
    label(canvas, margin, y, "Latest headlines")
    canvas.text(
        (width - margin, y),
        f"{len(snapshot.headlines[:15])} items",
        size=16,
        fill=MUTED,
        anchor="ra",
    )
    cursor = y + scaled(42, width)
    bottom = height - scaled(112, width)
    selected: list[Article] = list(snapshot.headlines[:15])
    groups: list[tuple[str, list[Article]]] = []
    for category in _CATEGORY_ORDER:
        items = [article for article in selected if article.category == category]
        if items:
            groups.append((category, items))
    uncategorized = [article for article in selected if article.category not in _CATEGORY_LABELS]
    if uncategorized:
        groups.append(("other", uncategorized))
    display_index = 0
    for category, items in groups:
        if cursor + scaled(65, width) > bottom:
            break
        icon_size = scaled(28, width)
        icons.category_mark(
            canvas.draw,
            (margin, cursor, margin + icon_size, cursor + icon_size),
            ink=INK,
            width=scaled(2, width),
        )
        canvas.text(
            (margin + scaled(43, width), cursor),
            _CATEGORY_LABELS.get(category, category.replace("_", " ").title()),
            size=17,
            stroke_width=1,
        )
        cursor += scaled(38, width)
        for article in items:
            if cursor + scaled(48, width) > bottom:
                break
            display_index += 1
            canvas.text(
                (margin, cursor + scaled(1, width)), f"{display_index:02}", size=14, fill=MUTED
            )
            title_x = margin + scaled(45, width)
            title, title_size = canvas.fit_text(
                article.title,
                width - margin - title_x,
                size=18,
                minimum=16,
            )
            canvas.draw.text((title_x, cursor), title, fill=INK, font=font(title_size))
            canvas.text(
                (title_x, cursor + scaled(27, width)),
                article.source,
                size=11,
                fill=SECONDARY,
            )
            cursor += scaled(49, width)
        canvas.draw.line(
            (margin, cursor - scaled(7, width), width - margin, cursor - scaled(7, width)),
            fill=DIVIDER,
            width=1,
        )
        cursor += scaled(9, width)

    footer(canvas, snapshot, page_index=4)
    return canvas

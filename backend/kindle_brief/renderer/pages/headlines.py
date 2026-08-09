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
    candidates: list[tuple[str, list[Article]]] = []
    for category in _CATEGORY_ORDER:
        items = [article for article in snapshot.headlines[:15] if article.category == category]
        if items:
            candidates.append((category, items))
    uncategorized = [
        article for article in snapshot.headlines[:15] if article.category not in _CATEGORY_LABELS
    ]
    if uncategorized:
        candidates.append(("other", uncategorized))

    chosen: dict[str, list[Article]] = {}
    for offset in range(3):
        for category, items in candidates:
            if sum(len(group) for group in chosen.values()) >= 9:
                break
            if offset < len(items):
                chosen.setdefault(category, []).append(items[offset])
    groups = [(category, chosen[category]) for category, _ in candidates if category in chosen]
    item_count = sum(len(items) for _, items in groups)

    label(canvas, margin, y, "Latest headlines")
    canvas.text(
        (width - margin, y),
        f"{item_count} items",
        size=20,
        fill=MUTED,
        anchor="ra",
    )
    cursor = y + scaled(49, width)
    bottom = height - scaled(110, width)
    display_index = 0
    for category, items in groups:
        if cursor + scaled(75, width) > bottom:
            break
        icon_size = scaled(36, width)
        icons.category_mark(
            canvas.draw,
            (margin, cursor, margin + icon_size, cursor + icon_size),
            ink=INK,
            width=scaled(3, width),
        )
        canvas.text(
            (margin + scaled(50, width), cursor),
            _CATEGORY_LABELS.get(category, category.replace("_", " ").title()),
            size=24,
            stroke_width=1,
        )
        cursor += scaled(50, width)
        for article in items:
            if cursor + scaled(76, width) > bottom:
                break
            display_index += 1
            canvas.text(
                (margin, cursor + scaled(2, width)), f"{display_index:02}", size=20, fill=MUTED
            )
            title_x = margin + scaled(58, width)
            title, title_size = canvas.fit_text(
                article.title,
                width - margin - title_x,
                size=31,
                minimum=28,
            )
            canvas.draw.text((title_x, cursor), title, fill=INK, font=font(title_size))
            canvas.text(
                (title_x, cursor + scaled(43, width)),
                article.source,
                size=19,
                fill=SECONDARY,
            )
            cursor += scaled(78, width)
        canvas.draw.line(
            (margin, cursor - scaled(8, width), width - margin, cursor - scaled(8, width)),
            fill=DIVIDER,
            width=1,
        )
        cursor += scaled(12, width)

    footer(canvas, snapshot, page_index=4)
    return canvas

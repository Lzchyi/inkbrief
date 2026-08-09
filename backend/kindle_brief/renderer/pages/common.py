from __future__ import annotations

from zoneinfo import ZoneInfo

from PIL import ImageDraw

from kindle_brief.models import DashboardSnapshot
from kindle_brief.renderer.canvas import EInkCanvas
from kindle_brief.renderer.formatting import header_text, snapshot_is_stale
from kindle_brief.renderer.theme import INK, MUTED, font, scaled


def page_canvas(snapshot: DashboardSnapshot, width: int, height: int) -> tuple[EInkCanvas, int]:
    canvas = EInkCanvas(width, height)
    content_top = canvas.header(header_text(snapshot), stale=snapshot_is_stale(snapshot))
    return canvas, content_top


def footer(
    canvas: EInkCanvas,
    snapshot: DashboardSnapshot,
    *,
    page_index: int,
    attribution: str = "",
) -> None:
    y = canvas.height - scaled(83, canvas.width)
    if attribution:
        text, font_size = canvas.fit_text(
            attribution,
            canvas.width - scaled(170, canvas.width),
            size=17,
            minimum=14,
        )
        canvas.draw.text(
            (scaled(54, canvas.width), y),
            text,
            font=font(font_size),
            fill=MUTED,
        )
    updated = snapshot.generated_at.astimezone(ZoneInfo(snapshot.timezone))
    label_text = "Cached" if snapshot_is_stale(snapshot) else "Updated"
    canvas.text(
        (canvas.width - scaled(54, canvas.width), y),
        f"{label_text} {updated:%H:%M}",
        size=17,
        fill=MUTED,
        anchor="ra",
    )
    canvas.page_indicator(page_index, 5)


def label(canvas: EInkCanvas, x: int, y: int, value: str) -> None:
    canvas.text((x, y), value.upper(), size=22, fill=MUTED, stroke_width=1)


def metric(
    draw: ImageDraw.ImageDraw,
    canvas: EInkCanvas,
    *,
    x: int,
    y: int,
    title: str,
    value: str,
) -> None:
    canvas.text((x, y), title, size=20, fill=MUTED)
    canvas.text((x, y + scaled(32, canvas.width)), value, size=32, fill=INK)

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from PIL import Image, ImageDraw

from . import icons
from .theme import DIVIDER, INK, MUTED, PAPER, font, scaled


@dataclass(frozen=True, slots=True)
class Hotspot:
    name: str
    left: int
    top: int
    right: int
    bottom: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "name": self.name,
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
        }


class EInkCanvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.image = Image.new("L", (width, height), PAPER)
        self.draw = ImageDraw.Draw(self.image)
        self.hotspots: list[Hotspot] = []
        self.layout: dict[str, object] = {}

    def header(self, text: str, *, stale: bool = False) -> int:
        top = scaled(34, self.width)
        home_size = scaled(52, self.width)
        home_left = scaled(45, self.width)
        icons.home(
            self.draw,
            (home_left, top, home_left + home_size, top + home_size),
            ink=INK,
            width=scaled(3, self.width),
        )
        pad = scaled(22, self.width)
        self.hotspots.append(
            Hotspot(
                "home",
                home_left - pad,
                top - pad,
                home_left + home_size + pad,
                top + home_size + pad,
            )
        )
        header_font = font(scaled(32, self.width))
        center_x = self.width // 2
        baseline_y = top + scaled(3, self.width)
        bbox = self.draw.textbbox(
            (center_x, baseline_y),
            text,
            font=header_font,
            anchor="ma",
        )
        self.draw.text(
            (center_x, baseline_y),
            text,
            fill=INK,
            font=header_font,
            anchor="ma",
        )
        self.layout["header"] = {
            "text": text,
            "left": bbox[0],
            "right": bbox[2],
            "center_x": (bbox[0] + bbox[2]) / 2,
        }
        if stale:
            radius = scaled(5, self.width)
            self.draw.ellipse(
                (
                    self.width - scaled(52, self.width),
                    top + radius,
                    self.width - scaled(52, self.width) + radius * 2,
                    top + radius * 3,
                ),
                fill=MUTED,
            )
        divider_y = top + home_size + scaled(30, self.width)
        self.rule(divider_y)
        return divider_y + scaled(32, self.width)

    def rule(self, y: int, *, left: int | None = None, right: int | None = None) -> None:
        margin = scaled(54, self.width)
        self.draw.line((left or margin, y, right or self.width - margin, y), fill=DIVIDER, width=1)

    def text(
        self,
        position: tuple[int, int],
        value: str,
        *,
        size: int,
        fill: int = INK,
        anchor: str | None = None,
        stroke_width: int = 0,
    ) -> None:
        self.draw.text(
            position,
            value,
            font=font(scaled(size, self.width)),
            fill=fill,
            anchor=anchor,
            stroke_width=stroke_width,
            stroke_fill=fill,
        )

    def fit_text(
        self, value: str, max_width: int, *, size: int, minimum: int = 18
    ) -> tuple[str, int]:
        candidate = value.strip()
        font_size = scaled(size, self.width)
        minimum_size = scaled(minimum, self.width)
        while (
            font_size > minimum_size
            and self.draw.textlength(candidate, font=font(font_size)) > max_width
        ):
            font_size -= 1
        if self.draw.textlength(candidate, font=font(font_size)) <= max_width:
            return candidate, font_size
        ellipsis = "…"
        while (
            candidate
            and self.draw.textlength(candidate + ellipsis, font=font(font_size)) > max_width
        ):
            candidate = candidate[:-1].rstrip()
        return candidate + ellipsis, font_size

    def wrapped_lines(self, value: str, max_width: int, *, size: int, max_lines: int) -> list[str]:
        words = value.split()
        lines: list[str] = []
        current = ""
        wrapped_font = font(scaled(size, self.width))
        while words and len(lines) < max_lines:
            word = words.pop(0)
            candidate = f"{current} {word}".strip()
            if self.draw.textlength(candidate, font=wrapped_font) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = word
            else:
                fitted, _ = self.fit_text(word, max_width, size=size, minimum=size)
                lines.append(fitted)
                current = ""
        if current and len(lines) < max_lines:
            lines.append(current)
        if words and lines:
            tail = lines[-1].rstrip("…")
            fitted, _ = self.fit_text(tail + "…", max_width, size=size, minimum=size)
            lines[-1] = fitted
        return lines

    def page_indicator(self, current: int, total: int) -> None:
        y = self.height - scaled(43, self.width)
        gap = scaled(25, self.width)
        radius = scaled(5, self.width)
        start = self.width / 2 - ((total - 1) * gap) / 2
        for index in range(total):
            x = start + index * gap
            if index == current:
                self.draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=INK)
            else:
                self.draw.ellipse(
                    (x - radius, y - radius, x + radius, y + radius), outline=MUTED, width=1
                )

    def metadata(self) -> dict[str, object]:
        return {
            "width": self.width,
            "height": self.height,
            "hotspots": [item.as_dict() for item in self.hotspots],
            "layout": self.layout,
        }

    def paste(self, image: Image.Image, position: tuple[int, int]) -> None:
        self.image.paste(image, position)

    def convert_for_eink(self, *, bits: int = 4, dither: bool = False) -> Image.Image:
        if bits == 1:
            method = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
            return self.image.convert("1", dither=method)
        if bits == 4:
            levels = 15
            return self.image.point(
                lambda value: round(value / 255 * levels) * 255 // levels, mode="L"
            )
        return self.image.copy()

    def draw_lines(
        self, lines: Iterable[str], *, x: int, y: int, size: int, line_height: int, fill: int = INK
    ) -> int:
        for line in lines:
            self.text((x, y), line, size=size, fill=fill)
            y += scaled(line_height, self.width)
        return y

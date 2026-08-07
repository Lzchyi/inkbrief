from datetime import date

import pytest
from kindle_brief.lunar import to_lunar_date


@pytest.mark.parametrize(
    ("gregorian", "expected"),
    (
        (date(2026, 2, 17), "农历正月初一"),
        (date(2026, 8, 8), "农历六月廿六"),
        (date(2023, 3, 22), "农历闰二月初一"),
    ),
)
def test_lunar_date_formats_normal_new_year_and_leap_month_dates(
    gregorian: date, expected: str
) -> None:
    converted = to_lunar_date(gregorian)

    assert converted.gregorian_date == gregorian
    assert converted.display_text == expected


def test_lunar_date_rejects_non_date_values() -> None:
    with pytest.raises(TypeError, match="must be a date"):
        to_lunar_date("2026-08-08")  # type: ignore[arg-type]

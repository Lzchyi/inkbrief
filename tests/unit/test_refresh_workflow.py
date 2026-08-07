from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_refresh_schedule_has_no_duplicate_2317_run() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "refresh.yml").read_text(encoding="utf-8")

    assert 'cron: "17 0-22 * * *"' in workflow
    assert 'cron: "0 23 * * *"' in workflow
    assert 'cron: "17 * * * *"' not in workflow

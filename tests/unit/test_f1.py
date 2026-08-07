from datetime import UTC, datetime
from typing import Any

import httpx
from kindle_brief.demo import demo_snapshot
from kindle_brief.f1 import (
    JolpicaClient,
    parse_jolpica_snapshot,
    to_malaysia_time,
)


def _race_payload(
    sessions: dict[str, object],
    *,
    include_race_time: bool = True,
    round_number: str = "11",
    race_name: str = "Hungarian Grand Prix",
    circuit_id: str = "hungaroring",
    circuit_name: str = "Hungaroring",
    race_date: str = "2026-07-26",
) -> dict[str, object]:
    race: dict[str, object] = {
        "season": "2026",
        "round": round_number,
        "raceName": race_name,
        "Circuit": {
            "circuitId": circuit_id,
            "circuitName": circuit_name,
        },
        "date": race_date,
    }
    if include_race_time:
        race["time"] = "13:00:00Z"
    race.update(sessions)
    return {"MRData": {"RaceTable": {"Races": [race]}}}


def _driver_payload() -> dict[str, object]:
    return {
        "MRData": {
            "StandingsTable": {
                "StandingsLists": [
                    {
                        "DriverStandings": [
                            {
                                "position": "2",
                                "points": "231",
                                "Driver": {
                                    "driverId": "piastri",
                                    "code": "PIA",
                                    "givenName": "Oscar",
                                    "familyName": "Piastri",
                                },
                            },
                            {
                                "position": "1",
                                "points": "245",
                                "Driver": {
                                    "driverId": "norris",
                                    "code": "NOR",
                                    "givenName": "Lando",
                                    "familyName": "Norris",
                                },
                            },
                            {
                                "position": "3",
                                "points": "198",
                                "Driver": {
                                    "driverId": "verstappen",
                                    "code": "VER",
                                    "givenName": "Max",
                                    "familyName": "Verstappen",
                                },
                            },
                            {
                                "position": "4",
                                "points": "160",
                                "Driver": {
                                    "driverId": "leclerc",
                                    "code": "LEC",
                                    "givenName": "Charles",
                                    "familyName": "Leclerc",
                                },
                            },
                        ]
                    }
                ]
            }
        }
    }


def _constructor_payload() -> dict[str, object]:
    return {
        "MRData": {
            "StandingsTable": {
                "StandingsLists": [
                    {
                        "ConstructorStandings": [
                            {
                                "position": "1",
                                "points": "476",
                                "Constructor": {
                                    "constructorId": "mclaren",
                                    "name": "McLaren",
                                },
                            },
                            {
                                "position": "2",
                                "points": "344",
                                "Constructor": {
                                    "constructorId": "red_bull",
                                    "name": "Red Bull",
                                },
                            },
                            {
                                "position": "3",
                                "points": "301",
                                "Constructor": {
                                    "constructorId": "ferrari",
                                    "name": "Ferrari",
                                },
                            },
                            {
                                "position": "4",
                                "points": "220",
                                "Constructor": {
                                    "constructorId": "mercedes",
                                    "name": "Mercedes",
                                },
                            },
                        ]
                    }
                ]
            }
        }
    }


def _parse(sessions: dict[str, object], **race_options: Any):
    return parse_jolpica_snapshot(
        _race_payload(sessions, **race_options),
        _driver_payload(),
        _constructor_payload(),
        fetched_at=datetime(2026, 7, 20, tzinfo=UTC),
    )


def test_demo_snapshot_uses_next_official_2026_weekend() -> None:
    snapshot = demo_snapshot()
    f1 = snapshot.f1

    assert f1 is not None
    assert (f1.season, f1.round_number) == (2026, 12)
    assert (f1.event_name, f1.circuit_id, f1.circuit_name) == (
        "Dutch Grand Prix",
        "zandvoort",
        "Circuit Park Zandvoort",
    )
    assert [(session.name, session.starts_at.isoformat()) for session in f1.sessions] == [
        ("Practice 1", "2026-08-21T10:30:00+00:00"),
        ("Sprint Qualifying", "2026-08-21T14:30:00+00:00"),
        ("Sprint", "2026-08-22T10:00:00+00:00"),
        ("Qualifying", "2026-08-22T14:00:00+00:00"),
        ("Race", "2026-08-23T13:00:00+00:00"),
    ]


def test_parses_normal_weekend_and_top_three_standings() -> None:
    snapshot = _parse(
        {
            "FirstPractice": {"date": "2026-07-24", "time": "11:30:00Z"},
            "SecondPractice": {"date": "2026-07-24", "time": "15:00:00Z"},
            "ThirdPractice": {"date": "2026-07-25", "time": "10:30:00Z"},
            "Qualifying": {"date": "2026-07-25", "time": "14:00:00Z"},
        }
    )

    assert snapshot.event_name == "Hungarian Grand Prix"
    assert snapshot.circuit_id == "hungaroring"
    assert [session.name for session in snapshot.sessions] == [
        "FP1",
        "FP2",
        "FP3",
        "Qualifying",
        "Race",
    ]
    assert [standing.code for standing in snapshot.driver_standings] == ["NOR", "PIA", "VER"]
    assert [standing.code for standing in snapshot.constructor_standings] == [
        "MCL",
        "RBR",
        "FER",
    ]
    assert snapshot.status.attribution == "F1 data by Jolpica-F1"


def test_parses_sprint_weekend_without_assuming_fp2_or_fp3() -> None:
    snapshot = _parse(
        {
            "FirstPractice": {"date": "2026-08-21", "time": "10:30:00Z"},
            "SprintQualifying": {"date": "2026-08-21", "time": "14:30:00Z"},
            "Sprint": {"date": "2026-08-22", "time": "10:00:00Z"},
            "Qualifying": {"date": "2026-08-22", "time": "14:00:00Z"},
        },
        round_number="12",
        race_name="Dutch Grand Prix",
        circuit_id="zandvoort",
        circuit_name="Circuit Park Zandvoort",
        race_date="2026-08-23",
    )

    assert snapshot.event_name == "Dutch Grand Prix"
    assert snapshot.circuit_id == "zandvoort"
    assert [session.name for session in snapshot.sessions] == [
        "FP1",
        "Sprint Qualifying",
        "Sprint",
        "Qualifying",
        "Race",
    ]


def test_preserves_older_and_unknown_session_shapes_dynamically() -> None:
    snapshot = _parse(
        {
            "SprintShootout": {"date": "2026-07-24", "time": "12:00:00Z"},
            "RookiePractice": {"date": "2026-07-24", "time": "15:00:00Z"},
        }
    )

    assert [session.name for session in snapshot.sessions] == [
        "Sprint Shootout",
        "Rookie Practice",
        "Race",
    ]


def test_session_time_converts_from_utc_to_malaysia_time() -> None:
    snapshot = _parse({})
    local_race = to_malaysia_time(snapshot.sessions[0].starts_at)

    assert local_race.isoformat() == "2026-07-26T21:00:00+08:00"


def test_parser_skips_identified_session_without_time() -> None:
    snapshot = _parse({"FirstPractice": {"date": "2026-07-24"}})

    assert [session.name for session in snapshot.sessions] == ["Race"]


def test_parser_keeps_event_when_race_time_is_missing() -> None:
    snapshot = parse_jolpica_snapshot(
        _race_payload(
            {"FirstPractice": {"date": "2026-07-24", "time": "11:30:00Z"}},
            include_race_time=False,
        ),
        _driver_payload(),
        _constructor_payload(),
        fetched_at=datetime(2026, 7, 20, tzinfo=UTC),
    )

    assert snapshot.event_name == "Hungarian Grand Prix"
    assert [session.name for session in snapshot.sessions] == ["FP1"]


def test_parser_skips_standings_without_numeric_positions() -> None:
    drivers: Any = _driver_payload()
    constructors: Any = _constructor_payload()
    driver_rows = drivers["MRData"]["StandingsTable"]["StandingsLists"][0]["DriverStandings"]
    constructor_rows = constructors["MRData"]["StandingsTable"]["StandingsLists"][0][
        "ConstructorStandings"
    ]
    driver_rows[0]["position"] = "excluded"
    driver_rows[1].pop("position")
    for row in constructor_rows:
        row["position"] = "not classified"

    snapshot = parse_jolpica_snapshot(
        _race_payload({}),
        drivers,
        constructors,
        fetched_at=datetime(2026, 7, 20, tzinfo=UTC),
    )

    assert snapshot.event_name == "Hungarian Grand Prix"
    assert [standing.code for standing in snapshot.driver_standings] == ["VER", "LEC"]
    assert snapshot.constructor_standings == ()


def test_client_uses_jolpica_endpoints_without_live_network_access() -> None:
    race = _race_payload({})
    drivers = _driver_payload()
    constructors = _constructor_payload()
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"].startswith("KindleBrief/")
        seen_paths.append(request.url.path)
        if request.url.path.endswith("/next/races/"):
            return httpx.Response(200, json=race)
        if request.url.path.endswith("/driverstandings/"):
            assert request.url.params["limit"] == "3"
            return httpx.Response(200, json=drivers)
        if request.url.path.endswith("/constructorstandings/"):
            assert request.url.params["limit"] == "3"
            return httpx.Response(200, json=constructors)
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        snapshot = JolpicaClient(client=http_client).fetch_next(
            fetched_at=datetime(2026, 7, 20, tzinfo=UTC)
        )

    assert snapshot.round_number == 11
    assert len(seen_paths) == 3

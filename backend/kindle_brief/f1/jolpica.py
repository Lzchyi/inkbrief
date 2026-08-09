"""Pure Jolpica response parsing plus a small synchronous HTTP client."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import cast
from zoneinfo import ZoneInfo

import httpx

from kindle_brief.models import F1Session, F1Snapshot, SourceStatus, Standing

F1_ATTRIBUTION = "F1 data by Jolpica-F1"
DEFAULT_USER_AGENT = "KindleBrief/0.1 (personal non-commercial e-ink dashboard)"
MALAYSIA_TIMEZONE = ZoneInfo("Asia/Kuala_Lumpur")
_JOLPICA_LICENSE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"

_SESSION_NAMES = {
    "FirstPractice": "FP1",
    "SecondPractice": "FP2",
    "ThirdPractice": "FP3",
    "Qualifying": "Qualifying",
    "SprintShootout": "Sprint Shootout",
    "SprintQualifying": "Sprint Qualifying",
    "Sprint": "Sprint",
}

_CONSTRUCTOR_CODES = {
    "alpine": "ALP",
    "aston_martin": "AMR",
    "audi": "AUD",
    "cadillac": "CAD",
    "ferrari": "FER",
    "haas": "HAS",
    "mclaren": "MCL",
    "mercedes": "MER",
    "rb": "RB",
    "racing_bulls": "RBS",
    "red_bull": "RBR",
    "sauber": "SAU",
    "williams": "WIL",
}

_OFFICIAL_CIRCUIT_NAMES = {
    # Jolpica still carries the venue's older expanded label.
    "zandvoort": "Circuit Zandvoort",
}


class F1DataError(ValueError):
    """Raised when a Jolpica response is incomplete or malformed."""


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise F1DataError(f"{field} must be an object")
    return cast(Mapping[str, object], value)


def _sequence(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise F1DataError(f"{field} must be an array")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise F1DataError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _number(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise F1DataError(f"{field} must be numeric")
    try:
        result = float(cast(str | int | float, value))
    except (TypeError, ValueError) as exc:
        raise F1DataError(f"{field} must be numeric") from exc
    if not math.isfinite(result):
        raise F1DataError(f"{field} must be finite")
    return result


def _integer(value: object, field: str) -> int:
    numeric = _number(value, field)
    if not numeric.is_integer():
        raise F1DataError(f"{field} must be an integer")
    return int(numeric)


def _optional_jolpica_datetime(value: Mapping[str, object]) -> datetime | None:
    event_date = _optional_text(value.get("date"))
    event_time = _optional_text(value.get("time"))
    if event_date is None or event_time is None:
        return None
    try:
        parsed = datetime.fromisoformat(f"{event_date}T{event_time.replace('Z', '+00:00')}")
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def to_malaysia_time(value: datetime) -> datetime:
    """Convert an aware session timestamp to Asia/Kuala_Lumpur."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise F1DataError("session timestamp must be timezone-aware")
    return value.astimezone(MALAYSIA_TIMEZONE)


def _humanize_session_key(key: str) -> str:
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", key).replace("_", " ")
    return " ".join(part for part in words.split() if part)


def _parse_sessions(race: Mapping[str, object]) -> tuple[F1Session, ...]:
    parsed: list[F1Session] = []
    race_start = _optional_jolpica_datetime(race)
    if race_start is not None:
        parsed.append(F1Session(name="Race", starts_at=race_start))

    ignored = {"Circuit", "season", "round", "raceName", "url", "date", "time"}
    for key, raw in race.items():
        if key in ignored or not isinstance(raw, Mapping):
            continue
        value = cast(Mapping[str, object], raw)
        if "date" not in value and "time" not in value:
            continue
        starts_at = _optional_jolpica_datetime(value)
        if starts_at is None:
            continue
        name = _SESSION_NAMES.get(key, _humanize_session_key(key))
        parsed.append(F1Session(name=name, starts_at=starts_at))

    unique: dict[tuple[str, datetime], F1Session] = {
        (session.name, session.starts_at): session for session in parsed
    }
    return tuple(sorted(unique.values(), key=lambda session: session.starts_at))


def _standings_list(payload: Mapping[str, object], field: str) -> Mapping[str, object]:
    mrdata = _mapping(payload.get("MRData"), f"{field}.MRData")
    table = _mapping(mrdata.get("StandingsTable"), f"{field}.StandingsTable")
    lists = _sequence(table.get("StandingsLists"), f"{field}.StandingsLists")
    if not lists:
        raise F1DataError(f"{field}.StandingsLists is empty")
    return _mapping(lists[0], f"{field}.StandingsLists[0]")


def _fallback_code(identifier: str) -> str:
    parts = [part for part in re.split(r"[^a-zA-Z0-9]+", identifier) if part]
    if not parts:
        raise F1DataError("cannot derive a standings code from an empty identifier")
    if len(parts) >= 2:
        return "".join(part[0] for part in parts)[:3].upper()
    return parts[0][:3].upper()


def _optional_standing_position(value: object) -> int | None:
    try:
        position = _integer(value, "position")
    except F1DataError:
        return None
    return position if position > 0 else None


def _driver_standings(payload: Mapping[str, object]) -> tuple[Standing, ...]:
    standings = _standings_list(payload, "driver standings")
    rows = _sequence(standings.get("DriverStandings"), "DriverStandings")
    result: list[Standing] = []
    for index, raw in enumerate(rows):
        row = _mapping(raw, f"DriverStandings[{index}]")
        position = _optional_standing_position(row.get("position"))
        if position is None:
            continue
        driver = _mapping(row.get("Driver"), f"DriverStandings[{index}].Driver")
        identifier = _text(driver.get("driverId"), f"DriverStandings[{index}].driverId")
        code = _optional_text(driver.get("code")) or _fallback_code(identifier)
        given_name = _text(driver.get("givenName"), f"DriverStandings[{index}].givenName")
        family_name = _text(driver.get("familyName"), f"DriverStandings[{index}].familyName")
        result.append(
            Standing(
                position=position,
                code=code.upper(),
                name=f"{given_name} {family_name}",
                points=_number(row.get("points"), f"DriverStandings[{index}].points"),
            )
        )
    return tuple(sorted(result, key=lambda item: item.position)[:3])


def _constructor_standings(payload: Mapping[str, object]) -> tuple[Standing, ...]:
    standings = _standings_list(payload, "constructor standings")
    rows = _sequence(standings.get("ConstructorStandings"), "ConstructorStandings")
    result: list[Standing] = []
    for index, raw in enumerate(rows):
        row = _mapping(raw, f"ConstructorStandings[{index}]")
        position = _optional_standing_position(row.get("position"))
        if position is None:
            continue
        constructor = _mapping(row.get("Constructor"), f"ConstructorStandings[{index}].Constructor")
        identifier = _text(
            constructor.get("constructorId"),
            f"ConstructorStandings[{index}].constructorId",
        )
        result.append(
            Standing(
                position=position,
                code=_CONSTRUCTOR_CODES.get(identifier, _fallback_code(identifier)),
                name=_text(constructor.get("name"), f"ConstructorStandings[{index}].name"),
                points=_number(row.get("points"), f"ConstructorStandings[{index}].points"),
            )
        )
    return tuple(sorted(result, key=lambda item: item.position)[:3])


def _next_race(payload: Mapping[str, object]) -> Mapping[str, object]:
    mrdata = _mapping(payload.get("MRData"), "race.MRData")
    table = _mapping(mrdata.get("RaceTable"), "race.RaceTable")
    races = _sequence(table.get("Races"), "race.Races")
    if not races:
        raise F1DataError("race.Races is empty")
    return _mapping(races[0], "race.Races[0]")


def parse_jolpica_snapshot(
    race_payload: Mapping[str, object],
    driver_payload: Mapping[str, object],
    constructor_payload: Mapping[str, object],
    *,
    fetched_at: datetime,
) -> F1Snapshot:
    """Parse Jolpica schedule and standings responses without network access."""

    race = _next_race(race_payload)
    circuit = _mapping(race.get("Circuit"), "race.Circuit")
    circuit_id = _optional_text(circuit.get("circuitId"))
    source_circuit_name = _text(circuit.get("circuitName"), "race.Circuit.circuitName")
    return F1Snapshot(
        season=_integer(race.get("season"), "race.season"),
        round_number=_integer(race.get("round"), "race.round"),
        event_name=_text(race.get("raceName"), "race.raceName"),
        circuit_name=_OFFICIAL_CIRCUIT_NAMES.get(circuit_id, source_circuit_name),
        circuit_id=circuit_id,
        sessions=_parse_sessions(race),
        driver_standings=_driver_standings(driver_payload),
        constructor_standings=_constructor_standings(constructor_payload),
        status=SourceStatus(
            source="Jolpica-F1",
            fetched_at=fetched_at,
            attribution=F1_ATTRIBUTION,
            license_url=_JOLPICA_LICENSE_URL,
        ),
    )


class JolpicaClient:
    """Client for the maintained Jolpica successor to the Ergast API."""

    BASE_URL = "https://api.jolpi.ca/ergast/f1"

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: float = 15.0,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("user_agent must be non-empty")
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None
        self._headers = {"User-Agent": user_agent, "Accept": "application/json"}

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> JolpicaClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch_next(self, *, fetched_at: datetime | None = None) -> F1Snapshot:
        race = self._get_json("current/next/races/")
        drivers = self._get_json("current/driverstandings/", params={"limit": 3})
        constructors = self._get_json("current/constructorstandings/", params={"limit": 3})
        return parse_jolpica_snapshot(
            race,
            drivers,
            constructors,
            fetched_at=fetched_at or datetime.now(UTC),
        )

    def _get_json(
        self, path: str, *, params: Mapping[str, int] | None = None
    ) -> Mapping[str, object]:
        url = f"{self.BASE_URL}/{path}"
        try:
            response = self._client.get(url, params=params, headers=self._headers)
            response.raise_for_status()
            return _mapping(response.json(), "response")
        except (httpx.HTTPError, ValueError) as exc:
            raise F1DataError(f"Jolpica request failed: {exc}") from exc

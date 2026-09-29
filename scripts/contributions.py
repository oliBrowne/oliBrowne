#!/usr/bin/env python3
"""Build a small animated profile calendar from GitHub's public daily counts.

Run from the repository root: python scripts/contributions.py --username oliBrowne
No third-party Python packages or personal access token are required.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
COLORS = ("#161b22", "#165b43", "#22845a", "#36b778", "#73e7a1")


class CalendarError(ValueError):
    """The endpoint did not contain a trustworthy daily calendar."""


class CalendarParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cells: list[dict[str, str | None]] = []
        self.tooltips: dict[str, str] = {}
        self._tooltip_target: str | None = None
        self._tooltip_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "td" and "data-date" in attributes:
            self.cells.append(attributes)
        if tag == "tool-tip":
            self._tooltip_target = attributes.get("for")
            self._tooltip_parts = []

    def handle_data(self, data: str) -> None:
        if self._tooltip_target is not None:
            self._tooltip_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "tool-tip" and self._tooltip_target is not None:
            target = self._tooltip_target
            if target in self.tooltips:
                raise CalendarError(f"Duplicate tooltip for {target}")
            self.tooltips[target] = " ".join("".join(self._tooltip_parts).split())
            self._tooltip_target = None
            self._tooltip_parts = []


def parse_calendar(html: str, *, today: date | None = None, min_days: int = 350) -> list[dict]:
    """Parse exact counts, rejecting missing or inconsistent source data.

    GitHub renders the table in weekday order, so it must be sorted by date.
    The range begins on a Sunday and may include more than 365 days.
    """
    today = today or datetime.now(timezone.utc).date()
    parser = CalendarParser()
    parser.feed(html)
    parser.close()
    records: dict[date, dict] = {}
    for cell in parser.cells:
        raw_date = cell.get("data-date") or ""
        try:
            day = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise CalendarError(f"Invalid calendar date: {raw_date!r}") from exc
        if day in records:
            raise CalendarError(f"Duplicate calendar date: {day}")
        raw_level = cell.get("data-level") or ""
        if raw_level not in {"0", "1", "2", "3", "4"}:
            raise CalendarError(f"Invalid contribution level for {day}")
        tooltip = parser.tooltips.get(cell.get("id") or "")
        if tooltip is None:
            raise CalendarError(f"Missing contribution count for {day}")
        if re.fullmatch(r"No contributions on .+\.", tooltip, re.IGNORECASE):
            count = 0
        else:
            match = re.fullmatch(r"(\d+|\d{1,3}(?:,\d{3})+) contributions? on .+\.", tooltip, re.IGNORECASE)
            if match is None:
                raise CalendarError(f"Unrecognized contribution count for {day}: {tooltip!r}")
            count = int(match.group(1).replace(",", ""))
        level = int(raw_level)
        if (count == 0) != (level == 0):
            raise CalendarError(f"Count and color level disagree for {day}")
        records[day] = {"date": day.isoformat(), "count": count, "level": level}

    dates = sorted(records)
    if not dates or not min_days <= len(dates) <= 378:
        raise CalendarError(f"Expected a full calendar; received {len(dates)} days")
    if dates[-1] > today or dates[-1] < today - timedelta(days=2):
        raise CalendarError(f"Calendar ends at an unexpected date: {dates[-1]}")
    for previous, current in zip(dates, dates[1:]):
        if current - previous != timedelta(days=1):
            raise CalendarError(f"Missing calendar day between {previous} and {current}")
    return [records[day] for day in dates]


def summarize(username: str, days: list[dict], *, fetched_on: date | None = None) -> dict:
    if not days:
        raise CalendarError("Cannot summarize an empty calendar")
    run = longest = 0
    for day in days:
        run = run + 1 if day["count"] else 0
        longest = max(longest, run)
    return {
        "username": username,
        "source": f"https://github.com/users/{username}/contributions",
        "fetched_on": (fetched_on or datetime.now(timezone.utc).date()).isoformat(),
        "range": {"start": days[0]["date"], "end": days[-1]["date"]},
        "total_contributions": sum(day["count"] for day in days),
        "active_days": sum(day["count"] > 0 for day in days),
        "longest_streak": longest,
        "days": days,
    }


def render_svg(data: dict) -> str:
    """Render real levels, Sunday-first columns, and a short one-shot reveal."""
    days = data["days"]
    first = date.fromisoformat(days[0]["date"])
    sunday = first - timedelta(days=(first.weekday() + 1) % 7)
    last = date.fromisoformat(days[-1]["date"])
    columns = (last - sunday).days // 7 + 1
    if columns > 54:
        raise CalendarError("Calendar is too wide to render")
    username = escape(data["username"])
    title = f"{username} / contribution history"
    total = data["total_contributions"]
    description = escape(
        f"{total} contributions, {data['active_days']} active days, and a longest streak "
        f"of {data['longest_streak']} days from {first} through {last}. "
        "Counts reflect the contribution calendar visible on the public GitHub profile."
    )
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="860" height="268" viewBox="0 0 860 268" role="img" aria-labelledby="title description">',
        f'<title id="title">{title}</title><desc id="description">{description}</desc>',
        '<style>',
        'text{font-family:ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace}',
        '.day{opacity:1;animation:arrive .36s ease-out backwards}',
        '@keyframes arrive{from{opacity:0;transform:translateY(-5px)}to{opacity:1;transform:translateY(0)}}',
        '@media(prefers-reduced-motion:reduce){.day{animation:none}}',
        '</style>',
        '<rect x=".5" y=".5" width="859" height="267" rx="16" fill="#0d1117" stroke="#30363d"/>',
        '<path d="M1 35H859" stroke="#30363d"/>',
        '<circle cx="21" cy="18" r="4" fill="#ff6b6b"/><circle cx="37" cy="18" r="4" fill="#e7bc5a"/><circle cx="53" cy="18" r="4" fill="#73e7a1"/>',
        f'<text x="430" y="22" text-anchor="middle" font-size="11" fill="#8b949e">{title}</text>',
        '<text x="24" y="60" font-size="12" fill="#73e7a1">$ git log --contributions</text>',
        '<text x="24" y="253" font-size="10" fill="#8b949e">Observed range only · public profile calendar</text>',
        f'<text x="836" y="253" text-anchor="end" font-size="10" fill="#8b949e">{first} — {last}</text>',
    ]
    left, top, step, size = 74, 92, 14, 10
    for weekday, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        parts.append(f'<text x="34" y="{top + weekday * step + 8}" font-size="10" fill="#8b949e">{label}</text>')
    seen_months: set[tuple[int, int]] = set()
    last_label_column = -5
    for day in days:
        current = date.fromisoformat(day["date"])
        offset = (current - sunday).days
        column, weekday = divmod(offset, 7)
        key = (current.year, current.month)
        if key not in seen_months:
            seen_months.add(key)
            # Keep a short initial partial month from colliding with the next.
            if (current.day <= 7 or column == 0 and current.day <= 22) and column - last_label_column >= 3:
                label = current.strftime("%b")
                parts.append(f'<text x="{left + column * step}" y="80" font-size="10" fill="#8b949e">{label}</text>')
                last_label_column = column
        delay = column * 0.025 + weekday * 0.04
        count = day["count"]
        plural = "" if count == 1 else "s"
        parts.append(
            f'<rect class="day" x="{left + column * step}" y="{top + weekday * step}" '
            f'width="{size}" height="{size}" rx="2" fill="{COLORS[day["level"]]}" '
            f'style="animation-delay:{delay:.3f}s"><title>{current}: {count:,} contribution{plural}</title></rect>'
        )
    parts.append('<path d="M24 207H836" stroke="#30363d"/>')
    stats = f'{total:,} contributions   ·   {data["active_days"]} active days   ·   {data["longest_streak"]}-day longest streak'
    parts.append(f'<text x="24" y="231" font-size="12" fill="#e6edf3">{stats}</text>')
    parts.append('<text x="699" y="231" font-size="10" fill="#8b949e">Less</text>')
    for level, color in enumerate(COLORS):
        parts.append(f'<rect x="{729 + level * 12}" y="222" width="9" height="9" rx="2" fill="{color}"/>')
    parts.append('<text x="794" y="231" font-size="10" fill="#8b949e">More</text>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def fetch_html(username: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", username) is None:
        raise CalendarError("Username must be a valid GitHub login")
    request = Request(
        f"https://github.com/users/{username}/contributions",
        headers={"User-Agent": "github-profile-calendar/1.0", "Accept-Language": "en-US,en;q=0.9"},
    )
    with urlopen(request, timeout=30) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise CalendarError("Contribution response exceeded the expected size")
    return raw.decode("utf-8")


def refresh(username: str, root: Path = ROOT) -> dict:
    # Complete fetching, parsing, validation, and rendering before touching output.
    days = parse_calendar(fetch_html(username))
    data = summarize(username, days)
    payloads = {
        root / "data" / "contributions.json": json.dumps(data, indent=2) + "\n",
        root / "assets" / "contrib-heatmap.svg": render_svg(data),
    }
    staged: list[tuple[Path, Path]] = []
    try:
        for destination, content in payloads.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=destination.parent, delete=False) as handle:
                temporary = Path(handle.name)
                staged.append((temporary, destination))
                handle.write(content)
        for temporary, destination in staged:
            os.replace(temporary, destination)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="oliBrowne")
    args = parser.parse_args()
    try:
        data = refresh(args.username)
    except (OSError, ValueError) as exc:
        print(f"Calendar refresh failed: {exc}", file=sys.stderr)
        return 1
    print(f"Updated {args.username}: {data['total_contributions']} contributions over {len(data['days'])} observed days.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

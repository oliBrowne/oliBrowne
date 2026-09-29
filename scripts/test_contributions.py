"""Focused tests for source integrity, calendar placement, and safe refreshes."""

from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import contributions


def fragment(rows):
    parts = []
    for index, (day, count, level) in enumerate(rows):
        tooltip = f"{count:,} contributions on September 28th." if count else "No contributions on September 28th."
        parts.append(f'<td id="day-{index}" data-date="{day}" data-level="{level}"></td><tool-tip for="day-{index}">{tooltip}</tool-tip>')
    return "".join(parts)


class CalendarTests(unittest.TestCase):
    def test_weekday_order_and_comma_counts_are_parsed_exactly(self):
        html = fragment([("2026-09-29", 1200, 4), ("2026-09-27", 0, 0), ("2026-09-28", 1, 1)])
        days = contributions.parse_calendar(html, today=date(2026, 9, 29), min_days=3)
        self.assertEqual([day["count"] for day in days], [0, 1, 1200])
        stats = contributions.summarize("oliBrowne", days)
        self.assertEqual((stats["total_contributions"], stats["active_days"], stats["longest_streak"]), (1201, 2, 2))

    def test_missing_unknown_and_inconsistent_counts_are_rejected(self):
        good = fragment([("2026-09-29", 1, 1)])
        invalid = [
            good.split("<tool-tip")[0],
            good.replace("1 contributions on September 28th.", "Contribution data unavailable"),
            good.replace('data-level="1"', 'data-level="0"'),
        ]
        for html in invalid:
            with self.subTest(html=html), self.assertRaises(contributions.CalendarError):
                contributions.parse_calendar(html, today=date(2026, 9, 29), min_days=1)

    def test_duplicate_gapped_short_stale_and_future_calendars_are_rejected(self):
        invalid = [
            [("2026-09-29", 0, 0), ("2026-09-29", 0, 0)],
            [("2026-09-27", 0, 0), ("2026-09-29", 0, 0)],
            [("2026-09-26", 0, 0)],
            [("2026-09-30", 0, 0)],
        ]
        for rows in invalid:
            with self.subTest(rows=rows), self.assertRaises(contributions.CalendarError):
                contributions.parse_calendar(fragment(rows), today=date(2026, 9, 29), min_days=1)
        with self.assertRaises(contributions.CalendarError):
            contributions.parse_calendar(fragment([("2026-09-29", 0, 0)]), today=date(2026, 9, 29))

    def test_streak_is_bounded_by_observed_days_and_breaks_on_zero(self):
        days = [{"date": f"2026-09-{23 + index}", "count": count, "level": int(count > 0)} for index, count in enumerate([1, 1, 1, 0, 1, 1, 0])]
        stats = contributions.summarize("oliBrowne", days)
        self.assertEqual(stats["longest_streak"], 3)
        self.assertEqual(stats["active_days"], 5)
        self.assertEqual(stats["range"], {"start": "2026-09-23", "end": "2026-09-29"})

    def test_sunday_starts_new_column_and_svg_remains_visible_without_animation(self):
        days = contributions.parse_calendar(fragment([("2026-09-26", 0, 0), ("2026-09-27", 1, 1), ("2026-09-28", 2, 2)]), today=date(2026, 9, 29), min_days=3)
        svg = contributions.render_svg(contributions.summarize("oliBrowne", days))
        root = ET.fromstring(svg)
        rects = [element for element in root.iter() if element.get("class") == "day"]
        self.assertEqual([(rect.get("x"), rect.get("y")) for rect in rects], [("74", "176"), ("88", "92"), ("88", "106")])
        self.assertIn(".day{opacity:1", svg)
        self.assertIn("prefers-reduced-motion:reduce", svg)
        self.assertNotIn("<script", svg)

    def test_invalid_live_response_does_not_replace_either_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = [root / "data" / "contributions.json", root / "assets" / "contrib-heatmap.svg"]
            for destination in files:
                destination.parent.mkdir()
                destination.write_text("previous valid artifact", encoding="utf-8")
            with patch.object(contributions, "fetch_html", return_value="<html>Try again later</html>"):
                with self.assertRaises(contributions.CalendarError):
                    contributions.refresh("oliBrowne", root)
            for destination in files:
                self.assertEqual(destination.read_text(encoding="utf-8"), "previous valid artifact")


if __name__ == "__main__":
    unittest.main()

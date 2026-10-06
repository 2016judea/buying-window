"""The page prints counts straight from site/data; these check the data agrees with itself."""
import csv
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "site" / "data"
D = json.loads((DATA / "events.json").read_text())


def matches(t, e):
    return any(e["event"] == ev and (not segs or e["segment"] in segs) for ev, segs in t["triggers"])


def test_every_trade_has_rows_and_its_csv_agrees():
    assert len(D["trades"]) >= 3
    for t in D["trades"]:
        rows = [e for e in D["events"] if matches(t, e)]
        assert rows and t["count"] == len(rows), t["slug"]
        with open(DATA / f"{t['slug']}.csv") as f:
            assert sum(1 for _ in csv.reader(f)) - 1 == len(rows), t["slug"]


def test_every_event_links_to_its_record():
    for e in D["events"]:
        assert e["source_url"].startswith("https://"), e
        assert e["date"] and e["stage"] and (e["name"] or e["address"]), e


def test_counts_are_the_events():
    for k, n in D["counts"].items():
        assert n == sum(e["event"] == k for e in D["events"])

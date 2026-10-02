"""Compare /rchg snapshots against /fchg for the same station.

Checks: (1) size, (2) is rchg a subset of fchg, (3) same stop -> same content,
(4) overlap between consecutive rchg snapshots. Then prints one differing
stop side by side as a unified diff.

Run with: uv run scripts/compare_chg.py
"""

from __future__ import annotations

import difflib
from pathlib import Path

from lxml import etree

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
TARGET_EVAS = ("8000261", "8003092")  # München Hbf, Ismaning

# remove_blank_text drops indentation whitespace, so two identical stops
# serialize identically no matter where they sit in the file.
PARSER = etree.XMLParser(remove_blank_text=True)


def snapshots(kind: str, eva: str) -> list[Path]:
    """Files named {kind}_{eva}_{HHMMSS}.xml, oldest first.

    Requiring the timestamp part skips old un-timestamped fixtures
    like fchg_{eva}.xml, which would silently be stale data.
    """
    paths = FIXTURES_DIR.glob(f"{kind}_{eva}_*.xml")
    return sorted(paths, key=lambda p: p.stem.split("_")[2])


def load_stops(path: Path) -> dict[str, etree._Element]:
    root = etree.parse(path, PARSER).getroot()
    return {s.get("id"): s for s in root.iter("s")}


def canonical(stop: etree._Element) -> bytes:
    return etree.tostring(stop, with_tail=False)


def pretty(stop: etree._Element) -> list[str]:
    return etree.tostring(stop, pretty_print=True, with_tail=False).decode().splitlines()


def split_same_diff(a: dict, b: dict) -> tuple[list[str], list[str]]:
    """Stop ids present in both dicts, split by identical vs different content."""
    same, diff = [], []
    for stop_id in a.keys() & b.keys():
        (same if canonical(a[stop_id]) == canonical(b[stop_id]) else diff).append(stop_id)
    return same, diff


def show_diff(stop_id: str, rchg_stop, fchg_stop) -> None:
    print(f"\nStop {stop_id}: rchg (-) vs fchg (+)")
    lines = difflib.unified_diff(
        pretty(rchg_stop), pretty(fchg_stop), "rchg", "fchg", lineterm="", n=2
    )
    print("\n".join(lines))


def compare_station(eva: str) -> None:
    print(f"\n{'=' * 10} EVA {eva} {'=' * 10}")
    rchg = {p.stem.split("_")[2]: load_stops(p) for p in snapshots("rchg", eva)}
    fchg_paths = snapshots("fchg", eva)
    if not rchg or not fchg_paths:
        print("missing rchg or fchg snapshots, skipping")
        return
    fchg = load_stops(fchg_paths[-1])  # newest full snapshot

    print("Check 1: size (stops)")
    for ts, stops in rchg.items():
        print(f"  rchg {ts}: {len(stops)}")
    print(f"  fchg {fchg_paths[-1].stem.split('_')[2]}: {len(fchg)}")

    print("Check 2: rchg ids missing from fchg")
    for ts, stops in rchg.items():
        print(f"  rchg {ts}: {len(stops.keys() - fchg.keys())}")

    print("Check 3: same stop, same content as fchg")
    first_diff = None
    for ts, stops in rchg.items():
        same, diff = split_same_diff(stops, fchg)
        print(f"  rchg {ts}: same={len(same)} different={len(diff)}")
        if diff and first_diff is None:
            first_diff = (diff[0], stops[diff[0]])

    print("Check 4: overlap between consecutive rchg snapshots")
    items = list(rchg.items())
    for (ts_a, a), (ts_b, b) in zip(items, items[1:]):
        print(
            f"  {ts_a} -> {ts_b}: in both={len(a.keys() & b.keys())} "
            f"new={len(b.keys() - a.keys())} dropped={len(a.keys() - b.keys())}"
        )

    if first_diff:
        stop_id, rchg_stop = first_diff
        show_diff(stop_id, rchg_stop, fchg[stop_id])


def main() -> None:
    for eva in TARGET_EVAS:
        compare_station(eva)


if __name__ == "__main__":
    main()

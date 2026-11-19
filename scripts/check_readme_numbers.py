"""Fail if a number in README.md is not in results/summary.json.

Every number in the README text (code blocks excluded) must match a value of the summary
file at some rounding (0, 1 or 2 decimals, or as a percentage of a share), or be one of
the model inputs listed in INPUTS below with the reason it is an input.

Usage: python scripts/check_readme_numbers.py [README] [summary.json]
Exit code 1 and a list of the numbers that were not found.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# numbers that are inputs or names, not results
INPUTS = {
    "62386": "standard number",
    "1200": "bit rate, source S1",
    "64": "short addresses / gear in the studies",
    "16": "groups",
    "8": "smallest installation, gear in the stagger table",
    "4": "evidence levels; gear count in the mains study",
    "2": "two causes / two in the delay formula / DALI-2 / 2 gear",
    "1": "one gear / 1 s slot",
    "0": "zero",
    "10": "ten faults; 10 V threshold, source S8",
    "20": "20 drivers (hardware plan); 20 ms order threshold, assumption",
    "30": "minutes of operation per run (A13)",
    "60": "runs per class; 60 s off period",
    "50": "traffic share in the delay study",
    "90": "traffic share in the delay study",
    "100": "percent; 100 ms visibility threshold (assumption); 100 m table row",
    "300": "s off period in the mains study",
    "0.2": "slot time in the delay study",
    "0.5": "mm2 conductor, source S2",
    "0.6": "noise, assumption A5",
    "1.0": "noise sensitivity",
    "4.5": "gateway low threshold, source S8",
    "9.5": "gear high threshold, source S8",
    "6.5": "gear low threshold, source S8",
    "2.45": "stop condition, source S1",
    "5.5": "backward window start, source S1",
    "10.5": "backward window end, source S1",
    "250": "maximum supply current, source S7",
}


def renderings(v) -> set[str]:
    out = set()
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return out
    for x in (v, 100 * v) if abs(v) <= 1.0 else (v,):
        for nd in (0, 1, 2):
            s = f"{x:.{nd}f}"
            out.add(s)
            if "." in s:
                out.add(s.rstrip("0").rstrip("."))
    return out


def walk(d, acc):
    if isinstance(d, dict):
        for v in d.values():
            walk(v, acc)
    elif isinstance(d, list):
        for v in d:
            walk(v, acc)
    else:
        acc |= renderings(d)
    return acc


def readme_numbers(text: str) -> list[str]:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"\(results/[^)]*\)|\(docs/[^)]*\)|`[^`]*`", "", text)
    text = re.sub(r"\b[A-Z]{1,4}\d+\b", "", text)          # ids such as E1, A5, S8, T7
    text = re.sub(r"DALI-2|DT\d|mm2|p99", "", text)
    return re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])", text)


def check(readme: Path, summary: Path) -> list[str]:
    known = walk(json.loads(summary.read_text(encoding="utf-8")), set())
    missing = []
    for n in readme_numbers(readme.read_text(encoding="utf-8")):
        if n in known or n in INPUTS:
            continue
        missing.append(n)
    return missing


def main():
    readme = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "README.md"
    summary = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "results" / "summary.json"
    missing = check(readme, summary)
    if missing:
        print("README numbers not found in summary.json:", sorted(set(missing)))
        sys.exit(1)
    print(f"all README numbers found in {summary.name}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate a generated reputation report before delivery."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("html")
    args = parser.parse_args()
    path = Path(args.html)
    if not path.exists() or path.stat().st_size < 20_000:
        sys.exit("report missing or suspiciously small")
    text = path.read_text(encoding="utf-8")
    match = re.search(r'<script id="report-data" type="application/json">(.*?)</script>', text, re.S)
    if not match:
        sys.exit("report-data block not found")
    data = json.loads(match.group(1))
    problems = []
    if not data.get("periods"):
        problems.append("no periods")
    if len(data.get("brands", [])) < 2:
        problems.append("fewer than 2 brands")
    for layer in data.get("layers", []):
        for brand in data.get("brands", []):
            values = (data.get("series", {}).get(layer) or {}).get(brand["key"])
            if not values or len(values) != len(data["periods"]):
                problems.append(f"series length mismatch: {layer}/{brand['name']}")
    own = next((b for b in data.get("brands", []) if b.get("own")), None)
    if not own:
        problems.append("no own brand")
    else:
        for layer in data.get("layers", []):
            total = sum((data.get("series", {}).get(layer, {}).get(own["key"]) or [[0, 0, 0]])[-1])
            if total == 0:
                problems.append(f"target has no samples in {layer}")
    copy = data.get("copy") or {}
    for key in ("summary", "insights", "kpiPosLabel", "kpiNegLabel", "kpiCatPosLabel", "kpiCatNegLabel"):
        if not copy.get(key):
            problems.append(f"missing copy: {key}")
    if "NaN" in text or "undefined" in text:
        problems.append("report contains NaN/undefined")
    print(json.dumps({
        "html": str(path), "periods": len(data.get("periods", [])),
        "brands": [b["name"] for b in data.get("brands", [])],
        "layers": data.get("layers"), "problems": problems,
    }, ensure_ascii=False, indent=2))
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()

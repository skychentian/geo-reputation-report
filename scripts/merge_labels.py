#!/usr/bin/env python3
"""Merge batch label files into labels.json and validate coverage."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VALID = {"正向", "中性", "负向", "无法判断"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge *.labels.json files")
    parser.add_argument("answers", help="answers.json")
    parser.add_argument("labels_dir", help="directory containing *.labels.json")
    parser.add_argument("--out", default=None, help="default <labels_dir>/labels.json")
    args = parser.parse_args()

    source = json.loads(Path(args.answers).read_text(encoding="utf-8"))
    meta = source["meta"]
    competitors = set(meta["competitors"])
    expected = {a["id"] for a in source["answers"]}
    by_id = {}
    for path in sorted(Path(args.labels_dir).glob("*.labels.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("labels", []):
            answer_id = str(item.get("id"))
            if answer_id not in expected:
                sys.exit(f"{path.name}: unexpected id {answer_id}")
            if answer_id in by_id:
                sys.exit(f"{path.name}: duplicate id {answer_id}")
            target = item.get("target") or {}
            if target.get("sentiment") not in VALID:
                sys.exit(f"{path.name}/{answer_id}: invalid target sentiment")
            for name, value in (item.get("competitors") or {}).items():
                if name not in competitors:
                    sys.exit(f"{path.name}/{answer_id}: unknown competitor {name}")
                if (value or {}).get("sentiment") not in VALID:
                    sys.exit(f"{path.name}/{answer_id}/{name}: invalid sentiment")
            by_id[answer_id] = item
    missing = sorted(expected - set(by_id))
    out = Path(args.out) if args.out else Path(args.labels_dir) / "labels.json"
    out.write_text(json.dumps({
        "target": meta["targetBrand"], "competitors": meta["competitors"],
        "coverage": {"expected": len(expected), "labeled": len(by_id), "missing": len(missing)},
        "byId": by_id,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out), "labeled": len(by_id), "expected": len(expected), "missing": len(missing)}, ensure_ascii=False))
    if missing:
        print(json.dumps(missing[:10], ensure_ascii=False))
        sys.exit(2)


if __name__ == "__main__":
    main()

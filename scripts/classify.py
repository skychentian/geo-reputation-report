#!/usr/bin/env python3
"""Batch-classify answer stance toward the target brand and competitors.

Backends:
  claude  Use the local `claude -p` CLI (default if available).
  openai  OpenAI-compatible chat completions via LLM_BASE_URL/LLM_API_KEY/LLM_MODEL.
  none    Only write batch files; a human/agent classifies them.

Outputs one JSON file per batch under <out>/batches and a combined labels.json.
The classifier is cached by batch content; use --force to rerun.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def read_prompt_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def json_from_text(text: str) -> dict:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z]*\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    start = value.find("{")
    end = value.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("classifier did not return a JSON object")
    return json.loads(value[start:end + 1])


def validate_labels(payload: dict, expected_ids: list[str], competitors: list[str]) -> list[dict]:
    labels = payload.get("labels")
    if not isinstance(labels, list):
        raise ValueError("missing labels array")
    allowed = {"正向", "中性", "负向", "无法判断"}
    seen = set()
    for item in labels:
        answer_id = str(item.get("id"))
        if answer_id not in expected_ids:
            raise ValueError(f"unexpected answer id in labels: {answer_id}")
        target = item.get("target") or {}
        if target.get("sentiment") not in allowed:
            raise ValueError(f"invalid target sentiment for {answer_id}")
        comps = item.get("competitors") or {}
        if not isinstance(comps, dict):
            raise ValueError(f"competitors must be an object for {answer_id}")
        for name, value in comps.items():
            if name not in competitors:
                raise ValueError(f"unknown competitor {name} for {answer_id}")
            if (value or {}).get("sentiment") not in allowed:
                raise ValueError(f"invalid competitor sentiment for {answer_id}/{name}")
        seen.add(answer_id)
    missing = [x for x in expected_ids if x not in seen]
    if missing:
        raise ValueError(f"missing labels for {len(missing)} answers, e.g. {missing[:3]}")
    return labels


def call_claude(prompt: str) -> str:
    proc = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=420)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:300]}")
    return proc.stdout


def call_openai(prompt: str, model: str) -> str:
    base = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
    key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("LLM_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY is not set")
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(base + "/chat/completions", data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=420) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload["choices"][0]["message"]["content"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify answer stance in batches")
    parser.add_argument("answers", help="answers.json from extract_answers.py")
    parser.add_argument("--out", default="work/labels")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--backend", choices=["claude", "openai", "none"], default=None)
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL", "deepseek-chat"))
    parser.add_argument("--prompt", default=str(Path(__file__).resolve().parent.parent / "references" / "classification-prompt.md"))
    parser.add_argument("--limit", type=int, default=0, help="test with the first N answers")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    source = json.loads(Path(args.answers).read_text(encoding="utf-8"))
    meta = source["meta"]
    answers = source["answers"][:args.limit] if args.limit else source["answers"]
    target = meta["targetBrand"]
    competitors = meta["competitors"]
    template = read_prompt_template(Path(args.prompt))

    out_dir = Path(args.out).expanduser().resolve()
    batch_dir = out_dir / "batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    backend = args.backend
    if backend is None:
        backend = "claude" if shutil.which("claude") else ("openai" if (os.environ.get("LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")) else "none")

    batches = []
    for i, group in enumerate(chunks(answers, max(1, args.batch_size)), 1):
        batch = {
            "id": f"batch-{i:03d}",
            "answers": [{
                "id": a["id"], "question": a["question"], "platform": a["platform"], "text": a["text"],
            } for a in group],
        }
        raw = json.dumps(batch["answers"], ensure_ascii=False, sort_keys=True)
        batch["hash"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        batches.append(batch)
        (batch_dir / f"{batch['id']}.json").write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")

    if backend == "none":
        (out_dir / "HOW-TO-CLASSIFY.md").write_text(
            "# 分类批次已生成\n\n"
            "请用 references/classification-prompt.md 的规则逐批判定，"
            "把结果写成 {batch-id}.labels.json，结构与 prompt 中的输出结构一致，"
            "然后运行 merge_labels.py。\n", encoding="utf-8")
        print(f"wrote {len(batches)} batches to {batch_dir}; backend=none")
        return

    def run_one(batch: dict) -> tuple[str, list[dict]]:
        label_path = out_dir / f"{batch['id']}.labels.json"
        if label_path.exists() and not args.force:
            payload = json.loads(label_path.read_text(encoding="utf-8"))
            return batch["id"], payload["labels"]
        prompt = (template
                  .replace("{target}", target)
                  .replace("{competitors}", "、".join(competitors))
                  .replace("{first_competitor}", competitors[0] if competitors else "竞品")
                  .replace("{answers_json}", json.dumps(batch["answers"], ensure_ascii=False, indent=1)))
        last_error = None
        for attempt in range(3):
            try:
                text = call_claude(prompt) if backend == "claude" else call_openai(prompt, args.model)
                payload = json_from_text(text)
                labels = validate_labels(payload, [a["id"] for a in batch["answers"]], competitors)
                label_path.write_text(json.dumps({"labels": labels}, ensure_ascii=False, indent=2), encoding="utf-8")
                return batch["id"], labels
            except Exception as exc:  # retry transient CLI/JSON failures
                last_error = exc
        raise RuntimeError(f"{batch['id']} failed after retries: {last_error}")

    combined = []
    failures = []
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        future_map = {pool.submit(run_one, batch): batch["id"] for batch in batches}
        for done, future in enumerate(as_completed(future_map), 1):
            batch_id = future_map[future]
            try:
                _, labels = future.result()
                combined.extend(labels)
                print(f"[{done}/{len(batches)}] {batch_id}: {len(labels)} labels")
            except Exception as exc:
                failures.append((batch_id, str(exc)))
                print(f"[{done}/{len(batches)}] {batch_id}: FAILED {exc}", file=sys.stderr)

    by_id = {str(item["id"]): item for item in combined}
    expected = {a["id"] for a in answers}
    missing = sorted(expected - set(by_id))
    (out_dir / "labels.json").write_text(json.dumps({
        "target": target, "competitors": competitors,
        "coverage": {"expected": len(expected), "labeled": len(by_id), "missing": len(missing)},
        "byId": by_id,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"labels": len(by_id), "expected": len(expected), "missing": len(missing), "failures": failures}, ensure_ascii=False, indent=2))
    if failures or missing:
        sys.exit(2)


if __name__ == "__main__":
    main()

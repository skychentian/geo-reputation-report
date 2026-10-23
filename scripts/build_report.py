#!/usr/bin/env python3
"""Aggregate classified answers into the reputation report HTML.

Inputs:
  answers.json  normalized by extract_answers.py
  labels.json   byId labels produced by classify.py / merge_labels.py

The history file accumulates one snapshot per period. Re-running the same
period replaces that snapshot instead of appending a duplicate.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PALETTE = ["#14684b", "#c08a2e", "#b45a3c", "#4f6d9a", "#7a5c9e", "#2f7f8f", "#8a6b4f"]
VALID = {"正向", "中性", "负向"}


def sentiment(label: dict, brand: str, target: str) -> str | None:
    if not label:
        return None
    if brand == target:
        value = (label.get("target") or {}).get("sentiment")
    else:
        value = ((label.get("competitors") or {}).get(brand) or {}).get("sentiment")
    return value if value in VALID else None


def count_answers(answers: list[dict], by_id: dict, target: str, brands: list[str]):
    series = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    unclear = defaultdict(lambda: defaultdict(int))
    platform_counts = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    for answer in answers:
        label = by_id.get(answer["id"])
        layer = answer["layer"]
        platform = answer["platform"]
        for brand in brands:
            value = sentiment(label, brand, target)
            if value is None:
                continue
            idx = {"正向": 0, "中性": 1, "负向": 2}[value]
            series[layer][brand][idx] += 1
            platform_counts[platform][brand][idx] += 1
        if label and (label.get("target") or {}).get("sentiment") == "无法判断":
            unclear[answer["layer"]][target] += 1
    return series, unclear, platform_counts


def rates(counts: list[int]) -> list[float]:
    total = sum(counts)
    if not total:
        return [0.0, 0.0, 0.0]
    return [round(counts[0] / total * 100, 1), round(counts[1] / total * 100, 1), round(counts[2] / total * 100, 1)]


def pct_rate(counts: list[int], index: int) -> float:
    total = sum(counts)
    return round(counts[index] / total * 100, 1) if total else 0.0


def direction(delta: float, good_when_down: bool = True):
    if abs(delta) < 0.05:
        return "持平", "flat", "→"
    if good_when_down:
        word = "下降" if delta < 0 else "上升"
        tone = "good" if delta < 0 else "bad"
    else:
        word = "上升" if delta > 0 else "下降"
        tone = "good" if delta > 0 else "bad"
    return word, tone, ("↓" if delta < 0 else "↑")


def gap_word(delta: float):
    if abs(delta) < 0.05:
        return "持平"
    return "收窄" if delta < 0 else "扩大"


def delta_html(current, first, good_when_down):
    delta = round(current - first, 1)
    if abs(delta) < 0.05:
        return '<span class="delta flat">→ 0.0</span> 较首期'
    tone = ('good' if delta < 0 else 'bad') if good_when_down else ('good' if delta > 0 else 'bad')
    arrow = '↓' if delta < 0 else '↑'
    return f'<span class="delta {tone}">{arrow} {abs(delta)}pp</span> 较首期'


def build_copy(meta, periods, series, brands, target, reference):
    L0, L1 = meta["layers"][0], meta["layers"][-1]
    own = target
    ref = reference
    last = periods[-1]
    first = periods[0]
    cur = series[L0][own][-1]
    first_counts = series[L0][own][0]
    ref_counts = series[L0][ref][-1]
    ref_first = series[L0][ref][0]
    cat_counts = series[L1][own][-1]
    first_cat_counts = series[L1][own][0]
    cur_neg = pct_rate(cur, 2)
    first_neg = pct_rate(first_counts, 2)
    ref_neg = pct_rate(ref_counts, 2)
    ref_first_neg = pct_rate(ref_first, 2)
    gap = round(cur_neg - ref_neg, 1)
    first_gap = round(first_neg - ref_first_neg, 1)
    cat_neg = pct_rate(cat_counts, 2)
    cat_pos = pct_rate(cat_counts, 0)
    pos_cur = pct_rate(cur, 0)
    pos_first = pct_rate(first_counts, 0)
    first_cat_pos = pct_rate(first_cat_counts, 0)
    first_cat_neg = pct_rate(first_cat_counts, 2)
    zero_streak = 0
    for period in reversed(periods):
        counts = series[L1][own][periods.index(period)]
        if sum(counts) > 0 and counts[2] == 0:
            zero_streak += 1
        else:
            break

    if len(periods) == 1:
        summary = (f"本期{own}{L0}负面率 <b>{cur_neg}%</b>，{ref} <b>{ref_neg}%</b>；"
                   f"{L1}负面率 <b>{cat_neg}%</b>。竞品为提及样本；首期数据，后续按期累积。")
        kpi_pos_sub = "首期数据"
        kpi_neg_sub = "首期数据"
        kpi_cat_pos_sub = "首期数据"
        kpi_cat_neg_sub = "首期数据"
        insight_neg = f"本期{L0}负面率 {cur_neg}%；{L1}负面率 {cat_neg}%。首期数据，后续按期累积后展示变化。"
        insight_pos = f"本期{L0}正面率 {pos_cur}%；{L1}正面率 {cat_pos}%。首期数据，后续按期累积后展示变化。"
    else:
        own_delta = round(cur_neg - first_neg, 1)
        own_word, own_tone, own_arrow = direction(own_delta, good_when_down=True)
        gap_delta = round(gap - first_gap, 1)
        if abs(own_delta) < 0.05:
            summary = f"{own}{L0}负面率 <b>{cur_neg}%</b>，与首期（{first}）持平；"
        else:
            summary = (f"{own}{L0}负面率 <b>{cur_neg}%</b>，较首期（{first}）{own_word} "
                       f"<b>{abs(own_delta)}pp</b>；")
        if abs(gap_delta) < 0.05:
            summary += f"与{ref}差距保持 <b>{gap}pp</b>。"
        else:
            summary += f"与{ref}差距从 <b>{first_gap}pp</b> {gap_word(gap_delta)}到 <b>{gap}pp</b>。"
        if zero_streak > 1:
            summary += f"{L1}已连续 <b>{zero_streak} 期</b>无负面。"
        summary += "竞品为提及样本。"
        kpi_pos_sub = delta_html(pos_cur, pos_first, good_when_down=False)
        kpi_neg_sub = delta_html(cur_neg, first_neg, good_when_down=True)
        kpi_cat_pos_sub = delta_html(cat_pos, first_cat_pos, good_when_down=False)
        kpi_cat_neg_sub = delta_html(cat_neg, first_cat_neg, good_when_down=True)
        cat_text = (f"{L1}已连续 {zero_streak} 期无负面" if zero_streak > 1
                    else f"{L1}本期负面率 {cat_neg}%")
        if abs(own_delta) < 0.05:
            lead = f"{L0}负面率与首期持平，为 <b>{cur_neg}%</b>；"
        else:
            lead = f"{L0}负面率从 <b>{first_neg}%</b> 变为 <b>{cur_neg}%</b>；"
        if abs(gap_delta) < 0.05:
            gap_text = f"与{ref}差距保持 <b>{gap}pp</b>"
        else:
            gap_text = f"与{ref}差距由 <b>{first_gap}pp</b> {gap_word(gap_delta)}到 <b>{gap}pp</b>"
        insight_neg = f"{lead}{gap_text}；{cat_text}。"
        insight_pos = (f"{L0}正面率从 <b>{pos_first}%</b> 变为 <b>{pos_cur}%</b>，{ref}最新 <b>"
                       f"{pct_rate(ref_counts, 0)}%</b>；{L1}正面率 <b>{cat_pos}%</b>。")

    layer_hints = {}
    for layer in meta["layers"]:
        target_total = sum(series[layer][own][-1])
        comp_totals = [sum(series[layer][b][-1]) for b in brands if b != own]
        low = min(comp_totals) if comp_totals else 0
        layer_hints[layer] = (f"{layer} · 目标 {target_total} 条 · 竞品提及样本" +
                              ("不足 20，仅供参考" if low < 20 else ""))

    return {
        "summary": summary,
        "kpiPosLabel": f"{L0} · 正面率",
        "kpiPosSub": kpi_pos_sub,
        "kpiNegLabel": f"{L0} · 负面率",
        "kpiNegSub": kpi_neg_sub,
        "kpiCatPosLabel": f"{L1} · 正面率",
        "kpiCatPosSub": kpi_cat_pos_sub,
        "kpiCatNegLabel": f"{L1} · 负面率",
        "kpiCatNegSub": kpi_cat_neg_sub,
        "layerHints": layer_hints,
        "insights": {"neg": insight_neg, "pos": insight_pos},
        "comparisonNote": "pp 为百分点；中性计入严格非正向风险，但不冲抵正负。竞品为回答中提及样本，样本量见各行。",
        "platformNote": "每平台目标品牌全量回答；竞品为提及样本，低样本仅作参考。",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build reputation report HTML")
    parser.add_argument("--answers", required=True)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--out", default="output")
    parser.add_argument("--history", default=None)
    parser.add_argument("--reference-brand", default=None)
    parser.add_argument("--template", default=str(Path(__file__).resolve().parent.parent / "assets" / "report-template.html"))
    parser.add_argument("--reset-history", action="store_true")
    args = parser.parse_args()

    source = json.loads(Path(args.answers).read_text(encoding="utf-8"))
    labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    by_id = labels.get("byId") or {}
    meta = source["meta"]
    answers = source["answers"]
    target = meta["targetBrand"]
    competitors = meta["competitors"]
    brand_names = [target] + competitors
    missing = [a["id"] for a in answers if a["id"] not in by_id]
    if missing:
        sys.exit(f"labels missing for {len(missing)} answers, e.g. {missing[:3]}")
    if not all(a["layer"] in meta["layers"] for a in answers):
        sys.exit("answers contain a layer not present in meta.layers")

    series_counts, unclear, platform_counts = count_answers(answers, by_id, target, brand_names)
    if sum(series_counts[meta["layers"][0]][target]) == 0:
        sys.exit("no valid labels for target brand")

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    history_path = Path(args.history).expanduser().resolve() if args.history else out_dir / "history.json"
    if history_path.exists() and not args.reset_history:
        history = json.loads(history_path.read_text(encoding="utf-8"))
    else:
        history = {"periods": []}
    period_entry = {
        "date": meta["period"],
        "label": meta["periodLabel"],
        "answerCount": len(answers),
        "platformCount": len(meta["platforms"]),
        "series": {layer: {brand: series_counts[layer][brand] for brand in brand_names} for layer in meta["layers"]},
        "platforms": {platform: {brand: rates(platform_counts[platform][brand]) for brand in brand_names}
                      for platform in meta["platforms"]},
        "unclear": {layer: unclear[layer][target] for layer in meta["layers"]},
    }
    history["periods"] = [p for p in history["periods"] if p.get("date") != meta["period"]]
    history["periods"].append(period_entry)
    history["periods"].sort(key=lambda p: p["date"])

    periods = history["periods"]
    period_labels = [p["label"] for p in periods]
    all_series = {}
    for layer in meta["layers"]:
        all_series[layer] = {}
        for brand in brand_names:
            all_series[layer][brand] = [p.get("series", {}).get(layer, {}).get(brand, [0, 0, 0]) for p in periods]

    brand_keys = [f"b{i}" for i in range(len(brand_names))]
    brands = [{"key": brand_keys[0], "name": target, "color": PALETTE[0], "own": True}]
    for i, name in enumerate(competitors, 1):
        brands.append({"key": brand_keys[i], "name": name, "color": PALETTE[i % len(PALETTE)]})
    reference_name = args.reference_brand if args.reference_brand in competitors else competitors[0]
    reference_key = brand_keys[brand_names.index(reference_name)]

    copy = build_copy(
        {"layers": meta["layers"]}, period_labels,
        {layer: {brand: [p["series"][layer][brand] for p in periods] for brand in brand_names} for layer in meta["layers"]},
        brand_names, target, reference_name)
    low_sample = {}
    for layer in meta["layers"]:
        low_sample[layer] = [brand_keys[brand_names.index(name)] for name in competitors
                             if sum(series_counts[layer][name]) < 20]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    data = {
        "meta": {
            "title": f"{meta['brandLine']} AI 美誉度对比分析",
            "brandLine": meta["brandLine"],
            "asOf": meta["period"],
            "issue": len(periods),
            "cadence": "周更",
            "referenceBrand": reference_key,
            "layerNames": meta["layers"],
            "demo": False,
            "generatedAt": now,
            "answerCount": len(answers),
            "questionCount": meta["questionCount"],
            "platformCount": len(meta["platforms"]),
            "sampleNote": "目标品牌全量回答；竞品为回答中提及样本。",
            "minSample": 20,
            "lowSample": low_sample,
        },
        "brands": brands,
        "layers": meta["layers"],
        "periods": [{"date": p["date"], "label": p["label"]} for p in periods],
        "series": {layer: {brand_keys[brand_names.index(name)]: all_series[layer][name] for name in brand_names}
                   for layer in meta["layers"]},
        "platforms": {
            "order": meta["platforms"],
            "rates": {platform: {brand_keys[brand_names.index(brand)]: rates(platform_counts[platform][brand])
                                for brand in brand_names}
                      for platform in meta["platforms"]},
        },
        "copy": copy,
    }

    template = Path(args.template).read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, indent=2).replace("</script>", "<\\/script>")
    pattern = re.compile(r'<script id="report-data" type="application/json">.*?</script>', re.S)
    if not pattern.search(template):
        sys.exit("template has no report-data script block")
    html = pattern.sub('<script id="report-data" type="application/json">\n' + payload + '\n</script>', template, count=1)
    html_path = out_dir / "reputation-report.html"
    html_path.write_text(html, encoding="utf-8")
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "snapshot.json").write_text(json.dumps(period_entry, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "html": str(html_path),
        "history": str(history_path),
        "periods": len(periods),
        "brands": brand_names,
        "reference": reference_name,
        "layers": meta["layers"],
        "target_counts": {layer: all_series[layer][target][-1] for layer in meta["layers"]},
        "competitor_counts": {layer: {b: all_series[layer][b][-1] for b in competitors} for layer in meta["layers"]},
        "unclear": period_entry["unclear"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

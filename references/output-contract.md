# 输出契约

## answers.json

```json
{
  "meta": {
    "targetBrand": "品牌 A",
    "competitors": ["品牌 B", "品牌 C"],
    "brandLine": "品牌 A · 品牌 B · 品牌 C",
    "period": "2026-10-15",
    "periodLabel": "10/15",
    "questionCount": 100,
    "answerCount": 600,
    "platforms": ["豆包", "DeepSeek", "..."],
    "layers": ["品牌整体", "食用油"],
    "layerCounts": {"品牌整体": 348, "食用油": 252},
    "unmappedTopics": {}
  },
  "answers": [
    {"id": "2026-10-15-1", "index": 1, "question": "...", "topic": "行业地位", "layer": "品牌整体", "platform": "豆包", "text": "..."}
  ]
}
```

## labels.json

```json
{
  "target": "品牌 A",
  "competitors": ["品牌 B", "品牌 C"],
  "coverage": {"expected": 600, "labeled": 600, "missing": 0},
  "byId": {
    "2026-10-15-1": {
      "target": {"sentiment": "正向", "reason": "...", "evidence": "..."},
      "competitors": {"品牌 C": {"sentiment": "中性", "reason": "...", "evidence": "..."}}
    }
  }
}
```

`byId` 的键必须和 `answers[].id` 一一对应；缺一条就不要生成报告。

## history.json

```json
{
  "periods": [
    {
      "date": "2026-10-15",
      "label": "10/15",
      "answerCount": 600,
      "platformCount": 6,
      "series": {
        "品牌整体": {"品牌 A": [112, 224, 10], "品牌 C": [16, 61, 0], "品牌 B": [15, 49, 0]},
        "食用油": {"品牌 A": [156, 92, 4], "品牌 C": [3, 12, 0], "品牌 B": [0, 6, 0]}
      },
      "platforms": {"豆包": {"品牌 A": [55.0, 45.0, 0.0], "...": [0, 0, 0]}},
      "unclear": {"品牌整体": 2, "食用油": 0}
    }
  ]
}
```

`series` 是 `[正向条数, 中性条数, 负向条数]`，不是百分比。竞品只在被提及时计数；`unclear` 不计入分母。`platforms` 是百分比，只用于本期平台表。

## report-data（HTML 内嵌）

```json
{
  "meta": {"title": "...", "brandLine": "...", "asOf": "2026-10-15", "issue": 1, "referenceBrand": "b2", "lowSample": {"食用油": ["b1", "b2"]}},
  "brands": [{"key": "b0", "name": "品牌 A", "color": "#14684b", "own": true}],
  "layers": ["品牌整体", "食用油"],
  "periods": [{"date": "2026-10-15", "label": "10/15"}],
  "series": {"品牌整体": {"b0": [[112, 224, 10]]}},
  "platforms": {"order": ["豆包"], "rates": {"豆包": {"b0": [55.0, 45.0, 0.0]}}},
  "copy": {"summary": "...", "kpiPosLabel": "...", "kpiPosSub": "...", "kpiNegLabel": "...", "kpiNegSub": "...", "kpiCatPosLabel": "...", "kpiCatPosSub": "...", "kpiCatNegLabel": "...", "kpiCatNegSub": "...", "layerHints": {}, "insights": {"neg": "...", "pos": "..."}, "comparisonNote": "...", "platformNote": "..."}
}
```

`series` 按品牌 key 索引；每个品牌在每个 period 上一条 `[正, 中, 负]`。缺失期用 `[0,0,0]`，但交付时应说明新增品牌从纳入期开始。

## 低样本规则

- 竞品在某分层总样本 `<20` 时：对比行显示「样本不足」，趋势图不画该竞品，但保留目标品牌。
- 平台表的小样本单元格保留百分比并加注「低样本仅作参考」。
- 报告不把低样本的 0% 负向写成「无风险」。

## 追加周期

1. 保留同一个 `<out>` 目录和 `history.json`。
2. 用新数据包重新跑提取、判定。
3. 用同一个 `<out>` 跑 `build_report.py`；同日期替换，不同日期追加。
4. 首期不足 3 期时，趋势区会显示「首期/数据累积中」，不补造历史。

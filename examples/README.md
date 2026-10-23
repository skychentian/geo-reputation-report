# 示例输入

本目录不放真实数据。使用 `diagnosis-answers.xlsx` + `manifest.json` 组成数据包，字段见 `references/input-contract.md`。

最小验证流程：

```bash
python3 scripts/extract_answers.py /path/to/package --out work/answers.json
python3 scripts/classify.py work/answers.json --out work/labels --backend none
# 按 references/classification-prompt.md 逐批判定，写入 work/labels/*.labels.json
python3 scripts/merge_labels.py work/answers.json work/labels
python3 scripts/build_report.py --answers work/answers.json \
  --labels work/labels/labels.json --out output
```

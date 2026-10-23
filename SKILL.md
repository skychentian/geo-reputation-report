---
name: geo-reputation-report
description: 从 GEO 诊断数据包（diagnosis-answers.xlsx）生成可直接打开或上传的「AI 美誉度对比」HTML 报告：本期三品牌对比、正面率/负面率逐期趋势、平台差异、竞品提及样本，支持按周累积历史与追加境外竞品。用户提到美誉度报告、竞品美誉度对比、品牌口碑对比、品牌 GEO 数据包、diagnosis-answers.xlsx、把诊断结果做成 HTML 报告、更新本期美誉度数据时使用。不要用于单次 GEO 采集、普通周报或文章写作。
---

# GEO 美誉度对比报告

把一份 GEO 诊断数据包变成客户可看的单页 HTML 报告。报告只讲三件事：本期品牌之间差多少、逐期在变好还是变坏、平台之间差多少。竞品数据来自回答中的提及样本，样本量必须显示出来，不能把提及样本伪装成等量对比。

## 何时用

- 用户给了一个 `diagnosis-answers.xlsx` / GEO 数据包，要出「美誉度对比」「竞品口碑对比」「品牌 AI 评价报告」。
- 已有报告，要追加本周/本期数据，保持历史累积。
- 已有报告，要追加境外竞品或新的竞品品牌，重新生成。

不用于：跑 GEO 采集（`geo-diagnosis-pipeline`）、写周报（`geo-weekly-report`）、写文章（`geo-article-writer`）。

## 输入

数据包目录（或直接给 xlsx）至少包含：

- `diagnosis-answers.xlsx`：`answers` sheet 必须有 `index, question, stage, topic, platform_name, round, status, answer_content`。
- `manifest.json`（可选但推荐）：读取 `task.brandName`、`task.title`、`task.completedAt`、`task.platforms`。
- `competitor_summary` sheet（可选）：默认取提及量最高的 2 个竞品；没有就用 `--competitors` 指定。

品牌名、周期从 manifest 推断；推断不对时用 `--target-brand`、`--competitors` 覆盖。平台名会归一化（`豆包手机版→豆包`、`元宝手机版→腾讯元宝` 等）。

分层默认两份：`品牌整体` 与 `食用油`，映射在 `config/layer-map.json`。`extract_answers.py` 会打印 `unmappedTopics`；出现未映射主题时先补映射再生成，不要默默塞进默认层。

## 工作流

以下命令在 skill 根目录执行；`<pkg>` 是数据包目录，`<work>` 是本次工作目录，`<out>` 是报告输出目录。

### 1. 提取与归一化

```bash
python3 scripts/extract_answers.py "<pkg>" \
  --out "<work>/answers.json" \
  --competitors "品牌 B,品牌 C"
```

竞品顺序就是报告里的展示顺序；`--reference-brand` 默认取第一个竞品，可用它指定对比基准（本案例传品牌 B）。先看输出里的 `target`、`competitors`、`layers`、`questions` 是否符合预期。

### 2. 判定每条回答的最终态度

```bash
python3 scripts/classify.py "<work>/answers.json" \
  --out "<work>/labels" \
  --batch-size 12 \
  --concurrency 6
```

默认用本机 `claude -p` 分批判定；也可以用 OpenAI 兼容接口：

```bash
LLM_BASE_URL=... LLM_API_KEY=... LLM_MODEL=... \
python3 scripts/classify.py "<work>/answers.json" --out "<work>/labels" --backend openai
```

没有可用模型时，先只生成批次，由当前 agent/人工按 `references/sentiment-rubric.md` 判定：

```bash
python3 scripts/classify.py "<work>/answers.json" --out "<work>/labels" --backend none
```

把每批判定结果写成 `<work>/labels/<batch-id>.labels.json`，再运行 `scripts/merge_labels.py` 合并。不要用关键词规则代替判定，也不要在判定失败时编造标签。

判定只输出每条回答对目标品牌、以及回答中实际提到的竞品的最终态度（正向/中性/负向/无法判断）。竞品没提到就不输出；不要给没出现的品牌补 0。

### 3. 生成报告

```bash
python3 scripts/build_report.py \
  --answers "<work>/answers.json" \
  --labels "<work>/labels/labels.json" \
  --out "<out>" \
  --reference-brand "品牌 B"
```

第一次生成会在 `<out>/history.json` 写入本期快照。以后每期用同一个 `<out>` 重跑，脚本按日期追加；同一天重跑会替换当天快照，不会重复。

### 4. 验收

- 打开 `<out>/reputation-report.html`，确认首屏结论、三品牌对比、两张趋势图、平台差异都能正常显示。
- 搜索 `NaN`、`undefined`、`0.0%` 的异常空图；确认目标品牌每个分层都有样本。
- 首期趋势只有 1 个点，页面会显示「首期数据，后续按期累积」，这是正常的；不要为了好看伪造历史。
- 竞品在某分层提及不足 20 条时，对比行显示「样本不足」，趋势图不画该竞品；这是有意的，不要改成 0% 强行比较。
- 报告只出现聚合结果，不出现回答原文、用户信息或内部路径。

## 口径与硬规则

1. **只认最终态度**：回答提到争议不等于负向；如果回答澄清争议并仍认可品牌，按正向或中性。判定规则见 `references/sentiment-rubric.md`。
2. **竞品是提及样本**：目标品牌用全量回答；竞品只用回答中明确提到的样本。报告里必须保留样本量提示，不能写成等量对比。
3. **低样本不比较**：竞品分层样本 <20 时，对比行显示「样本不足」，趋势图隐藏该竞品；平台表小样本仅作参考。
4. **历史只增不改**：`history.json` 按期累积；同日期替换；不要手工补造历史期。新增竞品时，旧期没有数据就是没有，不要补 0 冒充趋势。
5. **不可判定不硬判**：回答跑题、缺失或证据不足时用「无法判断」，从分母中排除，并在 `snapshot.json` 的 `unclear` 里保留数量。
6. **分层可改但要说清**：默认 `品牌整体 / 食用油`。改 `config/layer-map.json` 或传 `--layer-map` 后，确认 `unmappedTopics` 为空，再生成。
7. **不外发原文**：`answers.json`、`labels.json`、批次文件都留在工作目录；交付只给 HTML、`history.json`、`snapshot.json`。

## 输出

```
<out>/
├── reputation-report.html   # 自包含报告，可直接打开/上传
├── history.json             # 各期计数快照，追加用
└── snapshot.json            # 本期计数、分层、平台、不可判定数
```

`reputation-report.html` 的 `report-data` JSON 里包含 `meta / brands / layers / periods / series / platforms / copy`；需要二次开发或接系统上传时，直接读这个 JSON，不要解析 DOM。

## 失败处理

- `extract_answers.py` 报缺列：数据包不是当前版本，先确认 `answers` 表头，不要猜列。
- `classify.py` 有批次失败：保留已成功的缓存，重跑只会补失败批次；仍失败时用 `--backend none` 手动补，再 `merge_labels.py`。
- `build_report.py` 报 labels 缺失：不要生成半份报告；补齐标签或缩小样本后重跑，并在交付里说明。
- 竞品样本太少：先确认是否只导出了目标品牌的数据包；等竞品包/更多提及样本到位再比较，不要用 0% 填充。

## 追加境外竞品

把新竞品名加进 `--competitors`（顺序即展示顺序），重跑提取、判定、生成。旧期没有该竞品数据时，`history.json` 会保留空值/零值；报告应显示「样本不足」或从该期趋势中省略，不要回填。若竞品有独立数据包，先按同一口径提取再合并，确认品牌名、平台名、分层一致。

## 参考

- `references/input-contract.md`：xlsx/manifest 字段、品牌与周期推断、平台归一化。
- `references/sentiment-rubric.md`：判定规则、边界案例、竞品处理。
- `references/output-contract.md`：report-data / history / snapshot 结构。
- `references/layer-map.md`：分层映射与调整方法。
- `config/layer-map.json`：默认主题映射。

## 示例

用户说：「把这个示例数据包生成美誉度报告，竞品是品牌 B 和品牌 C。」

```bash
python3 scripts/extract_answers.py "$HOME/Downloads/example-package" \
  --out /tmp/reputation/answers.json --competitors "品牌 B,品牌 C"
python3 scripts/classify.py /tmp/reputation/answers.json --out /tmp/reputation/labels
python3 scripts/build_report.py --answers /tmp/reputation/answers.json \
  --labels /tmp/reputation/labels/labels.json --out /tmp/reputation/report --reference-brand "品牌 B"
open /tmp/reputation/report/reputation-report.html
```

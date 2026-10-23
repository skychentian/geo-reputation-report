# GEO Reputation Report

从 GEO 诊断数据包（`diagnosis-answers.xlsx`）生成一份自包含的「AI 品牌美誉度对比」HTML 报告。适合按周/按月把同一批问题的 AI 回答逐期累积，查看品牌自身与竞品在正面率、负面率上的变化。

> 仓库内不包含任何客户数据、回答原文、生成报告或凭据。示例品牌均为虚构占位。

## 报告长什么样

固定版式，数据驱动：

- **四张指标卡**：品牌整体正面率 / 负面率；食用油正面率 / 负面率。
- **本期三品牌对比**：品牌整体与核心品类两层，100% 构成条 + 正面/中性/负面占比 + 较上期变化。
- **逐期趋势**：品牌整体、食用油两张图，可切换「负面率 / 正面率」；期数按实际数据累积。
- **平台差异**：6 个 AI 平台的正面率/负面率对照。
- **低样本保护**：竞品在某一层提及不足 20 条时，对比行标「样本不足」，趋势图不画该竞品，避免拿小样本装成结论。

## 它解决什么问题

单份 GEO 诊断数据包通常只有目标品牌的问题集，竞品只会在回答里被提及。这个 skill 不把“提及样本”伪装成等量样本：

- 目标品牌：使用全量回答。
- 竞品：只使用回答中明确提到的样本，并在报告里显示样本量。
- 同一期数据重复生成只替换当天快照；不同日期自动追加到 `history.json`。
- 新增竞品时，旧期没有数据就显示“样本不足/无数据”，不回填成 0%。

## 安装

需要 Python 3.10+ 和 `openpyxl`：

```bash
git clone https://github.com/skychentian/geo-reputation-report.git
cd geo-reputation-report
python3 -m pip install -r requirements.txt
```

作为 agent skill 使用时，把仓库放到 skills 目录（二选一）：

```bash
# DeepSeek Harness / 兼容 Agent Skills 的目录
git clone https://github.com/skychentian/geo-reputation-report.git \
  ~/.agents/skills/geo-reputation-report

# Claude Code
git clone https://github.com/skychentian/geo-reputation-report.git \
  ~/.claude/skills/geo-reputation-report
```

仓库根目录的 `SKILL.md` 包含完整的 agent 工作流。

## 快速开始

```bash
# 1. 提取数据包（同一目录下应有 diagnosis-answers.xlsx 与 manifest.json）
python3 scripts/extract_answers.py "$HOME/Downloads/example-package" \
  --out work/answers.json \
  --competitors "品牌 B,品牌 C"

# 2. 判定每条回答的最终态度
#    默认使用本机 claude -p；也可以走 OpenAI 兼容接口或人工批次
python3 scripts/classify.py work/answers.json --out work/labels

# 3. 生成报告
python3 scripts/build_report.py \
  --answers work/answers.json \
  --labels work/labels/labels.json \
  --out output \
  --reference-brand "品牌 B"

open output/reputation-report.html
```

### 没有 Claude CLI / API

```bash
python3 scripts/classify.py work/answers.json --out work/labels --backend none
```

会生成 `work/labels/batches/*.json` 和判定规则。按 `references/classification-prompt.md` 逐批判定，写成 `<batch-id>.labels.json`，再运行：

```bash
python3 scripts/merge_labels.py work/answers.json work/labels
```

不要用关键词规则代替判定，也不要在判定失败时编造标签。

### 接入 OpenAI 兼容接口

```bash
LLM_BASE_URL="https://api.example.com/v1" \
LLM_API_KEY="..." \
LLM_MODEL="..." \
python3 scripts/classify.py work/answers.json --out work/labels --backend openai
```

## 一期一期累积

每次只给一期数据包，跑进**同一个输出目录**：

- 第 1 次生成第 1 期；
- 第 2 次用新数据包、同一个 `--out`，自动追加第 2 期；
- 同一天重跑只替换当天快照；
- 换目录会重新开始，历史不会自动迁移；需要延续时把 `--history` 指向旧的 `history.json`。

期数来自数据包 `manifest.json` 的 `task.completedAt`，不用手工填。

## 输入

数据包目录或 xlsx 至少包含：

- `diagnosis-answers.xlsx` 的 `answers` sheet：`index, question, stage, topic, platform_name, round, status, answer_content`。
- 推荐有 `manifest.json`：`task.brandName / task.title / task.completedAt / task.platforms`。
- 可选 `competitor_summary`：默认取提及量最高的两个竞品；也可用 `--competitors` 指定。

详细字段与口径见 [references/input-contract.md](references/input-contract.md)。

## 输出

```
output/
├── reputation-report.html   # 自包含报告，可直接打开/上传
├── history.json             # 各期计数快照，追加用
└── snapshot.json            # 本期计数、平台、不可判定数
```

`work/answers.json`、`work/labels.json`、批次文件都留在本地，不进入报告 HTML。报告只展示聚合结果。

## 判定口径

只判断回答的**最终态度**：正向 / 中性 / 负向 / 无法判断。提到争议不等于负向；竞品只在回答明确提及时才判定。完整规则和边界案例见 [references/sentiment-rubric.md](references/sentiment-rubric.md)。

分层默认「品牌整体 / 食用油」，映射在 [config/layer-map.json](config/layer-map.json)，可按行业调整。

## 开发与验证

```bash
python3 -m py_compile scripts/*.py
python3 scripts/extract_answers.py --help
python3 scripts/build_report.py --help
```

仓库只做本地语法和 CLI 冒烟，不包含任何客户数据。

## 许可

MIT，见 [LICENSE](LICENSE)。

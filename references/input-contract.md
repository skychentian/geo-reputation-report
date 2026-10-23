# 输入契约

## 数据包

支持两种输入：

1. 目录：包含 `diagnosis-answers.xlsx`、`manifest.json`、`00-README-AI-FIRST.md`。
2. 直接给 `diagnosis-answers.xlsx` 路径（同目录有 manifest 时自动读取）。

## answers sheet

必需列（按表头名读取，不按列号）：

`index, question, stage, topic, platform_name, round, status, answer_content`

可选列：`search_keywords, reference_count, citation_count, captured_at, screenshot_url, screenshot_path`。

- `index` 在包内唯一，用作回答 id 的一部分。
- `answer_content` 保留全文，不截断。
- `status` 非 `completed` 的回答默认仍保留；如需排除，在提取后过滤，并在报告里说明实际样本数。

## manifest

读取：

- `task.brandName`：目标品牌；会去掉“美誉度/口碑/GEO诊断/诊断/报告”等后缀。
- `task.title`：报告标题/周期兜底。
- `task.completedAt`：周期日期（取前 10 位）。
- `task.platforms`：平台顺序；没有就用实际出现顺序。
- `task.id`：任务 id，写入 meta。

## 品牌与竞品

- 目标品牌：`--target-brand` > manifest 推断。
- 竞品：`--competitors "品牌 B,品牌 C"` > `competitor_summary` 中提及量最高的 N 个（默认 2），排除目标品牌和“橄榄油/花生油/菜籽油/玉米油/调和油/大豆油/粮油”等品类词。
- 竞品顺序就是报告展示顺序；参考品牌 `--reference-brand` 默认取第一个竞品，本案例显式传品牌 B。

## 平台归一化

| 原始 | 归一 |
|---|---|
| 豆包手机版 / 豆包 | 豆包 |
| DeepSeek手机版 / DeepSeek | DeepSeek |
| 元宝手机版 / 腾讯元宝 | 腾讯元宝 |
| 通义千问手机版 / 通义千问 | 通义千问 |
| 文心一言 | 文心一言 |
| Kimi | Kimi |

其他平台去掉 `手机版/网页版/App版` 后缀。

## 分层

默认 `config/layer-map.json`：

- `品牌整体`：企业、品牌、合规、舆情、渠道、服务、竞争等主题。
- `食用油`：产品、烹饪、健康、成分、工艺、转基因、食用安全等主题。

提取时会打印 `unmappedTopics`。出现未映射主题时，补进 `config/layer-map.json`（或传 `--layer-map`），再重新提取。不要用“默认层”掩盖映射缺口。

## 周期

- 优先 `task.completedAt` 的日期。
- 没有就从标题里找 `YYYY-MM-DD / YYYY.MM.DD / YYYY年MM月DD日`。
- 都没有就用运行当天。
- 周期只到日；同一天重跑视为同一期并替换历史快照。

## 输出

`answers.json` 结构见 `references/output-contract.md`。提取只做归一化，不判定情感。

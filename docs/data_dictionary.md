# 数据字典与口径

一行 games 表代表一个唯一 Steam AppID；一行 game_tags 表代表一个唯一 AppID—标签关联。

| 字段 | 类型／单位 | 口径 |
| --- | --- | --- |
| app_id | 整数 | Steam 应用标识，清洗后唯一 |
| name | 文本 | 源游戏名，去首尾空白 |
| release_date | 日期 | 支持英文日期与 ISO 日期；仅月精度的日期暂记当月 1 日，本项目只分析到年份 |
| release_year | 整数 | 从有效发售日期提取 |
| price | USD | 采集时价格，可能已折扣；价格缺失／负数／非有限数为空 |
| price_band | 分类 | 零价、(0,5)、[5,10)、[10,20)、[20,40)、40+、价格未知 |
| positive / negative | 评价条数 | 非负整数；任一缺失或为负时两者均标为缺失 |
| reviews | 评价条数 | positive + negative，不是销量 |
| positive_rate | 0–1 | positive / reviews；零评价为空，不计为 0% |
| wilson_lower | 0–1 | 二项比例 Wilson 95% 置信区间下界，z=1.96，减少小样本满分偏差 |
| discount | 0–100 | 源字段折扣百分比；无折扣筛选要求精确为 0，未知不当作 0 |
| peak_ccu | 人数 | 保留源字段，观测时间窗未核实，仅在明细展示 |
| estimated_owners | 源文本区间 | 不参与销量、收入或用户规模计算 |
| genres / developers | 文本 | 原数组以分隔符连接，仅辅助核查 |
| game_tags.tag | 文本 | 源标签键名，不使用投票数权重；去重关联 |

## 指标

- 游戏好评率中位数：对非空 positive_rate 取中位数，各游戏等权。
- 评价加权好评率：sum(positive) / sum(reviews)，所有有效评价等权，爆款影响更大。
- 高好评游戏占比：有评价的游戏中 positive_rate ≥ 90% 的比例。
- 标签游戏数：当前筛选内具有该标签的唯一游戏数。多个标签之间有重叠，不可求和作市场总数。
- 同比：(本年样本发行数 − 上年样本发行数) / 上年样本发行数。先补齐年份；上年为零、范围内第一年、未完整年度均不提供有效同比。
- 标签排名：好评率中位数降序，DENSE_RANK 支持并列；标签最少游戏数可调。
- 价格带内游戏排名：至少 100 条评价，按 Wilson 下界排序。每组前十名可能因并列超过十款。

## 清洗与审计

按顺序判定：无效 AppID → 重复 AppID → 无名称 → 名称匹配 demo/playtest/dedicated server/soundtrack → 无有效日期 → 版本日期之后发售 → 保留。每条记录只记一个排除原因；重复保留源文件第一条，非按销量或评价择优。

数据源没有单独的准确采集时间和可靠应用类型字段，不能保证筛除所有非正式游戏。未来发售判定以版本更新日期 2026-10-02 为分析截止日期。更新数据版本时需同步修改 pipeline.py 中版本和日期，并重新生成报告。

## 来源

[Kaggle 数据集](https://www.kaggle.com/datasets/fronkongames/steam-games-dataset)；[作者采集器说明](https://github.com/FronkonGames/steam-games-scraper)。币种按采集器默认 USD 解释；源包中没有币种列，不能逐条独立校验。

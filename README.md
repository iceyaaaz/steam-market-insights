# Steam 游戏市场洞察

一个面向数据分析／数据运营岗位的可复现作品：使用 SQL 清洗真实 Steam 数据，Pandas 验证业务假设，Streamlit 展示筛选后的市场结构、口碑和竞品。当前版本不含 AI，也不需要 API 密钥。

## 在线体验

- [在线交互看板](https://iceyaaaz-steam-market.streamlit.app/)
- [Cozy 游戏竞品分析案例](reports/cozy/final_case.md)

支持按发行年份、价格带、游戏标签和评价数筛选，查看市场结构、
玩家口碑与竞品排名，并下载筛选结果。

## 快速运行

需要 Python 3.13（本项目验证版本）。项目已包含处理后的 Parquet 数据，启动看板无需重新下载 318 MB 原始包。

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

Windows 也可在项目目录运行 `powershell -ExecutionPolicy Bypass -File start.ps1`。浏览器打开终端显示的本地地址。

Linux / macOS：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

## 业务问题与入口

1. 供给集中在哪些价格带？——市场概览，使用全量样本时将最低评价数调到 0。
2. 价格和好评率是什么关系？——价格与口碑，查看分布、中位数和高好评占比。
3. 哪些标签口碑更高？——标签竞争，同时观察样本规模及评价数。
4. 评价关注度是否高度集中？——reports/analysis.md，使用 Pandas 计算头部约 1% 的评价份额。
5. 不同年份的发行结构如何变化？——发行趋势，SQL 补齐年份后用 LAG 计算同比。

默认至少 100 条评价；筛选器包含年份、价格带、标签（OR）、评价数、折扣和游戏名。所有页面共用筛选样本。游戏明细支持 CSV 导出，口碑排名支持 Wilson 下界，摘要是确定性规则生成。

当前数据中的 452 个标签均提供中文阅读释义：筛选项使用中英对照，图表使用中文标签并在悬停中显示英文，统计表单列中文解释与英文原名。释义见 tag_labels.py，不替换底层英文标签或改变统计口径。

## 项目结构

```text
app.py                  Streamlit 交互界面
pipeline.py             固定版本下载、JSON 解析、SQL 清洗、审计及 Parquet 输出
analytics.py            SQL 调用、Pandas 分组、敏感性分析、筛选和导出
report.py               根据真实数据重新生成 5 个业务问题的分析报告
sql/                    清洗、聚合、标签排名、同比、价格带内排名
data/                   处理后数据、元数据与审计（可直接部署）
reports/                分析报告及分析结果表
tests/                  数据口径与筛选边界测试、Streamlit 交互测试
docs/                   数据字典、部署说明、面试说明
```

## 从原始数据复现

```powershell
python pipeline.py
python report.py
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

也可执行 `python pipeline.py --archive 路径/steam-v52.zip` 使用已下载的原始包。下载地址固定 `datasetVersionNumber=52`；SHA-256 记录在 data/metadata.json。环境中完整依赖版本见 requirements-lock.txt。原始包不提交仓库。

## 数据来源与关键发现

- [FronkonGames Steam Games Dataset / Kaggle](https://www.kaggle.com/datasets/fronkongames/steam-games-dataset)，作者 Martin Bustos，版本 52，更新于 2026-10-02。数据集页面元数据标注 MIT。
- [作者采集代码与字段背景](https://github.com/FronkonGames/steam-games-scraper)。采集器默认美元；此数据包没有单独 currency 列，因此按默认 USD 解释，不用于汇率比较。
- **v52 CSV 表头字段错位：** `DiscountDLC count` 合并列名，后续数据与表头不匹配。本项目使用同包 `games.json`，并保留 AppID 496350 的评价核验测试。
- 数据是快照；价格可能包含折扣。评价量不是销量，Peak CCU 不是实时在线人数。无历史快照时不分析价格、口碑或收入同比。
- demo／playtest 等按名称规则剔除；该规则不是完整的应用类型识别器。详细排除计数在 data/audit.json。

数据局限与业务结论见 [分析报告](reports/analysis.md)，字段和口径见 [数据字典](docs/data_dictionary.md)。

## Cozy 业务案例

**从这里阅读：[业务案例终稿](reports/cozy/final_case.md)。** 已完成市场筛选、竞品核查、40条玩家评论的主题研究与业务建议。评论证据由助手逐条解读，未经过独立人工复核；公开包保留中文转述和来源，不包含评论全文。`python review_case.py` 可根据固定证据重新汇总；新采样必须重新标注。

后续研究：[三款叙事解谜游戏对比](reports/cozy/competitor_comparison.md)，核查具体玩法，并区分已有事实与需要评论验证的假设。

新增 [Cozy 游戏竞品研究](reports/cozy/case_report.md)：从737款Cozy游戏筛选183款近期付费竞品，比较价格与口碑、检查折扣和评价门槛影响，并提供12款候选游戏及标签覆盖局限。运行 `python cozy_case.py` 可复现报告和配套结果表；候选游戏尚需人工核查玩法、体量及团队规模。

## 发布为简历链接

本地验收通过后，可按 [部署说明](docs/deployment.md) 将项目放入自己的 GitHub 仓库并在 Streamlit Community Cloud 部署。本项目未内嵌任何账户、密钥或远程仓库地址。

## 后续 AI 扩展边界

后续可把当前筛选条件、样本数、SQL 聚合结果及限制说明打包成结构化上下文，交给大模型生成分析报告。计算仍由 SQL／Pandas 完成，API 密钥仅放服务端；本版没有模拟 AI 功能。

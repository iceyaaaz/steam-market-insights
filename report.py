"""Generate five evidence-backed findings and reproducible Pandas tables."""
import pandas as pd
from analytics import ROOT, load_data, price_summary, tag_summary, sensitivity, stratified_prices, release_trend


def table(frame, percent_columns=()):
    frame = frame.copy()
    for c in percent_columns:
        frame[c] = frame[c].map(lambda x: f'{x:.1%}' if pd.notna(x) else '—')
    for c in frame:
        frame[c] = frame[c].map(lambda x: str(x) if pd.notna(x) else '—')
    lines = ['| ' + ' | '.join(frame.columns) + ' |', '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |']
    lines += ['| ' + ' | '.join(str(v).replace('|', '/') for v in row) + ' |' for row in frame.itertuples(index=False, name=None)]
    return '\n'.join(lines)


def generate():
    games, tags, meta = load_data()
    out = ROOT / 'reports'
    out.mkdir(exist_ok=True)
    cohort = games.loc[games.reviews.ge(100)]
    all_prices = price_summary(games, tags)
    prices = price_summary(cohort, tags)
    ranks = tag_summary(cohort, tags, 100)
    robust = sensitivity(games, tags)
    strata = stratified_prices(games, tags)
    trend = release_trend(games, tags, (int(games.release_year.min()), 2026), 2026)
    for name, frame in [('price_all',all_prices), ('price_review100',prices), ('tags_review100',ranks),
                        ('threshold_sensitivity',robust), ('tag_year_price',strata), ('release_trend',trend)]:
        frame.to_csv(out / f'{name}.csv', index=False, encoding='utf-8-sig')
    largest = all_prices.sort_values('games',ascending=False).iloc[0]
    best = prices.loc[prices.rated_games.ge(100)].sort_values('median_positive_rate',ascending=False).iloc[0]
    top = ranks.iloc[0]
    review_total = games.reviews.sum()
    n_top = max(1, int(len(games) * .01))
    concentration = games.nlargest(n_top, 'reviews').reviews.sum() / review_total
    change = trend.loc[trend.release_year.eq(2025)].iloc[0]
    non_discount = price_summary(cohort.loc[cohort.discount.eq(0)], tags)
    non_discount.to_csv(out / 'price_no_discount.csv', index=False, encoding='utf-8-sig')
    winners = (robust.loc[robust.games.ge(100)].sort_values('median_positive_rate', ascending=False)
               .groupby('min_reviews').head(1).sort_values('min_reviews'))
    undiscounted_best = non_discount.loc[non_discount.rated_games.ge(100)].sort_values('median_positive_rate', ascending=False).iloc[0]
    # Within the same tag and release year, compare two paid bands where both n >= 30.
    pivot = strata.pivot(index=['tag','release_year'], columns='price_band', values='median_positive_rate')
    comparisons = pivot.dropna(subset=['[5,10)', '[10,20)']) if {'[5,10)', '[10,20)'}.issubset(pivot.columns) else pd.DataFrame()
    within = (f'在同标签、同发售年且两个价位各至少 30 款游戏的 {len(comparisons)} 个分组中，'
              f'[10,20) 美元组口碑中位数高于 [5,10) 美元组的比例为 '
              f'{(comparisons["[10,20)"] > comparisons["[5,10)"]).mean():.1%}。'
              if not comparisons.empty else '同标签、同年份分组的有效样本不足，不能做稳定的跨价格带比较。')
    text = f'''# Steam 游戏市场洞察：业务分析报告

## 分析范围

面向游戏品类研究、竞品分析和数据分析岗位作品展示。数据来自 [FronkonGames / Kaggle]({meta['source_url']}) v52，版本更新时间 {meta['source_updated']}。使用 games.json，共 {meta['quality']['raw_records']:,} 条原始记录，清洗后 {len(games):,} 款；口碑分析默认至少 100 条评价，共 {len(cohort):,} 款。标签可重叠，价格为 USD 快照价格。版本日期不代表每一条数据的抓取日期。

## 1. 游戏供给集中在哪些价格带？

全量清洗样本中，**{largest.price_band} 美元**数量最多，为 **{int(largest.games):,} 款，占 {largest.games/len(games):.1%}**。这是供给结构，不是销售结构。

{table(all_prices[['price_band','games','median_reviews']])}

业务含义：用价格带定位竞品范围，再比较题材、品质和评价量。数量多不能直接证明该价位更容易成功；零价记录也不能全部视为长期免费游戏。

## 2. 什么价位的游戏更容易获得高好评？

评价数至少 100，且价格带至少有 100 款有评价游戏时，**{best.price_band} 美元**的游戏好评率中位数最高，为 **{best.median_positive_rate:.1%}**，该组 **{int(best.games):,} 款**。好评率 ≥90% 的比例见下表，不能将中位数直接解释为成功概率。

{table(prices[['price_band','games','median_positive_rate','high_rating_share']], ['median_positive_rate','high_rating_share'])}

稳健性检查：将评价门槛改为 20／100／500，在各价格带至少 100 款游戏的前提下，最高中位数价格带如下。完整结果保存在 threshold_sensitivity.csv。

{table(winners[['min_reviews','price_band','games','median_positive_rate']], ['median_positive_rate'])}

仅保留明确无折扣且至少 100 条评价的游戏时，至少 100 款游戏的价格带中，{undiscounted_best.price_band} 美元组最高，为 {undiscounted_best.median_positive_rate:.1%}（{int(undiscounted_best.games):,} 款）。因此不应把全量快照的价格结论直接推广到原价市场。完整结果见 price_no_discount.csv。

{within}各标签组存在重叠，不能当作相互独立的统计试验；分组控制也不能消除所有混杂因素。

业务含义：用这些分布比较同类竞品，不能推导出“提高售价就能提高口碑”。价格可能受折扣影响，高价也可能伴随更高预算、品牌和制作质量。

## 3. 哪些标签拥有更高口碑？

在评价数至少 100、标签至少 100 款游戏的条件下，**{top.tag}** 位于好评率中位数榜首，为 **{top.median_positive_rate:.1%}**，包含 **{int(top.games):,} 款**。并列排名使用 DENSE_RANK，榜首不一定唯一。

{table(ranks.head(10)[['tag','games','median_positive_rate','median_reviews']], ['median_positive_rate'])}

业务含义：可从口碑较高、样本足够的标签中筛选竞品，再查看评价文本和具体玩法。小众高口碑不能直接解释为大市场；标签来自用户标注，也存在同义和风格标签。

## 4. 评价关注度是否集中在少数游戏？

全量清洗样本中，按评价量排序的前 **{n_top:,} 款（约 1%）贡献了 {concentration:.1%} 的评价数**。这是评价关注度集中度，不是收入份额或销量份额。

业务含义：整体加权好评率会更多反映热门游戏。分析普通竞品时应同时看每游戏中位数、分位数和样本数量，避免只用爆款推断市场。

## 5. 样本中的发行数量如何变化？

2025 年发售的游戏有 **{int(change.games):,} 款**，相较 2024 年的样本数量变化为 **{change.yoy:+.1%}**。使用补齐年份后的 LAG 计算同比；前一年数量为零则同比为空。2026 年不完整，不计算同比。

{table(trend.loc[trend.release_year.ge(2018)], ['yoy'])}

业务含义：发行结构可用于选择竞品年份，但本数据是存量快照，可能漏掉下架游戏，不能声称覆盖完整历史市场。新游戏评价积累时间更短，所以此处使用全量样本，不加最低评价数门槛。

## 数据质量发现与局限

- CSV 表头含 DiscountDLC count，后续字段错位。AppID 496350 在 JSON 中为 252 好评、3 差评；按原 CSV 表头读取却是 0 好评、252 差评。项目使用同包 JSON，不静默修补含义不明确的列。
- 缺失价格 {meta['quality']['missing_price']:,} 款；无评价 {meta['quality']['zero_reviews']:,} 款；评价字段缺失 {meta['quality']['missing_reviews']:,} 款；无标签 {meta['quality']['no_tags']:,} 款。缺失值不填零，无评价好评率为空。
- 按名称排除 Demo、Playtest、Dedicated Server、Soundtrack。这是可审计的启发式，不能保证剔除所有工具／非正式游戏；原数据没有可靠应用类型字段。
- 不估算收入、销量或用户转化。Peak CCU 的观测窗口不明确，只在明细中展示源值，不用于实时在线趋势。
- 没有历史价格或评价快照，不能分析口碑同比、价格变化的因果效果或实时市场。
- 源数据的更新周期、存活偏差、标签重叠、评论人群选择偏差和发售时长都会影响结果。

## 可复现路径

`python pipeline.py` → `python report.py` → `python -m streamlit run app.py`。
SQL 见 sql/；Pandas 分组和门槛敏感性分析见 analytics.py；审计计数见 data/audit.json；原始包校验值见 data/metadata.json。
'''
    (out / 'analysis.md').write_text(text, encoding='utf-8')
    print(f'Report written: {out / "analysis.md"}')


if __name__ == '__main__':
    generate()

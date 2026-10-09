"""Reproduce the Cozy competitor research case from the bundled snapshot."""
import json
import pandas as pd
from analytics import ROOT, load_data, price_summary, safe_csv
from tag_labels import tag_label
from report import table


def run():
    games, tags, metadata = load_data()
    out = ROOT / 'reports/cozy'
    out.mkdir(parents=True, exist_ok=True)
    cozy = games.loc[games.app_id.isin(tags.loc[tags.tag.eq('Cozy'), 'app_id'])].copy()
    rated = cozy.loc[cozy.reviews.ge(100)]
    recent = rated.loc[rated.release_year.between(2023, 2025) & rated.price.gt(0)].copy()
    no_discount = recent.loc[recent.discount.eq(0)]
    coverage = (games.assign(has_tags=games.app_id.isin(tags.app_id))
                .groupby('release_year').agg(games=('app_id', 'size'), with_tags=('has_tags', 'sum')))
    coverage['tag_coverage'] = coverage.with_tags / coverage.games
    coverage = coverage.reset_index()
    assert cozy.app_id.is_unique and recent.app_id.is_unique
    assert recent.reviews.ge(100).all() and recent.price.gt(0).all()

    price_tables = []
    for name, frame in [('all_cozy',cozy), ('review100',rated), ('recent_paid',recent), ('recent_no_discount',no_discount)]:
        result = price_summary(frame, tags)
        result.insert(0, 'cohort', name)
        price_tables.append(result)
    all_prices = pd.concat(price_tables, ignore_index=True)
    sensitivity = []
    for minimum in [20,100,500]:
        frame = cozy.loc[cozy.release_year.between(2023,2025) & cozy.price.gt(0) & cozy.reviews.ge(minimum)]
        summary = price_summary(frame,tags)
        summary.insert(0, 'minimum_reviews', minimum)
        sensitivity.append(summary)
    sensitivity = pd.concat(sensitivity, ignore_index=True)
    co_tags = (tags.loc[tags.app_id.isin(recent.app_id) & tags.tag.ne('Cozy')]
               .groupby('tag').app_id.nunique().sort_values(ascending=False).rename('games').reset_index())
    co_tags['chinese'] = co_tags.tag.map(tag_label)
    co_tags['share'] = co_tags.games / len(recent)

    # Transparent purposive selection, not a random sample or a success prediction.
    selected_ids = set()
    parts = []
    groups = [
        ('高评价量参照', recent.sort_values(['reviews','app_id'],ascending=[False,True]),
         '研究高关注度产品的表现；评价量不等于销量，也不代表小团队可复制。'),
        ('中等评价量高口碑', recent.loc[recent.reviews.between(100,999)].sort_values(
            ['wilson_lower','app_id'],ascending=[False,True]),
         '在100—999条评价中按Wilson下界选取，研究较少评价下的高口碑产品。'),
        ('相对低口碑对照', recent.sort_values(['positive_rate','reviews','app_id'],ascending=[True,False,True]),
         '对照研究玩家可能不满意的方面；差评原因须另外阅读评论验证。'),
        ('2025年新品观察', recent.loc[recent.release_year.eq(2025)].sort_values(
            ['reviews','app_id'],ascending=[False,True]),
         '研究样本中较新的产品；评价积累时长与老游戏不同。'),
    ]
    for role, pool, reason in groups:
        chosen = pool.loc[~pool.app_id.isin(selected_ids)].head(3).copy()
        selected_ids.update(chosen.app_id)
        chosen.insert(0,'role',role)
        chosen['reason'] = reason
        parts.append(chosen)
    candidates = pd.concat(parts,ignore_index=True)
    # Show gameplay evidence rather than inferring mechanics from a game's name.
    gameplay = {'Puzzle','Simulation','Building','Management','Farming Sim','Life Sim','Exploration',
                'Adventure','RPG','Platformer','Idler','Hidden Object','Crafting','Sandbox','Fishing',
                'Card Game','Strategy','Cooking','Collectathon','Creature Collector'}
    relevant = tags.loc[tags.tag.isin(gameplay)].assign(label=lambda x:x.tag.map(tag_label))
    label_map = relevant.groupby('app_id').label.agg(lambda values:' / '.join(sorted(values)))
    candidates['gameplay_tags'] = candidates.app_id.map(label_map).fillna('需人工核查玩法')
    candidates['store_url'] = candidates.app_id.map(lambda app:f'https://store.steampowered.com/app/{app}')
    columns = ['role','app_id','name','release_year','price','discount','reviews','positive_rate',
               'wilson_lower','developers','gameplay_tags','reason','store_url']
    candidates = candidates[columns]
    assert candidates.app_id.is_unique and len(candidates) == 12
    for name, frame in [('price_comparison',all_prices),('review_thresholds',sensitivity),
                        ('co_tags',co_tags),('tag_coverage',coverage),('candidates',candidates),('cohort',recent)]:
        (out/f'{name}.csv').write_bytes(safe_csv(frame))

    prices = price_summary(recent,tags)
    display = prices[['price_band','games','median_positive_rate','median_reviews']].rename(columns={
        'price_band':'快照价格（美元）','games':'游戏数','median_positive_rate':'好评率中位数','median_reviews':'评价数中位数'})
    display['评价数中位数'] = display['评价数中位数'].map(lambda x:f'{x:,.1f}')
    non_discount_table = price_summary(no_discount,tags)[['price_band','games','median_positive_rate']].rename(columns={
        'price_band':'快照价格（美元）','games':'游戏数','median_positive_rate':'好评率中位数'})
    role_display = candidates[['role','name','price','reviews','positive_rate']].rename(columns={
        'role':'选入目的','name':'游戏名','price':'快照价 USD','reviews':'评价数','positive_rate':'好评率'})
    text = f'''# Cozy 游戏竞品研究：小型工作室应先研究什么？

## 业务背景

模拟场景：一家小型工作室想开发温馨轻松的游戏，但尚未确定具体玩法。本次先回答：有哪些可参考的产品、价格和口碑呈现什么关系、下一步应该核查什么。这里的 Cozy 是风格标签，不是统一玩法；本报告不评估盈利，也不承诺某个方向会成功。

**核心结论：先确定玩法，再从下方名单选同类竞品。现有价格数据不足以支持直接决定发行价。**

## 竞品筛选标准

数据来自 [FronkonGames / Kaggle]({metadata['source_url']}) 第52版，更新于 {metadata['source_updated']}；不是实时数据。数据文件及筛选代码随项目提供。

| 层级 | 筛选条件 | 游戏数 | 用途 |
| --- | --- | ---: | --- |
| 市场观察 | 清洗后具有 Cozy 标签 | {len(cozy):,} | 看样本中的品类结构 |
| 口碑比较 | 再要求至少100条评价 | {len(rated):,} | 减少少量评价的波动 |
| 近期付费竞品池 | 再要求2023—2025年发售、价格大于0 | {len(recent):,} | 本报告主要比较范围 |
| 无折扣对照 | 近期竞品池内折扣字段为0 | {len(no_discount):,} | 检查促销是否影响观察结果 |

未先限定价格区间，也没有只挑高好评游戏。100条评价只是筛选门槛，不等于统计结论已经可靠。候选名单还需核实实际玩法、内容体量与团队规模；不能直接称作“小工作室可复制的产品”。

## 主要发现

### 1. Cozy 覆盖多种玩法，不能把所有产品当成直接竞品

183款近期竞品中，带模拟标签的有97款、探索78款、解谜59款、建造56款、生活模拟49款。标签可重叠，数量不能相加。温馨轻松是一种共同风格，不代表它们使用同样的玩法、开发成本或商业模式。

**建议：**先确定要研究解谜、建造还是生活模拟。然后在该玩法内比较竞品，而不是直接模仿整个 Cozy 榜单的前几名。

### 2. 低价组口碑较高，但排除折扣记录后排序改变

在183款近期付费游戏中，低于20美元共有 **{int(recent.price.lt(20).sum())}款，占{recent.price.lt(20).mean():.1%}**。各组如下：

{table(display,['好评率中位数'])}

低于5美元组的好评率中位数为94.3%，高于另外两个主要价格带；但这是快照价格，不能解释成“卖便宜就能得到更多好评”。近期竞品中 **{int(recent.discount.gt(0).sum())}款（{recent.discount.gt(0).mean():.1%}）**记录了折扣。

只看无折扣的41款游戏后，结果如下：

{table(non_discount_table,['好评率中位数'])}

三个主要价位组的排序发生变化，而且每组只剩11—16款；20—40美元组只有2款。这里的样本也发生了变化，所以不能把排序变化直接归因于打折本身。

另外，将评价门槛改为20、100、500条时，含折扣样本中仍是低于5美元组的好评率中位数最高，分别为95.2%、94.3%、96.9%。500条门槛下，三个主要价格带只剩19、23、30款。完整对照见 review_thresholds.csv。这些是描述性差异，没有进行因果推断或宣称差异具有统计显著性。

**建议：**把低于5美元、5—10美元、10—20美元作为竞品研究分组；先核实同玩法产品的常规定价和内容体量，再讨论本产品的候选定价。不能据这份快照直接推荐售价。

### 3. 2026年的标签覆盖缺失，不能据此判断最新趋势

清洗样本中2026年发售的20,792款游戏全部没有标签。2025年21,706款中只有5,953款有标签（27.4%）。因此“本样本没有2026年的Cozy游戏”不等于“2026年没有Cozy游戏”，也不能用样本中2025年Cozy数量较少来判断市场降温。

**建议：**本次名单用作历史样本的候选池。要支持当前立项，必须补查新品和标签覆盖；暂不做Cozy市场增长率结论。

## 候选竞品：先看这12款

分四组，每组3款；重复游戏只保留在先入选的组。高评价量组按评价数排序；中等评价量组限制100—999条评价后按Wilson口碑下界排序；低口碑对照按好评率升序；新品组从2025年游戏中按评价数排序。**这些是进一步研究的候选，不是“最佳游戏”榜单。**

{table(role_display,['好评率'])}

完整 [候选表](candidates.csv) 包含Steam链接、开发者、玩法标签、折扣比例和选入原因。游戏名称保留源数据原名；不是本轮核验后的商店现名。

## 下一步行动与局限

1. **选择一种玩法。** 从解谜、建造、生活模拟等方向选择实际要开发的玩法，再缩小名单。
2. **人工核查3—5款同类产品。** 记录核心玩法、内容时长、团队规模、常规价与折扣；确认可比性。
3. **补读玩家评论。** 当前数据只有好评／差评数量，不能解释玩家满意或不满意的具体原因。下一步再抽取并归纳评论主题。

评价量不等于销量；好评率不是盈利概率；缺少成本、收入和历史价格。标签来自源数据且可能不全，评价门槛也会漏掉新作和低关注度作品。本报告没有实时核验Steam商店，也未分析评论正文。小型工作室的预算、人数与周期尚未确定，所以不做开发可行性结论。

复现：在项目目录运行 `python cozy_case.py`。本报告以数据快照为依据，SQL价格汇总复用 sql/02_price_bands.sql；样本筛选、门槛检查、候选选择和覆盖率分析由 Pandas 完成。
'''
    (out/'case_report.md').write_text(text,encoding='utf-8')
    evidence = dict(cozy=len(cozy),review100=len(rated),recent_paid=len(recent),
                    recent_no_discount=len(no_discount),candidates=len(candidates))
    (out/'summary.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(evidence,ensure_ascii=True))
    print(candidates[['role','name','price','reviews','positive_rate']].to_string(index=False))


if __name__ == '__main__':
    run()

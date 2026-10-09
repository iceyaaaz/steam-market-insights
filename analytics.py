"""SQL aggregation and Pandas cohort analysis shared by the app and report."""
from pathlib import Path
import json
import duckdb
import pandas as pd
from tag_labels import tag_label

ROOT = Path(__file__).resolve().parent
BANDS = ['零价', '(0,5)', '[5,10)', '[10,20)', '[20,40)', '40+', '价格未知']


def load_data():
    return (pd.read_parquet(ROOT / 'data/games.parquet'),
            pd.read_parquet(ROOT / 'data/game_tags.parquet'),
            json.loads((ROOT / 'data/metadata.json').read_text(encoding='utf-8')))


def filter_games(games, tags, years, price_bands, selected_tags=(), min_reviews=100,
                 exclude_discount=False, name=''):
    mask = games.release_year.between(*years) & games.price_band.isin(price_bands)
    if min_reviews > 0:
        mask &= games.reviews.ge(min_reviews)
    if selected_tags:
        ids = tags.loc[tags.tag.isin(selected_tags), 'app_id'].unique()
        mask &= games.app_id.isin(ids)  # OR semantics; never duplicates the game rows.
    if exclude_discount:
        mask &= games.discount.eq(0)  # Unknown discount is not assumed to be zero.
    if name.strip():
        mask &= games.name.str.contains(name.strip(), case=False, regex=False, na=False)
    return games.loc[mask].copy()


def sql_query(filename, selected, tags, params=None):
    with duckdb.connect() as con:
        con.register('selected', selected)
        con.register('game_tags', tags)
        return con.execute((ROOT / 'sql' / filename).read_text(encoding='utf-8'), params or {}).df()


def price_summary(selected, tags):
    result = sql_query('02_price_bands.sql', selected, tags)
    result['price_band'] = pd.Categorical(result.price_band, BANDS, ordered=True)
    return result.sort_values('price_band')


def tag_summary(selected, tags, min_games=30):
    return sql_query('03_tags.sql', selected, tags, {'min_games': min_games})


def release_trend(selected, tags, years, snapshot_year):
    return sql_query('04_release_trend.sql', selected, tags,
                     dict(start_year=int(years[0]), end_year=int(years[1]), snapshot_year=int(snapshot_year)))


def kpis(selected):
    total = selected.reviews.sum(min_count=1)
    return dict(games=len(selected), median_price=selected.price.median(),
                median_rate=selected.positive_rate.median(),
                weighted_rate=selected.positive.sum(min_count=1) / total if total > 0 else float('nan'),
                reviews=total)


def sensitivity(games, tags):
    """Is the best price band stable when the review threshold changes?"""
    records = []
    for threshold in [20, 100, 500]:
        cohort = games.loc[games.reviews.ge(threshold)]
        for row in price_summary(cohort, tags).itertuples():
            records.append(dict(min_reviews=threshold, price_band=str(row.price_band),
                                games=row.games, median_positive_rate=row.median_positive_rate,
                                high_rating_share=row.high_rating_share))
    return pd.DataFrame(records)


def stratified_prices(games, tags):
    """Pandas: within-tag/year/price comparisons with explicit minimum sample sizes."""
    sample = games.loc[games.reviews.ge(100) & games.price.gt(0)]
    joined = sample.merge(tags, on='app_id', how='inner', validate='one_to_many')
    return (joined.groupby(['tag', 'release_year', 'price_band'], observed=True)
            .agg(games=('app_id', 'nunique'), median_positive_rate=('positive_rate', 'median'),
                 median_reviews=('reviews', 'median'))
            .query('games >= 30').reset_index()
            .sort_values(['tag', 'release_year', 'price_band']))


def narrative(selected, tags):
    """Deterministic facts for current filters; explicitly not an AI report."""
    if selected.empty:
        return ['当前筛选无样本，请放宽价格、年份或评价数条件。']
    facts = [f'当前筛选包含 {len(selected):,} 款游戏；有评价的游戏为 {selected.positive_rate.notna().sum():,} 款。']
    prices = price_summary(selected, tags)
    largest = prices.sort_values('games', ascending=False).iloc[0]
    facts.append(f'样本最多的价格带是 {largest.price_band} 美元，共 {int(largest.games):,} 款，占当前样本 {largest.games / len(selected):.1%}。')
    eligible = prices.loc[prices.rated_games.ge(30) & prices.median_positive_rate.notna()]
    if not eligible.empty:
        best = eligible.sort_values('median_positive_rate', ascending=False).iloc[0]
        facts.append(f'至少有 30 款有评价游戏的价格带中，{best.price_band} 美元的游戏好评率中位数最高，为 {best.median_positive_rate:.1%}（有评价样本 {int(best.rated_games):,} 款）。')
    ranked = tag_summary(selected, tags)
    if not ranked.empty and pd.notna(ranked.iloc[0].median_positive_rate):
        top = ranked.iloc[0]
        facts.append(f'至少包含 30 款游戏的标签中，{tag_label(top.tag)} 的好评率中位数排名靠前：{top.median_positive_rate:.1%}，样本 {int(top.games):,} 款。多标签样本有重叠。')
    return facts


def safe_csv(frame):
    """Prevent untrusted game names becoming formulas when opened in Excel."""
    result = frame.copy()
    for column in result.select_dtypes(include=['object', 'string', 'category']).columns:
        result[column] = result[column].astype('string').map(
            lambda value: "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value)
    return result.to_csv(index=False).encode('utf-8-sig')

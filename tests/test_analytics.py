import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import duckdb
import pandas as pd
import pytest
from analytics import ROOT, BANDS, filter_games, price_summary, release_trend, tag_summary, safe_csv


@pytest.fixture
def dataset():
    raw = pd.DataFrame([
        dict(app_id='1',name='A',release_date='Jan 1, 2023',price='0',positive='0',negative='0'),
        dict(app_id='2',name='B',release_date='Jan 1, 2025',price='5',positive='90',negative='10'),
        dict(app_id='3',name='C',release_date='Jan 1, 2025',price='10',positive='1',negative='0'),
        dict(app_id='4',name='D',release_date='Jan 1, 2026',price='bad',positive='-1',negative='0'),
        dict(app_id='5',name='Game Demo',release_date='Jan 1, 2025',price='2',positive='10',negative='0'),
        dict(app_id='6',name='Future',release_date='Jan 1, 2027',price='2',positive='1',negative='0'),
        dict(app_id='2',name='Duplicate',release_date='Jan 1, 2025',price='5',positive='90',negative='10'),
    ])
    raw['source_row'] = range(len(raw))
    for c in ['peak_ccu','discount']:
        raw[c] = '0'
    for c in ['genres','developers','estimated_owners']:
        raw[c] = ''
    tags = pd.DataFrame({'app_id':['2','2','2','3'],'tag':['Indie','RPG','Indie','RPG']})
    with duckdb.connect() as con:
        con.register('raw_games',raw)
        con.register('raw_tags',tags)
        con.execute("CREATE TABLE settings AS SELECT DATE '2026-10-02' AS as_of")
        con.execute((ROOT/'sql/01_clean.sql').read_text(encoding='utf-8'))
        return con.sql('SELECT * FROM games ORDER BY app_id').df(), con.sql('SELECT * FROM game_tags').df()


def test_cleaning_and_zero_vs_missing(dataset):
    games, tags = dataset
    assert len(games) == 4
    assert games.app_id.is_unique
    assert pd.isna(games.loc[games.app_id.eq(1),'positive_rate'].iloc[0])
    assert pd.isna(games.loc[games.app_id.eq(4),'reviews'].iloc[0])
    assert pd.isna(games.loc[games.app_id.eq(4),'price'].iloc[0])
    assert games.loc[games.app_id.eq(2),'price_band'].iloc[0] == '[5,10)'
    assert games.loc[games.app_id.eq(3),'price_band'].iloc[0] == '[10,20)'
    assert len(tags) == 3


def test_multitag_filter_does_not_double_count(dataset):
    games, tags = dataset
    sample = filter_games(games,tags,(2020,2026),BANDS,['Indie','RPG'],0)
    assert sorted(sample.app_id) == [2,3]
    assert price_summary(sample,tags).games.sum() == 2
    assert filter_games(games,tags,(2020,2026),BANDS,[],100).app_id.tolist() == [2]
    assert filter_games(games,tags,(2020,2026),[],[],0).empty
    assert filter_games(games,tags,(2020,2026),BANDS,[],0,name='[').empty


def test_yoy_gaps_and_partial_year(dataset):
    games,tags = dataset
    trend = release_trend(games,tags,(2023,2026),2026).set_index('release_year')
    assert trend.loc[2024,'games'] == 0
    assert trend.loc[2024,'yoy'] == -1
    assert pd.isna(trend.loc[2025,'yoy'])
    assert pd.isna(trend.loc[2026,'yoy'])


def test_wilson_and_weighted_rate(dataset):
    games,tags = dataset
    b = games.set_index('app_id')
    assert b.loc[2,'wilson_lower'] > b.loc[3,'wilson_lower']
    ranked = tag_summary(games,tags,1).set_index('tag')
    assert ranked.loc['RPG','weighted_positive_rate'] == pytest.approx(91/101)
    assert ranked.loc['RPG','games'] == 2


def test_export_formula_protection():
    raw = pd.DataFrame({'name':['=1+1',' @SUM(A1)','Normal']})
    result = safe_csv(raw).decode('utf-8-sig')
    assert "'=1+1" in result and "' @SUM(A1)" in result

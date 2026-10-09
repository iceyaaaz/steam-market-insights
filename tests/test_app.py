import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest
from analytics import ROOT, load_data, filter_games, BANDS


def test_default_and_filters():
    at = AppTest.from_file(str(ROOT/'app.py'), default_timeout=60).run()
    assert not at.exception
    assert len(at.metric) == 4
    games,tags,_ = load_data()
    assert at.metric[0].value == f'{games.reviews.ge(100).sum():,}'
    at.sidebar.multiselect[1].set_value(['Indie','RPG']).run()
    assert not at.exception
    expected = filter_games(games,tags,(int(games.release_year.min()),int(games.release_year.max())),BANDS,['Indie','RPG'],100)
    assert at.metric[0].value == f'{len(expected):,}'
    at.sidebar.text_input[0].set_value('__no_such_game_123456789__').run()
    assert not at.exception
    assert len(at.warning) > 0
    assert len(at.metric) == 0


def test_zero_reviews_and_no_prices():
    at = AppTest.from_file(str(ROOT/'app.py'), default_timeout=60).run()
    at.sidebar.select_slider[0].set_value(0).run()
    assert not at.exception
    games,_,_ = load_data()
    assert at.metric[0].value == f'{len(games):,}'
    at.sidebar.multiselect[0].set_value([]).run()
    assert not at.exception
    assert len(at.metric) == 0


def test_real_source_record_regression():
    games,tags,_ = load_data()
    example = games.set_index('app_id').loc[496350]
    assert example.positive == 252 and example.negative == 3
    assert example.reviews == 255
    assert games.app_id.is_unique
    assert not tags.duplicated(['app_id','tag']).any()
    assert tags.app_id.isin(games.app_id).all()

"""Rebuild the deliverable from the fixed Kaggle archive; no API key required."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile
from datetime import datetime, timezone

import duckdb
import ijson
import pandas as pd

ROOT = Path(__file__).resolve().parent
VERSION = 52
AS_OF = '2026-10-02'
EXPECTED_SHA256 = '86804e6e581bb70dbfc814e483a3ba37f6ec4b879902a8bb727ed20486bdcabe'
URL = f'https://www.kaggle.com/api/v1/datasets/download/fronkongames/steam-games-dataset?datasetVersionNumber={VERSION}'
FIELDS = ['name', 'release_date', 'price', 'positive', 'negative', 'peak_ccu',
          'discount', 'genres', 'developers', 'estimated_owners']


def build(archive: Path, destination: Path = ROOT / 'data'):
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        temp = archive.with_suffix('.part')
        print('Downloading fixed Kaggle version 52...', flush=True)
        with urllib.request.urlopen(URL, timeout=90) as response, temp.open('wb') as out:
            shutil.copyfileobj(response, out)
        if not zipfile.is_zipfile(temp):
            raise ValueError('Download is not a ZIP archive; check Kaggle access.')
        temp.replace(archive)
    with archive.open('rb') as source_file:
        archive_sha256 = hashlib.file_digest(source_file, 'sha256').hexdigest()
    if archive_sha256 != EXPECTED_SHA256:
        raise ValueError('Archive SHA-256 differs from verified v52. Inspect the source before updating the fixed version.')
    destination.mkdir(parents=True, exist_ok=True)
    rows, tags = [], []
    with zipfile.ZipFile(archive) as z, z.open('games.json') as stream:
        for idx, (app_id, item) in enumerate(ijson.kvitems(stream, '')):
            missing = set(FIELDS + ['tags']) - item.keys()
            if missing:
                raise ValueError(f'Unexpected source schema for AppID {app_id}: missing {sorted(missing)}')
            row = {'app_id': app_id, 'source_row': idx}
            for field in FIELDS:
                value = item.get(field)
                row[field] = (' | '.join(map(str, value)) if isinstance(value, list)
                              else None if value is None else str(value))
            rows.append(row)
            tag_values = item.get('tags', [])
            if isinstance(tag_values, (dict, list)):
                tags.extend({'app_id': app_id, 'tag': str(tag)} for tag in tag_values)
    raw = pd.DataFrame(rows)
    raw_tags = pd.DataFrame(tags, columns=['app_id', 'tag'])
    con = duckdb.connect()
    con.register('raw_games', raw)
    con.register('raw_tags', raw_tags)
    con.execute('CREATE TABLE settings AS SELECT ?::DATE AS as_of', [AS_OF])
    con.execute((ROOT / 'sql/01_clean.sql').read_text(encoding='utf-8'))
    games = con.sql('SELECT * FROM games ORDER BY app_id').df()
    clean_tags = con.sql('SELECT * FROM game_tags ORDER BY app_id, tag').df()
    audit = con.sql('SELECT disposition, count(*) AS records FROM audited GROUP BY 1 ORDER BY 2 DESC').df()
    games.to_parquet(destination / 'games.parquet', index=False)
    clean_tags.to_parquet(destination / 'game_tags.parquet', index=False)
    audit.to_json(destination / 'audit.json', orient='records', force_ascii=False, indent=2)
    quality = {
        'raw_records': len(raw), 'included_games': len(games), 'tag_links': len(clean_tags),
        'distinct_tags': int(clean_tags.tag.nunique()),
        'zero_reviews': int(games.reviews.eq(0).sum()),
        'missing_reviews': int(games.reviews.isna().sum()),
        'missing_price': int(games.price.isna().sum()),
        'no_tags': int((~games.app_id.isin(clean_tags.app_id)).sum()),
        'discounted_games': int(games.discount.gt(0).sum()),
    }
    metadata = {
        'dataset': 'FronkonGames / Steam Games Dataset', 'author': 'Martin Bustos (FronkonGames)',
        'source_url': 'https://www.kaggle.com/datasets/fronkongames/steam-games-dataset',
        'download_url': URL, 'version': VERSION, 'source_updated': AS_OF,
        'as_of_note': 'Version update date; individual records may have different crawl times.',
        'retrieved_utc': datetime.now(timezone.utc).isoformat(),
        'archive_sha256': archive_sha256,
        'license': 'MIT (Kaggle dataset metadata)',
        'format_used': 'games.json', 'currency': 'USD (source scraper default US store region)',
        'csv_issue': 'v52 CSV header combines Discount and DLC count, shifting subsequent fields. JSON used instead.',
        'quality': quality,
    }
    (destination / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    con.close()
    print(json.dumps(quality, ensure_ascii=False, indent=2), flush=True)
    return games, clean_tags


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, default=ROOT / 'data/raw/steam-v52.zip')
    args = parser.parse_args()
    build(args.archive.resolve())

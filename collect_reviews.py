"""Collect a small, transparent review sample for qualitative research.

Raw third-party review text stays in a caller-specified scratch directory.
Do not commit it as if covered by the Kaggle dataset's license.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

APPS = {2714620:'Duck Detective: The Ghost of Glamping',1791590:'Sunset Hills'}


def collect(destination):
    destination.mkdir(parents=True,exist_ok=True)
    records, batches = [], []
    for app_id, name in APPS.items():
        for sentiment in ['positive','negative']:
            params = dict(json=1,filter='recent',language='all',review_type=sentiment,
                          purchase_type='all',num_per_page=10,filter_offtopic_activity=1)
            url = f'https://store.steampowered.com/appreviews/{app_id}?{urlencode(params)}'
            collected_at = datetime.now(timezone.utc)
            with urlopen(url,timeout=30) as response:
                payload = response.read()
            result = json.loads(payload)
            if result.get('success') != 1:
                raise RuntimeError(f'Unsuccessful API response: {app_id}/{sentiment}')
            raw = destination/f'{app_id}_{sentiment}.json'
            raw.write_bytes(payload)
            rows = result.get('reviews',[])
            batches.append(dict(app_id=app_id,group=sentiment,url=url,count=len(rows),
                collected_at=collected_at.isoformat(),sha256=hashlib.sha256(payload).hexdigest()))
            for index, review in enumerate(rows,1):
                assert review['voted_up'] == (sentiment=='positive')
                assert review['timestamp_created'] <= collected_at.timestamp()
                author = review['author']
                records.append(dict(sample_id=f'{"D" if app_id==2714620 else "S"}{"P" if sentiment=="positive" else "N"}{index:02}',
                    app_id=app_id,game=name,group=sentiment,review_id=review['recommendationid'],
                    url=f'https://steamcommunity.com/profiles/{author["steamid"]}/recommended/{app_id}/',
                    language=review['language'],created_utc=datetime.fromtimestamp(review['timestamp_created'],timezone.utc).isoformat(),
                    updated_utc=datetime.fromtimestamp(review['timestamp_updated'],timezone.utc).isoformat(),
                    playtime_at_review_minutes=author.get('playtime_at_review'),
                    early_access=review.get('written_during_early_access'),
                    steam_purchase=review.get('steam_purchase'),received_for_free=review.get('received_for_free'),
                    text=review['review']))
    assert len({row['review_id'] for row in records}) == len(records)
    (destination/'sample.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    (destination/'manifest.json').write_text(json.dumps(batches,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Collected {len(records)} reviews in {len(batches)} strata; raw text saved to {destination}')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    collect(parser.parse_args().output)

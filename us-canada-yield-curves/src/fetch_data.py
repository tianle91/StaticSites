"""Explicit refresh of official US Treasury and Bank of Canada yields."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from staticsites.pipeline import write_snapshot
from staticsites.sources import get_response

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'curves.json'
TREASURY = 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml'
BOC = 'https://www.bankofcanada.ca/valet/observations'
SOFR = 'https://markets.newyorkfed.org/api/rates/secured/sofr/search.json'
OVERNIGHT_SOURCES = [
    {'name': 'New York Fed · SOFR', 'url': 'https://www.newyorkfed.org/markets/reference-rates/sofr/'},
    {'name': 'Bank of Canada · CORRA', 'url': 'https://www.bankofcanada.ca/rates/interest-rates/corra/'},
]
TENORS = [
    ('1M', 1/12, 'BC_1MONTH', 'TB.CDN.30D.MID'),
    ('2M', 2/12, 'BC_2MONTH', 'TB.CDN.60D.MID'),
    ('3M', 3/12, 'BC_3MONTH', 'TB.CDN.90D.MID'),
    ('6M', 6/12, 'BC_6MONTH', 'TB.CDN.180D.MID'),
    ('1Y', 1, 'BC_1YEAR', 'TB.CDN.1Y.MID'),
    ('2Y', 2, 'BC_2YEAR', 'BD.CDN.2YR.DQ.YLD'),
    ('3Y', 3, 'BC_3YEAR', 'BD.CDN.3YR.DQ.YLD'),
    ('5Y', 5, 'BC_5YEAR', 'BD.CDN.5YR.DQ.YLD'),
    ('7Y', 7, 'BC_7YEAR', 'BD.CDN.7YR.DQ.YLD'),
    ('10Y', 10, 'BC_10YEAR', 'BD.CDN.10YR.DQ.YLD'),
    ('30Y*', 30, 'BC_30YEAR', 'BD.CDN.LONG.DQ.YLD'),
]
SOURCES = [
    {'name': 'Bank of Canada · daily money-market yields',
     'url': 'https://www.bankofcanada.ca/rates/interest-rates/money-market-yields/'},
    {'name': 'US Treasury · daily par yield curve rates',
     'url': 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve'},
    {'name': 'Bank of Canada · selected benchmark bond yields',
     'url': 'https://www.bankofcanada.ca/rates/interest-rates/canadian-bonds/'},
]


def yield_value(value):
    """Reject malformed and nonfinite observations, keeping genuine zero yields."""
    number = float(value)
    if not math.isfinite(number) or not -10 <= number <= 50:
        raise ValueError('Invalid yield: ' + str(value))
    return number


def parse_treasury(content):
    rows = {}
    for entry in ET.fromstring(content).findall('{http://www.w3.org/2005/Atom}entry'):
        props = entry.find('.//{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}properties')
        if props is None:
            raise ValueError('Treasury entry has no properties')
        values = {node.tag.rsplit('}', 1)[-1]: node.text for node in props}
        day = date.fromisoformat(values['NEW_DATE'][:10]).isoformat()
        if any(values.get(tenor[2]) not in (None, '') for tenor in TENORS):
            curve = [yield_value(values[tenor[2]]) if values.get(tenor[2]) not in (None, '') else None
                     for tenor in TENORS]
            if day in rows:
                raise ValueError('Duplicate Treasury date: ' + day)
            rows[day] = curve
    if not rows:
        raise ValueError('Treasury feed contains no curve observations')
    return rows


def parse_canada(payload):
    keys = [tenor[3] for tenor in TENORS]
    details = payload.get('seriesDetail', {})
    if not all(key in details for key in keys):
        raise ValueError('Bank of Canada feed is missing required series')
    rows = {}
    for observation in payload.get('observations', []):
        day = date.fromisoformat(observation['d']).isoformat()
        values = [observation.get(key, {}).get('v') for key in keys]
        if any(value not in (None, '') for value in values):
            if day in rows:
                raise ValueError('Duplicate Bank of Canada date: ' + day)
            rows[day] = [yield_value(value) if value not in (None, '') else None for value in values]
    if not rows:
        raise ValueError('Bank of Canada feed contains no curve observations')
    return rows


def parse_sofr(payload):
    rows = {}
    for row in payload.get('refRates', []):
        if row.get('type') != 'SOFR':
            raise ValueError('Unexpected overnight rate type')
        day = date.fromisoformat(row['effectiveDate']).isoformat()
        if day in rows:
            raise ValueError('Duplicate SOFR date: ' + day)
        rows[day] = yield_value(row['percentRate'])
    if not rows:
        raise ValueError('SOFR feed has no observations')
    return rows


def parse_corra(payload):
    if 'AVG.INTWO' not in payload.get('seriesDetail', {}):
        raise ValueError('Bank of Canada feed is missing CORRA')
    rows = {}
    for row in payload.get('observations', []):
        value = row.get('AVG.INTWO', {}).get('v')
        if value in (None, ''):
            continue
        day = date.fromisoformat(row['d']).isoformat()
        if day in rows:
            raise ValueError('Duplicate CORRA date: ' + day)
        rows[day] = yield_value(value)
    if not rows:
        raise ValueError('CORRA feed has no observations')
    return rows


def complete_curves(rows):
    return {day: values for day, values in rows.items() if all(value is not None for value in values)}


def assemble(us, canada, today):
    us, canada = complete_curves(us), complete_curves(canada)
    shared = sorted(set(us) & set(canada))
    if not shared:
        raise ValueError('No complete trading date shared by both sources')
    day = shared[-1]
    age = (today - date.fromisoformat(day)).days
    if not 0 <= age <= 14:
        raise ValueError('Latest common curve is future-dated or more than 14 days old')
    return {
        'date': day,
        'latest_available': {'us': max(us), 'canada': max(canada)},
        'tenors': [{'label': label, 'years': years} for label, years, _, _ in TENORS],
        'series': [
            {'id': 'us', 'name': 'United States', 'color': '#116965', 'yields': us[day]},
            {'id': 'canada', 'name': 'Canada', 'color': '#aa5633', 'yields': canada[day]},
        ],
        'sources': SOURCES,
    }


def validate_history(history):
    if set(history) != {'us', 'canada'}:
        raise ValueError('History requires both countries')
    for observations in history.values():
        if not isinstance(observations, dict) or not observations:
            raise ValueError('History must contain dated curves')
        for day, values in observations.items():
            if date.fromisoformat(day).isoformat() != day or len(values) != len(TENORS):
                raise ValueError('Invalid historical curve')
            if not any(value is not None for value in values):
                raise ValueError('Historical curve has no observations')
            for value in values:
                if value is None:
                    continue
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError('Historical yields must be numbers')
                yield_value(value)
    return history


def build_snapshot(us, canada, sofr, corra, today):
    history = validate_history({
        'us': dict(sorted(us.items())),
        'canada': dict(sorted(canada.items())),
    })
    result = assemble(history['us'], history['canada'], today)
    result['history'] = history
    result['overnight_history'] = {
        'us': dict(sorted(sofr.items())),
        'canada': dict(sorted(corra.items())),
    }
    result['overnight_sources'] = OVERNIGHT_SOURCES
    result['coverage'] = coverage(result)
    return validate_dataset(result)


def validate_dataset(data):
    day = date.fromisoformat(data['date']).isoformat()
    if data['tenors'] != [{'label': label, 'years': years} for label, years, _, _ in TENORS]:
        raise ValueError('Unexpected maturity grid')
    if [series['id'] for series in data['series']] != ['us', 'canada']:
        raise ValueError('Both countries are required')
    for series in data['series']:
        if len(series['yields']) != len(TENORS):
            raise ValueError('Incomplete country curve')
        for value in series['yields']:
            yield_value(value)
        if date.fromisoformat(data['latest_available'][series['id']]).isoformat() < day:
            raise ValueError('Invalid source coverage')
    if data['sources'] != SOURCES:
        raise ValueError('Unexpected sources')
    if 'history' in data:
        history = validate_history(data['history'])
        shared = set(complete_curves(history['us'])) & set(complete_curves(history['canada']))
        if not shared or data['date'] != max(shared):
            raise ValueError('Displayed date must match latest common historical date')
        for series in data['series']:
            observations = history[series['id']]
            if series['yields'] != observations[day]:
                raise ValueError('Displayed curve differs from history')
            if data['latest_available'][series['id']] != max(complete_curves(observations)):
                raise ValueError('Source coverage differs from history')
    if 'overnight_history' in data:
        history = data['overnight_history']
        if set(history) != {'us', 'canada'} or data.get('overnight_sources') != OVERNIGHT_SOURCES:
            raise ValueError('Overnight history requires both countries and source definitions')
        for rows in history.values():
            if not isinstance(rows, dict) or not rows:
                raise ValueError('Overnight history must contain dated rates')
            for day, value in rows.items():
                if date.fromisoformat(day).isoformat() != day:
                    raise ValueError('Invalid overnight observation date')
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError('Overnight rates must be numbers')
                yield_value(value)
    if 'coverage' in data and data['coverage'] != coverage(data):
        raise ValueError('Coverage metadata differs from observations')
    return data


def series_coverage(rows):
    days = sorted(rows)
    return {'start': days[0] if days else None, 'end': days[-1] if days else None, 'observations': len(days)}


def coverage(data):
    return {
        'curves': {
            country: {tenor[0]: series_coverage({day: values[index] for day, values in rows.items()
                                               if values[index] is not None})
                      for index, tenor in enumerate(TENORS)}
            for country, rows in data['history'].items()
        },
        'overnight': {country: series_coverage(rows) for country, rows in data.get('overnight_history', {}).items()},
    }


def fetch_treasury_year(year):
    response = get_response(TREASURY, params={
        'data': 'daily_treasury_yield_curve', 'field_tdr_date_value': str(year),
    }, attempts=3)
    rows = parse_treasury(response.content)
    if any(date.fromisoformat(day).year != year for day in rows):
        raise ValueError('Treasury response contains dates outside requested year')
    print(f'Treasury {year} · {len(rows)} dates', flush=True)
    return rows


def main(start_date=None):
    today = date.today()
    since = start_date or date(1990, 1, 1)
    if not date(1990, 1, 1) <= since <= today:
        raise ValueError('Start date must be between 1990-01-01 and today')
    us = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        for rows in executor.map(fetch_treasury_year, range(since.year, today.year + 1)):
            us.update(rows)
    keys = ','.join([tenor[3] for tenor in TENORS] + ['AVG.INTWO'])
    response = get_response(f'{BOC}/{keys}/json', params={'start_date': since.isoformat()}, attempts=3)
    canadian_data = response.json()
    canada = parse_canada(canadian_data)
    corra = parse_corra(canadian_data)
    response = get_response(SOFR, params={'startDate': max(since, date(2018, 4, 2)).isoformat(),
                                          'endDate': today.isoformat()}, attempts=3)
    sofr = parse_sofr(response.json())
    us = {day: values for day, values in us.items() if day >= since.isoformat()}
    data = build_snapshot(us, canada, sofr, corra, today)
    changed = write_snapshot(OUT, data)
    print(('Wrote ' if changed else 'Unchanged ') + str(OUT) + ' · ' + data['date'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start-date', type=date.fromisoformat, help='History start date (default 1990-01-01)')
    main(parser.parse_args().start_date)

"""Fetch required sources, validate completely, then publish a single JSON file.

Accessible CMHC tables preserve published chart precision. TRREB PDF tables need
layout extraction: plain extraction can reverse columns and reorder headings.
"""
from __future__ import annotations

import calendar
from datetime import datetime, timezone
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from pypdf import PdfReader
import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data'
REPORT = 'https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-research/research-reports/housing-finance/residential-mortgage-industry-report'
MARKET = 'https://public.trreb.ca/market-data/market-watch/'
HISTORIC = 'https://public.trreb.ca/wp-content/files/market-stats/market-watch/historic.pdf'
ARCHIVE = 'https://public.trreb.ca/wp-content/files/market-stats/market-watch/mw{}12.pdf'
MONTHS = list(calendar.month_name)[1:]


def point(period, value, status='observed', source=None):
    result = {'period': period, 'value': float(value), 'status': status}
    if source:
        result['source'] = source
    return result


def cmhc_table(soup, caption):
    matches = [t for t in soup.select('table') if t.caption and
               t.caption.get_text(' ', strip=True).startswith(caption)]
    if len(matches) != 1:
        raise ValueError(f'Expected one CMHC table: {caption}; found {len(matches)}')
    return [[c.get_text(' ', strip=True).replace('\xa0', ' ')
             for c in row.select('th,td')] for row in matches[0].select('tr')]


def quarterly_group(soup, group_id, title, caption, note, source, minimum):
    rows = cmhc_table(soup, caption)
    series = [{'name': name.replace(' †', ''), 'points': []} for name in rows[0][1:]]
    for row in rows[1:]:
        match = re.fullmatch(r'(\d{4}) Q([1-4])\*?', row[0])
        if not match or len(row) != len(series) + 1:
            raise ValueError(f'Malformed quarterly row in {group_id}: {row}')
        period = f'{match[1]}-Q{match[2]}'
        for item, value in zip(series, row[1:]):
            item['points'].append(point(period, value))
    if len(series[0]['points']) < minimum:
        raise ValueError(f'Truncated CMHC history: {group_id}')
    return {'id': group_id, 'title': title, 'unit': '%', 'frequency': 'Quarterly',
            'note': note, 'source': source, 'series': series}


def parse_cmhc(html):
    soup = BeautifulSoup(html, 'html.parser')
    if not soup.h1 or 'Fall 2026' not in soup.h1.get_text():
        raise ValueError('CMHC edition changed; review definitions before updating the Fall 2026 parser')
    groups = [quarterly_group(soup, *spec) for spec in [
        ('provinces', 'Provincial mortgage arrears', 'Mortgage Arrears (90+ Days',
         '90+ days overdue. CBA-member bank mortgages; share of mortgage accounts. Ontario is a province, not the Toronto CMA or GTHA. Quarterly figures are kept separate from the monthly forecast table.',
         'CMHC; Canadian Bankers Association, Figure 1', 120),
        ('lenders', 'Mortgage arrears by lender type', 'Mortgage Delinquency (90+ days) by Lender Type',
         'Canada-wide reported 90+ day delinquency rates. Lender populations and source coverage differ. MIEs include mortgage investment corporations and other private entities; this is not the GTHA balance-weighted series.',
         'CMHC; regulatory reporting, Statistics Canada and CBA, Figure 7', 24),
        ('private', 'Private-lender stress in the GTHA', 'Dollar-Weighted 90+ Day Arrears Rate',
         'Mortgage investment entities (MIEs), 90+ days overdue, weighted by outstanding mortgage balance. 11.14% of balances does not mean one in nine loans. GTHA includes Hamilton; rest of Canada excludes the GTHA.',
         'CMHC; Statistics Canada Survey of Non-Bank Mortgage Lenders, Figure 8', 10),
        ('consumer', 'Other household credit delinquencies', 'Delinquency Rate (90+ days) for Non-Mortgage Credit',
         'Canada-wide 90+ day delinquency rates across consumers, not just mortgage holders. LOC = line of credit; HELOC = home equity line of credit.',
         'CMHC; Equifax, Figure 3', 48),
    ]]
    rows = cmhc_table(soup, 'Mortgage Delinquency Rates Forecast in Selected Provinces')
    series = [{'name': name, 'points': []} for name in rows[0][1:]]
    for row in rows[1:]:
        forecast = '(forecast)' in row[0]
        date = datetime.strptime(row[0].replace(' (forecast)', ''), '%b %Y')
        for item, value in zip(series, row[1:], strict=True):
            item['points'].append(point(date.strftime('%Y-%m'), value,
                                        'forecast' if forecast else 'observed'))
    if len(series[0]['points']) < 70 or not any(p['status'] == 'forecast' for p in series[0]['points']):
        raise ValueError('Monthly CMHC outlook table is incomplete')
    groups.append({'id': 'outlook', 'title': 'Monthly arrears and CMHC outlook', 'unit': '%',
                   'frequency': 'Monthly', 'source': 'CMHC; CBA, Statistics Canada, Figure 13',
                   'note': 'Fall 2026 forecast vintage. Solid lines are observed; dashed lines are forecasts, not outcomes. The forecast horizon is not a prediction of when house prices will bottom. Monthly observations differ from quarterly averages.',
                   'series': series})
    return groups


def parse_annual(content):
    text = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(content)).pages)
    matches = re.findall(r'(?m)^\s*((?:19|20)\d{2})\s+[\d,]+\s+\$([\d,]+)\s*$', text)
    values = {year: int(value.replace(',', '')) for year, value in matches}
    if len(values) < 40 or '1996' not in values or '2022' not in values:
        raise ValueError('TRREB annual history missing or malformed')
    return [point(year, value) for year, value in sorted(values.items())]


def parse_monthly(content, source):
    text = PdfReader(BytesIO(content)).pages[-1].extract_text(extraction_mode='layout')
    return parse_monthly_text(text, source)


def parse_monthly_text(text, source):
    current_year = None
    values = {}
    for line in text.splitlines():
        # Fonts sometimes have missing glyphs in 'Statistics'; match the stable word.
        if 'Monthly' in line or 'MONTHLY' in line:
            years = re.findall(r'\b20\d{2}', line)
            if years:
                current_year = years[0]
        match = re.match(r'^\s*(' + '|'.join(MONTHS) + r')\s+([\d,]+)\s+\$?([\d,]+)(?:\s|$)', line)
        if match and current_year:
            month, sales, price = match.groups()
            price = int(price.replace(',', ''))
            if not 100_000 < price < 5_000_000 or int(sales.replace(',', '')) <= 0:
                raise ValueError(f'Implausible TRREB monthly row: {line}')
            period = f'{current_year}-{MONTHS.index(month) + 1:02}'
            if period in values:
                raise ValueError(f'Duplicate TRREB monthly observation: {period}')
            values[period] = point(period, price, source=source)
    if len(values) < 12:
        raise ValueError(f'Incomplete TRREB monthly table: {source}')
    return values


def validate_dataset(data):
    ids = [g['id'] for g in data['groups']]
    if len(ids) != len(set(ids)) or len(ids) < 7:
        raise ValueError('Missing or duplicate metric groups')
    for group in data['groups']:
        for series in group['series']:
            periods = [p['period'] for p in series['points']]
            if not periods or periods != sorted(set(periods)):
                raise ValueError(f"Unsorted or duplicate periods: {series['name']}")
            # Missing quarters/months must fail, not disappear behind a connecting line.
            def ordinal(period):
                if group['frequency'] == 'Quarterly':
                    year, quarter = period.split('-Q')
                    return int(year) * 4 + int(quarter) - 1
                if group['frequency'] == 'Monthly':
                    year, month = period.split('-')
                    return int(year) * 12 + int(month) - 1
                return int(period)
            ordinals = [ordinal(period) for period in periods]
            if any(b - a != 1 for a, b in zip(ordinals, ordinals[1:])):
                raise ValueError(f"Gap in {series['name']}")
            for p in series['points']:
                if not math.isfinite(p['value']) or p['value'] < 0 or (group['unit'] == '%' and p['value'] > 100):
                    raise ValueError(f'Invalid value: {p}')
                if p['status'] not in {'observed', 'forecast'}:
                    raise ValueError(f'Invalid observation status: {p}')
    return data


def publish(data, target):
    """Unchanged records retain bytes/mtime; failures never publish partial data."""
    validate_dataset(data)
    previous = json.loads(target.read_text()) if target.exists() else None
    if previous and {k: v for k, v in previous.items() if k != 'retrieved_at'} == data:
        return False
    data = {**data, 'retrieved_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    encoded = (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(dir=target.parent, prefix='.series-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(encoded)
        os.replace(path, target)
    finally:
        if os.path.exists(path):
            os.unlink(path)
    return True


def collect(get):
    groups = parse_cmhc(get(REPORT).text)
    annual = parse_annual(get(HISTORIC).content)
    sources = [{'name': 'CMHC Residential Mortgage Industry Report, Fall 2026', 'url': REPORT},
               {'name': 'TRREB Historic Statistics — annual sales and average price', 'url': HISTORIC},
               {'name': 'TRREB Market Watch — latest report and coverage-change notice', 'url': MARKET}]
    market = BeautifulSoup(get(MARKET).text, 'html.parser')
    # Discover the latest well-formed report URL, not a month guessed from today.
    candidates = {}
    for link in market.select('a[href]'):
        match = re.search(r'/mw(\d{2})(\d{2})\.pdf$', link['href'])
        if match and 1 <= int(match[2]) <= 12:
            candidates[match[1] + match[2]] = urljoin(MARKET, link['href'])
    if not candidates:
        raise ValueError('Latest TRREB report link not found')
    latest_key = max(candidates)
    latest = candidates[latest_key]
    report_year, report_month = 2000 + int(latest_key[:2]), int(latest_key[2:])
    terminal_period = f'{report_year}-{report_month:02}'
    latest_periods = [f'{year}-{month:02}' for year in (report_year - 1, report_year)
                      for month in range(1, 13) if f'{year}-{month:02}' <= terminal_period]
    monthly = {}
    # Newer report revisions win; preserve per-point source URLs and coverage break.
    for url in [ARCHIVE.format('21'), ARCHIVE.format('23'), ARCHIVE.format('25'), latest]:
        parsed = parse_monthly(get(url).content, url)
        if url == latest and sorted(parsed) != latest_periods:
            raise ValueError(f'Latest TRREB report must cover January {report_year - 1} '
                             f'through {terminal_period}: {url}')
        if url != latest and len(parsed) != 24:
            raise ValueError(f'Year-end report must contain 24 monthly rows: {url}')
        monthly.update(parsed)
        sources.append({'name': 'TRREB Market Watch — ' + url.rsplit('/', 1)[-1], 'url': url})
    periods = sorted(monthly)
    expected = [f'{year}-{month:02}' for year in range(2020, report_year + 1)
                for month in range(1, 13) if f'{year}-{month:02}' <= terminal_period]
    if periods != expected:
        raise ValueError('TRREB monthly price history has a gap')
    groups += [
        {'id': 'prices', 'title': 'Toronto-area monthly sale prices', 'unit': 'CAD', 'frequency': 'Monthly',
         'source': 'Toronto Regional Real Estate Board, Market Watch monthly tables',
         'note': 'Nominal average sale price, not a quality-adjusted HPI and not seasonally adjusted. Legacy reports (2020–2023) and expanded board coverage (2024 onward) are separate lines. Sales mix, market boundaries and revisions affect comparisons; do not calculate a cross-break return.',
         'series': [{'name': name, 'points': [monthly[p] for p in periods if (p < '2024') == legacy]}
                    for name, legacy in [('Legacy TRREB coverage (2020–2023)', True),
                                         ('Expanded TRREB coverage (2024 onward)', False)]]},
        {'id': 'annual', 'title': 'Toronto-area annual sale prices', 'unit': 'CAD', 'frequency': 'Annual',
         'source': 'Toronto Regional Real Estate Board, Historic Statistics',
         'note': 'Nominal annual average sale price. TRREB warns that its market area changes over time and history is revised. Annual averages hide within-year troughs, including the 2008–2009 downturn. These prices cannot establish a precise arrears-to-price-bottom lag.',
         'series': [{'name': 'TRREB annual average sale price', 'points': annual}]},
    ]
    for group in groups:
        group['source_url'] = HISTORIC if group['id'] == 'annual' else MARKET if group['id'] == 'prices' else REPORT
    return validate_dataset({'schema_version': 1, 'sources': sources, 'groups': groups,
        'gaps': [
            {'metric': 'Power-of-sale listings', 'detail': 'No verified, consistently defined public historical series has been obtained. The reported 600+ figure is excluded.'},
            {'metric': 'Active listing inventory', 'detail': 'Available in individual TRREB monthly reports, but a consistent historical series has not yet been assembled. The roughly 26,000 figure is not plotted as a time series.'},
            {'metric': 'Comparable resale benchmark / HPI', 'detail': 'This version uses TRREB average prices. A consistently revised monthly benchmark series is still needed for a stronger cycle-timing study.'},
        ]})


def main():
    session = requests.Session()
    session.headers['User-Agent'] = 'StaticSites-mortgage-research/1.0'

    def get(url):
        print(f'Fetching {url}', flush=True)
        response = session.get(url, timeout=(15, 90))
        response.raise_for_status()
        return response

    data = collect(get)
    changed = publish(data, DATA_DIR / 'series.json')
    print('Updated series.json' if changed else 'Source records unchanged; preserved series.json')


if __name__ == '__main__':
    main()

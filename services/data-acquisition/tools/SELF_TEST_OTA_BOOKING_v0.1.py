from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / 'acquisition', ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from ota_techniques import booking_search_records, audit_booking_runs, default_query_context

context = {
    'destination_or_property': 'Bangkok', 'check_in': '2026-09-28', 'check_out': '2026-09-29',
    'occupancy': {'adults': 2, 'children': 0, 'rooms': 1}, 'currency': 'THB'
}

def card(slug, title, price, address='Bangkok'):
    return f'''<div data-testid="property-card">
      <a data-testid="title-link" href="/hotel/th/{slug}.html"><div data-testid="title">{title}</div></a>
      <span data-testid="address">{address}</span>
      <div data-testid="review-score">Scored 8.7 1,234 reviews</div>
      <span data-testid="price-and-discounted-price">THB {price:,}</span>
    </div>'''

html = '<html><body>' + ''.join([
    card('alpha-hotel', 'Alpha Hotel', 2500), card('bravo-resort', 'Bravo Resort', 3100),
    card('charlie-suites', 'Charlie Suites', 4200), card('delta-inn', 'Delta Inn', 1800),
    card('echo-bangkok', 'Echo Bangkok', 2900), card('foxtrot-house', 'Foxtrot House', 3600),
]) + '</body></html>'

first = booking_search_records(html, context, 'https://www.booking.com/searchresults.html')
second = booking_search_records(html, context, 'https://www.booking.com/searchresults.html')
props = [x for x in first['records'] if x['record_type'] == 'PropertyCandidate']
rates = [x for x in first['records'] if x['record_type'] == 'RateObservation']
assert len(props) == 6 and len(rates) == 6
assert rates[0]['currency'] == 'THB' and rates[0]['price'] == 2500
assert rates[0]['check_in'] == '2026-09-28' and rates[0]['occupancy']['adults'] == 2
assert props[0]['provenance'] == 'booking-public-search-card'

audit = audit_booking_runs({'ok': True, 'records': first['records'], 'query_context': context},
                           {'ok': True, 'records': second['records'], 'query_context': context})
assert audit['audit_passed'] is True
assert audit['repeatability']['property_repeatability_pct'] == 100.0

# Price without query context is never accepted as a RateObservation.
no_ctx = booking_search_records(html, {'destination_or_property': 'Bangkok'}, 'https://www.booking.com/city/th/bangkok.html')
assert len([x for x in no_ctx['records'] if x['record_type'] == 'RateObservation']) == 0

# Wrong currency must preserve property discovery but reject the rate.
usd_html = html.replace('THB 2,500', 'US$ 75')
usd = booking_search_records(usd_html, context, 'https://www.booking.com/searchresults.html')
alpha_rates = [x for x in usd['records'] if x['record_type']=='RateObservation' and x.get('property_id')=='alpha-hotel']
assert alpha_rates == []

ctx = default_query_context('Bangkok', today=__import__('datetime').date(2026, 8, 29), days_ahead=30, nights=2)
assert ctx['check_in'] == '2026-09-28' and ctx['check_out'] == '2026-09-30'
print('OTA Booking public search technique: PASS')

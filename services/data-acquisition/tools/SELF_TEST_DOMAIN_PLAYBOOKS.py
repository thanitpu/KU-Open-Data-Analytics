from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from control_plane.domain_playbooks import playbook, ranked_patterns, recommended_sequence

pb = playbook('Supermarket')
assert pb.get('required_business_tracks') == ['product_price', 'promotion', 'discovery']
product = ranked_patterns('supermarket', clues=['graphql', 'api_candidate'], track='product_price')
ids = [x['pattern_id'] for x in product]
assert ids[0] in {'graphql_catalog', 'public_catalog_api'}
assert ids.index('generic_html_last_resort') == len(ids) - 1

discovery = ranked_patterns('supermarket', clues=['cloud_access_blocked', 'indexed_product_urls'], track='discovery')
search = next(x for x in discovery if x['pattern_id'] == 'search_index_discovery')
assert 'Discovery only' in search.get('restriction', '')
seq = recommended_sequence('supermarket', clues=['product_sitemap'])
assert set(seq['tracks']) == {'product_price', 'promotion', 'discovery'}
assert seq['quality_gates']['price_completeness_pct'] == 80
assert any(x.get('action') == 'prefer_edge_runner' for x in seq['environment_rules'])

ota = recommended_sequence('Online Travel Agencies', clues=['search_api', 'availability', 'promotion'])
assert set(ota['tracks']) == {'property_offer', 'rate_availability', 'promotion_benefit', 'discovery'}
assert set(ota['observation_context_required']) >= {'check_in', 'check_out', 'occupancy', 'currency'}
rate_ids = [x['pattern_id'] for x in ota['tracks']['rate_availability']]
assert rate_ids[0] in {'ota_public_search_api', 'ota_rate_calendar'}

coffee = recommended_sequence('Cafe', clues=['menu_api', 'menu_cards'])
assert set(coffee['tracks']) == {'menu_price', 'promotion', 'discovery'}
menu_ids = [x['pattern_id'] for x in coffee['tracks']['menu_price']]
assert menu_ids[0] == 'coffee_public_menu_api'
assert playbook('coffee shop').get('label') == 'Coffee Chain / Cafe'

qdiving = recommended_sequence('Q-diving', clues=['rss', 'article_cards', 'youtube'])
assert set(qdiving['tracks']) == {'content_index', 'content_metadata', 'discovery'}
content_ids = [x['pattern_id'] for x in qdiving['tracks']['content_index']]
assert content_ids[0] == 'diving_rss_feed'
assert playbook('scuba diving').get('label') == 'Q-diving / Scuba Knowledge and Community'

print('Domain playbook ranking: PASS')

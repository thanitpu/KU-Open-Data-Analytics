from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT/'acquisition',ROOT):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from qdiving_techniques import padi_rss_records,audit_padi_runs

items=[]
for i in range(1,7):
    items.append(f'''<item><title>Diving Story {i}</title><link>https://blog.padi.com/diving-story-{i}/</link><pubDate>Fri, {20+i:02d} Aug 2026 10:00:00 +0000</pubDate><dc:creator><![CDATA[Author {i}]]></dc:creator><category><![CDATA[Diving]]></category><description><![CDATA[<p>Useful scuba diving story {i}</p>]]></description></item>''')
xml='''<?xml version="1.0"?><rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>'''+''.join(items)+'''</channel></rss>'''
rows=padi_rss_records(xml,observed_at='2026-08-29T00:00:00+00:00')
assert len(rows)==6 and rows[0]['title']=='Diving Story 1' and rows[0]['author']=='Author 1'
assert rows[0]['published_at'].startswith('2026-08-21') and rows[0]['provenance']=='padi-rss-feed'
a=audit_padi_runs({'ok':True,'records':rows},{'ok':True,'records':rows})
assert a['audit_passed'] is True and a['repeatability']['content_repeatability_pct']==100.0
print('Q-diving PADI public feed technique: PASS')

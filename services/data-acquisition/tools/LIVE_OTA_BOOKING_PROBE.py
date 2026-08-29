from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / 'acquisition', ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from ota_techniques import booking_public_search, default_query_context, audit_booking_runs


def compact_run(run: dict) -> dict:
    records = run.get('records') or []
    return {
        'ok': run.get('ok'), 'status': run.get('status'), 'source_url': run.get('source_url'),
        'final_url': run.get('final_url'), 'bytes': run.get('bytes'), 'query_context': run.get('query_context'),
        'diagnostics': run.get('diagnostics'), 'error': run.get('error'), 'elapsed_seconds': run.get('elapsed_seconds'),
        'sample_records': records[:12],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--destination', default='Bangkok')
    ap.add_argument('--days-ahead', type=int, default=30)
    ap.add_argument('--nights', type=int, default=1)
    ap.add_argument('--repeat-delay', type=float, default=12.0)
    ap.add_argument('--output', default='validation/ota-booking-live.json')
    args = ap.parse_args()

    context = default_query_context(args.destination, days_ahead=args.days_ahead, nights=args.nights,
                                    adults=2, rooms=1, children=0, currency='THB')
    first = booking_public_search(context, timeout=18)
    # Repeatability must not be tested by hammering the same public search endpoint.
    # A deliberate pause is part of the source access profile, not an anti-bot bypass.
    delay = max(8.0, min(30.0, float(args.repeat_delay)))
    time.sleep(delay)
    second = booking_public_search(context, timeout=18)
    audit = audit_booking_runs(first, second)
    payload = {
        'schema': 'ku2d.ota-booking-live-evidence.v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'execution_environment': 'cloud-hosted-public-read-only',
        'source': 'Booking.com',
        'technique': 'booking_public_search',
        'query_context': context,
        'repeat_delay_seconds': delay,
        'first_run': compact_run(first),
        'second_run': compact_run(second),
        'audit': audit,
        'approval_status': 'eligible-for-human-review' if audit.get('audit_passed') else 'not-approved',
        'guardrail': 'This probe cannot approve or store production data. It tests public search results only with explicit dates, occupancy and currency and uses a bounded respectful repeat delay.',
    }
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'repeat_delay_seconds': delay, 'first': first.get('diagnostics'), 'second': second.get('diagnostics'),
        'audit_passed': audit.get('audit_passed'), 'hard_failures': audit.get('hard_failures'),
        'repeatability': audit.get('repeatability')
    }, ensure_ascii=False, indent=2))
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()

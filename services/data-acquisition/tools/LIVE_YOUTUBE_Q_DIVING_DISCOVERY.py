"""Explicit, bounded Q-Diving YouTube metadata pilot. Not scheduled by CI."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "acquisition", ROOT / "acquisition" / "providers"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from youtube_data_api import YouTubeDataAPI, YouTubeProviderError, load_policy
from youtube_source_foundation import discover, select_query_profiles


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Bounded, metadata-only Q-Diving YouTube Data API discovery")
    p.add_argument("--profile", action="append", dest="profiles", required=True,
                   help="Approved query_profile_id; repeat for multiple profiles")
    p.add_argument("--max-results", type=int, default=10)
    p.add_argument("--max-pages", type=int, default=1)
    p.add_argument("--max-search-calls", type=int, default=8)
    p.add_argument("--quota-budget", type=int, default=50)
    p.add_argument("--endpoint", default="discovery")
    p.add_argument("--no-approve", action="store_true")
    p.add_argument("--no-production-store", action="store_true")
    p.add_argument("--output", type=Path)
    return p


def validate_options(args, *, policy=None, environ=None) -> None:
    policy = policy or load_policy()
    env = os.environ if environ is None else environ
    if not str(env.get("KU2D_YOUTUBE_API_KEY") or "").strip():
        raise ValueError("KU2D_YOUTUBE_API_KEY is not configured.")
    if args.endpoint != "discovery":
        raise ValueError("Only the metadata discovery endpoint is supported.")
    if not args.no_approve or not args.no_production_store:
        raise ValueError("This foundation requires --no-approve and --no-production-store.")
    limits = policy["pilot_limits"]
    if args.max_results < 1 or args.max_results > int(limits["max_results_per_search"]):
        raise ValueError("--max-results exceeds the configured pilot limit.")
    if args.max_pages < 1 or args.max_pages > int(limits["max_pages_per_query"]):
        raise ValueError("--max-pages exceeds the configured pilot limit.")
    selected_count = len(set(args.profiles or []))
    if args.max_search_calls < selected_count or args.max_search_calls > int(limits["max_query_profiles"]):
        raise ValueError("--max-search-calls must cover selected profiles and stay within the pilot limit.")
    if args.quota_budget < 1:
        raise ValueError("--quota-budget must be positive.")


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        policy = load_policy()
        validate_options(args, policy=policy)
        profiles = select_query_profiles(args.profiles, policy=policy)
        provider = YouTubeDataAPI(policy=policy, quota_budget=args.quota_budget)
        result = discover(provider, profiles, max_search_calls=args.max_search_calls, max_pages_per_query=args.max_pages,
                          max_results=args.max_results, policy=policy)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({
            "schema": result["schema"], "video_count": len(result["videos"]),
            "channel_count": len(result["channels"]), "quality_passed": result["quality_report"]["passed"],
            "review_stage": result["review_stage"], "approved": result["approved"],
            "production_store": result["production_store"], "output": str(args.output) if args.output else None,
        }, ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, YouTubeProviderError) as exc:
        print(f"YouTube discovery refused or failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

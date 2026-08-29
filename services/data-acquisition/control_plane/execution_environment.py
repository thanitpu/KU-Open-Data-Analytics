from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PROFILE_FILE = ROOT / "config" / "execution_environment_profiles.json"


def load_profiles() -> dict:
    if not PROFILE_FILE.exists():
        return {"profiles": {}}
    return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))


def runtime_environment() -> str:
    return (os.getenv("KU2D_EXECUTION_ENVIRONMENT") or "local").strip().lower()


def source_host(source: dict) -> str:
    return (urlparse(source.get("url") or "").hostname or "").lower()


def source_profile(source: dict) -> dict:
    host = source_host(source)
    profiles = load_profiles().get("profiles") or {}
    if host in profiles:
        return profiles[host]
    for domain, profile in profiles.items():
        if host == domain or host.endswith("." + domain):
            return profile
    return {}


def qualification(source: dict, runtime: str | None = None) -> dict:
    runtime = (runtime or runtime_environment()).lower()
    profile = source_profile(source)
    preferred = (profile.get("preferred_live_environment") or "any").lower()
    cloud_status = (profile.get("cloud_hosted_status") or "unknown").lower()

    allowed = True
    reason = None
    if runtime in {"cloud", "cloud-hosted", "github-hosted"} and cloud_status == "blocked":
        allowed = False
        reason = profile.get("reason") or "Source is not qualified for cloud-hosted live acquisition."
    elif preferred == "edge" and runtime in {"cloud", "cloud-hosted", "github-hosted"}:
        allowed = False
        reason = profile.get("reason") or "Source requires an Edge live-acquisition environment."

    return {
        "runtime_environment": runtime,
        "preferred_live_environment": preferred,
        "allowed": allowed,
        "cloud_hosted_status": cloud_status,
        "reason": reason,
        "profile": profile,
    }

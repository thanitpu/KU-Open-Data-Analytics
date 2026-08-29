from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "acquisition", ROOT / "repository"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from tools.LIVE_GOURMET_LIFECYCLE import (
    REQUIRED_SUPERMARKET_APPROVAL_TRACKS,
    resolved_assigned_tracks,
)

rows = [
    {
        "technique": "gourmet_rendered_catalog",
        "evidence": {"tracks": ["product_price"]},
    },
    {
        "technique": "gourmet_catalog_network",
        "evidence": {"tracks": ["discovery"]},
    },
]
tracks = resolved_assigned_tracks(rows)
assert tracks == {"product_price", "discovery"}
assert REQUIRED_SUPERMARKET_APPROVAL_TRACKS <= tracks
assert "promotion" not in REQUIRED_SUPERMARKET_APPROVAL_TRACKS

rows_with_promotion = rows + [
    {
        "technique": "gourmet_promotion_surface",
        "evidence": {"tracks": ["promotion"]},
    }
]
assert resolved_assigned_tracks(rows_with_promotion) == {"product_price", "discovery", "promotion"}

# Compatibility for a normalized legacy/synthetic row that exposes track_name.
assert resolved_assigned_tracks([{"track_name": "discovery", "evidence": {}}]) == {"discovery"}

print("Gourmet approval track policy: PASS")

from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "acquisition"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

with TemporaryDirectory() as td:
    os.environ["KU2D_OPERATIONS_DB"] = str(Path(td) / "ops.sqlite3")
    import operations_store as ops

    sid = "PROFILE-GOURMET-001"
    base = {
        "technique": "gourmet_graphql_catalog",
        "label": "Gourmet Market GraphQL Product Catalog",
        "score": 105,
        "record_count": 10,
        "tracks": ["product_price"],
        "engine_version": "0.24",
        "potential": {
            "operational_config": {
                "graphql_endpoint": "https://api-stark.gourmetmarketthailand.com/graphql",
                "graphql_operation": "Products",
                "graphql_query_hash": "aaaaaaaaaaaaaaaa",
                "identity_source": "gtin",
            }
        },
    }
    ops.replace_technique_assignments(sid, [base])
    ops.save_quality_audit(
        sid,
        {
            "audit_passed": True,
            "quality_score": 99,
            "quality_label": "strong",
            "technique_profile": {"fingerprint": "fixture"},
        },
    )
    ops.set_quality_approval(sid, approved=True, continuous=True)
    q = ops.quality_profile(sid)
    assert q["audit_passed"] == 1 and q["approved_for_store"] == 1 and q["continuous_enabled"] == 1

    changed = {**base, "potential": {"operational_config": {**base["potential"]["operational_config"], "graphql_query_hash": "bbbbbbbbbbbbbbbb"}}}
    ops.replace_technique_assignments(sid, [changed])
    q2 = ops.quality_profile(sid)
    assert q2["audit_passed"] == 0, "GraphQL query change must stale prior Deep Audit"
    assert q2["approved_for_store"] == 0, "GraphQL query change must revoke prior store approval"
    assert q2["continuous_enabled"] == 0, "GraphQL query change must disable continuous acquisition"
    assert q2["quality_label"] == "stale-technique-profile"

print("Technique operational-config invalidation: PASS")

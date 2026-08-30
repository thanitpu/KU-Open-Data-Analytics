from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
if str(ACQUISITION) not in sys.path:
    sys.path.insert(0, str(ACQUISITION))

from providers.youtube_data_api import api_status


def main() -> int:
    print(json.dumps(api_status(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

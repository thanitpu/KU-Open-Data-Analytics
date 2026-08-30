"""Create a compact, non-production Human Review package from foundation JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "acquisition") not in sys.path:
    sys.path.insert(0, str(ROOT / "acquisition"))

from youtube_human_review import prepare_review_package


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="YouTube Foundation result JSON")
    parser.add_argument("--output", required=True, type=Path, help="Human Review package JSON")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    source = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise ValueError("Foundation result must be a JSON object.")
    package = prepare_review_package(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Human Review package: {len(package['candidate_videos'])} videos, "
        f"{len(package['candidate_channels'])} channels; production remains disabled."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

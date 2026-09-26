"""Export the API contract, or check that the saved contract is current."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
destination = Path(__file__).resolve().parents[2] / "docs/api/openapi.json"
content = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
if args.check:
    if not destination.exists() or destination.read_text(encoding="utf-8") != content:
        raise SystemExit("OpenAPI contract differs. Run uv run python scripts/export_openapi.py")
else:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")

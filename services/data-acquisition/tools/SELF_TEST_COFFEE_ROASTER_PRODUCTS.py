from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "acquisition", ROOT):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from coffee_techniques import roaster_product_record

FIXTURES = ROOT / "fixtures" / "coffee_roaster_products"
OBSERVED = "2026-08-31T05:00:00+00:00"

roots = roaster_product_record(
    (FIXTURES / "roots_house_blend.html").read_text(encoding="utf-8"),
    "https://shop.rootsbkk.com/collections/frontpage/products/house-blend-coffee",
    "Roots Coffee", OBSERVED,
)
assert roots["coffee_product_id"] == "shop.rootsbkk.com:house-blend-coffee"
assert roots["price"] == 450.0 and roots["currency"] == "THB"
assert roots["origin"] == "Pangkhon Village, Chiang Rai"
assert roots["process"] == "Honey Process and Kenya-style Washed Process"
assert roots["tasting_notes"] == "Red Plum, Pear, Honeycomb Candy Finish"
assert roots["roast_level"] == "Medium Roast" and roots["package_size"] == "500 g"
assert roots["production_approved"] is False

nana = roaster_product_record(
    (FIXTURES / "nana_house_blend.html").read_text(encoding="utf-8"),
    "https://nanacoffeeroasters.com/products/house-blend",
    "Nana Coffee Roasters", OBSERVED,
)
assert nana["coffee_product_id"] == "nanacoffeeroasters.com:house-blend"
assert nana["price"] == 470.0 and nana["availability"] == "InStock"
assert nana["origin"] == "Colombia, Brazil, Kenya, Ethiopia"
assert nana["process"] == "Washed & Natural"

# A drink numeral, quantity, or context-free title cannot become a product.
assert roaster_product_record("<h1>250 Gram Coffee</h1><p>22 Oz.</p>", "https://example.com/products/x", "Example", OBSERVED) is None
assert roaster_product_record("<h1>Coffee</h1><p>450.00 ฿</p>", "http://example.com/products/x", "Example", OBSERVED) is None

print("Coffee official roaster product technique: PASS")

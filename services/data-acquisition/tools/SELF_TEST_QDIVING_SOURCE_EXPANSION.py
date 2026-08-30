from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "acquisition", ROOT):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from qdiving_source_expansion import (
    aquamaster_equipment_records,
    scubadoo_course_records,
    ssi_blog_records,
)

FIXTURES = ROOT / "fixtures" / "qdiving_source_expansion"
OBSERVED = "2026-08-31T06:00:00+00:00"

content = ssi_blog_records((FIXTURES / "ssi_blog.html").read_text(encoding="utf-8"), OBSERVED)
assert len(content) == 2
assert content[0]["content_id"] == "scuba-diving-holidays-fall-2827"
assert content[0]["human_review_required"] is True and content[0]["production_approved"] is False

courses = scubadoo_course_records((FIXTURES / "scubadoo_courses.html").read_text(encoding="utf-8"), OBSERVED)
assert len(courses) == 2 and courses[0]["price"] == 9900.0
assert courses[0]["record_type"] == "DiveCourseServiceCandidate"
assert courses[0]["booking_performed"] is False

products = aquamaster_equipment_records((FIXTURES / "aquamaster_equipment.html").read_text(encoding="utf-8"), OBSERVED)
assert len(products) == 2
assert products[0]["product_id"] == "oceanic-zeo"
assert products[0]["current_or_range_min_price"] == 28970.0
assert products[0]["range_max_price"] == 34940.0
assert products[0]["demand_signal"] is None and products[0]["production_approved"] is False

# The three evidence classes cannot silently contaminate one another.
assert {content[0]["record_type"], courses[0]["record_type"], products[0]["record_type"]} == {
    "DivingContentCandidate", "DiveCourseServiceCandidate", "DivingEquipmentProductCandidate"
}

print("Q-Diving non-YouTube source expansion: PASS")

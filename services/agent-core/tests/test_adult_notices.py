"""JM-D15: Jana is for learners aged 18 or over, so no consent notice speaks of guardians, parents or minors; the Study
notice states the learner's own consent."""

import json
import re
from pathlib import Path

NOTICES = Path(__file__).resolve().parents[3] / "content" / "agent" / "notices" / "notices.json"


def test_no_notice_speaks_of_guardians_or_minors() -> None:
    notices = json.loads(NOTICES.read_text())["notices"]
    for notice in notices:
        assert not re.search(r"guardian|parent|under 18|minor", notice["text"], re.IGNORECASE), notice["id"]
    study = next(n for n in notices if n["id"] == "study_materials")
    assert "18 or over" in study["text"]

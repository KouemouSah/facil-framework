import pytest
from pydantic import ValidationError

from app.modules.location.schemas import SiteCreate, SiteUpdate

BASE = {"organization_id": "o1", "code": "S1", "name": "Site 1"}


def test_old_shape_is_normalized_to_canonical():
    s = SiteCreate(**BASE, operating_hours={"mon": ["09:00-17:00"], "sat": []})
    assert s.operating_hours == {"weekly": {"mon": {"ranges": ["09:00-17:00"]}}, "exceptions": []}


def test_overnight_ok_but_from_equals_to_rejected():
    SiteCreate(**BASE, operating_hours={"weekly": {"mon": {"ranges": ["22:00-02:00"]}}, "exceptions": []})
    with pytest.raises(ValidationError):
        SiteCreate(**BASE, operating_hours={"weekly": {"mon": {"ranges": ["09:00-09:00"]}}, "exceptions": []})


def test_overlap_rejected():
    with pytest.raises(ValidationError):
        SiteCreate(**BASE, operating_hours={"weekly": {"mon": {"ranges": ["09:00-12:00", "11:00-13:00"]}}, "exceptions": []})


def test_bad_mode_and_bad_exception_date_rejected():
    with pytest.raises(ValidationError):
        SiteCreate(**BASE, operating_hours={"weekly": {"mon": {"nope": True}}, "exceptions": []})
    with pytest.raises(ValidationError):
        SiteCreate(**BASE, operating_hours={"weekly": {}, "exceptions": [{"date": "2026-13-40", "closed": True}]})


def test_duplicate_exception_date_rejected():
    with pytest.raises(ValidationError):
        SiteCreate(**BASE, operating_hours={"weekly": {}, "exceptions": [
            {"date": "2026-01-01", "closed": True}, {"date": "2026-01-01", "h24": True}]})


def test_update_also_validates():
    with pytest.raises(ValidationError):
        SiteUpdate(operating_hours={"weekly": {"mon": {"ranges": ["17:00-17:00"]}}, "exceptions": []})
    assert SiteUpdate(operating_hours=None).operating_hours is None  # optional stays optional


def test_old_shape_malformed_day_rejected():
    with pytest.raises(ValidationError):
        SiteCreate(**BASE, operating_hours={"mon": {"foo": "bar"}})


def test_exception_date_must_be_dashed_iso():
    for bad in ("20260101", "2026-W01-1"):
        with pytest.raises(ValidationError):
            SiteCreate(**BASE, operating_hours={"weekly": {}, "exceptions": [{"date": bad, "closed": True}]})


def test_omitted_operating_hours_is_canonicalized():
    s = SiteCreate(**BASE)
    assert s.operating_hours == {"weekly": {}, "exceptions": []}

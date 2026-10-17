"""Session/approval gating and the withdrawn-member retention purge."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import database
import dependencies
import main
from tests.fakes import FakeDB


def make_request(cookie=None):
    cookies = {"user_uid": cookie} if cookie else {}
    return SimpleNamespace(cookies=cookies)


def use_db(monkeypatch, fake):
    monkeypatch.setattr(database, "db", fake)


class TestRequireApproved:
    def _db(self, status):
        users = {"u1": {"is_auth": status}} if status is not None else {}
        return FakeDB({"users": users})

    def test_approved_passes(self, monkeypatch):
        use_db(monkeypatch, self._db("approved"))
        req = make_request(dependencies.sign_uid("u1"))
        assert dependencies.require_approved(req) == "u1"

    @pytest.mark.parametrize("status", ["pending", "withdrawn"])
    def test_non_approved_rejected(self, monkeypatch, status):
        use_db(monkeypatch, self._db(status))
        req = make_request(dependencies.sign_uid("u1"))
        with pytest.raises(HTTPException) as e:
            dependencies.require_approved(req)
        assert e.value.status_code == 403

    def test_missing_user_doc_rejected(self, monkeypatch):
        use_db(monkeypatch, self._db(None))
        req = make_request(dependencies.sign_uid("u1"))
        with pytest.raises(HTTPException) as e:
            dependencies.require_approved(req)
        assert e.value.status_code == 403

    def test_no_cookie_rejected(self, monkeypatch):
        use_db(monkeypatch, self._db("approved"))
        with pytest.raises(HTTPException) as e:
            dependencies.require_approved(make_request())
        assert e.value.status_code == 401

    def test_forged_cookie_rejected(self, monkeypatch):
        use_db(monkeypatch, self._db("approved"))
        with pytest.raises(HTTPException) as e:
            dependencies.require_approved(make_request("u1.forged.signature"))
        assert e.value.status_code == 401


class TestRetentionPurge:
    def _now(self):
        return datetime.now(timezone.utc)

    def test_old_withdrawn_member_is_purged(self):
        db = FakeDB({"users": {
            "old": {"is_auth": "withdrawn", "phone": "010-1111-2222", "memo": "x",
                    "withdrawn_at": self._now() - timedelta(days=366)},
        }})
        result = main.purge_withdrawn_personal_data(db)
        assert result == {"stamped": 0, "purged": 1}
        assert db.collection("users").document("old").get().to_dict()["phone"] == ""
        assert db.collection("users").document("old").get().to_dict()["memo"] == ""

    def test_recent_withdrawn_member_untouched(self):
        db = FakeDB({"users": {
            "new": {"is_auth": "withdrawn", "phone": "010-1111-2222",
                    "withdrawn_at": self._now() - timedelta(days=30)},
        }})
        result = main.purge_withdrawn_personal_data(db)
        assert result == {"stamped": 0, "purged": 0}
        assert db.collection("users").document("new").get().to_dict()["phone"] == "010-1111-2222"

    def test_legacy_withdrawn_without_timestamp_gets_stamped_not_purged(self):
        db = FakeDB({"users": {
            "legacy": {"is_auth": "withdrawn", "phone": "010-1111-2222"},
        }})
        result = main.purge_withdrawn_personal_data(db)
        assert result == {"stamped": 1, "purged": 0}
        # phone must survive: the clock starts today, not retroactively
        assert db.collection("users").document("legacy").get().to_dict()["phone"] == "010-1111-2222"

    def test_approved_members_never_touched(self):
        db = FakeDB({"users": {
            "a": {"is_auth": "approved", "phone": "010-1111-2222",
                  "withdrawn_at": self._now() - timedelta(days=999)},
        }})
        result = main.purge_withdrawn_personal_data(db)
        assert result == {"stamped": 0, "purged": 0}
        assert db.collection("users").document("a").get().to_dict()["phone"] == "010-1111-2222"

    def test_already_empty_fields_skip_write(self):
        db = FakeDB({"users": {
            "old": {"is_auth": "withdrawn", "phone": "", "memo": "",
                    "withdrawn_at": self._now() - timedelta(days=400)},
        }})
        result = main.purge_withdrawn_personal_data(db)
        assert result == {"stamped": 0, "purged": 0}

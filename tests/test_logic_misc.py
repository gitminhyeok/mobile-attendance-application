"""IP checks, X-Forwarded-For parsing, date helpers, unnotified-date purging."""
from datetime import date
from types import SimpleNamespace

import logic
from tests.fakes import FakeCollection


def make_request(headers=None, host="10.0.0.9"):
    return SimpleNamespace(headers=headers or {}, client=SimpleNamespace(host=host))


class TestClientIP:
    def test_prefers_first_xff_entry(self):
        req = make_request({"x-forwarded-for": "1.2.3.4, 5.6.7.8"})
        assert logic.get_client_ip(req) == "1.2.3.4"

    def test_falls_back_to_socket_host(self):
        assert logic.get_client_ip(make_request()) == "10.0.0.9"


class TestCheckIP:
    def test_localhost_always_allowed(self):
        assert logic.check_ip("127.0.0.1") is True
        assert logic.check_ip("::1") is True

    def test_allowed_and_denied(self, monkeypatch):
        monkeypatch.setattr(logic, "ALLOWED_IP", "211.1.1.1, 211.2.2.2")
        assert logic.check_ip("211.1.1.1") is True
        assert logic.check_ip("211.2.2.2") is True
        assert logic.check_ip("211.3.3.3") is False
        # adversarial: spoofed values must not pass by substring/prefix tricks
        assert logic.check_ip("211.1.1.10") is False
        assert logic.check_ip("211.1.1.1 ") is False  # exact match only (XFF values arrive stripped)


class TestSubtractMonths:
    def test_simple(self):
        assert logic.subtract_months(date(2026, 10, 15), 3) == date(2026, 7, 15)

    def test_year_wrap(self):
        assert logic.subtract_months(date(2026, 1, 10), 3) == date(2025, 10, 10)

    def test_month_end_clamped(self):
        assert logic.subtract_months(date(2026, 3, 31), 1) == date(2026, 2, 28)


class TestParseUnnotifiedDate:
    def test_two_digit_year(self):
        assert logic.parse_unnotified_date("26-05-03") == date(2026, 5, 3)

    def test_four_digit_year(self):
        assert logic.parse_unnotified_date("2026-05-03") == date(2026, 5, 3)

    def test_garbage_returns_none(self):
        assert logic.parse_unnotified_date("hello") is None
        assert logic.parse_unnotified_date("") is None


class TestPurgeExpiredUnnotified:
    def _run(self, d1, d2, today=date(2026, 10, 17)):
        col = FakeCollection({"u1": {"unnotified_date1": d1, "unnotified_date2": d2}})
        ref = col.document("u1")
        kept = logic.purge_expired_unnotified(
            ref, {"unnotified_date1": d1, "unnotified_date2": d2}, today)
        return kept, ref

    def test_recent_dates_kept_without_write(self):
        kept, ref = self._run("26-10-01", "26-09-15")
        assert kept == ("26-10-01", "26-09-15")
        assert ref.update_calls == []

    def test_expired_date_dropped_and_compacted(self):
        kept, ref = self._run("26-01-01", "26-10-01")
        assert kept == ("26-10-01", "")
        assert ref.update_calls == [{"unnotified_date1": "26-10-01", "unnotified_date2": ""}]

    def test_unparseable_value_is_kept_for_admin(self):
        kept, ref = self._run("not-a-date", "")
        assert kept == ("not-a-date", "")
        assert ref.update_calls == []

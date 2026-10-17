"""Adversarial boundary tests for the attendance time windows.

Policy under test (KST):
  Saturday: present 12:45:00-13:10:59, late 13:11:00-13:59:59, else closed
  Sunday:   present 15:45:00-16:10:59, late 16:11:00-16:59:59, else closed
  Weekdays: always closed
"""
from datetime import datetime

import pytest

import logic

SATURDAY = datetime(2026, 10, 17)   # verified in test_preconditions
SUNDAY = datetime(2026, 10, 18)
MONDAY = datetime(2026, 10, 19)


def at(day, h, m, s=0, micro=0):
    return logic.KST.localize(day.replace(hour=h, minute=m, second=s, microsecond=micro))


def status_at(monkeypatch, moment):
    monkeypatch.setattr(logic, "get_current_kst_time", lambda: moment)
    status, _ = logic.check_attendance_time()
    return status


def test_preconditions():
    assert SATURDAY.weekday() == 5
    assert SUNDAY.weekday() == 6
    assert MONDAY.weekday() == 0


@pytest.mark.parametrize("h,m,s,micro,expected", [
    (12, 44, 59, 999999, "closed"),   # one tick before the window
    (12, 45, 0, 0, "open"),
    (13, 10, 59, 0, "open"),
    (13, 10, 59, 999999, "open"),     # fractional seconds inside 10:59
    (13, 11, 0, 0, "late"),
    (13, 59, 59, 999999, "late"),
    (14, 0, 0, 0, "closed"),          # late window is exclusive at the top
    (15, 0, 0, 0, "closed"),          # old pre-shortening boundary stays closed
])
def test_saturday_windows(monkeypatch, h, m, s, micro, expected):
    assert status_at(monkeypatch, at(SATURDAY, h, m, s, micro)) == expected


@pytest.mark.parametrize("h,m,s,micro,expected", [
    (15, 44, 59, 999999, "closed"),
    (15, 45, 0, 0, "open"),
    (16, 10, 59, 999999, "open"),
    (16, 11, 0, 0, "late"),
    (16, 59, 59, 999999, "late"),
    (17, 0, 0, 0, "closed"),
    (18, 0, 0, 0, "closed"),          # old pre-shortening boundary stays closed
])
def test_sunday_windows(monkeypatch, h, m, s, micro, expected):
    assert status_at(monkeypatch, at(SUNDAY, h, m, s, micro)) == expected


def test_weekday_always_closed(monkeypatch):
    assert status_at(monkeypatch, at(MONDAY, 13, 0)) == "closed"

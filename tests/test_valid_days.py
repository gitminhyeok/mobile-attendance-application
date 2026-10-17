"""count_valid_class_days: the single source of truth for the rate denominator."""
from datetime import datetime

import logic

# 2026-10: Saturdays 3,10,17,24,31 / Sundays 4,11,18,25 -> 9 weekend days


def kst(y, mo, d, h=12, mi=0):
    return logic.KST.localize(datetime(y, mo, d, h, mi))


def test_past_month_counts_all_weekend_days():
    assert logic.count_valid_class_days(2026, 10, now=kst(2026, 11, 5)) == 9


def test_future_month_clamps_to_one():
    assert logic.count_valid_class_days(2026, 12, now=kst(2026, 10, 17)) == 1


def test_current_month_counts_up_to_today():
    # as of Mon 2026-10-12: Sat 3, Sun 4, Sat 10, Sun 11 -> 4
    assert logic.count_valid_class_days(2026, 10, now=kst(2026, 10, 12)) == 4


def test_todays_class_excluded_before_start():
    # Saturday 2026-10-17 morning: today's class (12:45) not started yet
    assert logic.count_valid_class_days(2026, 10, now=kst(2026, 10, 17, 9, 0)) == 4
    # ...and included from the moment attendance opens
    assert logic.count_valid_class_days(2026, 10, now=kst(2026, 10, 17, 12, 45)) == 5


def test_sunday_cutoff():
    assert logic.count_valid_class_days(2026, 10, now=kst(2026, 10, 18, 15, 44)) == 5
    assert logic.count_valid_class_days(2026, 10, now=kst(2026, 10, 18, 15, 45)) == 6


def test_year_boundary_is_not_string_compared():
    # past month of the NEXT year must not be misclassified
    assert logic.count_valid_class_days(2026, 12, now=kst(2027, 1, 10)) > 1


def test_member_status_fallbacks():
    assert logic.member_status({"is_auth": "pending"}) == "pending"
    assert logic.member_status({"status": "withdrawn"}) == "withdrawn"
    assert logic.member_status({}) == "approved"
    assert logic.member_status(None) == "approved"

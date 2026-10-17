"""Streak computation, status message priority, admin last-attendance map."""
from routers.views import compute_longest_weekly_streak, build_status_message
from routers.admin import get_last_attendance_map
from tests.fakes import FakeDB


class TestWeeklyStreak:
    def test_empty(self):
        assert compute_longest_weekly_streak([]) == (0, "")

    def test_single_attendance(self):
        assert compute_longest_weekly_streak(["2026-10-03"]) == (1, "2026-10-03")

    def test_consecutive_weeks(self):
        # Sat 3rd (wk41), Sun 11th (wk42), Sat 17th (wk42... no: 17th is wk42)
        dates = ["2026-10-03", "2026-10-10", "2026-10-17"]
        streak, end = compute_longest_weekly_streak(dates)
        assert streak == 3
        assert end == "2026-10-17"

    def test_gap_resets_streak(self):
        # weeks 41, 42, (skip), 44
        dates = ["2026-10-03", "2026-10-10", "2026-10-31"]
        streak, _ = compute_longest_weekly_streak(dates)
        assert streak == 2

    def test_same_week_counts_once(self):
        # Sat+Sun of the same ISO week are one week of streak
        dates = ["2026-10-03", "2026-10-04"]
        streak, _ = compute_longest_weekly_streak(dates)
        assert streak == 1

    def test_year_boundary(self):
        # consecutive ISO weeks across the new year
        dates = ["2026-12-26", "2027-01-02"]
        streak, _ = compute_longest_weekly_streak(dates)
        assert streak == 2


class TestStatusMessage:
    def test_sick_leave_wins_over_everything(self):
        msg, color = build_status_message(True, 999, 2, 0)
        assert "병결" in msg and color == "text-blue-600"

    def test_never_attended(self):
        msg, _ = build_status_message(False, -1, 0, 0)
        assert "첫 출석" in msg

    def test_dropout_by_absence(self):
        msg, color = build_status_message(False, 23, 0, 0)
        assert "제적" in msg and "장기 결석" in msg and color == "text-red-600"

    def test_dropout_by_unnotified(self):
        msg, _ = build_status_message(False, 3, 2, 1)
        assert "미통보" in msg

    def test_warning(self):
        msg, color = build_status_message(False, 16, 0, 0)
        assert "2주째" in msg and color == "text-yellow-600"

    def test_active(self):
        msg, _ = build_status_message(False, 2, 0, 3)
        assert "연속으로" in msg
        msg, _ = build_status_message(False, 2, 0, 1)
        assert "이번 주" in msg


class TestLastAttendanceMap:
    def test_latest_date_per_user(self):
        db = FakeDB({"attendance": {
            "a1": {"user_id": "u1", "date": "2026-10-03", "status": "present"},
            "a2": {"user_id": "u1", "date": "2026-10-10", "status": "late"},
            "a3": {"user_id": "u2", "date": "2026-09-27", "status": "present"},
            "a4": {"user_id": None, "date": "2026-10-10"},  # malformed doc ignored
        }})
        assert get_last_attendance_map(db) == {"u1": "2026-10-10", "u2": "2026-09-27"}

    def test_empty_collection(self):
        assert get_last_attendance_map(FakeDB({"attendance": {}})) == {}

"""Adversarial tests for the monthly ranking computation."""
from datetime import datetime

import pytest

from routers.views import get_ranking_data
from tests.fakes import FakeDB

OCT = datetime(2026, 10, 1)


def build_db(attendance, users):
    return FakeDB({
        "attendance": {f"a{i}": doc for i, doc in enumerate(attendance)},
        "users": users,
    })


def approved(nickname):
    return {"nickname": nickname, "is_auth": "approved", "profile_image": ""}


def test_counts_only_present_in_target_month():
    db = build_db(
        attendance=[
            {"user_id": "u1", "date": "2026-10-03", "status": "present"},
            {"user_id": "u1", "date": "2026-10-04", "status": "late"},      # excluded
            {"user_id": "u1", "date": "2026-09-27", "status": "present"},   # other month
            {"user_id": "u1", "date": "2026-11-01", "status": "present"},   # other month
        ],
        users={"u1": approved("A")},
    )
    rows = get_ranking_data(db, OCT, valid_days_count=4, uid="u1")
    assert len(rows) == 1
    assert rows[0]["count"] == 1
    assert rows[0]["rate"] == 25
    assert rows[0]["is_me"] is True


def test_non_approved_members_are_hidden():
    db = build_db(
        attendance=[
            {"user_id": "ghost", "date": "2026-10-03", "status": "present"},
            {"user_id": "u1", "date": "2026-10-03", "status": "present"},
        ],
        users={
            "ghost": {"nickname": "G", "is_auth": "withdrawn", "profile_image": ""},
            "u1": approved("A"),
        },
    )
    rows = get_ranking_data(db, OCT, valid_days_count=1, uid=None)
    assert [r["nickname"] for r in rows] == ["A"]


def test_ties_share_rank_dense():
    db = build_db(
        attendance=[
            {"user_id": "u1", "date": "2026-10-03", "status": "present"},
            {"user_id": "u1", "date": "2026-10-04", "status": "present"},
            {"user_id": "u2", "date": "2026-10-03", "status": "present"},
            {"user_id": "u2", "date": "2026-10-04", "status": "present"},
            {"user_id": "u3", "date": "2026-10-03", "status": "present"},
        ],
        users={"u1": approved("A"), "u2": approved("B"), "u3": approved("C")},
    )
    rows = get_ranking_data(db, OCT, valid_days_count=2, uid=None)
    ranks = {r["nickname"]: r["rank"] for r in rows}
    assert ranks["A"] == 1 and ranks["B"] == 1
    assert ranks["C"] == 2


def test_no_rank_gap_when_non_approved_member_interleaves():
    """A withdrawn member sitting between two approved members must not
    leave a hole in the visible rank numbers (1, 3, ...)."""
    db = build_db(
        attendance=[
            {"user_id": "u1", "date": f"2026-10-{d:02d}", "status": "present"}
            for d in (3, 4, 10)
        ] + [
            {"user_id": "ghost", "date": f"2026-10-{d:02d}", "status": "present"}
            for d in (3, 4)
        ] + [
            {"user_id": "u2", "date": "2026-10-03", "status": "present"},
        ],
        users={
            "u1": approved("A"),
            "ghost": {"nickname": "G", "is_auth": "withdrawn", "profile_image": ""},
            "u2": approved("B"),
        },
    )
    rows = get_ranking_data(db, OCT, valid_days_count=3, uid=None)
    assert [(r["nickname"], r["rank"]) for r in rows] == [("A", 1), ("B", 2)]

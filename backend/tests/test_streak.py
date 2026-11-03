from datetime import date, timedelta

from app.streak import count_streak

T = date(2026, 11, 3)


def days(*offsets):
    return {T - timedelta(days=o) for o in offsets}


def test_empty():
    assert count_streak(set(), T) == 0


def test_counts_through_today():
    assert count_streak(days(0, 1, 2), T) == 3


def test_not_sent_today_keeps_yesterdays_streak():
    # Ainda dá tempo hoje: a streak não zera, conta até ontem.
    assert count_streak(days(1, 2, 3), T) == 3


def test_gap_breaks_streak():
    assert count_streak(days(0, 1, 3, 4, 5), T) == 2
    assert count_streak(days(2, 3), T) == 0  # perdeu ontem: zerou

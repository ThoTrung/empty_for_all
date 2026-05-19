# -*- coding: utf-8 -*-
"""Shared helpers: stale end payloads from Odoo form ``force_save`` vs real schedule fields."""

from datetime import timedelta

from odoo import fields

# Context: allow inverse to apply end even when shorter than start+duration (calendar resize / end-only write).
CTX_SCHEDULE_END_ONLY_WRITE = "spa_schedule_end_only_write"

BOOKING_CALENDAR_DISPLAY_WRITE_KEYS = frozenset({
    "display_start_datetime",
    "display_end_datetime",
})


def sanitize_booking_write_vals(vals, *, is_create=False):
    """``spa.service.booking`` — keep ``display_end`` + force_save on form; strip stale payloads on write.

    See ``spa.service.booking`` model docstring / BUG_LOG BC-BUG-2026-05-19-01.
    """
    if not vals:
        return vals
    cleaned = dict(vals)
    if is_create:
        if "duration" in cleaned:
            cleaned.pop("display_end_datetime", None)
            cleaned.pop("end_datetime", None)
        return cleaned
    if cleaned.get("start_datetime"):
        for key in ("display_start_datetime", "display_end_datetime", "end_datetime"):
            cleaned.pop(key, None)
        return cleaned
    if set(cleaned.keys()).issubset(BOOKING_CALENDAR_DISPLAY_WRITE_KEYS):
        return cleaned
    cleaned.pop("display_end_datetime", None)
    cleaned.pop("end_datetime", None)
    return cleaned


def sanitize_line_write_vals(vals, *, is_create=False):
    """``spa.service.booking.line`` — modal uses ``end_datetime`` + force_save (same stale-end class of bugs)."""
    if not vals:
        return vals
    cleaned = dict(vals)
    if is_create:
        if "duration_minutes" in cleaned:
            cleaned.pop("end_datetime", None)
        return cleaned
    if cleaned.get("start_datetime"):
        cleaned.pop("end_datetime", None)
        return cleaned
    if set(cleaned.keys()) == {"end_datetime"}:
        return cleaned
    cleaned.pop("end_datetime", None)
    return cleaned


def write_with_optional_end_only_context(records, vals):
    """Return recordset with context flag when calendar write should apply display_end inverse."""
    keys = set(vals.keys())
    if not keys.issubset(BOOKING_CALENDAR_DISPLAY_WRITE_KEYS):
        return records
    if keys == {"display_end_datetime"}:
        new_end = fields.Datetime.to_datetime(vals["display_end_datetime"])
        apply = False
        for rec in records:
            implied = duration_minutes_between(rec.start_datetime, new_end)
            if implied == 60 and rec.duration and int(rec.duration) != 60:
                continue
            cur_end = (
                fields.Datetime.to_datetime(rec.end_datetime) if rec.end_datetime else None
            )
            if cur_end and new_end and abs((new_end - cur_end).total_seconds()) > 1:
                apply = True
                break
        if not apply:
            return records
    return records.with_context(**{CTX_SCHEDULE_END_ONLY_WRITE: True})


def duration_minutes_between(start_dt, end_dt):
    """Minutes from start to end (>= 1), or 0 if invalid."""
    if not start_dt or not end_dt:
        return 0
    start = fields.Datetime.to_datetime(start_dt)
    end = fields.Datetime.to_datetime(end_dt)
    if not start or not end or end <= start:
        return 0
    return max(int(round((end - start).total_seconds() / 60.0)), 1)


def is_stale_longer_force_saved_end(start_dt, duration_minutes, new_end_dt, *, tolerance_seconds=1):
    """``force_save`` posted an end later than ``start + duration`` (e.g. old 60p bar while duration is 45)."""
    if not start_dt or not duration_minutes or not new_end_dt:
        return False
    start = fields.Datetime.to_datetime(start_dt)
    new_end = fields.Datetime.to_datetime(new_end_dt)
    if not start or not new_end:
        return False
    min_end = start + timedelta(minutes=max(int(duration_minutes or 0), 1))
    return new_end > min_end + timedelta(seconds=tolerance_seconds)


def is_intentional_line_end_resize(start_dt, duration_minutes, new_end_dt, *, tolerance_seconds=1):
    """Line end-only write that should change ``duration_minutes`` (shorter or longer than current window)."""
    if not start_dt or not new_end_dt or is_stale_longer_force_saved_end(
        start_dt, duration_minutes, new_end_dt, tolerance_seconds=tolerance_seconds
    ):
        return False
    start = fields.Datetime.to_datetime(start_dt)
    new_end = fields.Datetime.to_datetime(new_end_dt)
    if not start or not new_end or new_end <= start:
        return False
    if not duration_minutes:
        return True
    min_end = start + timedelta(minutes=max(int(duration_minutes or 0), 1))
    return abs((new_end - min_end).total_seconds()) > tolerance_seconds

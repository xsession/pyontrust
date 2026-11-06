from __future__ import annotations

import datetime


def utc_timestamp_id() -> str:
    # Example: 20260117T153012Z
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

from datetime import datetime, timezone

from .constants import WAREHOUSE_UPLOAD_FORMAT, WAREHOUSE_UPLOAD_FORMAT_ANY


def warehouse_date_to_epoch(iso8601_str: str) -> int:
    for format_str in WAREHOUSE_UPLOAD_FORMAT_ANY:
        try:
            return int(
                datetime.strptime(iso8601_str, format_str)
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
        except ValueError:
            continue
    raise ValueError(  # pragma: no cover
        f"'{iso8601_str}' didn't match any of {WAREHOUSE_UPLOAD_FORMAT_ANY}"
    )


def epoch_to_warehouse_date(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime(
        WAREHOUSE_UPLOAD_FORMAT
    )

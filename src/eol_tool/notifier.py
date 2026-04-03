"""Send notifications via ntfy when EOL changes are detected."""

import logging

import httpx

from .diff import DiffResult, format_diff_text

logger = logging.getLogger(__name__)


def _classify_diff_severity(diff: DiffResult) -> str:
    """Return the highest severity level present in the diff."""
    for entry in diff.changes:
        if entry.severity == "critical":
            return "critical"
    for entry in diff.changes:
        if entry.severity == "warning":
            return "warning"
    if diff.changes:
        return "info"
    return "none"


def _should_notify(severity: str, notify_on: str) -> bool:
    """Decide whether to send based on notify_on config and diff severity."""
    if notify_on == "none":
        return False
    if notify_on == "all":
        return True
    if notify_on == "critical":
        return severity == "critical"
    # "warning" (default): send if critical or warning
    return severity in ("critical", "warning")


async def send_ntfy(config, diff: DiffResult) -> bool:
    """Send a diff notification to ntfy. Returns True on success."""
    severity = _classify_diff_severity(diff)

    if not _should_notify(severity, config.notify_on):
        logger.info("Skipping notification: severity=%s, notify_on=%s", severity, config.notify_on)
        return False

    total = diff.summary.total_changes
    title = f"EOL Check: {total} changes detected" if total else "EOL Check: no changes"

    body = format_diff_text(diff, verbose=False)

    # Priority mapping
    if severity == "critical":
        priority = "5"
    elif severity == "warning":
        priority = "3"
    elif severity == "info":
        priority = "2"
    else:
        priority = "1"

    # Tag mapping
    if severity == "critical":
        tags = "rotating_light,warning"
    elif severity == "warning":
        tags = "warning"
    elif severity == "info":
        tags = "information_source"
    else:
        tags = "white_check_mark"

    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": tags,
    }
    if config.ntfy_token:
        headers["Authorization"] = f"Bearer {config.ntfy_token}"

    url = f"{config.ntfy_url.rstrip('/')}/{config.ntfy_topic}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, content=body, headers=headers)
            resp.raise_for_status()
        logger.info("Notification sent to %s (priority %s)", config.ntfy_topic, priority)
        return True
    except Exception as exc:
        logger.error("Failed to send notification: %s", exc)
        return False


async def send_ntfy_error(config, error: str) -> bool:
    """Send an error notification when a scheduled check fails."""
    headers = {
        "Title": "EOL Check Failed",
        "Priority": "4",
        "Tags": "x",
    }
    if config.ntfy_token:
        headers["Authorization"] = f"Bearer {config.ntfy_token}"

    url = f"{config.ntfy_url.rstrip('/')}/{config.ntfy_topic}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, content=error, headers=headers)
            resp.raise_for_status()
        logger.info("Error notification sent to %s", config.ntfy_topic)
        return True
    except Exception as exc:
        logger.error("Failed to send error notification: %s", exc)
        return False

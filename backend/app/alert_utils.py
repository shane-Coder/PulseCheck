import json
import urllib.error
import urllib.request

# Plain urllib rather than adding requests/httpx — this is one JSON POST
# with a short timeout, stdlib is plenty and it keeps the dependency list
# from growing for something this small.


def _post_json(url: str, payload: dict, timeout: int = 10) -> None:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response.read()


def send_slack_alert(webhook_url: str, text: str) -> None:
    """Slack's incoming-webhook format: a JSON body with a "text" field.
    Best-effort, same as send_email — a broken webhook URL should never
    stop the overdue check from finishing or crash the caller."""
    if not webhook_url:
        return
    try:
        _post_json(webhook_url, {"text": text})
    except Exception as exc:  # noqa: BLE001
        print(f"[slack alert error] error={exc}")


def send_discord_alert(webhook_url: str, text: str) -> None:
    """Discord's incoming-webhook format uses "content" instead of "text",
    otherwise the same idea as Slack's."""
    if not webhook_url:
        return
    try:
        _post_json(webhook_url, {"content": text})
    except Exception as exc:  # noqa: BLE001
        print(f"[discord alert error] error={exc}")


def send_generic_webhook(webhook_url: str, payload: dict) -> None:
    """No fixed shape to match here — this is for anyone piping alerts into
    their own system, so the payload is just whatever structured data the
    caller passes, unmodified."""
    if not webhook_url:
        return
    try:
        _post_json(webhook_url, payload)
    except Exception as exc:  # noqa: BLE001
        print(f"[webhook alert error] error={exc}")

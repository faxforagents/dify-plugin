"""Calls to the Fax for Agents REST API (https://faxforagents.com/docs/api/) shared by the tools.

Every refusal from the API is an `error` envelope with a stable `code`. The tools turn the codes an
agent can act on into the same remedies the MCP server gives (faxforagents/mcp src/server.ts,
2026-10-31), so a workflow sees what to do next instead of a bare status.
"""

import os
import re
from typing import Any

import requests

# FAXFORAGENTS_API_URL points a local debug run at a fake server. The published plugin reads nothing
# else from the environment.
API_URL = os.environ.get("FAXFORAGENTS_API_URL", "https://api.faxforagents.com").rstrip("/")
USER_AGENT = "dify-plugin-faxforagents/0.1.0"
DEFAULT_HTTP_TIMEOUT = 60
ID_RE = re.compile(r"^[a-z]{2,8}_[0-9a-f]{32}$")

REMEDIES = {
    "invalid_token": "The API key was rejected. Use an ffa_test_... or ffa_live_... key from app.faxforagents.com.",
    "scope_missing": "This key lacks the scope the call needs. Ask the key's owner for a key that has it.",
    "not_found": "No such id in your organization, or it was deleted.",
    "approval_required": (
        "No approval and no policy allows this send. A person approves the quote in the dashboard, "
        "then pass the approval id to Send fax."
    ),
    "approval_expired": "The approval expired with its quote. Quote again and ask for a new approval.",
    "approval_mismatch": "The approval was given for a different send. Quote again and ask again for exactly this send.",
    "approval_not_granted": "The request is not approved. Only an approved request authorizes a send.",
    "approval_consumed": "This approval was already used. One approval, one send.",
    "document_hash_mismatch": "The document changed since the quote or approval. Quote and ask again.",
    "insufficient_balance": "The wallet does not cover this fax. A person tops it up in the dashboard.",
    "quote_expired": "The quote expired (10 minutes). Quote again.",
    "quote_consumed": "This quote already created a fax. Read it with Get fax status instead of sending again.",
    "not_cancelable": "The fax is past the point where it can be canceled.",
    "rate_limited": "Rate limit reached. Retry in a few seconds with the same idempotency key.",
}


class FaxForAgentsError(Exception):
    pass


def call(
    key: str,
    method: str,
    path: str,
    *,
    params: dict | None = None,
    body: Any = None,
    headers: dict | None = None,
    timeout: int = DEFAULT_HTTP_TIMEOUT,
) -> Any:
    if not key:
        raise FaxForAgentsError("Add your Fax for Agents API key in the plugin settings.")
    all_headers = {"Authorization": f"Bearer {key}", "User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        all_headers.update(headers)
    if body is not None:
        body = {k: v for k, v in body.items() if v is not None}
    try:
        res = requests.request(
            method, f"{API_URL}{path}", headers=all_headers, params=params, json=body, timeout=timeout
        )
    except requests.Timeout as e:
        raise FaxForAgentsError("Fax for Agents did not answer in time. Retry once, then report it.") from e
    except requests.RequestException as e:
        raise FaxForAgentsError(f"Could not reach Fax for Agents: {e}") from e
    if res.status_code >= 400:
        code, message = "http_error", f"HTTP {res.status_code}"
        try:
            err = (res.json() or {}).get("error") or {}
            code = err.get("code") or code
            message = err.get("message") or message
        except ValueError:
            pass
        raise FaxForAgentsError(f"{REMEDIES.get(code, message)} (error_code={code})")
    return res.json() if res.content else {}


def resource_id(value: Any, name: str) -> str:
    """An id of the API: a short prefix, an underscore and 32 hex characters."""
    text = str(value or "").strip()
    if not ID_RE.match(text):
        raise FaxForAgentsError(f"{name} is not a Fax for Agents id (a prefix, an underscore and 32 hex characters).")
    return text


def whole_number(value: Any, name: str, default: int, low: int, high: int) -> int:
    if value is None or value == "":
        return default
    try:
        n = int(value)
    except (TypeError, ValueError) as e:
        raise FaxForAgentsError(f"{name} must be a whole number.") from e
    return max(low, min(n, high))


def dollars(micro: Any) -> str:
    return f"${int(micro) / 1_000_000:.3f}"


STATE_MESSAGES = {
    "queued": "queued: accepted, waiting for the worker.",
    "active": "at the carrier. Read the status again later.",
    "delivered": "delivered: every page arrived and the carrier's evidence is attached.",
    "partial": "partial: only some pages arrived. No automatic retransmit, a human decides.",
    "failed": "failed: nothing arrived. The hold was released.",
    "unknown": "outcome unknown: the carrier gave no answer. Nothing retransmits on its own.",
}


def describe_fax(job: dict) -> str:
    state = str(job.get("state"))
    text = f"Fax {job.get('id')} to {job.get('to')} is {STATE_MESSAGES.get(state, state)}"
    if state in ("failed", "partial") and job.get("failure_code"):
        text += f" Reason: {job.get('failure_code')}."
    if state == "partial":
        text += f" Pages sent: {job.get('pages_sent')} of {job.get('billable_pages')}."
    return text

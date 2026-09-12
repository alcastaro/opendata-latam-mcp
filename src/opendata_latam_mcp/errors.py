"""The error contract this server owes the model: return, never raise.

Measured on 2026-08-30 through a real client session, before this module
existed. Calling `search_datasets` with an unsupported country code returned,
over the wire:

    is_error=True
    structured_content=None
    text='Error executing tool search_datasets'

That is the whole message. The underlying exception said
``Unknown country: 'XX'. Supported: ['AR', 'CL', 'DO', 'EC', 'MX', 'PA', 'UY']``
— perfectly actionable — and the SDK discarded it. Every failure this server can
produce collapsed into that one useless sentence: a bad country code, a portal
answering 403, a timeout, a CKAN-side error.

Three reasons that matters, in order of how much they cost:

1. **A model cannot act on it.** It cannot tell whether the country does not
   exist, the portal is down, or it wrote the argument wrong — so it retries
   blindly and burns turns. With Ecuador answering 403 to everything today, that
   is a live cost, not a hypothetical one.
2. **It is a documented rejection cause** for the Claude connectors directory:
   *"Generic errors ('Internal Server Error', 'Bad Request' with no detail) fail
   review."* That sentence IS such an error.
3. It contradicts the project's own invariant, which the sibling servers hold
   and this one held in exactly one of fifteen tools.

**The design, and the bonus it buys.** Tools return ``{"error", "hint"}`` as an
ordinary successful result rather than raising. That sidesteps the SDK v2 defect
entirely: the sibling Dominican project had to wrap the low-level ``tools/call``
handler because v2 still hardcodes ``is_error=False`` on the success path and
rebuilds the error path from ``str(exc)`` with no structured content. If nothing
ever raises, that broken path is never walked, and no handler patch is needed
here.

**Why `hint` and not just a better `error`.** The error says what happened; the
hint says what to do next. A model given only "portal returned 403" retries. A
model told "this portal refuses programmatic access; try another country or use
cross_country_search which returns per-country errors without failing the whole
call" does something useful on the next turn.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("opendata-latam-mcp")

# Keep the model's context bounded even in the failure path. A portal that
# returns an HTML error page can otherwise put kilobytes of markup in the error.
MAX_ERROR_CHARS = 400


def _hint_for(message: str) -> str:
    """Map a failure to what the model should try next.

    Ordered most specific first. Every branch names an action, not a diagnosis:
    "the portal is refusing" is a diagnosis, "try another country" is an action.
    """
    low = message.lower()

    if "unknown country" in low:
        return (
            "Call list_supported_countries to see valid ISO alpha-2 codes. "
            "This server covers a fixed set of national portals; a country not "
            "on that list is not supported yet, and retrying will not change it."
        )
    if "kind must be one of" in low:
        return "Pass kind as one of: dataset, organization, group, tag."
    # Before any status-code branch, on purpose. This message embeds the first
    # bytes of the page the portal sent, and a maintenance page that says "404
    # Not Found" or "Request timeout" in its body would otherwise be claimed by
    # the identifier or timeout branch and send the model to fix an argument
    # that was fine. The marker is ours, so it is the most specific thing here.
    if "non-json body" in low:
        return (
            "The portal answered with a web page instead of the API — a WAF, "
            "maintenance or error page. The request was well-formed; retrying it "
            "will not help. Try another country, or come back later."
        )
    if "http 403" in low or "forbidden" in low:
        return (
            "The portal is refusing programmatic access — this is the portal's "
            "policy, not a bad request, so retrying the same call will fail the "
            "same way. Try another country, or use cross_country_search, which "
            "reports a per-country error without failing the whole call."
        )
    if "http 404" in low or "not found" in low:
        return (
            "That identifier does not exist on this portal. Identifiers are not "
            "shared between countries — an id from one portal is meaningless on "
            "another. Use search_datasets or search_resources to get a valid one."
        )
    if "http 429" in low or "too many" in low:
        return "The portal is rate-limiting. Wait before retrying and request fewer rows."
    if "timeout" in low:
        return (
            "The portal did not answer in time. Retry once; if it persists, "
            "lower `limit`, since large pages are what these portals are slowest at."
        )
    # CKAN's own errors are checked BEFORE the network branch. Portals forward
    # messages like "database connection failed" inside a CKAN error, and a bare
    # "connect" substring would claim those for the network hint — sending the
    # model to retry a call the portal rejected on its contents. Specific marker
    # first; a test pins this ordering so a future reshuffle fails loudly.
    if "ckan error" in low:
        return (
            "The portal accepted the request and rejected its contents. Check the "
            "argument values; the portal's own message is in `error`."
        )
    if "network error" in low or "connect" in low:
        return (
            "The portal was unreachable — a DNS or connectivity failure on its "
            "side or on this machine's. Retry once, then try another country."
        )
    if "http 5" in low:
        return "The portal has a server-side fault. Retry once, then try another country."
    return (
        "Unexpected failure. The original message is in `error`. If it names an "
        "argument, correct it; otherwise try another country or another dataset."
    )


def build_error(exc: Exception, *, tool: str, country: str | None = None) -> dict[str, Any]:
    """Turn an exception into the envelope, keeping the original message.

    The original text is never swallowed. It is the difference between a model
    that can act and a model that guesses — which is the whole reason this
    module exists.
    """
    message = str(exc).strip() or exc.__class__.__name__
    if len(message) > MAX_ERROR_CHARS:
        message = message[:MAX_ERROR_CHARS].rstrip() + "…"

    out: dict[str, Any] = {"error": message, "hint": _hint_for(message), "tool": tool}
    if country:
        out["country"] = country
    return out


def tool_envelope(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a tool so it returns the envelope instead of raising.

    Applied under ``@mcp.tool()`` so the decorator sees the wrapper and derives
    the schema from it — ``functools.wraps`` carries the signature, annotations
    and docstring across, which is what the SDK reads.

    One constraint this imposes on every tool, and it is not optional: **the
    return annotation must be ``dict``.** SDK v2 generates an output schema from
    the annotation and validates against it, so a tool annotated ``-> list[str]``
    that returns the error dict raises ``UnexpectedToolError`` — turning a
    handled failure back into the opaque one this module exists to remove.
    Measured, not assumed. Tools that used to return bare lists now wrap them in
    a named key, which also gives the model the portal context a bare list never
    carried.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — converting every failure is the point
            country = kwargs.get("country")
            logger.warning("%s failed (country=%s): %s", fn.__name__, country, exc)
            return build_error(exc, tool=fn.__name__, country=country)

    return wrapper

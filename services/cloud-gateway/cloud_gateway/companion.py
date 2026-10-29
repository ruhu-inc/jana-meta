"""The personal learning agent's admission on the chat route (W8, SPEC §19.4, §19.7, JM-D21).

The device names a call's engine role in `X-Jana-Role`, as it does for every role; the gateway admits the Study
companion (`companion`) and the Reflector's tutor-memory job on Spark (`reflector`) here, before any provider sees
the call:

1. The call's upper bound (its input bound, `inference_budget.input_bound`, and its output cap, at the model's price)
   is held in this daily ledger under its feature, `companion` or `reflector`, against `companion.per_day_usd`; the
   forwarded body carries that output cap, so the bound is a true bound. The call keeps its feature as its role, so
   the deployment's inference budget (when one is set) holds the same bound under it too, and its request row is
   recorded under it. When the call ends, its hold is replaced by the cost recorded for it.
2. A request that starts a turn or a job counts against the plan's `companion_turns_per_day` or
   `tutor_memory_jobs_per_day` (`Limits`); a request whose last message is a tool result continues the turn already
   counted (a tool round is two requests, SPEC §19.7), so it is held against the spend but not counted again.

Both are kept per session pseudonym per UTC day. At a cap the call is refused 429 `plan_limit` until midnight UTC. The
refusal never says "quota": that word makes the device pause the whole cloud tier (MDL-24), and only this feature has
reached its limit. An unset limit is no limit. An aid made from the companion's thread is a Study job (`/v1/study`,
role `study`), charged to Study's own feature, never here.

Privacy (PRV-25, OBS-22): a row's key is an HMAC of the subscription and the pseudonym under the day's key
(`GatewayStore.device_hash`), and that key is deleted at the day's rollover, so no pseudonym is stored and no row links
to another day; a day's rows are deleted once it is over. No prompt or reply is stored."""

from __future__ import annotations

import math
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from cloud_gateway.config import GatewayConfig, ModelSpec
from cloud_gateway.errors import DeviceError
from cloud_gateway.inference_budget import MICROS, input_bound, micros
from cloud_gateway.providers.base import Usage
from cloud_gateway.quotas import cost_usd
from cloud_gateway.store import GatewayStore, day_of

# The roles this module admits, each a ledger feature, and the plan limit that caps its count per day.
FEATURES: dict[str, str] = {"companion": "companion_turns_per_day", "reflector": "tutor_memory_jobs_per_day"}
WHAT = {"companion": "the day's companion turns", "reflector": "the day's tutor-memory jobs"}
CODE = "plan_limit"
SCHEMA = """
CREATE TABLE IF NOT EXISTS companion_days (
    day TEXT NOT NULL, holder TEXT NOT NULL, feature TEXT NOT NULL, counted INTEGER NOT NULL,
    spent_micros INTEGER NOT NULL, held_micros INTEGER NOT NULL, PRIMARY KEY (day, holder, feature));
CREATE TABLE IF NOT EXISTS companion_holds (
    id TEXT PRIMARY KEY, day TEXT NOT NULL, holder TEXT NOT NULL, feature TEXT NOT NULL,
    reserved_micros INTEGER NOT NULL);
"""


def daily_cap(config: GatewayConfig, feature: str) -> int | None:
    """A feature's count per day from the paid plans' limits (TABLE BIZ-18a). A credential does not name its plan and
    every paid plan gives the same limits (D121), so the lowest one set applies; none set is no cap."""
    caps = [getattr(plan.limits, FEATURES[feature]) for plan in config.plans.paid.values()]
    named = [cap for cap in caps if cap is not None]
    return min(named) if named else None


def bounded(config: GatewayConfig, body: dict[str, Any]) -> dict[str, Any]:
    """The body with its output capped as the inference budget caps it: the request's own limit, if it names one,
    within `deployment_max_output_tokens`, sent as `max_completion_tokens`."""
    limit = config.quotas.deployment_max_output_tokens
    for field in ("max_tokens", "max_completion_tokens"):
        value = body.get(field)
        if type(value) is int and value >= 0:
            limit = min(limit, value)
    capped = {name: value for name, value in body.items() if name != "max_tokens"}
    capped["max_completion_tokens"] = limit
    return capped


def bound_usd(config: GatewayConfig, model: ModelSpec, body: dict[str, Any]) -> float:
    """The most a bounded body can cost on its model: every input token uncached and the full output cap."""
    usage = Usage(input_bound(body, config.quotas.deployment_image_input_tokens), body["max_completion_tokens"])
    return cost_usd(config.prices.get(model.id), usage)


def continues(body: dict[str, Any]) -> bool:
    """The request carries a tool result last: the second request of a turn already counted."""
    messages = body.get("messages") or []
    return bool(messages) and isinstance(messages[-1], dict) and messages[-1].get("role") == "tool"


class CompanionLedger:
    def __init__(self, config: GatewayConfig, store: GatewayStore, clock: Callable[[], float]) -> None:
        self.config, self.store, self.clock = config, store, clock
        self.per_day_micros = math.floor(config.companion.per_day_usd * MICROS)  # costs round up, the cap down
        store._db.executescript(SCHEMA)

    def holder(self, account: str, pseudonym: str, now: float) -> str:
        """The day's key for one session pseudonym of one subscription: never the pseudonym itself."""
        return self.store.device_hash(f"companion\x1f{account}\x1f{pseudonym}", now)

    def admit(self, account: str, pseudonym: str, feature: str, model: ModelSpec, body: dict[str, Any],
              now: float) -> tuple[str, dict[str, Any]] | DeviceError:  # fmt: skip
        """Hold the call's bound and count its turn or job, or say why not: (hold id, bounded body), else the
        `plan_limit` refusal."""
        sent = bounded(self.config, body)
        bound = micros(bound_usd(self.config, model, sent))
        holder, day = self.holder(account, pseudonym, now), day_of(now)
        counts = not continues(sent)
        cap = daily_cap(self.config, feature)
        with self.store._tx() as db:
            db.execute("DELETE FROM companion_days WHERE day < ?", (day,))
            db.execute("DELETE FROM companion_holds WHERE day < ?", (day,))
            row = db.execute("SELECT counted FROM companion_days WHERE day=? AND holder=? AND feature=?",
                             (day, holder, feature)).fetchone()  # fmt: skip
            counted = row[0] if row else 0
            if counts and cap is not None and counted >= cap:
                return refusal(WHAT[feature], now)
            spent, held = db.execute(
                "SELECT coalesce(sum(spent_micros),0), coalesce(sum(held_micros),0) FROM companion_days "
                "WHERE day=? AND holder=?",
                (day, holder),
            ).fetchone()
            if spent + held + bound > self.per_day_micros:
                return refusal("the day's companion spend", now)
            key = secrets.token_hex(16)
            db.execute(
                "INSERT INTO companion_days VALUES (?,?,?,?,0,?) ON CONFLICT(day, holder, feature) "
                "DO UPDATE SET counted=counted+excluded.counted, held_micros=held_micros+excluded.held_micros",
                (day, holder, feature, int(counts), bound),
            )
            db.execute("INSERT INTO companion_holds VALUES (?,?,?,?,?)", (key, day, holder, feature, bound))
        return key, sent

    def settle(self, key: str, cost: float) -> None:
        """Replace a hold with the call's recorded cost, once; a hold of a day already over is simply dropped."""
        with self.store._tx() as db:
            row = db.execute("SELECT day, holder, feature, reserved_micros FROM companion_holds WHERE id=?",
                             (key,)).fetchone()  # fmt: skip
            if row is None:
                return
            day, holder, feature, reserved = row
            db.execute("DELETE FROM companion_holds WHERE id=?", (key,))
            db.execute(
                "UPDATE companion_days SET held_micros=max(0, held_micros-?), spent_micros=spent_micros+? "
                "WHERE day=? AND holder=? AND feature=?",
                (reserved, micros(max(0.0, cost)), day, holder, feature),
            )

    def purge(self, now: float) -> None:
        """Delete every row of a day that is over."""
        day = day_of(now)
        with self.store._tx() as db:
            db.execute("DELETE FROM companion_days WHERE day < ?", (day,))
            db.execute("DELETE FROM companion_holds WHERE day < ?", (day,))


def refusal(what: str, now: float) -> DeviceError:
    """429 `plan_limit` until midnight UTC, when the day's counts start again."""
    midnight = datetime.fromtimestamp(now, UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    until = (midnight + timedelta(days=1)).timestamp() - now
    return DeviceError(429, CODE, f"Plan limit reached: {what}; it resets at midnight UTC.", until)

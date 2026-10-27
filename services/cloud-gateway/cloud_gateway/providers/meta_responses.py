"""Muse Spark web search through Meta's Responses API, for the research agent (SPEC §18.3 stage 3).

One ordinary request per sub-question: `POST {base}/responses` with the Study model, `tools: [{"type":
"web_search"}]`, `include: ["web_search_call.results"]` and `reasoning: {"effort": "low"}`. Not `background: true`:
measured 2026-10-27, a plain request took ~6 s while a background one queued for 36 s, and the job already runs in
the background. What came back in the live probes:

- `output` holds `reasoning` items (ignored), one or two `web_search_call` items (Spark searches by itself) with
  `action.query` and `results: [{type, title, url, snippet}]`, and a `message` whose `output_text` is Spark's answer.
- Snippets were usually empty and the answer carried no `url_citation` annotations, so the job fetches the pages
  itself; Spark's answer is a guide to which pages matter, never evidence. Annotations are read when present.
- `usage` has `input_tokens` and `output_tokens` (reasoning inside the output, in `output_tokens_details`), and
  never the searches: they are counted from the `web_search_call` items and priced per 1,000.

A sent request is never cancelled: a cancelled response reports no usage, so its cost could not be known. Nothing
here logs a prompt, an answer or a result. The key goes in the `Authorization` header only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from cloud_gateway.config import Price
from cloud_gateway.custody import Secret
from cloud_gateway.providers.base import UpstreamError, Usage
from cloud_gateway.providers.http import post_json
from cloud_gateway.quotas import cost_usd


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""


@dataclass(frozen=True)
class SearchReply:
    """One Responses reply: Spark's answer, the queries it ran, the results in the order given (cited URLs first),
    the number of searches billed and the token usage (None when the reply carried none)."""

    text: str
    queries: tuple[str, ...]
    results: tuple[SearchResult, ...]
    searches: int
    usage: Usage | None
    status: str


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int(value: Any) -> int:
    return value if type(value) is int and value >= 0 else 0


def parse_usage(raw: Any) -> Usage | None:
    """Responses usage as the gateway's `Usage`: reasoning is part of the output tokens and billed with them."""
    if not isinstance(raw, dict) or type(raw.get("input_tokens")) is not int:
        return None
    inputs, outputs = _dict(raw.get("input_tokens_details")), _dict(raw.get("output_tokens_details"))
    return Usage(_int(raw.get("input_tokens")), _int(raw.get("output_tokens")), _int(inputs.get("cached_tokens")),
                 _int(outputs.get("reasoning_tokens")))  # fmt: skip


def parse(raw: Any) -> SearchReply:
    """The searches, results, answer and usage of a Responses reply. Every `web_search_call` item is one billed
    search, whatever its status; results without an https URL are dropped; a URL seen twice is kept once."""
    if not isinstance(raw, dict) or not isinstance(raw.get("output", []), list):
        raise UpstreamError("bad_response", "the research response is not a Responses object")
    queries: list[str] = []
    found: list[SearchResult] = []
    cited: list[str] = []
    texts: list[str] = []
    searches = 0
    for item in raw.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "web_search_call":
            searches += 1
            action = _dict(item.get("action"))
            if isinstance(action.get("query"), str) and action["query"].strip():
                queries.append(action["query"].strip())
            for result in item.get("results") or action.get("sources") or []:
                if isinstance(result, dict) and isinstance(result.get("url"), str):
                    found.append(SearchResult(str(result.get("title") or "").strip(), result["url"].strip(),
                                              str(result.get("snippet") or "").strip()))  # fmt: skip
        elif item.get("type") == "message":
            for content in item.get("content") or []:
                if not isinstance(content, dict) or content.get("type") != "output_text":
                    continue
                texts.append(str(content.get("text") or ""))
                for note in content.get("annotations") or []:
                    if (
                        isinstance(note, dict)
                        and note.get("type") == "url_citation"
                        and isinstance(note.get("url"), str)
                    ):
                        cited.append(note["url"].strip())
                        if not any(r.url == note["url"].strip() for r in found):
                            found.append(SearchResult(str(note.get("title") or "").strip(), note["url"].strip()))
    # Pages Spark cited come first, then the rest in the order the search gave them.
    rank = {url: i for i, url in enumerate(dict.fromkeys(cited))}
    seen: set[str] = set()
    results = []
    for result in sorted(found, key=lambda r: (0, rank[r.url]) if r.url in rank else (1, 0)):
        if result.url.startswith("https://") and result.url not in seen:
            seen.add(result.url)
            results.append(result)
    status = str(raw.get("status") or "completed")
    return SearchReply("".join(texts), tuple(queries), tuple(results), searches, parse_usage(raw.get("usage")), status)


def search_cost(reply: SearchReply, price: Price | None, search_usd_per_1000: float) -> float | None:
    """What a reply billed: its tokens at the model's price plus its searches. None when the reply carried no usage."""
    if reply.usage is None:
        return None
    return cost_usd(price, reply.usage) + reply.searches * search_usd_per_1000 / 1000


class ResponsesClient:
    def __init__(self, base_url: str, model: str, key: Secret | None, client: httpx.AsyncClient, *,
                 timeout_s: float, max_output_tokens: int) -> None:  # fmt: skip
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._key = key
        self.client = client
        self.timeout = httpx.Timeout(timeout_s, connect=5.0)
        self.max_output_tokens = max_output_tokens

    def __repr__(self) -> str:
        return f"ResponsesClient(base_url={self.base_url!r}, model={self.model!r})"

    @property
    def configured(self) -> bool:
        return self._key is not None

    def body(self, instructions: str, prompt: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "instructions": instructions,
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            "tools": [{"type": "web_search"}],
            "include": ["web_search_call.results"],
            "reasoning": {"effort": "low"},
            "max_output_tokens": self.max_output_tokens,
        }

    async def search(self, instructions: str, prompt: str) -> SearchReply:
        if self._key is None:
            raise UpstreamError("upstream_auth", "no provider key in the secret source", extra={"unbilled": True})
        headers = {"authorization": f"Bearer {self._key.reveal()}", "content-type": "application/json"}
        raw = await post_json(self.client, f"{self.base_url}/responses", headers, self.body(instructions, prompt),
                              self.timeout)  # fmt: skip
        return parse(raw)

    async def aclose(self) -> None:
        await self.client.aclose()

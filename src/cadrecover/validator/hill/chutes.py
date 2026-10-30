"""Fixed-prompt Chutes vision inference. Generated source is never executed here."""

from __future__ import annotations

import base64
import json
import math
import os
import re
import sqlite3
import time
from dataclasses import dataclass

import httpx

from cadrecover.protocol import PublicChallenge
from cadrecover.validator.hill.budget import BudgetGuard


BASE_URL = "https://llm.chutes.ai/v1"
SYSTEM_PROMPT_V1 = """You reconstruct parametric CAD from an engineering drawing.
Read the attached PNG and the public challenge record. Return exactly one fenced
python code block, with no surrounding prose. Use build123d 0.13.0 to implement
the record's build_part(overrides) entry point, returning a single build123d Part.
Read default dimensions from the drawing. The initial call receives {}; hidden
edits pass only changed parameters. Merge overrides into your drawn defaults and
rebuild all dependent features. Follow the coordinate frame, edit rules, and
critical features exactly. All dimensions are millimetres. The validator scores
the drawing and three hidden edits equally. A missing or misplaced critical
feature zeroes that set. Do not read files, access the network, or export files.
Use only Python's standard library and build123d. Do not provide executable
top-level work other than imports, constants, and function/class definitions.
"""
# v2 adds a checked build123d API reference: v1 replies failed on invented calls (Align from ints,
# BuildPart.add_cylinder, positional extrude), which measured the prompt rather than the weights.
SYSTEM_PROMPT = SYSTEM_PROMPT_V1 + """
build123d 0.13.0 reference (algebra mode; every call below is checked against 0.13.0):
- Box(size_x, size_y, size_z, align=...) and Cylinder(radius, height, align=...). Cylinder takes a
  RADIUS. align is a tuple of Align members, e.g. (Align.CENTER, Align.CENTER, Align.MIN) puts the
  base on z=0; never pass numbers as Align.
- Pos(x, y, z) * shape moves a shape; Rot(rx, ry, rz) * shape rotates it (degrees).
- a + b unions; a - b and a -= b subtract. Subtract each tool in a loop.
- PolarLocations(radius, count) yields locations on a circle:
  for loc in PolarLocations(r, n): part -= loc * tool
- 2D sketches (Circle(radius), Rectangle(x, y), SlotCenterToCenter(center_separation, width)) become
  solids with extrude(sketch, amount=height). amount is a keyword argument.
- There are no BuildPart methods such as add_cylinder or add_box; do not use builder mode.
Example of the expected form of a solution (illustrative values, not this task):
```python
from build123d import Align, Box, Cylinder, PolarLocations, Pos, Rot, SlotCenterToCenter, extrude

BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)


def build_part(overrides):
    p = {"width": 120.0, "length": 80.0, "thickness": 10.0, "hole_diameter": 8.0,
         "bolt_count": 6, "bolt_circle_diameter": 50.0, "slot_length": 30.0, "slot_width": 8.0}
    p.update(overrides)
    t = p["thickness"]
    part = Box(p["width"], p["length"], t, align=BOTTOM)
    part -= Cylinder(15.0, t, align=BOTTOM)
    for loc in PolarLocations(p["bolt_circle_diameter"] / 2, int(p["bolt_count"])):
        part -= loc * Cylinder(p["hole_diameter"] / 2, t, align=BOTTOM)
    slot = extrude(SlotCenterToCenter(p["slot_length"] - p["slot_width"], p["slot_width"]), amount=t)
    part -= Pos(0, 30, 0) * Rot(0, 0, 90) * slot
    part -= Pos(45, 0, t - 2) * Cylinder(6.0, 2.0, align=BOTTOM)
    return part
```
"""
# Bumped whenever SYSTEM_PROMPT or the request shape changes; recorded on every match start.
HARNESS_VERSION = 2
SYSTEM_PROMPTS = {1: SYSTEM_PROMPT_V1, 2: SYSTEM_PROMPT}


class ChutesUnavailable(RuntimeError):
    """Infrastructure/configuration failure, not a miner's CAD failure."""


@dataclass(frozen=True)
class CatalogModel:
    id: str
    input_usd_per_million: float
    output_usd_per_million: float
    context_length: int
    max_output_length: int
    tee: bool = False

    @property
    def name(self) -> str:
        return self.id.rsplit("/", 1)[-1]

    def cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (prompt_tokens * self.input_usd_per_million
                + completion_tokens * self.output_usd_per_million) / 1_000_000


@dataclass(frozen=True)
class Generation:
    source: str | None
    error: str | None
    latency_s: float
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float


def extract_source(content: object) -> str | None:
    if not isinstance(content, str):
        return None
    match = re.fullmatch(r"\s*```python[ \t]*\r?\n(.*?)\r?\n```\s*", content, flags=re.DOTALL)
    if not match or not match.group(1).strip() or "```" in match.group(1):
        return None
    return match.group(1).strip() + "\n"


def _positive_int(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError("Missing positive token limit")
    return value


class ChutesRunner:
    def __init__(self, con: sqlite3.Connection, *, total_cap: float = 3.0, match_cap: float = .50,
                 http: httpx.Client | None = None, max_output_tokens: int = 4096, timeout_s: float = 180,
                 include_expensive: bool = False):
        if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 8192:
            raise ValueError("max_output_tokens must be between 1 and 8192")
        self.budget = BudgetGuard(con, total_cap=total_cap, match_cap=match_cap)
        self.http = http or httpx.Client(timeout=timeout_s, follow_redirects=False)
        self._owns_http = http is None
        self.max_output_tokens = max_output_tokens
        self.timeout_s = timeout_s
        self.include_expensive = include_expensive
        self._catalog: dict[str, CatalogModel] | None = None

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def catalog(self) -> list[CatalogModel]:
        """Only priced vision models, with the cheap baseline first. GET is free."""
        try:
            response = self.http.get(f"{BASE_URL}/models", timeout=self.timeout_s)
            response.raise_for_status()
            records = response.json()["data"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise ChutesUnavailable("Chutes catalog unavailable") from None
        models = []
        for record in records:
            if "image" not in record.get("input_modalities", []):
                continue
            model_id = record.get("id", "")
            if not self.include_expensive and "kimi-k3" in model_id.lower():
                continue
            try:
                prices = record.get("price", {})
                fallback = record.get("pricing", {})
                input_price = float(prices["input"]["usd"] if "input" in prices else fallback["prompt"])
                output_price = float(prices["output"]["usd"] if "output" in prices else fallback["completion"])
                if not model_id or any(not math.isfinite(p) or p < 0 for p in (input_price, output_price)):
                    continue
                context = _positive_int(record.get("context_length", record.get("max_model_len")))
                max_output = _positive_int(record.get("max_output_length"))
                models.append(CatalogModel(model_id, input_price, output_price, context, max_output,
                                           bool(record.get("confidential_compute", False))))
            except (KeyError, ValueError, TypeError):
                # Unknown prices/limits cannot support a safe upper-bound reservation.
                continue
        models.sort(key=lambda m: (0 if "gemma-4-31b-turbo" in m.id.lower() else 1,
                                   m.cost(4096, self.max_output_tokens), m.id))
        self._catalog = {m.id: m for m in models}
        return models

    def generate(self, model_id: str, public: PublicChallenge, png_bytes: bytes, match_id: str,
                 harness: int = HARNESS_VERSION) -> Generation:
        """Make one request, with at most one separately reserved network retry.

        BudgetExceeded and ChutesUnavailable propagate: neither may become a
        zero-quality miner result. Invalid model output returns a Generation
        error and still incurs its reported token cost.
        """
        api_key = os.environ.get("CHUTES_API_KEY")
        if not api_key:
            raise ChutesUnavailable("CHUTES_API_KEY is not configured")
        if harness not in SYSTEM_PROMPTS:
            raise ChutesUnavailable(f"Unknown harness version {harness}")
        if self._catalog is None:
            self.catalog()
        model = self._catalog.get(model_id)
        if model is None:
            raise ChutesUnavailable("Model is not in the enabled priced vision catalog")
        output_limit = min(self.max_output_tokens, model.max_output_length)
        if output_limit >= model.context_length:
            raise ChutesUnavailable("Output token limit leaves no room for the drawing")
        # Reserving the entire possible context bounds image tokens without
        # guessing the model's image tiling/tokenizer. The server enforces context.
        reservation = model.cost(model.context_length, output_limit)
        public_json = json.dumps(public.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        payload = {
            "model": model_id, "temperature": 0, "max_tokens": output_limit, "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPTS[harness]},
                {"role": "user", "content": [
                    {"type": "text", "text": "Public challenge record:\n" + public_json},
                    {"type": "image_url", "image_url": {
                        "url": "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")}},
                ]},
            ],
        }
        started = time.monotonic()
        incurred = 0.0
        for attempt in range(2):
            spend_id = self.budget.reserve(match_id, model_id, reservation)
            try:
                response = self.http.post(
                    f"{BASE_URL}/chat/completions", json=payload,
                    headers={"Authorization": "Bearer " + api_key}, timeout=self.timeout_s,
                    follow_redirects=False,
                )
            except httpx.TransportError:
                self.budget.mark_unknown(spend_id)
                incurred += reservation
                if attempt == 0:
                    continue
                raise ChutesUnavailable("Chutes network failure after one retry; charges reserved") from None
            if response.status_code != 200:
                self.budget.mark_unknown(spend_id)
                raise ChutesUnavailable(f"Chutes HTTP {response.status_code}; charge reserved")
            try:
                data = response.json()
                usage = data["usage"]
                prompt = usage["prompt_tokens"]
                completion = usage["completion_tokens"]
                if any(type(n) is not int or n < 0 for n in (prompt, completion)):
                    raise ValueError("Invalid token usage")
                if prompt > model.context_length or completion > output_limit:
                    raise ValueError("Token usage exceeds the request bounds")
                if prompt + completion > model.context_length:
                    raise ValueError("Token usage exceeds model context")
                if "total_tokens" in usage and usage["total_tokens"] != prompt + completion:
                    raise ValueError("Inconsistent token usage")
            except (ValueError, KeyError, TypeError):
                self.budget.mark_unknown(spend_id)
                raise ChutesUnavailable("Chutes returned invalid token usage; charge reserved") from None
            cost = model.cost(prompt, completion)
            self.budget.settle(spend_id, cost, prompt_tokens=prompt, completion_tokens=completion)
            from cadrecover.storage import db
            def safe_id(value):
                return value[:256] if isinstance(value,str) else None
            db.add_event(self.budget.con,"hill.provider_response",{
                "match_id":match_id,"spend_id":spend_id,"endpoint":f"{BASE_URL}/chat/completions",
                "status_code":response.status_code,"requested_model":model_id,
                "reported_model":safe_id(data.get("model")),"response_id":safe_id(data.get("id")),
                "request_id":safe_id(response.headers.get("x-request-id") or response.headers.get("x-chutes-request-id")),
                "prompt_tokens":prompt,"completion_tokens":completion,"cost_usd":cost})
            incurred += cost
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                content = None
            source = extract_source(content)
            return Generation(source, None if source else "Expected exactly one python code block",
                              time.monotonic() - started, prompt, completion, incurred)
        raise AssertionError("unreachable")

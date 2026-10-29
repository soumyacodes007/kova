"""Readable terminal logs for the validator and the auditor (owner: agent C).

`round.py` and `auditor.py` take a `log=print` callable and emit plain text lines
(`[round] …`, `  uid 2 mock-oracle done Q 100.0 sets […]`, `[chain] …`, `[audit] …`). This module
turns those lines into Rich-styled output without touching either module: colours for
pass/fail, Q values graded green / yellow / red. When stdout is not a terminal Rich prints
the same text without colour, so redirected logs stay greppable.
"""

from __future__ import annotations

import re

from rich.console import Console
from rich.markup import escape

Q_GOOD, Q_OK = 85.0, 50.0  # 50 is the reward floor (PRD v2.1)

_TAGS = {"round": "bold cyan", "chain": "bold magenta", "audit": "bold blue"}
_TAG = re.compile(r"^(\s*)\[(round|chain|audit)\]")
_UID = re.compile(r"^(\s+)uid (\d+)(\s+)(.*?)(\s+)(done|failed|timeout|pending|sent)(\s+)Q(\s+)([\d.]+|—)(.*)$")
_Q = re.compile(r"\bQ ([\d.]+)")
_VERDICT = re.compile(r"-> (PASS|FAIL|INCONCLUSIVE)")
_STATUS_STYLE = {"done": "green", "failed": "red", "timeout": "yellow", "pending": "dim", "sent": "dim"}
_VERDICT_STYLE = {"PASS": "bold green", "FAIL": "bold red", "INCONCLUSIVE": "bold yellow"}


def q_style(q: float) -> str:
    return "bold green" if q >= Q_GOOD else "yellow" if q >= Q_OK else "bold red"


def style_line(line: str) -> str:
    """Rich markup for one log line. Pure function, so it is easy to test."""
    m = _UID.match(line)
    if m:
        lead, uid, s1, label, s2, status, s3, s4, qtext, rest = m.groups()
        qs = "dim" if qtext == "—" else q_style(float(qtext))
        return (f"{lead}[bold]uid {uid}[/]{s1}[cyan]{escape(label)}[/]{s2}[{_STATUS_STYLE[status]}]{status}[/]{s3}"
                f"Q{s4}[{qs}]{qtext}[/][dim]{escape(rest)}[/]")
    text = escape(line)
    text = _Q.sub(lambda mm: f"Q [{q_style(float(mm.group(1)))}]{mm.group(1)}[/]", text)
    text = _VERDICT.sub(lambda mm: f"-> [{_VERDICT_STYLE[mm.group(1)]}]{mm.group(1)}[/]", text)
    t = _TAG.match(line)
    if t:
        tag = f"{t.group(1)}\\[{t.group(2)}]"
        text = f"[{_TAGS[t.group(2)]}]{tag}[/]" + text[len(tag):]
    low = line.lower()
    if "failed" in low or "not readable" in low or "outage" in low:
        text = f"[red]{text}[/]" if not t else text
    elif line.lstrip().startswith("task ") or line.lstrip().startswith("poll "):
        text = f"[dim]{text}[/]"
    return text


def rich_logger(console: Console | None = None):
    """A `log(str)` callable for run_round / run_audits."""
    console = console or Console(highlight=False, soft_wrap=True)

    def log(line: str = "") -> None:
        console.print(style_line(str(line)))

    return log


def plain_logger():
    return print

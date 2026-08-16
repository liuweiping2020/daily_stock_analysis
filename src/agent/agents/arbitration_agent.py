# -*- coding: utf-8 -*-
"""
ArbitrationAgent — fact-checking and cross-verification specialist.

Responsible for:
- Cross-verifying the data points cited by prior agents (prices, PE/PB,
  news events, capital-flow figures)
- Flagging hallucinations, conflicts, or stale facts
- Returning corrected facts so the downstream debate / decision agents
  operate on a verified evidence base

The arbitration agent has read access to a small set of market-data tools
so it can re-fetch authoritative values when a prior agent's claim looks
suspicious.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from src.agent.agents.base_agent import BaseAgent
from src.agent.protocols import AgentContext, AgentOpinion
from src.agent.runner import try_parse_json
from src.report_language import normalize_report_language

logger = logging.getLogger(__name__)


class ArbitrationAgent(BaseAgent):
    """Fact-checking / arbitration agent that verifies prior agent claims."""

    agent_name = "arbitration"
    max_steps = 4
    tool_names = [
        "get_realtime_quote",
        "get_stock_info",
        "search_stock_news",
    ]

    def system_prompt(self, ctx: AgentContext) -> str:
        report_language = normalize_report_language(ctx.meta.get("report_language", "zh"))
        prompt = """\
You are a **Fact Arbitration Agent** for a multi-agent stock analysis \
pipeline.

Earlier agents (technical, intel, risk) have produced opinions that cite \
concrete data points: prices, PE/PB ratios, news events, capital-flow \
figures, support/resistance levels. Your job is to **independently \
verify** those claims against authoritative data and flag any \
hallucinations, conflicts, or stale values.

## Workflow
1. Read the prior agent opinions and extract every concrete factual \
   claim (price, valuation ratio, news headline, capital-flow number, \
   key level).
2. For each high-impact claim, call the appropriate tool \
   (`get_realtime_quote`, `get_stock_info`, `search_stock_news`) to \
   fetch the authoritative value.
3. Compare cited vs. authoritative values and classify each as:
   - `verified` — within a reasonable tolerance
   - `conflict` — materially different (flag the correct value)
   - `hallucination` — cited value has no supporting evidence
   - `stale` — correct direction but outdated number
4. Return a corrected fact sheet and a list of discrepancies.

## Output Format
Return **only** a JSON object (no markdown fences):
{
  "verified_facts": {
    "current_price": <float>,
    "pe": <float|null>,
    "pb": <float|null>,
    "market_cap": <float|null>,
    "key_news": ["headline 1", "headline 2"]
  },
  "discrepancies": [
    {
      "claim": "PE = 35",
      "source_agent": "technical",
      "authoritative_value": "PE = 58",
      "classification": "conflict|hallucination|stale|verified",
      "note": "short explanation"
    }
  ],
  "signal": "buy|hold|sell",
  "confidence": 0.0-1.0,
  "reasoning": "2-3 sentence summary of the fact-check outcome",
  "has_hallucination": true|false,
  "has_conflict": true|false
}

Important: only flag a claim as `hallucination` or `conflict` when you have \
authoritative evidence to back the correction. If you cannot verify a \
claim, leave it out of the discrepancies list rather than guessing.
"""
        if report_language == "en":
            return prompt + "\nWrite all human-readable JSON values in English.\n"
        return prompt + "\n所有面向用户的人类可读文本值必须使用中文。\n"

    def build_user_message(self, ctx: AgentContext) -> str:
        parts = [
            f"# Fact Arbitration Request for {ctx.stock_code}",
            f"Stock: {ctx.stock_code} ({ctx.stock_name})" if ctx.stock_name else f"Stock: {ctx.stock_code}",
            "",
        ]

        # Surface pre-fetched data so the arbitration agent does not redo
        # searches already performed by the intel / technical agents.
        realtime = ctx.get_data("realtime_quote")
        if realtime is not None:
            parts.append("## Pre-fetched realtime quote")
            parts.append(json.dumps(realtime, ensure_ascii=False, default=str))
            parts.append("")

        if not ctx.opinions:
            parts.append("No prior agent opinions to verify.")
            return "\n".join(parts)

        parts.append("## Prior Agent Opinions (extract claims from these)")
        for op in ctx.opinions:
            parts.append(f"\n### {op.agent_name}")
            parts.append(f"Signal: {op.signal} | Confidence: {op.confidence:.2f}")
            parts.append(f"Reasoning: {op.reasoning}")
            if op.key_levels:
                parts.append(f"Key levels: {json.dumps(op.key_levels, ensure_ascii=False)}")
            if op.raw_data:
                # Emphasise the numeric / factual fields most likely to
                # contain citable claims (valuation, flow, news).
                extra_keys = {
                    k: v for k, v in op.raw_data.items()
                    if k not in ("signal", "confidence", "reasoning", "key_levels")
                }
                if extra_keys:
                    parts.append(f"Extra data: {json.dumps(extra_keys, ensure_ascii=False, default=str)}")
            parts.append("")

        parts.append(
            "Extract every concrete factual claim from the opinions above, "
            "verify each high-impact claim against authoritative data, and "
            "return the arbitration JSON."
        )
        return "\n".join(parts)

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        parsed = try_parse_json(raw_text)
        if parsed is None:
            logger.warning("[ArbitrationAgent] failed to parse arbitration JSON")
            return None

        # Cache the verified fact sheet so the debate / decision agents can
        # reuse the corrected numbers instead of re-fetching.
        ctx.set_data("arbitration_facts", parsed)

        discrepancies = parsed.get("discrepancies", []) or []
        has_hallucination = bool(parsed.get("has_hallucination")) or any(
            str(d.get("classification", "")).lower() == "hallucination"
            for d in discrepancies if isinstance(d, dict)
        )
        has_conflict = bool(parsed.get("has_conflict")) or any(
            str(d.get("classification", "")).lower() == "conflict"
            for d in discrepancies if isinstance(d, dict)
        )

        # The arbitration agent's signal is informational: it nudges the
        # debate / decision stage rather than overriding them. Default to
        # hold so we do not double-count prior agent signals.
        signal = parsed.get("signal") or "hold"
        if signal not in {"buy", "hold", "sell"}:
            signal = "hold"

        # Confidence drops when we uncovered hallucinations or conflicts,
        # because the prior evidence base is unreliable.
        confidence = float(parsed.get("confidence", 0.5))
        if has_hallucination:
            confidence = min(confidence, 0.35)
        elif has_conflict:
            confidence = min(confidence, 0.55)

        return AgentOpinion(
            agent_name=self.agent_name,
            signal=signal,
            confidence=confidence,
            reasoning=parsed.get("reasoning", ""),
            raw_data={
                "verified_facts": parsed.get("verified_facts", {}),
                "discrepancies": discrepancies,
                "has_hallucination": has_hallucination,
                "has_conflict": has_conflict,
                **parsed,
            },
        )

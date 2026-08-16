# -*- coding: utf-8 -*-
"""
DebateAgent — multi-agent bull/bear debate moderator.

Responsible for:
- Reading prior agent opinions (technical / intel / risk / arbitration)
- Synthesising a structured bull case (reasons to buy) and bear case
  (reasons to sell / avoid)
- Producing a net signal based on which side wins, with a confidence
  derived from argument strength and consensus

The debate agent works purely from ``ctx.opinions`` (no tool calls), so it
is cheap to run and acts as an adversarial cross-check before the final
decision stage.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from src.agent.agents.base_agent import BaseAgent
from src.agent.protocols import AgentContext, AgentOpinion
from src.agent.runner import try_parse_json
from src.report_language import normalize_report_language

logger = logging.getLogger(__name__)


# Signals treated as bullish / bearish when tallying prior opinions.
_BULL_SIGNALS = {"strong_buy", "buy"}
_BEAR_SIGNALS = {"strong_sell", "sell"}


class DebateAgent(BaseAgent):
    """Bull-bear debate moderator that synthesises prior opinions."""

    agent_name = "debate"
    max_steps = 3  # pure synthesis from context, should not need many steps
    tool_names: Optional[List[str]] = []  # no tool access — works from context only

    def system_prompt(self, ctx: AgentContext) -> str:
        report_language = normalize_report_language(ctx.meta.get("report_language", "zh"))
        prompt = """\
You are a **Bull-Bear Debate Moderator** for a multi-agent stock analysis \
pipeline.

You will receive the structured opinions produced by earlier agents \
(technical, intel, risk, arbitration). Your job is to construct a \
rigorous, balanced debate between a **bull** (买入方) and a **bear** \
(卖出方), then deliver a verdict on which side prevails.

## Debate Rules
1. **Bull case**: assemble the strongest reasons to BUY or HOLD, citing \
   technical momentum, positive catalysts, capital-flow support, and \
   attractive risk/reward.
2. **Bear case**: assemble the strongest reasons to SELL or AVOID, citing \
   trend weakness, risk flags, valuation extremes, negative news, and \
   main-force outflow.
3. Each point must be backed by an explicit reference to a prior agent's \
   evidence (e.g. "[technical]", "[intel]", "[risk]"). Do not fabricate \
   facts not present in the inputs.
4. **Verdict**: weigh the arguments and declare a winner. If the evidence \
   is genuinely mixed, declare a draw (hold).

## Output Format
Return **only** a JSON object (no markdown fences):
{
  "bull_points": ["reason 1", "reason 2", ...],
  "bear_points": ["reason 1", "reason 2", ...],
  "winner": "bull|bear|draw",
  "signal": "strong_buy|buy|hold|sell|strong_sell",
  "confidence": 0.0-1.0,
  "reasoning": "2-3 sentence verdict summary",
  "key_levels": {"support": <float>, "resistance": <float>}
}

Important: ``confidence`` reflects the *strength of the winning argument*, \
not your general certainty. A draw should land near 0.4-0.5.
"""
        if report_language == "en":
            return prompt + "\nWrite all human-readable JSON values in English.\n"
        return prompt + "\n所有面向用户的人类可读文本值必须使用中文。\n"

    def build_user_message(self, ctx: AgentContext) -> str:
        parts = [
            f"# Debate Request for {ctx.stock_code}",
            f"Stock: {ctx.stock_code} ({ctx.stock_name})" if ctx.stock_name else f"Stock: {ctx.stock_code}",
            "",
        ]

        if not ctx.opinions:
            parts.append("No prior agent opinions available. Declare a draw (hold).")
            return "\n".join(parts)

        parts.append("## Prior Agent Opinions")
        for op in ctx.opinions:
            parts.append(f"\n### {op.agent_name}")
            parts.append(f"Signal: {op.signal} | Confidence: {op.confidence:.2f}")
            parts.append(f"Reasoning: {op.reasoning}")
            if op.key_levels:
                parts.append(f"Key levels: {json.dumps(op.key_levels, ensure_ascii=False)}")
            if op.raw_data:
                extra_keys = {
                    k: v for k, v in op.raw_data.items()
                    if k not in ("signal", "confidence", "reasoning", "key_levels")
                }
                if extra_keys:
                    parts.append(f"Extra data: {json.dumps(extra_keys, ensure_ascii=False, default=str)}")
            parts.append("")

        if ctx.risk_flags:
            parts.append("## Risk Flags")
            for rf in ctx.risk_flags:
                parts.append(
                    f"- [{rf.get('severity', 'medium')}] "
                    f"{rf.get('category', '')}: {rf.get('description', '')}"
                )
            parts.append("")

        parts.append(
            "Construct the bull and bear cases from the opinions above, "
            "then return the JSON verdict."
        )
        return "\n".join(parts)

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        parsed = try_parse_json(raw_text)
        if parsed is None:
            logger.warning("[DebateAgent] failed to parse debate JSON, falling back to tally")
            return self._fallback_opinion(ctx)

        winner = str(parsed.get("winner", "draw")).lower().strip()
        signal = parsed.get("signal") or _winner_to_signal(winner)
        confidence = float(parsed.get("confidence", 0.5))

        # Sanity-check the declared signal against the winner; if they
        # contradict each other, trust the winner (more constrained).
        expected = _winner_to_signal(winner)
        if expected == "hold" and signal in _BULL_SIGNALS.union(_BEAR_SIGNALS):
            # Allow a "draw" winner with a lean, but cap the confidence.
            confidence = min(confidence, 0.5)
        elif expected != "hold" and signal not in _signals_for_winner(expected):
            signal = expected

        return AgentOpinion(
            agent_name=self.agent_name,
            signal=signal,
            confidence=confidence,
            reasoning=parsed.get("reasoning", ""),
            key_levels={
                k: float(v) for k, v in (parsed.get("key_levels") or {}).items()
                if isinstance(v, (int, float))
            },
            raw_data={
                "bull_points": parsed.get("bull_points", []),
                "bear_points": parsed.get("bear_points", []),
                "winner": winner,
                **parsed,
            },
        )

    # -----------------------------------------------------------------
    # Fallback: derive a debate verdict mechanically when the LLM fails
    # to return structured JSON.
    # -----------------------------------------------------------------
    def _fallback_opinion(self, ctx: AgentContext) -> AgentOpinion:
        bull_score = 0.0
        bear_score = 0.0
        bull_points: List[str] = []
        bear_points: List[str] = []

        for op in ctx.opinions:
            weight = max(0.0, min(1.0, float(op.confidence)))
            sig = str(op.signal or "").lower()
            if sig in _BULL_SIGNALS:
                bull_score += weight
                if op.reasoning:
                    bull_points.append(f"[{op.agent_name}] {op.reasoning}")
            elif sig in _BEAR_SIGNALS:
                bear_score += weight
                if op.reasoning:
                    bear_points.append(f"[{op.agent_name}] {op.reasoning}")

        if bull_score > bear_score:
            winner = "bull"
            signal = "buy"
            confidence = min(0.8, bull_score / max(bull_score + bear_score, 1e-9))
        elif bear_score > bull_score:
            winner = "bear"
            signal = "sell"
            confidence = min(0.8, bear_score / max(bull_score + bear_score, 1e-9))
        else:
            winner = "draw"
            signal = "hold"
            confidence = 0.4

        reasoning = (
            f"Bull score {bull_score:.2f} vs bear score {bear_score:.2f}; "
            f"winner={winner}."
        )
        return AgentOpinion(
            agent_name=self.agent_name,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            raw_data={
                "bull_points": bull_points,
                "bear_points": bear_points,
                "winner": winner,
                "fallback": True,
            },
        )


def _winner_to_signal(winner: str) -> str:
    """Map a debate winner to a canonical signal."""
    return {
        "bull": "buy",
        "bear": "sell",
        "draw": "hold",
    }.get(winner, "hold")


def _signals_for_winner(winner_signal: str) -> set:
    """Return the set of signals compatible with a winner-derived signal."""
    if winner_signal == "buy":
        return _BULL_SIGNALS
    if winner_signal == "sell":
        return _BEAR_SIGNALS
    return {"hold"}

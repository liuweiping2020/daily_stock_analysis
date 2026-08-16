# -*- coding: utf-8 -*-
"""Financial Chain-of-Thought (CoT) prompt templates.

Inspired by FinRobot (arXiv 2405.14767), this module provides structured
prompt skeletons that break financial analysis into explicit reasoning steps:
1. Instruction (task definition)
2. Financial Context (market data, filings, news)
3. Financial Knowledge (domain rules, valuation models)
4. Chain-of-Thought (step-by-step reasoning)
5. Conclusion (answer + confidence)

This reduces LLM hallucination on financial facts by forcing explicit
domain knowledge injection and verifiable intermediate conclusions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FinancialCoTTemplate:
    """A 5-section Financial CoT prompt template."""

    role: str = ""                    # e.g. "技术面分析师"
    task: str = ""                    # e.g. "分析股票技术面并给出买卖建议"
    financial_context: str = ""       # market data, indicators, etc.
    financial_knowledge: str = ""     # domain rules, valuation methods
    cot_steps: List[str] = field(default_factory=list)  # reasoning steps
    conclusion_format: str = ""       # expected output format

    def render(self) -> str:
        """Render the full CoT prompt."""
        sections = []

        sections.append(f"[Instruction]\n你是一个{self.role}。任务：{self.task}\n")

        if self.financial_context:
            sections.append(f"[Financial Context]\n{self.financial_context}\n")

        if self.financial_knowledge:
            sections.append(f"[Financial Knowledge]\n{self.financial_knowledge}\n")

        if self.cot_steps:
            steps_text = "\n".join(
                f"Step {i+1}: {step}"
                for i, step in enumerate(self.cot_steps)
            )
            sections.append(f"[Chain-of-Thought]\n{steps_text}\n")

        if self.conclusion_format:
            sections.append(f"[Conclusion]\n{self.conclusion_format}\n")

        return "\n".join(sections)


# ============================================================
# Pre-built templates for common financial analysis tasks
# ============================================================

TECHNICAL_ANALYSIS_COT = FinancialCoTTemplate(
    role="技术面分析师",
    task="基于K线形态、技术指标和量价关系，分析股票短期走势并给出交易信号",
    financial_context="""
- 股票代码：{stock_code}
- 当前价格：{current_price}
- 近期K线数据：{recent_bars}
- 技术指标：{indicators}
""",
    financial_knowledge="""
- 趋势判断：MA5 > MA20 为多头排列，MA5 < MA20 为空头排列
- 超买超卖：RSI > 70 为超买，RSI < 30 为超卖
- 量价关系：放量上涨为多头信号，缩量下跌为空头信号
- 支撑压力位：近期低点为支撑，近期高点为压力
- MACD金叉/死叉：DIF上穿DEA为金叉（看多），下穿为死叉（看空）
""",
    cot_steps=[
        "识别当前趋势方向（上升/下降/震荡）",
        "检查关键技术指标信号（MA、RSI、MACD）",
        "分析量价配合情况",
        "确定支撑位和压力位",
        "综合评估给出交易信号（买入/持有/卖出）",
    ],
    conclusion_format="""请以JSON格式输出：
```json
{{
  "signal": "buy|hold|sell",
  "confidence": 0.0-1.0,
  "reasoning": "详细分析理由",
  "key_levels": {{"support": 0.0, "resistance": 0.0, "stop_loss": 0.0}}
}}
```""",
)

FUNDAMENTAL_ANALYSIS_COT = FinancialCoTTemplate(
    role="基本面分析师",
    task="基于财务数据和估值指标，评估公司基本面质量和投资价值",
    financial_context="""
- 股票代码：{stock_code}
- 股票名称：{stock_name}
- 财务数据：{financials}
- 估值指标：{valuation}
- 行业对比：{industry_comparison}
""",
    financial_knowledge="""
- PE估值：PE < 行业平均且增长稳健 = 低估
- ROE：持续 > 15% 为优秀
- 营收增长率：> 20% 为高增长
- 负债率：资产负债率 > 70% 需警惕
- 现金流：经营现金流持续为正是健康信号
""",
    cot_steps=[
        "评估盈利能力（ROE、净利率、毛利率趋势）",
        "评估成长性（营收/利润增长率）",
        "评估财务健康（负债率、现金流）",
        "对比行业估值水平",
        "综合给出基本面评分和投资建议",
    ],
    conclusion_format="""请以JSON格式输出：
```json
{{
  "signal": "buy|hold|sell",
  "confidence": 0.0-1.0,
  "reasoning": "基本面分析理由",
  "fundamental_score": 0-100,
  "valuation_level": "undervalued|fair|overvalued"
}}
```""",
)

RISK_ASSESSMENT_COT = FinancialCoTTemplate(
    role="风险评估师",
    task="识别和评估该股票的所有潜在风险因素",
    financial_context="""
- 股票代码：{stock_code}
- 近期新闻：{recent_news}
- 股东行为：{shareholder_actions}
- 监管信息：{regulatory_info}
- 估值异常：{valuation_anomalies}
""",
    financial_knowledge="""
- 减持风险：大股东或高管减持是负面信号
- 质押风险：高质押率（>50%）存在平仓风险
- 业绩变脸：预亏、业绩大幅下修需警惕
- 监管风险：处罚、立案调查是重大风险
- 估值风险：PE远高于行业均值存在回调风险
- 解禁风险：限售股解禁带来抛压
""",
    cot_steps=[
        "检查股东减持和质押情况",
        "检查业绩预警和财务异常",
        "检查监管处罚和合规风险",
        "检查估值是否偏离合理区间",
        "检查限售解禁时间表",
        "汇总风险等级和是否需要否决买入信号",
    ],
    conclusion_format="""请以JSON格式输出：
```json
{{
  "risk_level": "low|medium|high|critical",
  "risk_flags": ["风险1", "风险2"],
  "signal_override": "none|downgrade|veto",
  "reasoning": "风险评估理由"
}}
```""",
)

PORTFOLIO_DECISION_COT = FinancialCoTTemplate(
    role="投资组合经理",
    task="综合所有分析师意见，做出最终投资决策",
    financial_context="""
- 股票代码：{stock_code}
- 技术面分析：{technical_opinion}
- 基本面分析：{fundamental_opinion}
- 风险评估：{risk_assessment}
- 新闻舆情：{news_sentiment}
- 当前持仓：{current_position}
""",
    financial_knowledge="""
- 决策原则：风险优先，收益次之
- 仓位管理：高信心+低风险 → 重仓，低信心+高风险 → 轻仓或不建仓
- 止损纪律：每笔交易必须设定止损位
- 多空平衡：综合多空因素后给出明确方向
- 时效性：短期看技术面，长期看基本面
""",
    cot_steps=[
        "汇总各方信号和置信度",
        "评估风险因素是否构成否决条件",
        "确定仓位建议（0-100%）",
        "设定入场价、止损位和止盈位",
        "给出最终决策和理由",
    ],
    conclusion_format="""请以JSON格式输出：
```json
{{
  "action": "BUY|HOLD|SELL",
  "conviction": 0.0-1.0,
  "position_size": "light|medium|heavy|none",
  "entry_price": 0.0,
  "stop_loss": 0.0,
  "take_profit": 0.0,
  "reasoning": "决策理由",
  "summary": "一句话总结"
}}
```""",
)


# Template registry
_COT_TEMPLATES: Dict[str, FinancialCoTTemplate] = {
    "technical": TECHNICAL_ANALYSIS_COT,
    "fundamental": FUNDAMENTAL_ANALYSIS_COT,
    "risk": RISK_ASSESSMENT_COT,
    "portfolio": PORTFOLIO_DECISION_COT,
}


def get_cot_template(name: str) -> Optional[FinancialCoTTemplate]:
    """Get a CoT template by name."""
    return _COT_TEMPLATES.get(name)


def list_cot_templates() -> List[str]:
    """List available CoT template names."""
    return list(_COT_TEMPLATES.keys())


def render_cot_prompt(template_name: str, **kwargs) -> str:
    """Render a CoT prompt with variables filled in."""
    template = _COT_TEMPLATES.get(template_name)
    if template is None:
        return ""

    # Format context fields with provided kwargs
    rendered = FinancialCoTTemplate(
        role=template.role,
        task=template.task,
        financial_context=template.financial_context.format(**kwargs) if kwargs else template.financial_context,
        financial_knowledge=template.financial_knowledge,
        cot_steps=template.cot_steps,
        conclusion_format=template.conclusion_format,
    )
    return rendered.render()

# -*- coding: utf-8 -*-
"""Prompt engineering module — Financial CoT templates and prompt management."""

from src.prompts.cot_templates import (
    FinancialCoTTemplate,
    get_cot_template,
    list_cot_templates,
    render_cot_prompt,
    TECHNICAL_ANALYSIS_COT,
    FUNDAMENTAL_ANALYSIS_COT,
    RISK_ASSESSMENT_COT,
    PORTFOLIO_DECISION_COT,
)

__all__ = [
    "FinancialCoTTemplate",
    "get_cot_template",
    "list_cot_templates",
    "render_cot_prompt",
    "TECHNICAL_ANALYSIS_COT",
    "FUNDAMENTAL_ANALYSIS_COT",
    "RISK_ASSESSMENT_COT",
    "PORTFOLIO_DECISION_COT",
]

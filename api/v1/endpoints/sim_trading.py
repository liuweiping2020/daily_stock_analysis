# -*- coding: utf-8 -*-
"""Simulated trading endpoints — orders, executions, and positions."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_database_manager
from api.v1.schemas.common import ErrorResponse
from src.services.sim_trading_service import SimTradingError, SimTradingService
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------
# Request / response schemas (route-local)
# ---------------------------------------------------------------------
class OrderPlaceRequest(BaseModel):
    account_id: int = Field(..., description="组合账户 id")
    code: str = Field(..., description="股票代码")
    side: str = Field(..., description="buy/sell")
    quantity: float = Field(..., gt=0, description="数量（股）")
    price: Optional[float] = Field(None, gt=0, description="限价或市价参考价")
    order_type: str = Field("market", description="market/limit")


class OrderPlaceResponse(BaseModel):
    id: int
    account_id: int
    code: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float] = None
    status: str = "pending"


class OrderExecuteRequest(BaseModel):
    execution_price: float = Field(..., gt=0, description="成交价")


class ExecutionResponse(BaseModel):
    id: int
    order_id: int
    account_id: int
    code: str
    side: str
    quantity: float
    execution_price: float
    commission: float
    stamp_duty: float
    transfer_fee: float
    total_cost: float
    trade_date: Optional[str] = None
    executed_at: Optional[str] = None


class PositionLotItem(BaseModel):
    open_date: Optional[str] = None
    remaining_quantity: float
    unit_cost: float


class PositionItem(BaseModel):
    code: str
    market: Optional[str] = None
    currency: Optional[str] = None
    quantity: float
    avg_cost: float
    total_cost: float
    last_price: float
    market_value: float
    unrealized_pnl: float
    lots: List[PositionLotItem] = Field(default_factory=list)


class PositionsResponse(BaseModel):
    account_id: int
    positions: List[PositionItem] = Field(default_factory=list)


# ---------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------
@router.post(
    "/orders",
    response_model=OrderPlaceResponse,
    responses={
        400: {"description": "参数错误或交易规则校验失败", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="下达模拟订单",
    description="按 A 股规则（100 股整手、T+1）校验后下达模拟订单",
)
def place_order(
    request: OrderPlaceRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> OrderPlaceResponse:
    try:
        service = SimTradingService(db_manager)
        order = service.place_order(
            account_id=request.account_id,
            code=request.code,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            order_type=request.order_type,
        )
        return OrderPlaceResponse(
            id=order.id,
            account_id=order.account_id,
            code=order.code,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            status=order.status,
        )
    except SimTradingError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_order", "message": str(exc)},
        )
    except Exception as exc:
        logger.error(f"下达模拟订单失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"下达模拟订单失败: {str(exc)}"},
        )


@router.post(
    "/execute/{order_id}",
    response_model=ExecutionResponse,
    responses={
        400: {"description": "订单状态或 T+1 校验失败", "model": ErrorResponse},
        404: {"description": "订单不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="执行模拟订单",
    description="按成交价结算模拟订单，计算印花税/佣金/过户费并更新持仓",
)
def execute_order(
    order_id: int,
    request: OrderExecuteRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> ExecutionResponse:
    try:
        service = SimTradingService(db_manager)
        execution = service.execute_order(order_id, request.execution_price)
        return ExecutionResponse(
            id=execution.id,
            order_id=execution.order_id,
            account_id=execution.account_id,
            code=execution.code,
            side=execution.side,
            quantity=execution.quantity,
            execution_price=execution.execution_price,
            commission=execution.commission,
            stamp_duty=execution.stamp_duty,
            transfer_fee=execution.transfer_fee,
            total_cost=execution.total_cost,
            trade_date=execution.trade_date.isoformat() if execution.trade_date else None,
            executed_at=execution.executed_at.isoformat() if execution.executed_at else None,
        )
    except SimTradingError as exc:
        status_code = 404 if "not found" in str(exc) else 400
        raise HTTPException(
            status_code=status_code,
            detail={"error": "invalid_order", "message": str(exc)},
        )
    except Exception as exc:
        logger.error(f"执行模拟订单失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"执行模拟订单失败: {str(exc)}"},
        )


@router.get(
    "/positions/{account_id}",
    response_model=PositionsResponse,
    responses={
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取模拟持仓",
    description="返回账户当前持仓及 FIFO 批次明细",
)
def get_positions(
    account_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PositionsResponse:
    try:
        service = SimTradingService(db_manager)
        positions = service.get_positions(account_id)
        items = [PositionItem(**p) for p in positions]
        return PositionsResponse(account_id=account_id, positions=items)
    except Exception as exc:
        logger.error(f"查询模拟持仓失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询模拟持仓失败: {str(exc)}"},
        )

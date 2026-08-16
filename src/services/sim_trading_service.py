# -*- coding: utf-8 -*-
"""Simulated trading service with A-share-specific rules.

Implements an event-sourced paper-trading ledger on top of the existing
``Portfolio*`` storage models plus the new ``SimOrder`` / ``SimExecution``
tables.  A-share rules enforced for ``market == 'cn'``:

- Buy orders must be in 100-share lots (整手).
- Sells follow T+1: shares bought today cannot be sold until the next
  trading day.
- Fees on execution:
  * Stamp duty (印花税): 0.05% on sells only.
  * Commission (佣金): broker rate, minimum 5 CNY per trade.
  * Transfer fee (过户费): 0.001% of turnover (both sides).

The service intentionally avoids any network calls — callers must supply
the execution price and current market price themselves so the ledger
remains deterministic and offline-safe.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select

from src.storage import (
    DatabaseManager,
    PortfolioAccount,
    PortfolioPosition,
    PortfolioPositionLot,
    SimExecution,
    SimOrder,
)

logger = logging.getLogger(__name__)

# A-share fee schedule (configurable constants, not magic numbers inline).
A_SHARE_LOT_SIZE = 100
STAMP_DUTY_RATE = 0.0005  # 0.05%, sell only
DEFAULT_COMMISSION_RATE = 0.00025  # 0.025%
MIN_COMMISSION_CNY = 5.0
TRANSFER_FEE_RATE = 0.00001  # 0.001%, both sides
EPS = 1e-9


class SimTradingError(ValueError):
    """Raised when a simulated order violates trading rules."""


class SimTradingService:
    """Manages simulated orders, executions, and FIFO positions."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------
    def place_order(
        self,
        *,
        account_id: int,
        code: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "market",
    ) -> SimOrder:
        """Place a simulated order after A-share rule validation.

        Args:
            account_id: target portfolio account id.
            code: stock code (e.g. ``600519``).
            side: ``buy`` or ``sell``.
            quantity: number of shares.
            price: limit price (for limit orders) or quoted market price.
            order_type: ``market`` (default) or ``limit``.

        Returns:
            The persisted :class:`SimOrder` (status ``pending``).
        """
        side = (side or "").strip().lower()
        if side not in {"buy", "sell"}:
            raise SimTradingError(f"invalid side: {side!r} (expected buy/sell)")
        order_type = (order_type or "market").strip().lower()
        if order_type not in {"market", "limit"}:
            raise SimTradingError(f"invalid order_type: {order_type!r}")
        try:
            qty = float(quantity)
        except (TypeError, ValueError) as exc:
            raise SimTradingError(f"invalid quantity: {quantity!r}") from exc
        if qty <= 0:
            raise SimTradingError(f"quantity must be positive: {qty}")

        account = self._get_account(account_id)
        market = (account.market or "cn").lower()

        # A-share 100-share lot rule applies to buys.
        if market == "cn" and side == "buy":
            if abs(qty - round(qty / A_SHARE_LOT_SIZE) * A_SHARE_LOT_SIZE) > EPS:
                raise SimTradingError(
                    f"A-share buy must be a multiple of {A_SHARE_LOT_SIZE} shares, got {qty}"
                )

        if order_type == "limit" and price is None:
            raise SimTradingError("limit order requires a price")

        # T+1: sells need enough T-N (N>=1) lots. We validate at placement
        # time against the current position; the trade_date is decided at
        # execution time, so a final guard also runs in execute_order.
        if side == "sell":
            available = self._available_t1_quantity(
                account_id=account_id, code=code, as_of=date.today()
            )
            if qty > available + EPS:
                raise SimTradingError(
                    f"insufficient T+1 sellable quantity for {code}: "
                    f"requested={qty}, available={available}"
                )

        order = SimOrder(
            account_id=account_id,
            code=code,
            side=side,
            order_type=order_type,
            quantity=qty,
            price=float(price) if price is not None else None,
            status="pending",
        )
        with self.db.session_scope() as session:
            session.add(order)
            session.flush()
            session.refresh(order)
            session.expunge(order)
        logger.info(
            "[SimTrading] order placed: id=%s account=%s %s %s qty=%s price=%s",
            order.id, account_id, side, code, qty, price,
        )
        return order

    def execute_order(self, order_id: int, execution_price: float) -> SimExecution:
        """Execute and settle a pending order with A-share fees.

        Updates the order status to ``filled``, writes a :class:`SimExecution`
        row, and replays the FIFO lots / position snapshot.
        """
        try:
            exec_price = float(execution_price)
        except (TypeError, ValueError) as exc:
            raise SimTradingError(f"invalid execution_price: {execution_price!r}") from exc
        if exec_price <= 0:
            raise SimTradingError(f"execution_price must be positive: {exec_price}")

        with self.db.get_session() as session:
            order = session.get(SimOrder, order_id)
            if order is None:
                raise SimTradingError(f"order not found: {order_id}")
            if order.status != "pending":
                raise SimTradingError(
                    f"order {order_id} is not pending (status={order.status})"
                )
            account = session.get(PortfolioAccount, order.account_id)
            if account is None:
                raise SimTradingError(f"account not found: {order.account_id}")
            market = (account.market or "cn").lower()
            base_currency = account.base_currency or "CNY"
            # Snapshot fields we need after session close.
            order_snapshot = {
                "id": order.id,
                "account_id": order.account_id,
                "code": order.code,
                "side": order.side,
                "quantity": float(order.quantity),
                "order_type": order.order_type,
                "price": float(order.price) if order.price is not None else None,
            }

        trade_date = date.today()

        # T+1 final guard at execution time.
        if order_snapshot["side"] == "sell":
            available = self._available_t1_quantity(
                account_id=order_snapshot["account_id"],
                code=order_snapshot["code"],
                as_of=trade_date,
            )
            if order_snapshot["quantity"] > available + EPS:
                raise SimTradingError(
                    f"T+1 guard: insufficient sellable quantity for {order_snapshot['code']}: "
                    f"requested={order_snapshot['quantity']}, available={available}"
                )

        fees = self._compute_fees(
            side=order_snapshot["side"],
            quantity=order_snapshot["quantity"],
            price=exec_price,
            market=market,
        )
        turnover = exec_price * order_snapshot["quantity"]
        if order_snapshot["side"] == "buy":
            total_cost = turnover + fees["commission"] + fees["transfer_fee"]
        else:
            # Sells: net proceeds = turnover - stamp_duty - commission - transfer_fee.
            # total_cost stores the net cash impact (negative = inflow) so the
            # ledger uses a uniform "cost = cash outflow" convention.
            net_proceeds = turnover - fees["stamp_duty"] - fees["commission"] - fees["transfer_fee"]
            total_cost = -net_proceeds

        execution = SimExecution(
            order_id=order_snapshot["id"],
            account_id=order_snapshot["account_id"],
            code=order_snapshot["code"],
            side=order_snapshot["side"],
            quantity=order_snapshot["quantity"],
            execution_price=exec_price,
            commission=fees["commission"],
            stamp_duty=fees["stamp_duty"],
            transfer_fee=fees["transfer_fee"],
            total_cost=total_cost,
            trade_date=trade_date,
            executed_at=datetime.now(),
        )

        with self.db.session_scope() as session:
            # Re-fetch order for update inside the write transaction.
            order = session.get(SimOrder, order_snapshot["id"])
            order.status = "filled"
            session.add(execution)
            session.flush()
            session.refresh(execution)
            exec_id = execution.id
            # Detach a safe copy for the return value.
            exec_copy = SimExecution(
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
                trade_date=execution.trade_date,
                executed_at=execution.executed_at,
            )
            session.expunge(exec_copy)

        # Replay FIFO lots + position snapshot outside the order write txn.
        self._replay_position(
            account_id=order_snapshot["account_id"],
            code=order_snapshot["code"],
            market=market,
            currency=base_currency,
        )
        logger.info(
            "[SimTrading] order executed: id=%s exec_id=%s price=%s fees=%s",
            order_snapshot["id"], exec_id, exec_price, fees,
        )
        return exec_copy

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------
    def get_positions(self, account_id: int) -> List[Dict[str, Any]]:
        """Return current positions for an account with FIFO batch detail."""
        with self.db.get_session() as session:
            positions = session.execute(
                select(PortfolioPosition).where(
                    PortfolioPosition.account_id == account_id
                )
            ).scalars().all()
            result = []
            for pos in positions:
                lots = session.execute(
                    select(PortfolioPositionLot).where(
                        and_(
                            PortfolioPositionLot.account_id == account_id,
                            PortfolioPositionLot.symbol == pos.symbol,
                            PortfolioPositionLot.remaining_quantity > 0,
                        )
                    ).order_by(PortfolioPositionLot.open_date)
                ).scalars().all()
                result.append({
                    "code": pos.symbol,
                    "market": pos.market,
                    "currency": pos.currency,
                    "quantity": float(pos.quantity),
                    "avg_cost": float(pos.avg_cost),
                    "total_cost": float(pos.total_cost),
                    "last_price": float(pos.last_price),
                    "market_value": float(pos.market_value_base),
                    "unrealized_pnl": float(pos.unrealized_pnl_base),
                    "lots": [
                        {
                            "open_date": lot.open_date.isoformat() if lot.open_date else None,
                            "remaining_quantity": float(lot.remaining_quantity),
                            "unit_cost": float(lot.unit_cost),
                        }
                        for lot in lots
                    ],
                })
            return result

    def apply_stop_loss_take_profit(
        self,
        *,
        account_id: int,
        code: str,
        current_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> List[SimOrder]:
        """Auto-generate sell orders when SL/TP levels are hit.

        Returns the list of newly created sell orders (may be empty).
        """
        orders: List[SimOrder] = []
        try:
            price = float(current_price)
        except (TypeError, ValueError):
            return orders
        if price <= 0:
            return orders

        # Available (T+1) quantity drives how much we can auto-sell today.
        available = self._available_t1_quantity(
            account_id=account_id, code=code, as_of=date.today()
        )
        if available <= EPS:
            return orders

        # Take profit takes priority over stop loss when both trigger on the
        # same tick — locking in gains is preferred over cutting losses.
        triggered = False
        if take_profit is not None and price >= float(take_profit) - EPS:
            triggered = True
        elif stop_loss is not None and price <= float(stop_loss) + EPS:
            triggered = True

        if not triggered:
            return orders

        # Round down to the nearest A-share lot if the account is A-share.
        account = self._get_account(account_id)
        market = (account.market or "cn").lower()
        sell_qty = available
        if market == "cn":
            sell_qty = (int(available // A_SHARE_LOT_SIZE)) * A_SHARE_LOT_SIZE
        if sell_qty <= 0:
            return orders

        reason = "take_profit" if (take_profit is not None and price >= float(take_profit) - EPS) else "stop_loss"
        order = self.place_order(
            account_id=account_id,
            code=code,
            side="sell",
            quantity=sell_qty,
            price=price,
            order_type="market",
        )
        # Annotate the persisted order with the trigger reason.
        with self.db.session_scope() as session:
            persisted = session.get(SimOrder, order.id)
            if persisted is not None:
                persisted.notes = f"auto {reason} @ {price}"
        orders.append(order)
        logger.info(
            "[SimTrading] %s triggered for %s: qty=%s price=%s",
            reason, code, sell_qty, price,
        )
        return orders

    # ------------------------------------------------------------------
    # Fee calculation (A-share schedule)
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_fees(
        *,
        side: str,
        quantity: float,
        price: float,
        market: str,
    ) -> Dict[str, float]:
        """Return commission / stamp_duty / transfer_fee for one trade."""
        turnover = abs(price * quantity)
        commission = max(turnover * DEFAULT_COMMISSION_RATE, MIN_COMMISSION_CNY) if market == "cn" else turnover * DEFAULT_COMMISSION_RATE
        stamp_duty = turnover * STAMP_DUTY_RATE if side == "sell" and market == "cn" else 0.0
        transfer_fee = turnover * TRANSFER_FEE_RATE if market == "cn" else 0.0
        return {
            "commission": round(commission, 4),
            "stamp_duty": round(stamp_duty, 4),
            "transfer_fee": round(transfer_fee, 4),
        }

    # ------------------------------------------------------------------
    # T+1 available quantity
    # ------------------------------------------------------------------
    def _available_t1_quantity(
        self,
        *,
        account_id: int,
        code: str,
        as_of: date,
    ) -> float:
        """Return the quantity sellable today under T+1 (lots opened before as_of)."""
        with self.db.get_session() as session:
            lots = session.execute(
                select(PortfolioPositionLot).where(
                    and_(
                        PortfolioPositionLot.account_id == account_id,
                        PortfolioPositionLot.symbol == code,
                        PortfolioPositionLot.remaining_quantity > 0,
                    )
                ).order_by(PortfolioPositionLot.open_date)
            ).scalars().all()
            total = 0.0
            for lot in lots:
                if lot.open_date is None:
                    continue
                # T+1: only lots opened strictly before today are sellable.
                if lot.open_date < as_of:
                    total += float(lot.remaining_quantity)
            return total

    # ------------------------------------------------------------------
    # Position replay (FIFO)
    # ------------------------------------------------------------------
    def _replay_position(
        self,
        *,
        account_id: int,
        code: str,
        market: str,
        currency: str,
    ) -> None:
        """Rebuild the PortfolioPosition + lots for one symbol from executions."""
        with self.db.session_scope() as session:
            executions = session.execute(
                select(SimExecution).where(
                    and_(
                        SimExecution.account_id == account_id,
                        SimExecution.code == code,
                    )
                ).order_by(SimExecution.executed_at, SimExecution.id)
            ).scalars().all()

            # Rebuild FIFO lots from scratch (idempotent given the executions).
            session.execute(
                PortfolioPositionLot.__table__.delete().where(
                    and_(
                        PortfolioPositionLot.account_id == account_id,
                        PortfolioPositionLot.symbol == code,
                    )
                )
            )

            lots: List[Dict[str, Any]] = []
            for ex in executions:
                if ex.side == "buy":
                    unit_cost = (
                        (ex.execution_price * ex.quantity + ex.commission + ex.transfer_fee)
                        / ex.quantity
                        if ex.quantity > 0 else 0.0
                    )
                    lots.append({
                        "open_date": ex.trade_date,
                        "remaining_quantity": float(ex.quantity),
                        "unit_cost": unit_cost,
                        "source_trade_id": None,
                    })
                else:  # sell — consume FIFO
                    to_sell = float(ex.quantity)
                    for lot in lots:
                        if to_sell <= EPS:
                            break
                        consumed = min(lot["remaining_quantity"], to_sell)
                        lot["remaining_quantity"] -= consumed
                        to_sell -= consumed

            # Persist remaining lots.
            for lot in lots:
                if lot["remaining_quantity"] > EPS:
                    session.add(PortfolioPositionLot(
                        account_id=account_id,
                        cost_method="fifo",
                        symbol=code,
                        market=market,
                        currency=currency,
                        open_date=lot["open_date"],
                        remaining_quantity=lot["remaining_quantity"],
                        unit_cost=lot["unit_cost"],
                        source_trade_id=lot["source_trade_id"],
                    ))

            # Recompute the position snapshot.
            remaining_qty = sum(l["remaining_quantity"] for l in lots)
            total_cost = sum(
                l["remaining_quantity"] * l["unit_cost"] for l in lots
                if l["remaining_quantity"] > 0
            )
            avg_cost = (total_cost / remaining_qty) if remaining_qty > EPS else 0.0
            last_price = 0.0
            last_exec = executions[-1] if executions else None
            if last_exec is not None:
                last_price = float(last_exec.execution_price)

            # Upsert the position row.
            existing = session.execute(
                select(PortfolioPosition).where(
                    and_(
                        PortfolioPosition.account_id == account_id,
                        PortfolioPosition.symbol == code,
                        PortfolioPosition.cost_method == "fifo",
                    )
                )
            ).scalar_one_or_none()

            market_value = remaining_qty * last_price
            unrealized = market_value - total_cost

            if existing is None:
                if remaining_qty > EPS:
                    session.add(PortfolioPosition(
                        account_id=account_id,
                        cost_method="fifo",
                        symbol=code,
                        market=market,
                        currency=currency,
                        quantity=remaining_qty,
                        avg_cost=avg_cost,
                        total_cost=total_cost,
                        last_price=last_price,
                        market_value_base=market_value,
                        unrealized_pnl_base=unrealized,
                        valuation_currency=currency,
                    ))
            else:
                if remaining_qty <= EPS:
                    session.delete(existing)
                else:
                    existing.quantity = remaining_qty
                    existing.avg_cost = avg_cost
                    existing.total_cost = total_cost
                    existing.last_price = last_price
                    existing.market_value_base = market_value
                    existing.unrealized_pnl_base = unrealized
                    existing.valuation_currency = currency

    # ------------------------------------------------------------------
    # Account lookup
    # ------------------------------------------------------------------
    def _get_account(self, account_id: int) -> PortfolioAccount:
        with self.db.get_session() as session:
            account = session.get(PortfolioAccount, account_id)
            if account is None:
                raise SimTradingError(f"account not found: {account_id}")
            # Detach a lightweight copy so the session can close.
            detached = PortfolioAccount(
                id=account.id,
                owner_id=account.owner_id,
                name=account.name,
                broker=account.broker,
                market=account.market,
                base_currency=account.base_currency,
                is_active=account.is_active,
            )
            session.expunge(detached)
            return detached

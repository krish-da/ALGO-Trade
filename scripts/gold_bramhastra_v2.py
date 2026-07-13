#!/usr/bin/env python3
"""Causal multi-timeframe XAUUSD line research backtester.

Research software only. It does not place orders or imply future performance.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class Config:
    start_balance: float = 10_000.0
    risk_pct: float = 1.0
    leverage: float = 10.0
    max_notional: float = 50_000.0
    grid: float = 5.0
    tolerance: float = 1.25
    invalidation_buffer: float = 1.0
    stop_buffer: float = 0.30
    min_score: float = 2.0
    break_lookback: int = 3
    max_setup_bars: int = 8
    spread: float = 0.30
    slippage: float = 0.10
    commission_per_oz: float = 0.0
    train_fraction: float = 0.60


@dataclass
class Zone:
    id: str
    price: float
    created_at: pd.Timestamp
    source_timeframes: set[str] = field(default_factory=set)
    score: float = 0.0
    sides: set[str] = field(default_factory=set)
    touches: int = 0
    last_touch: Optional[pd.Timestamp] = None
    invalidated_at: Optional[pd.Timestamp] = None
    invalidation_reason: str = ""

    @property
    def active(self) -> bool:
        return self.invalidated_at is None


@dataclass
class Setup:
    zone_id: str
    kind: str
    direction: str
    started_at: pd.Timestamp
    expires_index: int
    spike: float
    stage: str


TIMEFRAMES = {"15m": ("15min", 3, 1.0), "1h": ("1h", 3, 1.7), "4h": ("4h", 2, 2.5)}


def load_candles(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, header=None, names=["time", "open", "high", "low", "close"])
    for col in ["time", "open", "high", "low", "close"]:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    if raw.isna().any().any():
        raise ValueError("Input contains missing or non-numeric OHLC values")
    raw["datetime"] = pd.to_datetime(raw["time"], unit="s", utc=True)
    raw = raw.sort_values("datetime").drop_duplicates("datetime", keep="last").set_index("datetime")
    valid = (raw.high >= raw[["open", "close"]].max(axis=1)) & (raw.low <= raw[["open", "close"]].min(axis=1)) & (raw.high >= raw.low)
    if not valid.all():
        raise ValueError(f"Input contains {(~valid).sum()} malformed candles")
    return raw[["open", "high", "low", "close"]].astype(float)


def resample_closed(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Timestamp bars by close time; only complete source intervals are retained."""
    bars = df.resample(rule, label="right", closed="left").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), count=("close", "count")
    ).dropna()
    expected = int(pd.Timedelta(rule) / pd.Timedelta("1min"))
    return bars[bars["count"] == expected].drop(columns="count")


def confirmed_swings(bars: pd.DataFrame, right: int, timeframe: str) -> list[dict]:
    """A pivot becomes observable only at i + right, never at pivot time."""
    found: list[dict] = []
    for i in range(right, len(bars) - right):
        window = bars.iloc[i - right : i + right + 1]
        pivot, confirmed = bars.index[i], bars.index[i + right]
        if bars.iloc[i].high >= window.high.max():
            found.append({"pivot_at": pivot, "confirmed_at": confirmed, "raw_price": bars.iloc[i].high, "side": "high", "timeframe": timeframe})
        if bars.iloc[i].low <= window.low.min():
            found.append({"pivot_at": pivot, "confirmed_at": confirmed, "raw_price": bars.iloc[i].low, "side": "low", "timeframe": timeframe})
    return found


def snap(price: float, grid: float) -> float:
    return round(price / grid) * grid


class ResearchBacktester:
    def __init__(self, config: Config):
        self.c = config
        self.zones: dict[str, Zone] = {}
        self.events: list[dict] = []
        self.trades: list[dict] = []
        self.balance = config.start_balance
        self.position: Optional[dict] = None
        self.setups: dict[tuple[str, str], Setup] = {}
        self.last_episode: dict[tuple[str, str], pd.Timestamp] = {}
        self._zone_counter = 0

    def build_candidates(self, one_minute: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
        bars15 = resample_closed(one_minute, "15min")
        candidates: list[dict] = []
        for name, (rule, right, weight) in TIMEFRAMES.items():
            bars = bars15 if name == "15m" else resample_closed(one_minute, rule)
            for item in confirmed_swings(bars, right, name):
                item["price"] = snap(item["raw_price"], self.c.grid)
                item["weight"] = weight
                candidates.append(item)
        candidates.sort(key=lambda x: x["confirmed_at"])
        return bars15, candidates

    def _add_candidate(self, candidate: dict) -> None:
        nearby = [z for z in self.zones.values() if z.active and abs(z.price - candidate["price"]) <= self.c.tolerance]
        if nearby:
            zone = min(nearby, key=lambda z: abs(z.price - candidate["price"]))
            new_tf = candidate["timeframe"] not in zone.source_timeframes
            zone.source_timeframes.add(candidate["timeframe"])
            zone.sides.add(candidate["side"])
            zone.score += candidate["weight"] + (0.5 if new_tf else 0.0)
            self.events.append(self._event(candidate["confirmed_at"], zone, "zone_updated", candidate["timeframe"]))
        else:
            self._zone_counter += 1
            zone = Zone(
                id=f"Z{self._zone_counter:04d}",
                price=candidate["price"],
                created_at=candidate["confirmed_at"],
                source_timeframes={candidate["timeframe"]},
                score=candidate["weight"],
                sides={candidate["side"]},
            )
            self.zones[zone.id] = zone
            self.events.append(self._event(candidate["confirmed_at"], zone, "zone_created", candidate["timeframe"]))

    @staticmethod
    def _event(at: pd.Timestamp, zone: Zone, event: str, detail: str = "") -> dict:
        return {"time": at.isoformat(), "zone_id": zone.id, "zone_price": zone.price, "event": event, "detail": detail}

    def _active_zones(self) -> list[Zone]:
        return sorted((z for z in self.zones.values() if z.active and z.score >= self.c.min_score), key=lambda z: z.price)

    def _next_target(self, entry: float, direction: str, excluded: str) -> Optional[float]:
        prices = [z.price for z in self._active_zones() if z.id != excluded]
        valid = [p for p in prices if p > entry + self.c.tolerance] if direction == "LONG" else [p for p in prices if p < entry - self.c.tolerance]
        return min(valid) if direction == "LONG" and valid else max(valid) if valid else None

    def _invalidate(self, i: int, bars: pd.DataFrame) -> None:
        if i == 0:
            return
        prev, bar = bars.iloc[i - 1], bars.iloc[i]
        for zone in self._active_zones():
            # Both confirming closes must occur after the line became observable.
            if bars.index[i - 1] < zone.created_at:
                continue
            above = "high" in zone.sides and "low" not in zone.sides and prev.close > zone.price + self.c.invalidation_buffer and bar.close > zone.price + self.c.invalidation_buffer
            below = "low" in zone.sides and "high" not in zone.sides and prev.close < zone.price - self.c.invalidation_buffer and bar.close < zone.price - self.c.invalidation_buffer
            if above or below:
                zone.invalidated_at = bars.index[i]
                zone.invalidation_reason = "two_closes_above" if above else "two_closes_below"
                self.events.append(self._event(bars.index[i], zone, "zone_invalidated", zone.invalidation_reason))

    def _detect_setups(self, i: int, bars: pd.DataFrame) -> None:
        if i < self.c.break_lookback + 1:
            return
        bar, prev = bars.iloc[i], bars.iloc[i - 1]
        at = bars.index[i]
        prior = bars.iloc[i - self.c.break_lookback : i]
        for zone in self._active_zones():
            touched = bar.low <= zone.price + self.c.tolerance and bar.high >= zone.price - self.c.tolerance
            if touched:
                zone.touches += 1
                zone.last_touch = at
                zone.score += 0.15
                self.events.append(self._event(at, zone, "touch"))
                if bar.close > zone.price and bar.low < zone.price and bar.close > bar.open:
                    self.setups[(zone.id, "reversal")] = Setup(zone.id, "reversal", "LONG", at, i + self.c.max_setup_bars, bar.low, "rejected")
                elif bar.close < zone.price and bar.high > zone.price and bar.close < bar.open:
                    self.setups[(zone.id, "reversal")] = Setup(zone.id, "reversal", "SHORT", at, i + self.c.max_setup_bars, bar.high, "rejected")
            if prev.close <= zone.price + self.c.tolerance and bar.close > zone.price + self.c.invalidation_buffer:
                self.setups[(zone.id, "continuation")] = Setup(zone.id, "continuation", "LONG", at, i + self.c.max_setup_bars, min(prev.low, bar.low), "broken")
            elif prev.close >= zone.price - self.c.tolerance and bar.close < zone.price - self.c.invalidation_buffer:
                self.setups[(zone.id, "continuation")] = Setup(zone.id, "continuation", "SHORT", at, i + self.c.max_setup_bars, max(prev.high, bar.high), "broken")

            for kind in ("reversal", "continuation"):
                setup = self.setups.get((zone.id, kind))
                if not setup or i > setup.expires_index or self.position:
                    continue
                direction = setup.direction
                if kind == "reversal":
                    structure = bar.close > prior.high.max() if direction == "LONG" else bar.close < prior.low.min()
                    confirmed = structure
                else:
                    retest = bar.low <= zone.price + self.c.tolerance and bar.close > zone.price if direction == "LONG" else bar.high >= zone.price - self.c.tolerance and bar.close < zone.price
                    confirmed = retest and at > setup.started_at
                if confirmed:
                    self._enter(at, float(bar.close), setup, zone)
                    del self.setups[(zone.id, kind)]
                    break

    def _enter(self, at: pd.Timestamp, raw_entry: float, setup: Setup, zone: Zone) -> None:
        side = 1 if setup.direction == "LONG" else -1
        entry = raw_entry + side * (self.c.spread / 2 + self.c.slippage)
        stop = setup.spike - self.c.stop_buffer if side == 1 else setup.spike + self.c.stop_buffer
        risk_distance = abs(entry - stop)
        target = self._next_target(entry, setup.direction, zone.id)
        if target is None or risk_distance <= 0 or (side == 1 and target <= entry) or (side == -1 and target >= entry):
            self.events.append(self._event(at, zone, "setup_skipped", "no_target_or_invalid_risk"))
            return
        qty = min(self.balance * self.c.risk_pct / 100 / risk_distance, self.balance * self.c.leverage / entry, self.c.max_notional / entry)
        if not math.isfinite(qty) or qty <= 0:
            return
        self.position = {"entry_time": at.isoformat(), "setup": setup.kind, "direction": setup.direction, "zone_id": zone.id, "zone_price": zone.price, "entry": entry, "initial_stop": stop, "stop": stop, "target": target, "qty": qty, "risk_usd": risk_distance * qty, "balance_before": self.balance}
        self.events.append(self._event(at, zone, "trade_entered", f"{setup.kind}:{setup.direction}"))

    def _manage(self, i: int, bars: pd.DataFrame) -> None:
        if not self.position:
            return
        p, bar, at = self.position, bars.iloc[i], bars.index[i]
        long = p["direction"] == "LONG"
        hit_stop = bar.low <= p["stop"] if long else bar.high >= p["stop"]
        hit_target = bar.high >= p["target"] if long else bar.low <= p["target"]
        if hit_stop:  # conservative ordering when both are touched
            self._close(at, p["stop"], "stop_or_ambiguous" if hit_target else "stop")
            return
        if hit_target:
            self._close(at, p["target"], "target")
            return
        right = 2
        if i >= right * 2:
            pivot = bars.iloc[i - right]
            window = bars.iloc[i - right * 2 : i + 1]
            if long and pivot.low <= window.low.min() and pivot.low > p["stop"]:
                p["stop"] = float(pivot.low - self.c.stop_buffer)
            elif not long and pivot.high >= window.high.max() and pivot.high < p["stop"]:
                p["stop"] = float(pivot.high + self.c.stop_buffer)

    def _close(self, at: pd.Timestamp, raw_exit: float, reason: str) -> None:
        p = self.position
        assert p is not None
        side = 1 if p["direction"] == "LONG" else -1
        exit_price = raw_exit - side * (self.c.spread / 2 + self.c.slippage)
        gross = side * (exit_price - p["entry"]) * p["qty"]
        commission = p["qty"] * self.c.commission_per_oz * 2
        pnl = gross - commission
        estimated_friction = p["qty"] * (self.c.spread + 2 * self.c.slippage) + commission
        baseline_pnl = pnl + estimated_friction
        self.balance += pnl
        p.update(exit_time=at.isoformat(), exit=exit_price, exit_reason=reason, pnl=pnl, baseline_no_cost_pnl=baseline_pnl, estimated_cost=estimated_friction, r_multiple=pnl / p["risk_usd"] if p["risk_usd"] else 0, balance_after=self.balance)
        self.trades.append(p)
        self.position = None

    def run(self, one_minute: pd.DataFrame) -> dict:
        bars, candidates = self.build_candidates(one_minute)
        cursor = 0
        for i, at in enumerate(bars.index):
            while cursor < len(candidates) and candidates[cursor]["confirmed_at"] <= at:
                self._add_candidate(candidates[cursor]); cursor += 1
            self._manage(i, bars)
            self._detect_setups(i, bars)
            self._invalidate(i, bars)
        if self.position:
            self._close(bars.index[-1], float(bars.iloc[-1].close), "end_of_data")
        return self.metrics(bars)

    def metrics(self, bars: pd.DataFrame) -> dict:
        pnls = [t["pnl"] for t in self.trades]
        wins, losses = [p for p in pnls if p > 0], [p for p in pnls if p <= 0]
        equity = [self.c.start_balance] + [t["balance_after"] for t in self.trades]
        peak, max_dd = equity[0], 0.0
        for value in equity:
            peak = max(peak, value); max_dd = max(max_dd, (peak - value) / peak if peak else 0)
        split = {}
        for kind in ("reversal", "continuation"):
            ts = [t for t in self.trades if t["setup"] == kind]
            split[kind] = {"trades": len(ts), "win_rate_pct": 100 * sum(t["pnl"] > 0 for t in ts) / len(ts) if ts else 0, "pnl": sum(t["pnl"] for t in ts)}
        boundary = bars.index[int((len(bars) - 1) * self.c.train_fraction)]
        period_split = {}
        for label, period_trades in {
            "calibration": [t for t in self.trades if pd.Timestamp(t["entry_time"]) < boundary],
            "out_of_sample": [t for t in self.trades if pd.Timestamp(t["entry_time"]) >= boundary],
        }.items():
            period_split[label] = {"trades": len(period_trades), "pnl": sum(t["pnl"] for t in period_trades), "win_rate_pct": 100 * sum(t["pnl"] > 0 for t in period_trades) / len(period_trades) if period_trades else 0}
        return {"research_warning": "Historical simulation is not a guarantee of future performance.", "start_balance": self.c.start_balance, "final_balance": self.balance, "return_pct": 100 * (self.balance / self.c.start_balance - 1), "baseline_no_cost_pnl": sum(t["baseline_no_cost_pnl"] for t in self.trades), "estimated_total_cost": sum(t["estimated_cost"] for t in self.trades), "trades": len(pnls), "wins": len(wins), "losses": len(losses), "win_rate_pct": 100 * len(wins) / len(pnls) if pnls else 0, "expectancy_usd": float(np.mean(pnls)) if pnls else 0, "profit_factor": sum(wins) / abs(sum(losses)) if losses and sum(losses) else None, "average_win": float(np.mean(wins)) if wins else 0, "average_loss": float(np.mean(losses)) if losses else 0, "max_drawdown_pct": 100 * max_dd, "active_zones_end": len(self._active_zones()), "setup_split": split, "evaluation_boundary": boundary.isoformat(), "period_split": period_split, "sample_warning": "Fewer than 30 trades; results are statistically weak." if len(pnls) < 30 else ""}

    def export(self, output: Path, metrics: dict) -> None:
        output.mkdir(parents=True, exist_ok=True)
        zone_rows = []
        for z in self.zones.values():
            row = asdict(z); row["source_timeframes"] = ";".join(sorted(z.source_timeframes)); row["sides"] = ";".join(sorted(z.sides)); row["created_at"] = z.created_at.isoformat(); row["last_touch"] = z.last_touch.isoformat() if z.last_touch else ""; row["invalidated_at"] = z.invalidated_at.isoformat() if z.invalidated_at else ""
            zone_rows.append(row)
        pd.DataFrame(zone_rows).to_csv(output / "zones.csv", index=False)
        pd.DataFrame(self.events).to_csv(output / "events.csv", index=False)
        pd.DataFrame(self.trades).to_csv(output / "trades.csv", index=False)
        (output / "summary.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")


def compare_annotations(path: Path, zones: list[Zone], tolerance: float) -> dict:
    if not path.exists():
        return {"annotations": 0, "matched": 0, "coverage_pct": 0}
    manual = pd.read_csv(path)
    if manual.empty:
        return {"annotations": 0, "matched": 0, "coverage_pct": 0}
    required = {"line_id", "created_at", "timeframe", "price", "side", "notes"}
    if not required.issubset(manual.columns):
        raise ValueError(f"Annotation CSV requires columns: {sorted(required)}")
    prices = [z.price for z in zones]
    distances = [min((abs(float(p) - z) for z in prices), default=float("inf")) for p in manual.price]
    matched = sum(d <= tolerance for d in distances)
    return {"annotations": len(manual), "matched": matched, "coverage_pct": 100 * matched / len(manual), "mean_distance": float(np.mean(distances)) if distances else None}


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=here / "cache_xauusd_spot_mt5_1m_30d.csv")
    p.add_argument("--annotations", type=Path, default=here / "manual_zones_template.csv")
    p.add_argument("--output", type=Path, default=here / "backtest_output")
    p.add_argument("--risk-pct", type=float, default=1.0)
    p.add_argument("--spread", type=float, default=0.30)
    p.add_argument("--slippage", type=float, default=0.10)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    config = Config(risk_pct=args.risk_pct, spread=args.spread, slippage=args.slippage)
    engine = ResearchBacktester(config)
    metrics = engine.run(load_candles(args.data))
    metrics["manual_zone_comparison"] = compare_annotations(args.annotations, list(engine.zones.values()), config.tolerance)
    engine.export(args.output, metrics)
    print(json.dumps(metrics, indent=2))
    print(f"Artifacts: {args.output.resolve()}")


if __name__ == "__main__":
    main()

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from gold_bramhastra_v2 import Config, ResearchBacktester, Setup, Zone, compare_annotations, confirmed_swings, resample_closed, snap


class BacktesterTests(unittest.TestCase):
    def minute_bars(self, periods=60):
        idx = pd.date_range("2026-01-01", periods=periods, freq="1min", tz="UTC")
        close = [100 + (i % 10) for i in range(periods)]
        return pd.DataFrame({"open": close, "high": [x + 1 for x in close], "low": [x - 1 for x in close], "close": close}, index=idx)

    def test_resampling_requires_complete_bars_and_uses_close_timestamp(self):
        bars = resample_closed(self.minute_bars(31), "15min")
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars.index[0], pd.Timestamp("2026-01-01 00:15:00", tz="UTC"))

    def test_swing_is_confirmed_after_right_bars(self):
        idx = pd.date_range("2026-01-01", periods=5, freq="15min", tz="UTC")
        bars = pd.DataFrame({"open": [1]*5, "high": [2, 3, 9, 3, 2], "low": [0, -1, -2, -1, 0], "close": [1]*5}, index=idx)
        swings = confirmed_swings(bars, 2, "15m")
        self.assertTrue(all(s["confirmed_at"] == idx[4] for s in swings))
        self.assertTrue(all(s["confirmed_at"] > s["pivot_at"] for s in swings))

    def test_grid_snap(self):
        self.assertEqual(snap(4063.1, 5), 4065)
        self.assertEqual(snap(4051.2, 5), 4050)

    def test_zone_invalidates_only_after_two_closes(self):
        engine = ResearchBacktester(Config(min_score=1))
        zone = Zone(id="Z1", price=100, created_at=pd.Timestamp("2026-01-01", tz="UTC"), source_timeframes={"15m"}, score=2, sides={"high"})
        engine.zones[zone.id] = zone
        idx = pd.date_range("2026-01-01", periods=3, freq="15min", tz="UTC")
        bars = pd.DataFrame({"open": [100]*3, "high": [102]*3, "low": [99]*3, "close": [100, 101.2, 101.3]}, index=idx)
        engine._invalidate(1, bars)
        self.assertTrue(zone.active)
        engine._invalidate(2, bars)
        self.assertFalse(zone.active)

    def test_ambiguous_candle_uses_stop_first(self):
        engine = ResearchBacktester(Config())
        engine.position = {"entry_time": "x", "setup": "reversal", "direction": "LONG", "zone_id": "Z1", "zone_price": 100, "entry": 101, "initial_stop": 99, "stop": 99, "target": 105, "qty": 1, "risk_usd": 2, "balance_before": 10000}
        idx = pd.DatetimeIndex([pd.Timestamp("2026-01-01", tz="UTC")])
        bars = pd.DataFrame({"open": [101], "high": [106], "low": [98], "close": [102]}, index=idx)
        engine._manage(0, bars)
        self.assertEqual(engine.trades[0]["exit_reason"], "stop_or_ambiguous")

    def test_annotation_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "zones.csv"
            path.write_text("line_id,created_at,timeframe,price,side,notes\n", encoding="utf-8")
            self.assertEqual(compare_annotations(path, [], 1)["annotations"], 0)


if __name__ == "__main__":
    unittest.main()

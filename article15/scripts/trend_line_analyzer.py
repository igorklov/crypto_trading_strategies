#!/usr/bin/env python3
"""
Trend Line Analyzer for crypto trading.
Article 15 — LLM-агенты для криптотрейдинга.

Usage:
    from trend_line_analyzer import TrendLineAnalyzer

    analyzer = TrendLineAnalyzer(symbol, interval, config)
    result = analyzer.analyze(df)
    print(result['breakouts'])
    print(result['current_trend'])
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone


class TrendLineAnalyzer:
    """
    Анализатор трендовых линий.
    Находит swing-точки, строит линии, детектит пробои.

    Параметры (config):
        swing_window (int): окно поиска экстремумов (5)
        min_touches (int): мин. касаний для валидной линии (3)
        max_gap_pct (float): допуск касания линии в %% (0.03)
        atr_period (int): период ATR (14)
        breakout_threshold_atr (float): порог пробоя в ATR (0.5)
    """

    def __init__(self, symbol, interval, config=None):
        self.symbol = symbol
        self.interval = interval
        config = config or {}
        self.swing_window = config.get('swing_window', 5)
        self.min_touches = config.get('min_touches', 3)
        self.max_gap_pct = config.get('max_gap_pct', 0.03)
        self.atr_period = config.get('atr_period', 14)
        self.breakout_threshold_atr = config.get('breakout_threshold_atr', 0.5)

    def analyze(self, df):
        """
        Полный анализ трендовых линий на данных DataFrame.
        df: колонки timestamp, open, high, low, close, volume.
        """
        if df is None or len(df) < 30:
            return None

        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        volumes = df['volume'].values
        timestamps = df['timestamp'].values

        swing_highs_idx, swing_lows_idx = self._find_swing_points(
            highs, lows, self.swing_window
        )

        uptrend_lines = self._build_trend_lines(
            timestamps, lows, swing_lows_idx, is_uptrend=True
        )
        downtrend_lines = self._build_trend_lines(
            timestamps, highs, swing_highs_idx, is_uptrend=False
        )

        all_lines = uptrend_lines + downtrend_lines
        breakouts = self._detect_breakouts(
            closes, timestamps, volumes, highs, lows, all_lines
        )

        valid_signals = []
        for breakout in breakouts:
            atr = self._calculate_atr(highs, lows, closes)
            validation = self._validate_breakout(breakout, closes, volumes, atr)
            if validation['is_valid']:
                valid_signals.append({
                    **breakout,
                    'confidence': validation['confidence'],
                    'reasons': validation['reasons'],
                    'norm_momentum': validation['norm_momentum']
                })

        return {
            'symbol': self.symbol,
            'interval': self.interval,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'swing_highs': [(int(timestamps[i]), float(highs[i])) for i in swing_highs_idx],
            'swing_lows': [(int(timestamps[i]), float(lows[i])) for i in swing_lows_idx],
            'uptrend_lines': uptrend_lines,
            'downtrend_lines': downtrend_lines,
            'breakouts': valid_signals,
            'current_trend': self._determine_current_trend(
                closes[-1], uptrend_lines, downtrend_lines
            )
        }

    # ---- private methods ----

    def _find_swing_points(self, highs, lows, window):
        """Поиск значимых максимумов и минимумов."""
        length = len(highs)
        swing_highs = []
        swing_lows = []
        for i in range(window, length - window):
            if highs[i] == max(highs[i - window:i + window + 1]):
                swing_highs.append(i)
            if lows[i] == min(lows[i - window:i + window + 1]):
                swing_lows.append(i)
        return swing_highs, swing_lows

    def _build_trend_lines(self, timestamps, prices, swing_indices, is_uptrend):
        """Строит валидные трендовые линии."""
        lines = []
        points = [(timestamps[i], prices[i]) for i in swing_indices]
        if len(points) < 2:
            return lines

        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                t1, p1 = points[i]
                t2, p2 = points[j]
                if t2 == t1:
                    continue

                slope = (p2 - p1) / (t2 - t1)
                if (is_uptrend and slope <= 0) or (not is_uptrend and slope >= 0):
                    continue

                intercept = p1 - slope * t1
                touches = 0
                for t, p in points:
                    expected = slope * t + intercept
                    if abs(p - expected) / expected <= self.max_gap_pct:
                        touches += 1

                if touches >= self.min_touches:
                    lines.append({
                        'slope': slope,
                        'intercept': intercept,
                        'touches': touches,
                        'strength': touches / max(len(points), 1),
                        'is_uptrend': is_uptrend
                    })

        lines.sort(key=lambda x: x['touches'], reverse=True)
        return lines[:3]

    def _detect_breakouts(self, closes, timestamps, volumes, highs, lows, lines):
        """Детектит пробои на последней свече."""
        breakouts = []
        if len(closes) < 2:
            return breakouts

        current_price = closes[-1]
        prev_price = closes[-2]
        current_time = timestamps[-1]
        current_high = highs[-1]
        current_low = lows[-1]

        for line in lines:
            expected_price = line['slope'] * current_time + line['intercept']
            prev_expected = line['slope'] * timestamps[-2] + line['intercept']

            if line['is_uptrend']:
                if prev_price >= prev_expected and current_low < expected_price:
                    breakouts.append({
                        'type': 'bearish_breakout',
                        'line_type': 'uptrend',
                        'momentum': abs(current_price - expected_price) / expected_price,
                        'strength': line['strength']
                    })
            else:
                if prev_price <= prev_expected and current_high > expected_price:
                    breakouts.append({
                        'type': 'bullish_breakout',
                        'line_type': 'downtrend',
                        'momentum': abs(current_price - expected_price) / expected_price,
                        'strength': line['strength']
                    })

        return breakouts

    def _calculate_atr(self, highs, lows, closes, period=None):
        """Расчёт Average True Range."""
        period = period or self.atr_period
        if len(closes) < period + 1:
            return 0.0
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                abs(highs[1:] - closes[:-1]),
                abs(lows[1:] - closes[:-1])
            )
        )
        return float(np.mean(tr[-period:]))

    def _validate_breakout(self, breakout, closes, volumes, atr):
        """Фильтрация ложных пробоев."""
        reasons = []
        current_price = closes[-1]

        if atr > 0 and breakout['momentum'] * current_price > atr * self.breakout_threshold_atr:
            reasons.append('momentum_atr')

        avg_volume = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
        if avg_volume > 0 and volumes[-1] > avg_volume * 1.5:
            reasons.append('high_volume')

        if breakout['strength'] > 0.6:
            reasons.append('strong_line')

        norm_momentum = (breakout['momentum'] * current_price / atr) if atr > 0 else 0
        if norm_momentum > 1.0:
            reasons.append('strong_momentum')

        return {
            'is_valid': len(reasons) >= 2,
            'confidence': len(reasons) / 5.0,
            'reasons': reasons,
            'norm_momentum': norm_momentum
        }

    def _determine_current_trend(self, current_price, uptrend_lines, downtrend_lines):
        """Определяет текущий тренд."""
        if not uptrend_lines and not downtrend_lines:
            return 'undefined'

        scores = {'uptrend': 0, 'downtrend': 0, 'ranging': 0}
        for line in uptrend_lines:
            expected = line['slope'] * 0 + line['intercept']
            if current_price > expected:
                scores['uptrend'] += line['strength']
        for line in downtrend_lines:
            expected = line['slope'] * 0 + line['intercept']
            if current_price < expected:
                scores['downtrend'] += line['strength']

        best = max(scores, key=scores.get)
        return best if scores[best] > 0.5 else 'ranging'


# ---- CLI entry point ----
if __name__ == '__main__':
    import sys
    import json

    symbol = sys.argv[1] if len(sys.argv) > 1 else 'BTCUSDT'
    interval = sys.argv[2] if len(sys.argv) > 2 else '1h'

    # Example: generate mock data for testing
    print(f"Fetching data for {symbol} ({interval})...")

    # In production, replace with BinanceConnector or your data source
    from src.binance_connector import BinanceConnector  # noqa: F402
    connector = BinanceConnector()
    df = connector.get_klines(symbol, interval, limit=200)

    analyzer = TrendLineAnalyzer(symbol, interval, {
        'swing_window': 5,
        'min_touches': 3,
        'max_gap_pct': 0.03,
        'breakout_threshold_atr': 0.5
    })

    result = analyzer.analyze(df)

    print(f"\n{'='*60}")
    print(f"📊 Trend Lines Analysis — {symbol} ({interval})")
    print(f"{'='*60}")
    print(f"\n📍 Swing points: {len(result['swing_highs'])} highs, {len(result['swing_lows'])} lows")
    print(f"📈 Uptrend lines: {len(result['uptrend_lines'])}")
    print(f"📉 Downtrend lines: {len(result['downtrend_lines'])}")
    print(f"📊 Current trend: {result['current_trend']}")

    if result['breakouts']:
        print(f"\n🚨 BREAKOUT SIGNALS:")
        for b in result['breakouts']:
            icon = '🟢' if 'bullish' in b['type'] else '🔴'
            print(f"   {icon} {b['type']} — conf: {b['confidence']:.0%}, reasons: {', '.join(b['reasons'])}")
    else:
        print(f"\n✅ No valid breakouts detected")

    # Save to file for logging
    out_path = f"trend_line_{symbol}_{interval}.json"
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n💾 Full result saved to {out_path}")

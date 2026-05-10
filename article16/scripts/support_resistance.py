#!/usr/bin/env python3
"""
Support/Resistance Detector — объединение горизонтальных S/R,
трендовых линий и уровней Фибоначчи в единую систему.

Использование:
    python3 support_resistance.py --symbol ETHUSDT --interval 1h --days 7

Статья 16: https://github.com/igorklov/crypto_trading_strategies
"""

import argparse
import json
import numpy as np
import pandas as pd


class SupportResistanceDetector:
    """
    Единый детектор уровней поддержки/сопротивления.
    Объединяет горизонтальные уровни, трендовые линии и Фибоначчи.
    """

    def __init__(self, config=None):
        self.config = config or {
            'swing_window': 5,
            'cluster_distance': 0.02,
            'fib_levels': [0.382, 0.5, 0.618, 0.786, 1.0],
            'min_touches_sr': 2,
            'atr_multiplier': 0.5,
        }
        self.levels = []

    # ── 1. Поиск swing-точек ──────────────────────────────────

    def _find_swing_points(self, highs, lows, window=5):
        length = len(highs)
        swing_highs, swing_lows = [], []
        for i in range(window, length - window):
            if highs[i] == max(highs[i - window:i + window + 1]):
                swing_highs.append((i, highs[i]))
            if lows[i] == min(lows[i - window:i + window + 1]):
                swing_lows.append((i, lows[i]))
        return swing_highs, swing_lows

    # ── 2. Группировка близких уровней ───────────────────────

    def _cluster_levels(self, points, max_dist_pct):
        if not points:
            return []
        sorted_pts = sorted(points, key=lambda x: x[1])
        clusters = [[sorted_pts[0]]]
        for pt in sorted_pts[1:]:
            if abs(pt[1] / clusters[-1][0][1] - 1) < max_dist_pct:
                clusters[-1].append(pt)
            else:
                clusters.append([pt])
        result = []
        for c in clusters:
            avg_price = np.mean([p[1] for p in c])
            touches = len(set(p[0] for p in c))
            result.append({'price': avg_price, 'touches': touches,
                           'type': 'horizontal'})
        return result

    # ── 3. Горизонтальные S/R ────────────────────────────────

    def _detect_horizontal(self, swing_highs, swing_lows, price):
        supports = self._cluster_levels(swing_lows,
                                        self.config['cluster_distance'])
        resistances = self._cluster_levels(swing_highs,
                                           self.config['cluster_distance'])
        near_support = [s for s in supports
                        if s['price'] < price * 1.05]
        near_resistance = [r for r in resistances
                           if r['price'] > price * 0.95]
        return near_support, near_resistance

    # ── 4. Трендовые линии ───────────────────────────────────

    def _detect_trend_lines(self, highs, lows, timestamps):
        swing_highs, swing_lows = self._find_swing_points(
            highs, lows, self.config['swing_window'])
        lines = {'uptrend': [], 'downtrend': []}

        for i in range(1, len(swing_lows)):
            x1, y1 = swing_lows[i - 1]
            x2, y2 = swing_lows[i]
            if y1 < y2:
                slope = (y2 - y1) / (x2 - x1)
                intercept = y1 - slope * x1
                touches = sum(1 for j in range(len(lows))
                              if abs(lows[j] - (slope * j + intercept))
                                 / lows[j] < 0.03)
                lines['uptrend'].append({
                    'slope': slope, 'intercept': intercept,
                    'touches': touches
                })

        for i in range(1, len(swing_highs)):
            x1, y1 = swing_highs[i - 1]
            x2, y2 = swing_highs[i]
            if y1 > y2:
                slope = (y2 - y1) / (x2 - x1)
                intercept = y1 - slope * x1
                touches = sum(1 for j in range(len(highs))
                              if abs(highs[j] - (slope * j + intercept))
                                 / highs[j] < 0.03)
                lines['downtrend'].append({
                    'slope': slope, 'intercept': intercept,
                    'touches': touches
                })

        result = {'support': None, 'resistance': None}
        if lines['uptrend']:
            result['support'] = lines['uptrend'][-1]
        if lines['downtrend']:
            result['resistance'] = lines['downtrend'][-1]
        return result

    # ── 5. Уровни Фибоначчи ──────────────────────────────────

    def _detect_fibonacci(self, swing_highs, swing_lows, price):
        if not swing_highs or not swing_lows:
            return []
        latest_high = max(swing_highs, key=lambda x: x[0])
        latest_low = max(swing_lows, key=lambda x: x[0])
        if latest_high[0] > latest_low[0]:
            low, high = latest_low[1], latest_high[1]
        else:
            low, high = latest_low[1], latest_high[1]
        diff = high - low
        levels = []
        for ratio in self.config['fib_levels']:
            level_price = high - diff * ratio
            levels.append({
                'price': level_price,
                'ratio': ratio,
                'type': 'fibonacci',
                'strength': 'strong' if ratio in [0.618, 0.786] else 'normal'
            })
        return levels

    # ── 6. Ранжирование уровней ──────────────────────────────

    def _rank_levels(self, all_levels, price, atr):
        ranked = []
        for level in all_levels:
            score = 0
            dist = abs(level['price'] - price) / price
            if dist < 0.01:
                score += 40
            elif dist < 0.02:
                score += 30
            elif dist < 0.05:
                score += 20
            elif dist < 0.1:
                score += 10
            touches = level.get('touches', 1)
            score += min(touches * 10, 30)
            if level['type'] == 'fibonacci':
                score += 30 if level.get('ratio') in [0.618, 0.786] else 15
            elif level['type'] == 'dynamic':
                score += 25
            elif level['type'] == 'horizontal':
                score += 20
            ranked.append({**level, 'score': score})
        return sorted(ranked, key=lambda x: x['score'], reverse=True)

    # ── 7. Главный метод ─────────────────────────────────────

    def analyze(self, df):
        price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]

        swing_highs, swing_lows = self._find_swing_points(
            df['high'].values, df['low'].values,
            self.config['swing_window']
        )
        all_levels = []

        # 1) Горизонтальные
        supports, resistances = self._detect_horizontal(
            swing_highs, swing_lows, price)
        for s in supports:
            s['side'] = 'support'
            all_levels.append(s)
        for r in resistances:
            r['side'] = 'resistance'
            all_levels.append(r)

        # 2) Трендовые линии
        trend_lines = self._detect_trend_lines(
            df['high'].values, df['low'].values, df.index.values)
        if trend_lines['support']:
            sl = trend_lines['support']
            dynamic_support = sl['slope'] * len(df) + sl['intercept']
            all_levels.append({
                'price': dynamic_support,
                'type': 'dynamic',
                'side': 'support',
                'touches': sl['touches'],
            })
        if trend_lines['resistance']:
            sl = trend_lines['resistance']
            dynamic_resistance = sl['slope'] * len(df) + sl['intercept']
            all_levels.append({
                'price': dynamic_resistance,
                'type': 'dynamic',
                'side': 'resistance',
                'touches': sl['touches'],
            })

        # 3) Фибоначчи
        fib_levels = self._detect_fibonacci(swing_highs, swing_lows, price)
        for fl in fib_levels:
            fl['side'] = 'support' if fl['price'] < price else 'resistance'
            all_levels.append(fl)

        ranked = self._rank_levels(all_levels, price, atr)
        nearest_support = next((l for l in ranked
                                if l['side'] == 'support'), None)
        nearest_resistance = next((l for l in ranked
                                   if l['side'] == 'resistance'), None)

        return {
            'price': price,
            'atr': atr,
            'all_levels': ranked,
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'top_levels': ranked[:10],
        }


def fetch_binance_data(symbol, interval, days):
    """Загрузка данных с Binance через python-binance."""
    from binance.client import Client as BinanceClient
    from binance.exceptions import BinanceAPIException
    import os

    api_key = os.getenv('BINANCE_API_KEY', '')
    api_secret = os.getenv('BINANCE_API_SECRET', '')
    client = BinanceClient(api_key, api_secret)

    interval_map = {
        '1m': client.KLINE_INTERVAL_1MINUTE,
        '5m': client.KLINE_INTERVAL_5MINUTE,
        '15m': client.KLINE_INTERVAL_15MINUTE,
        '1h': client.KLINE_INTERVAL_1HOUR,
        '4h': client.KLINE_INTERVAL_4HOUR,
        '1d': client.KLINE_INTERVAL_1DAY,
    }
    kline_interval = interval_map.get(interval, client.KLINE_INTERVAL_1HOUR)

    klines = client.get_klines(
        symbol=symbol,
        interval=kline_interval,
        limit=days * 24  # приблизительно
    )
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_vol', 'trades', 'taker_buy_vol',
        'taker_buy_quote_vol', 'ignore'
    ])
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df


def main():
    parser = argparse.ArgumentParser(
        description='S/R Detector — объединённая система поддержки/сопротивления')
    parser.add_argument('--symbol', default='ETHUSDT',
                        help='Торговая пара (по умолчанию ETHUSDT)')
    parser.add_argument('--interval', default='1h',
                        choices=['1m', '5m', '15m', '1h', '4h', '1d'],
                        help='Таймфрейм (по умолчанию 1h)')
    parser.add_argument('--days', type=int, default=7,
                        help='Глубина истории в днях (по умолчанию 7)')
    parser.add_argument('--json', action='store_true',
                        help='Вывод в JSON')
    args = parser.parse_args()

    print(f"📥 Загрузка {args.symbol} ({args.interval}, {args.days} дней)...")
    df = fetch_binance_data(args.symbol, args.interval, args.days)
    print(f"   Получено {len(df)} свечей")

    detector = SupportResistanceDetector()
    result = detector.analyze(df)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return

    print(f"\n📊 Результаты S/R анализа — {args.symbol}")
    print(f"   Цена: ${result['price']:.2f}")
    print(f"   ATR(14): ${result['atr']:.2f}")
    print()

    if result['nearest_support']:
        ns = result['nearest_support']
        print(f"🟢 Ближайшая поддержка: ${ns['price']:.2f} "
              f"(type={ns['type']}, touches={ns.get('touches',1)}, "
              f"score={ns['score']})")
    if result['nearest_resistance']:
        nr = result['nearest_resistance']
        print(f"🔴 Ближайшее сопротивление: ${nr['price']:.2f} "
              f"(type={nr['type']}, touches={nr.get('touches',1)}, "
              f"score={nr['score']})")

    print(f"\n📋 Топ-10 уровней:")
    print(f"   {'Type':>10s} | {'Side':>9s} | {'Price':>10s} | Score")
    print(f"   {'-'*10}-+-{'-'*9}-+-{'-'*10}-+-------")
    for lv in result['top_levels']:
        print(f"   {lv['type']:>10s} | {lv['side']:>9s} | "
              f"${lv['price']:>8.2f} | {lv['score']}")


if __name__ == '__main__':
    main()

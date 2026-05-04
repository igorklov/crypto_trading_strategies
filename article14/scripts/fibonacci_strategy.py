#!/usr/bin/env python3
"""
Fibonacci Strategy для фьючерсной торговли
Версия: 1.0
Стратегия: вход от уровней Фибоначчи 0.618/0.786 с подтверждением RSI и объёма

Использование:
    python3 fibonacci_strategy.py --symbol ETHUSDT --interval 4h --leverage 3
    python3 fibonacci_strategy.py --symbol BTCUSDT --interval 1h --leverage 2 --no-volume
    python3 fibonacci_strategy.py --symbol SOLUSDT --interval 4h --save results.json
"""

import os
import sys
import json
import time
import argparse
import logging
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
import requests

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('fibonacci_strategy.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BinanceFuturesClient:
    """Клиент для получения данных с Binance Futures"""
    
    BASE_URL = 'https://fapi.binance.com'
    
    def __init__(self, symbol='ETHUSDT'):
        self.symbol = symbol
    
    def get_klines(self, interval='1h', limit=500):
        """Получает исторические свечи"""
        url = f'{self.BASE_URL}/fapi/v1/klines'
        params = {
            'symbol': self.symbol,
            'interval': interval,
            'limit': limit
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'count',
                'taker_buy_vol', 'taker_buy_quote', 'ignore'
            ])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        except Exception as e:
            logger.error(f'Ошибка получения данных: {e}')
            return None


class FibonacciStrategy:
    """
    Торговая стратегия на уровнях Фибоначчи
    """
    
    FIB_RETRACEMENT = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 0.886, 1.0]
    FIB_EXTENSION = [1.272, 1.618, 2.0, 2.618]
    
    def __init__(
        self,
        symbol='ETHUSDT',
        leverage=3,
        interval='1h',
        swing_window=5,
        confirmation_rsi=True,
        volume_filter=True,
        entry_levels=(0.618, 0.786),
    ):
        self.symbol = symbol
        self.leverage = leverage
        self.interval = interval
        self.swing_window = swing_window
        self.confirmation_rsi = confirmation_rsi
        self.volume_filter = volume_filter
        self.entry_levels = entry_levels
        
        self.client = BinanceFuturesClient(symbol)
        self.trades = []
        self.position = None
    
    def add_indicators(self, df):
        """Добавляет RSI, Volume SMA, ATR"""
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Volume SMA и Ratio
        df['volume_sma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        df['tr'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = df['tr'].rolling(14).mean()
        
        return df
    
    def find_swing_points(self, df):
        """Находит swing high и swing low"""
        window = self.swing_window
        df['swing_high'] = False
        df['swing_low'] = False
        
        for i in range(window, len(df) - window):
            if df['high'].iloc[i] == df['high'].iloc[i-window:i+window+1].max():
                df.loc[df.index[i], 'swing_high'] = True
            if df['low'].iloc[i] == df['low'].iloc[i-window:i+window+1].min():
                df.loc[df.index[i], 'swing_low'] = True
        
        return df
    
    def build_fibonacci_levels(self, high, low, is_uptrend):
        """Строит уровни Фибоначчи между high и low
        
        Нумерация уровней (retracement):
        - Для uptrend: 0.0 = high (0% retracement), 0.618 = high - 0.618*diff (61.8% вниз), 1.0 = low
        - Для downtrend: 0.0 = low (0% retracement), 0.618 = low + 0.618*diff (61.8% вверх), 1.0 = high
        
        Extension:
        - Для uptrend: 1.272/1.618 = выше high
        - Для downtrend: 1.272/1.618 = ниже low
        """
        diff = abs(high - low)
        levels = {}
        
        if is_uptrend:
            # Retracement от high вниз к low
            for ratio in self.FIB_RETRACEMENT:
                levels[ratio] = high - diff * ratio
            # Extension от high вверх
            for ratio in self.FIB_EXTENSION:
                levels[ratio] = high + diff * (ratio - 1.0)
        else:
            # Retracement от low вверх к high
            for ratio in self.FIB_RETRACEMENT:
                levels[ratio] = low + diff * ratio
            # Extension от low вниз
            for ratio in self.FIB_EXTENSION:
                levels[ratio] = low - diff * (ratio - 1.0)
        
        return levels
    
    def check_entry(self, row, prev_row, fib_levels, trend):
        """Проверяет условия входа по уровням Фибоначчи"""
        if trend == 'uptrend':
            for level_key in self.entry_levels:
                if level_key not in fib_levels:
                    continue
                level_price = fib_levels[level_key]
                
                # Цена crossed уровень сверху вниз (цена упала к уровню, пересекла его)
                if prev_row['high'] >= level_price >= row['low']:
                    if not self._confirm_signal(row, prev_row, 'buy'):
                        continue
                    
                    entry_price = level_price
                    # Стоп: уровень глубже (ближе к low) — 0.886 = 88.6% retracement от high
                    stop_loss = fib_levels.get(0.886, fib_levels.get(1.0, level_price * 0.97))
                    # Тейк: уровень выше (ближе к high) — 0.236 или 0.382
                    take_profit = fib_levels.get(self._get_tp_level(trend), level_price * 1.02)
                    
                    return 'buy', entry_price, stop_loss, take_profit, level_key
        
        elif trend == 'downtrend':
            for level_key in self.entry_levels:
                if level_key not in fib_levels:
                    continue
                level_price = fib_levels[level_key]
                
                # Цена crossed уровень снизу вверх (цена поднялась к уровню)
                if prev_row['low'] <= level_price <= row['high']:
                    if not self._confirm_signal(row, prev_row, 'sell'):
                        continue
                    
                    entry_price = level_price
                    # Стоп: 0.886 = 88.6% retracement — выше входа (цена пошла против шорта)
                    stop_loss = fib_levels.get(0.886, fib_levels.get(1.0, level_price * 1.03))
                    # Тейк: 0.236 = 23.6% retracement — ниже входа (цель)
                    take_profit = fib_levels.get(0.236, level_price * 0.98)
                    
                    return 'sell', entry_price, stop_loss, take_profit, level_key
        
        return None, None, None, None, None
    
    def _get_tp_level(self, trend):
        """Возвращает целевой уровень Фибоначчи для тейка"""
        if trend == 'uptrend':
            return 0.236  # 23.6% retracement от high (ближе к вершине)
        return 0.236  # 23.6% retracement от low (ближе к дну)
    
    def _confirm_signal(self, row, prev_row, side):
        """Подтверждает сигнал индикаторами"""
        if self.confirmation_rsi:
            rsi_val = row.get('rsi', 50)
            if side == 'buy' and not (40 < rsi_val < 75):
                return False
            if side == 'sell' and not (25 < rsi_val < 60):
                return False
        
        if self.volume_filter:
            vol_ratio = row.get('volume_ratio', 1.0)
            if vol_ratio < 0.8:
                return False
        
        return True
    
    def run_backtest(self, df):
        """Запускает бектест на исторических данных"""
        logger.info(f'Запуск бектеста {self.symbol} ({len(df)} свечей)')
        
        df = self.add_indicators(df)
        df = self.find_swing_points(df)
        
        # Определяем тренд через SMA
        df['sma50'] = df['close'].rolling(50).mean()
        df['sma200'] = df['close'].rolling(200).mean()
        
        trades = []
        last_swing_high = None
        last_swing_low = None
        last_fib_high = None
        last_fib_low = None
        
        for i in range(200, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            # Обновляем swing high/low
            if row['swing_high']:
                last_swing_high = row['high']
            if row['swing_low']:
                last_swing_low = row['low']
            
            # Определяем тренд
            if row['sma50'] > row['sma200']:
                trend = 'uptrend'
            elif row['sma50'] < row['sma200']:
                trend = 'downtrend'
            else:
                continue
            
            # Строим уровни Фибоначчи
            fib_levels = None
            if trend == 'uptrend' and last_swing_high and last_swing_low:
                if last_swing_high != last_fib_high or last_swing_low != last_fib_low:
                    fib_levels = self.build_fibonacci_levels(
                        last_swing_high, last_swing_low, is_uptrend=True
                    )
                    last_fib_high = last_swing_high
                    last_fib_low = last_swing_low
                else:
                    fib_levels = self.build_fibonacci_levels(
                        last_swing_high, last_swing_low, is_uptrend=True
                    )
            elif trend == 'downtrend' and last_swing_high and last_swing_low:
                if last_swing_high != last_fib_high or last_swing_low != last_fib_low:
                    fib_levels = self.build_fibonacci_levels(
                        last_swing_high, last_swing_low, is_uptrend=False
                    )
                    last_fib_high = last_swing_high
                    last_fib_low = last_swing_low
                else:
                    fib_levels = self.build_fibonacci_levels(
                        last_swing_high, last_swing_low, is_uptrend=False
                    )
            
            if not fib_levels:
                continue
            
            # Проверяем вход
            signal, entry, sl, tp, level = self.check_entry(
                row, prev_row, fib_levels, trend
            )
            
            if signal:
                trade = {
                    'timestamp': row['timestamp'],
                    'signal': signal,
                    'entry_price': round(entry, 2),
                    'stop_loss': round(sl, 2),
                    'take_profit': round(tp, 2),
                    'fib_level': level,
                    'rsi': round(row.get('rsi', 0), 1),
                    'volume_ratio': round(row.get('volume_ratio', 0), 2),
                    'trend': trend,
                    'atr': round(row.get('atr', 0), 2),
                }
                
                outcome = self._simulate_trade(df, i, entry, sl, tp, signal)
                trade.update(outcome)
                trades.append(trade)
        
        results_df = pd.DataFrame(trades)
        self._analyze_results(results_df)
        
        return results_df
    
    def _simulate_trade(self, df, entry_idx, entry_price, sl, tp, side, max_bars=48):
        """Симулирует сделку: стоп или тейк сработал раньше"""
        for i in range(entry_idx, min(entry_idx + max_bars, len(df))):
            row = df.iloc[i]
            
            if side == 'buy':
                if row['low'] <= sl:
                    return {
                        'exit_price': round(sl, 2),
                        'exit_reason': 'stop_loss',
                        'pnl_pct': round((sl - entry_price) / entry_price * 100 * self.leverage, 2),
                        'bars_held': i - entry_idx
                    }
                if row['high'] >= tp:
                    return {
                        'exit_price': round(tp, 2),
                        'exit_reason': 'take_profit',
                        'pnl_pct': round((tp - entry_price) / entry_price * 100 * self.leverage, 2),
                        'bars_held': i - entry_idx
                    }
            else:
                if row['high'] >= sl:
                    return {
                        'exit_price': round(sl, 2),
                        'exit_reason': 'stop_loss',
                        'pnl_pct': round((entry_price - sl) / entry_price * 100 * self.leverage, 2),
                        'bars_held': i - entry_idx
                    }
                if row['low'] <= tp:
                    return {
                        'exit_price': round(tp, 2),
                        'exit_reason': 'take_profit',
                        'pnl_pct': round((entry_price - tp) / entry_price * 100 * self.leverage, 2),
                        'bars_held': i - entry_idx
                    }
        
        # Таймаут — закрываем по рынку
        final_price = df.iloc[min(entry_idx + max_bars, len(df) - 1)]['close']
        if side == 'buy':
            pnl = (final_price - entry_price) / entry_price * 100 * self.leverage
        else:
            pnl = (entry_price - final_price) / entry_price * 100 * self.leverage
        
        return {
            'exit_price': round(final_price, 2),
            'exit_reason': 'timeout',
            'pnl_pct': round(pnl, 2),
            'bars_held': max_bars
        }
    
    def _analyze_results(self, trades_df):
        """Анализирует результаты торговли"""
        if len(trades_df) == 0:
            logger.info('Нет сделок для анализа')
            return
        
        total_trades = len(trades_df)
        wins = trades_df[trades_df['pnl_pct'] > 0]
        losses = trades_df[trades_df['pnl_pct'] <= 0]
        win_rate = len(wins) / total_trades * 100
        
        avg_win = wins['pnl_pct'].mean() if len(wins) > 0 else 0
        avg_loss = abs(losses['pnl_pct'].mean()) if len(losses) > 0 else 0
        total_pnl = trades_df['pnl_pct'].sum()
        
        profit_factor = (
            wins['pnl_pct'].sum() / abs(losses['pnl_pct'].sum())
            if len(losses) > 0 and losses['pnl_pct'].sum() != 0
            else float('inf')
        )
        
        # Распределение по уровням
        level_stats = {}
        for level in sorted(trades_df['fib_level'].unique()):
            lt = trades_df[trades_df['fib_level'] == level]
            lw = lt[lt['pnl_pct'] > 0]
            level_stats[level] = {
                'trades': len(lt),
                'win_rate': len(lw) / len(lt) * 100,
                'pnl': round(lt['pnl_pct'].sum(), 1)
            }
        
        # Статистика по направлениям
        long_trades = trades_df[trades_df['signal'] == 'buy']
        short_trades = trades_df[trades_df['signal'] == 'sell']
        
        logger.info('')
        logger.info('=' * 55)
        logger.info(f'  РЕЗУЛЬТАТЫ БЕКТЕСТА {self.symbol} ({self.interval})')
        logger.info('=' * 55)
        logger.info(f'  Всего сделок:      {total_trades}')
        logger.info(f'  Win Rate:          {win_rate:.1f}%')
        logger.info(f'  Средний выигрыш:   {avg_win:.2f}%')
        logger.info(f'  Средний проигрыш:  {avg_loss:.2f}%')
        logger.info(f'  Общий PnL:         {total_pnl:.2f}%')
        logger.info(f'  Profit Factor:     {profit_factor:.2f}')
        logger.info(f'  Макс. просадка:     {trades_df["pnl_pct"].min():.2f}%')
        logger.info(f'  Макс. прибыль:     {trades_df["pnl_pct"].max():.2f}%')
        
        if len(long_trades) > 0:
            lw_rate = len(long_trades[long_trades['pnl_pct'] > 0]) / len(long_trades) * 100
            logger.info(f'  Long:  {len(long_trades)} сделок, WR {lw_rate:.0f}%')
        if len(short_trades) > 0:
            sw_rate = len(short_trades[short_trades['pnl_pct'] > 0]) / len(short_trades) * 100
            logger.info(f'  Short: {len(short_trades)} сделок, WR {sw_rate:.0f}%')
        
        logger.info(f'')
        logger.info(f'  Распределение по уровням Фибоначчи:')
        for level, stats in sorted(level_stats.items()):
            logger.info(f'    Fib {level:.3f}: {stats["trades"]} сделок, '
                        f'WR {stats["win_rate"]:.0f}%, PnL {stats["pnl"]:+.1f}%')
        
        logger.info(f'')
        logger.info(f'  Причины выхода:')
        for reason in trades_df['exit_reason'].unique():
            rt = trades_df[trades_df['exit_reason'] == reason]
            logger.info(f'    {reason}: {len(rt)} сделок, '
                        f'средний PnL {rt["pnl_pct"].mean():+.2f}%')
        
        logger.info('=' * 55)
        logger.info('')


def main():
    parser = argparse.ArgumentParser(
        description='Fibonacci Strategy Backtest — фьючерсная торговля по уровням'
    )
    parser.add_argument('--symbol', type=str, default='ETHUSDT',
                        help='Торговая пара (ETHUSDT, BTCUSDT, SOLUSDT)')
    parser.add_argument('--interval', type=str, default='4h',
                        help='Таймфрейм (1h, 2h, 4h, 1d)')
    parser.add_argument('--leverage', type=int, default=3,
                        help='Плечо (1-5 для теста)')
    parser.add_argument('--swing-window', type=int, default=5,
                        help='Окно поиска экстремумов (3-10)')
    parser.add_argument('--no-rsi', action='store_true',
                        help='Отключить RSI фильтр')
    parser.add_argument('--no-volume', action='store_true',
                        help='Отключить фильтр объёма')
    parser.add_argument('--limit', type=int, default=500,
                        help='Количество свечей для теста')
    parser.add_argument('--save', type=str, default=None,
                        help='Сохранить результаты в JSON')
    
    args = parser.parse_args()
    
    logger.info(f'🚀 Fibonacci Strategy — запуск')
    logger.info(f'   Пара: {args.symbol} | ТФ: {args.interval} | Плечо: {args.leverage}x')
    logger.info(f'   Swing Window: {args.swing_window} | Свечей: {args.limit}')
    logger.info(f'   RSI: {"✅" if not args.no_rsi else "❌"} | Объём: {"✅" if not args.no_volume else "❌"}')
    
    strategy = FibonacciStrategy(
        symbol=args.symbol,
        leverage=args.leverage,
        interval=args.interval,
        swing_window=args.swing_window,
        confirmation_rsi=not args.no_rsi,
        volume_filter=not args.no_volume,
    )
    
    df = strategy.client.get_klines(args.interval, args.limit)
    if df is None:
        logger.error('❌ Не удалось получить данные с Binance')
        sys.exit(1)
    
    logger.info(f'📊 Данные: {len(df)} свечей, '
                f'{df["timestamp"].iloc[0].strftime("%Y-%m-%d")} — '
                f'{df["timestamp"].iloc[-1].strftime("%Y-%m-%d")}')
    
    results = strategy.run_backtest(df)
    
    if args.save and len(results) > 0:
        results_save = results.copy()
        results_save['timestamp'] = results_save['timestamp'].astype(str)
        results_save.to_json(args.save, orient='records', indent=2)
        logger.info(f'💾 Результаты сохранены в {args.save}')
    
    # Общая статистика
    if len(results) > 0:
        logger.info(f'\n📈 Итог: {len(results)} сделок, '
                    f'PnL {results["pnl_pct"].sum():+.2f}%')
    else:
        logger.info('\n📭 Сделок не найдено — попробуйте другие параметры')

    logger.info('✅ Бектест завершён')


if __name__ == '__main__':
    main()

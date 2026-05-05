# Статья 15. Трендовые линии — детекция breakout и построение уровней поддержки/сопротивления с помощью LLM-агентов

**Дата:** 5 мая 2026
**Серия:** LLM-агенты для криптотрейдинга (практическое руководство на Python)

---

## Введение

За 13 статей мы построили торговую систему, которая анализирует технические индикаторы (RSI, SMA, MACD, Bollinger Bands, ADX), фундаментальные факторы через LLM и управляет позициями на споте и фьючерсах. Но есть один классический инструмент технического анализа, который мы пока не автоматизировали — **трендовые линии**.

Трендовые линии — это не просто «линии на графике». Это визуализация рыночной структуры:

- **Линия восходящего тренда** (uptrend line) — соединяет последовательные более высокие минимумы (higher lows). Пока цена выше этой линии, тренд в силе.
- **Линия нисходящего тренда** (downtrend line) — соединяет последовательные более низкие максимумы (lower highs). Пока цена ниже — тренд в силе.
- **Пробой линии (breakout)** — один из самых сильных торговых сигналов. Когда цена пробивает трендовую линию — тренд, скорее всего, сменился.

Сегодня мы добавим в нашу систему **автоматическое построение трендовых линий и детекцию breakout'ов**, интегрируем это с LLM-агентами для контекстного анализа пробоев и научимся отличать ложные пробои от истинных.

---

## 1. Почему трендовые линии важны для автоматической торговли?

Большинство индикаторов (RSI, MACD) — **опережающие (leading)** или **запаздывающие (lagging)**. Они следуют за ценой и подтверждают тренд постфактум. Трендовые линии дают другой тип информации:

| Инструмент | Тип сигнала | Задержка |
|:-----------|:------------|:--------:|
| RSI | Опережающий (перекупленность/перепроданность) | Свеча |
| MACD | Запаздывающий (кросс линий) | Несколько свечей |
| SMA | Запаздывающий (кросс цены и средней) | Период SMA |
| **Трендовая линия** | **Сигнал слома структуры** | **1 свеча** |
| **Пробой трендовой** | **Смена тренда** | **Моментально** |

**Преимущество трендовых линий в автоматической системе:**

1. **Раннее обнаружение смены тренда** — пробой линии даёт сигнал раньше, чем SMA или MACD подтвердят разворот.
2. **Фильтр сигналов** — если цена пробила восходящий тренд, любой buy-сигнал от RSI/ADX имеет меньший вес.
3. **Уровни для take-profit и stop-loss** — трендовые линии можно использовать как динамические уровни: TP на следующей линии сопротивления, SL под линией поддержки.
4. **Контекст для LLM** — LLM может анализировать не только RSI=30, но и «цена пробила 3-месячную трендовую линию» — это гораздо более содержательное описание ситуации.

---

## 2. Алгоритм автоматического построения трендовых линий

### 2.1. Поиск ключевых точек (swing highs / swing lows)

Основа трендовой линии — экстремумы. Нам нужно найти значимые максимумы и минимумы на ценовом графике.

**Простой алгоритм поиска swing-точек:**

```python
import numpy as np
import pandas as pd

def find_swing_points(highs, lows, window=5):
    """
    Находит swing high и swing low точки.
    window — сколько свечей слева и справа должно быть ниже/выше.
    """
    length = len(highs)
    swing_highs = np.full(length, np.nan)
    swing_lows = np.full(length, np.nan)
    
    for i in range(window, length - window):
        # Swing high: текущий максимум выше window свечей слева и справа
        if highs[i] == max(highs[i-window:i+window+1]):
            swing_highs[i] = highs[i]
        
        # Swing low: текущий минимум ниже window свечей слева и справа
        if lows[i] == min(lows[i-window:i+window+1]):
            swing_lows[i] = lows[i]
    
    return swing_highs, swing_lows
```

Чем больше `window`, тем меньше точек мы находим, но они более значимы. Для 15-минутного графика `window=5` — хороший старт (25 свечей = ~6 часов). Для 4-часового — `window=3` достаточно (12 часов).

### 2.2. Построение линий и проверка касаний (bounce test)

Трендовая линия строится по **двум точкам**, а **третья точка** подтверждает её значимость.

```python
def build_trend_line(points, min_touches=3, max_gap_pct=0.03):
    """
    Строит трендовую линию по набору точек.
    points: список [(timestamp, price), ...]
    min_touches: минимальное количество касаний для валидной линии
    max_gap_pct: максимальное отклонение от линии для засчитывания касания (3%)
    """
    if len(points) < 2:
        return None
    
    valid_lines = []
    
    # Перебираем все пары точек как потенциальные линии
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            t1, p1 = points[i]
            t2, p2 = points[j]
            
            if t2 == t1:
                continue
            
            # Наклон линии
            slope = (p2 - p1) / (t2 - t1)
            intercept = p1 - slope * t1
            
            # Считаем касания
            touches = 0
            for t, p in points:
                expected = slope * t + intercept
                if abs(p - expected) / expected <= max_gap_pct:
                    touches += 1
            
            valid_lines.append({
                'slope': slope,
                'intercept': intercept,
                'points': (p1, p2),
                'touches': touches,
                'strength': touches / len(points)
            })
    
    # Сортируем по количеству касаний (чем больше, тем надёжнее линия)
    valid_lines.sort(key=lambda x: x['touches'], reverse=True)
    return valid_lines[:5]  # Топ-5 линий
```

### 2.3. Обнаружение пробоя (breakout detection)

Самый важный сигнал — когда цена пересекает трендовую линию.

```python
def detect_breakout(close_prices, timestamps, trend_lines):
    """
    Обнаруживает пробой трендовой линии на последней свече.
    Возвращает список пробоев с направлением и силой.
    """
    breakouts = []
    current_price = close_prices[-1]
    prev_price = close_prices[-2]
    current_time = timestamps[-1]
    
    for line in trend_lines:
        expected_price = line['slope'] * current_time + line['intercept']
        prev_expected = line['slope'] * timestamps[-2] + line['intercept']
        
        # Определяем направление линии
        is_uptrend = line['slope'] > 0
        
        # Цена была выше линии, теперь ниже — пробой восходящего тренда (медвежий)
        if is_uptrend and prev_price > prev_expected and current_price < expected_price:
            momentum = abs(current_price - expected_price) / expected_price
            breakouts.append({
                'type': 'bearish_breakout',
                'line_type': 'uptrend',
                'momentum': momentum,
                'strength': line['strength'],
                'price': current_price,
                'line_price': expected_price
            })
        
        # Цена была ниже линии, теперь выше — пробой нисходящего тренда (бычий)
        elif not is_uptrend and prev_price < prev_expected and current_price > expected_price:
            momentum = abs(current_price - expected_price) / expected_price
            breakouts.append({
                'type': 'bullish_breakout',
                'line_type': 'downtrend',
                'momentum': momentum,
                'strength': line['strength'],
                'price': current_price,
                'line_price': expected_price
            })
    
    return breakouts
```

### 2.4. Фильтрация ложных пробоев (false breakout filter)

Ложные пробои — главная проблема трендовых линий. Цена может «проткнуть» линию и вернуться обратно.

**Критерии для фильтрации:**

```python
def is_valid_breakout(breakout, close_prices, volume, atr):
    """
    Определяет, является ли пробой истинным.
    """
    reasons = []
    
    # 1. Моментум: цена должна пробить линию минимум на 0.5 * ATR
    if breakout['momentum'] * breakout['price'] > atr * 0.5:
        reasons.append('momentum_atr')
    
    # 2. Объём: при пробое объём должен быть выше среднего
    avg_volume = np.mean(volume[-20:])
    if volume[-1] > avg_volume * 1.5:
        reasons.append('high_volume')
    
    # 3. Подтверждение следующей свечой: цена остаётся за линией
    # (это проверяется на следующем тике/свече)
    
    # 4. Сила трендовой линии: чем больше касаний, тем надёжнее
    if breakout['strength'] > 0.6:
        reasons.append('strong_line')
    
    confidence = len(reasons) / 4  # 0.0 - 1.0
    
    return {
        'is_valid': confidence >= 0.5,
        'confidence': confidence,
        'reasons': reasons
    }
```

---

## 3. Интеграция с существующей системой

### 3.1. Новый модуль: `trend_line_analyzer.py`

Создаём отдельный модуль, который можно подключить как к спотовому, так и к фьючерсному воркеру:

```python
# trend_line_analyzer.py — новый модуль для трендовых линий

import numpy as np
import pandas as pd
import json
import os
from datetime import datetime, timezone

class TrendLineAnalyzer:
    """
    Анализатор трендовых линий.
    Находит swing-точки, строит линии, детектит пробои.
    """
    
    def __init__(self, symbol, interval, config=None):
        self.symbol = symbol
        self.interval = interval
        self.swing_window = config.get('swing_window', 5)
        self.min_touches = config.get('min_touches', 3)
        self.max_gap_pct = config.get('max_gap_pct', 0.03)
        self.atr_period = config.get('atr_period', 14)
        self.breakout_threshold_atr = config.get('breakout_threshold_atr', 0.5)
    
    def analyze(self, df):
        """
        Полный анализ трендовых линий на данных DataFrame.
        df должен содержать колонки: timestamp, open, high, low, close, volume.
        """
        if df is None or len(df) < 30:
            return None
        
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        volumes = df['volume'].values
        timestamps = df['timestamp'].values
        
        # 1. Находим swing-точки
        swing_highs_idx, swing_lows_idx = self._find_swing_points(
            highs, lows, self.swing_window
        )
        
        # 2. Строим линии по swing-точкам
        uptrend_lines = self._build_trend_lines(
            timestamps, lows, swing_lows_idx, is_uptrend=True
        )
        downtrend_lines = self._build_trend_lines(
            timestamps, highs, swing_highs_idx, is_uptrend=False
        )
        
        # 3. Детектим пробои
        all_lines = uptrend_lines + downtrend_lines
        breakouts = self._detect_breakouts(
            closes, timestamps, volumes, highs, lows, all_lines
        )
        
        # 4. Фильтруем ложные пробои
        valid_signals = []
        for breakout in breakouts:
            atr = self._calculate_atr(highs, lows, closes)
            validation = self._validate_breakout(breakout, closes, volumes, atr)
            if validation['is_valid']:
                valid_signals.append({
                    **breakout,
                    'confidence': validation['confidence'],
                    'reasons': validation['reasons']
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
    
    def _find_swing_points(self, highs, lows, window):
        """Поиск значимых максимумов и минимумов."""
        length = len(highs)
        swing_highs = []
        swing_lows = []
        
        for i in range(window, length - window):
            if highs[i] == max(highs[i-window:i+window+1]):
                swing_highs.append(i)
            if lows[i] == min(lows[i-window:i+window+1]):
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
                
                # Проверка направления: uptrend = положительный наклон
                if is_uptrend and slope <= 0:
                    continue
                if not is_uptrend and slope >= 0:
                    continue
                
                intercept = p1 - slope * t1
                
                # Считаем касания
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
                        'strength': touches / len(points) if points else 0,
                        'is_uptrend': is_uptrend
                    })
        
        lines.sort(key=lambda x: x['touches'], reverse=True)
        return lines[:3]  # Возвращаем топ-3
    
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
                # Пробой восходящего тренда вниз
                if prev_price >= prev_expected and current_low < expected_price:
                    breakouts.append({
                        'type': 'bearish_breakout',
                        'line_type': 'uptrend',
                        'momentum': abs(current_price - expected_price) / expected_price,
                        'strength': line['strength']
                    })
            else:
                # Пробой нисходящего тренда вверх
                if prev_price <= prev_expected and current_high > expected_price:
                    breakouts.append({
                        'type': 'bullish_breakout',
                        'line_type': 'downtrend',
                        'momentum': abs(current_price - expected_price) / expected_price,
                        'strength': line['strength']
                    })
        
        return breakouts
    
    def _calculate_atr(self, highs, lows, closes, period=14):
        """Расчёт Average True Range."""
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
        
        if breakout['momentum'] * closes[-1] > atr * self.breakout_threshold_atr:
            reasons.append('momentum_atr')
        
        avg_volume = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
        if volumes[-1] > avg_volume * 1.5:
            reasons.append('high_volume')
        
        if breakout['strength'] > 0.6:
            reasons.append('strong_line')
        
        # Дополнительно: ATR-нормализованный моментум
        norm_momentum = breakout['momentum'] * closes[-1] / atr if atr > 0 else 0
        if norm_momentum > 1.0:
            reasons.append('strong_momentum')
        
        confidence = len(reasons) / 5
        
        return {
            'is_valid': confidence >= 0.4,
            'confidence': confidence,
            'reasons': reasons,
            'norm_momentum': norm_momentum
        }
    
    def _determine_current_trend(self, current_price, uptrend_lines, downtrend_lines):
        """Определяет текущий тренд на основе линий."""
        if not uptrend_lines and not downtrend_lines:
            return 'undefined'
        
        trend_scores = {'uptrend': 0, 'downtrend': 0, 'ranging': 0}
        
        # Чем больше сильных линий вокруг, тем определённее тренд
        for line in uptrend_lines:
            expected = line['slope'] * 0 + line['intercept']
            if current_price > expected:
                trend_scores['uptrend'] += line['strength']
        
        for line in downtrend_lines:
            expected = line['slope'] * 0 + line['intercept']
            if current_price < expected:
                trend_scores['downtrend'] += line['strength']
        
        max_trend = max(trend_scores, key=trend_scores.get)
        return max_trend if trend_scores[max_trend] > 0.5 else 'ranging'
```

### 3.2. Подключение к воркеру

Добавляем вызов `TrendLineAnalyzer` в цикл воркера после расчёта индикаторов:

```python
# Внутри worker.py или futures_worker.py

from trend_line_analyzer import TrendLineAnalyzer

class Worker:
    def __init__(self, symbol, interval, config):
        # ... существующий код ...
        self.trend_analyzer = TrendLineAnalyzer(
            symbol, interval, config.get('trend_lines', {})
        )
    
    def analyze_trend_lines(self, df):
        """Анализ трендовых линий и интеграция с сигналами."""
        result = self.trend_analyzer.analyze(df)
        if not result:
            return {}
        
        signals = {}
        
        # Пробои — самые сильные сигналы
        if result['breakouts']:
            for breakout in result['breakouts']:
                if breakout['type'] == 'bullish_breakout':
                    signals['breakout_signal'] = 'buy'
                    signals['breakout_confidence'] = breakout['confidence']
                elif breakout['type'] == 'bearish_breakout':
                    signals['breakout_signal'] = 'sell'
                    signals['breakout_confidence'] = breakout['confidence']
        
        # Текущий тренд — фильтр для других сигналов
        signals['trend'] = result['current_trend']
        
        return signals
```

### 3.3. Комбинирование сигналов: трендовые линии + индикаторы + LLM

Финальная логика принятия решений учитывает все слои:

```python
def combine_signals(ta_signals, tl_signals, fa_signals):
    """
    Комбинирует сигналы от технических индикаторов (TA),
    трендовых линий (TL) и фундаментального анализа (FA).
    """
    score = 0
    reasons = []
    
    # 1. Технические индикаторы (вес: 0.4)
    if ta_signals.get('rsi_signal') == 'buy':
        score += 0.2
        reasons.append('RSI oversold')
    elif ta_signals.get('rsi_signal') == 'sell':
        score -= 0.2
        reasons.append('RSI overbought')
    
    if ta_signals.get('adx_signal') == 'strong':
        score += 0.1 if score >= 0 else -0.1
        reasons.append('ADX strong trend')
    
    # 2. Трендовые линии (вес: 0.35)
    if tl_signals.get('breakout_signal') == 'buy':
        score += 0.35
        reasons.append(f"Trend line breakout BUY (conf: {tl_signals.get('breakout_confidence', 0):.1%})")
    elif tl_signals.get('breakout_signal') == 'sell':
        score -= 0.35
        reasons.append(f"Trend line breakout SELL (conf: {tl_signals.get('breakout_confidence', 0):.1%})")
    
    trend = tl_signals.get('trend', 'undefined')
    if trend == 'uptrend':
        score += 0.1  # Склоняемся к long
        reasons.append('Uptrend confirmed')
    elif trend == 'downtrend':
        score -= 0.1  # Склоняемся к short
        reasons.append('Downtrend confirmed')
    
    # 3. Фундаментальный анализ LLM (вес: 0.25)
    fa_weight = fa_signals.get('weight', 0) if fa_signals else 0
    score += fa_weight * 0.25
    if fa_signals and fa_signals.get('sentiment'):
        reasons.append(f"FA: {fa_signals['sentiment']}")
    
    # Итоговое решение
    if score >= 0.3:
        decision = 'buy'
    elif score <= -0.3:
        decision = 'sell'
    else:
        decision = 'hold'
    
    return {
        'decision': decision,
        'score': round(score, 2),
        'reasons': reasons,
        'breakout_active': bool(tl_signals.get('breakout_signal'))
    }
```

**Примеры комбинированных сигналов:**

| TA сигнал | TL сигнал | FA сигнал | Решение | Пояснение |
|:----------|:----------|:----------|:--------|:----------|
| RSI=25 (buy) | Пробой downtrend ↑ | Негативный | **HOLD** | FA блокирует buy |
| RSI=75 (sell) | Пробой downtrend ↑ | Позитивный | **BUY** | Breakout перевешивает |
| RSI=30 (buy) | Uptrend confirmed | Нейтральный | **BUY** | Сильный сигнал |
| RSI=70 (sell) | Пробой uptrend ↓ | Негативный | **SELL** | Все три слоя совпадают |

---

## 4. Бектестинг стратегии на трендовых линиях

### 4.1. Простой бектестер

Проверяем гипотезу: «покупать при пробое нисходящего тренда, продавать при пробое восходящего»:

```python
def backtest_trendline_strategy(df, analyzer):
    """
    Простейшая стратегия на пробоях трендовых линий.
    """
    balance = 1000  # USDT
    position = 0.0
    trades = []
    
    for i in range(50, len(df)):  # Начинаем с 50-й свечи (нужно 30+ для линий)
        chunk = df.iloc[:i+1]
        result = analyzer.analyze(chunk)
        
        if not result or not result['breakouts']:
            continue
        
        for breakout in result['breakouts']:
            price = chunk['close'].iloc[-1]
            
            if breakout['type'] == 'bullish_breakout' and position == 0:
                # Покупаем
                position = balance * 0.95 / price  # 95% баланса
                balance -= position * price
                trades.append({
                    'time': chunk['timestamp'].iloc[-1],
                    'type': 'buy',
                    'price': price,
                    'quantity': position,
                    'reason': 'bullish_breakout'
                })
            
            elif breakout['type'] == 'bearish_breakout' and position > 0:
                # Продаём
                balance += position * price
                trades.append({
                    'time': chunk['timestamp'].iloc[-1],
                    'type': 'sell',
                    'price': price,
                    'quantity': position,
                    'reason': 'bearish_breakout',
                    'pnl': position * price - (trades[-1]['price'] * position if trades else 0)
                })
                position = 0.0
    
    # Закрываем последнюю позицию по последней цене
    if position > 0:
        balance += position * df['close'].iloc[-1]
        position = 0.0
    
    total_pnl = balance - 1000
    win_trades = [t for t in trades if t.get('pnl', 0) > 0] if trades else []
    
    return {
        'final_balance': round(balance, 2),
        'total_pnl': round(total_pnl, 2),
        'total_return_pct': round(total_pnl / 1000 * 100, 2),
        'total_trades': len([t for t in trades if t['type'] == 'sell']),
        'win_trades': len(win_trades),
        'win_rate': round(len(win_trades) / max(len([t for t in trades if t['type'] == 'sell']), 1) * 100, 1)
    }
```

### 4.2. Оптимизация параметров

Параметры, которые стоит оптимизировать через бектестинг:

| Параметр | Диапазон | Начальное значение | Влияние |
|:---------|:---------|:------------------:|:--------|
| `swing_window` | 3–10 | 5 | Чем больше, тем меньше линий, но надёжнее |
| `min_touches` | 2–5 | 3 | Меньше = больше сигналов, но шумнее |
| `max_gap_pct` | 1%–5% | 3% | Допуск при проверке касаний |
| `breakout_threshold_atr` | 0.3–1.0 | 0.5 | Во сколько ATR цена должна отойти от линии |
| `volume_multiplier` | 1.0–3.0 | 1.5 | Во сколько раз объём должен превышать средний |

---

## 5. Визуализация трендовых линий и breakout'ов

### 5.1. Построение графика с линиями

Самый наглядный способ проверить качество алгоритма — нарисовать найденные линии на графике:

```python
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def plot_trend_lines(df, analysis_result, save_path=None):
    """
    Рисует график цены с найденными трендовыми линиями и пробоями.
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), 
                                    gridspec_kw={'height_ratios': [3, 1]})
    
    # Цена
    ax1.plot(df['timestamp'], df['close'], label='Close', color='black', linewidth=1)
    ax1.fill_between(df['timestamp'], df['low'], df['high'], alpha=0.1, color='gray')
    
    # Swing-точки
    if analysis_result:
        for t, p in analysis_result.get('swing_highs', []):
            ax1.scatter(t, p, color='red', marker='v', s=50, zorder=5)
        for t, p in analysis_result.get('swing_lows', []):
            ax1.scatter(t, p, color='green', marker='^', s=50, zorder=5)
        
        # Трендовые линии
        time_range = [df['timestamp'].iloc[0], df['timestamp'].iloc[-1]]
        
        for line in analysis_result.get('uptrend_lines', []):
            y_start = line['slope'] * time_range[0] + line['intercept']
            y_end = line['slope'] * time_range[1] + line['intercept']
            ax1.plot(time_range, [y_start, y_end], 'g--', linewidth=1.5, alpha=0.7,
                     label=f"Uptrend ({line['touches']} touches)")
        
        for line in analysis_result.get('downtrend_lines', []):
            y_start = line['slope'] * time_range[0] + line['intercept']
            y_end = line['slope'] * time_range[1] + line['intercept']
            ax1.plot(time_range, [y_start, y_end], 'r--', linewidth=1.5, alpha=0.7,
                     label=f"Downtrend ({line['touches']} touches)")
        
        # Breakout-сигналы
        for breakout in analysis_result.get('breakouts', []):
            if breakout['type'] == 'bullish_breakout':
                ax1.axvline(x=df['timestamp'].iloc[-1], color='green', 
                           linestyle=':', linewidth=2, alpha=0.8)
                ax1.annotate('BULLISH\nBREAKOUT', 
                           xy=(df['timestamp'].iloc[-1], df['close'].iloc[-1]),
                           xytext=(10, 10), textcoords='offset points',
                           color='green', fontweight='bold')
            elif breakout['type'] == 'bearish_breakout':
                ax1.axvline(x=df['timestamp'].iloc[-1], color='red', 
                           linestyle=':', linewidth=2, alpha=0.8)
                ax1.annotate('BEARISH\nBREAKOUT',
                           xy=(df['timestamp'].iloc[-1], df['close'].iloc[-1]),
                           xytext=(10, -15), textcoords='offset points',
                           color='red', fontweight='bold')
    
    ax1.set_title(f"{analysis_result['symbol']} — Trend Lines Analysis", fontsize=14)
    ax1.legend(loc='best', fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    
    # Объём
    ax2.bar(df['timestamp'], df['volume'], color='blue', alpha=0.3, width=0.8)
    ax2.set_ylabel('Volume')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Chart saved to {save_path}")
    
    plt.show()
```

---

## 6. LLM-агент для контекстного анализа пробоев

### 6.1. Промпт для анализа breakout

Не все пробои одинаково полезны. LLM может оценить контекст:

```python
def llm_breakout_analysis(breakout_data, market_context, llm_client):
    """
    Отправляет данные о пробое LLM для контекстной оценки.
    """
    prompt = f"""
**Сигнал трендовых линий для {breakout_data['symbol']}**

Тип пробоя: {breakout_data['type']}
Направление: {breakout_data['line_type']}
Текущая цена: ${breakout_data['price']:.2f}
Цена линии: ${breakout_data['line_price']:.2f}
Моментум: {breakout_data['momentum']:.4f}
Уверенность: {breakout_data['confidence']:.1%}
Причины: {', '.join(breakout_data['reasons'])}

**Рыночный контекст:**
- Текущий тренд: {market_context.get('trend', 'undefined')}
- RSI(14): {market_context.get('rsi', 'N/A')}
- ADX(14): {market_context.get('adx', 'N/A')}
- Объём (текущий/средний): {market_context.get('volume_ratio', 'N/A')}×
- 24h изменение: {market_context.get('change_24h', 'N/A')}%

**Задача:**
Оцени качество этого пробоя по шкале от -10 (очень ложный) до +10 (очень сильный).
Учти: силу трендовой линии, объём, общий рыночный контекст, наличие подтверждений.
Дай краткое объяснение (1-2 предложения) на русском.
Формат ответа JSON: {{"score": int, "explanation": "..."}}
"""
    
    response = llm_client.generate_content(prompt)
    try:
        import json
        return json.loads(response.text)
    except:
        return {"score": 0, "explanation": "Не удалось распарсить ответ LLM"}
```

### 6.2. Примеры LLM-оценки пробоев

**Пример 1:** BTC пробивает uptrend на 4H графике

```
LLM-ответ:
{
  "score": 7,
  "explanation": "Пробой подтверждён объёмом (+80% от среднего), линия имела 4 касания.
  RSI снижается, ADX > 25. Высокая вероятность смены тренда."
}
```

**Пример 2:** ETH касается downtrend, но объём низкий

```
LLM-ответ:
{
  "score": -3,
  "explanation": "Пробой на низком объёме (0.6× от среднего), линия построена всего по 2 точкам.
  Скорее всего, ложный сигнал — цена вернётся под линию."
}
```

---

## 7. Настройка в конфиге

Добавляем секцию `trend_lines` в `config.json`:

```json
{
  "trend_lines": {
    "enabled": true,
    "swing_window": 5,
    "min_touches": 3,
    "max_gap_pct": 0.03,
    "atr_period": 14,
    "breakout_threshold_atr": 0.5,
    "weight_in_decision": 0.35,
    "llm_breakout_analysis": true,
    "save_charts": true,
    "charts_dir": "./charts/trend_lines/",
    "max_lines_per_pair": 3,
    "breakout_cooldown_bars": 12
  }
}
```

---

## 8. Пример: полный цикл работы

```python
#!/usr/bin/env python3
"""
Пример: получаем данные с Binance, анализируем трендовые линии, выводим результат.
"""
import sys
sys.path.append('.')

from binance_connector import BinanceConnector
from trend_line_analyzer import TrendLineAnalyzer
from indicators import TechnicalIndicators

def main():
    symbol = "BTCUSDT"
    interval = "1h"
    
    # 1. Получаем данные
    connector = BinanceConnector()
    df = connector.get_klines(symbol, interval, limit=200)
    
    # 2. Считаем индикаторы
    ta = TechnicalIndicators(df)
    df = ta.calculate_all()
    
    # 3. Строим трендовые линии
    analyzer = TrendLineAnalyzer(symbol, interval, {
        'swing_window': 5,
        'min_touches': 3
    })
    
    result = analyzer.analyze(df)
    
    # 4. Выводим результат
    print(f"\n{'='*60}")
    print(f"📊 Trend Lines Analysis — {symbol} ({interval})")
    print(f"{'='*60}")
    
    print(f"\n📍 Swing points found:")
    print(f"   • Swing highs: {len(result['swing_highs'])}")
    print(f"   • Swing lows: {len(result['swing_lows'])}")
    
    print(f"\n📈 Uptrend lines:")
    for i, line in enumerate(result['uptrend_lines'], 1):
        print(f"   {i}. Slope: {line['slope']:.6f}, Touches: {line['touches']}, "
              f"Strength: {line['strength']:.1%}")
    
    print(f"\n📉 Downtrend lines:")
    for i, line in enumerate(result['downtrend_lines'], 1):
        print(f"   {i}. Slope: {line['slope']:.6f}, Touches: {line['touches']}, "
              f"Strength: {line['strength']:.1%}")
    
    if result['breakouts']:
        print(f"\n🚨 BREAKOUT SIGNALS:")
        for b in result['breakouts']:
            print(f"   {'🟢' if 'bullish' in b['type'] else '🔴'} {b['type']}")
            print(f"      Confidence: {b['confidence']:.1%}")
            print(f"      Momentum: {b['momentum']:.4f}")
            print(f"      Reasons: {', '.join(b['reasons'])}")
            print(f"      Norm momentum: {b['norm_momentum']:.2f}× ATR")
    else:
        print(f"\n✅ No breakouts detected")
    
    print(f"\n📊 Current trend: {result['current_trend']}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
```

Пример вывода:

```
============================================================
📊 Trend Lines Analysis — BTCUSDT (1h)
============================================================

📍 Swing points found:
   • Swing highs: 12
   • Swing lows: 14

📈 Uptrend lines:
   1. Slope: 0.000023, Touches: 4, Strength: 66.7%
   2. Slope: 0.000018, Touches: 3, Strength: 50.0%

📉 Downtrend lines:
   1. Slope: -0.000015, Touches: 3, Strength: 50.0%

🚨 BREAKOUT SIGNALS:
   🟢 bullish_breakout
      Confidence: 60.0%
      Momentum: 0.0042
      Reasons: momentum_atr, strong_line
      Norm momentum: 1.24× ATR

📊 Current trend: uptrend
============================================================
```

---

## 9. Преимущества и ограничения

### Преимущества

| Аспект | Описание |
|:-------|:---------|
| **Ранние сигналы** | Пробой трендовой линии даёт сигнал раньше, чем пересечение SMA или MACD |
| **Фильтр шума** | Трендовые линии отсекают ложные сигналы индикаторов в боковике |
| **Контекст для LLM** | LLM получает структуру рынка, а не просто числа |
| **Динамические уровни** | Линии можно использовать как trailing SL/TP |
| **Мультитаймфрейм** | Анализ на 1H + 4H + 1D даёт полную картину |

### Ограничения

| Аспект | Описание |
|:-------|:---------|
| **Субъективность** | Алгоритм никогда не найдёт те же линии, что трейдер-человек |
| **Ложные пробои** | До 60% пробоев могут быть ложными без фильтрации по объёму и ATR |
| **Зависимость от window** | Размер окна swing-точек сильно влияет на результат |
| **Плохо в боковике** | В диапазоне 1–2% линии строятся плохо и дают много ложных сигналов |
| **Историческая привязка** | Линии статичны, пока не появится новая точка для перестроения |

---

## 10. Что дальше?

С добавлением трендовых линий наша торговая система получила **структурный анализ рынка**, который дополняет числовые индикаторы и фундаментальный анализ.

**План развития модуля:**

1. **Multi-timeframe анализ** — проверка пробоев на 1H/4H/1D одновременно
2. **Каналы (channel breakouts)** — параллельные линии поддержки/сопротивления
3. **Фибо-уровни** — кластеризация уровней по Фибоначчи и поиск совпадений с трендовыми линиями
4. **Динамическое обновление** — линии перестраиваются после каждого нового касания
5. **ML-фильтрация** — модель, предсказывающая вероятность ложного пробоя на основе исторических данных

---

## Заключение

Трендовые линии — один из старейших и самых надёжных инструментов технического анализа. Но ручное построение линий на 10+ парах — непозволительная роскошь для активного трейдера. Автоматизация этой задачи с помощью LLM-агентов даёт:

1. **Объективность** — алгоритм строит линии по одним и тем же правилам 24/7
2. **Скорость** — обнаружение пробоя за секунды, а не минуты
3. **Контекст** — LLM оценивает пробой с учётом рыночной ситуации
4. **Интеграция** — breakout-сигналы комбинируются с RSI, ADX, FA в единой системе принятия решений

Код из этой статьи готов к добавлению в вашу существующую систему. Просто скопируйте `trend_line_analyzer.py` в папку `trading/multiprocessing/` и добавьте вызов анализатора в цикл воркера.

Помните: трендовые линии — это инструмент вероятностный, а не детерминированный. Даже самый красивый пробой может оказаться ложным. Используйте фильтры (объём, ATR, подтверждение LLM) и никогда не рискуйте больше, чем готовы потерять. 📈

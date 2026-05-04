🚀 *СТАТЬЯ 6/12*  
*LLM‑агенты для трейдинга: практическое руководство на Python + OpenClaw*

📉 *Риск‑менеджмент и управление капиталом: как агент защищает ваш депозит*

В предыдущих статьях мы научили агента находить сигналы, тестировать стратегии и оптимизировать параметры. Теперь настало время для самого важного — **защиты капитала**. Самые прибыльные стратегии бесполезны, если одна неудачная сделка уничтожает весь депозит.

Сегодня мы внедрим в агента полноценный риск‑менеджмент и систему управления капиталом. Он будет рассчитывать размер позиции на основе волатильности актива, ограничивать максимальную просадку, диверсифицировать портфель и автоматически снижать риск при ухудшении рыночных условий.

К концу статьи у вас будет:

✅ **Позиционный риск‑менеджмент** — расчёт размера позиции на основе ATR (Average True Range) и волатильности  
✅ **Портфельный риск‑менеджмент** — распределение капитала между несколькими активами по методу Келли или Fixed Fractional  
✅ **Динамический стоп‑лосс и тейк‑профит** — автоматическая адаптация уровней остановки к текущей волатильности  
✅ **Лимиты на максимальную просадку и дневные потери** — агент остановит торговлю при превышении порогов  
✅ **Интеграция с OpenClaw** — мониторинг рисков в реальном времени, уведомления о критических ситуациях, автоматическое снижение экспозиции  

---

🤖 *Зачем риск‑менеджмент трейдеру?*

Без управления рисками даже самая точная стратегия обречена на провал. Статистика: 90% трейдеров теряют деньги именно из‑за отсутствия дисциплины в риск‑менеджменте.

1. **Размер позиции** — сколько торговать в каждой сделке? Фиксированный лот или процент от капитала? Агент рассчитает оптимальный размер на основе волатильности актива.
2. **Стоп‑лосс и тейк‑профит** — где ставить остановки? Жёсткие уровни или динамические, основанные на ATR? Агент адаптирует их к текущему рынку.
3. **Диверсификация** — как распределить капитал между несколькими активами, чтобы снизить общий риск? Агент использует современные портфельные теории.
4. **Мониторинг просадки** — когда остановиться, если стратегия перестала работать? Агент отслеживает максимальную просадку и автоматически прекращает торговлю при достижении лимита.

*Пример сценария:* Агент торгует BTC, ETH и SOL одновременно. Для каждого актива он рассчитывает размер позиции как 2% от капитала, умноженный на коэффициент волатильности (ATR). Стоп‑лосс устанавливается на уровне 1.5×ATR ниже цены входа, тейк‑профит — 3×ATR выше. Максимальная допустимая просадка на портфель — 20%. При достижении 15% просадки агент снижает размер позиций вдвое, при 20% — закрывает все позиции и отправляет уведомление. Еженедельно агент пересчитывает распределение капитала по методу Келли на основе исторической доходности и корреляции активов.

---

🔧 *Шаг 1. Установка дополнительных библиотек*

Для расчёта волатильности и корреляций нам понадобятся библиотеки `scipy` (для статистических функций) и `yfinance` (для загрузки данных традиционных активов, если хотим диверсифицировать за пределы крипто). Установим их:

```bash
pip3 install scipy yfinance
```

*Примечание:* `ta` (Technical Analysis) уже установлена и содержит функцию `average_true_range`.

---

🔧 *Шаг 2. Позиционный риск‑менеджмент на основе ATR*

Average True Range (ATR) — индикатор волатильности, который показывает средний диапазон движения цены за определённый период. Используем его для расчёта динамического стоп‑лосса и размера позиции.

Создадим файл `risk_position.py` в директории `trading/`:

```python
import pandas as pd
import ta

def calculate_position_size(capital, risk_per_trade, entry_price, stop_loss_price):
    """
    Рассчитывает размер позиции в единицах актива на основе процента риска на сделку.
    
    Параметры:
        capital: доступный капитал (например, 10 000 USDT)
        risk_per_trade: доля капитала, которую можно рискнуть на одну сделку (например, 0.02 = 2%)
        entry_price: цена входа
        stop_loss_price: цена стоп‑лосса
    
    Возвращает:
        size: количество единиц актива для покупки/продажи
    """
    risk_amount = capital * risk_per_trade
    price_risk = abs(entry_price - stop_loss_price)
    size = risk_amount / price_risk
    return size

def calculate_atr_stop_loss(data, period=14, multiplier=1.5):
    """
    Рассчитывает динамический стоп‑лосс на основе ATR.
    
    Параметры:
        data: DataFrame с колонками High, Low, Close
        period: период для расчёта ATR
        multiplier: множитель ATR (например, 1.5 означает стоп‑лосс на расстоянии 1.5×ATR)
    
    Возвращает:
        stop_loss: Series со значениями стоп‑лосса для каждой свечи
    """
    atr = ta.volatility.AverageTrueRange(data['High'], data['Low'], data['Close'], window=period).average_true_range()
    stop_loss = data['Close'] - multiplier * atr
    return stop_loss

def calculate_position_size_by_atr(capital, risk_per_trade, entry_price, atr_value, multiplier=1.5):
    """
    Рассчитывает размер позиции на основе ATR.
    
    Параметры:
        capital: доступный капитал
        risk_per_trade: доля капитала для риска на сделку
        entry_price: цена входа
        atr_value: текущее значение ATR
        multiplier: множитель ATR для стоп‑лосса
    
    Возвращает:
        size: количество единиц актива
        stop_loss: цена стоп‑лосса
    """
    stop_loss = entry_price - multiplier * atr_value
    size = calculate_position_size(capital, risk_per_trade, entry_price, stop_loss)
    return size, stop_loss

# Пример использования
if __name__ == "__main__":
    from data_fetcher import fetch_historical_data
    
    data = fetch_historical_data('BTCUSDT', '1d', days=100)
    if data.empty:
        print("Ошибка: не удалось загрузить данные. Проверьте подключение к интернету и API‑ключи.")
        exit(1)
    atr = ta.volatility.AverageTrueRange(data['High'], data['Low'], data['Close'], window=14).average_true_range()
    current_atr = atr.iloc[-1]
    entry_price = data['Close'].iloc[-1]
    capital = 10_000
    risk_per_trade = 0.02  # 2%
    
    size, stop_loss = calculate_position_size_by_atr(capital, risk_per_trade, entry_price, current_atr, multiplier=1.5)
    print(f"Цена входа: {entry_price:.2f}")
    print(f"ATR: {current_atr:.2f}")
    print(f"Стоп‑лосс: {stop_loss:.2f}")
    print(f"Размер позиции: {size:.6f} BTC")
    print(f"Сумма риска: {capital * risk_per_trade:.2f} USDT")
```

Теперь агент может рассчитать, сколько BTC купить, чтобы рискнуть только 2% капитала, при этом стоп‑лосс будет адаптирован к текущей волатильности.

---

🔧 *Шаг 3. Портфельный риск‑менеджмент и диверсификация*

Торговать несколькими активами без учёта корреляции — всё равно что носить воду в решете. Реализуем простую модель диверсификации на основе исторической корреляции и волатильности.

Создадим файл `risk_portfolio.py`:

```python
import pandas as pd
import numpy as np
from scipy.optimize import minimize

def calculate_correlation_matrix(returns_df):
    """
    Рассчитывает матрицу корреляции доходностей активов.
    
    Параметры:
        returns_df: DataFrame, где каждая колонка — доходность одного актива
    
    Возвращает:
        corr_matrix: матрица корреляции
    """
    return returns_df.corr()

def minimum_variance_portfolio(returns_df):
    """
    Находит веса портфеля с минимальной дисперсией (минимальным риском).
    
    Параметры:
        returns_df: DataFrame с доходностями активов
    
    Возвращает:
        weights: массив весов (сумма = 1)
        portfolio_return: ожидаемая доходность портфеля
        portfolio_volatility: волатильность портфеля
    """
    cov_matrix = returns_df.cov()
    n_assets = len(returns_df.columns)
    
    # Целевая функция: дисперсия портфеля
    def portfolio_variance(weights):
        return weights @ cov_matrix @ weights
    
    # Ограничения: сумма весов = 1, веса >= 0 (без коротких позиций)
    constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1})
    bounds = tuple((0, 1) for _ in range(n_assets))
    initial_weights = np.ones(n_assets) / n_assets
    
    result = minimize(portfolio_variance, initial_weights, method='SLSQP', bounds=bounds, constraints=constraints)
    weights = result.x
    portfolio_return = np.sum(returns_df.mean() * weights)
    portfolio_volatility = np.sqrt(portfolio_variance(weights))
    
    return weights, portfolio_return, portfolio_volatility

def kelly_criterion(win_rate, avg_win, avg_loss):
    """
    Рассчитывает дробь Келли — оптимальный процент капитала для ставки.
    
    Параметры:
        win_rate: вероятность выигрыша (0..1)
        avg_win: средний выигрыш (в процентах или абсолютных единицах)
        avg_loss: средний проигрыш (в процентах или абсолютных единицах)
    
    Возвращает:
        kelly_fraction: рекомендуемая доля капитала
    """
    if avg_loss == 0:
        return 0
    b = avg_win / avg_loss  # отношение выигрыша к проигрышу
    kelly = (win_rate * (b + 1) - 1) / b
    return max(0, kelly)  # не может быть отрицательной

# Пример использования
if __name__ == "__main__":
    # Загружаем исторические данные для нескольких активов
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
    all_data = {}
    for sym in symbols:
        data = fetch_historical_data(sym, '1d', limit=365)
        all_data[sym] = data['Close'].pct_change().dropna()
    
    returns_df = pd.DataFrame(all_data)
    
    # Минимально‑дисперсионный портфель
    weights, ret, vol = minimum_variance_portfolio(returns_df)
    print("Веса минимально‑дисперсионного портфеля:")
    for sym, w in zip(symbols, weights):
        print(f"  {sym}: {w:.2%}")
    print(f"Ожидаемая доходность: {ret:.2%}")
    print(f"Ожидаемая волатильность: {vol:.2%}")
    
    # Критерий Келли для одной стратегии
    win_rate = 0.6  # 60% выигрышных сделок
    avg_win = 0.05  # средний выигрыш 5%
    avg_loss = 0.02 # средний проигрыш 2%
    kelly = kelly_criterion(win_rate, avg_win, avg_loss)
    print(f"\nДробь Келли для стратегии: {kelly:.2%}")
```

Теперь агент может рекомендовать, как распределить капитал между BTC, ETH и SOL, чтобы минимизировать общий риск, и сколько ставить на каждую сделку по Келли.

---

🔧 *Шаг 4. Лимиты на просадку и автоматическое отключение*

Самый опасный враг трейдера — эмоциональная привязанность к убыточной стратегии. Агент должен отслеживать просадку и останавливаться при достижении лимитов.

Создадим файл `risk_monitor.py`:

```python
import pandas as pd
import time
from datetime import datetime

class DrawdownMonitor:
    """
    Мониторит просадку капитала и автоматически останавливает торговлю при превышении лимитов.
    """
    def __init__(self, initial_capital, max_portfolio_dd=0.20, max_daily_loss=0.05):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.peak_capital = initial_capital
        self.max_portfolio_dd = max_portfolio_dd
        self.max_daily_loss = max_daily_loss
        self.daily_start_capital = initial_capital
        self.trading_enabled = True
        self.history = []
        
    def update_capital(self, new_capital, timestamp=None):
        """
        Обновляет текущий капитал, пересчитывает просадку и проверяет лимиты.
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        self.current_capital = new_capital
        if new_capital > self.peak_capital:
            self.peak_capital = new_capital
        
        # Рассчитываем текущую просадку от пика
        drawdown = (self.peak_capital - self.current_capital) / self.peak_capital if self.peak_capital > 0 else 0
        
        # Рассчитываем дневную просадку
        daily_drawdown = (self.daily_start_capital - self.current_capital) / self.daily_start_capital if self.daily_start_capital > 0 else 0
        
        # Проверяем лимиты
        if drawdown >= self.max_portfolio_dd:
            self.trading_enabled = False
            reason = f"Превышена максимальная просадка портфеля: {drawdown:.1%} >= {self.max_portfolio_dd:.1%}"
        elif daily_drawdown >= self.max_daily_loss:
            self.trading_enabled = False
            reason = f"Превышен максимальный дневной убыток: {daily_drawdown:.1%} >= {self.max_daily_loss:.1%}"
        else:
            reason = None
        
        # Записываем в историю
        self.history.append({
            'timestamp': timestamp,
            'capital': new_capital,
            'peak': self.peak_capital,
            'drawdown': drawdown,
            'daily_drawdown': daily_drawdown,
            'trading_enabled': self.trading_enabled
        })
        
        return drawdown, daily_drawdown, reason
    
    def reset_daily(self):
        """
        Сбрасывает дневной отсчёт (вызывается в начале каждого торгового дня).
        """
        self.daily_start_capital = self.current_capital
    
    def get_status(self):
        """
        Возвращает текущий статус монитора.
        """
        return {
            'current_capital': self.current_capital,
            'peak_capital': self.peak_capital,
            'drawdown': (self.peak_capital - self.current_capital) / self.peak_capital if self.peak_capital > 0 else 0,
            'trading_enabled': self.trading_enabled,
            'history_count': len(self.history)
        }

# Пример использования
if __name__ == "__main__":
    monitor = DrawdownMonitor(initial_capital=10_000, max_portfolio_dd=0.20, max_daily_loss=0.05)
    
    # Симуляция изменения капитала
    capitals = [10_000, 10_500, 9_800, 9_200, 8_500, 9_000, 8_200]
    for i, cap in enumerate(capitals):
        drawdown, daily_dd, reason = monitor.update_capital(cap)
        print(f"Капитал: ${cap}, Просадка: {drawdown:.1%}, Дневная: {daily_dd:.1%}, Торговля: {'вкл' if monitor.trading_enabled else 'ВЫКЛ'}")
        if reason:
            print(f"  ⚠️ {reason}")
            break
```

Теперь агент будет следить за просадкой и автоматически отключать торговлю при достижении лимитов, предотвращая катастрофические потери.

---

🔧 *Шаг 5. Интеграция риск‑менеджмента в торговую стратегию*

Объединим все модули риск‑менеджмента с торговой стратегией. Модифицируем наш класс стратегии так, чтобы он рассчитывал размер позиции на основе ATR, устанавливал динамический стоп‑лосс и соблюдал лимиты просадки.

Создадим файл `strategy_with_risk.py`:

```python
import pandas as pd
import ta
from backtesting import Strategy, Backtest

class RiskManagedStrategy(Strategy):
    """
    Стратегия с встроенным риск‑менеджментом.
    """
    # Параметры риск‑менеджмента
    risk_per_trade = 0.02  # 2% риска на сделку
    atr_period = 14
    atr_multiplier = 1.5
    max_portfolio_dd = 0.20
    max_daily_loss = 0.05
    
    def init(self):
        # Рассчитываем ATR для всего временного ряда
        self.atr = self.I(ta.volatility.AverageTrueRange, self.data.High, self.data.Low, self.data.Close, window=self.atr_period)
        # Монитор просадки
        from risk_monitor import DrawdownMonitor
        self.monitor = DrawdownMonitor(10_000, self.max_portfolio_dd, self.max_daily_loss)
        
    def next(self):
        # Если торговля отключена из‑за превышения просадки — пропускаем
        if not self.monitor.trading_enabled:
            return
        
        # Пример торгового сигнала: RSI < 30 (перепроданность)
        if self.data.RSI[-1] < 30 and not self.position:
            entry_price = self.data.Close[-1]
            current_atr = self.atr[-1]
            
            # Рассчитываем размер позиции и стоп‑лосс
            from risk_position import calculate_position_size_by_atr
            capital = self.monitor.current_capital
            size, stop_loss = calculate_position_size_by_atr(
                capital, self.risk_per_trade, entry_price, current_atr, self.atr_multiplier
            )
            
            # Открываем позицию с рассчитанным размером
            self.buy(size=size, sl=stop_loss, tp=entry_price + 3*current_atr)
            
        # Обновляем капитал (в реальной торговле здесь нужно брать актуальный баланс)
        # Для демо просто используем начальный капитал
        self.monitor.update_capital(self.monitor.current_capital)

# Запуск бектеста
if __name__ == "__main__":
    from data_fetcher import fetch_historical_data
    
    data = fetch_historical_data('BTCUSDT', '1d', limit=365)
    bt = Backtest(data, RiskManagedStrategy, cash=10_000, commission=0.001)
    stats = bt.run()
    print(stats)
    
    # Выводим статус риск‑монитора
    print("\nСтатус риск‑монитора:")
    for key, value in bt.strategy.monitor.get_status().items():
        print(f"  {key}: {value}")
```

Теперь стратегия автоматически рассчитывает размер позиции на основе волатильности, устанавливает стоп‑лосс и следит за просадкой.

---

🔧 *Шаг 6. Интеграция с OpenClaw — агент‑риск‑менеджер*

Настроим агента OpenClaw для постоянного мониторинга рисков. Он будет:

1. Каждый час проверять текущую просадку портфеля.
2. При приближении к лимитам — отправлять предупреждение в Telegram.
3. При достижении лимитов — автоматически закрывать все позиции (если подключено к бирже).
4. Ежедневно пересчитывать оптимальное распределение капитала.

Создадим скрипт `agent_risk_manager.py`:

```python
import sys
sys.path.append('/root/.openclaw/workspace/trading')

from risk_monitor import DrawdownMonitor
from risk_portfolio import minimum_variance_portfolio
from data_fetcher import fetch_historical_data
from notify_telegram import send_telegram_message
import pandas as pd
import time
from datetime import datetime, timedelta

class RiskManagerAgent:
    def __init__(self, initial_capital=10_000):
        self.monitor = DrawdownMonitor(initial_capital)
        self.symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        self.positions = {}  # В реальности здесь будут текущие позиции с биржи
        
    def run_daily_allocation(self):
        """
        Ежедневный перерасчёт оптимального распределения капитала.
        """
        # Загружаем исторические данные
        returns_data = {}
        for sym in self.symbols:
            data = fetch_historical_data(sym, '1d', limit=90)
            returns_data[sym] = data['Close'].pct_change().dropna()
        
        returns_df = pd.DataFrame(returns_data)
        weights, _, _ = minimum_variance_portfolio(returns_df)
        
        # Формируем отчёт
        report = "📊 *Ежедневное распределение капитала*\n\n"
        for sym, w in zip(self.symbols, weights):
            report += f"• {sym}: {w:.1%}\n"
        
        send_telegram_message(report)
        return weights
    
    def run_hourly_check(self):
        """
        Ежечасная проверка просадки и рисков.
        """
        # В реальности здесь запрос текущего баланса с биржи
        # Для демо используем случайное изменение
        import random
        current_capital = self.monitor.current_capital * (1 + random.uniform(-0.02, 0.03))
        
        drawdown, daily_dd, reason = self.monitor.update_capital(current_capital)
        
        if reason:
            send_telegram_message(f"🚨 *Критическое превышение рисков!*\n{reason}\nТорговля остановлена.")
            # В реальности здесь закрытие всех позиций
        elif drawdown > 0.15:
            send_telegram_message(f"⚠️ *Высокая просадка:* {drawdown:.1%}\nРекомендуется снизить экспозицию.")
        elif drawdown > 0.10:
            send_telegram_message(f"📉 *Просадка:* {drawdown:.1%}\nМониторим ситуацию.")
    
    def run_continuous(self):
        """
        Бесконечный цикл мониторинга (запускается как сервис).
        """
        last_daily = datetime.now().date()
        
        while True:
            now = datetime.now()
            
            # Ежедневный перерасчёт в 00:00
            if now.date() != last_daily and now.hour == 0:
                self.run_daily_allocation()
                self.monitor.reset_daily()
                last_daily = now.date()
            
            # Ежечасная проверка
            self.run_hourly_check()
            
            # Ждём 1 час
            time.sleep(3600)

if __name__ == "__main__":
    agent = RiskManagerAgent(initial_capital=10_000)
    send_telegram_message("🤖 Агент риск‑менеджмента запущен.")
    agent.run_continuous()
```

Теперь у вас есть автономный агент, который круглосуточно следит за рисками и защищает ваш капитал.

---

✅ *Что мы получили?*

1. **Позиционный риск‑менеджмент** — расчёт размера позиции на основе ATR, динамические стоп‑лоссы.
2. **Портфельный риск‑менеджмент** — диверсификация по методу минимальной дисперсии, критерий Келли.
3. **Мониторинг просадки** — автоматическое отключение торговли при превышении лимитов.
4. **Интеграцию с OpenClaw** — агент‑риск‑менеджер, работающий 24/7, с уведомлениями в Telegram.
5. **Готовые скрипты** — `risk_position.py`, `risk_portfolio.py`, `risk_monitor.py`, `strategy_with_risk.py`, `agent_risk_manager.py`.

Теперь ваш агент не только ищет прибыльные возможности, но и защищает депозит от неконтролируемых потерь. В следующей статье мы добавим **реальный трейдинг через Binance API** — агент будет не только тестировать, но и реально торговать с соблюдением всех правил риск‑менеджмента.

---

📚 *Ресурсы*

- [Полный код из статьи](https://github.com/igorklov/llm-trading-guide/tree/main/day6)
- [Материалы по риск‑менеджменту от Van Tharp](https://www.vantharp.com/)
- [Modern Portfolio Theory на Wikipedia](https://en.wikipedia.org/wiki/Modern_portfolio_theory)

🚀 *Продолжение следует…*
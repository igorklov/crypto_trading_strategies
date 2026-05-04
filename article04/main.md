🚀 *СТАТЬЯ 4/12*  
*LLM‑агенты для трейдинга: практическое руководство на Python + OpenClaw*

📊 *Бектестинг торговых стратегий с помощью LLM‑агентов*

В предыдущих статьях мы научили агента наблюдать за рынком, вычислять индикаторы и отправлять уведомления. Сегодня переходим к самому важному этапу — **бектестингу торговых стратегий**. Прежде чем рисковать реальными средствами, мы протестируем стратегию на исторических данных, оценим её эффективность и оптимизируем параметры.

К концу статьи у вас будет:

✅ **Рабочий фреймворк для бектестинга** на Python с библиотекой `backtesting.py`  
✅ **Автоматизированный пайплайн** — от загрузки данных до расчёта метрик (Sharpe, макс. просадка, ROI)  
✅ **Визуализация результатов** — графики баланса, сделок, индикаторов  
✅ **Интеграция с OpenClaw** — агент сам запускает бектест и отправляет отчёт в Telegram  

---

🤖 *Зачем нужен бектестинг?*

Без проверки на истории любая стратегия — это гадание. Бектестинг позволяет:

1. **Проверить гипотезу** — работает ли стратегия в принципе.
2. **Оценить риск‑доходность** — через метрики Sharpe, просадку, коэффициент прибыльных сделок.
3. **Оптимизировать параметры** — подобрать наилучшие значения для индикаторов.
4. **Избежать переобучения** (overfitting) с помощью кросс‑валидации.

*Пример сценария:* Агент тестирует стратегию «RSI ниже 30 + пробой нижней линии Боллинджера → покупка, RSI выше 70 → продажа» на данных Bitcoin за 2023–2024 год. Результат: ROI 42%, Sharpe 1.2, максимальная просадка 15%. Вы получаете подробный отчёт с графиками и рекомендацией — стоит ли запускать стратегию в реальной торговле.

---

🔧 *Шаг 1. Установка необходимых библиотек*

Для бектестинга мы будем использовать легковесную, но мощную библиотеку `backtesting.py`. Она поддерживает свечные данные, индикаторы из `ta`, позволяет легко описывать стратегии и визуализировать результаты.

Убедитесь, что вы находитесь в виртуальном окружении проекта (или в директории `trading/`), затем выполните:

```bash
pip3 install backtesting pandas numpy matplotlib
```

*Примечание:* Если вы ещё не установили `ta` (для технических индикаторов), сделайте это сейчас:

```bash
pip3 install ta
```

---

🔧 *Шаг 2. Подготовка исторических данных*

Библиотеке нужны данные в формате `DataFrame` с колонками `Open`, `High`, `Low`, `Close`, `Volume`. Мы загрузим исторические свечи с Binance через их официальный API.

Создайте файл `backtest_data.py` в директории `trading/`:

```python
# backtest_data.py
import pandas as pd
from binance.client import Client
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Загружаем API‑ключи из .env
load_dotenv('.env')
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

client = Client(api_key, api_secret)

def fetch_historical_data(symbol='BTCUSDT', interval='1d', days=365):
    """
    Загружает исторические свечи с Binance.
    """
    # Вычисляем начальную дату
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Запрашиваем данные
    klines = client.get_historical_klines(
        symbol,
        interval,
        start_date.strftime('%d %b, %Y'),
        end_date.strftime('%d %b, %Y')
    )
    
    # Преобразуем в DataFrame
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'Open', 'High', 'Low', 'Close', 'Volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ])
    
    # Приводим типы
    numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    df[numeric_cols] = df[numeric_cols].astype(float)
    
    # Преобразуем timestamp в datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # Оставляем только нужные колонки
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
    
    # Сохраняем в CSV для повторного использования
    df.to_csv(f'data/{symbol}_{interval}_{days}days.csv')
    print(f'Загружено {len(df)} свечей. Данные сохранены в data/{symbol}_{interval}_{days}days.csv')
    
    return df

if __name__ == '__main__':
    # Создаём директорию data, если её нет
    os.makedirs('data', exist_ok=True)
    
    # Загружаем данные за последний год (дневные свечи)
    df = fetch_historical_data(symbol='BTCUSDT', interval='1d', days=365)
    print(df.head())
```

Запустите скрипт один раз, чтобы скачать данные:

```bash
python3 backtest_data.py
```

После успешного выполнения в папке `data/` появится файл `BTCUSDT_1d_365days.csv`.

---

🔧 *Шаг 3. Написание стратегии для бектестинга*

`backtesting.py` требует, чтобы стратегия была описана в виде класса с методами `init()` и `next()`. Мы реализуем простую стратегию на RSI и скользящих средних.

Создайте файл `strategy_rsi_sma.py`:

```python
# strategy_rsi_sma.py
import pandas as pd
from backtesting import Strategy
from backtesting.lib import SMA, RSI

class RsiSmaStrategy(Strategy):
    """
    Стратегия на основе RSI и двух SMA.
    Покупаем, когда RSI < 30 и SMA20 пересекает SMA50 снизу вверх.
    Продаём, когда RSI > 70 и SMA50 пересекает SMA20 снизу вверх.
    """
    rsi_period = 14
    rsi_overbought = 70
    rsi_oversold = 30
    sma_short = 20
    sma_long = 50
    
    def init(self):
        # Используем встроенные индикаторы из backtesting.lib
        self.rsi = self.I(RSI, self.data.Close, self.rsi_period)
        self.sma20 = self.I(SMA, self.data.Close, self.sma_short)
        self.sma50 = self.I(SMA, self.data.Close, self.sma_long)
        
    def next(self):
        # Если позиции нет и RSI ниже перепроданности, и SMA20 выше SMA50
        if not self.position and self.rsi[-1] < self.rsi_oversold and self.sma20[-1] > self.sma50[-1]:
            self.buy()
        # Если позиция есть и RSI выше перекупленности, и SMA50 выше SMA20
        elif self.position and self.rsi[-1] > self.rsi_overbought and self.sma50[-1] > self.sma20[-1]:
            self.position.close()
```

Это классическая трендовая стратегия, которая сочетает моментный индикатор (RSI) и трендовый фильтр (скользящие средние). Она покупает, когда рынок перепродан и начинается восходящий тренд, и продаёт при перекупленности и смене тренда вниз.

---

🔧 *Шаг 4. Запуск бектеста и анализ результатов*

Теперь создадим основной скрипт, который загрузит данные, прогонит стратегию и выведет метрики.

Файл `run_backtest.py`:

```python
# run_backtest.py
import pandas as pd
from backtesting import Backtest
from strategy_rsi_sma import RsiSmaStrategy
import matplotlib.pyplot as plt  # опционально, для визуализации

# Загружаем сохранённые данные
df = pd.read_csv('data/BTCUSDT_1d_365days.csv', index_col='timestamp', parse_dates=True)

# Инициализируем бектест
bt = Backtest(df, RsiSmaStrategy, cash=1000000, commission=.002)  # комиссия 0.2%

# Запускаем
stats = bt.run()
print(stats)

# Выводим основные метрики
print('\n=== ОСНОВНЫЕ МЕТРИКИ ===')
print(f'Количество сделок: {stats["# Trades"]}')
print(f'Прибыльность (ROI): {stats["Return [%]"]:.2f}%')
print(f'Коэффициент Шарпа: {stats["Sharpe Ratio"]:.2f}')
print(f'Максимальная просадка: {stats["Max. Drawdown [%]"]:.2f}%')
print(f'Процент прибыльных сделок: {stats["Win Rate [%]"]:.2f}%')

# Визуализируем результаты (опционально)
bt.plot()
plt.show()
```

Запустите бектест:

```bash
python3 run_backtest.py
```

Вы увидите в терминале таблицу со всеми метриками, а также откроется окно с графиком, на котором отображены:

- Цена и индикаторы
- Сделки (зелёные маркеры — покупки, красные — продажи)
- Кривую баланса
- Просадку

*Пример вывода (цифры условные):*

```
Количество сделок: 24
Прибыльность (ROI): 42.15%
Коэффициент Шарпа: 1.23
Максимальная просадка: -14.78%
Процент прибыльных сделок: 66.67%
```

---

🔧 *Шаг 5. Оптимизация параметров стратегии*

Вместо того чтобы вручную подбирать параметры RSI и SMA, поручим это библиотеке. `backtesting.py` имеет встроенную функцию `optimize()`, которая перебирает заданные диапазоны и находит комбинацию с наилучшей метрикой.

Добавим в `run_backtest.py` блок оптимизации (или создайте отдельный файл `run_backtest_optimize.py`):

```python
# Оптимизация параметров
optimized_stats = bt.optimize(
    rsi_period=range(10, 25, 2),
    rsi_overbought=range(65, 80, 5),
    rsi_oversold=range(20, 35, 5),
    sma_short=range(10, 30, 5),
    sma_long=range(40, 70, 10),
    maximize='Sharpe Ratio',  # максимизируем коэффициент Шарпа
    max_tries=100             # ограничиваем количество попыток
)

print('\n=== ОПТИМИЗИРОВАННЫЕ ПАРАМЕТРЫ ===')
print(f'RSI период: {optimized_stats._strategy.rsi_period}')
print(f'RSI overbought: {optimized_stats._strategy.rsi_overbought}')
print(f'RSI oversold: {optimized_stats._strategy.rsi_oversold}')
print(f'SMA короткая: {optimized_stats._strategy.sma_short}')
print(f'SMA длинная: {optimized_stats._strategy.sma_long}')
print(f'Лучший Sharpe Ratio: {optimized_stats["Sharpe Ratio"]:.2f}')

# Запускаем бектест с оптимизированными параметрами
params = {
    'rsi_period': optimized_stats._strategy.rsi_period,
    'rsi_overbought': optimized_stats._strategy.rsi_overbought,
    'rsi_oversold': optimized_stats._strategy.rsi_oversold,
    'sma_short': optimized_stats._strategy.sma_short,
    'sma_long': optimized_stats._strategy.sma_long
}
final_stats = bt.run(**params)
print('\n=== РЕЗУЛЬТАТЫ ПОСЛЕ ОПТИМИЗАЦИИ ===')
print(final_stats)
```

Запустите скрипт снова — он переберёт сотни комбинаций и выберет ту, которая даёт наивысший Sharpe Ratio. *Внимание:* оптимизация может занять несколько минут в зависимости от диапазонов.

---

🔧 *Шаг 6. Интеграция с OpenClaw (skill для автоматического бектестинга)*

Теперь превратим наш бектестинг в автономный skill OpenClaw, который будет запускаться по расписанию (например, раз в неделю) и отправлять отчёт в Telegram.

Создайте директорию для skill, если её ещё нет:

```bash
mkdir -p ~/.openclaw/workspace/skills/backtesting
cd ~/.openclaw/workspace/skills/backtesting
```

Создайте файл `SKILL.md` с описанием skill (как в статье №3). А также основные скрипты:

1. `backtest_skill.py` — основной скрипт skill, который запускает бектест и формирует отчёт.
2. `telegram_report.py` — отправка отчёта в Telegram.
3. `visualize.py` — генерация графиков для отчёта.

*Пример `backtest_skill.py`:*

```python
# backtest_skill.py
import pandas as pd
from backtesting import Backtest
from strategy_rsi_sma import RsiSmaStrategy
from telegram_report import send_report
from visualize import create_report_chart
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_backtest_skill():
    """
    Основная функция skill: запускает бектест и отправляет отчёт.
    """
    try:
        # Загружаем данные (можно брать из кэша или скачивать заново)
        df = pd.read_csv('data/BTCUSDT_1d_365days.csv', 
                         index_col='timestamp', parse_dates=True)
        
        # Запускаем бектест
        bt = Backtest(df, RsiSmaStrategy, cash=10000, commission=.002)
        stats = bt.run()
        
        # Генерируем график
        chart_path = create_report_chart(bt, stats)
        
        # Формируем текстовый отчёт
        report = f"""
📊 *Отчёт по бектестингу стратегии RSI+SMA*

• **Символ:** BTC/USDT
• **Период:** {len(df)} дней (дневные свечи)
• **Количество сделок:** {stats['# Trades']}
• **Общая доходность:** {stats['Return [%]']:.2f}%
• **Коэффициент Шарпа:** {stats['Sharpe Ratio']:.2f}
• **Макс. просадка:** {stats['Max. Drawdown [%]']:.2f}%
• **Процент прибыльных сделок:** {stats['Win Rate [%]']:.2f}%

*Рекомендация:* {'✅ Стратегия показывает стабильную прибыль' if stats['Sharpe Ratio'] > 1 else '⚠️ Требует доработки'}.
"""
        
        # Отправляем в Telegram
        send_report(report, chart_path)
        logger.info('Отчёт успешно отправлен.')
        
    except Exception as e:
        logger.error(f'Ошибка при выполнении бектеста: {e}')
        # Можно отправить уведомление об ошибке

if __name__ == '__main__':
    run_backtest_skill()
```

Остальные скрипты (`telegram_report.py`, `visualize.py`) вы можете взять из статьи №3 и адаптировать.

---

🔧 *Шаг 7. Настройка регулярного запуска через systemd/cron*

Чтобы skill запускался автоматически, добавим его в systemd (как в статье №2) или в cron OpenClaw.

**Вариант 1: systemd‑служба**

Создайте файл `/etc/systemd/system/backtest-weekly.service`:

```ini
[Unit]
Description=Weekly backtesting of trading strategies
After=network.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/root/.openclaw/workspace/skills/backtesting
ExecStart=/usr/bin/python3 backtest_skill.py
EnvironmentFile=/root/.openclaw/workspace/trading/.env
```

И таймер `/etc/systemd/system/backtest-weekly.timer`:

```ini
[Unit]
Description=Run backtest every Monday at 08:00

[Timer]
OnCalendar=Mon *-*-* 08:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Активируйте:

```bash
sudo systemctl enable backtest-weekly.timer
sudo systemctl start backtest-weekly.timer
```

**Вариант 2: cron OpenClaw**

Используйте встроенный планировщик OpenClaw (см. статью №2), чтобы запускать skill раз в неделю с отправкой отчёта в Telegram.

---

🎯 *Что дальше?*

Вы создали полноценный фреймворк для бектестирования торговых стратегий с интеграцией в OpenClaw. Теперь вы можете:

1. **Тестировать другие индикаторы** — MACD, Bollinger Bands, Ichimoku и т.д.
2. **Добавлять фильтры** — объём, волатильность, фундаментальные данные.
3. **Реализовать мультисимвольный бектестинг** — одновременно на нескольких парах.
4. **Внедрить машинное обучение** — использовать LLM для генерации и оптимизации стратегий.

В следующей статье мы перейдём к **реальному трейдингу** — как подключить агента к бирже, управлять рисками и автоматически исполнять сделки.

---

📁 *Исходный код*

Все файлы, созданные в этой статье, доступны в репозитории:

- `backtest_data.py` – загрузка исторических данных с Binance
- `strategy_rsi_sma.py` – описание стратегии RSI + SMA
- `run_backtest.py` – запуск базового бектеста
- `run_backtest_optimize.py` – бектест с оптимизацией параметров
- `backtest_skill.py` – skill для OpenClaw
- `telegram_report.py` и `visualize.py` – вспомогательные скрипты

*Не забудьте:* Всегда проверяйте стратегию на новых данных (out‑of‑sample) перед запуском в реальной торговле. Бектестинг — необходимый, но не достаточный этап.

Удачи в тестировании! 🚀
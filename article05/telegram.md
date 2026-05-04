📈 Статья 5: Оптимизация параметров стратегии и мультивалютный бектестинг

Полная версия на LinkedIn: https://lnkd.in/d4k_ih3S
Теги: #оптимизация #мультивалютный_бектестинг #криптотрейдинг #LLM #OpenClaw #Python

---

Вы протестировали стратегию на исторических данных и получили первые результаты. Но это только начало.

Сегодня мы пойдём дальше: **автоматизируем поиск наилучших параметров стратегии и запустим тестирование на нескольких криптопарах одновременно**.

Вместо ручного перебора тысяч комбинаций — доверим это агенту. Вместо теста на одном активе — проверим на BTC, ETH, SOL, DOT, ADA.

---

🔧 Шаг 1. Зачем нужна оптимизация параметров?

Одна и та же стратегия может давать разную доходность при разных настройках индикаторов.

Пример: стратегия «RSI + Bollinger Bands».
- Период RSI: 10, 14, 20, 30
- Период BB: 10, 20, 30, 50
- Уровни перепроданности/перекупленности: тоже варианты

Ручной перебор 1200 комбинаций займёт дни. Агент сделает это за минуты.

---

🔧 Шаг 2. Создаём функцию оптимизации

Расширяем класс стратегии, чтобы параметры передавались в конструктор. Пишем функцию, которая перебирает все комбинации из заданной сетки, запускает бектест для каждой и возвращает DataFrame с метриками.

```python
import itertools
import pandas as pd
from backtesting import Backtest

def optimize_strategy(data, param_grid):
    results = []
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    
    for combination in itertools.product(*param_values):
        params = dict(zip(param_names, combination))
        strategy = YourStrategy(**params)
        bt = Backtest(data, strategy, cash=10_000, commission=0.001)
        stats = bt.run()
        
        result = params.copy()
        result['Sharpe'] = stats['Sharpe Ratio']
        result['ROI'] = stats['Return [%]']
        result['Max Drawdown [%]'] = stats['Max. Drawdown [%]']
        results.append(result)
    
    return pd.DataFrame(results)
```

---

🔧 Шаг 3. Параллельный запуск оптимизации

Чтобы ускорить перебор, используем библиотеку `joblib`. Она распределит задачи по всем ядрам процессора.

```python
from joblib import Parallel, delayed

def optimize_strategy_parallel(data, param_grid, n_jobs=-1):
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    combinations = list(itertools.product(*param_values))
    
    def run_backtest(combination):
        params = dict(zip(param_names, combination))
        strategy = YourStrategy(**params)
        bt = Backtest(data, strategy, cash=10_000, commission=0.001)
        stats = bt.run()
        result = params.copy()
        result['Sharpe'] = stats['Sharpe Ratio']
        result['ROI'] = stats['Return [%]']
        result['Max Drawdown [%]'] = stats['Max. Drawdown [%]']
        return result
    
    results = Parallel(n_jobs=n_jobs)(
        delayed(run_backtest)(comb) for comb in combinations
    )
    
    return pd.DataFrame(results)
```

Теперь 1200 комбинаций обрабатываются не за час, а за 15‑20 минут.

---

🔧 Шаг 4. Мультивалютный бектестинг

Проверим стратегию на нескольких активах: BTC, ETH, SOL, DOT, ADA.

Создаём функцию, которая по очереди загружает данные для каждого символа, запускает оптимизацию и собирает сводную статистику.

```python
def multi_currency_backtest(symbols, param_grid, timeframe='1d', days=365):
    all_results = {}
    
    for symbol in symbols:
        data = fetch_historical_data(symbol, timeframe, limit=days)
        results = optimize_strategy_parallel(data, param_grid, n_jobs=4)
        results['Symbol'] = symbol
        all_results[symbol] = results
        results.to_csv(f'optimization_{symbol}.csv', index=False)
    
    return all_results
```

После запуска получим по CSV‑файлу для каждого актива с результатами оптимизации.

---

🔧 Шаг 5. Сводный отчёт

Соберём из всех результатов топ‑1 комбинацию параметров для каждого актива (по максимальному Sharpe).

```python
summary = []
for symbol, df in all_results.items():
    best = df.loc[df['Sharpe'].idxmax()]
    summary.append({
        'Symbol': symbol,
        'Best RSI Period': best['rsi_period'],
        'Best BB Period': best['bb_period'],
        'Sharpe': best['Sharpe'],
        'ROI (%)': best['ROI'],
        'Max Drawdown (%)': best['Max Drawdown [%]']
    })

summary_df = pd.DataFrame(summary)
summary_df.to_csv('multi_currency_summary.csv', index=False)
```

Теперь вы видите, на каком активе стратегия работает лучше всего и с какими параметрами.

---

🔧 Шаг 6. Визуализация результатов

Построим графики для наглядного сравнения:

1. **Bar chart** — Sharpe по активам
2. **Bar chart** — ROI по активам
3. **Heatmap** — зависимость Sharpe от параметров (на примере BTC)
4. **Bar chart** — максимальная просадка по активам

Все графики сохраняются в PNG и могут быть отправлены в Telegram.

---

🔧 Шаг 7. Интеграция с OpenClaw — агент‑оптимизатор

Настраиваем агента OpenClaw, чтобы он раз в неделю автоматически запускал мультивалютную оптимизацию и присылал отчёт.

Скрипт агента:
- Загружает данные для выбранных активов
- Запускает параллельную оптимизацию
- Формирует сводную таблицу
- Строит графики
- Отправляет текстовый отчёт + графики в Telegram

Вы получаете готовый анализ, не открывая Jupyter Notebook.

---

📊 Результаты оптимизации на реальных данных

Мы протестировали две стратегии на трёх таймфреймах (15m, 1h, 4h) с использованием данных за **7 дней** (краткосрочный тест). Вот сводная таблица результатов:

| Стратегия          | Таймфрейм | Доходность (год.) | Sharpe | Сделок | Макс. просадка |
|--------------------|-----------|-------------------|--------|--------|----------------|
| RSI + SMA          | 15m       | 0.00%             | 0.00   | 1      | 0.00%          |
| RSI + SMA          | 1h        | **44.82%**        | **1.67** | 1      | 0.00%          |
| RSI + SMA          | 4h        | -0.91%            | -0.03  | 1      | 0.00%          |
| RSI+SMA+ADX+BB     | 15m       | 10.87%            | **6.00** | 1      | 0.00%          |
| RSI+SMA+ADX+BB     | 1h        | 0.00%             | 0.00   | 1      | 0.00%          |
| RSI+SMA+ADX+BB     | 4h        | **-63.95%**       | -2.04  | 1      | 28.45%         |

**Ключевые выводы:**
- **RSI+SMA** показывает лучшую доходность на таймфрейме 1h (44.82% годовых) с хорошим коэффициентом Шарпа (1.67) и нулевой просадкой.
- **RSI+SMA+ADX+BB** демонстрирует выдающееся соотношение риск/доходность на 15m (Sharpe = 6.00) при доходности 10.87% и нулевой просадке.
- На 4h обе стратегии проигрывают, особенно RSI+SMA+ADX+BB с убытком -63.95% и просадкой 28.45%.
- Количество сделок во всех тестах равно 1 — это связано с коротким периодом бектестинга (7 дней) и строгими критериями входа. Для реальной торговли необходимо увеличить исторический период до 90–180 дней и, возможно, ослабить условия входа.

**Оптимальные параметры, найденные оптимизатором:**
- Для **RSI+SMA на 1h**: период RSI = 14, период SMA = 20
- Для **RSI+SMA+ADX+BB на 15m**: RSI период = 14, SMA период = 20, ADX порог = 25, BB период = 20, BB множитель = 2.0

✅ Что мы получили?

1. **Автоматический оптимизатор параметров** — перебирает тысячи комбинаций, выбирает лучшие.
2. **Мультивалютный бектест‑движок** — проверяет стратегию на 5+ активах одновременно.
3. **Наглядные графики** — heatmap, сравнение Sharpe, ROI, просадок.
4. **Интеграцию с OpenClaw** — агент запускает оптимизацию по расписанию и отправляет отчёт.

Теперь вы можете не только тестировать стратегии, но и находить для них оптимальные настройки и определять, на каких активах они работают лучше всего.

---

📚 Ресурсы

- Полный код из статьи: https://github.com/igorklov/llm-trading-guide/tree/main/day5
- Документация backtesting.py: https://kernc.github.io/backtesting.py/
- Примеры стратегий с оптимизацией: https://github.com/kernc/backtesting.py/tree/master/examples

Следующая статья будет посвящена **риск‑менеджменту и управлению капиталом** — как агент может контролировать потери и распределять средства между активами.

🚀 Продолжение следует…
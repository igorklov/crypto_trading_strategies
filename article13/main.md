# Статья 13: Финальная архитектура — объединение спотовой и фьючерсной торговли в единую LLM-систему

**Дата:** 26 апреля 2026
**Серия:** LLM-агенты для криптотрейдинга (практическое руководство на Python)

---

## Введение

Это финальная статья цикла. За 12 предыдущих статей мы прошли путь от простого скрипта, подключающегося к Binance API, до многослойной распределённой торговой системы на LLM-агентах.

**Что построили:**
- Агент-наблюдатель с мониторингом цен
- Технические индикаторы (RSI, SMA, MACD, Bollinger Bands, ADX)
- Уведомления через Telegram-бота
- Бектестинг с оптимизацией параметров
- Multi-валютный бектестинг на нескольких таймфреймах
- Риск-менеджмент и управление капиталом
- Масштабирование через мультипроцессинг с базой данных (`trading.db`)
- Фундаментальный анализ через LLM (Playwright + Gemini)
- Uptime-мониторинг (Docker, Grafana, systemd)
- Деплой на облачный сервер 24/7

Сегодня мы объединяем это в единую архитектуру, которая поддерживает **параллельную торговлю на споте и фьючерсах**.

---

## 1. Recap: архитектура спотовой системы

```
┌──────────────────────────────────────────────────┐
│                     main.py                       │
│   (оркестратор — запускает воркеры в процессах)   │
└──────────┬───────────────────────────┬───────────┘
           │                           │
    ┌──────▼─────────┐      ┌─────────▼────────┐
    │  WorkerPool     │      │  TelegramNotifier │
    │  (процессы)     │      │  (уведомления)    │
    └──────┬─────────┘      └──────────────────┘
           │
    ┌──────┴──────────────────────────────────────┐
    │  Worker (×N — по одному на пару)             │
    │  ┌──────────────┐  ┌──────────────────────┐  │
    │  │ IndicatorEngine │  │ FundamentalEngine    │  │
    │  │ (RSI, ADX, BB,  │  │ (Playwright + Gemini) │  │
    │  │  SMA)          │  │ → только для BTC    │  │
    │  └──────┬───────┘  └─────────┬────────────┘  │
    │         │                    │               │
    │         ▼                    ▼               │
    │  ┌───────────────────────────────────────┐   │
    │  │         Комбинатор сигналов            │   │
    │  │  (ADX gate ⇒ RSI + BB + SMA ⇒ сигнал) │   │
    │  └───────────────┬───────────────────────┘   │
    │                  ▼                           │
    │  ┌───────────────────────────────────────┐   │
    │  │   BinanceTrader (спот)                 │   │
    │  │   → demo или live                     │   │
    │  │   → trade_fraction, trailing stop, TP │   │
    │  └───────────────────────────────────────┘   │
    └─────────────────────────────────────────────┘
```

Каждый воркер — отдельный процесс, который:
1. Загружает klines с Binance
2. Вычисляет индикаторы
3. Проверяет FA (только BTC)
4. Комбинирует сигналы → решение buy/sell/hold
5. Размещает ордер (спот, market или limit)
6. Сохраняет всё в SQLite
7. Ждёт следующую свечу

---

## 2. Фьючерсы: что меняется

Фьючерсная торговля кардинально отличается от спотовой:

| Аспект | Спот | Фьючерс |
|:-------|:-----|:---------|
| Что покупаем | Актив | Контракт |
| Плечо (leverage) | 1× (нет) | 1× — 125× |
| Короткие продажи | ❌ | ✅ (short) |
| Маржа | Вся стоимость | Процент (начальная маржа) |
| Ликвидация | Нет | Есть (при падении маржи ниже поддерживающей) |
| Комиссия taker | 0.1% | 0.04% |
| Комиссия maker | 0.1% | 0.02% |

**Ключевые изменения в коде:**

1. Добавляется **фьючерсный модуль** (`futures_trader.py`), который параллельно спотовому анализирует те же пары
2. Сигналы технического анализа и FA — одинаковые для спота и фьючерсов
3. Разное: размер позиции (с учётом плеча), тип ордера, риск-менеджмент (ликвидация)
4. Спот-сигналы идут в спотовый трейдер, фьючерс-сигналы — во фьючерсный

Логика разделения сигналов:

```
Сигнал buy:
  → Спот: купить актив на USDT (trade_fraction от баланса)
  → Фьючерс: открыть LONG с плечом X (margin_fraction от маржи)

Сигнал sell:
  → Спот: продать актив (только если есть в портфеле)
  → Фьючерс: открыть SHORT с плечом X (margin_fraction от маржи)
```

---

## 3. Получение тестовых API-ключей для Futures

**Этот шаг — самый важный перед запуском.** Ошибка с ключами может стоить реальных денег.

### 3.1. Где взять demo-ключи

Binance предоставляет отдельную тестовую среду для фьючерсов — **Binance Futures Testnet**.

**Пошаговая инструкция:**

**Шаг 1.** Откройте https://demo.binance.com

> ⚠️ **Важно:** веб-интерфейс тестнета переехал на `demo.binance.com`. API-эндпоинты остались на `testnet.binancefuture.com` — не путайте URL для входа и URL для API.

**Шаг 2.** Войдите через **GitHub** или **по e-mail**:
- GitHub — быстрее, не требует реального Binance-аккаунта
- E-mail — альтернативный вариант

**Шаг 3.** После входа: **Аккаунт (аватарка) → API Management** (или напрямую `https://demo.binance.com/en/my/settings/api-management`)

**Шаг 4.** Нажмите **«Generate API Key»**

Вы получите пару:
```
API Key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Secret Key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**⚠️ Скопируйте Secret Key сразу!** Он показывается только один раз.

**Шаг 5.** По умолчанию на тестовом счёте **$5000 USDT** виртуального баланса (пополняется автоматически). Проверить баланс: **Dashboard** → **Wallet**.

### 3.2. Как проверить, что ключи рабочие

Самый быстрый тест:

```python
import hashlib, hmac, time, requests

API_KEY = "ваш_api_key"
SECRET_KEY = "ваш_secret_key"

# Тест Ping (без авторизации)
r = requests.get("https://testnet.binancefuture.com/fapi/v1/ping")
print("Ping:", "OK" if r.status_code == 200 else "FAIL")

# Тест Account (с авторизацией)
timestamp = int(time.time() * 1000)
params = f"timestamp={timestamp}"
signature = hmac.new(SECRET_KEY.encode(), params.encode(), hashlib.sha256).hexdigest()

headers = {"X-MBX-APIKEY": API_KEY}
r = requests.get(
    f"https://testnet.binancefuture.com/fapi/v2/account?{params}&signature={signature}",
    headers=headers
)

if r.status_code == 200:
    data = r.json()
    print(f"✅ Успех! canTrade: {data.get('canTrade')}")
    for asset in data.get('assets', []):
        wallet = float(asset.get('walletBalance', 0))
        if wallet > 0:
            print(f"  {asset['asset']}: ${wallet}")
else:
    print(f"❌ Ошибка {r.status_code}: {r.json().get('msg')}")
```

Ожидаемый результат при успехе:
```
Ping: OK
✅ Успех! canTrade: True
  USDT: $5000.00
```

### 3.3. Отличие testnet от live ключей

| Признак | Testnet | Live |
|:--------|:--------|:-----|
| URL (REST) | `testnet.binancefuture.com` | `fapi.binance.com` |
| URL (веб-интерфейс) | `demo.binance.com` | `binance.com` |
| URL (WebSocket) | `stream.binancefuture.com` | `fstream.binance.com` |
| Баланс | $5000 виртуальных | Реальные деньги |
| Риск | Нулевой | Полный |
| Ключи | Генерируются на `demo.binance.com` | Генерируются в реальном UI |
| Плечо | Можно любое | Любое (зависит от баланса) |

**Важно:** live-ключи Binance Futures НЕЛЬЗЯ использовать с testnet URL, и наоборот. Если ключ подходит к testnet — это testnet-ключ. Если к live — live-ключ. Они не взаимозаменяемы.

---

## 4. Архитектура: спот + фьючерсы вместе

### 4.1. Структура файлов

```
trading/
├── multiprocessing/          # Основная система
│   ├── main.py               # Оркестратор
│   ├── worker.py             # Воркер (спот)
│   ├── futures_worker.py     # Фьючерсный воркер (НОВЫЙ)
│   ├── config.json           # Конфигурация
│   ├── database.py           # Работа с SQLite
│   ├── metrics.py            # P&L метрики
│   ├── process_manager.py    # Управление процессами
│   ├── dashboard.py          # Панель мониторинга
│   ├── binance_connector.py  # Подключение к Binance
│   ├── binance_trader.py     # Спотовый трейдер
│   ├── futures_trader.py     # Фьючерсный трейдер (НОВЫЙ)
│   ├── indicators.py         # Индикаторы
│   ├── notify_telegram.py    # Telegram уведомления
│   └── optimal_params.json   # Оптимальные параметры
├── analysis/
│   └── pnl_report.py         # P&L отчёт
└── data/
    └── trading.db            # Основная БД
```

### 4.2. Фьючерсный воркер: логика

Основное отличие `futures_worker.py` от `worker.py`:

```python
class FuturesWorker:
    """Фьючерсный воркер — открывает LONG/SHORT на основе сигналов."""

    def __init__(self, symbol, interval, config):
        self.symbol = symbol
        self.interval = interval
        self.leverage = config.get('leverage', 3)        # Плечо
        self.margin_fraction = config.get('margin_fraction', 0.1)  # 10% маржи на сделку
        self.hedge_mode = config.get('hedge_mode', False)          # Хедж-режим
        self.position_amt = 0.0  # Текущий размер позиции (>0 = long, <0 = short)
        self.liquidation_price = 0.0

    def _calculate_position_size(self, side, price):
        """Размер позиции с учётом плеча и маржи."""
        available_margin = self.client.get_balance('USDT')
        margin_to_use = available_margin * self.margin_fraction
        # Размер контракта = маржа × плечо
        contract_size = margin_to_use * self.leverage
        quantity = contract_size / price
        # Округляем до шага лота
        return self._round_step_size(quantity)

    def place_order(self, side, quantity, order_type='MARKET'):
        """Размещает фьючерсный ордер."""
        if side == 'BUY':
            # LONG
            return self.client.futures_create_order(
                symbol=self.symbol,
                side='BUY',
                type=order_type,
                quantity=quantity,
                positionSide='LONG'  # В one-way режиме можно не указывать
            )
        elif side == 'SELL':
            # SHORT
            return self.client.futures_create_order(
                symbol=self.symbol,
                side='SELL',
                type=order_type,
                quantity=quantity,
                positionSide='SHORT'
            )
```

### 4.3. Настройка в config.json

```json
{
  "demo": true,
  "futures_demo": true,
  "leverage": 3,
  "margin_fraction": 0.1,
  "futures_api_key": "ВАШ_FUTURES_TESTNET_KEY",
  "futures_secret_key": "ВАШ_FUTURES_TESTNET_SECRET",
  "symbols": {
    "BTCUSDT": { "interval": "15m", "spot": true, "futures": true },
    "ETHUSDT": { "interval": "15m", "spot": true, "futures": true }
  }
}
```

Параметр `margin_fraction: 0.1` означает, что на каждую сделку уходит только 10% от доступной маржи. При плече 3× это даёт эффективный рычаг 0.3× от баланса — консервативно.

---

## 5. Адаптация торговой стратегии под фьючерсы

### 5.1. Плечо и размер позиции

**Правило большого пальца:** никогда не используйте плечо больше, чем можете позволить себе потерять. Для LLM-системы:

| Уровень | Плечо | Маржа на сделку | Описание |
|:--------|:-----:|:----------------:|:---------|
| Консервативный | 2× | 5% | Тестирование, низкий риск |
| Умеренный | 3× | 10% | Рабочий режим |
| Агрессивный | 5× | 15% | Проверенные стратегии |
| Безрассудный | >10× | >20% | Фатально при просадке |

### 5.2. Типы сигналов для фьючерсов

Спотовая стратегия генерирует `buy` (купить) и `sell` (продать имеющееся). Для фьючерсов добавляется **short**:

```
Сигнал → buy:
  ТА: RSI < 20, цена у нижней BB, ADX > 25
  FA: нейтральный или позитивный сентимент
  Действие: LONG (купить контракт)

Сигнал → sell:
  ТА: RSI > 80, цена у верхней BB
  FA: нейтральный или негативный сентимент
  Действие: SHORT (продать контракт)

Сигнал → close_long:
  Достигнут take-profit, trailing stop или RSI вернулся к 50
  Действие: закрыть LONG

Сигнал → close_short:
  Достигнут take-profit, trailing stop или RSI вернулся к 50
  Действие: закрыть SHORT
```

### 5.3. Trailing stop для фьючерсов

Для фьючерсов trailing stop ещё важнее, чем для спота, из-за риска ликвидации:

```python
LIQUIDATION_BUFFER = 0.3  # 30% буфер до ликвидации
TRAILING_STOP = 0.05      # 5% от максимума/минимума

# Для LONG: цена ликвидации должна быть > entry * (1 - 1/leverage + buffer)
max_leverage = 1 / (1 - min(1 - liquidation_price / entry_price, 0.99))
safe_entry = entry_price > liquidation_price * (1 + LIQUIDATION_BUFFER)
```

---

## 6. Запуск: спот + фьючерсы вместе

### 6.1. Вариант 1: Два параллельных процесса

Самый простой способ — запустить два инстанса `main.py` с разными конфигами:

```bash
# Спот (как сейчас)
python main.py --config config_spot.json

# Фьючерсы
python main.py --config config_futures.json
```

Это надёжно и изолированно: если упадёт фьючерсный модуль, спотовый продолжит работать.

### 6.2. Вариант 2: Единый оркестратор (запускаем и спот- и фьючерс-воркеры)

В `main.py` добавляем запуск фьючерсных воркеров:

```python
def main():
    config = load_config()
    
    spot_workers = []
    futures_workers = []
    
    for symbol, params in config['symbols'].items():
        if params.get('spot', True):
            w = SpotWorker(symbol, params['interval'], config)
            spot_workers.append(Process(target=w.run))
        if params.get('futures', False):
            fw = FuturesWorker(symbol, params['interval'], config)
            futures_workers.append(Process(target=fw.run))
    
    all_workers = spot_workers + futures_workers
    for w in all_workers:
        w.start()
    
    for w in all_workers:
        w.join()
```

---

## 7. Безопасность и риски

### 🔴 Абсолютные правила для фьючерсов

1. **Никогда не запускайте live-фьючерсы без недели тестов на testnet**
2. **Никогда не используйте плечо выше 3× на старте**
3. **Всегда ставьте take-profit и stop-loss** — алгоритм может зависнуть
4. **Не ставьте margin_fraction > 0.2** (риск каскадных убытков)
5. **Отдельные API-ключи** для спота и фьючерсов (с разными правами)
6. **Лимитные ордера** вместо рыночных — снижают комиссию (maker 0.02% vs taker 0.04%)

### 🟡 Проверочный чек-лист перед live

- [ ] Testnet-ключи работают
- [ ] Баланс testnet = $5000 (или сколько зачислено)
- [ ] Спотовая система стабильно приносит прибыль >2 недель
- [ ] P&L реализованный > комиссий
- [ ] Trailing stop, take-profit, max hold настроены
- [ ] Telegram-уведомления приходят на каждый ордер
- [ ] Есть человек, готовый вмешаться вручную
- [ ] Риск на сделку ≤ 2% от депозита

---

## 8. Что дальше? Roadmap

Наш цикл из 13 статей подошёл к концу, но система продолжает эволюционировать:

**Краткосрочно (1–2 недели):**
- ✅ Спотовая торговля (работает с 19 апреля)
- ✅ P&L анализ (скрипт готов)
- ✅ Оптимизация стратегии (затянутые пороги)
- 🔄 Тестирование фьючерсов на testnet
- 🔄 Сравнение P&L: новая vs старая стратегия

**Среднесрочно (1 месяц):**
- Интеграция WebSocket для real-time цен (снижает задержку)
- Добавление ML-моделей для предсказания направления
- Grid-торговля на фьючерсах
- Telegram-бот для ручного управления (открыть/закрыть позицию голосом)

**Долгосрочно (3+ месяцев):**
- Multi-exchange (Bybit, OKX)
- Стратегии арбитража (спот vs фьючерсы)
- DAO-управление стратегией
- Полностью автономный AI-трейдер

---

## Заключение

За 13 статей мы прошли полный путь: от первого подключения к Binance API до многослойной распределённой торговой системы, способной одновременно торговать на споте и фьючерсах с LLM-анализом фундаментальных факторов.

**Что отличает эту систему:**
- Весь код — ваш, без чёрных ящиков
- LLM не предсказывает цены, а анализирует контекст (новости, сентимент)
- Модульная архитектура: можно отключить любой компонент
- Демо-режим для любой части системы
- Полная прозрачность через SQLite и P&L отчёты

**И главное:** это не законченный продукт, а **фреймворк**. Каждый может взять нашу архитектуру, заменить свои индикаторы, добавить свои источники данных, настроить риск-менеджмент под свой стиль — и построить свою идеальную торговую систему.

Удачи в трейдинге. Пусть ваши Long будут зелёными, а Short — точными. 🚀

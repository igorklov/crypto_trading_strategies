# День 9: Масштабирование агентов — управление множеством пар, базы данных и панели мониторинга

## Введение

Когда ваш первый агент‑наблюдатель успешно работает с одной‑двумя парами, возникает естественный вопрос: как управлять **десятками активов** одновременно? Как хранить историю сигналов, отслеживать производительность и оперативно реагировать на сбои? Масштабирование — это переход от единичного скрипта к **системе**, где каждый компонент выполняет свою роль, а вы сохраняете контроль над всей инфраструктурой.

В этой статье вы научитесь:

*   Организовывать **мультипроцессный мониторинг** нескольких торговых пар с помощью Python‑модуля `multiprocessing`.
*   Использовать **базу данных SQLite** для хранения исторических цен, индикаторов, сигналов и результатов торгов.
*   Создавать **панель мониторинга** на базе Grafana + Prometheus (или простой веб‑интерфейс на Flask) для визуализации метрик.
*   Автоматизировать **оркестрацию агентов** через systemd юниты и менеджер‑скрипт, который запускает, останавливает и перезагружает агентов по расписанию или в ответ на события.
*   Интегрировать **централизованное логирование и алертинг** — все логи пишутся в единое место, а важные события дублируются в Telegram.
*   **Тестировать** масштабированную систему на демо‑аккаунте Binance перед переходом на реальные средства.

**🎯 Цель:** построить отказоустойчивую, наблюдаемую и легко управляемую инфраструктуру для торговых агентов, способную работать 24/7 без вашего постоянного вмешательства.

## 1. Архитектура масштабированной системы

Прежде чем писать код, определимся с компонентами:

1.  **Агенты‑воркеры** — отдельные процессы (или потоки), каждый из которых мониторит одну или несколько торговых пар, вычисляет индикаторы и генерирует сигналы. Они не размещают ордера самостоятельно, а передают сигналы в центральный диспетчер.
2.  **Диспетчер (менеджер)** — центральный процесс, который получает сигналы от воркеров, принимает решение о размещении ордера (учитывая риск‑менеджмент и текущую позицию) и отправляет команды на исполнение.
3.  **База данных** — SQLite (для начала) или PostgreSQL (для production). Хранит:
    *   Исторические свечи (цена, объем, время)
    *   Значения индикаторов (RSI, MACD, SMA и т.д.)
    *   Сигналы (время, тип, сила)
    *   Ордера (ID, тип, цена, количество, статус)
    *   Состояние портфеля (баланс, эквити, просадка)
4.  **Панель мониторинга** — веб‑интерфейс или Grafana‑дашборд, отображающий:
    *   Текущие цены и индикаторы по всем парам
    *   Статус агентов (работают/остановлены)
    *   Историю сигналов и ордеров
    * *   Графики эквити и просадки
5.  **Оркестратор** — systemd службы + скрипт‑надсмотрщик, который перезапускает упавших агентов, обновляет конфигурацию на лету и отправляет уведомления о критических событиях.
6.  **Логирование и алертинг** — все компоненты пишут логи в единый файл (или syslog), а важные события (ошибки, значительные изменения цены, размещение ордеров) дублируются в Telegram.

Такая архитектура позволяет добавлять новые пары простым добавлением конфигурационной строки, а также легко заменять или обновлять отдельные компоненты без остановки всей системы.

## 2. Мультипроцессный мониторинг: запуск десятков воркеров

### 2.1 Зачем multiprocessing, а не multithreading?

GIL (Global Interpreter Lock) в Python ограничивает параллельное выполнение CPU‑bound операций в потоках. Поскольку мониторинг в основном состоит из ожидания сетевых ответов (I/O‑bound), потоки могли бы подойти, но для полной изоляции и устойчивости к падениям лучше использовать **процессы**. Каждый воркер работает в своём процессе — если он «упадёт», остальные продолжат работу.

### 2.2 Пример воркера

Создадим класс `Worker`, который будет запускаться как отдельный процесс и мониторить одну торговую пару.

```python
# worker.py
import time
import signal
import sys
from multiprocessing import Process, Queue
from binance_connector import BinanceClient
from indicators import calculate_rsi, calculate_sma
from database import save_candle, save_signal

class Worker(Process):
    def __init__(self, symbol, interval, config, signal_queue):
        super().__init__()
        self.symbol = symbol
        self.interval = interval
        self.config = config
        self.signal_queue = signal_queue  # очередь для отправки сигналов диспетчеру
        self.running = False
        
    def run(self):
        self.running = True
        client = BinanceClient(self.config['api_key'], self.config['api_secret'])
        
        while self.running:
            try:
                # Получаем последние свечи
                klines = client.get_klines(self.symbol, self.interval, limit=100)
                latest = klines[-1]
                
                # Сохраняем в базу
                save_candle(self.symbol, self.interval, latest)
                
                # Вычисляем индикаторы
                prices = [float(k[4]) for k in klines]  # цены закрытия
                rsi = calculate_rsi(prices, period=14)
                sma_short = calculate_sma(prices, period=20)
                sma_long = calculate_sma(prices, period=50)
                
                # Генерируем сигнал (упрощённо)
                signal = None
                if rsi[-1] < 30:
                    signal = {'type': 'buy', 'strength': 'strong', 'rsi': rsi[-1]}
                elif rsi[-1] > 70:
                    signal = {'type': 'sell', 'strength': 'strong', 'rsi': rsi[-1]}
                
                if signal:
                    signal['symbol'] = self.symbol
                    signal['timestamp'] = time.time()
                    self.signal_queue.put(signal)  # отправляем диспетчеру
                    save_signal(signal)            # сохраняем в базу
                
                # Ждём до следующей итерации (например, 60 секунд)
                time.sleep(60)
                
            except Exception as e:
                print(f"Worker {self.symbol} error: {e}")
                time.sleep(10)  # пауза перед повторной попыткой
    
    def stop(self):
        self.running = False
```

### 2.3 Менеджер процессов

Менеджер запускает, останавливает и перезапускает воркеров на основе конфигурации.

```python
# process_manager.py
import signal
import sys
from multiprocessing import Process, Queue
from worker import Worker

class ProcessManager:
    def __init__(self, config):
        self.config = config
        self.workers = {}
        self.signal_queue = Queue()
        
    def start_all(self):
        for symbol, params in self.config['symbols'].items():
            w = Worker(symbol, params['interval'], self.config, self.signal_queue)
            w.start()
            self.workers[symbol] = w
            print(f"Started worker for {symbol}")
    
    def stop_all(self):
        for symbol, w in self.workers.items():
            w.stop()
            w.join(timeout=5)
            print(f"Stopped worker for {symbol}")
    
    def restart(self, symbol):
        if symbol in self.workers:
            self.workers[symbol].stop()
            self.workers[symbol].join(timeout=5)
        w = Worker(symbol, self.config['symbols'][symbol]['interval'], 
                   self.config, self.signal_queue)
        w.start()
        self.workers[symbol] = w
        print(f"Restarted worker for {symbol}")
    
    def get_signal_queue(self):
        return self.signal_queue
```

Такой подход позволяет управлять десятками пар, при этом каждый воркер изолирован и не влияет на остальные.

## 3. База данных SQLite: храним историю и метрики

### 3.1 Схема базы данных

Создадим файл `database.py` с определением таблиц и функциями для работы с SQLite.

```python
# database.py
import sqlite3
import json
from datetime import datetime

DB_PATH = 'data/trading.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Таблица свечей
    c.execute('''
        CREATE TABLE IF NOT EXISTS candles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            open_time INTEGER NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            close_time INTEGER NOT NULL,
            UNIQUE(symbol, interval, open_time)
        )
    ''')
    
    # Таблица индикаторов
    c.execute('''
        CREATE TABLE IF NOT EXISTS indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            rsi REAL,
            sma_short REAL,
            sma_long REAL,
            macd REAL,
            macd_signal REAL,
            bb_upper REAL,
            bb_middle REAL,
            bb_lower REAL,
            UNIQUE(symbol, interval, timestamp)
        )
    ''')
    
    # Таблица сигналов
    c.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            signal_type TEXT NOT NULL,  # buy, sell, hold
            strength TEXT,              # weak, medium, strong
            timestamp INTEGER NOT NULL,
            rsi REAL,
            price REAL,
            processed INTEGER DEFAULT 0  # 0 = не обработан, 1 = отправлен в ордер, 2 = исполнен
        )
    ''')
    
    # Таблица ордеров
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,         # BUY, SELL
            type TEXT NOT NULL,         # MARKET, LIMIT, STOP_LOSS
            price REAL,
            quantity REAL NOT NULL,
            status TEXT NOT NULL,       # NEW, FILLED, CANCELED, REJECTED
            timestamp INTEGER NOT NULL,
            filled_price REAL,
            filled_quantity REAL,
            commission REAL,
            UNIQUE(order_id)
        )
    ''')
    
    # Таблица состояния портфеля (снимки на момент времени)
    c.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            total_balance REAL NOT NULL,
            available_balance REAL NOT NULL,
            locked_balance REAL NOT NULL,
            equity REAL NOT NULL,
            margin REAL,
            leverage REAL
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized")
```

### 3.2 Функции для сохранения и чтения данных

```python
# database.py (продолжение)
def save_candle(symbol, interval, candle_data):
    """Сохраняет одну свечу."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''
            INSERT OR IGNORE INTO candles 
            (symbol, interval, open_time, open, high, low, close, volume, close_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, interval, candle_data[0], float(candle_data[1]), 
              float(candle_data[2]), float(candle_data[3]), float(candle_data[4]),
              float(candle_data[5]), candle_data[6]))
        conn.commit()
    except Exception as e:
        print(f"Error saving candle: {e}")
    finally:
        conn.close()

def save_signal(signal):
    """Сохраняет сигнал."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO signals 
            (symbol, signal_type, strength, timestamp, rsi, price)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (signal['symbol'], signal['type'], signal.get('strength', 'medium'),
              signal['timestamp'], signal.get('rsi'), signal.get('price')))
        conn.commit()
    except Exception as e:
        print(f"Error saving signal: {e}")
    finally:
        conn.close()

def get_latest_candles(symbol, interval, limit=100):
    """Возвращает последние свечи."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT * FROM candles 
        WHERE symbol=? AND interval=?
        ORDER BY open_time DESC LIMIT ?
    ''', (symbol, interval, limit))
    rows = c.fetchall()
    conn.close()
    return rows

# ... аналогичные функции для других таблиц
```

База данных даёт возможность анализировать историю, строить графики и проводить пост‑анализ стратегий.

## 4. Панель мониторинга: Grafana + Prometheus или простой Flask‑интерфейс

### 4.1 Вариант A: Prometheus метрики + Grafana (продвинутый)

Prometheus — система сбора метрик, Grafana — инструмент для их визуализации. Наш агент будет экспортировать метрики в формате, понятном Prometheus.

Установим `prometheus_client`:

```bash
pip3 install prometheus_client
```

Добавим в агента код для экспорта метрик:

```python
# metrics.py
from prometheus_client import start_http_server, Gauge, Counter

# Создаём метрики
PRICE_GAUGE = Gauge('crypto_price', 'Current price', ['symbol'])
RSI_GAUGE = Gauge('crypto_rsi', 'RSI value', ['symbol'])
SIGNAL_COUNTER = Counter('crypto_signals_total', 'Total signals generated', ['symbol', 'type'])

def update_price(symbol, price):
    PRICE_GAUGE.labels(symbol=symbol).set(price)

def update_rsi(symbol, rsi):
    RSI_GAUGE.labels(symbol=symbol).set(rsi)

def increment_signal(symbol, signal_type):
    SIGNAL_COUNTER.labels(symbol=symbol, type=signal_type).inc()

# Запускаем HTTP‑сервер для Prometheus (на порту 8000)
start_http_server(8000)
```

Prometheus будет опрашивать `http://localhost:8000/metrics` и забирать метрики. В Grafana вы создадите дашборд с графиками цен, RSI, количеством сигналов и т.д.

### 4.2 Вариант B: Простой веб‑интерфейс на Flask (быстрый старт)

Если не хотите возиться с Prometheus, можно сделать лёгкий Flask‑сервер, который отдаёт HTML‑страницу с таблицей текущих цен и статусом агентов.

```python
# dashboard.py
from flask import Flask, render_template, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_PATH = 'data/trading.db'

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/prices')
def get_prices():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT symbol, close, MAX(open_time) 
        FROM candles 
        GROUP BY symbol
    ''')
    rows = c.fetchall()
    conn.close()
    prices = [{'symbol': r[0], 'price': r[1], 'time': r[2]} for r in rows]
    return jsonify(prices)

@app.route('/api/signals')
def get_signals():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT symbol, signal_type, strength, timestamp 
        FROM signals 
        ORDER BY timestamp DESC LIMIT 20
    ''')
    rows = c.fetchall()
    conn.close()
    signals = [{'symbol': r[0], 'type': r[1], 'strength': r[2], 'time': r[3]} for r in rows]
    return jsonify(signals)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

Запустив этот сервер, вы откроете в браузере `http://ваш‑сервер:5000` и увидите дашборд.

## 5. Оркестрация: systemd службы и скрипт‑надсмотрщик

### 5.1 Создаём systemd службы для каждого компонента

Мы уже создавали службы для отдельных агентов в Дне 7. Теперь сделаем службы для менеджера процессов, диспетчера и панели мониторинга.

Пример службы для менеджера процессов (`trading-manager.service`):

```ini
[Unit]
Description=Trading Process Manager
After=network.target
Wants=network.target

[Service]
Type=simple
User=openclaw
WorkingDirectory=/root/.openclaw/workspace/skills/binance-trading/scripts
ExecStart=/usr/bin/python3 /root/.openclaw/workspace/skills/binance-trading/scripts/process_manager.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Службы для воркеров можно не создавать отдельно — их запускает менеджер. Но можно сделать одну службу, которая запускает менеджер, а тот уже поднимает воркеров.

### 5.2 Скрипт‑надсмотрщик (watchdog)

Надсмотрщик периодически проверяет, работают ли все компоненты, и перезапускает упавшие. Он же может обновлять конфигурацию на лету (например, добавить новую пару без остановки всей системы).

```python
# watchdog.py
import time
import subprocess
import psutil
from notify_telegram import TelegramNotifier

class Watchdog:
    def __init__(self):
        self.notifier = TelegramNotifier()
        self.services = [
            'trading-manager.service',
            'trading-agent-monitor.service',
            'dashboard.service'  # если есть
        ]
    
    def check_service(self, service_name):
        try:
            result = subprocess.run(['systemctl', 'is-active', service_name], 
                                   capture_output=True, text=True)
            return result.stdout.strip() == 'active'
        except Exception as e:
            print(f"Error checking {service_name}: {e}")
            return False
    
    def restart_service(self, service_name):
        try:
            subprocess.run(['systemctl', 'restart', service_name], check=True)
            self.notifier.send_message(f"🔄 Restarted {service_name}")
            return True
        except Exception as e:
            self.notifier.send_message(f"❌ Failed to restart {service_name}: {e}")
            return False
    
    def run(self):
        while True:
            for service in self.services:
                if not self.check_service(service):
                    print(f"Service {service} is down, restarting...")
                    self.restart_service(service)
            time.sleep(60)  # проверяем каждую минуту

if __name__ == '__main__':
    wd = Watchdog()
    wd.run()
```

Запускаем надсмотрщик как отдельную службу (`watchdog.service`), и он будет поддерживать систему в рабочем состоянии 24/7.

## 6. Интеграция с OpenClaw: skill для масштабирования

Соберём все компоненты в единый skill `binance‑trading` (который у нас уже есть) и добавим новые файлы:

```
skills/binance‑trading/
├── scripts/
│   ├── worker.py
│   ├── process_manager.py
│   ├── database.py
│   ├── metrics.py
│   ├── dashboard.py
│   ├── watchdog.py
│   └── ...
├── assets/
│   ├── .env
│   └── config.yaml   # общая конфигурация
└── SKILL.md
```

Обновим `SKILL.md` с описанием новых скриптов и инструкцией по запуску масштабированной системы.

## 7. Тестирование и развертывание

### 7.1 Поэтапный запуск

1.  **Инициализируйте базу данных:** `python3 database.py` (функция `init_db()`).
2.  **Запустите менеджер процессов:** `python3 process_manager.py`.
3.  **Запустите панель мониторинга:** `python3 dashboard.py`.
4.  **Запустите надсмотрщик:** `python3 watchdog.py`.
5.  **Проверьте логи:** `tail -f /var/log/syslog` или файлы в `logs/`.

### 7.2 Переход на production

*   Замените SQLite на PostgreSQL для большей надёжности и производительности.
*   Используйте Docker‑контейнеры для изоляции компонентов.
*   Настройте бэкапы базы данных.
*   Добавьте SSL‑сертификаты для веб‑интерфейса.
*   Настройте более тонкие алерты (например, через PagerDuty или Opsgenie).

## Заключение

Масштабирование превращает набор разрозненных скриптов в профессиональную торговую инфраструктуру. Вы получили инструменты для управления десятками пар, хранения истории, визуализации метрик и автоматического восстановления после сбоев.

**Что дальше?** В следующих статьях мы рассмотрим:

*   **День 10:** Развёртывание на облачном сервере (VPS) и настройка резервного копирования.
*   **День 11:** Интеграция с внешними источниками данных (новости, социальные сети, on‑chain метрики).
*   **День 12:** Создание собственного торгового API и бота для Telegram.

Все скрипты из этой статьи доступны в [репозитории GitHub](ссылка). Вопросы и предложения оставляйте в комментариях или в Telegram‑канале @crypto_logic_pro.

**Торгуйте ответственно. Удачи!**
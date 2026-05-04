# Подключение к Binance API и создание первого агента‑наблюдателя

*24 марта 2026* | **Серия:** LLM‑агенты для трейдинга: практическое руководство на Python + OpenClaw | **Статья 2 из 12**

---

## Введение

В первой статье мы установили и настроили OpenClaw — платформу для создания LLM‑агентов. Теперь пора научить агента взаимодействовать с реальным рынком. В этой статье мы подключимся к Binance API, напишем Python‑скрипт для мониторинга цены BTC/USDT и настроим автономного агента, который будет отслеживать рынок 24/7.

К концу статьи у вас будет работающая система, которая каждые 5 минут запрашивает цену Bitcoin, записывает её в CSV‑файл и готова к расширению (уведомления в Telegram, технический анализ, торговые сигналы).

---

## Шаг 1. Получение API‑ключей Binance

Для доступа к данным Binance вам понадобятся два ключа:

1. **API Key** (публичный) — идентифицирует ваш аккаунт.
2. **Secret Key** (приватный) — используется для подписи запросов. **Никогда не делитесь им публично.**

### 1.1 Создание ключей в Binance

1. Авторизуйтесь на [Binance](https://www.binance.com).
2. Перейдите в **API Management** (Настройки → Управление API).
3. Нажмите **«Создать API»**, выберите тип **«Системный API»**.
4. Придумайте имя (например, `OpenClaw Monitor`) и подтвердите через 2FA.

### 1.2 Настройка прав и ограничений

**Рекомендуемые права для мониторинга:**
- ✅ **Enable Reading** — доступ к рыночным данным.
- ✅ **Enable Spot & Margin Trading** — если планируется торговля (можно отложить).
- ❌ **Enable Withdrawals** — никогда не включайте для API‑ключей трейдинг‑агентов.

**Ограничение по IP (обязательно!):**
Добавьте IP‑адрес вашего сервера Hetzner. Это предотвратит использование ключей с других машин.

**Пример настроек:**
```
API Name: OpenClaw Monitor
Permissions: Reading, Spot & Margin Trading
IP Access Restriction: 204.168.167.70/32 (ваш сервер)
```

### 1.3 Сохранение ключей

После создания вы увидите **API Key** и **Secret Key**. **Secret Key показывается только один раз** — сохраните его в надёжном месте (менеджер паролей). Если потеряете, придётся создать новый ключ.

---

## Шаг 2. Установка зависимостей

На сервере уже должен быть установлен Python 3.13.5 (как в статье 1). Установим необходимые пакеты:

```bash
# Активируем виртуальное окружение (если создавали в статье 1)
cd ~/.openclaw/workspace/trading
python3 -m venv venv
source venv/bin/activate

# Устанавливаем пакеты
pip3 install python-binance python-dotenv pandas
```

**Что мы устанавливаем:**
- `python-binance` — официальная библиотека для работы с Binance API.
- `python-dotenv` — загрузка переменных окружения из `.env` файла.
- `pandas` — для анализа данных (понадобится в следующих статьях).

---

## Шаг 3. Настройка окружения (безопасное хранение ключей)

Никогда не храните API‑ключи в коде. Используем файл `.env`, который не попадает в git.

### 3.1 Создаём файл `.env`

В директории `trading/` создайте файл `.env` со следующим содержимым:

```env
# Binance API Keys
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_secret_key_here
```

**Важно:** Замените `your_api_key_here` и `your_secret_key_here` на свои собственные ключи. Файл `.env` уже добавлен в `.gitignore`.

### 3.2 Права доступа к файлу

Ограничиваем доступ к файлу с ключами:

```bash
chmod 600 ~/.openclaw/workspace/trading/.env
```

Это разрешит чтение и запись только владельцу (root).

---

## Шаг 4. Скрипт мониторинга BTC/USDT

Создадим скрипт `monitor.py`, который будет запрашивать цену Bitcoin каждые 5 минут и записывать её в CSV.

### 4.1 Полный код скрипта

```python
#!/usr/bin/env python3
"""
BTC/USDT price monitor with CSV logging.
"""
import os
import time
import csv
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

# Configuration
SYMBOL = "BTCUSDT"
INTERVAL_SECONDS = 300  # 5 minutes
CSV_FILE = "data/btc_price.csv"

def load_api_keys():
    """Load API keys from .env file or environment variables."""
    load_dotenv()
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    return api_key, api_secret

def init_csv():
    """Initialize CSV file with headers if not exists."""
    if not os.path.exists(CSV_FILE):
        os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
        with open(CSV_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'price_usd'])
        print(f"Created new CSV file: {CSV_FILE}")

def log_price(price):
    """Append price to CSV file."""
    timestamp = datetime.utcnow().isoformat()
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, price])
    print(f"Logged: {timestamp} | ${price}")

def get_public_price(client, symbol=SYMBOL):
    """Get latest price using public endpoint."""
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        return ticker['price']
    except BinanceAPIException as e:
        print(f"Error getting price: {e}")
        return None

def main():
    print("BTC/USDT Monitor starting...")
    
    # Load API keys
    api_key, api_secret = load_api_keys()
    
    # Initialize client
    client = Client(api_key, api_secret)
    
    # Check if keys are valid (optional)
    if not api_key or not api_secret:
        print("Warning: API keys not found. Using public data only.")
    else:
        print("API keys loaded. Using authenticated connection.")
    
    # Initialize CSV
    init_csv()
    
    print(f"Monitoring {SYMBOL} every {INTERVAL_SECONDS} seconds...")
    
    try:
        while True:
            price = get_public_price(client, SYMBOL)
            if price:
                log_price(price)
            else:
                print("Failed to get price. Retrying next interval.")
            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == "__main__":
    main()
```

### 4.2 Пояснения к коду

- **Безопасное подключение:** Ключи загружаются из `.env`, не хардкодятся.
- **Обработка ошибок:** При сбое API скрипт продолжит работу через 5 минут.
- **Логирование:** Каждая запись включает UTC‑время и цену.
- **Интервал:** 300 секунд (5 минут) — оптимально для мониторинга без лимитов Binance.

### 4.3 Первый запуск

```bash
cd ~/.openclaw/workspace/trading
source venv/bin/activate
python3 monitor.py
```

Вы должны увидеть:
```
BTC/USDT Monitor starting...
API keys loaded. Using authenticated connection.
Created new CSV file: data/btc_price.csv
Monitoring BTCUSDT every 300 seconds...
Logged: 2026-03-24T13:45:00 | $98765.43
```

Остановите скрипт через 1–2 цикла (Ctrl+C). Проверьте файл `data/btc_price.csv`:

```csv
timestamp,price_usd
2026-03-24T13:45:00,98765.43
2026-03-24T13:50:00,98812.67
```

---

## Шаг 5. Запуск через cron (простой вариант)

Для периодического запуска можно использовать cron. Добавьте задание:

```bash
crontab -e
```

Добавьте строку:

```cron
*/5 * * * * cd /root/.openclaw/workspace/trading && /root/.openclaw/workspace/trading/venv/bin/python3 monitor.py >> /root/.openclaw/workspace/trading/logs/cron.log 2>&1
```

**Недостатки cron:**
- Нет автоматического перезапуска при сбое.
- Нет контроля за процессом (не знаем, работает ли).
- Сложнее управлять (остановить/перезапустить).

Для производственного использования лучше systemd.

---

## Шаг 6. Настройка systemd‑службы (рекомендуемый способ)

Systemd обеспечивает надёжный запуск, автоперезапуск при сбоях, централизованное логирование и управление через стандартные команды.

### 6.1 Создаём файл службы

Создайте файл `/etc/systemd/system/binance-monitor.service`:

```ini
[Unit]
Description=Binance BTC Price Monitor
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/.openclaw/workspace/trading
ExecStart=/root/.openclaw/workspace/trading/venv/bin/python3 monitor.py
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Restart=always
RestartSec=10
StandardOutput=append:/root/.openclaw/workspace/trading/logs/monitor.log
StandardError=append:/root/.openclaw/workspace/trading/logs/monitor-error.log

[Install]
WantedBy=multi-user.target
```

### 6.2 Устанавливаем и запускаем службу

```bash
# Перезагружаем конфигурацию systemd
sudo systemctl daemon-reload

# Включаем автозапуск при старте системы
sudo systemctl enable binance-monitor

# Запускаем службу
sudo systemctl start binance-monitor

# Проверяем статус
sudo systemctl status binance-monitor
```

Вы должны увидеть `active (running)`.

### 6.3 Управление службой

```bash
# Остановить
sudo systemctl stop binance-monitor

# Перезапустить
sudo systemctl restart binance-monitor

# Просмотр логов
sudo journalctl -u binance-monitor -f

# Или прямо из файла
tail -f ~/.openclaw/workspace/trading/logs/monitor.log
```

### 6.4 Скрипт для быстрого старта (опционально)

Создайте `scripts/start_monitor.sh`:

```bash
#!/bin/bash
# Start Binance monitor in background with screen
cd "$(dirname "$0")/.."
source venv/bin/activate
mkdir -p logs
screen -dmS binance-monitor python3 monitor.py
echo "Monitor started in screen session 'binance-monitor'"
echo "Attach: screen -r binance-monitor"
```

---

## Шаг 7. Добавление уведомлений в Telegram (бонус)

Когда цена изменится больше чем на 2% за 5 минут, отправим уведомление в Telegram.

### 7.1 Создаём Telegram‑бота

1. Напишите `@BotFather` в Telegram.
2. Команда `/newbot` → укажите имя (например, `Binance Alert Bot`).
3. Получите токен (выглядит как `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`).

### 7.2 Добавляем токен в `.env`

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=ваш_chat_id
```

Чтобы узнать `chat_id`, напишите боту `/start`, затем выполните:

```bash
curl -s "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates" | jq '.result[0].message.chat.id'
```

### 7.3 Расширяем `monitor.py`

Добавьте функцию отправки уведомления и логику сравнения цен. Полный код будет в статье 3.

---

## Шаг 8. Тестирование и отладка

### 8.1 Проверка подключения к Binance

```bash
cd ~/.openclaw/workspace/trading
source venv/bin/activate
python3 -c "from binance.client import Client; import os; from dotenv import load_dotenv; load_dotenv(); c = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET')); print(c.get_account())"
```

Если видите баланс — подключение работает.

### 8.2 Распространённые ошибки

| Ошибка | Решение |
|--------|---------|
| `BinanceAPIException: API-key format invalid.` | Проверьте, что ключи скопированы полностью, без пробелов. |
| `BinanceAPIException: Invalid signature.` | Secret Key неверен или содержит лишние символы. |
| `BinanceAPIException: IP banned.` | Добавьте IP сервера в белый список на Binance. |
| `ModuleNotFoundError: No module named 'binance'` | Активируйте виртуальное окружение или установите пакет. |
| `Permission denied` при записи в CSV | Убедитесь, что директория `data/` существует и доступна для записи. |

---

## Заключение

Сегодня мы сделали большой шаг:

✅ **Получили API‑ключи Binance** и безопасно их сохранили.  
✅ **Написали Python‑скрипт** для мониторинга цены BTC/USDT.  
✅ **Настроили systemd‑службу** для круглосуточной работы.  
✅ **Запустили автономного агента**, который теперь работает на сервере 24/7.

**Что дальше?**

В статье №3 добавим:
- **Уведомления в Telegram** при значительных изменениях цены.
- **Технические индикаторы** (RSI, MACD) прямо в скрипте.
- **Визуализацию данных** — простой график цен через matplotlib.

А пока ваш агент уже собирает рыночные данные. Через сутки у вас будет 288 записей цены Bitcoin — отличная основа для анализа.

**Готовы к следующему шагу?** В статье №3 научим агента «понимать» рынок и принимать первые автоматические решения.

---

## Ресурсы

- [Binance API Documentation](https://binance-docs.github.io/apidocs/spot/en/)
- [python-binance Library](https://github.com/binance/binance-connector-python)
- [OpenClaw Documentation](https://docs.openclaw.ai)

*Статья будет опубликована в [канале @crypto_logic_pro](https://t.me/crypto_logic_pro) 25 марта 2026.*
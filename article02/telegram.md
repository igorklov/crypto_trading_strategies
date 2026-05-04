🚀 *СТАТЬЯ 2/12*  
*LLM‑агенты для трейдинга: практическое руководство на Python + OpenClaw*

🔌 *Подключение к Binance API и создание первого агента‑наблюдателя*

В первой статье мы установили OpenClaw. Теперь научим агента взаимодействовать с реальным рынком. Сегодня подключимся к Binance API, напишем Python‑скрипт для мониторинга цены BTC/USDT и настроим автономного агента, который будет отслеживать рынок 24/7.

К концу статьи у вас будет работающая система, которая каждые 5 минут запрашивает цену Bitcoin, записывает её в CSV‑файл и готова к расширению.

---

🔑 *Шаг 1. Получение API‑ключей Binance*

Для доступа к данным Binance нужны два ключа:

1. **API Key** (публичный) — идентифицирует ваш аккаунт.
2. **Secret Key** (приватный) — используется для подписи запросов. **Никогда не делитесь им публично.**

*Как создать ключи:*

1. Авторизуйтесь на Binance.
2. Перейдите в **API Management** (Настройки → Управление API).
3. Нажмите **«Создать API»**, выберите тип **«Системный API»**.
4. Придумайте имя (например, `OpenClaw Monitor`) и подтвердите через 2FA.

*Рекомендуемые права для мониторинга:*
- ✅ **Enable Reading** — доступ к рыночным данным.
- ✅ **Enable Spot & Margin Trading** — если планируется торговля.
- ❌ **Enable Withdrawals** — никогда не включайте для API‑ключей трейдинг‑агентов.

*Ограничение по IP (обязательно!):*
Добавьте IP‑адрес вашего сервера Hetzner (например, `204.168.167.70/32`). Это предотвратит использование ключей с других машин.

*Важно:* **Secret Key показывается только один раз** — сохраните его в надёжном месте (менеджер паролей).

---

📦 *Шаг 2. Установка зависимостей*

На сервере уже должен быть установлен Python 3.13.5 (как в статье 1). Установим необходимые пакеты:

```bash
# Активируем виртуальное окружение
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

🔐 *Шаг 3. Настройка окружения (безопасное хранение ключей)*

Никогда не храните API‑ключи в коде. Используем файл `.env`, который не попадает в git.

*Создаём файл `.env`* в директории `trading/`:

```env
# Binance API Keys
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_secret_key_here
```

**Важно:** Замените `your_api_key_here` и `your_secret_key_here` на свои ключи.

*Ограничиваем доступ к файлу:*
```bash
chmod 600 ~/.openclaw/workspace/trading/.env
```

Это разрешит чтение и запись только владельцу (root).

---

🐍 *Шаг 4. Скрипт мониторинга BTC/USDT*

Создадим скрипт `monitor.py`, который будет запрашивать цену Bitcoin каждые 5 минут и записывать её в CSV.

*Основные функции:*
- Безопасное подключение (ключи из `.env`)
- Логирование в CSV с UTC‑временем
- Обработка ошибок API
- Интервал 300 секунд (5 минут) — оптимально для мониторинга без лимитов Binance

*Полный код скрипта:*

```python
#!/usr/bin/env python3
import os
import time
import csv
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

SYMBOL = "BTCUSDT"
INTERVAL_SECONDS = 300
CSV_FILE = "data/btc_price.csv"

def load_api_keys():
    load_dotenv()
    return os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_API_SECRET")

def init_csv():
    if not os.path.exists(CSV_FILE):
        os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
        with open(CSV_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'price_usd'])

def log_price(price):
    timestamp = datetime.utcnow().isoformat()
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, price])
    print(f"Logged: {timestamp} | ${price}")

def get_public_price(client, symbol=SYMBOL):
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        return ticker['price']
    except BinanceAPIException as e:
        print(f"Error getting price: {e}")
        return None

def main():
    print("BTC/USDT Monitor starting...")
    api_key, api_secret = load_api_keys()
    client = Client(api_key, api_secret)
    init_csv()
    print(f"Monitoring {SYMBOL} every {INTERVAL_SECONDS} seconds...")
    try:
        while True:
            price = get_public_price(client, SYMBOL)
            if price:
                log_price(price)
            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == "__main__":
    main()
```

*Первый запуск:*
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

Остановите скрипт через 1–2 цикла (Ctrl+C). Проверьте файл `data/btc_price.csv`.

---

🕒 *Шаг 5. Запуск через cron (простой вариант)*

Для периодического запуска можно использовать cron:

```bash
crontab -e
```

Добавьте строку:
```cron
*/5 * * * * cd /root/.openclaw/workspace/trading && /root/.openclaw/workspace/trading/venv/bin/python3 monitor.py >> /root/.openclaw/workspace/trading/logs/cron.log 2>&1
```

*Недостатки cron:* нет автоматического перезапуска при сбое, сложнее управлять. Для производства лучше systemd.

---

⚙️ *Шаг 6. Настройка systemd‑службы (рекомендуемый способ)*

Systemd обеспечивает надёжный запуск, автоперезапуск при сбоях, централизованное логирование.

*Создаём файл службы* `/etc/systemd/system/binance-monitor.service`:

```ini
[Unit]
Description=Binance BTC Price Monitor
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/.openclaw/workspace/trading
ExecStart=/root/.openclaw/workspace/trading/venv/bin/python3 monitor.py
Restart=always
RestartSec=10
StandardOutput=append:/root/.openclaw/workspace/trading/logs/monitor.log
StandardError=append:/root/.openclaw/workspace/trading/logs/monitor-error.log

[Install]
WantedBy=multi-user.target
```

*Устанавливаем и запускаем:*
```bash
sudo systemctl daemon-reload
sudo systemctl enable binance-monitor
sudo systemctl start binance-monitor
sudo systemctl status binance-monitor
```

Вы должны увидеть `active (running)`.

*Управление службой:*
- Остановить: `sudo systemctl stop binance-monitor`
- Перезапустить: `sudo systemctl restart binance-monitor`
- Логи: `sudo journalctl -u binance-monitor -f`

---

🤖 *Шаг 7. Добавление уведомлений в Telegram (бонус)*

Когда цена изменится больше чем на 2% за 5 минут, отправим уведомление в Telegram.

1. Создайте бота через `@BotFather`, получите токен.
2. Добавьте в `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=ваш_токен
   TELEGRAM_CHAT_ID=ваш_chat_id
   ```
3. Расширьте `monitor.py` функцией отправки уведомления.

Полный код будет в статье 3.

---

🔍 *Шаг 8. Тестирование и отладка*

*Проверка подключения к Binance:*
```bash
cd ~/.openclaw/workspace/trading
source venv/bin/activate
python3 -c "from binance.client import Client; import os; from dotenv import load_dotenv; load_dotenv(); c = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET')); print(c.get_account())"
```

Если видите баланс — подключение работает.

*Распространённые ошибки:*
| Ошибка | Решение |
|--------|---------|
| `API‑key format invalid.` | Проверьте, что ключи скопированы полностью. |
| `Invalid signature.` | Secret Key неверен или содержит лишние символы. |
| `IP banned.` | Добавьте IP сервера в белый список на Binance. |
| `ModuleNotFoundError` | Активируйте виртуальное окружение. |

---

✅ *Заключение*

Сегодня мы сделали большой шаг:

✅ **Получили API‑ключи Binance** и безопасно их сохранили.  
✅ **Написали Python‑скрипт** для мониторинга цены BTC/USDT.  
✅ **Настроили systemd‑службу** для круглосуточной работы.  
✅ **Запустили автономного агента**, который теперь работает на сервере 24/7.

*Что дальше?* В статье №3 добавим уведомления в Telegram, технические индикаторы (RSI, MACD) и визуализацию данных.

---

📢 *Серия «LLM‑агенты для трейдинга: практическое руководство на Python + OpenClaw» будет выходить 2–3 раза в неделю. Подписывайтесь на [канал @crypto_logic_pro](https://t.me/crypto_logic_pro), чтобы не пропустить новые статьи.*

💬 Вопросы и предложения пишите в комментариях — будем улучшать материал вместе.

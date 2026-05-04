🚀 *СТАТЬЯ 3/12*  
*LLM‑агенты для трейдинга: практическое руководство на Python + OpenClaw*

📱 *Уведомления в Telegram + технические индикаторы (RSI, MACD) и визуализация данных*

В статье №2 мы подключились к Binance API и запустили простого агента‑наблюдателя, который записывает цену BTC/USDT каждые 5 минут. Сегодня добавим интеллекта: научим агента вычислять технические индикаторы (RSI, MACD), строить графики и отправлять умные уведомления в Telegram при выполнении заданных условий.

К концу статьи у вас будет автономная система, которая:

✅ **Отслеживает рынок 24/7** с расчётом индикаторов  
✅ **Визуализирует данные** в профессиональных графиках  
✅ **Отправляет алерты в Telegram** при значимых событиях  
✅ **Работает как skill OpenClaw** (экономит ресурсы LLM)

---

🤖 *Зачем это нужно?*

Ручной мониторинг десятков индикаторов утомителен и подвержен ошибкам. Автоматизация даёт:

1. **Объективность** — алгоритм не подвержен эмоциям.
2. **Скорость** — мгновенная реакция на рыночные изменения.
3. **Масштабируемость** — один агент может следить за сотнями пар.
4. **Документирование** — все сигналы и графики сохраняются для анализа.

*Пример сценария:* Агент обнаруживает, что RSI Bitcoin упал ниже 30 (перепроданность) при одновременном пробое нижней линии Боллинджера. Он отправляет вам уведомление в Telegram с графиком и рекомендацией рассмотреть покупку.

---

🔧 *Шаг 1. Настройка Telegram‑бота*

Для отправки уведомлений нужен бот и ваш chat ID.

### 1.1 Создание бота
1. Откройте Telegram, найдите `@BotFather`.
2. Отправьте `/newbot`, следуйте инструкциям.
3. Получите токен вида `1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ`.

### 1.2 Получение chat ID
1. Найдите бота `@userinfobot`, отправьте ему `/start`.
2. Он покажет ваш `ID:` (число, например `987654321`).

### 1.3 Добавление в `.env`
Откройте файл `.env` в директории `trading/` и добавьте:

```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=ваш_токен_бота
TELEGRAM_CHAT_ID=ваш_chat_id
```

*Безопасность:* Как и ключи Binance, эти данные никогда не должны попадать в публичный репозиторий.

---

📦 *Шаг 2. Установка дополнительных зависимостей*

Нашему агенту понадобятся библиотеки для технического анализа и визуализации. Активируем виртуальное окружение и устанавливаем:

```bash
cd ~/.openclaw/workspace/trading
source venv/bin/activate

pip3 install ta matplotlib requests
```

**Что мы устанавливаем:**
- `ta` — библиотека технических индикаторов (RSI, MACD и др.).
- `matplotlib` — построение графиков.
- `requests` — отправка HTTP‑запросов (уже установлен с `python-binance`, но для надёжности).

Проверяем установку:
```bash
python3 -c "import ta, matplotlib, requests; print('Библиотеки загружены')"
```

---

📊 *Шаг 3. Технические индикаторы: теория и реализация*

Индикаторы — математические производные от цены и объёма, помогающие оценить тренд, волатильность и моментум.

### 3.1 RSI (Relative Strength Index)
- **Что измеряет:** Уровень перекупленности/перепроданности.
- **Диапазон:** 0–100. Выше 70 — перекупленность, ниже 30 — перепроданность.
- **Период:** Обычно 14 свечей.

### 3.2 MACD (Moving Average Convergence Divergence)
- **Что измеряет:** Разность между короткой и длинной экспоненциальными скользящими средними.
- **Сигналы:** Пересечение линии MACD с сигнальной линией (бычий/медвежий кроссовер).

### 3.3 SMA/EMA (Simple/Exponential Moving Average)
- **Что измеряет:** Среднюю цену за период.
- **Использование:** Определение тренда, уровней поддержки/сопротивления.

### 3.4 Bollinger Bands
- **Что измеряет:** Волатильность и экстремальные уровни цены.
- **Состоит из:** SMA (средняя линия) ± 2 стандартных отклонения.

### 3.5 Реализация в `indicators.py`
Создадим скрипт `scripts/indicators.py` в skill `binance‑trading`. Полный код доступен в skill, вот ключевые функции:

```python
def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices, fast=12, slow=26, signal=9):
    exp1 = prices.ewm(span=fast, adjust=False).mean()
    exp2 = prices.ewm(span=slow, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram
```

*Примечание:* Для точности мы используем библиотеку `ta`, но код выше показывает математику индикаторов.

**Тестирование индикаторов:**
```bash
cd ~/.openclaw/workspace/skills/binance-trading
python3 scripts/indicators.py
```

Скрипт загрузит данные из `data/btc_price.csv`, рассчитает индикаторы и выведет последние значения.

---

📈 *Шаг 4. Визуализация данных с matplotlib*

Человеческий мозг лучше воспринимает графики, чем таблицы чисел. Создадим скрипт `scripts/visualize.py`, который строит:

1. **График цены** с SMA(20), SMA(50) и Bollinger Bands.
2. **RSI** с уровнями перекупленности/перепроданности.
3. **MACD** с гистограммой.

**Пример использования:**
```bash
python3 scripts/visualize.py
```

Графики сохраняются в `charts/`:
- `price_chart.png` — цена и скользящие средние.
- `macd_chart.png` — MACD и сигнальная линия.
- `price_summary_YYYYMMDD_HHMM.png` — сводный график за последние N дней.

**Ключевой фрагмент кода (построение графика цены):**
```python
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
ax1.plot(df.index, df['price'], label='Price', color='black')
ax1.plot(df.index, df['SMA_20'], label='SMA 20', color='blue')
ax1.fill_between(df.index, df['BB_Lower'], df['BB_Upper'], alpha=0.1, color='gray')
ax1.set_ylabel('Price (USDT)')
ax1.legend()
ax1.grid(True, alpha=0.3)
```

---

🔔 *Шаг 5. Логика алертов*

Алерты должны срабатывать при значимых событиях, но не спамить. Скрипт `scripts/alert_logic.py` содержит условия:

| Условие | Параметры | Описание |
|---------|-----------|----------|
| **Изменение цены** | >2% за 5 минут | Резкий скачок волатильности |
| **RSI выходит из зоны** | <30 или >70 | Перепроданность/перекупленность |
| **MACD кроссовер** | Линия MACD пересекает сигнальную | Смена тренда |
| **Цена вне Bollinger Bands** | Цена > Upper Band или < Lower Band | Экстремальные уровни |
| **Золотой/смертельный крест** | SMA(20) пересекает SMA(50) | Долгосрочный тренд |

**Пример проверки RSI:**
```python
def check_rsi(rsi_value, overbought=70, oversold=30):
    if rsi_value >= overbought:
        return {"signal": "overbought", "value": rsi_value}
    if rsi_value <= oversold:
        return {"signal": "oversold", "value": rsi_value}
    return None
```

*Важно:* Чтобы избежать спама, реализуем **cooldown‑период** (например, 30 минут между алертами одного типа).

---

🤖 *Шаг 6. Отправка уведомлений в Telegram*

Скрипт `scripts/notify_telegram.py` отправляет сообщения и графики.

**Основные функции:**
- `send_message(text)` — текстовое уведомление.
- `send_photo(photo_path, caption)` — отправка графика.
- `send_price_alert(symbol, price, change_percent, message)` — форматированный алерт.
- `send_indicator_alert(symbol, indicator, value, signal, message)` — алерт по индикатору.

**Пример отправки алерта:**
```python
notifier.send_price_alert(
    symbol="BTCUSDT",
    price=98765.43,
    change_percent=2.5,
    previous_price=96345.12,
    message="Price increased by more than 2% in 5 minutes."
)
```

**Тестирование Telegram‑бота:**
```bash
python3 scripts/notify_telegram.py
```

Если настройки верны, вы получите тестовое сообщение в Telegram.

---

⚙️ *Шаг 7. Расширенный мониторинг (интеграция)*

Теперь объединим всё в одном скрипте `scripts/advanced_monitor.py`. Его логика:

1. **Каждые 5 минут** запрашивает цену BTC/USDT.
2. **Рассчитывает индикаторы** на основе истории.
3. **Проверяет условия** алертов.
4. **Отправляет уведомления** в Telegram при срабатывании.
5. **Логирует расширенные данные** (цена + индикаторы) в CSV.

**Запуск:**
```bash
cd ~/.openclaw/workspace/skills/binance-trading
python3 scripts/advanced_monitor.py
```

**Первые несколько минут** скрипт будет собирать данные (нужно ≥50 точек для индикаторов), затем начнёт проверку алертов.

---

🛠 *Шаг 8. Настройка systemd‑службы*

Для постоянной работы создадим службу `binance-advanced-monitor.service`.

**Создаём файл** `/etc/systemd/system/binance-advanced-monitor.service`:

```ini
[Unit]
Description=Binance Advanced Monitor (Telegram + Indicators)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/.openclaw/workspace/skills/binance-trading
ExecStart=/root/.openclaw/workspace/skills/binance-trading/venv/bin/python3 scripts/advanced_monitor.py
Restart=always
RestartSec=10
StandardOutput=append:/root/.openclaw/workspace/skills/binance-trading/logs/advanced-monitor.log
StandardError=append:/root/.openclaw/workspace/skills/binance-trading/logs/advanced-monitor-error.log

[Install]
WantedBy=multi-user.target
```

**Устанавливаем и запускаем:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable binance-advanced-monitor
sudo systemctl start binance-advanced-monitor
sudo systemctl status binance-advanced-monitor
```

**Управление:**
- Остановить: `sudo systemctl stop binance-advanced-monitor`
- Логи: `sudo journalctl -u binance-advanced-monitor -f`
- Перезапустить: `sudo systemctl restart binance-advanced-monitor`

---

🧪 *Шаг 9. Тестирование системы*

1. **Запустите расширенный монитор** (через systemd или прямо в терминале).
2. **Подождите 10–15 минут**, пока наберётся достаточно данных.
3. **Имитируйте условие алерта:** если цена не двигается, можно временно изменить порог изменения цены в `alert_logic.py` на 0.1% для теста.
4. **Проверьте Telegram** — должны прийти уведомления.
5. **Посмотрите графики** в `charts/` — они обновляются автоматически.

**Что должно работать:**
- ✅ Цена записывается каждые 5 минут в `data/btc_price_advanced.csv`.
- ✅ Индикаторы рассчитываются.
- ✅ Графики создаются.
- ✅ При срабатывании условий отправляются Telegram‑уведомления.

---

✅ *Заключение*

Сегодня мы значительно расширили функциональность нашего LLM‑агента:

✅ **Настроили Telegram‑бота** для уведомлений.  
✅ **Установили библиотеки** технического анализа и визуализации.  
✅ **Реализовали расчёт индикаторов** (RSI, MACD, SMA, Bollinger Bands).  
✅ **Создали систему визуализации** с профессиональными графиками.  
✅ **Разработали логику алертов** с cooldown‑периодами.  
✅ **Интегрировали всё в расширенный монитор** с отправкой уведомлений.  
✅ **Настроили systemd‑службу** для круглосуточной работы.

Теперь у вас есть автономный агент, который не только отслеживает цену, но и анализирует рынок, строит графики и оперативно сообщает о важных событиях.

*Что дальше?* В статье №4 займёмся **бектестингом торговых стратегий** — научим агента проверять историческую эффективность сигналов RSI, MACD и других индикаторов.

---

📢 *Серия «LLM‑агенты для трейдинга: практическое руководство на Python + OpenClaw» выходит 2–3 раза в неделю. Подписывайтесь на [канал @crypto_logic_pro](https://t.me/crypto_logic_pro), чтобы не пропустить новые статьи.*

💬 Вопросы и предложения пишите в комментариях — будем улучшать материал вместе.

*Все скрипты доступны в skill `binance‑trading` OpenClaw. Установите skill через `openclaw skills install` или скопируйте из `/root/.openclaw/workspace/skills/binance-trading/`.*
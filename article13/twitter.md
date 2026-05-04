1/12 🎬 ФИНАЛ ЦИКЛА: Спот + Фьючерсы в одной LLM-системе

За 12 статей мы построили распределённую торговую систему на Python. Сегодня — объединяем спот и фьючерсы.

🧵👇

2/12 🔍 Вспомним, что работает сейчас:
• 4 агента-воркера (ADA, ETH, SOL, BTC)
• RSI, ADX, BB, SMA
• Фундаментальный анализ через Gemini
• Telegram-уведомления
• Trailing stop + take-profit
• P&L учёт в SQLite

Результат: +$259 за неделю (демо)

3/12 🆕 Что добавляем: фьючерсная торговля

Спот: купил → ждёшь
Фьючерсы: LONG/SHORT с плечом

Одни и те же сигналы → разные действия. Параллельно.

4/12 🔑 ГДЕ взять demo-ключи (важно!)

⚠️ Веб-интерфейс переехал на demo.binance.com. API остался на testnet.binancefuture.com.

Идём на demo.binance.com
→ Login (GitHub / e-mail)
→ Аккаунт → API Management
→ Create API Key

В коде используем URL: testnet.binancefuture.com

Получаем $5000 виртуальных, риск = 0.

5/12 ✅ Как проверить ключи

```python
import hashlib, hmac, time, requests
API_KEY = "..."
SECRET = "..."
ts = int(time.time() * 1000)
sig = hmac.new(SECRET.encode(), f"timestamp={ts}".encode(), hashlib.sha256).hexdigest()
r = requests.get(f"https://testnet.binancefuture.com/fapi/v2/account?timestamp={ts}&signature={sig}",
    headers={"X-MBX-APIKEY": API_KEY})
print(r.json().get('canTrade'))
```

Ответ: True → ключи работают 🟢

6/12 🏗 Архитектура

futures_trader.py — размещение ордеров
futures_worker.py — воркер

Сигнал Buy → LONG (купить контракт)
Сигнал Sell → SHORT (продать контракт)

Запускается отдельным процессом, параллельно споту.

7/12 ⚙️ Настройка плеча

```json
{
  "leverage": 3,
  "margin_fraction": 0.1
}
```

10% маржи × 3× плечо = консервативный старт.
Никогда >20% на сделку.

8/12 📊 Типы сигналов

Buy + RSI < 20 + ADX > 25 → LONG 🟢
Sell + RSI > 80 + ADX > 25 → SHORT 🔴
Trailing stop -3% → CLOSE ❌
Take-profit +2.5% + RSI > 60 → CLOSE ✅

FA (Gemini) блокирует LONG при негативных новостях.

9/12 🛑 Абсолютные правила

1. Неделя testnet перед live
2. Плечо ≤ 3×
3. Всегда TP + SL
4. Отдельные ключи для спота и фьючерсов
5. Лимитные ордера (комиссия 0.02%)

10/12 🗺 Что дальше?

Кратко:
• Фьючерсы на testnet 🔄
• WebSocket real-time
• ML-модели
• Telegram-бот для голосового управления
• Multi-exchange (Bybit, OKX)
• Арбитраж спот↔фьючерсы

11/12 🎬 Это финал цикла из 13 статей

Что построили:
✅ Агент-наблюдатель
✅ Индикаторы + FA
✅ Бектестинг
✅ Оптимизация
✅ Риск-менеджмент
✅ Мультипроцессинг + SQLite
✅ Docker + мониторинг
✅ 24/7 на облаке
✅ Спот + фьючерсы

12/12 💡 Главный урок

LLM не предсказывает цены. Она анализирует контекст: новости, сентимент, настроение рынка.

Комбинация: TA (быстрые сигналы) + FA (LLM-контекст) + риск-менеджмент = рабочая система.

Весь код — ваш. Без чёрных ящиков.
Берите, стройте свою систему 🚀

#LLM #Binance #Futures #Trading #Python #AI

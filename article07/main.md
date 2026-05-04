# День 7: Реальный трейдинг через Binance API — размещение ордеров и управление позициями

## Введение

До этого момента мы строили агентов‑наблюдателей, анализировали данные, тестировали стратегии и управляли рисками. Пришло время перейти к самому ответственному этапу — **реальному трейдингу**. В этой статье вы научитесь:

*   Размещать рыночные и лимитные ордера через Binance API.
*   Отслеживать исполнение ордеров и управлять открытыми позициями.
*   Интегрировать торговую логику в агента OpenClaw для автономной работы.
*   Тестировать стратегию на демо‑сети Binance (demo) перед запуском на реальные средства.
*   Организовать безопасное хранение торговых ключей и логирование всех операций.

**⚠️ Внимание:** Торговля криптовалютами связана с высокими рисками. Всегда тестируйте стратегии на демо‑счете и начинайте с минимальных объемов. Автор не несет ответственности за ваши финансовые потери.

## 1. Подготовка: торговые ключи и демо‑сеть (demo)

### 1.1 Создание API‑ключей с правами на торговлю

1.  Зайдите в [Binance](https://www.binance.com/) → «API Management».
2.  Создайте новый ключ, **отметив галочку «Enable Trading»**. Остальные разрешения (например, вывод) оставьте выключенными — это минимизирует риски.
3.  Сохраните `API Key` и `Secret Key` в надёжном месте (они покажутся только один раз).

### 1.2 Настройка демо‑сети (demo)

Binance предоставляет демо‑сеть с виртуальными USDT (в режиме «spot»). Это идеальная среда для отладки.

1.  Перейдите на [Binance Demo](https://demo.binance.com/).
2.  Войдите под своими учётными данными Binance (или зарегистрируйтесь, если нет аккаунта).
3.  Создайте API‑ключи на демо‑платформе — процесс аналогичен основной сети.
4.  Пополните демо‑баланс (на странице есть кнопка «Generate» для получения виртуальных USDT).

**Важно:** URL эндпоинтов для demo другие:
*   REST: `https://demo.binance.com/api`
*   WebSocket: `wss://demo.binance.com/ws`

## 2. Размещение ордеров: market, limit, stop‑loss

Установим библиотеку `python‑binance` (если ещё не установлена):

```bash
pip3 install python-binance
```

Создадим модуль `trading.py`, который будет содержать базовые функции для торговли.

```python
# trading.py
import logging
from binance.client import Client
from binance.exceptions import BinanceAPIException

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BinanceTrader:
    def __init__(self, api_key, api_secret, demo=True):
        """
        Инициализация клиента Binance.
        :param demo: Если True, использует demo‑эндпоинты (https://demo.binance.com/api).
        """
        if demo:
            # Для demo используем специальный параметр demo=True
            self.client = Client(api_key, api_secret, demo=True)
            logging.info("Подключение к Binance Demo")
        else:
            self.client = Client(api_key, api_secret)
            logging.info("Подключение к Binance Mainnet")
    
    def place_market_order(self, symbol, side, quantity):
        """
        Разместить рыночный ордер.
        :param symbol: Пара (например, 'BTCUSDT')
        :param side: 'BUY' или 'SELL'
        :param quantity: Количество (в базовой валюте, например 0.001 BTC)
        :return: Ответ API или None при ошибке
        """
        try:
            order = self.client.order_market(
                symbol=symbol,
                side=side,
                quantity=quantity
            )
            logging.info(f"Рыночный ордер размещён: {order}")
            return order
        except BinanceAPIException as e:
            logging.error(f"Ошибка размещения рыночного ордера: {e}")
            return None
    
    def place_limit_order(self, symbol, side, quantity, price):
        """
        Разместить лимитный ордер.
        :param price: Цена, по которой должен исполниться ордер
        """
        try:
            order = self.client.order_limit(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price
            )
            logging.info(f"Лимитный ордер размещён: {order}")
            return order
        except BinanceAPIException as e:
            logging.error(f"Ошибка размещения лимитного ордера: {e}")
            return None
    
    def place_stop_loss_order(self, symbol, side, quantity, stop_price):
        """
        Разместить стоп‑лосс ордер (активируется при достижении stop_price).
        Для спотовой торговли используется тип STOP_LOSS_LIMIT.
        """
        try:
            # Получаем текущую цену для установки limitPrice (можно использовать stop_price или чуть ниже)
            limit_price = stop_price  # В демо можно так, в реальности нужен расчёт
            order = self.client.create_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                stopPrice=stop_price,
                price=limit_price,
                type="STOP_LOSS_LIMIT",
                timeInForce="GTC"
            )
            logging.info(f"Стоп‑лосс ордер размещён: {order}")
            return order
        except BinanceAPIException as e:
            logging.error(f"Ошибка размещения стоп‑лосс ордера: {e}")
            return None
    
    def get_open_orders(self, symbol=None):
        """Получить список открытых ордеров."""
        try:
            orders = self.client.get_open_orders(symbol=symbol)
            logging.info(f"Открытые ордеры ({symbol or 'все'}): {len(orders)}")
            return orders
        except BinanceAPIException as e:
            logging.error(f"Ошибка получения открытых ордеров: {e}")
            return []
    
    def cancel_order(self, symbol, order_id):
        """Отменить ордер по его ID."""
        try:
            result = self.client.cancel_order(symbol=symbol, orderId=order_id)
            logging.info(f"Ордер отменён: {result}")
            return result
        except BinanceAPIException as e:
            logging.error(f"Ошибка отмены ордера: {e}")
            return None

# Пример использования (тест на demo)
if __name__ == "__main__":
    # Используйте свои demo‑ключи (создаются на https://demo.binance.com/)
    API_KEY = "your_demo_api_key"
    API_SECRET = "your_demo_api_secret"
    
    trader = BinanceTrader(API_KEY, API_SECRET, demo=True)
    
    # Проверим баланс
    balance = trader.client.get_account()
    print("Доступные активы:", [b for b in balance['balances'] if float(b['free']) > 0])
    
    # Пример: разместить лимитный ордер на покупку 0.001 BTC по цене 50000 USDT
    # order = trader.place_limit_order('BTCUSDT', 'BUY', 0.001, 50000)
```

## 2.1 Практические примеры: рыночные и стоп‑ордера

Теперь, когда у нас есть рабочий класс `BinanceTrader`, мы можем создать отдельные скрипты для размещения рыночных и стоп‑ордеров. Эти скрипты помогут вам быстро протестировать разные типы ордеров на демо‑сети.

### Рыночные ордера (market_orders.py)

Рыночный ордер исполняется мгновенно по текущей лучшей цене на рынке. Используется, когда нужно быстро войти в позицию или выйти из неё.

Основные шаги скрипта:
1.  Подключение к Binance Demo с использованием ключей.
2.  Проверка баланса USDT и BTC.
3.  Размещение рыночного ордера на покупку (например, 0.0001 BTC).
4.  Если есть достаточный баланс BTC — размещение рыночного ордера на продажу.
5.  Вывод статуса ордеров и проверка исполнения.

```python
# Краткий пример из market_orders.py
from trading import BinanceTrader

trader = BinanceTrader(API_KEY, API_SECRET, demo=True)

# Рыночная покупка
market_buy = trader.place_market_order('BTCUSDT', 'BUY', 0.0001)
if market_buy:
    print(f"✅ Рыночный ордер на покупку размещён: {market_buy['orderId']}")
```

### Стоп‑ордера (stop_orders.py)

Стоп‑лосс и тейк‑профит ордера активируются при достижении заданной цены (`stopPrice`) и затем исполняются как лимитные (`STOP_LOSS_LIMIT`) или рыночные (`STOP_LOSS`).

Основные шаги скрипта:
1.  Получение текущей цены актива.
2.  Расчёт уровней стоп‑лосса (например, -2%) и тейк‑профита (+3%).
3.  Размещение стоп‑лосс лимитного ордера с указанием `stopPrice` и `price` (лимитная цена исполнения).
4.  Размещение тейк‑профит лимитного ордера.
5.  Использование готового метода `trader.place_stop_loss_order()` для упрощённого размещения.

```python
# Краткий пример из stop_orders.py
from trading import BinanceTrader

trader = BinanceTrader(API_KEY, API_SECRET, demo=True)

# Получаем текущую цену
ticker = trader.client.get_symbol_ticker(symbol='BTCUSDT')
current_price = float(ticker['price'])

# Стоп‑лосс ордер (защита от убытков)
stop_loss_price = current_price * 0.98  # -2%
stop_order = trader.place_stop_loss_order('BTCUSDT', 'SELL', 0.0001, stop_loss_price)
if stop_order:
    print(f"✅ Стоп‑лосс ордер размещён: {stop_order['orderId']}")
```

Полные версии этих скриптов с обработкой ошибок, логированием и подробными комментариями находятся в папке `trading/`:
- `market_orders.py` — размещение рыночных ордеров.
- `stop_orders.py` — размещение стоп‑лосс и тейк‑профит ордеров.

Вы можете запустить их напрямую после настройки демо‑ключей:
```bash
cd trading
python3 market_orders.py
python3 stop_orders.py
```

## 3. Управление позициями и мониторинг

Торговля — это не только размещение ордеров, но и постоянный мониторинг позиций, баланса и рыночных условий.

### 3.1 Отслеживание исполнения ордеров

```python
# monitoring.py
import time
from trading import BinanceTrader

class OrderMonitor:
    def __init__(self, trader, symbol):
        self.trader = trader
        self.symbol = symbol
    
    def wait_for_order_fill(self, order_id, timeout=60):
        """
        Ожидает полного исполнения ордера.
        :param timeout: Максимальное время ожидания в секундах
        :return: True если ордер исполнен, False если истёк таймаут
        """
        start = time.time()
        while time.time() - start < timeout:
            orders = self.trader.get_open_orders(self.symbol)
            # Если ордера с таким ID нет среди открытых — он исполнен
            if not any(o['orderId'] == order_id for o in orders):
                logging.info(f"Ордер {order_id} исполнен.")
                return True
            time.sleep(2)  # Опрашиваем каждые 2 секунды
        logging.warning(f"Таймаут ожидания ордера {order_id}")
        return False
    
    def get_position_info(self):
        """Получить информацию о текущей позиции по паре."""
        # Для спотовой торговли позиция — это баланс базовой валюты
        account = self.trader.client.get_account()
        for balance in account['balances']:
            if balance['asset'] == self.symbol.replace('USDT', ''):
                return float(balance['free']), float(balance['locked'])
        return 0.0, 0.0
```

### 3.2 Интеграция с агентом OpenClaw

Теперь встроим торговую логику в агента OpenClaw, чтобы он мог принимать решения автономно.

```python
# agent_trading.py
import os
from openclaw.agent import Agent, tool
from trading import BinanceTrader
from monitoring import OrderMonitor

class TradingAgent(Agent):
    def __init__(self):
        super().__init__()
        # Загружаем ключи из переменных окружения
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")
        demo = os.getenv("BINANCE_DEMO", "true").lower() == "true"
        
        self.trader = BinanceTrader(api_key, api_secret, demo=demo)
        self.monitor = OrderMonitor(self.trader, "BTCUSDT")
    
    @tool
    def check_balance(self):
        """Проверить доступный баланс USDT и BTC."""
        account = self.trader.client.get_account()
        usdt = next(b for b in account['balances'] if b['asset'] == 'USDT')
        btc = next(b for b in account['balances'] if b['asset'] == 'BTC')
        return {
            "USDT": {"free": usdt['free'], "locked": usdt['locked']},
            "BTC": {"free": btc['free'], "locked": btc['locked']}
        }
    
    @tool
    def place_trade(self, symbol: str, side: str, quantity: float, order_type: str = "market", price: float = None):
        """
        Разместить торговый ордер.
        :param symbol: Торговая пара (например, BTCUSDT)
        :param side: BUY или SELL
        :param quantity: Количество
        :param order_type: market, limit, stop_loss
        :param price: Цена (для limit и stop_loss)
        """
        if order_type == "market":
            order = self.trader.place_market_order(symbol, side, quantity)
        elif order_type == "limit":
            if price is None:
                return {"error": "Для лимитного ордера требуется цена"}
            order = self.trader.place_limit_order(symbol, side, quantity, price)
        elif order_type == "stop_loss":
            if price is None:
                return {"error": "Для стоп‑лосса требуется цена активации"}
            order = self.trader.place_stop_loss_order(symbol, side, quantity, price)
        else:
            return {"error": f"Неизвестный тип ордера: {order_type}"}
        
        if order:
            return {"success": True, "order_id": order['orderId'], "details": order}
        else:
            return {"success": False, "error": "Не удалось разместить ордер"}
    
    @tool
    def monitor_orders(self, symbol: str = None):
        """Получить список открытых ордеров."""
        orders = self.trader.get_open_orders(symbol)
        return {"open_orders": orders}
    
    @tool
    def cancel_trade(self, symbol: str, order_id: int):
        """Отменить ордер."""
        result = self.trader.cancel_order(symbol, order_id)
        return {"cancelled": result is not None, "details": result}

if __name__ == "__main__":
    agent = TradingAgent()
    agent.run()
```

## 4. Полноценная торговая стратегия на основе RSI

Объединим полученные модули в стратегию, которая:

1.  Каждые 5 минут вычисляет RSI для BTC/USDT.
2.  Если RSI < 30 (перепроданность) — размещает лимитный ордер на покупку.
3.  Если RSI > 70 (перекупленность) — размещает лимитный ордер на продажу.
4.  Устанавливает стоп‑лосс на 2% ниже цены покупки.
5.  Мониторит исполнение и корректирует ордера.

```python
# strategy_rsi_trading.py
import time
import pandas as pd
from binance.client import Client
from trading import BinanceTrader
from monitoring import OrderMonitor

class RSIStrategy:
    def __init__(self, trader, symbol='BTCUSDT', interval='5m', rsi_period=14):
        self.trader = trader
        self.symbol = symbol
        self.interval = interval
        self.rsi_period = rsi_period
        self.client = trader.client
        self.monitor = OrderMonitor(trader, symbol)
    
    def calculate_rsi(self, closes):
        """Вычисление RSI по закрытиям."""
        delta = pd.Series(closes).diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not rsi.empty else 50
    
    def get_historical_data(self, limit=100):
        """Получить исторические данные для расчёта индикаторов."""
        klines = self.client.get_klines(
            symbol=self.symbol,
            interval=self.interval,
            limit=limit
        )
        closes = [float(k[4]) for k in klines]  # Цена закрытия
        return closes
    
    def run(self):
        """Основной цикл стратегии."""
        while True:
            try:
                closes = self.get_historical_data()
                rsi = self.calculate_rsi(closes)
                current_price = closes[-1]
                
                print(f"[{time.ctime()}] Цена: {current_price:.2f}, RSI: {rsi:.2f}")
                
                # Проверяем открытые ордера
                open_orders = self.trader.get_open_orders(self.symbol)
                if len(open_orders) > 0:
                    print(f"Есть открытые ордеры: {len(open_orders)}")
                    # Логика управления ордерами (можно добавить trailing stop)
                
                # Сигналы
                if rsi < 30:
                    print("Сигнал на покупку (RSI < 30)")
                    # Размещаем лимитный ордер на 1% ниже текущей цены
                    buy_price = current_price * 0.99
                    quantity = 0.001  # 0.001 BTC
                    order = self.trader.place_limit_order(
                        self.symbol, 'BUY', quantity, buy_price
                    )
                    if order:
                        # Устанавливаем стоп‑лосс на 2% ниже цены покупки
                        stop_price = buy_price * 0.98
                        self.trader.place_stop_loss_order(
                            self.symbol, 'SELL', quantity, stop_price
                        )
                
                elif rsi > 70:
                    print("Сигнал на продажу (RSI > 70)")
                    # Если есть BTC в балансе, размещаем ордер на продажу
                    btc_balance, locked = self.monitor.get_position_info()
                    if btc_balance > 0.001:
                        sell_price = current_price * 1.01
                        order = self.trader.place_limit_order(
                            self.symbol, 'SELL', 0.001, sell_price
                        )
                
                time.sleep(300)  # Ждём 5 минут
            except Exception as e:
                print(f"Ошибка в стратегии: {e}")
                time.sleep(60)

if __name__ == "__main__":
    # Используйте demo‑аккаунт для тестирования!
    API_KEY = os.getenv("BINANCE_API_KEY")
    API_SECRET = os.getenv("BINANCE_API_SECRET")
    trader = BinanceTrader(API_KEY, API_SECRET, demo=True)
    
    strategy = RSIStrategy(trader)
    strategy.run()
```

## 5. Безопасность и логирование

### 5.1 Хранение ключей

Никогда не храните API‑ключи в коде! Используйте переменные окружения или секреты OpenClaw.

```bash
# В ~/.bashrc или через OpenClaw конфиг
export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"
export BINANCE_DEMO="true"
```

В OpenClaw можно использовать `secrets` плагин для безопасного хранения.

### 5.2 Логирование всех операций

Логи должны содержать:
*   Время операции
*   Тип ордера (buy/sell)
*   Цену и количество
*   ID ордера
*   Результат (успех/ошибка)

Пример настройки логирования в файл:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)
```

## 6. Запуск агента как службы

Создадим systemd‑службу для автономной работы торгового агента.

```ini
# /etc/systemd/system/binance-trading-agent.service
[Unit]
Description=Binance Trading Agent (RSI Strategy)
After=network.target

[Service]
Type=simple
User=openclaw
WorkingDirectory=/path/to/agent
Environment="BINANCE_API_KEY=your_key"
Environment="BINANCE_API_SECRET=your_secret"
Environment="BINANCE_DEMO=true"
ExecStart=/usr/bin/python3 /path/to/agent/strategy_rsi_trading.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Активируем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable binance-trading-agent
sudo systemctl start binance-trading-agent
sudo systemctl status binance-trading-agent
```

## Заключение

Вы построили полноценного торгового агента, который может:

✅ Размещать рыночные, лимитные и стоп‑лосс ордера через Binance API.
✅ Отслеживать исполнение и управлять позициями.
✅ Работать по стратегии на основе индикаторов (RSI).
✅ Запускаться как автономная служба на сервере.

**Следующие шаги:**

1.  **Тщательно протестируйте стратегию на демо‑сети** как минимум неделю.
2.  **Начните с минимальных объёмов** (например, 0.001 BTC) даже на реальном счёте.
3.  **Добавьте мониторинг просадки (drawdown)** и автоматическую остановку при превышении лимита.
4.  **Реализуйте более сложные стратегии** (например, с машинным обучением или анализом order book).

Помните: автоматизация торговли не гарантирует прибыли. Рынки непредсказуемы, а алгоритмы могут вести себя неожиданно при экстремальных условиях. Всегда имейте план управления рисками и будьте готовы вручную остановить агента.

Удачи в торговле!

---

*📚 Все файлы этого урока доступны в [репозитории GitHub](https://github.com/ваш-репозиторий).*

*💬 Вопросы и обсуждение — в Telegram‑канале [@crypto_logic_pro](https://t.me/crypto_logic_pro).*
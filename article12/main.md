# День 12: Фундаментальные факторы и их влияние при открытии ордеров

*20 апреля 2026*

В предыдущих статьях мы построили полноценную торговую систему, которая анализирует технические индикаторы (RSI, SMA, Bollinger Bands, ADX), генерирует сигналы и размещает ордера на Binance. Однако технический анализ — лишь одна сторона медали. Крипторынок сильно реагирует на новости, события, макроэкономические тренды и социальный сентимент. Игнорировать эти факторы — значит торговать с завязанными глазами.

Сегодня мы добавим в нашу систему **фундаментальный анализ**, научимся собирать данные из внешних источников, оценивать их влияние с помощью LLM и комбинировать с техническими сигналами для принятия более обоснованных решений.

## 1. Зачем фундаментальные факторы в автоматической торговле?

Технический анализ отлично работает на исторических данных, но часто «не видит» резких движений, вызванных внешними событиями:

- **Внезапные новости**: взлом биржи, изменение регуляции, заявление влиятельного лица.
- **Запланированные события**: хардфорк, апгрейд сети, листинг новой монеты.
- **Макроэкономика**: изменение процентных ставок ФРС, инфляционные данные, геополитические кризисы.
- **Социальный сентимент**: волна обсуждений в Twitter, Reddit, Telegram.
- **On‑chain метрики**: рост числа активных адресов, объём переводов, балансы на биржах.

**Пример:** 10 апреля 2026 года SEC неожиданно одобрила spot‑ETF на Ethereum. Цена ETH выросла на 18% за два часа. Технические индикаторы не предсказывали этот скачок, но мониторинг новостей мог дать сигнал к покупке за минуты до публикации.

**Наша цель:** создать слой фундаментального анализа, который будет:
1. Собирать данные из множества источников в реальном времени.
2. Оценивать их тональность и важность с помощью LLM.
3. Генерировать дополнительные сигналы (buy/hold/sell) с весом.
4. Комбинировать с техническими сигналами в единой системе принятия решений.

## 2. Какие фундаментальные факторы важны для крипторынка?

### 2.1. Новости и события

| Источник                   | Тип данных                               | Частота обновления |
|----------------------------|------------------------------------------|--------------------|
| Cryptopanic API            | Агрегатор новостей, можно фильтровать по монетам, тегам (атака, регулирование, партнёрство). | 1–5 минут          |
| CoinMarketCal              | Календарь событий: митапы, AMA, апгрейды, хардфорки. | Ежедневно          |
| CoinGecko API              | Общая информация о монетах, разработческая активность. | По запросу         |
| Собственный парсинг СМИ    | Крупные издания (CoinDesk, Cointelegraph, Bloomberg). | 10–30 минут        |

### 2.2. Социальный сентимент

| Платформа   | Метрика                                  | Инструмент          |
|-------------|------------------------------------------|---------------------|
| Twitter/X   | Количество твитов, репостов, лайков по хештегам, тональность текста. | Tweepy (Twitter API v2) |
| Reddit      | Активность в сабреддитах (r/CryptoCurrency, r/ethereum), upvote/downvote ratio. | PRAW (Reddit API)   |
| Telegram    | Упоминания в каналах, частота сообщений. | Telethon (MTProto)  |

### 2.3. On‑chain метрики

| Метрика                    | Что показывает                          | Источник             |
|----------------------------|------------------------------------------|----------------------|
| Активные адреса            | Количество уникальных адресов, совершающих транзакции. Рост — признак интереса. | Glassnode API, Dune  |
| Балансы на биржах          | Увеличение балансов на биржах → возможная продажа; уменьшение → уход в холодные кошельки (HODL). | Glassnode, CoinMetrics |
| Объём транзакций           | Суммарный объём переводов в сети. Рост — высокая активность. | Blockchair API       |
| Hash Rate (PoW‑сети)       | Вычислительная мощность сети. Падение — снижение безопасности; рост — укрепление сети. | BTC.com, Etherscan   |

### 2.4. Макроэкономические данные

- **Процентные ставки ФРС** (решения FOMC) — влияют на всю риск‑он‑активность.
- **Инфляция (CPI, PCE)** — высокие показатели могут снижать привлекательность крипто как хеджа.
- **Индекс доллара (DXY)** — обратная корреляция с BTC (рост доллара → падение крипто).
- **Доходности гособлигаций** — рост доходностей снижает привлекательность рискованных активов.

Эти данные публикуются по расписанию (например, CPI раз в месяц). Их можно получать через FRED API, Investing.com или специализированные финансовые API.

## 3. Инструменты для сбора данных

### 3.1. Cryptopanic API — агрегатор новостей

Cryptopanic предоставляет бесплатный API (до 30 запросов в день), который возвращает новости с фильтрацией по монетам, региону и важности.

```python
import requests
import json

class NewsCollector:
    def __init__(self, api_key=None):
        self.base_url = "https://cryptopanic.com/api/v1/posts/"
        self.api_key = api_key  # опционально, но даёт больше запросов

    def fetch_news(self, currencies="BTC,ETH", filter="hot"):
        """Получает последние новости для указанных монет."""
        params = {
            "auth_token": self.api_key,
            "currencies": currencies,
            "filter": filter,
            "public": "true" if not self.api_key else "false"
        }
        try:
            resp = requests.get(self.base_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", [])
        except Exception as e:
            print(f"Error fetching news: {e}")
            return []

# Пример использования
collector = NewsCollector(api_key="your_api_key_here")
news = collector.fetch_news(currencies="ADA,ETH,SOL,TRX", filter="hot")
for item in news[:5]:
    print(f"{item['title']} | Source: {item['source']['title']} | Votes: {item['votes']}")
```

### 3.2. Tweepy — мониторинг Twitter

Для доступа к Twitter API v2 нужен проект в Developer Portal и Bearer Token.

```python
import tweepy
from textblob import TextBlob

class TwitterMonitor:
    def __init__(self, bearer_token):
        self.client = tweepy.Client(bearer_token=bearer_token)

    def search_tweets(self, query, max_results=10):
        """Ищет твиты по запросу."""
        try:
            tweets = self.client.search_recent_tweets(
                query=query,
                max_results=max_results,
                tweet_fields=["created_at", "public_metrics"]
            )
            results = []
            if tweets.data:
                for tweet in tweets.data:
                    # Анализ тональности
                    analysis = TextBlob(tweet.text)
                    sentiment = "positive" if analysis.sentiment.polarity > 0 else \
                                "negative" if analysis.sentiment.polarity < 0 else "neutral"
                    results.append({
                        "text": tweet.text,
                        "created_at": tweet.created_at,
                        "likes": tweet.public_metrics["like_count"],
                        "retweets": tweet.public_metrics["retweet_count"],
                        "sentiment": sentiment
                    })
            return results
        except Exception as e:
            print(f"Twitter error: {e}")
            return []

# Пример: мониторинг твитов о Cardano
monitor = TwitterMonitor(bearer_token="your_bearer_token")
tweets = monitor.search_tweets("Cardano OR ADA", max_results=20)
positive_count = sum(1 for t in tweets if t["sentiment"] == "positive")
print(f"Positive tweets: {positive_count}/{len(tweets)}")
```

### 3.3. Glassnode API — on‑chain метрики

Glassnode — платный сервис, но предоставляет бесплатный доступ к некоторым индикаторам.

```python
import requests
import pandas as pd

class OnChainMetrics:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.glassnode.com/v1/metrics"

    def get_active_addresses(self, symbol="BTC", interval="24h"):
        """Получает количество активных адресов."""
        endpoint = f"{self.base_url}/addresses/active_count"
        params = {
            "a": symbol,
            "i": interval,
            "api_key": self.api_key
        }
        resp = requests.get(endpoint, params=params)
        if resp.status_code == 200:
            data = resp.json()
            df = pd.DataFrame(data)
            df['t'] = pd.to_datetime(df['t'], unit='s')
            return df
        else:
            print(f"Glassnode error: {resp.status_code}")
            return None
```

### 3.4. Календарь событий CoinMarketCal

CoinMarketCal предоставляет API для получения запланированных событий.

```python
import requests
from datetime import datetime, timedelta

class EventCalendar:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://developers.coinmarketcal.com/v1/events"

    def get_upcoming_events(self, max_results=10):
        """Получает ближайшие события."""
        params = {
            "access_token": self.api_key,
            "max": max_results,
            "sortBy": "date"
        }
        resp = requests.get(self.base_url, params=params)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"CoinMarketCal error: {resp.status_code}")
            return []
```

## 4. Анализ сентимента с помощью LLM

Современные языковые модели (ChatGPT, Claude, локальные модели) отлично справляются с классификацией тональности и извлечением сути из текста. Вместо простых правил (ключевые слова) мы можем использовать LLM для более тонкой оценки.

### 4.1. Использование OpenAI API

```python
import openai

class SentimentAnalyzer:
    def __init__(self, api_key):
        openai.api_key = api_key

    def analyze_news(self, title, content):
        """Оценивает тональность новости и её важность для крипторынка."""
        prompt = f"""
Ты — аналитик крипторынка. Оцени следующую новость:
Заголовок: {title}
Текст: {content}

Ответь в формате JSON:
{{
  "sentiment": "positive" | "negative" | "neutral",
  "impact": "high" | "medium" | "low",
  "affected_coins": ["BTC", "ETH", ...]  # список монет, на которые может повлиять новость
}}
"""
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=300
            )
            result = response.choices[0].message.content
            # Парсим JSON
            import json
            return json.loads(result)
        except Exception as e:
            print(f"OpenAI error: {e}")
            return {"sentiment": "neutral", "impact": "low", "affected_coins": []}
```

### 4.2. Локальная модель (Hugging Face)

Если нет доступа к OpenAI, можно использовать бесплатные модели из Hugging Face.

```python
from transformers import pipeline

class LocalSentimentAnalyzer:
    def __init__(self):
        self.classifier = pipeline("sentiment-analysis", model="blanchefort/rubert-base-cased-sentiment")

    def analyze(self, text):
        """Анализирует тональность текста на русском/английском."""
        result = self.classifier(text[:512])  # ограничиваем длину
        label = result[0]['label']
        score = result[0]['score']
        # Маппинг меток
        mapping = {"POSITIVE": "positive", "NEGATIVE": "negative", "NEUTRAL": "neutral"}
        return mapping.get(label, "neutral"), score
```

## 5. Интеграция фундаментального анализа с техническими сигналами

Теперь у нас есть два независимых источника сигналов:
- **Технический анализ** (TA) → сигнал от индикаторов (RSI, SMA и т.д.).
- **Фундаментальный анализ** (FA) → сигнал от новостей, сентимента, событий.

Как их объединить? Простейший способ — **взвешенная модель**.

### 5.1. Система весов

Присвоим каждому фактору вес (от 0 до 1), где сумма всех весов равна 1:

| Фактор                    | Вес   | Описание                               |
|---------------------------|-------|----------------------------------------|
| Технические индикаторы    | 0.6   | Основной источник, работает постоянно. |
| Новости (срочные)         | 0.2   | Влияет на краткосрочные движения.      |
| Социальный сентимент      | 0.1   | Отражает настроение сообщества.        |
| On‑chain метрики          | 0.1   | Показывает реальную активность сети.   |

### 5.2. Алгоритм принятия решения

1. **Вычисляем технический сигнал** (TA_score) в диапазоне [-1, 1], где -1 = strong sell, 0 = neutral, +1 = strong buy.
2. **Вычисляем фундаментальный сигнал** (FA_score) на основе новостей и сентимента (также в диапазоне [-1, 1]).
3. **Комбинируем**: `final_score = TA_weight * TA_score + FA_weight * FA_score`.
4. **Пороговое значение**:
   - `final_score > 0.3` → **BUY**
   - `final_score < -0.3` → **SELL**
   - В противном случае → **HOLD**

### 5.3. Пример кода

```python
class HybridDecisionSystem:
    def __init__(self, ta_weight=0.6, fa_weight=0.4):
        self.ta_weight = ta_weight
        self.fa_weight = fa_weight

    def get_ta_signal(self, symbol, indicators):
        """Вычисляет технический сигнал на основе индикаторов."""
        # Пример: комбинация RSI, ADX, Bollinger Bands, SMA
        rsi_signal = 1.0 if indicators['rsi'] < 30 else -1.0 if indicators['rsi'] > 70 else 0
        adx_signal = 1.0 if indicators['adx'] > 25 else 0  # сильный тренд
        bb_signal = 1.0 if indicators['price'] < indicators['bb_lower'] else \
                    -1.0 if indicators['price'] > indicators['bb_upper'] else 0
        sma_signal = 1.0 if indicators['price'] > indicators['sma20'] else -1.0

        # Среднее арифметическое (можно взвесить)
        ta_score = (rsi_signal + adx_signal + bb_signal + sma_signal) / 4.0
        return ta_score

    def get_fa_signal(self, symbol, news_items, sentiment_data):
        """Вычисляет фундаментальный сигнал."""
        if not news_items:
            return 0.0

        total_impact = 0.0
        count = 0
        for news in news_items:
            # news['impact'] = 'high' (1.0), 'medium' (0.5), 'low' (0.2)
            impact_map = {'high': 1.0, 'medium': 0.5, 'low': 0.2}
            impact = impact_map.get(news.get('impact', 'low'), 0.2)
            # news['sentiment'] = 'positive' (1), 'negative' (-1), 'neutral' (0)
            sentiment_map = {'positive': 1, 'negative': -1, 'neutral': 0}
            sentiment = sentiment_map.get(news.get('sentiment', 'neutral'), 0)
            total_impact += impact * sentiment
            count += 1

        fa_score = total_impact / max(count, 1)
        return fa_score

    def decide(self, symbol, ta_indicators, news_items, sentiment_data):
        """Принимает финальное решение."""
        ta_score = self.get_ta_signal(symbol, ta_indicators)
        fa_score = self.get_fa_signal(symbol, news_items, sentiment_data)
        final_score = self.ta_weight * ta_score + self.fa_weight * fa_score

        if final_score > 0.3:
            return "BUY", final_score
        elif final_score < -0.3:
            return "SELL", final_score
        else:
            return "HOLD", final_score
```

## 6. Практический пример: монитор новостей с Telegram‑оповещениями

Создадим отдельный процесс, который будет собирать новости, анализировать их и отправлять алерты в Telegram, а также корректировать торговые решения в реальном времени.

```python
import time
import threading
from datetime import datetime

class NewsMonitor:
    def __init__(self, news_collector, sentiment_analyzer, telegram_notifier, symbols):
        self.news_collector = news_collector
        self.sentiment_analyzer = sentiment_analyzer
        self.telegram_notifier = telegram_notifier
        self.symbols = symbols
        self.last_news_ids = set()

    def run(self, interval_seconds=300):
        """Запускает бесконечный цикл мониторинга."""
        while True:
            try:
                self.check_news()
            except Exception as e:
                print(f"Error in news monitor: {e}")
            time.sleep(interval_seconds)

    def check_news(self):
        """Проверяет новые новости для всех символов."""
        for symbol in self.symbols:
            news = self.news_collector.fetch_news(currencies=symbol, filter="hot")
            for item in news:
                if item['id'] not in self.last_news_ids:
                    self.last_news_ids.add(item['id'])
                    # Анализ сентимента
                    analysis = self.sentiment_analyzer.analyze_news(
                        title=item['title'],
                        content=item.get('body', '')
                    )
                    # Отправка алерта в Telegram
                    message = (
                        f"📰 *Новость для {symbol}*\n"
                        f"Заголовок: {item['title']}\n"
                        f"Источник: {item['source']['title']}\n"
                        f"Тональность: {analysis['sentiment']}\n"
                        f"Влияние: {analysis['impact']}\n"
                        f"Затронутые монеты: {', '.join(analysis['affected_coins'])}"
                    )
                    self.telegram_notifier.send_message(message)
                    # Логирование в базу данных
                    self.save_to_db(symbol, item, analysis)

    def save_to_db(self, symbol, news_item, analysis):
        """Сохраняет новость в базу данных."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO news (symbol, news_id, title, source, sentiment, impact, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            symbol,
            news_item['id'],
            news_item['title'],
            news_item['source']['title'],
            analysis['sentiment'],
            analysis['impact'],
            int(time.time() * 1000)
        ))
        conn.commit()
        conn.close()
```

## 7. Ограничения и риски

1. **Задержка данных** — новости могут приходить с опозданием, особенно при парсинге сайтов. API‑источники более оперативны.
2. **Ложные новости и манипуляции** — не все источники достоверны. Нужна система проверки репутации.
3. **Переобучение на шум** — рынок часто реагирует на новости краткосрочно, затем откатывается. Сигналы могут быть ложными.
4. **Стоимость API** — качественные данные (Glassnode, Twitter API) часто платные.
5. **Сложность интерпретации** — одна и та же новость может быть истолкована по‑разному (например, регуляция — это и риск, и легитимность).

**Рекомендации:**
- Начинайте с бесплатных источников (Cryptopanic, CoinGecko).
- Тестируйте гибридную стратегию на демо‑счёте минимум месяц.
- Вводите «карантин» для новостей: игнорируйте сигналы, если прошло меньше 5 минут после публикации (чтобы избежать паники).
- Комбинируйте несколько источников для перекрёстной проверки.

## 8. Заключение

Фундаментальный анализ перестаёт быть прерогативой человеческих трейдеров. С помощью LLM‑агентов мы можем автоматизировать сбор, оценку и интеграцию внешних факторов в торговую систему. Это не заменяет технический анализ, а дополняет его, позволяя учитывать «событийные» движения, которые индикаторы не ловят.

**Что мы получили в итоге:**
- Набор скриптов для сбора данных из новостей, Twitter, on‑chain метрик.
- Классификатор сентимента на основе LLM (можно использовать как облачные, так и локальные модели).
- Гибридную систему принятия решений, объединяющую технические и фундаментальные сигналы.
- Отдельный монитор новостей с Telegram‑уведомлениями.

**Следующий шаг** — интегрировать этот слой в нашу мультипроцессную торговую систему, чтобы каждый воркер учитывал не только индикаторы, но и свежие новости по своей паре. А после этого мы перейдём к финальной статье цикла, где объединим все наработки в единую систему для спотовой **и** фьючерсной торговли.

Код из этой статьи доступен в репозитории skill `binance‑trading` в папке `scripts/fundamental/`. Используйте его как отправную точку для своих экспериментов.

**Удачи в автоматизации!**
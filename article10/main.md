# День 10: Развёртывание на облачном сервере — от локального скрипта к production‑системе 24/7

## Введение

Вы построили торговую систему, которая работает на вашем ноутбуке или домашнем ПК. Но что произойдёт, когда вы выключите компьютер? Торговля остановится, сигналы будут пропущены, потенциальная прибыль ускользнёт. Чтобы ваш LLM‑агент работал **круглосуточно, без перерывов**, его нужно перенести в облако — на удалённый сервер с гарантированным аптаймом, защитой от сбоев питания и возможностью масштабирования.

В этой статье вы шаг за шагом развернёте всю инфраструктуру торговых агентов на облачном сервере (Hetzner, AWS, DigitalOcean или любом другом VPS). Вы научитесь:

*   Выбирать подходящий **облачный провайдер и тариф** под задачи трейдинга (низкие задержки, стабильный аптайм, предсказуемая цена).
*   **Настраивать сервер с нуля**: обновление системы, создание пользователя с sudo, настройка SSH‑ключей, базовый фаервол.
*   Устанавливать **Docker и Docker Compose** для контейнеризации всех компонентов (агенты, база данных, монитор).
*   **Переносить** вашу торговую систему (скрипты, конфиги, ключи API) на сервер и запускать её в изолированных контейнерах.
*   Настраивать **мониторинг и алертинг** на уровне сервера (ресурсы CPU, RAM, диск) и уровня приложения (статус контейнеров, свежесть данных).
*   Автоматизировать **обновление кода и резервное копирование** базы данных и конфигураций.
*   Интегрировать **удалённое управление через OpenClaw** — получать уведомления о состоянии системы и отдавать команды прямо из Telegram или веб‑чата.

**🎯 Цель:** получить полностью автономную, отказоустойчивую торговую платформу, которая работает 24/7 без вашего ежедневного вмешательства, и которую можно масштабировать на десятки пар и стратегий.

## 1. Выбор облачного провайдера и тарифа

Торговые агенты не требуют огромных вычислительных ресурсов, но критически важны два параметра:

1.  **Низкая и стабильная задержка (latency)** до биржи Binance. Чем ближе сервер к дата‑центру Binance (например, в Европе или Азии), тем быстрее будут приходить данные и исполняться ордера.
2.  **Высокий аптайм (uptime)** — сервер должен быть доступен 99,9% времени. Провайдеры с гарантией SLA (Service Level Agreement) обычно обеспечивают это.

### Популярные варианты

| Провайдер | Минимальная цена (месяц) | Регионы | Плюсы | Минусы |
|-----------|--------------------------|---------|-------|--------|
| **Hetzner** | ~ €4–6 (CX11) | Германия, Финляндия | Отличное соотношение цены и производительности, низкие задержки в Европе, предсказуемый биллинг | Меньше регионов, нет SLA на дешёвых тарифах |
| **DigitalOcean** | $6 (Basic Droplet) | США, Европа, Азия | Простота настройки, хорошая документация, встроенный мониторинг | Дороже за аналогичные ресурсы |
| **AWS Lightsail** | $3.5 (Nanode) | Глобально | Интеграция с экосистемой AWS, автоматические бэкапы | Сложнее для новичка, цена растёт с трафиком |
| **Vultr** | $2.5 (High Frequency) | 17 регионов | Высокая производительность SSD, гибкость | Интерфейс менее интуитивный |

**Рекомендация для старта:** Hetzner CX11 (1 vCPU, 2 GB RAM, 20 GB SSD) за ~ €4.3/месяц. Этого достаточно для 5–10 торговых агентов, монитора и лёгкой базы данных.

### Как проверить задержку до Binance

Перед покупкой сервера можно «пропинговать» кандидатов:

```bash
# Установите mtr (на Linux)
sudo apt install mtr

# Проверьте задержку до API Binance
mtr -r -c 10 api.binance.com
```

Выберите регион с наименьшим средним временем отклика (обычно < 30 мс).

## 2. Настройка сервера с нуля

Допустим, вы создали инстанс в Hetzner Cloud и получили IP‑адрес `203.0.113.1` (замените на свой).

### 2.1 Первое подключение и обновление системы

```bash
# Подключитесь к серверу (пароль или SSH‑ключ вам выдали при создании)
ssh root@203.0.113.1

# Обновите пакеты
apt update && apt upgrade -y

# Установите базовые утилиты
apt install -y curl wget git htop nano tmux
```

### 2.2 Создание пользователя с sudo (безопаснее, чем root)

```bash
# Создаём пользователя trader
adduser trader
usermod -aG sudo trader

# Копируем SSH‑ключ root'а в нового пользователя (чтобы подключаться без пароля)
mkdir -p /home/trader/.ssh
cp /root/.ssh/authorized_keys /home/trader/.ssh/
chown -R trader:trader /home/trader/.ssh
chmod 700 /home/trader/.ssh
chmod 600 /home/trader/.ssh/authorized_keys
```

Теперь вы можете подключаться как `trader`:
```bash
ssh trader@203.0.113.1
```

### 2.3 Настройка фаервола (UFW)

Разрешим только SSH и необходимые для агентов порты (если есть веб‑панель).

```bash
# Установите UFW
sudo apt install -y ufw

# Разрешите SSH (порт 22)
sudo ufw allow 22/tcp

# Если будете использовать веб‑панель мониторинга на порту 8080
sudo ufw allow 8080/tcp

# Включаем фаервол
sudo ufw enable

# Проверьте правила
sudo ufw status verbose
```

### 2.4 Настройка часового пояса и времени

Торговые агенты должны работать по UTC, чтобы избежать путаницы с летним/зимним временем.

```bash
# Установите часовой пояс UTC
sudo timedatectl set-timezone UTC

# Убедитесь, что время синхронизируется через NTP
sudo timedatectl set-ntp true

# Проверьте
date
```

## 3. Установка Docker и Docker Compose

Контейнеризация — лучший способ развернуть торговую систему: все зависимости изолированы, версии фиксированы, обновление и откат занимают секунды.

### 3.1 Установка Docker (официальный репозиторий)

```bash
# Удаляем старые версии (если есть)
sudo apt remove docker docker-engine docker.io containerd runc

# Устанавливаем зависимости
sudo apt update
sudo apt install -y ca-certificates curl gnupg

# Добавляем GPG‑ключ Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Добавляем репозиторий
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Устанавливаем Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Проверяем
sudo docker --version
sudo docker compose version
```

### 3.2 Настройка прав для пользователя `trader`

Чтобы не писать `sudo` перед каждой docker‑командой:

```bash
# Добавляем пользователя в группу docker
sudo usermod -aG docker trader

# Применяем изменения (нужно перелогиниться или выполнить)
newgrp docker
```

## 4. Перенос торговой системы на сервер

Предположим, ваш код лежит в Git‑репозитории (GitHub, GitLab) или вы можете скопировать его через SCP.

### 4.1 Клонирование репозитория

```bash
# Переходим в домашнюю директорию
cd /home/trader

# Клонируем ваш репозиторий (пример)
git clone https://github.com/yourname/crypto-trading-agents.git
cd crypto-trading-agents
```

Если репозитория нет, можно скопировать файлы через `scp` с локальной машины:
```bash
# На локальной машине (не на сервере!)
scp -r ./trading-agents/* trader@203.0.113.1:/home/trader/crypto-trading-agents/
```

### 4.2 Подготовка конфигурационных файлов

**Никогда не коммитьте секреты (API‑ключи, пароли) в Git!** Используйте `.env`‑файлы, которые остаются только на сервере.

Создайте файл `.env` в корне проекта:
```bash
cd /home/trader/crypto-trading-agents
nano .env
```

Содержимое `.env` (пример):
```
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET_KEY=your_secret_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=586716752
TELEGRAM_MONITOR_BOT_TOKEN=your_monitor_bot_token
TELEGRAM_MONITOR_CHAT_ID=586716752
```

Установите строгие права:
```bash
chmod 600 .env
```

### 4.3 Docker Compose для оркестрации

Создайте `docker-compose.yml`, который запустит все ваши сервисы. Пример для трёх торговых агентов и монитора:

```yaml
version: '3.8'

services:
  trading-agent-adausdt:
    build: .
    container_name: trading-agent-adausdt
    command: python trading/agent_trading.py --symbol ADAUSDT --interval 15m
    env_file: .env
    restart: unless-stopped
    volumes:
      - ./data:/app/data

  trading-agent-ethusdt:
    build: .
    container_name: trading-agent-ethusdt
    command: python trading/agent_trading.py --symbol ETHUSDT --interval 15m
    env_file: .env
    restart: unless-stopped
    volumes:
      - ./data:/app/data

  trading-agent-solusdt:
    build: .
    container_name: trading-agent-solusdt
    command: python trading/agent_trading.py --symbol SOLUSDT --interval 15m
    env_file: .env
    restart: unless-stopped
    volumes:
      - ./data:/app/data

  trading-monitor:
    build: .
    container_name: trading-monitor
    command: python trading/agent_monitor.py --interval 3600
    env_file: .env
    restart: unless-stopped
    volumes:
      - ./data:/app/data
```

И `Dockerfile` в корне проекта:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY skills/ /app/skills/
COPY trading/ /app/trading/
COPY .env /app/.env

CMD ["python", "trading/agent_trading.py"]
```

### 4.4 Запуск контейнеров

```bash
# Собираем образы (в первый раз это займёт несколько минут)
docker compose build

# Запускаем в фоне
docker compose up -d

# Проверяем статус
docker compose ps

# Смотрим логи одного из агентов
docker compose logs -f trading-agent-adausdt
```

## 5. Мониторинг и алертинг

Запущенные контейнеры — это хорошо, но нужно знать, что они работают корректно и не потребляют все ресурсы.

### 5.1 Мониторинг ресурсов сервера

Установите `htop` для быстрого просмотра:
```bash
sudo apt install -y htop
htop
```

Для автоматического алертинга можно использовать **Prometheus + Node Exporter + Grafana**, но для начала хватит простого скрипта, который проверяет загрузку CPU и отправляет уведомление в Telegram, если она превышает порог.

Создайте `monitor_server.py`:
```python
import psutil
import requests
import os
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_MONITOR_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_MONITOR_CHAT_ID')

def send_telegram(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    requests.post(url, json=payload)

def check_resources():
    cpu_percent = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    alerts = []
    if cpu_percent > 80:
        alerts.append(f'⚠️ CPU load {cpu_percent}%')
    if mem.percent > 85:
        alerts.append(f'⚠️ RAM usage {mem.percent}%')
    if disk.percent > 90:
        alerts.append(f'⚠️ Disk usage {disk.percent}%')

    if alerts:
        send_telegram(f'<b>Server alert</b>\n' + '\n'.join(alerts))
    else:
        print(f'{datetime.now()} – OK: CPU {cpu_percent}%, RAM {mem.percent}%, Disk {disk.percent}%')

if __name__ == '__main__':
    check_resources()
```

Добавьте его в `docker-compose.yml` как отдельный сервис, запускаемый по cron.

### 5.2 Мониторинг состояния контейнеров

Скрипт `check_containers.py`:
```python
import docker
import os
import requests

client = docker.from_env()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_MONITOR_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_MONITOR_CHAT_ID')

def send_telegram(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    requests.post(url, json=payload)

containers = client.containers.list(all=True)
running = [c.name for c in containers if c.status == 'running']
stopped = [c.name for c in containers if c.status != 'running']

if stopped:
    send_telegram(f'<b>Container alert</b>\nStopped: {", ".join(stopped)}')
else:
    print(f'All containers running: {", ".join(running)}')
```

### 5.3 Настройка cron для регулярных проверок

```bash
# Открываем crontab для пользователя trader
crontab -e

# Добавляем строки (проверка каждые 30 минут)
*/30 * * * * cd /home/trader/crypto-trading-agents && docker compose exec -T trading-monitor python monitor_server.py
*/30 * * * * cd /home/trader/crypto-trading-agents && docker compose exec -T trading-monitor python check_containers.py
```

## 6. Автоматическое обновление и резервное копирование

### 6.1 Обновление кода из Git

Создайте скрипт `update.sh`:
```bash
#!/bin/bash
cd /home/trader/crypto-trading-agents
git pull origin main
docker compose down
docker compose build
docker compose up -d
```

Сделайте его исполняемым и запускайте по расписанию (например, раз в сутки в 03:00):
```bash
chmod +x update.sh
crontab -e
# 0 3 * * * /home/trader/crypto-trading-agents/update.sh
```

### 6.2 Резервное копирование базы данных и конфигов

Если вы используете SQLite, файл базы лежит в смонтированном томе `./data`. Резервируйте его ежедневно.

Скрипт `backup.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/home/trader/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
cp /home/trader/crypto-trading-agents/data/trading.db $BACKUP_DIR/trading_$DATE.db
# Копируем .env (секреты!) только в защищённое место
cp /home/trader/crypto-trading-agents/.env $BACKUP_DIR/.env_$DATE
# Удаляем старые бэкапы (храним 7 дней)
find $BACKUP_DIR -name "*.db" -mtime +7 -delete
find $BACKUP_DIR -name ".env_*" -mtime +7 -delete
```

Добавьте в cron:
```bash
0 4 * * * /home/trader/crypto-trading-agents/backup.sh
```

## 7. Интеграция с OpenClaw для удалённого управления

OpenClaw позволяет вам получать уведомления о состоянии торговой системы прямо в Telegram (или другой мессенджер) и отправлять команды без SSH‑подключения.

### 7.1 Установка OpenClaw на сервер

```bash
# Установите Node.js (требуется версия ≥ 22.16.0)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# Установите OpenClaw глобально
sudo npm install -g openclaw

# Инициализируйте OpenClaw (ответьте на вопросы)
openclaw onboard
```

### 7.2 Настройка агента для мониторинга торговой системы

Создайте скрипт `openclaw_monitor.py`, который будет собирать ключевые метрики (прибыль/убыток, количество активных агентов, последние сигналы) и отправлять их в OpenClaw как системное событие.

Пример простой интеграции через REST API OpenClaw (если включён):
```python
import requests
import json
import os

OPENCLAW_URL = 'http://localhost:18789/api/v1/events'
API_KEY = os.getenv('OPENCLAW_API_KEY')  # нужно сгенерировать в настройках OpenClaw

def send_metric(metric_name, value):
    payload = {
        'event': 'trading_metric',
        'data': {metric_name: value},
        'timestamp': datetime.now().isoformat()
    }
    headers = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}
    requests.post(OPENCLAW_URL, json=payload, headers=headers)
```

### 7.3 Получение уведомлений в Telegram

Настройте в OpenClaw подключение Telegram‑бота. После этого все события (ошибки, сигналы, алерты ресурсов) будут дублироваться в ваш личный чат.

## 8. Что дальше?

Вы развернули production‑готовую торговую платформу в облаке. Теперь можно:

*   **Масштабировать** — добавлять новые пары простым копированием блока в `docker-compose.yml`.
*   **Углублять мониторинг** — подключить Prometheus, Grafana, настроить дашборды с графиками доходности.
*   **Внедрить A/B‑тестирование стратегий** — запускать две версии агента на одной паре и сравнивать результаты.
*   **Автоматизировать деплой** — использовать GitHub Actions или GitLab CI для сборки Docker‑образов и обновления сервера при пуше в main.

Главное преимущество облачного развёртывания — **свобода**. Ваша торговая система работает независимо от того, где вы находитесь, что позволяет сосредоточиться на улучшении стратегий, а не на поддержке инфраструктуры.

**Удачи в трейдинге!**
🚀 День 10: Развёртывание на облачном сервере — от локального скрипта к production‑системе 24/7

Торговая система работает на вашем ноутбуке? Отлично. Но что, когда вы его выключите? Сигналы пропадут, прибыль ускользнёт. Пора перенести агентов в облако — на сервер, который работает круглосуточно без вашего вмешательства.

👇 Далее: выбор облачного провайдера и тарифа.

---

2/12
☁️ Выбор облачного провайдера и тарифа

Критично: низкая задержка до Binance и высокий аптайм.

**Популярные варианты:**

• **Hetzner** (€4–6/мес) – лучшее соотношение цена/качество, Европа, низкие пинги.
• **DigitalOcean** ($6/мес) – простота, хорошая документация, встроенный мониторинг.
• **AWS Lightsail** ($3.5/мес) – интеграция с AWS, автоматические бэкапы.
• **Vultr** ($2.5/мес) – высокая производительность, 17 регионов.

**Рекомендация:** Hetzner CX11 (1 vCPU, 2 GB RAM, 20 GB SSD) за ~ €4.3/месяц. Хватит на 5–10 агентов + монитор.

Перед покупкой проверьте задержку:
```bash
mtr -r -c 10 api.binance.com
```

---

3/12
🛠️ Настройка сервера с нуля

Подключитесь к серверу (IP вам выдадут):

```bash
ssh root@ваш_ip
apt update && apt upgrade -y
apt install -y curl wget git htop nano tmux
```

**Безопасность:** создайте пользователя `trader` с sudo:
```bash
adduser trader
usermod -aG sudo trader
mkdir -p /home/trader/.ssh
cp /root/.ssh/authorized_keys /home/trader/.ssh/
chown -R trader:trader /home/trader/.ssh
```

Теперь подключайтесь как `trader@ваш_ip`.

---

4/12
🔥 Настройка фаервола и времени

**Фаервол (UFW):**
```bash
sudo apt install -y ufw
sudo ufw allow 22/tcp
sudo ufw allow 8080/tcp   # если будет веб‑панель
sudo ufw enable
sudo ufw status verbose
```

**Часовой пояс UTC** (чтобы избежать путаницы с летним/зимним временем):
```bash
sudo timedatectl set-timezone UTC
sudo timedatectl set-ntp true
date
```

---

5/12
🐳 Установка Docker и Docker Compose

Контейнеризация — лучший способ развернуть систему: зависимости изолированы, версии фиксированы, обновление — секунды.

**Установка Docker (официальный репозиторий):**
```bash
# Добавляем репозиторий
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Устанавливаем
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Проверяем
sudo docker --version
sudo docker compose version
```

---

6/12
👤 Настройка прав для пользователя

Чтобы не писать `sudo` перед каждой docker‑командой:

```bash
sudo usermod -aG docker trader
newgrp docker
```

Теперь пользователь `trader` может управлять контейнерами напрямую.

---

7/12
📦 Перенос торговой системы на сервер

**Клонируем репозиторий:**
```bash
cd /home/trader
git clone https://github.com/yourname/crypto-trading-agents.git
cd crypto-trading-agents
```

**Создаём `.env`‑файл с секретами (никогда не коммитьте его в Git!):**
```
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET_KEY=your_secret_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=586716752
TELEGRAM_MONITOR_BOT_TOKEN=your_monitor_bot_token
TELEGRAM_MONITOR_CHAT_ID=586716752
```

**Устанавливаем строгие права:**
```bash
chmod 600 .env
```

---

8/12
🎼 Docker Compose для оркестрации

Создаём `docker-compose.yml` для трёх агентов и монитора:

```yaml
version: '3.8'
services:
  trading-agent-adausdt:
    build: .
    command: python trading/agent_trading.py --symbol ADAUSDT --interval 15m
    env_file: .env
    restart: unless-stopped
    volumes:
      - ./data:/app/data

  trading-agent-ethusdt:
    build: .
    command: python trading/agent_trading.py --symbol ETHUSDT --interval 15m
    env_file: .env
    restart: unless-stopped
    volumes:
      - ./data:/app/data

  trading-monitor:
    build: .
    command: python trading/agent_monitor.py --interval 3600
    env_file: .env
    restart: unless-stopped
    volumes:
      - ./data:/app/data
```

---

9/12
🚀 Запуск контейнеров

```bash
# Собираем образы (первый раз долго)
docker compose build

# Запускаем в фоне
docker compose up -d

# Проверяем статус
docker compose ps

# Смотрим логи агента
docker compose logs -f trading-agent-adausdt
```

Если всё хорошо, вы увидите, как агенты начали мониторить рынок и отправлять сигналы в Telegram.

---

10/12
📈 Мониторинг и алертинг

**Мониторинг ресурсов сервера:** простой скрипт на Python (`monitor_server.py`) проверяет CPU, RAM, диск и отправляет алерт в Telegram, если что‑то превышает порог.

**Мониторинг состояния контейнеров:** скрипт `check_containers.py` смотрит, все ли контейнеры запущены, и сообщает об остановленных.

**Настройка cron для регулярных проверок:**
```bash
crontab -e
*/30 * * * * cd /home/trader/crypto-trading-agents && docker compose exec -T trading-monitor python monitor_server.py
*/30 * * * * cd /home/trader/crypto-trading-agents && docker compose exec -T trading-monitor python check_containers.py
```

---

11/12
🔄 Автоматическое обновление и резервное копирование

**Обновление кода из Git (скрипт `update.sh`):**
```bash
#!/bin/bash
cd /home/trader/crypto-trading-agents
git pull origin main
docker compose down
docker compose build
docker compose up -d
```

**Резервное копирование базы данных (`backup.sh`):**
```bash
#!/bin/bash
BACKUP_DIR="/home/trader/backups"
DATE=$(date +%Y%m%d_%H%M%S)
cp /home/trader/crypto-trading-agents/data/trading.db $BACKUP_DIR/trading_$DATE.db
cp /home/trader/crypto-trading-agents/.env $BACKUP_DIR/.env_$DATE
find $BACKUP_DIR -name "*.db" -mtime +7 -delete
```

Добавляем оба скрипта в cron (например, обновление в 03:00, бэкап в 04:00).

---

12/12
🔗 Интеграция с OpenClaw для удалённого управления

OpenClaw позволяет получать уведомления о состоянии системы прямо в Telegram и отправлять команды без SSH.

**Установка OpenClaw на сервер:**
```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g openclaw
openclaw onboard
```

**Настройка агента мониторинга:** создайте скрипт `openclaw_monitor.py`, который собирает метрики (прибыль/убыток, активные агенты, сигналы) и отправляет их в OpenClaw как событие.

После настройки Telegram‑бота в OpenClaw все алерты будут дублироваться в ваш личный чат.

**Итог:** ваша торговая система теперь работает 24/7 в облаке, автономно, с мониторингом и алертингом. Вы свободны заниматься стратегиями, а не инфраструктурой.

Удачи в трейдинге!
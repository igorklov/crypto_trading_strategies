# День 8: Работа с DEX и flash‑loans — децентрализованная торговля и арбитраж

## Введение

Централизованные биржи (CEX), такие как Binance, удобны для начала, но они требуют KYC, хранят ваши средства и могут заморозить вывод. **Децентрализованные биржи (DEX)** — следующий уровень свободы: вы торгуете напрямую из своего кошелька, используя смарт‑контракты, без посредников. А **flash‑loans** — это уникальный инструмент DeFi, позволяющий брать огромные суммы в долг без залога, при условии возврата в пределах одной транзакции. Вместе они открывают возможности для арбитража, ребалансировки пулов и сложных стратегий.

В этой статье вы научитесь:

*   Подключаться к Ethereum/Polygon/BSC через Web3.py и взаимодействовать с DEX‑контрактами (Uniswap, PancakeSwap).
*   Получать цены, ликвидность и другие данные прямо из блокчейна.
*   Использовать flash‑loans через протоколы типа Aave или dYdX для арбитражных операций.
*   Интегрировать DEX‑логику в агента OpenClaw для мониторинга и автоматической торговли.
*   Тестировать стратегии на тестовых сетях (Sepolia, Mumbai, BSC Testnet) перед запуском на мейннете.

**⚠️ Внимание:** Работа с DEX и flash‑loans требует глубокого понимания смарт‑контрактов, комиссий (gas) и рисков (проскальзывание, ликвидация). Всегда тестируйте на testnet и начинайте с минимальных сумм. Автор не несёт ответственности за ваши финансовые потери.

## 1. Подготовка: настройка окружения и тестовые сети

### 1.1 Установка необходимых библиотек

```bash
pip3 install web3 python-dotenv requests
```

Для работы с разными сетями также может понадобиться `aiohttp` (асинхронные запросы) и `eth-account` (подпись транзакций).

### 1.2 Получение доступа к блокчейну (RPC‑провайдеры)

Для чтения данных и отправки транзакций нужен RPC‑узел. Бесплатные варианты:

*   **Ethereum (Sepolia testnet):** https://rpc.sepolia.org
*   **Polygon (Mumbai testnet):** https://rpc‑mumbai.maticvigil.com
*   **BNB Smart Chain (Testnet):** https://data‑seed‑pre‑0‑s1.binance.org:8545

Для мейннета можно использовать публичные RPC, но для серьёзной нагрузки лучше зарегистрировать свой узел у Infura, Alchemy или QuickNode.

Сохраним RPC‑URL в `.env`:

```env
ETH_RPC_URL=https://rpc.sepolia.org
POLYGON_RPC_URL=https://rpc‑mumbai.maticvigil.com
BSC_RPC_URL=https://data‑seed‑pre‑0‑s1.binance.org:8545
PRIVATE_KEY=your_private_key_here  # Никогда не коммитьте этот файл!
```

**Примечание:** Адреса контрактов на Sepolia (WETH, USDC, роутер) могут меняться со временем. Проверяйте актуальные адреса на [sepolia.etherscan.io](https://sepolia.etherscan.io) или в официальной документации протоколов.

### 1.3 Тестовые токены и faucets

На тестовых сетях можно получить бесплатные токены через краны (faucets):

*   Sepolia ETH: https://sepoliafaucet.com
*   Mumbai MATIC: https://faucet.polygon.technology
*   BSC Testnet BNB: https://testnet.binance.org/faucet-smart

## 2. Взаимодействие с DEX: чтение цен и ликвидности

### 2.1 Подключение к Uniswap V2 через Web3.py

Универсальный подход — использовать ABI (Application Binary Interface) роутера Uniswap V2. Адреса контрактов для разных сетей:

*   Ethereum (mainnet): `0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D`
*   Sepolia (testnet): `0xC532a74256D3Db42D0Bf7a0400fEFDbad7694008` (Uniswap V2 Router)
*   Polygon: `0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff`
*   BSC (PancakeSwap): `0x10ED43C718714eb63d5aA57B78B54704E256024E`

Создадим модуль `dex_connector.py`:

```python
# dex_connector.py
import os
import json
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

class DEXConnector:
    def __init__(self, network='ethereum'):
        self.network = network
        rpc_url = self._get_rpc_url()
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to {network} RPC")
        
        self.router_address = self._get_router_address()
        with open('abis/uniswap_v2_router.json') as f:
            router_abi = json.load(f)
        self.router = self.w3.eth.contract(address=self.router_address, abi=router_abi)
    
    def _get_rpc_url(self):
        urls = {
            'ethereum': os.getenv('ETH_RPC_URL'),
            'polygon': os.getenv('POLYGON_RPC_URL'),
            'bsc': os.getenv('BSC_RPC_URL')
        }
        return urls.get(self.network, os.getenv('ETH_RPC_URL'))
    
    def _get_router_address(self):
        addresses = {
            'ethereum': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
            'polygon': '0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff',
            'bsc': '0x10ED43C718714eb63d5aA57B78B54704E256024E'
        }
        return Web3.to_checksum_address(addresses.get(self.network, addresses['ethereum']))
    
    def get_price(self, token_in, token_out, amount_in):
        """Возвращает ожидаемое количество token_out за amount_in token_in."""
        path = [Web3.to_checksum_address(token_in), Web3.to_checksum_address(token_out)]
        amounts = self.router.functions.getAmountsOut(
            amount_in, path
        ).call()
        return amounts[1]
    
    def get_liquidity(self, token0, token1):
        """Возвращает резервы пары (reserve0, reserve1)."""
        factory_address = self.router.functions.factory().call()
        with open('abis/uniswap_v2_factory.json') as f:
            factory_abi = json.load(f)
        factory = self.w3.eth.contract(address=factory_address, abi=factory_abi)
        pair_address = factory.functions.getPair(token0, token1).call()
        if pair_address == '0x' + '0'*40:
            return (0, 0)
        with open('abis/uniswap_v2_pair.json') as f:
            pair_abi = json.load(f)
        pair = self.w3.eth.contract(address=pair_address, abi=pair_abi)
        reserves = pair.functions.getReserves().call()
        return (reserves[0], reserves[1])

if __name__ == '__main__':
    dex = DEXConnector(network='ethereum')
    # Пример: цена 1 ETH в USDC (адреса токенов Sepolia)
    usdc_address = '0x94a9D9AC8a22534E3FaCa9F4e7F2E2cf85d5E4C8'
    weth_address = '0x7b79995e5f793A07Bc00c21412e50Ecae098E7f9'
    amount_eth = Web3.to_wei(1, 'ether')
    price = dex.get_price(weth_address, usdc_address, amount_eth)
    print(f"1 ETH = {Web3.from_wei(price, 'ether')} USDC")
```

### 2.2 ABI‑файлы

Для работы нужны ABI контрактов. Их можно получить на Etherscan, Polygonscan и т.п. Сохраним их в папку `abis/`:

*   `uniswap_v2_router.json`
*   `uniswap_v2_factory.json`
*   `uniswap_v2_pair.json`

Пример ABI для Uniswap V2 Router (сокращённо):

```json
[
  {
    "inputs": [
      {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
      {"internalType": "address[]", "name": "path", "type": "address[]"},
      {"internalType": "address", "name": "to", "type": "address"},
      {"internalType": "uint256", "name": "deadline", "type": "uint256"}
    ],
    "name": "swapExactETHForTokens",
    "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
    "stateMutability": "payable",
    "type": "function"
  },
  ...
]
```

## 3. Flash‑loans: теория и практика

Flash‑loan — это кредит, который выдаётся и должен быть возвращён в пределах одной транзакции. Если возврат не произошёл, вся транзакция откатывается. Это позволяет брать огромные суммы без залога, но требует безупречной логики.

### 3.1 Протоколы, предоставляющие flash‑loans: выбираем оптимальный

*   **Aave:** Самый популярный, мультичейн (Ethereum, Polygon, Avalanche), но имеет фиксированную комиссию **0.09%** от суммы займа. Для арбитража с малым спредом это может съесть всю прибыль.
*   **dYdX:** Отдельный протокол для flash‑loans (только Ethereum mainnet), комиссия отсутствует, но требует интеграции через их смарт‑контракты.
*   **Uniswap V3:** Механизм `flashSwap` позволяет выполнить обмен с последующей оплатой внутри одной транзакции, комиссия — только газ. Подходит для арбитража между парами внутри Uniswap, но не предоставляет произвольные активы.
*   **Собственный контракт:** Если вы работаете в нишевом DeFi‑протоколе, можно написать свой flash‑loan‑логику, используя более дешёвые заимствования (например, через протоколы lending с низкой комиссией).

**Рекомендация:** Для тестирования и обучения используйте **Uniswap V3 flash swap** (дешевле) или напишите mock‑контракт, эмулирующий flash‑loan. Для продакшена оцените спред и выберите протокол с наименьшей комиссией.

В этой статье мы покажем пример с Aave (как наиболее документированный), но в коде предусмотрим возможность замены на другой протокол.

### 3.2 Сравнение комиссий и практические рекомендации

Перед тем как интегрировать flash‑loan в свою стратегию, оцените **комиссии** и **доступность протоколов** на выбранной сети.

| Протокол | Комиссия | Сети | Примечания |
|----------|----------|------|------------|
| Aave v3  | 0.09% от суммы | Ethereum, Polygon, Avalanche, ... | Высокая документация, мультичейн, но комиссия фиксированная |
| dYdX     | 0%       | Ethereum mainnet только | Требует интеграции через их контракты, нет тестовой сети |
| Uniswap V3 flash swap | Только газ (комиссия пула ~0.01–1%) | Все сети с Uniswap V3 | Работает только для пар внутри Uniswap, нельзя занять произвольный актив |
| Собственный контракт | Зависит от реализации | Любая | Максимальная гибкость, но требует глубокого знания Solidity и аудита |

**Как выбрать?**

1.  **Тестирование на Sepolia:** Поскольку Aave может быть не развёрнут на Sepolia, используйте **mock‑контракт**, который эмулирует логику flash‑loan без реального заимствования. Это позволит отладить всю цепочку (вызов, колбэк, возврат) без затрат на комиссии.
2.  **Расчёт прибыльности:** Если ваш арбитражный спред меньше **0.09%**, Aave не подходит — ищите альтернативы с нулевой или меньшей комиссией.
3.  **Использование Uniswap V3 flash swap:** Если ваша стратегия завязана на обмене между двумя токенами, которые есть в Uniswap V3, этот механизм будет самым дешёвым. Изучите [документацию Uniswap V3](https://docs.uniswap.org/concepts/protocol/flash-swaps) и примеры контрактов.
4.  **Переход на mainnet:** Перед запуском на мейннете проведите тесты в fork‑сети (например, через Hardhat) с реальными адресами контрактов.

**Важно:** Flash‑loan арбитраж — это высококонкурентная область. Боты мониторят мемпул и могут фронтраннить ваши транзакции. Помимо комиссий протокола, учитывайте **газ** и возможные **проскальзывания**.

### 3.3 Структура flash‑loan транзакции

**На примере Aave v3:**

1.  Вызываем функцию `flashLoan` у контракта Aave LendingPool.
2.  Указываем сумму, адрес актива, адрес получателя (наш контракт) и данные для колбэка.
3.  В течение той же транзакции выполняется `executeOperation` (наш колбэк), где мы:
    *   Используем заёмные средства (например, арбитраж между DEX).
    *   Возвращаем сумму + комиссию (0.09% на Aave).
4.  Если баланс контракта после выполнения недостаточен для возврата, транзакция откатывается.

**Важно:** На тестовой сети Sepolia протокол Aave может быть не развёрнут. Для обучения можно использовать **mock‑контракт**, который эмулирует логику flash‑loan без реального заимствования. В продакшене выбирайте протокол с минимальной комиссией (Uniswap V3 flash swap, dYdX или собственный интеграционный слой).

### 3.4 Пример смарт‑контракта для flash‑loan (Solidity)

```solidity
// SPDX‑License‑Identifier: MIT
pragma solidity ^0.8.0;

import "@aave/core‑v3/contracts/flashloan/interfaces/IFlashLoanSimpleReceiver.sol";
import "@aave/core‑v3/contracts/interfaces/IPool.sol";

// Этот контракт предназначен для Aave v3. Для других протоколов (Uniswap V3 flash swap, dYdX)
// потребуется изменить интерфейс и логику возврата займа.
contract FlashLoanArbitrage is IFlashLoanSimpleReceiver {
    address immutable POOL;
    address immutable OWNER;

    constructor(address poolAddress) {
        POOL = poolAddress;
        OWNER = msg.sender;
    }

    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external override returns (bool) {
        require(msg.sender == POOL, "Caller must be pool");
        require(initiator == OWNER, "Initiator must be owner");

        // Здесь ваша арбитражная логика (например, обмен на Uniswap)
        // ...

        uint256 totalAmount = amount + premium;
        IERC20(asset).approve(POOL, totalAmount);
        return true;
    }

    function requestFlashLoan(address asset, uint256 amount) external {
        require(msg.sender == OWNER, "Only owner");
        IPool(POOL).flashLoanSimple(
            address(this),
            asset,
            amount,
            "",
            0
        );
    }
}
```

### 3.5 Интеграция flash‑loan в Python

Чтобы вызвать flash‑loan из Python, нужно:
1.  Развернуть смарт‑контракт (как выше) в тестовой сети.
2.  Использовать Web3.py для вызова `requestFlashLoan`.

Создадим модуль `flashloan_caller.py`:

```python
# flashloan_caller.py
import os
import json
from web3 import Web3, HTTPProvider
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

class FlashLoanCaller:
    def __init__(self, network='ethereum'):
        rpc_url = os.getenv(f'{network.upper()}_RPC_URL')
        self.w3 = Web3(HTTPProvider(rpc_url))
        self.account = Account.from_key(os.getenv('PRIVATE_KEY'))
        self.w3.eth.default_account = self.account.address
        
        # Загружаем ABI и адрес нашего контракта
        with open('abis/FlashLoanArbitrage.json') as f:
            self.contract_abi = json.load(f)
        self.contract_address = os.getenv('FLASHLOAN_CONTRACT_ADDRESS')
        self.contract = self.w3.eth.contract(
            address=self.contract_address,
            abi=self.contract_abi
        )
    
    def request_loan(self, asset_address, amount_wei):
        """Вызывает flash‑loan через наш контракт."""
        tx = self.contract.functions.requestFlashLoan(
            asset_address, amount_wei
        ).build_transaction({
            'from': self.account.address,
            'gas': 500000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        return self.w3.eth.wait_for_transaction_receipt(tx_hash)

if __name__ == '__main__':
    caller = FlashLoanCaller(network='ethereum')
    # Пример: занять 1 ETH (WETH) на Sepolia
    weth_address = '0x7b79995e5f793A07Bc00c21412e50Ecae098E7f9'
    receipt = caller.request_loan(weth_address, Web3.to_wei(1, 'ether'))
    print(f"Flash‑loan транзакция: {receipt['transactionHash'].hex()}")
```

## 4. Интеграция с OpenClaw: агент для DEX‑мониторинга и арбитража

Теперь соберём всё воедино и создадим агента OpenClaw, который будет следить за разницей цен между CEX (Binance) и DEX (Uniswap/PancakeSwap) и при обнаружении арбитражной возможности либо сигнализировать, либо (если настроено) выполнять flash‑loan арбитраж.

### 4.1 Структура агента

Создадим skill `dex-arbitrage` в директории OpenClaw:

```
skills/dex-arbitrage/
├── SKILL.md
├── monitor.py          # Основной модуль мониторинга
├── flashloan.py        # Логика flash‑loan
├── connectors/
│   ├── binance_connector.py
│   └── dex_connector.py
└── config.yaml         # Конфигурация сетей и порогов
```

### 4.2 Код агента‑монитора (`monitor.py`)

```python
# monitor.py
import asyncio
import logging
from connectors.binance_connector import BinanceConnector
from connectors.dex_connector import DEXConnector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DEXArbitrageMonitor:
    def __init__(self, config):
        self.config = config
        self.binance = BinanceConnector()
        self.dex = DEXConnector(network=config['network'])
        self.threshold = config['threshold']  # минимальная прибыль в %
    
    async def check_pair(self, symbol, token_in, token_out):
        """Сравнивает цену на Binance и DEX."""
        # Цена на Binance
        binance_price = self.binance.get_price(symbol)
        # Цена на DEX (через 1 единицу базового токена)
        dex_price = self.dex.get_price(token_in, token_out, 10**18)  # 1 ETH/BNB/MATIC
        dex_price_normalized = dex_price / 10**18
        
        spread = (binance_price - dex_price_normalized) / dex_price_normalized * 100
        if abs(spread) > self.threshold:
            logger.info(f"Арбитраж {symbol}: Binance={binance_price:.6f}, DEX={dex_price_normalized:.6f}, spread={spread:.2f}%")
            # Здесь можно вызвать flash‑loan или отправить уведомление
            return True, spread
        return False, spread
    
    async def run(self):
        """Основной цикл мониторинга."""
        pairs = self.config['pairs']
        while True:
            for pair in pairs:
                arbitrage, spread = await self.check_pair(**pair)
                if arbitrage:
                    # Действие при обнаружении арбитража
                    pass
            await asyncio.sleep(self.config['interval'])

if __name__ == '__main__':
    config = {
        'network': 'ethereum',
        'threshold': 1.0,  # 1%
        'interval': 30,    # секунды
        'pairs': [
            {'symbol': 'ETHUSDT', 'token_in': '0xB4FBF271143F4FBf7B91A5ded31805e42b2208d6', 'token_out': '0x73967c6a0904aA032C103b4104747E88c566B1A2'}
        ]
    }
    monitor = DEXArbitrageMonitor(config)
    asyncio.run(monitor.run())
```

### 4.3 Настройка OpenClaw skill

Создадим `SKILL.md` с описанием skill и командами для запуска. Skill будет добавлять команды типа:

```bash
openclaw dex‑arbitrage monitor --network polygon
openclaw dex‑arbitrage flash‑loan --asset WETH --amount 10
```

## 5. Тестирование на testnet и переход на мейннет

### 5.1 Полный цикл тестирования

1.  **Разверните контракт FlashLoanArbitrage** в Sepolia/Mumbai/BSC Testnet.
2.  **Пополните его** небольшим количеством нативных токенов (ETH, MATIC, BNB) для оплаты газа.
3.  **Запустите монитор** на тестовых парах (используйте тестовые токены).
4.  **Сымитируйте арбитраж** — создайте искусственный спред, изменив цену на локальном DEX‑форке (например, с помощью Ganache).
5.  **Выполните flash‑loan** и убедитесь, что логика работает и комиссия возвращается.

### 5.2 Риски и меры предосторожности

*   **Проскальзывание (slippage):** Всегда устанавливайте лимит `amountOutMin` при обмене.
*   **Комиссии газа:** На мейннете они могут быть высоки и съесть всю прибыль.
*   **Ликвидация:** Если ваш контракт не вернёт flash‑loan, транзакция откатится, но вы потеряете газ.
*   **Атаки фронтраннинга:** Вашу арбитражную транзакцию могут перехватить майнеры/боты. Используйте механизмы защиты (например, commit‑reveal).

## Заключение

Работа с DEX и flash‑loans открывает новый уровень возможностей для алгоритмической торговли: от простого арбитража до сложных стратегий ребалансировки и ликвидаций. Интеграция с OpenClaw позволяет автоматизировать эти процессы и запускать их 24/7.

**Что дальше?** В следующей статье (День 9) мы разберём **масштабирование агентов**: как управлять множеством пар, сетей и стратегий, использовать базы данных для хранения истории и подключать панели мониторинга (Grafana, Prometheus).

---

**Полезные ссылки:**

*   [Документация Web3.py](https://web3py.readthedocs.io/)
*   [Aave Developer Portal](https://docs.aave.com/developers/)
*   [Uniswap V2 Documentation](https://docs.uniswap.org/)
*   [OpenClaw Skills Guide](https://docs.openclaw.ai/guide/skills/)

**Код статьи:** Все файлы доступны в репозитории [ссылка на GitHub].

---

*Если у вас есть вопросы или нужна помощь с настройкой — пишите в комментариях или в Telegram‑канал @crypto_logic_pro.*
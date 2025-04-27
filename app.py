import os
import logging
from flask import Flask, request
import ccxt
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Инициализация Flask
app = Flask(__name__)

# Загрузка переменных окружения
load_dotenv()
KUCOIN_API_KEY = os.getenv('KUCOIN_API_KEY')
KUCOIN_API_SECRET = os.getenv('KUCOIN_API_SECRET')
KUCOIN_API_PASSPHRASE = os.getenv('KUCOIN_API_PASSPHRASE')

# Инициализация KuCoin Futures
kucoin = ccxt.kucoinfutures({
    'apiKey': KUCOIN_API_KEY,
    'secret': KUCOIN_API_SECRET,
    'password': KUCOIN_API_PASSPHRASE,
    'enableRateLimit': True
})

# Настройки бота
SYMBOL = 'HBAR/USDT'  # Торговая пара (можно изменить через сигнал)
LEVERAGE = 50  # Кредитное плечо
DEPOSIT_PERCENT = 0.20  # 20% от депозита на сделку
MIN_ORDER_SIZE = 28  # Минимальный объем для HBAR/USDT

def set_leverage(symbol, leverage):
    """Установка кредитного плеча для торговой пары."""
    try:
        kucoin.set_leverage(leverage, symbol)
        logger.info(f"Leverage set to {leverage}x for {symbol}")
    except Exception as e:
        logger.error(f"Failed to set leverage: {str(e)}")
        raise

def get_position_size(symbol, deposit_percent):
    """Расчет объема позиции на основе 20% депозита."""
    try:
        balance = kucoin.fetch_balance()
        total_usdt = balance['total']['USDT']
        position_usdt = total_usdt * deposit_percent
        ticker = kucoin.fetch_ticker(symbol)
        price = ticker['last']
        position_size = position_usdt / price
        if position_size < MIN_ORDER_SIZE:
            logger.warning(f"Position size {position_size} below minimum {MIN_ORDER_SIZE}")
            return MIN_ORDER_SIZE
        return position_size
    except Exception as e:
        logger.error(f"Error calculating position size: {str(e)}")
        raise

def place_order(symbol, action, amount, stop_loss, take_profit):
    """Размещение ордера с установкой стоп-лосса и тейк-профита."""
    try:
        side = 'buy' if action == 'buy' else 'sell'
        order = kucoin.create_market_order(symbol, side, amount, params={'leverage': LEVERAGE})
        logger.info(f"Placed {side} order: {order}")

        # Установка стоп-лосса и тейк-профита
        stop_side = 'sell' if side == 'buy' else 'buy'
        kucoin.create_stop_loss_order(symbol, stop_side, amount, stop_loss)
        kucoin.create_take_profit_order(symbol, stop_side, amount, take_profit)
        logger.info(f"Set stop-loss at {stop_loss} and take-profit at {take_profit}")
        return order
    except Exception as e:
        logger.error(f"Error placing order: {str(e)}")
        raise

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка Webhook от TradingView."""
    try:
        data = request.json
        logger.info(f"Received webhook: {data}")

        # Извлечение данных из сигнала
        action = data.get('action')  # buy или sell
        symbol = data.get('symbol', SYMBOL)  # По умолчанию HBAR/USDT
        stop_loss = float(data.get('stop_loss'))
        take_profit = float(data.get('take_profit'))

        if action not in ['buy', 'sell']:
            return {"status": "error", "message": "Invalid action"}, 400

        # Установка кредитного плеча
        set_leverage(symbol, LEVERAGE)

        # Расчет объема позиции
        amount = get_position_size(symbol, DEPOSIT_PERCENT)

        # Размещение ордера
        order = place_order(symbol, action, amount, stop_loss, take_profit)

        return {"status": "success", "order": order}, 200
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return {"status": "error", "message": str(e)}, 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
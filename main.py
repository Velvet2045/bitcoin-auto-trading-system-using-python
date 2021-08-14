import ccxt
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
import time
import os
import logging
import telegram
import pyupbit

import config
import strategy as st
import practice_strategy as pst
import function as fn
import definition as df

###########################################################################################################

# 텔레그램 봇 만들기
telegram_token = config.access_token
chat_id = config.chat_id
bot = telegram.Bot(token=telegram_token)   # bot을 선언합니다.
# bot.sendMessage(chat_id=chat_id, text="Hello world!")

# CoinBot Demo Version
exchange_name = fn.get_ini(df.SETTING_INI_PATH, 'EXCHANGE', 'EXCHANGE_NAME')

api_key = ''
secret_key = ''
if exchange_name == "Binance":
    api_key = config.binance_api_key
    secret_key = config.binance_api_secret
elif exchange_name == "Upbit":
    api_key = config.upbit_api_key
    secret_key = config.upbit_api_secret

bot_version = float(fn.get_ini(df.SETTING_INI_PATH, 'SETTING', 'BOT_VER'))

now = datetime.now()
creation_day = datetime.strptime(fn.get_ini(df.SETTING_INI_PATH, 'SETTING', 'CREATION_DAY',
                                 now.strftime('%Y/%m/%d %H:%M:%S')), '%Y/%m/%d %H:%M:%S')
fn.set_ini(df.SETTING_INI_PATH, 'SETTING', 'CREATION_DAY', creation_day.strftime('%Y/%m/%d %H:%M:%S'))
duration_day = now - creation_day

rank_limit = int(fn.get_ini(df.SETTING_INI_PATH, 'SETTING', 'RANK_LIMIT'))
run_mode = int(fn.get_ini(df.SETTING_INI_PATH, 'SETTING', 'RUN_MODE'))

# Strategy number 0~199
use_holding_cash_strategy = int(fn.get_ini(df.SETTING_INI_PATH, 'SETTING', 'USE_HOLDING_CASH_STRATEGY'))
use_dual_strategy = int(fn.get_ini(df.SETTING_INI_PATH, 'SETTING', 'USE_DUAL_STRATEGY'))
strategy1 = int(fn.get_ini(df.SETTING_INI_PATH, 'SETTING', 'STRATEGY1'))
strategy2 = int(fn.get_ini(df.SETTING_INI_PATH, 'SETTING', 'STRATEGY2'))

# start time
trading_interval = fn.get_ini(df.SETTING_INI_PATH, 'SETTING', 'TRADING_INTERVAL')

# symbol list
use_static_sysbol_list = int(fn.get_ini(df.SETTING_INI_PATH, 'SETTING', 'USE_STATIC_SYMBOL_LIST'))

# use bnb fee
use_bnb_fee = int(fn.get_ini(df.SETTING_INI_PATH, 'SETTING', 'USE_BNB_FEE'))
trading_fee = 0.001
if exchange_name == "Binance" and use_bnb_fee:
    trading_fee = 0
elif exchange_name == "Upbit":
    trading_fee = 0.0005

# static symbol
static_symbol_list = []

for i in range(fn.get_keys_num(df.SETTING_INI_PATH, 'STATIC_SYMBOL')):
    temp_symbol = fn.get_ini(df.SETTING_INI_PATH, 'STATIC_SYMBOL', i)
    if temp_symbol != '0':
        static_symbol_list.append(temp_symbol)

# except symbol
exception_symbol_list = []

for i in range(fn.get_keys_num(df.SETTING_INI_PATH, 'EXCEPTION_SYMBOL')):
    temp_symbol = fn.get_ini(df.SETTING_INI_PATH, 'EXCEPTION_SYMBOL', i)
    if temp_symbol != '0':
        exception_symbol_list.append(temp_symbol)

# 로거 정의
logger = logging.getLogger("CoinBot1320")
logger.setLevel(logging.DEBUG)

# 콘솔 출력
stream_hander = logging.StreamHandler()
logger.addHandler(stream_hander)

# 로깅 저장
log_dir = './logs'

if not os.path.exists(log_dir):
    os.mkdir(log_dir)

logging_file_name = time.strftime('/SystemLog_%Y%m%d', time.localtime(time.time())) + ".log"
file_handler = logging.FileHandler(filename=log_dir + logging_file_name)
formatter = logging.Formatter(
  '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s'
  )
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.info("Log file save to " + log_dir + logging_file_name)

print("#################################################################################")
print("################################## CoinBot v" + str(bot_version) + " #################################")
print("#################################################################################\n\n")

logger.info("Trading starts at every time with strategy " + str(strategy1) + ".")

#exchange = pyupbit.Upbit(api_key, secret_key)
#order = exchange.buy_limit_order("KRW-XRP", 1645, 10)
#time.sleep(15)
#print(order)

#resp = exchange.get_order("KRW-XRP")
#print(resp[0])

try:
    def job_binance():
        # 잔고 조회
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret_key,
            'enableRateLimit': True,
            'options': {
                'api-expires': 86400
            }
        })
        exchange.nonce = lambda: exchange.milliseconds() - 1000
        balance = exchange.fetch_balance()
        # print(balance)

        # ticker 조회
        markets = exchange.fetch_tickers()

        # coin rank 조회
        rank_list = fn.get_coin_rank()

        # USDT 자산 조회
        total_money = 1000.0
        if run_mode == df.MODE_RUN:
            total_money = balance['USDT']['total']
        etc_money = 0.0

        # rank_limit 안에 드는 놈만 거래
        symbol_list = []
        if use_static_sysbol_list:
            for key in static_symbol_list:
                symbol_list.append(key)
        else:
            for key in markets.keys():
                if '/USDT' in key:
                    temp_res = False
                    for expt_key in exception_symbol_list:
                        if expt_key in key:
                            temp_res = True
                            break

                    if temp_res:
                        continue

                    if use_bnb_fee:
                        if 'BNB/USDT' in key:
                            continue

                    symbol = key.split('/')[0]
                    try:
                        rank = rank_list.index(symbol)
                    except ValueError:
                        rank = -1
                    if rank > -1 and rank < rank_limit:
                        symbol_list.append(key)

        # 실잔고 계산
        for key in markets.keys():
            if '/USDT' in key:
                symbol = key.split('/')[0]
                count = balance[symbol]['total']
                if count > 0:
                    ticker = exchange.fetch_ticker(key)
                    total_money += ticker['close'] * count
                    etc_money += ticker['close'] * count


        print("# 운용 정보 #")
        print("- 잔고: " + str(total_money) + " USDT")
        print("- 거래소: " + exchange_name)
        print("- 생성일: " + creation_day.strftime("%Y-%m-%d"))
        print("- 가동일수: " + str(duration_day.days) + "일\n")

        seed_money = float(fn.get_ini(df.SETTING_INI_PATH, 'SETTING', 'SEED_MONEY'))
        profit_money = total_money - seed_money

        print("# 자산 정보 #")
        print("- USDT 보유량: " + str(round(balance['USDT']['total'], 2)) + " USDT")
        print("- 기타 보유량: " + str(round(etc_money, 2)) + " USDT")
        print("- 수익금: " + str(round(profit_money, 2)) + " USDT")
        print("- 투자원금: " + str(seed_money) + " USDT\n")

        if seed_money != 0:
            asset_change_rate = float(round(profit_money / seed_money * 100.0, 2))
        else:
            asset_change_rate = 0

        print("# 자산 변동 현황 #")
        print("- 변동 기간: " + str(duration_day.days) + " 일")
        print("- 자산 변동률: " + str(asset_change_rate) + " %\n")

        one_unit = 10.0
        cash_ratio = 0
        if use_holding_cash_strategy:
            cash_ratio = 0.5

        if use_dual_strategy:
            one_unit = round((total_money / (len(symbol_list) * 2)), 2)
        else:
            one_unit = round((total_money / len(symbol_list)), 2)

        print("# 시스템 정보 #")
        print("- 동작 모드: " + str(run_mode))
        print("- 주문 단위: " + str(one_unit) + " USDT\n")

        # 최소 주문 크기 : 10 USDT
        if one_unit >= 10.0 or run_mode != df.MODE_RUN:

            # 트레이딩 시작
            fn.time_print("Start trading to " + str(strategy1))
            s_cnt = 0
            strategy_num = strategy1
            while(True):
                read_balance = False
                trading_signal = int(fn.get_ini(df.SIGNAL_INI_PATH, strategy_num, symbol_list[s_cnt], df.SIGNAL_NONE))
                direction = "Long"
            # 잔고 읽기
                while not read_balance:
                    try:
                        balance = exchange.fetch_balance()
                        read_balance = True
                    except Exception as e:
                        pass

                if read_balance:
                    # df.WALLET_INI_PATH에서 잔고 받아오기
                    holding_quantity = float(fn.get_ini(df.WALLET_INI_PATH, strategy_num, symbol_list[s_cnt], 0.0))
                    total_money = 1000.0
                    if run_mode == df.MODE_RUN:
                        total_money = balance['USDT']['total']
                    etc_money = 0.0
                    for key in markets.keys():
                        if '/USDT' in key:
                            symbol = key.split('/')[0]
                            count = balance[symbol]['total']

                            if count > 0:
                                ticker = exchange.fetch_ticker(key)
                                total_money += ticker['close'] * count
                                etc_money += ticker['close'] * count

                    fn.time_print("cur symbol: " + symbol_list[s_cnt])
                    if strategy_num == 0:
                        trading_signal = st.get_signal_by_donchian(exchange_name, exchange, symbol_list[s_cnt],
                                                                   run_mode, logger, 25, 14, "1d", 2, 20)
                    elif strategy_num == 1:
                        trading_signal = st.get_signal_by_donchian(exchange_name, exchange, symbol_list[s_cnt],
                                                                   run_mode, logger, 55, 20, "1d")
                    elif strategy_num == 2:
                        trading_signal = st.get_signal_by_ma_double(exchange_name, exchange, symbol_list[s_cnt],
                                                                    run_mode, logger, 10, 5, "1d")
                    elif strategy_num == 3:
                        trading_signal = st.get_signal_by_ma_double_2(exchange_name, exchange, symbol_list[s_cnt],
                                                                      run_mode, logger, 25, 14, "1d", 20, 10)
                    elif strategy_num == 4:
                        trading_signal = st.get_signal_by_larry_williams(exchange_name, exchange, symbol_list[s_cnt],
                                                                         run_mode, logger, "1d")
                    elif strategy_num == 5:
                        trading_signal = st.get_signal_by_reverse_rsi_2(exchange_name, exchange, symbol_list[s_cnt],
                                                                        run_mode, logger, trading_signal,
                                                                        150, 10, 2, 97, "1d")
                    elif strategy_num == 6:
                        trading_signal = st.get_signal_by_rsi(exchange_name, exchange, symbol_list[s_cnt],
                                                              run_mode, logger, 2, 5, 95, "1d")
                    elif strategy_num == 7:
                        trading_signal = st.get_signal_by_efficiency_ratio(exchange_name, exchange, symbol_list[s_cnt],
                                                                           run_mode, logger, 10, 120, "1d")
                    elif strategy_num == 8:
                        trading_signal = st.get_signal_by_maemfe(exchange_name, exchange, symbol_list[s_cnt],
                                                                 run_mode, logger, 0.5, "15m")
                    elif strategy_num == 101:
                        trading_signal = pst.get_signal_by_strategy1(exchange_name, exchange, symbol_list[s_cnt],
                                                                     run_mode, logger, trading_signal, "15m", "1d")
                    elif strategy_num == 102:
                        trading_signal = pst.get_signal_by_strategy2(exchange_name, exchange, symbol_list[s_cnt],
                                                                     run_mode, logger, trading_signal, "15m", "1d",
                                                                     60)

                    if run_mode == df.MODE_DRY or run_mode == df.MODE_RUN:
                        order_price = 0.0
                        order_count = 0.0
                        if trading_signal == df.SIGNAL_BUY:
                            if balance['USDT']['free'] < total_money * cash_ratio:
                                continue

                            order_ticker = exchange.fetch_ticker(symbol_list[s_cnt])
                            holding_usdt = order_ticker['close'] * holding_quantity

                            if direction == "Long":
                                # 호가 조회
                                orderbook = exchange.fetch_order_book(symbol_list[s_cnt])
                                dec_price = fn.get_decimal_places(orderbook['asks'], 0)
                                dec_count = fn.get_decimal_places(orderbook['asks'], 1)

                                if orderbook['asks']:
                                    try:
                                        # 지정가 매수 : 티커, 주문 수량, 주문 가격 ('orderId': 주문 조회 및 취소)
                                        order_price = fn.get_decimal_round_off(orderbook['asks'][0][0], dec_price)
                                        order_count = fn.get_decimal_round_off(one_unit / order_price, dec_count)

                                        if orderbook['asks'][0][1] > order_count:
                                            pass
                                        elif orderbook['asks'][0][1] + orderbook['asks'][1][1] > order_count:
                                            order_price = fn.get_decimal_round_off(orderbook['asks'][1][0], dec_price)
                                        elif orderbook['asks'][0][1] + orderbook['asks'][1][1] + \
                                                orderbook['asks'][2][1] > order_count:
                                            order_price = fn.get_decimal_round_off(orderbook['asks'][2][0], dec_price)

                                        if run_mode == df.MODE_DRY:
                                            fn.web_logging(config.logger_address, "info", strategy_num,
                                                           symbol_list[s_cnt], trading_signal,
                                                           order_price, order_count, "OK")

                                        elif run_mode == df.MODE_RUN and holding_usdt < 10.0 and \
                                                balance['USDT']['free'] >= one_unit:
                                            order = exchange.create_limit_buy_order(symbol_list[s_cnt], order_count,
                                                                                   order_price)
                                            time.sleep(5)
                                            if order:
                                                if order['status'] == 'closed':
                                                    if order['filled'] > 0:
                                                        fn.web_logging(config.logger_address, "info", strategy_num,
                                                                       symbol_list[s_cnt], trading_signal,
                                                                       order_price, order_count, "OK")

                                                        holding_quantity += order['filled'] * (1.0-trading_fee)
                                                        fn.set_ini(df.WALLET_INI_PATH, strategy_num, symbol_list[s_cnt],
                                                                   holding_quantity)

                                                else:
                                                    time.sleep(10)
                                                    resp = exchange.fetch_order(order['info']['orderId'],
                                                                               symbol_list[s_cnt])
                                                    if resp['filled'] > 0:
                                                        fn.web_logging(config.logger_address, "info", strategy_num,
                                                                       symbol_list[s_cnt], trading_signal,
                                                                       order_price, order_count, "OK")

                                                        holding_quantity += resp['filled'] * (1.0-trading_fee)
                                                        fn.set_ini(df.WALLET_INI_PATH, strategy_num, symbol_list[s_cnt],
                                                                   holding_quantity)
                                                    else:
                                                        # 주문 취소
                                                        exchange.cancel_order(resp['info']['orderId'], symbol_list[s_cnt])
                                                        fn.web_logging(config.logger_address, "info", strategy_num,
                                                                       symbol_list[s_cnt], trading_signal,
                                                                       order_price, order_count, "CANCEL")

                                    except ccxt.BaseError as e:
                                        logger.error("Buy order error : ", e, exchange, symbol_list[s_cnt], order_count,
                                                     order_price)
                                        pass
                                else:
                                    # 에러 발생하는 심볼은 거래에서 제외
                                    fn.set_ini(df.SETTING_INI_PATH, 'EXCEPTION_SYMBOL', len(exception_symbol_list),
                                               symbol_list[s_cnt])
                                    exception_symbol_list.append(symbol_list[s_cnt])

                                    logger.error("Order Book error : ", exchange, symbol_list[s_cnt], order_count,
                                                 order_price)

                        elif trading_signal == df.SIGNAL_SELL or trading_signal == df.SIGNAL_NONE:
                            order_ticker = exchange.fetch_ticker(symbol_list[s_cnt])
                            holding_usdt = order_ticker['close'] * holding_quantity

                            if direction == "Long":
                                # 호가 조회
                                orderbook = exchange.fetch_order_book(symbol_list[s_cnt])
                                dec_price = fn.get_decimal_places(orderbook['bids'], 0)
                                dec_count = fn.get_decimal_places(orderbook['bids'], 1)

                                if orderbook['bids']:
                                    try:
                                        # 지정가 매도 : 티커, 주문 수량, 주문 가격 ('orderId': 주문 조회 및 취소)
                                        order_price = fn.get_decimal_round_off(orderbook['bids'][0][0], dec_price)
                                        order_count = fn.get_decimal_round_off(holding_quantity * (1.0-trading_fee),
                                                                               dec_count)

                                        if orderbook['bids'][0][1] > order_count:
                                            pass
                                        elif orderbook['bids'][0][1] + orderbook['bids'][1][1] > order_count:
                                            order_price = fn.get_decimal_round_off(orderbook['bids'][1][0], dec_price)
                                        elif orderbook['bids'][0][1] + orderbook['bids'][1][1] + \
                                                orderbook['bids'][2][1] > order_count:
                                            order_price = fn.get_decimal_round_off(orderbook['bids'][2][0], dec_price)

                                        if run_mode == df.MODE_DRY and trading_signal == df.SIGNAL_SELL:
                                            fn.web_logging(config.logger_address, "info", strategy_num,
                                                           symbol_list[s_cnt], trading_signal,
                                                           order_price, order_count, "OK")

                                        elif run_mode == df.MODE_RUN and holding_usdt > 10.0:
                                            order = exchange.create_limit_sell_order(symbol_list[s_cnt], order_count,
                                                                                    order_price)
                                            time.sleep(5)
                                            # 주문 체결 여부 : 주문 아이디, 티커
                                            if order:
                                                if order['status'] == 'closed':
                                                    if order['filled'] > 0:
                                                        fn.web_logging(config.logger_address, "info", strategy_num,
                                                                       symbol_list[s_cnt], trading_signal,
                                                                       order_price, order_count, "OK")
                                                        holding_quantity -= order['filled']

                                                        # 보유 수량이 10.0 USDT보다 작으면 거래 불가
                                                        if order_price * holding_quantity < 10.0:
                                                            holding_quantity = 0.0
                                                        fn.set_ini(df.WALLET_INI_PATH, strategy_num, symbol_list[s_cnt],
                                                                   holding_quantity)
                                                else:
                                                    time.sleep(10)
                                                    resp = exchange.fetch_order(order['info']['orderId'],
                                                                               symbol_list[s_cnt])
                                                    if resp['status'] == 'closed':
                                                        if resp['filled'] > 0:
                                                            fn.web_logging(config.logger_address, "info", strategy_num,
                                                                           symbol_list[s_cnt], trading_signal,
                                                                           order_price, order_count, "OK")
                                                            holding_quantity -= resp['filled']

                                                            # 보유 수량이 10.0 USDT보다 작으면 거래 불가
                                                            if order_price * holding_quantity < 10.0:
                                                                holding_quantity = 0.0

                                                            fn.set_ini(df.WALLET_INI_PATH, strategy_num, symbol_list[s_cnt],
                                                                       holding_quantity)
                                                    else:
                                                        # 주문 취소
                                                        exchange.cancel_order(resp['info']['orderId'], symbol_list[s_cnt])
                                                        fn.web_logging(config.logger_address, "info", strategy_num,
                                                                       symbol_list[s_cnt], trading_signal,
                                                                       order_price, order_count, "CANCEL")

                                    except ccxt.BaseError as e:
                                        logger.error('Sell Order error : ', e, exchange, symbol_list[s_cnt], order_count,
                                                     order_price)
                                        pass
                                else:
                                    # 에러 발생하는 심볼은 거래에서 제외
                                    fn.set_ini(df.SETTING_INI_PATH, 'EXCEPTION_SYMBOL', len(exception_symbol_list),
                                               symbol_list[s_cnt])
                                    exception_symbol_list.append(symbol_list[s_cnt])

                                    logger.error("Order Book error : ", exchange, symbol_list[s_cnt], order_count,
                                                 order_price)

                    elif run_mode == df.MODE_BOT:
                        order_price = 0.0
                        order_count = 0.0
                        if trading_signal == df.SIGNAL_BUY:
                            try:
                                # 호가 조회
                                orderbook = exchange.fetch_order_book(symbol_list[s_cnt])
                                if orderbook['asks']:
                                    order_price = orderbook['asks'][0][0]
                                    order_count = one_unit / order_price
                            except ccxt.BaseError as e:
                                logger.error("Fetch order error : ", e, exchange, symbol_list[s_cnt], order_count,
                                             order_price)
                                pass

                            if direction == "Long":
                                msg = "# 매매 신호 발생 #\n- 신호 유형: 매수\n- 거래 종목: " + symbol_list[s_cnt] + \
                                      "\n- 매매 전략: " + str(strategy_num) + "번\n- 매매 가격: " + str(order_price) + " USDT"
                                bot.sendMessage(chat_id=chat_id, text=msg)
                            else:
                                msg = "# 매매 신호 발생 #\n- 신호 유형: 공매도 청산\n- 거래 종목: " + symbol_list[s_cnt] + \
                                      "\n- 매매 전략: " + str(strategy_num) + "번\n- 매매 가격: " + str(order_price) + " USDT"
                                bot.sendMessage(chat_id=chat_id, text=msg)

                        elif trading_signal == df.SIGNAL_SELL:
                            try:
                                # 호가 조회
                                orderbook = exchange.fetch_order_book(symbol_list[s_cnt])
                                if orderbook['bids']:
                                    order_price = orderbook['bids'][0][0]
                                    order_count = one_unit / order_price
                            except ccxt.BaseError as e:
                                logger.error("Fetch order error : ", e, exchange, symbol_list[s_cnt], order_count,
                                             order_price)
                                pass

                            if direction == "Long":
                                msg = "# 매매 신호 발생 #\n- 신호 유형: 매도\n- 거래 종목: " + symbol_list[s_cnt] + \
                                      "\n- 매매 전략: " + str(strategy_num) + "번\n- 매매 가격: " + str(order_price) + " USDT"
                                bot.sendMessage(chat_id=chat_id, text=msg)
                            else:
                                msg = "# 매매 신호 발생 #\n- 신호 유형: 공매도\n- 거래 종목: " + symbol_list[s_cnt] + \
                                      "\n- 매매 전략: " + str(strategy_num) + "번\n- 매매 가격: " + str(order_price) + " USDT"
                                bot.sendMessage(chat_id=chat_id, text=msg)

                    # 전략 신호 저장
                    fn.set_ini(df.SIGNAL_INI_PATH, strategy_num, symbol_list[s_cnt], trading_signal)

                    if s_cnt < len(symbol_list)-1:
                        s_cnt += 1
                    else:
                        if use_dual_strategy and strategy_num != strategy2:
                            s_cnt = 0
                            strategy_num = strategy2
                        else:
                            fn.time_print("End of list..")
                            break

    def job_upbit():
        # 잔고 조회
        exchange = pyupbit.Upbit(api_key, secret_key)
        balance = exchange.get_balances()
        #print(balance)

        symbol_list = []
        if use_static_sysbol_list:
            for key in static_symbol_list:
                symbol_list.append(key)
        else:
            for i in range(rank_limit):
                symbol = fn.get_ini(df.RANK_INI_PATH, 'RANK_LIST', i, 'None')
                if symbol != 'None':
                    symbol_list.append(symbol)
        #print(symbol_list)

        total_money = 1000000.0
        etc_money = 0.0

        # 실잔고 계산
        if run_mode == df.MODE_RUN:
            total_money = 0.0
            for b in balance:
                if b['currency'] == 'KRW':
                    total_money += float(b['balance'])
                else:
                    count = float(b['balance'])
                    if count > 0:
                        total_money += float(b['avg_buy_price']) * count
                        etc_money += float(b['avg_buy_price']) * count

        print("# 운용 정보 #")
        print("- 잔고: " + str(total_money) + " 원")
        print("- 거래소: " + exchange_name)
        print("- 생성일: " + creation_day.strftime("%Y-%m-%d"))
        print("- 가동일수: " + str(duration_day.days) + "일\n")

        seed_money = float(fn.get_ini(df.SETTING_INI_PATH, 'SETTING', 'SEED_MONEY'))
        profit_money = total_money - seed_money

        print("# 자산 정보 #")
        print("- 원화 보유량: " + str(round(total_money - etc_money, 2)) + " 원")
        print("- 기타 보유량: " + str(round(etc_money, 2)) + " 원")
        print("- 수익금: " + str(round(profit_money, 2)) + " 원")
        print("- 투자원금: " + str(seed_money) + " 원\n")

        if seed_money != 0:
            asset_change_rate = float(round(profit_money / seed_money * 100.0, 2))
        else:
            asset_change_rate = 0

        print("# 자산 변동 현황 #")
        print("- 변동 기간: " + str(duration_day.days) + " 일")
        print("- 자산 변동률: " + str(asset_change_rate) + " %\n")

        one_unit = 10.0
        cash_ratio = 0
        if use_holding_cash_strategy:
            cash_ratio = 0.5

        if use_dual_strategy:
            one_unit = round((total_money / (len(symbol_list) * 2)), 2) * 0.9
        else:
            one_unit = round((total_money / len(symbol_list)), 2) * 0.9

        print("# 시스템 정보 #")
        print("- 동작 모드: " + str(run_mode))
        print("- 주문 단위: " + str(one_unit) + " 원\n")

        # 최소 주문 크기 : 10 USDT
        if one_unit >= 10.0 or run_mode != df.MODE_RUN:

            # 트레이딩 시작
            fn.time_print("Start trading to " + str(strategy1))
            s_cnt = 0
            strategy_num = strategy1
            while (True):
                read_balance = False
                trading_signal = int(fn.get_ini(df.SIGNAL_INI_PATH, strategy_num, symbol_list[s_cnt], df.SIGNAL_NONE))
                direction = "Long"
                # 잔고 읽기
                while not read_balance:
                    try:
                        balance = exchange.get_balances()
                        read_balance = True
                    except Exception as e:
                        pass

                if read_balance:
                    # df.WALLET_INI_PATH에서 잔고 받아오기
                    holding_quantity = float(fn.get_ini(df.WALLET_INI_PATH, strategy_num, symbol_list[s_cnt], 0.0))
                    total_money = 1000000.0
                    etc_money = 0.0
                    if run_mode == df.MODE_RUN:
                        total_money = 0.0
                        for b in balance:
                            if b['currency'] == 'KRW':
                                total_money += float(b['balance'])
                            else:
                                count = float(b['balance'])
                                if count > 0:
                                    total_money += float(b['avg_buy_price']) * count
                                    etc_money += float(b['avg_buy_price']) * count

                    fn.time_print("cur symbol: " + symbol_list[s_cnt])

                    if strategy_num == 0:
                        trading_signal = st.get_signal_by_donchian(exchange_name, exchange, symbol_list[s_cnt],
                                                                   run_mode, logger, 25, 14, "1d", 2, 20)
                    elif strategy_num == 1:
                        trading_signal = st.get_signal_by_donchian(exchange_name, exchange, symbol_list[s_cnt],
                                                                   run_mode, logger, 55, 20, "1d")

                    elif strategy_num == 4:
                        trading_signal = st.get_signal_by_larry_williams(exchange_name, exchange, symbol_list[s_cnt],
                                                                         run_mode, logger, "1d", 0.0005, 0.001)
                    elif strategy_num == 5:
                        trading_signal = st.get_signal_by_reverse_rsi_2(exchange_name, exchange, symbol_list[s_cnt],
                                                                        run_mode, logger, trading_signal,
                                                                        150, 10, 2, 97, "1d")
                    elif strategy_num == 101:
                        trading_signal = pst.get_signal_by_strategy1(exchange_name, exchange, symbol_list[s_cnt],
                                                                     run_mode, logger, trading_signal,
                                                                     "minute15", "minute240")
                    elif strategy_num == 102:
                        trading_signal = pst.get_signal_by_strategy2(exchange_name, exchange, symbol_list[s_cnt],
                                                                     run_mode, logger, trading_signal, "minute240",
                                                                     "day", 20, 7)
                    elif strategy_num == 103:
                        trading_signal = pst.get_signal_by_strategy3(exchange_name, exchange, symbol_list[s_cnt],
                                                                     run_mode, logger, trading_signal, trading_interval,
                                                                     0.02, 0.01)

                    if run_mode == df.MODE_DRY or run_mode == df.MODE_RUN:
                        order_price = 0.0
                        order_count = 0.0
                        if trading_signal == df.SIGNAL_BUY:
                            if total_money - etc_money < total_money * cash_ratio:
                                continue

                            order_ticker = pyupbit.get_current_price(symbol_list[s_cnt])
                            holding_usdt = order_ticker * holding_quantity

                            if direction == "Long":
                                # 호가 조회
                                orderbook = pyupbit.get_orderbook(symbol_list[s_cnt])
                                bids_asks = orderbook[0]['orderbook_units']
                                dec_price = 0
                                dec_count = 8

                                if bids_asks:
                                    try:
                                        # 지정가 매수 : 티커, 주문 수량, 주문 가격 ('orderId': 주문 조회 및 취소)
                                        order_price = fn.get_decimal_round_off(bids_asks[0]['ask_price'], dec_price)
                                        order_count = fn.get_decimal_round_off(one_unit / order_price, dec_count)

                                        if bids_asks[0]['ask_size'] > order_count:
                                            pass
                                        elif bids_asks[0]['ask_size'] + bids_asks[1]['ask_size'] > order_count:
                                            order_price = fn.get_decimal_round_off(bids_asks[1]['ask_price'], dec_price)
                                        elif orderbook[0]['ask_size'] + bids_asks[1]['ask_size'] + \
                                                bids_asks[2]['ask_size'] > order_count:
                                            order_price = fn.get_decimal_round_off(bids_asks[2]['ask_price'], dec_price)

                                        if run_mode == df.MODE_DRY:
                                            fn.web_logging(config.logger_address, "info", strategy_num,
                                                           symbol_list[s_cnt], trading_signal,
                                                           order_price, order_count, "OK")

                                        elif run_mode == df.MODE_RUN and holding_usdt < 10000.0 and \
                                                total_money - etc_money >= one_unit:
                                            order = exchange.buy_limit_order(symbol_list[s_cnt], order_price,
                                                                             order_count)
                                            time.sleep(10)
                                            if order:
                                                if order['state'] == 'done':
                                                    if float(order['volume']) > 0:
                                                        fn.web_logging(config.logger_address, "info", strategy_num,
                                                                       symbol_list[s_cnt], trading_signal,
                                                                       order_price, order_count, "OK")

                                                        holding_quantity += float(order['volume'])
                                                        fn.set_ini(df.WALLET_INI_PATH, strategy_num, symbol_list[s_cnt],
                                                                   holding_quantity)

                                                elif order['state'] == 'wait':
                                                    time.sleep(10)
                                                    resp = exchange.get_order(symbol_list[s_cnt])
                                                    if resp:
                                                        if resp[0]['state'] == 'done':
                                                            fn.web_logging(config.logger_address, "info", strategy_num,
                                                                           symbol_list[s_cnt], trading_signal,
                                                                           order_price, order_count, "OK")

                                                            holding_quantity += float(resp[0]['volume'])
                                                            fn.set_ini(df.WALLET_INI_PATH, strategy_num, symbol_list[s_cnt],
                                                                       holding_quantity)
                                                        elif resp[0]['state'] == 'wait':
                                                            # 주문 취소
                                                            exchange.cancel_order(resp['uuid'], symbol_list[s_cnt])
                                                            fn.web_logging(config.logger_address, "info", strategy_num,
                                                                           symbol_list[s_cnt], trading_signal,
                                                                           order_price, order_count, "CANCEL")
                                                    else:
                                                        fn.web_logging(config.logger_address, "info", strategy_num,
                                                                       symbol_list[s_cnt], trading_signal,
                                                                       order_price, order_count, "OK")

                                                        holding_quantity += float(order['volume'])
                                                        fn.set_ini(df.WALLET_INI_PATH, strategy_num, symbol_list[s_cnt],
                                                                   holding_quantity)
                                    except Exception as x:
                                        logger.error("Buy order error : ", x.__class__.__name__, exchange,
                                                     symbol_list[s_cnt], order_count, order_price)
                                        pass
                                else:
                                    # 에러 발생하는 심볼은 거래에서 제외
                                    fn.set_ini(df.SETTING_INI_PATH, 'EXCEPTION_SYMBOL', len(exception_symbol_list),
                                               symbol_list[s_cnt])
                                    exception_symbol_list.append(symbol_list[s_cnt])

                                    logger.error("Order Book error : ", exchange, symbol_list[s_cnt], order_count,
                                                 order_price)

                        elif trading_signal == df.SIGNAL_SELL or trading_signal == df.SIGNAL_NONE:
                            order_ticker = pyupbit.get_current_price(symbol_list[s_cnt])
                            holding_usdt = order_ticker * holding_quantity

                            if direction == "Long":
                                # 호가 조회
                                orderbook = pyupbit.get_orderbook(symbol_list[s_cnt])
                                bids_asks = orderbook[0]['orderbook_units']
                                dec_price = 0
                                dec_count = 8

                                if bids_asks:
                                    try:
                                        # 지정가 매도 : 티커, 주문 수량, 주문 가격 ('orderId': 주문 조회 및 취소)
                                        order_price = fn.get_decimal_round_off(bids_asks[0]['bid_price'], dec_price)
                                        order_count = fn.get_decimal_round_off(holding_quantity,
                                                                               dec_count)

                                        if bids_asks[0]['bid_size'] > order_count:
                                            pass
                                        elif bids_asks[0]['bid_size'] + bids_asks[1]['bid_size'] > order_count:
                                            order_price = fn.get_decimal_round_off(bids_asks[1]['bid_price'], dec_price)
                                        elif bids_asks[0]['bid_size'] + bids_asks[1]['bid_size'] + \
                                                bids_asks[2]['bid_size'] > order_count:
                                            order_price = fn.get_decimal_round_off(bids_asks[2]['bid_price'], dec_price)

                                        if run_mode == df.MODE_DRY and trading_signal == df.SIGNAL_SELL:
                                            fn.web_logging(config.logger_address, "info", strategy_num,
                                                           symbol_list[s_cnt], trading_signal,
                                                           order_price, order_count, "OK")

                                        elif run_mode == df.MODE_RUN and holding_usdt > 10000.0:
                                            order = exchange.sell_limit_order(symbol_list[s_cnt], order_price,
                                                                              order_count)
                                            time.sleep(10)
                                            # 주문 체결 여부 : 주문 아이디, 티커
                                            if order:
                                                if order['state'] == 'done':
                                                    if float(order['volume']) > 0:
                                                        fn.web_logging(config.logger_address, "info", strategy_num,
                                                                       symbol_list[s_cnt], trading_signal,
                                                                       order_price, order_count, "OK")
                                                        holding_quantity -= float(order['volume'])

                                                        # 보유 수량이 10.0 USDT보다 작으면 거래 불가
                                                        if order_price * holding_quantity < 10.0:
                                                            holding_quantity = 0.0
                                                        fn.set_ini(df.WALLET_INI_PATH, strategy_num, symbol_list[s_cnt],
                                                                   holding_quantity)
                                                elif order['state'] == 'wait':
                                                    time.sleep(10)
                                                    resp = exchange.get_order(symbol_list[s_cnt])
                                                    if resp:
                                                        if resp[0]['state'] == 'done':
                                                            if float(resp['volume']) > 0:
                                                                fn.web_logging(config.logger_address, "info", strategy_num,
                                                                               symbol_list[s_cnt], trading_signal,
                                                                               order_price, order_count, "OK")
                                                                holding_quantity -= float(resp[0]['volume'])

                                                                # 보유 수량이 10.0 USDT보다 작으면 거래 불가
                                                                if order_price * holding_quantity < 10.0:
                                                                    holding_quantity = 0.0

                                                                fn.set_ini(df.WALLET_INI_PATH, strategy_num, symbol_list[s_cnt],
                                                                           holding_quantity)
                                                        elif resp[0]['state'] == 'wait':
                                                            # 주문 취소
                                                            exchange.cancel_order(resp['uuid'])
                                                            fn.web_logging(config.logger_address, "info", strategy_num,
                                                                           symbol_list[s_cnt], trading_signal,
                                                                           order_price, order_count, "CANCEL")
                                                    else:
                                                        fn.web_logging(config.logger_address, "info", strategy_num,
                                                                       symbol_list[s_cnt], trading_signal,
                                                                       order_price, order_count, "OK")
                                                        holding_quantity -= float(order['volume'])

                                                        # 보유 수량이 10.0 USDT보다 작으면 거래 불가
                                                        if order_price * holding_quantity < 10.0:
                                                            holding_quantity = 0.0
                                                        fn.set_ini(df.WALLET_INI_PATH, strategy_num, symbol_list[s_cnt],
                                                                   holding_quantity)
                                    except Exception as x:
                                        logger.error('Sell Order error : ', x.__class__.__name__, exchange,
                                                     symbol_list[s_cnt], order_count, order_price)
                                        pass
                                else:
                                    # 에러 발생하는 심볼은 거래에서 제외
                                    fn.set_ini(df.SETTING_INI_PATH, 'EXCEPTION_SYMBOL', len(exception_symbol_list),
                                               symbol_list[s_cnt])
                                    exception_symbol_list.append(symbol_list[s_cnt])

                                    logger.error("Order Book error : ", exchange, symbol_list[s_cnt], order_count,
                                                 order_price)


                    # 전략 신호 저장
                    fn.set_ini(df.SIGNAL_INI_PATH, strategy_num, symbol_list[s_cnt], trading_signal)

                    if s_cnt < len(symbol_list) - 1:
                        s_cnt += 1
                    else:
                        if use_dual_strategy and strategy_num != strategy2:
                            s_cnt = 0
                            strategy_num = strategy2
                        else:
                            fn.time_print("End of list..")
                            break

    def job_get_coin_rank():
        now = datetime.now()
        update_day = datetime.strptime(fn.get_ini(df.RANK_INI_PATH, 'SETTING', 'UPDATE_DAY',
                                                  '1900/01/01 00:00:00'), '%Y/%m/%d %H:%M:%S')
        if now > update_day + timedelta(hours=3):
            fn.set_ini(df.RANK_INI_PATH, 'SETTING', 'UPDATE_DAY', now.strftime('%Y/%m/%d %H:%M:%S'))

            # ticker 조회
            markets = pyupbit.get_tickers(fiat="KRW")

            # coin rank 조회
            rank_list = {}
            for key in markets:
                if 'KRW-' in key:
                    cur_ohlcvs = pyupbit.get_ohlcv(key, interval='minute240', count=1)
                    if cur_ohlcvs['close'][0]:
                        #print(" - rank update: " + cur_ohlcvs['time'][0])
                        rank_list[key] = cur_ohlcvs['close'][0] * cur_ohlcvs['volume'][0]
                    time.sleep(0.5)

            sorted(rank_list, key=lambda rank: rank[1], reverse=True)

            i = 0
            for key in rank_list.keys():
                fn.set_ini(df.RANK_INI_PATH, 'RANK_LIST', i, key)
                i += 1

    def job_get_expected_value():
        now = datetime.now()
        update_day = datetime.strptime(fn.get_ini(df.STRATEGY_INI_PATH, 'SETTING_103', 'UPDATE_DAY',
                                                  '1900/01/01 00:00:00'), '%Y/%m/%d %H:%M:%S')
        if now > update_day + timedelta(hours=3):
            fn.set_ini(df.STRATEGY_INI_PATH, 'SETTING_103', 'UPDATE_DAY', now.strftime('%Y/%m/%d %H:%M:%S'))

            # 잔고 조회
            exchange = pyupbit.Upbit(api_key, secret_key)

            # ticker 조회
            markets = pyupbit.get_tickers(fiat="KRW")

            for key in markets:
                pst.get_signal_by_strategy3_sub(exchange_name, exchange, key, trading_interval)

    if run_mode == df.MODE_SIM:
        if exchange_name == "Binance":
            job_binance()
        elif exchange_name == "Upbit":
            #job_get_coin_rank()
            #job_get_expected_value()
            job_upbit()
    else:
        sched = BlockingScheduler()
        if exchange_name == "Binance":
            if trading_interval == "1d":
                sched.add_job(job_binance, 'cron', hour='9', minute='0', second='1')
            elif trading_interval == "1h":
                sched.add_job(job_binance, 'cron', minute='0', second='1')
            elif trading_interval == "15m":
                sched.add_job(job_binance, 'cron', minute='0,15,30,45', second='1')
            elif trading_interval == "5m":
                sched.add_job(job_binance, 'cron', minute='0,5,10,15,20,25,30,35,40,45,50,55', second='1')
            elif trading_interval == "1m":
                sched.add_job(job_binance, 'cron', second='1')

        elif exchange_name == "Upbit":
            #job_get_coin_rank()
            #job_get_expected_value()
            #sched.add_job(job_get_coin_rank, 'cron', hour='1,5,9,13,17,21', minute='0', second='1')
            #sched.add_job(job_get_expected_value, 'cron', hour='1,5,9,13,17,21', minute='0', second='1')
            if trading_interval == "1d":
                sched.add_job(job_upbit, 'cron', hour='9', minute='0', second='1')
            elif trading_interval == "4h":
                sched.add_job(job_upbit, 'cron', hour='1,5,9,13,17,21', minute='0', second='1')
            elif trading_interval == "1h":
                sched.add_job(job_upbit, 'cron', minute='0', second='1')
            elif trading_interval == "15m":
                sched.add_job(job_upbit, 'cron', minute='0,15,30,45', second='1')
            elif trading_interval == "5m":
                sched.add_job(job_upbit, 'cron', minute='0,5,10,15,20,25,30,35,40,45,50,55', second='1')
            elif trading_interval == "1m":
                sched.add_job(job_upbit, 'cron', second='1')

        sched.start()


except KeyboardInterrupt:
    fn.time_print("\b\bCtrl+C를 눌러서 프로그램을 종료합니다.")


import configparser
from datetime import datetime
from math import log
import pyupbit
import matplotlib.pyplot as plt

import definition as df
import function as fn

def get_signal_by_strategy1(exchange_name, exchange, symbol, run_mode, logger, cur_signal,
                    ticker="15m",
                    day_ticker="6h",
                    stop_loss_ratio=0.03,
                    ):
    INI = configparser.ConfigParser()
    INI.read(df.STRATEGY_INI_PATH)

    if exchange_name == "Binance":
        cur_ohlcvs = exchange.fetch_ohlcv(symbol, ticker)
        curd_ohlcvs = exchange.fetch_ohlcv(symbol, day_ticker)
        btc_ohlcvs = exchange.fetch_ohlcv("BTC/USDT", ticker)
    elif exchange_name == "Upbit":
        if ticker == "1d":
            ticker = "day"
        elif ticker == "1h":
            ticker = "minute60"
        elif ticker == "15m":
            ticker = "minute15"
        elif ticker == "5m":
            ticker = "minute5"
        elif ticker == "1m":
            ticker = "minute1"
        cur_ohlcvs = pyupbit.get_ohlcv(symbol, interval=ticker)
        curd_ohlcvs = pyupbit.get_ohlcv(symbol, interval=day_ticker)
        btc_ohlcvs = pyupbit.get_ohlcv("KRW-BTC", interval=ticker)

    time = []
    high = []
    low = []
    open = []
    close = []
    if exchange_name == "Binance":
        for ohlc in cur_ohlcvs:
            time.append(ohlc[df.OHLCV_TIMESTAMP])
            high.append(ohlc[df.OHLCV_HIGH])
            low.append(ohlc[df.OHLCV_LOW])
            open.append(ohlc[df.OHLCV_OPEN])
            close.append(ohlc[df.OHLCV_CLOSE])
    elif exchange_name == "Upbit":
        time = cur_ohlcvs.index
        high = cur_ohlcvs['high']
        low = cur_ohlcvs['low']
        open = cur_ohlcvs['open']
        close = cur_ohlcvs['close']

    timed = []
    highd = []
    lowd = []
    opend = []
    closed = []
    if exchange_name == "Binance":
        for ohlc in curd_ohlcvs:
            timed.append(ohlc[df.OHLCV_TIMESTAMP])
            highd.append(ohlc[df.OHLCV_HIGH])
            lowd.append(ohlc[df.OHLCV_LOW])
            opend.append(ohlc[df.OHLCV_OPEN])
            closed.append(ohlc[df.OHLCV_CLOSE])
    elif exchange_name == "Upbit":
        timed = curd_ohlcvs.index
        highd = curd_ohlcvs['high']
        lowd = curd_ohlcvs['low']
        opend = curd_ohlcvs['open']
        closed = curd_ohlcvs['close']

    day_range = []
    for i in range(len(curd_ohlcvs)):
        day_range.append(highd[i] - lowd[i])

    # ma range
    atr_len = 50
    ma_day_range = []
    for i in range(len(curd_ohlcvs)):
        if i < atr_len:
            ma_day_range.append(999999.0)
        else:
            ma_day_range.append(max(day_range[i - atr_len + 1:i]))

    # noise filter
    noise_period = 20
    noise = []
    for i in range(len(cur_ohlcvs)):
        if high[i] - low[i] > 0:
            noise.append(1 - abs((open[i] - close[i]) / (high[i] - low[i])))
        else:
            noise.append(0)

    # btc 일봉 ma
    btc_close = []
    if exchange_name == "Binance":
        for ohlc in btc_ohlcvs:
            btc_close.append(ohlc[df.OHLCV_CLOSE])
    elif exchange_name == "Upbit":
        for i in range(len(btc_ohlcvs.index)):
            btc_close.append(float(btc_ohlcvs['close'][i]))

    btc_ma = []
    for i in range(len(btc_close)):
        if i < 7:
            btc_ma.append(btc_close[i])
        else:
            btc_ma.append(sum(btc_close[i - 7 + 1:i]) / len(btc_close[i - 7 + 1:i]))


    # cur_volatility 계산 : ohlcvs 최근값은 아직 확정된 값이 아님
    day_index = len(curd_ohlcvs) - 2
    noise_mean = sum(noise[day_index - noise_period + 1:day_index]) / len(noise[day_index - noise_period + 1:day_index])
    cur_volatility = noise_mean * day_range[day_index]

    len1 = 3
    len2 = 2.2
    len3 = 2.9
    brk = 3
    big = 8
    before_index = len(cur_ohlcvs) - 2
    cur_index = len(cur_ohlcvs) - 1
    curd_index = len(curd_ohlcvs) - 1
    if exchange_name == "Binance":
        cur_price = exchange.fetch_ticker(symbol)['close']
        btc_price = exchange.fetch_ticker('BTC/USDT')['close']
    elif exchange_name == "Upbit":
        cur_price = pyupbit.get_current_price(symbol)
        btc_price = pyupbit.get_current_price('KRW-BTC')
    if cur_signal == df.SIGNAL_BUY or cur_signal == df.SIGNAL_HOLD:
        hhv = float(fn.get_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_HHV_101', high[cur_index]))

        if hhv < high[before_index]:
            hhv = high[before_index]

        entry_price = float(fn.get_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_PRICE_101', open[cur_index]))

        clear_condition = False

        # 청산 1. break down or stop loss
        if not clear_condition:
            clear_condition = cur_price <= opend[day_index] - cur_volatility
            if clear_condition:
                fn.time_print("- break_down: " + str(opend[day_index] - cur_volatility))

        if not clear_condition:
            clear_condition = cur_price <= entry_price * (1.0 - stop_loss_ratio)
            if clear_condition:
                fn.time_print("- stop_loss: " + str(entry_price * (1.0 - stop_loss_ratio)))

        # 청산 2. 매수 추적
        if not clear_condition:
            # 매수 시점부터 계속 최고가를 기록
            fn.set_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_HHV', high[before_index])

            clear_condition = cur_price <= hhv - ma_day_range[day_index] * len1
            if clear_condition:
                fn.time_print("- clear price 2: " + str(hhv - ma_day_range[day_index] * len1))

        # 청산 3. 매수 변동성
        if not clear_condition:
            clear_condition = cur_price <= close[before_index] - ma_day_range[day_index] * len2
            if clear_condition:
                fn.time_print("- clear price 3: " + str(close[before_index] - ma_day_range[day_index] * len2))

        # 청산 4. 매수 손익분기
        if not clear_condition:
            if hhv >= entry_price + day_range[day_index] * brk:
                clear_condition = cur_price <= entry_price + day_range[day_index] * len3
            if clear_condition:
                fn.time_print("- clear price 4: " + str(entry_price + day_range[day_index] * len3))

        # 청산 5. 매수추적1
        if not clear_condition:
            if hhv >= entry_price + day_range[day_index] * brk:
                clear_condition = cur_price <= hhv - day_range[day_index] * len3
            if clear_condition:
                fn.time_print("- clear price 5: " + str(hhv - day_range[day_index] * len3))

        # 청산 6. 매수 초과수익
        if not clear_condition:
            if hhv >= entry_price + day_range[day_index] * big:
                # 봉 3개의 최저가를 기록
                llv = low[before_index]
                for i in range(3):
                    if llv > low[before_index - i]:
                        llv = low[before_index - i]

                clear_condition = cur_price <= llv
                if clear_condition:
                    fn.time_print("- clear price 6: " + str(llv))

        # 청산 7. 일정 시간 경과
        if not clear_condition:
            # 매도 시점
            now = datetime.now()
            entry_time = datetime.strptime(fn.get_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_TIME_101',
                                                      now.strftime('%Y/%m/%d %H:%M:%S')), '%Y/%m/%d %H:%M:%S')
            clear_condition = timed[curd_index] > entry_time
            if clear_condition:
                fn.time_print("- clear price 7: " + str(cur_price))

        # 청산 8. 비트코인 7일 이평선 이탈
        if not clear_condition:
            clear_condition = btc_price < btc_ma[len(btc_ohlcvs) - 1]
            if clear_condition:
                fn.time_print("- clear price 8: " + str(cur_price))

        if clear_condition:
            cur_signal = df.SIGNAL_SELL

        else:
            cur_signal = df.SIGNAL_HOLD

    else:
        # 매도 시점
        entry_time = datetime.strptime(fn.get_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_TIME_101',
                                                  '1900/01/01 00:00:00'), '%Y/%m/%d %H:%M:%S')

        # 조건 1: 이전 거래 후 일봉 변경 확인
        entry_condition1 = entry_time < timed[curd_index]
        if not entry_condition1:
            fn.time_print("- buy condition 1 fail: " + entry_time.strftime('%Y/%m/%d %H:%M:%S') + " < " +
                          timed[curd_index].strftime('%Y/%m/%d %H:%M:%S'))

        # 조건 2: 변동성 돌파
        entry_condition2 = cur_price >= opend[day_index] + cur_volatility
        if not entry_condition2:
            fn.time_print("- buy condition 2 fail: " + str(cur_price) + " >= " + str(opend[day_index] + cur_volatility))

        # 조건 3: 변동성이 전일 종가 1% 이상
        entry_condition3 = day_range[day_index] / opend[day_index] * 100.0 > 1.0
        if not entry_condition3:
            fn.time_print("- buy condition 3 fail: " + str(day_range[day_index] / opend[day_index] * 100.0) + " > 1.0")

        # 조건 4: 비트코인 7일 이평선 이탈 여부
        entry_condition4 = btc_price > btc_ma[len(btc_ohlcvs) - 1]
        if not entry_condition4:
            fn.time_print("- buy condition 4 fail: " + str(btc_price) + " > " + str(btc_ma[len(btc_ohlcvs) - 1]))

        break_up = entry_condition1 and entry_condition2 and entry_condition3 and entry_condition4

        # 매수 전, 당일 시가까지 아는 상황
        if break_up:
            cur_signal = df.SIGNAL_BUY

            # 매수 시점 기록
            now = datetime.now()
            fn.set_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_TIME_101', now.strftime('%Y/%m/%d %H:%M:%S'))

            # 매수 시점부터 계속 최고가를 기록
            fn.set_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_HHV_101', high[before_index])
            fn.set_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_PRICE_101', cur_price)

            fn.time_print("- cur price : " + str(cur_price))
            fn.time_print("- day open price : " + str(opend[day_index]))
            fn.time_print("- cur volatility : " + str(cur_volatility))
        else:
            cur_signal = df.SIGNAL_NONE

    return cur_signal


def get_signal_by_strategy2(exchange_name, exchange, symbol, run_mode, logger, cur_signal,
                    ticker="15m",
                    day_ticker="1d",
                    enter_period=60,
                    exit_period=10,
                    commission=0.001,
                    slipage=0.0015
                    ):
    INI = configparser.ConfigParser()
    INI.read(df.STRATEGY_INI_PATH)

    if exchange_name == "Binance":
        cur_ohlcvs = exchange.fetch_ohlcv(symbol, ticker)
        btc_ohlcvs = exchange.fetch_ohlcv("BTC/USDT", ticker)
    elif exchange_name == "Upbit":
        if ticker == "1d":
            ticker = "day"
        elif ticker == "1h":
            ticker = "minute60"
        elif ticker == "15m":
            ticker = "minute15"
        elif ticker == "5m":
            ticker = "minute5"
        elif ticker == "1m":
            ticker = "minute1"
        cur_ohlcvs = pyupbit.get_ohlcv(symbol, interval=ticker)
        btc_ohlcvs = pyupbit.get_ohlcv("KRW-BTC", interval=ticker)

    time = []
    high = []
    low = []
    open = []
    close = []
    volume = []
    if exchange_name == "Binance":
        for ohlc in cur_ohlcvs:
            time.append(ohlc[df.OHLCV_TIMESTAMP])
            high.append(ohlc[df.OHLCV_HIGH])
            low.append(ohlc[df.OHLCV_LOW])
            open.append(ohlc[df.OHLCV_OPEN])
            close.append(ohlc[df.OHLCV_CLOSE])
            volume.append(ohlc[df.OHLCV_VOLUME])
    elif exchange_name == "Upbit":
        time = cur_ohlcvs.index
        close = cur_ohlcvs['close']
        volume = cur_ohlcvs['volume']

    ma_enter = []
    ma_exit = []
    for i in range(len(cur_ohlcvs)):
        if i < enter_period:
            ma_enter.append(0.0)
        else:
            ma_enter.append(sum(close[i - enter_period + 1:i]) / len(close[i - enter_period + 1:i]))

        if i < exit_period:
            ma_exit.append(0.0)
        else:
            ma_exit.append(sum(close[i - exit_period + 1:i]) / len(close[i - exit_period + 1:i]))

    # btc 일봉 ma
    btc_close = []
    if exchange_name == "Binance":
        for ohlc in btc_ohlcvs:
            btc_close.append(ohlc[df.OHLCV_CLOSE])
    elif exchange_name == "Upbit":
        for i in range(len(btc_ohlcvs.index)):
            btc_close.append(float(btc_ohlcvs['close'][i]))

    btc_ma = []
    for i in range(len(btc_close)):
        if i < 7:
            btc_ma.append(btc_close[i])
        else:
            btc_ma.append(sum(btc_close[i - 7 + 1:i]) / len(btc_close[i - 7 + 1:i]))

    if run_mode == df.MODE_SIM:
        trading_odds = 0.0
        trading_count = 0.0
        trading_price_stamp = 0
        virtual_balance = 100
        virtual_balance_ctrl = 0
        virtual_balance_stamp = 100
        holding_balance = 100
        past_trading_profit = 0
        cur_signal = df.SIGNAL_NONE
        result = []
        holding_result = []
        for i in range(len(cur_ohlcvs)):
            if i >= enter_period+1:

                break_up = ma_exit[i-1] >= ma_enter[i-1] and ma_exit[i-2] < ma_enter[i-2]
                break_down = ma_exit[i-1] < ma_enter[i-1]
                stop_loss = close[i] < trading_price_stamp * 0.97

                if cur_signal == df.SIGNAL_BUY:
                    cur_signal = df.SIGNAL_HOLD
                elif cur_signal == df.SIGNAL_SELL:
                    cur_signal = df.SIGNAL_NONE

                if cur_signal == df.SIGNAL_NONE:
                    if past_trading_profit <= 0:
                        # 매수 포지션
                        if break_up:
                            cur_signal = df.SIGNAL_BUY
                            if virtual_balance_stamp * 0.9 > virtual_balance:
                                virtual_balance_ctrl = virtual_balance * 0.2
                                virtual_balance *= 0.8
                            else:
                                virtual_balance += virtual_balance_ctrl
                                virtual_balance_ctrl = 0

                            virtual_balance *= 1.0 - commission - slipage
                            virtual_balance_stamp = virtual_balance + virtual_balance_ctrl
                            trading_price_stamp = close[i]
                            if run_mode == df.MODE_SIM:
                                fn.time_print("[" + time[i].strftime('%Y-%m-%d %H:%M') + "] BUY: " +
                                              str(round(close[i], 2)) + " / BREAK_UP: " +
                                              str(round(ma_enter[i-1], 2)) + " / STOP_LOSS: " +
                                              str(round(trading_price_stamp * 0.97, 2)))
                    else:
                        past_trading_profit = 0

                elif cur_signal == df.SIGNAL_HOLD:
                    if break_down or stop_loss:
                        cur_signal = df.SIGNAL_SELL

                        trading_count += 1.0
                        past_trading_profit = (close[i] - trading_price_stamp) / trading_price_stamp
                        if past_trading_profit > 0:
                            trading_odds += 1.0

                        virtual_balance *= 1.0 - commission - slipage + (close[i] - close[i - 1]) / close[i - 1]
                        virtual_balance += virtual_balance_ctrl
                        virtual_balance_ctrl = 0
                        trading_price_stamp = 0

                        if run_mode == df.MODE_SIM:
                            fn.time_print("[" + time[i].strftime('%Y-%m-%d %H:%M') + "] CLEAR: " +
                                          str(round(close[i], 2)) + " / BREAK_DOWN: " +
                                          str(round(ma_enter[i - 1], 2)) + " / STOP_LOSS: " +
                                          str(round(trading_price_stamp * 0.97, 2)))
                            fn.time_print("=> TOTAL: " + str(round(virtual_balance, 2)) + " / INVESTED: " +
                                          str(round(virtual_balance_stamp, 2)))
                    else:
                        cur_signal = df.SIGNAL_HOLD
                        virtual_balance *= (1 + (close[i] - close[i - 1]) / close[i - 1])

                # print("balance: " + str(virtual_balance) + ", close: " + str(total_close[index-1]))
                holding_balance *= (1 + (close[i] - close[i - 1]) / close[i - 1])

            result.append(virtual_balance + virtual_balance_ctrl)
            holding_result.append(holding_balance)

            fn.time_print("[" + time[i].strftime('%Y-%m-%d %H:%M') + "] LAST: " +
                          str(round(close[len(close) - 1], 2)) + " / BREAK_DOWN: " +
                          str(round(ma_enter[len(ma_enter) - 1], 2)) + " / STOP_LOSS: " +
                          str(round(close[len(close) - 1], 2)))
            fn.time_print("=> TOTAL: " + str(round(virtual_balance, 2)) + " / INVESTED: " +
                          str(round(virtual_balance_stamp, 2)))

        if trading_count > 0:
            fn.time_print("- 매매 횟수 : " + str(trading_count) + " / 매매 승률 : " + str(
                round(trading_odds / trading_count * 100)) + ("%"))
        else:
            fn.time_print("- 매매 횟수 : 0 / 매매 승률 : 0%")

        label_strategy = "Alpha trading strategy (MA60/VOLUME) " + str(enter_period)
        plt.plot(time, result, label=label_strategy)
        plt.plot(time, holding_result, label='Buy and hold strategy')
        plt.legend(loc=2)

        plt.xlabel('Time')
        plt.ylabel('Value')
        plot_title = symbol + " Backtesting Result"
        plt.title(plot_title)
        plt.xticks([time[0], time[round((len(time)) / 2)], time[len(time) - 1]])
        # plt.xticks(rotation='vertical')
        plt.show()
        return df.SIGNAL_NONE
    else:
        last_index = len(cur_ohlcvs) - 1
        if exchange_name == "Binance":
            cur_price = exchange.fetch_ticker(symbol)['close']
            #btc_price = exchange.fetch_ticker('BTC/USDT')['close']
        elif exchange_name == "Upbit":
            cur_price = pyupbit.get_current_price(symbol)
            #btc_price = pyupbit.get_current_price('KRW-BTC')

        if cur_signal == df.SIGNAL_BUY:
            cur_signal = df.SIGNAL_HOLD
        elif cur_signal == df.SIGNAL_SELL:
            cur_signal = df.SIGNAL_NONE

        if cur_signal == df.SIGNAL_NONE:
            break_up = ma_exit[last_index] >= ma_enter[last_index] and \
                       ma_exit[last_index - 1] < ma_enter[last_index - 1]

            if break_up:
                cur_signal = df.SIGNAL_BUY

                # 매수 시점 기록
                now = datetime.now()
                fn.set_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_TIME_102', now.strftime('%Y/%m/%d %H:%M:%S'))
                fn.set_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_PRICE_102', cur_price)

                fn.time_print("- cur price : " + str(cur_price))

        elif cur_signal == df.SIGNAL_HOLD:
            # 매도 시점
            entry_time = datetime.strptime(fn.get_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_TIME_101',
                                                      '1900/01/01 00:00:00'), '%Y/%m/%d %H:%M:%S')
            entry_price = float(fn.get_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_PRICE_101', cur_price))

            break_down = ma_exit[last_index] < ma_enter[last_index]
            stop_loss = cur_price < entry_price * 0.97

            if break_down or stop_loss:
                cur_signal = df.SIGNAL_SELL

        else:
            cur_signal = df.SIGNAL_HOLD

        return cur_signal


def get_signal_by_strategy3(exchange_name, exchange, symbol, run_mode, logger, cur_signal,
                    ticker="1m",
                    k=0.02,
                    loss=0.01,
                    commission=0.001,
                    slipage=0.0015
                    ):
    INI = configparser.ConfigParser()
    INI.read(df.STRATEGY_INI_PATH)

    if cur_signal == df.SIGNAL_BUY:
        cur_signal = df.SIGNAL_HOLD
    elif cur_signal == df.SIGNAL_SELL:
        cur_signal = df.SIGNAL_NONE

    if exchange_name == "Binance":
        cur_ohlcvs = exchange.fetch_ohlcv(symbol, ticker)
    elif exchange_name == "Upbit":
        if ticker == "1d":
            ticker = "day"
        elif ticker == "1h":
            ticker = "minute60"
        elif ticker == "15m":
            ticker = "minute15"
        elif ticker == "5m":
            ticker = "minute5"
        elif ticker == "1m":
            ticker = "minute1"
        cur_ohlcvs = pyupbit.get_ohlcv(symbol, interval=ticker)

    #time = []
    #high = []
    #low = []
    open = []
    close = []
    #volume = []
    if exchange_name == "Binance":
        for ohlc in cur_ohlcvs:
            #time.append(ohlc[df.OHLCV_TIMESTAMP])
            #high.append(ohlc[df.OHLCV_HIGH])
            #low.append(ohlc[df.OHLCV_LOW])
            open.append(ohlc[df.OHLCV_OPEN])
            close.append(ohlc[df.OHLCV_CLOSE])
            #volume.append(ohlc[df.OHLCV_VOLUME])
    elif exchange_name == "Upbit":
        #time = cur_ohlcvs.index
        #high = cur_ohlcvs['high']
        #low = cur_ohlcvs['low']
        open = cur_ohlcvs['open']
        close = cur_ohlcvs['close']
        #volume = cur_ohlcvs['volume']

    last_index = len(cur_ohlcvs) - 2
    if exchange_name == "Binance":
        cur_price = exchange.fetch_ticker(symbol)['close']
    elif exchange_name == "Upbit":
        cur_price = pyupbit.get_current_price(symbol)

    total_trials = {}
    for i in range(-20, 21):
        if i != 0:
            total_trials[i] = int(fn.get_ini(df.STRATEGY_INI_PATH, ticker, i))

    positive_total_item = 0
    negative_total_item = 0
    positive_sum_value = 0
    negative_sum_value = 0
    expected_value = 0
    number_of_trials = sum(total_trials.values())
    for key, value in total_trials.items():
        expected_value += key * (value / number_of_trials)
        if key > 0:
            positive_total_item += key * value
            positive_sum_value += value
        else:
            negative_total_item += key * value
            negative_sum_value += value

    """
    print("- 양신호 평균: " + str(round(positive_total_item / positive_sum_value, 2)))
    print("- 음신호 평균: " + str(round(negative_total_item / negative_sum_value, 2)))
    print("- 전체 신호 기댓값: " + str(round(expected_value, 2)))
    print(total_trials)
    """

    if cur_signal == df.SIGNAL_NONE:
        threshold_key = 0
        threshold_value = round(negative_sum_value * (1 - k))
        temp_value = negative_sum_value
        for i in range(-20, 0):
            if i != 0:
                if temp_value - total_trials[i] > threshold_value:
                    threshold_key = i
        print(" - Negative Threshold: " + str(threshold_key))

        if threshold_key < 0:
            private_trials = {}
            for i in range(-20, 21):
                if i != 0:
                    private_trials[i] = 0

            private_trial_count = 1
            for i in range(len(cur_ohlcvs)-1):
                if i > 1:
                    candle_range = close[i - 1] - open[i - 1]
                    candle_range2 = close[i] - open[i]
                    if candle_range * candle_range2 > 0:
                        private_trial_count += 1
                    else:
                        if candle_range > 0:
                            private_trials[private_trial_count] += 1
                        else:
                            private_trials[-1 * private_trial_count] += 1

                        private_trial_count = 1

            print(" - Private Candle Range: " + str(close[last_index] - open[last_index]))
            print(" - Private Trial Count: " + str(private_trial_count))

            break_up = close[last_index] - open[last_index] < 0 and private_trial_count >= abs(threshold_key)

            if break_up:
                cur_signal = df.SIGNAL_BUY

                # 매수 시점 기록
                now = datetime.now()
                fn.set_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_TIME_103', now.strftime('%Y/%m/%d %H:%M:%S'))
                fn.set_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_PRICE_103', cur_price)

    elif cur_signal == df.SIGNAL_HOLD:
        """
        private_trials = {}
        for i in range(-20, 21):
            if i != 0:
                private_trials[i] = 0

        private_trial_count = 1
        for i in range(len(cur_ohlcvs)-1):
            if i > 1:
                candle_range = close[i - 1] - open[i - 1]
                candle_range2 = close[i] - open[i]
                if candle_range * candle_range2 > 0:
                    private_trial_count += 1
                else:
                    if candle_range > 0:
                        private_trials[private_trial_count] += 1
                    else:
                        private_trials[-1 * private_trial_count] += 1

                    private_trial_count = 1

        print(" - Positive Threshold: " + str(round(positive_total_item / positive_sum_value)))
        print(" - Private Candle Range: " + str(close[last_index] - open[last_index]))
        print(" - Private Trial Count: " + str(private_trial_count))

        break_down = close[last_index] - open[last_index] > 0
        
        entry_time = datetime.strptime(fn.get_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_TIME_103',
                                                  '1900/01/01 00:00:00'), '%Y/%m/%d %H:%M:%S')
        entry_price = float(fn.get_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_PRICE_103', cur_price))

        stop_loss = cur_price < entry_price * (1 - loss)

        if break_down or stop_loss:
            cur_signal = df.SIGNAL_SELL
        """
        # 매수 후 바로 매도
        cur_signal = df.SIGNAL_SELL
        print(" - Sell")


    return cur_signal


def get_signal_by_strategy3_sub(exchange_name, exchange, symbol,
                                ticker="1m"
                                ):
    INI = configparser.ConfigParser()
    INI.read(df.STRATEGY_INI_PATH)

    if exchange_name == "Binance":
        cur_ohlcvs = exchange.fetch_ohlcv(symbol, ticker)
    elif exchange_name == "Upbit":
        if ticker == "1d":
            ticker = "day"
        elif ticker == "1h":
            ticker = "minute60"
        elif ticker == "15m":
            ticker = "minute15"
        elif ticker == "5m":
            ticker = "minute5"
        elif ticker == "1m":
            ticker = "minute1"
        cur_ohlcvs = pyupbit.get_ohlcv(symbol, interval=ticker)

    open = []
    close = []
    if exchange_name == "Binance":
        for ohlc in cur_ohlcvs:
            open.append(ohlc[df.OHLCV_OPEN])
            close.append(ohlc[df.OHLCV_CLOSE])
    elif exchange_name == "Upbit":
        open = cur_ohlcvs['open']
        close = cur_ohlcvs['close']

    total_trials = {}
    for i in range(-20, 21):
        if i != 0:
            total_trials[i] = int(fn.get_ini(df.STRATEGY_INI_PATH, ticker, i))

    trial_count = 1
    for i in range(len(cur_ohlcvs)-1):
        if i > 1:
            candle_range = close[i - 1] - open[i - 1]
            candle_range2 = close[i] - open[i]
            if candle_range * candle_range2 > 0:
                trial_count += 1
            else:
                if candle_range > 0:
                    total_trials[trial_count] += 1
                else:
                    total_trials[-1 * trial_count] += 1

                trial_count = 1

    for key, value in total_trials.items():
        fn.set_ini(df.STRATEGY_INI_PATH, ticker, key, value)


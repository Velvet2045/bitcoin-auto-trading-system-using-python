from datetime import datetime
import matplotlib.pyplot as plt
import definition as df
import function as fn
import numpy as np
import pyupbit

def get_signal_by_donchian(exchange_name, exchange, symbol, run_mode, logger,
                    enter_period=20,
                    exit_period=10,
                    ticker="1d",
                    atr_mult=2.0,
                    atr_period=20,
                    commission=0.001,
                    slipage=0.0015
                    ):

    max_weight = 3
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

    time = []
    high = []
    low = []
    open = []
    close = []
    if exchange_name == "Binance":
        for ohlc in cur_ohlcvs:
            time.append(datetime.fromtimestamp(ohlc[df.OHLCV_TIMESTAMP] / 1000))
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

    ma_upper = []
    ma_lower = []
    for i in range(len(cur_ohlcvs)):
        if i < enter_period:
            ma_upper.append(999999.0)
        else:
            ma_upper.append(max(high[i-enter_period+1:i]))

    for i in range(len(cur_ohlcvs)):
        if i < exit_period:
            ma_lower.append(0.0)
        else:
            ma_lower.append(min(low[i-exit_period+1:i]))

    daily_range = []
    high_close_range = []
    low_close_range = []
    true_range = []
    for i in range(len(cur_ohlcvs)):
        daily_range.append(high[i] - low[i])
        if i == 0:
            high_close_range.append(0.0)
            low_close_range.append(0.0)
            true_range.append(0.0)
        else:
            high_close_range.append(high[i] - close[i-1])
            low_close_range.append(low[i] - close[i-1])
            true_range.append(max(daily_range[i], high_close_range[i], low_close_range[i]))

    atr = []
    atr_stop = []
    for i in range(len(cur_ohlcvs)):
        if i < atr_period:
            atr.append(0.0)
            atr_stop.append(0.0)
        else:
            atr.append(sum(true_range[i-atr_period+1:i], 0.0) / atr_period)
            atr_stop.append(atr_mult * atr[i])

    #print("2atr: " + str(atr_stop[cur_index]))

    atr_upper = []
    atr_lower = []
    weight = 2 / (max_weight + 1)
    for i in range(len(cur_ohlcvs)):
        if i < atr_period:
            atr_upper.append(0.0)
            atr_lower.append(0.0)
        elif i == atr_period:
            atr_upper.append(close[i] + atr_stop[i])
            atr_lower.append(close[i] - atr_stop[i])
        else:
            atr_upper.append((close[i] + atr_stop[i] - atr_upper[i-1]) * weight + atr_upper[i-1])
            atr_lower.append((close[i] - atr_stop[i] - atr_lower[i-1]) * weight + atr_lower[i-1])

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
        if i >= atr_period:
            plotted_atr = atr_lower[i-1]

            # break upper Donchian (with 1 candle offset) (buy signal)
            break_up = close[i] >= ma_upper[i-1]
            # break lower Donchian (with 1 candle offset) (sell signal)
            break_down = close[i] <= ma_lower[i-1]

            stop_loss = close[i] <= plotted_atr or close[i] <= (trading_price_stamp - 2 * atr_stop[i-1])

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
                                          str(round(close[i],2)) + " / BREAK_UP: " +
                                          str(round(ma_upper[i], 2)) + " / STOP_LOSS: " + str(round(plotted_atr,2)))
                else:
                    past_trading_profit = 0

            elif cur_signal == df.SIGNAL_HOLD:
                if break_down or stop_loss:
                    cur_signal = df.SIGNAL_SELL

                    trading_count += 1.0
                    past_trading_profit = (close[i] - trading_price_stamp) / trading_price_stamp
                    if past_trading_profit > 0:
                        trading_odds += 1.0

                    virtual_balance *= 1.0 - commission - slipage + (close[i] - close[i-1]) / close[i-1]
                    virtual_balance += virtual_balance_ctrl
                    virtual_balance_ctrl = 0
                    trading_price_stamp = 0

                    if run_mode == df.MODE_SIM:
                        fn.time_print("[" + time[i].strftime('%Y-%m-%d %H:%M') + "] CLEAR: " +
                                      str(round(close[i], 2)) + " / BREAK_DOWN: " +
                                      str(round(ma_lower[i-1], 2)) + " / STOP_LOSS: " + str(round(plotted_atr, 2)))
                        fn.time_print("=> TOTAL: " + str(round(virtual_balance, 2)) + " / INVESTED: " +
                                      str(round(virtual_balance_stamp, 2)))
                else:
                    cur_signal = df.SIGNAL_HOLD
                    virtual_balance *= (1 + (close[i] - close[i-1]) / close[i-1])

            # print("balance: " + str(virtual_balance) + ", close: " + str(total_close[index-1]))
            holding_balance *= (1 + (close[i] - close[i-1]) / close[i-1])

        result.append(virtual_balance + virtual_balance_ctrl)
        holding_result.append(holding_balance)

    if run_mode == df.MODE_SIM:
        fn.time_print("[" + time[i].strftime('%Y-%m-%d %H:%M') + "] LAST: " +
                      str(round(close[len(close)-1], 2)) + " / BREAK_DOWN: " +
                      str(round(ma_lower[len(ma_lower)-1], 2)) + " / STOP_LOSS: " + str(round(plotted_atr, 2)))
        fn.time_print("=> TOTAL: " + str(round(virtual_balance, 2)) + " / INVESTED: " +
                      str(round(virtual_balance_stamp, 2)))

        if trading_count > 0:
            fn.time_print("- 매매 횟수 : " + str(trading_count) + " / 매매 승률 : " + str(
                          round(trading_odds / trading_count * 100)) + ("%"))
        else:
            fn.time_print("- 매매 횟수 : 0 / 매매 승률 : 0%")

        label_strategy = "Turtle trading strategy (Donchian/ATR) " + str(enter_period) + " " + str(exit_period)
        plt.plot(time, result, label=label_strategy)
        plt.plot(time, holding_result, label='Buy and hold strategy')
        plt.legend(loc=2)

        plt.xlabel('Time')
        plt.ylabel('Value')
        plot_title = symbol + " Backtesting Result"
        plt.title(plot_title)
        plt.xticks([time[0], time[round((len(time))/2)], time[len(time)-1]])
        # plt.xticks(rotation='vertical')
        plt.show()
        return df.SIGNAL_NONE
    else:
        last_index = len(cur_ohlcvs) - 2
        plotted_atr = atr_lower[last_index]
        if exchange_name == "Binance":
            cur_price = exchange.fetch_ticker(symbol)['close']
        elif exchange_name == "Upbit":
            cur_price = pyupbit.get_current_price(symbol)

        break_up = cur_price >= ma_upper[last_index]
        break_down = cur_price <= ma_lower[last_index]
        stop_loss = cur_price <= plotted_atr or cur_price <= (trading_price_stamp - 2 * atr_stop[last_index])

        if cur_signal == df.SIGNAL_BUY:
            cur_signal = df.SIGNAL_HOLD
        elif cur_signal == df.SIGNAL_SELL:
            cur_signal = df.SIGNAL_NONE

        if cur_signal == df.SIGNAL_NONE:
            if past_trading_profit <= 0:
                # 매수 포지션
                if break_up:
                    cur_signal = df.SIGNAL_BUY

        elif cur_signal == df.SIGNAL_HOLD:
            if break_down or stop_loss:
                cur_signal = df.SIGNAL_SELL

        else:
            cur_signal = df.SIGNAL_HOLD

        return cur_signal


def get_signal_by_ma_double(exchange_name, exchange, symbol, run_mode, logger,
                    enter_period=24,
                    exit_period=15,
                    ticker="1h",
                    direction="Long",
                    commission=0.001,
                    slipage=0.0015
                    ):

    cur_ohlcvs = exchange.fetch_ohlcv(symbol, ticker)

    time = []
    high = []
    low = []
    open = []
    close = []
    for ohlc in cur_ohlcvs:
        time.append(datetime.fromtimestamp(ohlc[df.OHLCV_TIMESTAMP] / 1000))
        high.append(ohlc[df.OHLCV_HIGH])
        low.append(ohlc[df.OHLCV_LOW])
        open.append(ohlc[df.OHLCV_OPEN])
        close.append(ohlc[df.OHLCV_CLOSE])

    ma_upper = []
    ma_lower = []
    for i in range(len(close)):
        if i < enter_period:
            ma_upper.append(0.0)
        else:
            ma_upper.append(sum(close[i - enter_period+1:i]) / len(close[i - enter_period+1:i]))
        if i < exit_period:
            ma_lower.append(0.0)
        else:
            ma_lower.append(sum(close[i - exit_period+1:i]) / len(close[i - exit_period+1:i]))

    long_period = enter_period
    if enter_period < exit_period:
        long_period = exit_period

    trading_odds = 0.0
    trading_count = 0
    virtual_balance = 100
    virtual_balance_ctrl = 0
    virtual_balance_stamp = 100
    holding_balance = 100
    trading_price_stamp = 0
    cur_signal = df.SIGNAL_NONE
    result = []
    holding_result = []
    for i in range(len(cur_ohlcvs)):
        if i >= long_period:
            # print("upper: " + str(ma_upper[index]) + " / lower: " + str(ma_lower[index]))
            # break upper MA (with 1 candle offset) (buy signal)
            break_up = ma_lower[i] >= ma_upper[i] and ma_lower[i - 1] < ma_upper[i - 1]
            # break lower MA (with 1 candle offset) (sell signal)
            break_down = ma_upper[i] >= ma_lower[i] and ma_upper[i - 1] < ma_lower[i - 1]

            stop_loss = close[i] <= trading_price_stamp * 0.9

            if cur_signal == df.SIGNAL_BUY:
                    cur_signal = df.SIGNAL_HOLD
            elif cur_signal == df.SIGNAL_SELL:
                    cur_signal = df.SIGNAL_NONE

            if cur_signal == df.SIGNAL_NONE:
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
                                      str(round(trading_price_stamp, 2)) + " / BREAK_UP: " +
                                      str(round(ma_upper[i], 2)) + " / STOP_LOSS: " +
                                      str(round(trading_price_stamp * 0.9, 2)))

            elif cur_signal == df.SIGNAL_HOLD:
                if break_down or stop_loss:
                    cur_signal = df.SIGNAL_SELL

                    trading_count += 1
                    if close[i] - trading_price_stamp > 0:
                        trading_odds += 1

                    virtual_balance *= 1.0 - commission - slipage + (close[i] - close[i - 1]) / close[i - 1]
                    virtual_balance += virtual_balance_ctrl
                    virtual_balance_ctrl = 0
                    trading_price_stamp = 0

                    if run_mode == df.MODE_SIM:
                        fn.time_print("[" + time[i].strftime('%Y-%m-%d %H:%M') + "] CLEAR: " +
                                      str(round(close[i - 1], 2)) + " / BREAK_DOWN: " +
                                      str(round(ma_lower[i], 2)) + " / STOP_LOSS: " +
                                      str(round(trading_price_stamp * 0.9, 2)))
                        fn.time_print("=> TOTAL: " + str(round(virtual_balance, 2)) + " / INVESTED: " +
                                      str(round(virtual_balance_stamp, 2)))
                else:
                    cur_signal = df.SIGNAL_HOLD
                    virtual_balance *= 1 + (close[i] - close[i - 1]) / close[i - 1]

            holding_balance *= 1 + (close[i] - close[i - 1]) / close[i - 1]
        result.append(virtual_balance + virtual_balance_ctrl)
        holding_result.append(holding_balance)

    if run_mode == df.MODE_SIM:
        fn.time_print("LAST: " + str(round(close[i-1], 2)) +
                    " / BREAK_DOWN: " + str(break_down) + " / STOP_LOSS: " + str(stop_loss))
        fn.time_print("=> TOTAL: " + str(round(virtual_balance, 2)) + " / INVESTED: " + str(round(virtual_balance_stamp, 2)))

        if trading_count > 0:
            fn.time_print("- 매매 횟수 : " + str(trading_count) + " / 매매 승률 : " + str(
                round(trading_odds / trading_count * 100, 2)) + ("%"))
        else:
            fn.time_print("- 매매 횟수 : 0 / 매매 승률 : 0%")

        label_strategy = "MA double trading strategy " + str(enter_period) + " " + str(
            exit_period) + " " + str(direction)
        plt.plot(time, result, label=label_strategy)
        plt.plot(time, holding_result, label='Buy and hold strategy')
        plt.legend(loc=2)
        plt.xlabel('Time')
        plt.ylabel('Value')
        plot_title = symbol + " Backtesting Result"
        plt.title(plot_title)
        plt.xticks([time[0], time[round((len(time)) / 2)], time[len(time) - 1]])
        #        plt.xticks(rotation='vertical')
        plt.show()

        return df.SIGNAL_NONE
    else:
        return cur_signal


def get_signal_by_ma_double_2(exchange_name, exchange, symbol, run_mode, logger,
                    enter_period=10,
                    exit_period=5,
                    ticker="1m",
                    mt_enter_period=20,
                    mt_exit_period=10,
                    commission=0.001,
                    slipage=0.0015
                    ):

    btc_ohlcvs = exchange.fetch_ohlcv("BTC/USDT", ticker)
    cur_ohlcvs = exchange.fetch_ohlcv(symbol, ticker)

    time = []
    high = []
    low = []
    open = []
    close = []
    for ohlc in cur_ohlcvs:
        time.append(datetime.fromtimestamp(ohlc[df.OHLCV_TIMESTAMP] / 1000))
        high.append(ohlc[df.OHLCV_HIGH])
        low.append(ohlc[df.OHLCV_LOW])
        open.append(ohlc[df.OHLCV_OPEN])
        close.append(ohlc[df.OHLCV_CLOSE])

    btc_close = []
    for ohlc in btc_ohlcvs:
        btc_close.append(ohlc[df.OHLCV_CLOSE])

    ma_btc_upper = []
    ma_btc_lower = []
    for i in range(len(btc_close)):
        if i < mt_enter_period:
            ma_btc_upper.append(btc_close[i])
        else:
            ma_btc_upper.append(sum(btc_close[i-mt_enter_period+1:i]) / len(btc_close[i-mt_enter_period+1:i]))

    for i in range(len(btc_close)):
        if i < mt_exit_period:
            ma_btc_lower.append(btc_close[i])
        else:
            ma_btc_lower.append(sum(btc_close[i-mt_exit_period+1:i]) / len(btc_close[i-mt_exit_period+1:i]))

    ma_upper = []
    ma_lower = []
    for i in range(len(close)):
        if i < enter_period:
            ma_upper.append(close[i])
        else:
            ma_upper.append(sum(close[i-enter_period+1:i]) / len(close[i-enter_period+1:i]))

    for i in range(len(close)):
        if i < exit_period:
            ma_lower.append(close[i])
        else:
            ma_lower.append(sum(close[i-exit_period+1:i]) / len(close[i-exit_period+1:i]))

    upper_envelop = []
    for i in range(len(close)):
        if i == 0:
            upper_envelop.append(0)
        else:
            upper_envelop.append(close[i] / ma_upper[i])

    #print(upper_envelop)

    trading_odds = 0.0
    trading_count = 0
    virtual_balance = 100
    virtual_balance_ctrl = 0
    virtual_balance_stamp = 100
    holding_balance = 100
    trading_price_stamp = 0
    cur_signal = df.SIGNAL_NONE
    result = []
    holding_result = []
    long_period = enter_period
    if enter_period < exit_period:
        long_period = exit_period

    for i in range(len(cur_ohlcvs)):
        if i >= long_period:

            break_up = ma_lower[i] >= ma_upper[i] and ma_lower[i - 1] < ma_upper[i - 1] and ma_btc_lower[i] >= ma_btc_upper[i]
            break_down = ma_upper[i] >= ma_lower[i] and ma_upper[i - 1] < ma_lower[i - 1] or ma_btc_upper[i] > ma_btc_lower[i]

            stop_loss = close[i] <= trading_price_stamp * 0.9

            if cur_signal == df.SIGNAL_BUY:
                    cur_signal = df.SIGNAL_HOLD
            elif cur_signal == df.SIGNAL_SELL:
                    cur_signal = df.SIGNAL_NONE

            if cur_signal == df.SIGNAL_NONE:
                if break_up:
                    cur_signal = df.SIGNAL_BUY
                    if virtual_balance_stamp * 0.9 > virtual_balance:
                        virtual_balance_ctrl = virtual_balance * 0.2
                        virtual_balance *= 0.8
                    else:
                        virtual_balance += virtual_balance_ctrl
                        virtual_balance_ctrl = 0.0

                    virtual_balance *= 1.0 - commission - slipage
                    virtual_balance_stamp = virtual_balance + virtual_balance_ctrl
                    trading_price_stamp = close[i]

                    if run_mode == df.MODE_SIM:
                        fn.time_print("[" + time[i].strftime('%Y-%m-%d %H:%M') + "] BUY: " +
                                      str(round(trading_price_stamp, 2)) + " / BREAK_UP: " +
                                      str(round(ma_upper[i], 2)) + " / STOP_LOSS: " +
                                      str(round(trading_price_stamp * 0.9, 2)))
                        fn.time_print("=> TOTAL: " + str(round(virtual_balance_stamp, 2)) + " / INVEST: " +
                                      str(round(virtual_balance, 2)) + " / REMAIN: " +
                                      str(round(virtual_balance_ctrl, 2)))

            elif cur_signal == df.SIGNAL_HOLD:
                if break_down or stop_loss:
                    cur_signal = df.SIGNAL_SELL

                    trading_count += 1
                    if close[i] - trading_price_stamp > 0:
                        trading_odds += 1

                    virtual_balance *= 1.0 - commission - slipage + (close[i] - close[i-1]) /\
                                       close[i-1]
                    virtual_balance += virtual_balance_ctrl
                    virtual_balance_ctrl = 0
                    trading_price_stamp = 0

                    if run_mode == df.MODE_SIM:
                        fn.time_print("[" + time[i].strftime('%Y-%m-%d %H:%M') + "] CLEAR: " +
                                      str(round(close[i], 2)) + " / BREAK_DOWN: " + str(break_down) +
                                      " / STOP_LOSS: " + str(stop_loss))
                else:
                    cur_signal = df.SIGNAL_HOLD
                    virtual_balance *= (
                            1 + (close[i] - close[i-1]) / close[i-1])

            holding_balance *= (
                    1 + (close[i] - close[i-1]) / close[i-1])

        result.append(virtual_balance + virtual_balance_ctrl)
        holding_result.append(holding_balance)

    if run_mode == df.MODE_SIM:
        fn.time_print("[" + time[len(time)-1].strftime('%Y-%m-%d %H:%M') + "] LAST: " +
                      str(round(close[len(close)-1], 2)) + " / BREAK_DOWN: " +
                      str(round(ma_lower[len(ma_lower)-1], 2)) + " / STOP_LOSS: " +
                      str(round(trading_price_stamp * 0.9, 2)))
        fn.time_print("=> TOTAL: " + str(round(virtual_balance, 2)) + " / INVESTED: " +
                      str(round(virtual_balance_stamp, 2)))

        if trading_count > 0:
            fn.time_print("- 매매 횟수 : " + str(trading_count) + " / 매매 승률 : " +
                          str(round(trading_odds / trading_count * 100, 2)) + ("%"))
        else:
            fn.time_print("- 매매 횟수 : 0 / 매매 승률 : 0%")

        label_strategy = "MA double 2 trading strategy " + str(enter_period) + " " + str(exit_period)
        plt.plot(time, result, label=label_strategy)
        plt.plot(time, holding_result, label='Buy and hold strategy')
        plt.legend(loc=2)
        plt.xlabel('Time')
        plt.ylabel('Value')
        plot_title = symbol + " Backtesting Result"
        plt.title(plot_title)
        plt.xticks([time[0], time[round((len(time)) / 2)], time[len(time) - 1]])
        plt.show()

        return df.SIGNAL_NONE
    else:
        return cur_signal


def get_signal_by_larry_williams(exchange_name, exchange, symbol, run_mode, logger,
                                 ticker="1d",
                                 commission=0.001,
                                 slipage=0.0015
                                 ):
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

    time = []
    high = []
    low = []
    open = []
    close = []
    if exchange_name == "Binance":
        for ohlc in cur_ohlcvs:
            time.append(datetime.fromtimestamp(ohlc[df.OHLCV_TIMESTAMP] / 1000))
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

    # noise filter
    noise_period = 20
    noise = []
    for i in range(len(cur_ohlcvs)):
        if high[i] - low[i] > 0:
            noise.append(1 - abs((open[i] - close[i]) / (high[i] - low[i])))
        else:
            noise.append(0)

    noise_mean = []
    for i in range(len(cur_ohlcvs)):
        if i < noise_period:
            noise_mean.append(noise[i])
        else:
            noise_mean.append(sum(noise[i-noise_period+1:i]) / len(noise[i-noise_period+1:i]))

    if run_mode == df.MODE_SIM:
        trading_odds = 0
        trading_count = 0
        virtual_balance = 100
        virtual_balance_stamp = 0
        holding_balance = 100
        trading_price_stamp = 0
        cur_signal = df.SIGNAL_NONE
        result = []
        holding_result = []
        for i in range(len(cur_ohlcvs)):
            if i >= noise_period:
                #cur_volatility = open[i] + noise_mean[i-1] * (high[i-1] - low[i-1])
                cur_volatility = open[i] + 0.6 * (high[i - 1] - low[i - 1])
                break_up = high[i] > cur_volatility

                if cur_signal == df.SIGNAL_BUY:
                    cur_signal = df.SIGNAL_SELL
                    virtual_balance -= virtual_balance_stamp

                    virtual_margin = (open[i] - trading_price_stamp) / trading_price_stamp

                    virtual_balance_stamp *= 1 + virtual_margin

                    virtual_balance += virtual_balance_stamp * (1.0 - commission - slipage)
                    trading_count += 1
                    if open[i] - trading_price_stamp > 0:
                        trading_odds += 1

                    if run_mode == df.MODE_SIM:
                        fn.time_print("[" + time[i].strftime('%Y-%m-%d %H:%M') + "] SELL: " + str(round(open[i], 2)))
                        fn.time_print("=> TOTAL: " + str(virtual_balance))

                if cur_signal != df.SIGNAL_BUY and break_up:
                    cur_signal = df.SIGNAL_BUY
                    if open[i] > cur_volatility:
                        trading_price_stamp = open[i]
                    else:
                        trading_price_stamp = cur_volatility

                    virtual_balance_stamp = virtual_balance * (1.0 - commission - slipage) * 0.9
                    virtual_balance = virtual_balance_stamp + virtual_balance * 0.1

                    if run_mode == df.MODE_SIM:
                        fn.time_print("[" + time[i].strftime('%Y-%m-%d %H:%M') + "] BUY: " +
                                      str(round(trading_price_stamp, 2)))

                else:
                    cur_signal = df.SIGNAL_NONE

                holding_balance *= 1 + (close[i] - close[i-1]) / close[i-1]

            result.append(virtual_balance)
            holding_result.append(holding_balance)

        fn.time_print("[" + time[len(time)-1].strftime('%Y-%m-%d %H:%M') + "] LAST: " +
                      str(round(open[len(open)-1], 2)) + " / BREAK_DOWN: " +
                      str(round(open[len(open)-1], 2)) + " / STOP_LOSS: " +
                      str(round(trading_price_stamp * 0.9, 2)))
        fn.time_print("=> TOTAL: " + str(round(virtual_balance, 2)) + " / INVESTED: " +
                      str(round(virtual_balance_stamp, 2)))

        if trading_count > 0:
            fn.time_print("- 매매 횟수 : " + str(trading_count) + " / 매매 승률 : " +
                          str(round(trading_odds / trading_count * 100, 2)) + ("%"))
        else:
            fn.time_print("- 매매 횟수 : 0 / 매매 승률 : 0%")

        label_strategy = "Larry Williams trading strategy "
        plt.plot(time, result, label=label_strategy)
        plt.plot(time, holding_result, label='Buy and hold strategy')
        plt.legend(loc=2)
        plt.xlabel('Time')
        plt.ylabel('Value')
        plot_title = symbol + " Backtesting Result"
        plt.title(plot_title)
        plt.xticks([time[0], time[round((len(time)) / 2)], time[len(time) - 1]])
        plt.show()

        return df.SIGNAL_NONE
    else:
        cur_index = len(cur_ohlcvs) - 1
        last_index = len(cur_ohlcvs) - 2
        if exchange_name == "Binance":
            cur_price = exchange.fetch_ticker(symbol)['close']
        elif exchange_name == "Upbit":
            cur_price = pyupbit.get_current_price(symbol)

        #cur_volatility = open[cur_index] + noise_mean[last_index] * (high[last_index] - low[last_index])
        cur_volatility = open[cur_index] + 0.6 * (high[last_index] - low[last_index])

        break_up = cur_price > cur_volatility

        if break_up:
            cur_signal = df.SIGNAL_BUY

        else:
            cur_signal = df.SIGNAL_SELL

        return cur_signal


def get_signal_by_reverse_rsi_2(exchange_name, exchange, symbol, run_mode, logger, cur_signal,
                                enter_period=200,
                                exit_period=5,
                                rsi_period=2,
                                over_sold=97,
                                ticker="1d",
                                commission=0.001,
                                slipage=0.0015
                                ):
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

        time = []
        high = []
        low = []
        open = []
        close = []
        if exchange_name == "Binance":
            for ohlc in cur_ohlcvs:
                time.append(datetime.fromtimestamp(ohlc[df.OHLCV_TIMESTAMP] / 1000))
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
            #volume = cur_ohlcvs['volume']

        ma_upper = []
        ma_lower = []
        for i in range(len(cur_ohlcvs)):
            if i < enter_period:
                ma_upper.append(0.0)
            else:
                ma_upper.append(sum(close[i - enter_period+1:i]) / len(close[i - enter_period+1:i]))

            if i < exit_period:
                ma_lower.append(0.0)
            else:
                ma_lower.append(sum(close[i - exit_period+1:i]) / len(close[i - exit_period+1:i]))

        close_u = []
        close_d = []
        for i in range(len(cur_ohlcvs)):
            if i < 1:
                close_u.append(0.0)
                close_d.append(0.0)
            else:
                diff = close[i] - close[i-1]
                if diff > 0:
                    close_u.append(diff)
                    close_d.append(0.0)
                else:
                    close_u.append(0.0)
                    close_d.append(-1.0*diff)

        close_au = []
        close_ad = []
        for i in range(len(cur_ohlcvs)):
            if i < rsi_period:
                close_au.append(0.0)
                close_ad.append(0.0)
            elif i == rsi_period:
                close_au.append(sum(close_u[i-rsi_period:i-1])/rsi_period)
                close_ad.append(sum(close_d[i-rsi_period:i-1])/rsi_period)
            else:
                close_au.append((close_au[i-1] * (rsi_period-1) + close_u[i]) / rsi_period)
                close_ad.append((close_ad[i-1] * (rsi_period-1) + close_d[i]) / rsi_period)

        rsi = []
        for i in range(len(cur_ohlcvs)):
            if i < rsi_period:
                rsi.append(0.0)
            else:
                if close_au[i] + close_ad[i] > 0:
                    rsi.append(round(100.0 * close_au[i] / (close_au[i] + close_ad[i]), 2))
                else:
                    rsi.append(0.0)

        long_period = enter_period
        if enter_period < exit_period:
            long_period = exit_period

        if run_mode == df.MODE_SIM:
            trading_odds = 0.0
            trading_count = 0
            virtual_balance = 100
            virtual_balance_ctrl = 0
            virtual_balance_stamp = 100
            holding_balance = 100
            trading_price_stamp = 0
            cur_signal = df.SIGNAL_NONE
            result = []
            holding_result = []
            for i in range(len(cur_ohlcvs)):
                if i >= long_period:
                    break_up = close[i] > ma_upper[i-1] and close[i] < ma_lower[i-1] and rsi[i-1] < 15

                    break_down = close[i] > ma_lower[i-1]

                    stop_loss = close[i] <= trading_price_stamp * 0.9

                    if cur_signal == df.SIGNAL_BUY:
                        cur_signal = df.SIGNAL_HOLD
                    elif cur_signal == df.SIGNAL_SELL:
                        cur_signal = df.SIGNAL_NONE

                    if cur_signal == df.SIGNAL_NONE:
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
                                              str(round(trading_price_stamp, 2)) + " / BREAK_UP: " +
                                              str(round(ma_upper[i-1])) + " / STOP_LOSS: " +
                                              str(round(trading_price_stamp * 0.9, 2)))

                    elif cur_signal == df.SIGNAL_HOLD:
                        if break_down or stop_loss:
                            cur_signal = df.SIGNAL_SELL

                            trading_count += 1
                            if close[i] - trading_price_stamp > 0:
                                trading_odds += 1

                            virtual_balance *= 1.0 - commission - slipage + (close[i] - close[i - 1]) / close[i - 1]
                            virtual_balance += virtual_balance_ctrl
                            virtual_balance_ctrl = 0
                            trading_price_stamp = 0

                            if run_mode == df.MODE_SIM:
                                fn.time_print("[" + time[i].strftime('%Y-%m-%d %H:%M') + "] CLEAR: " +
                                              str(round(close[i], 2)) + " / BREAK_DOWN: " + str(break_down) +
                                              " / STOP_LOSS: " + str(stop_loss))
                                fn.time_print("=> TOTAL: " + str(round(virtual_balance, 2)) + " / INVESTED: " +
                                              str(round(virtual_balance_stamp, 2)))
                        else:
                            cur_signal = df.SIGNAL_HOLD
                            virtual_balance *= 1 + (close[i] - close[i-1]) / close[i-1]

                    holding_balance *= 1 + (close[i] - close[i-1]) / close[i-1]
                result.append(virtual_balance + virtual_balance_ctrl)
                holding_result.append(holding_balance)

            fn.time_print(
                "[" + time[len(time) - 1].strftime('%Y-%m-%d %H:%M') + "] LAST: " +
                str(round(close[len(close) - 1], 2)) + " / BREAK_DOWN: " + str(round(ma_lower[len(ma_lower) - 1], 2)) +
                " / STOP_LOSS: " + str(round(trading_price_stamp * 0.9, 2)))
            fn.time_print(
                "=> TOTAL: " + str(round(virtual_balance, 2)) + " / INVESTED: " + str(round(virtual_balance_stamp, 2)))

            if trading_count > 0:
                fn.time_print("- 매매 횟수 : " + str(trading_count) + " / 매매 승률 : " +
                              str(round(trading_odds / trading_count * 100, 2)) + ("%"))
            else:
                fn.time_print("- 매매 횟수 : 0 / 매매 승률 : 0%")

            label_strategy = "Reverse RSI(2) trading strategy " + str(enter_period) + " " + str(exit_period)
            plt.plot(time, result, label=label_strategy)
            plt.plot(time, holding_result, label='Buy and hold strategy')
            plt.legend(loc=2)
            plt.xlabel('Time')
            plt.ylabel('Value')
            plot_title = symbol + " Backtesting Result"
            plt.title(plot_title)
            plt.xticks([time[0], time[round((len(time)) / 2)], time[len(time) - 1]])
            #        plt.xticks(rotation='vertical')
            plt.show()

            return df.SIGNAL_NONE
        else:
            cur_index = len(cur_ohlcvs) - 1
            last_index = len(cur_ohlcvs) - 2
            if exchange_name == "Binance":
                cur_price = exchange.fetch_ticker(symbol)['close']
            elif exchange_name == "Upbit":
                cur_price = pyupbit.get_current_price(symbol)

            if cur_signal == df.SIGNAL_BUY:
                cur_signal = df.SIGNAL_HOLD
            elif cur_signal == df.SIGNAL_SELL:
                cur_signal = df.SIGNAL_NONE

            if cur_signal == df.SIGNAL_NONE:
                break_up = cur_price > ma_upper[last_index] and cur_price < ma_lower[last_index] \
                           and rsi[last_index] < 15
                if break_up:
                    cur_signal = df.SIGNAL_BUY

                    # 매수 시점 기록
                    now = datetime.now()
                    fn.set_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_TIME_5', now.strftime('%Y/%m/%d %H:%M:%S'))

                    # 매수 시점부터 계속 최고가를 기록
                    fn.set_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_PRICE_5', cur_price['close'])
                    fn.time_print("- cur price : " + str(cur_price['close']))

            elif cur_signal == df.SIGNAL_HOLD:
                entry_price = float(fn.get_ini(df.STRATEGY_INI_PATH, symbol, 'VALUE_ENTRY_PRICE_5', cur_price['open']))

                break_down = cur_price['close'] > ma_lower[last_index]
                stop_loss = cur_price['close'] <= entry_price * 0.9
                if break_down or stop_loss:
                    cur_signal = df.SIGNAL_SELL

            else:
                cur_signal = df.SIGNAL_HOLD

            return cur_signal

def get_signal_by_rsi(exchange_name, exchange, symbol, run_mode, logger,
                        rsi_period=14,
                        over_sold=30,
                        over_bought=70,
                        ticker="15m",
                        commission=0.001,
                        slipage=0.0015
                        ):

    cur_ohlcvs = exchange.fetch_ohlcv(symbol, ticker)

    time = []
    high = []
    low = []
    open = []
    close = []
    for ohlc in cur_ohlcvs:
        time.append(datetime.fromtimestamp(ohlc[df.OHLCV_TIMESTAMP] / 1000))
        high.append(ohlc[df.OHLCV_HIGH])
        low.append(ohlc[df.OHLCV_LOW])
        open.append(ohlc[df.OHLCV_OPEN])
        close.append(ohlc[df.OHLCV_CLOSE])

    close_u = []
    close_d = []
    for i in range(len(close)):
        if i < 1:
            close_u.append(0.0)
            close_d.append(0.0)
        else:
            diff = close[i] - close[i-1]
            if diff > 0:
                close_u.append(diff)
                close_d.append(0.0)
            else:
                close_u.append(0.0)
                close_d.append(-1.0*diff)

    close_au = []
    close_ad = []
    for i in range(len(close)):
        if i < rsi_period:
            close_au.append(0.0)
            close_ad.append(0.0)
        elif i == rsi_period:
            close_au.append(sum(close_u[i-rsi_period:i-1])/rsi_period)
            close_ad.append(sum(close_d[i-rsi_period:i-1])/rsi_period)
        else:
            close_au.append((close_au[i-1] * (rsi_period-1) + close_u[i]) / rsi_period)
            close_ad.append((close_ad[i-1] * (rsi_period-1) + close_d[i]) / rsi_period)

    rsi = []
    for i in range(len(close)):
        if i < rsi_period:
            rsi.append(0.0)
        else:
            if close_au[i] + close_ad[i] > 0:
                rsi.append(round(100.0 * close_au[i] / (close_au[i] + close_ad[i]), 2))
            else:
                rsi.append(0.0)

    trading_odds = 0.0
    trading_count = 0
    virtual_balance = 100
    virtual_balance_ctrl = 0
    virtual_balance_stamp = 100
    holding_balance = 100
    trading_price_stamp = 0
    cur_signal = df.SIGNAL_NONE
    result = []
    holding_result = []
    for i in range(len(close)):
        if i >= rsi_period:
            break_up = rsi[i] < over_sold #and rsi[i] > rsi[i-1]
            break_down = rsi[i] > over_bought #and rsi[i] < rsi[i-1]
            stop_loss = close[i] <= trading_price_stamp * 0.9

            if cur_signal == df.SIGNAL_BUY:
                cur_signal = df.SIGNAL_HOLD
            elif cur_signal == df.SIGNAL_SELL:
                cur_signal = df.SIGNAL_NONE

            if cur_signal == df.SIGNAL_NONE:
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
                                      str(round(trading_price_stamp, 2)) + " / BREAK_UP: " +
                                      str(round(close[i], 2)) + " / STOP_LOSS: " +
                                      str(round(trading_price_stamp * 0.9, 2)))

            elif cur_signal == df.SIGNAL_HOLD:
                if break_down or stop_loss:
                    cur_signal = df.SIGNAL_SELL

                    trading_count += 1
                    if close[i] - trading_price_stamp > 0:
                        trading_odds += 1

                    virtual_balance *= 1.0 - commission - slipage + (close[i] - close[i - 1]) / close[i - 1]
                    virtual_balance += virtual_balance_ctrl
                    virtual_balance_ctrl = 0
                    trading_price_stamp = 0

                    if run_mode == df.MODE_SIM:
                        fn.time_print("[" + time[i].strftime('%Y-%m-%d %H:%M') + "] CLEAR: " +
                                      str(round(close[i], 2)) + " / BREAK_DOWN: " +
                                      str(break_down) + " / STOP_LOSS: " + str(stop_loss))
                        fn.time_print("=> TOTAL: " + str(round(virtual_balance, 2)) + " / INVESTED: " +
                                      str(round(virtual_balance_stamp, 2)))
                else:
                    cur_signal = df.SIGNAL_HOLD
                    virtual_balance *= 1 + (close[i] - close[i-1]) / close[i-1]

            holding_balance *= 1 + (close[i] - close[i-1]) / close[i-1]
        result.append(virtual_balance + virtual_balance_ctrl)
        holding_result.append(holding_balance)

    if run_mode == df.MODE_SIM:
        fn.time_print(
            "[" + time[len(time)-1].strftime('%Y-%m-%d %H:%M') + "] LAST: " +
            str( round(close[len(close)-1], 2)) + " / BREAK_DOWN: " + str(round(close[len(close)-1])) +
            " / STOP_LOSS: " + str(round(trading_price_stamp * 0.9, 2)))
        fn.time_print(
            "=> TOTAL: " + str(round(virtual_balance, 2)) + " / INVESTED: " + str(round(virtual_balance_stamp, 2)))

        if trading_count > 0:
            fn.time_print("- 매매 횟수 : " + str(trading_count) + " / 매매 승률 : " +
                          str(round(trading_odds / trading_count * 100, 2)) + ("%"))
        else:
            fn.time_print("- 매매 횟수 : 0 / 매매 승률 : 0%")

        label_strategy = "RSI trading strategy " + str(over_sold) + " " + str(over_bought)
        plt.plot(time, result, label=label_strategy)
        plt.plot(time, holding_result, label='Buy and hold strategy')
        plt.legend(loc=2)
        plt.xlabel('Time')
        plt.ylabel('Value')
        plot_title = symbol + " Backtesting Result"
        plt.title(plot_title)
        plt.xticks([time[0], time[round((len(time)) / 2)], time[len(time) - 1]])
        #        plt.xticks(rotation='vertical')
        plt.show()

        return df.SIGNAL_NONE
    else:
        return cur_signal


def get_signal_by_efficiency_ratio(exchange_name, exchange, symbol, run_mode, logger,
                        er_period=10,
                        at_period=12,
                        ticker="1d",
                        commission=0.001,
                        slipage=0.0015
                        ):

    cur_ohlcvs = exchange.fetch_ohlcv(symbol, ticker)

    time = []
    high = []
    low = []
    open = []
    close = []
    for ohlc in cur_ohlcvs:
        time.append(datetime.fromtimestamp(ohlc[df.OHLCV_TIMESTAMP] / 1000))
        high.append(ohlc[df.OHLCV_HIGH])
        low.append(ohlc[df.OHLCV_LOW])
        open.append(ohlc[df.OHLCV_OPEN])
        close.append(ohlc[df.OHLCV_CLOSE])

    long_ticker = "1M"
    long_ohlcvs = exchange.fetch_ohlcv(symbol, ticker)

    time = []
    high = []
    low = []
    open = []
    close = []
    for ohlc in cur_ohlcvs:
        time.append(datetime.fromtimestamp(ohlc[df.OHLCV_TIMESTAMP] / 1000))
        high.append(ohlc[df.OHLCV_HIGH])
        low.append(ohlc[df.OHLCV_LOW])
        open.append(ohlc[df.OHLCV_OPEN])
        close.append(ohlc[df.OHLCV_CLOSE])

    efficiency_ratio = []
    for i in range(len(close)):
        if i < er_period:
            efficiency_ratio.append(0.0)
        else:
            sum_close = 0.0
            for j in range(i-er_period+1, i):
                sum_close += abs(close[j] - close[j-1])
            if sum_close > 0:
                efficiency_ratio.append(round(abs(close[i] - close[i-er_period+1]) / sum_close, 2))
            else:
                efficiency_ratio.append(0.0)

        #print(str(time[i]) + ", " + str(efficiency_ratio[i]))

    long_period = er_period
    if at_period > er_period:
        long_period = at_period

    adaptive_ratio = []
    for i in range(len(close)):
        if i < long_period:
            adaptive_ratio.append(0.0)
        else:
            adaptive_ratio.append(close[i] - close[i-round(efficiency_ratio[i] * at_period)+1])

    trading_odds = 0.0
    trading_count = 0
    virtual_balance = 100
    virtual_balance_ctrl = 0
    virtual_balance_stamp = 100
    holding_balance = 100
    trading_price_stamp = 0
    cur_signal = df.SIGNAL_NONE
    result = []
    holding_result = []
    for i in range(len(close)):
        if i >= long_period:
            break_up = adaptive_ratio[i] > 0
            break_down = adaptive_ratio[i] < 0
            stop_loss = close[i] <= trading_price_stamp * 0.9

            if cur_signal == df.SIGNAL_BUY:
                cur_signal = df.SIGNAL_HOLD
            elif cur_signal == df.SIGNAL_SELL:
                cur_signal = df.SIGNAL_NONE

            if cur_signal == df.SIGNAL_NONE:
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
                                      str(round(trading_price_stamp, 2)) + " / BREAK_UP: " +
                                      str(round(close[i], 2)) + " / STOP_LOSS: " +
                                      str( round(trading_price_stamp * 0.9, 2)))

            elif cur_signal == df.SIGNAL_HOLD:
                if break_down or stop_loss:
                    cur_signal = df.SIGNAL_SELL

                    trading_count += 1
                    if close[i] - trading_price_stamp > 0:
                        trading_odds += 1

                    virtual_balance *= 1.0 - commission - slipage + (close[i] - close[i - 1]) / close[i - 1]
                    virtual_balance += virtual_balance_ctrl
                    virtual_balance_ctrl = 0
                    trading_price_stamp = 0

                    if run_mode == df.MODE_SIM:
                        fn.time_print("[" + time[i].strftime('%Y-%m-%d %H:%M') + "] CLEAR: " +
                                      str(round(close[i], 2)) + " / BREAK_DOWN: " +
                                      str(break_down) + " / STOP_LOSS: " + str(stop_loss))
                        fn.time_print("=> TOTAL: " + str(round(virtual_balance, 2)) + " / INVESTED: " +
                                      str(round(virtual_balance_stamp, 2)))
                else:
                    cur_signal = df.SIGNAL_HOLD
                    virtual_balance *= 1 + (close[i] - close[i-1]) / close[i-1]

            holding_balance *= 1 + (close[i] - close[i-1]) / close[i-1]
        result.append(virtual_balance + virtual_balance_ctrl)
        holding_result.append(holding_balance)

    if run_mode == df.MODE_SIM:
        fn.time_print(
            "[" + time[len(time)-1].strftime('%Y-%m-%d %H:%M') + "] LAST: " +
            str(round(close[len(close)-1], 2)) + " / BREAK_DOWN: " +
            str(round(close[len(close)-1])) + " / STOP_LOSS: " +
            str(round(trading_price_stamp * 0.9, 2)))
        fn.time_print(
            "=> TOTAL: " + str(round(virtual_balance, 2)) + " / INVESTED: " +
            str(round(virtual_balance_stamp, 2)))

        if trading_count > 0:
            fn.time_print("- 매매 횟수 : " + str(trading_count) + " / 매매 승률 : " +
                          str(round(trading_odds / trading_count * 100, 2)) + ("%"))
        else:
            fn.time_print("- 매매 횟수 : 0 / 매매 승률 : 0%")

        label_strategy = "Efficiency ratio trading strategy " + str(er_period)
        plt.plot(time, result, label=label_strategy)
        plt.plot(time, holding_result, label='Buy and hold strategy')
        plt.legend(loc=2)
        plt.xlabel('Time')
        plt.ylabel('Value')
        plot_title = symbol + " Backtesting Result"
        plt.title(plot_title)
        plt.xticks([time[0], time[round((len(time)) / 2)], time[len(time) - 1]])
        #        plt.xticks(rotation='vertical')
        plt.show()

        return df.SIGNAL_NONE
    else:
        return cur_signal


def get_signal_by_maemfe(exchange_name, exchange, symbol, run_mode, logger,
                    k=0.5,
                    ticker="15m",
                    commission=0.001,
                    slipage=0.0015
                    ):
    cur_ohlcvs = exchange.fetch_ohlcv(symbol, ticker)
    curd_ohlcvs = exchange.fetch_ohlcv(symbol, "1h")

    time = []
    high = []
    low = []
    open = []
    close = []
    for ohlc in cur_ohlcvs:
        time.append(datetime.fromtimestamp(ohlc[df.OHLCV_TIMESTAMP] / 1000))
        high.append(ohlc[df.OHLCV_HIGH])
        low.append(ohlc[df.OHLCV_LOW])
        open.append(ohlc[df.OHLCV_OPEN])
        close.append(ohlc[df.OHLCV_CLOSE])

    timed = []
    highd = []
    lowd = []
    opend = []
    closed = []
    for ohlc in curd_ohlcvs:
        timed.append(datetime.fromtimestamp(ohlc[df.OHLCV_TIMESTAMP] / 1000))
        highd.append(ohlc[df.OHLCV_HIGH])
        lowd.append(ohlc[df.OHLCV_LOW])
        opend.append(ohlc[df.OHLCV_OPEN])
        closed.append(ohlc[df.OHLCV_CLOSE])

    day_range = []
    for i in range(len(curd_ohlcvs)):
        day_range.append(highd[i] - lowd[i])

    atr_len = 50
    ma_day_range = []
    for i in range(len(curd_ohlcvs)):
        if i < atr_len:
            ma_day_range.append(999999.0)
        else:
            ma_day_range.append(max(day_range[i - atr_len + 1:i]))

    hhv = 0
    llv = 99999.0
    len1 = 3
    len2 = 2.2
    len3 = 2.9
    brk = 3
    big = 8
    stop_loss = 0.03
    day_index = 0
    trading_odds = 0
    trading_count = 0
    virtual_balance = 100
    virtual_balance_stamp = 0
    holding_balance = 100
    trading_price_stamp = 0
    cur_signal = df.SIGNAL_NONE
    result = []
    holding_result = []
    for i in range(len(cur_ohlcvs)):
        if i >= 2:

            # 매도 전, 전일 종가까지 아는 상황
            if cur_signal == df.SIGNAL_BUY:
                cur_signal == df.SIGNAL_SELL

                sig_list = []

                # 청산2. 매수 추적
                sig_list.append(hhv - ma_day_range[day_index-1] * len1)

                # 청산3. 매수 변동성
                sig_list.append(close[i - 1] - ma_day_range[day_index-1] * len2)

                # if문 1
                if1 = hhv >= trading_price_stamp + day_range[day_index-1] * brk

                if if1:
                    # 청산5. 매수 손익분기 and if 1
                    sig_list.append(trading_price_stamp + day_range[day_index-1] * len3)

                    # 청산6. 매수추적1 and if 1
                    sig_list.append(hhv - day_range[day_index-1] * len3)

                # if문 2
                if2 = hhv >= trading_price_stamp + day_range[day_index-1] * big

                if if2:
                    # 청산8. 매수 초과수익 and if 2
                    sig_list.append(llv)

                max_sig = 0.0
                max_sig_idx = 0
                for j in range(len(sig_list)):
                    if sig_list[j] <= high[i] and sig_list[j] > low[i]:
                        if sig_list[j] > max_sig:
                            max_sig = sig_list[j]
                            max_sig_idx = j

                if max_sig > 0:
                    virtual_margin = ((max_sig - trading_price_stamp) / trading_price_stamp)
                    virtual_balance_stamp *= 1 + virtual_margin
                else:
                    # 청산1. stoploss 3%
                    virtual_margin = ((low[i] - trading_price_stamp) / trading_price_stamp)
                    sig1 = virtual_margin <= -1.0 * stop_loss
                    if sig1:
                        virtual_balance_stamp *= 1 - stop_loss
                    else:
                        virtual_balance_stamp *= 1 + virtual_margin

                hhv = 0

                virtual_balance = virtual_balance_stamp * (1.0 - commission - slipage)
                trading_count += 1
                if close[i] - trading_price_stamp > 0:
                    trading_odds += 1

                if run_mode == df.MODE_SIM:
                    fn.time_print("[" + time[i].strftime('%Y-%m-%d %H:%M') + "] SELL: " +
                                  str(round(open[i], 2)))
                    fn.time_print("=> TOTAL: " + str(virtual_balance))

            # cur_volatility 계산
            for j in range(len(curd_ohlcvs)):
                if time[i].strftime('%Y-%m-%d %H:%M') == timed[j].strftime('%Y-%m-%d %H:%M'):
                    day_index = j
                    break

            cur_volatility = k * day_range[day_index - 1]
            break_up = high[i] >= opend[day_index] + cur_volatility

            # 매수 전, 당일 시가까지 아는 상황
            if cur_signal != df.SIGNAL_BUY and break_up:
                cur_signal = df.SIGNAL_BUY
                trading_price_stamp = opend[day_index] + cur_volatility

                llv = low[i - 2]
                if llv > low[i - 1]:
                    llv = low[i - 1]

                if llv > low[i]:
                    llv = low[i]

                if hhv < trading_price_stamp:
                    hhv = trading_price_stamp

                virtual_balance_stamp = virtual_balance * (1.0 - commission - slipage)
                virtual_balance = virtual_balance_stamp

                if run_mode == df.MODE_SIM:
                    fn.time_print("[" + time[i].strftime('%Y-%m-%d %H:%M') + "] BUY: " + str(
                        round(trading_price_stamp, 2)))
            else:
                cur_signal = df.SIGNAL_NONE

            holding_balance *= 1 + (close[i] - close[i - 1]) / close[i - 1]

        result.append(virtual_balance)
        holding_result.append(holding_balance)

    if run_mode == df.MODE_SIM:
        fn.time_print(
            "[" + time[len(time) - 1].strftime('%Y-%m-%d %H:%M') + "] LAST: " +
            str(round(open[len(open) - 1], 2)) + " / BREAK_DOWN: " +
            str(round(open[len(open) - 1], 2)) + " / STOP_LOSS: " +
            str(round(trading_price_stamp * (1 - stop_loss), 2)))
        fn.time_print(
            "=> TOTAL: " + str(round(virtual_balance, 2)) + " / INVESTED: " +
            str(round(virtual_balance_stamp, 2)))

        if trading_count > 0:
            fn.time_print("- 매매 횟수 : " + str(trading_count) + " / 매매 승률 : " +
                          str(round(trading_odds / trading_count * 100, 2)) + ("%"))
        else:
            fn.time_print("- 매매 횟수 : 0 / 매매 승률 : 0%")

        label_strategy = "Larry Williams trading strategy "
        plt.plot(time, result, label=label_strategy)
        plt.plot(time, holding_result, label='Buy and hold strategy')
        plt.legend(loc=2)
        plt.xlabel('Time')
        plt.ylabel('Value')
        plot_title = symbol + " Backtesting Result"
        plt.title(plot_title)
        plt.xticks([time[0], time[round((len(time)) / 2)], time[len(time) - 1]])
        plt.show()

        return df.SIGNAL_NONE
    else:
        return cur_signal
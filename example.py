"""
binance = ccxt.binance()

# ticker 조회
markets = binance.fetch_tickers()
print(markets.keys())

# 현재가 조회
ticker = binance.fetch_ticker('ETH/BTC')
print(ticker['open'], ticker['high'], ticker['low'], ticker['close'])

# 종가는 오전 9시 기준 발생
# 과거 데이터 조회 / timestamp, open, high, low, close, volume
ohlcvs = binance.fetch_ohlcv('ETH/BTC')
print(ohlcvs)
for ohlc in ohlcvs:
    print(datetime.fromtimestamp(ohlc[0]/1000).strftime('%Y-%m-%d %H:%M:%S'))


# 호가 조회
orderbook = binance.fetch_order_book('ETH/BTC')
print(orderbook['bids'])
print(orderbook['asks'])
for ask in orderbook['asks']:
   print(ask[0], ask[1])

# 잔고 조회
binance = ccxt.binance({
    'apiKey': '본인 API KEY',
    'secret': '본인 Secret KEY',
})
balance = binance.fetch_balance()
print(balance.keys())
print(balance['BTC']['free'], balance['BTC']['used'], balance['BTC']['total'])

# 지정가 매수 : 티커, 주문 수량, 주문 가격 ('orderId': 주문 조회 및 취소)
order = binance.create_limit_buy_order('XRP/BNB', 50, 0.03)
print(order)

# 시장가 매수 : 티커, 주문 수량
order = binance.create_limit_buy_order('XRP/BNB', 50)
print(order)

# 주문 체결 여부 : 주문 아이디, 티커
resp = binance.fetch_order(2312440, "XRP/BNB")
print(resp)

# 주문 취소
resp = binance.cancel_order(2312440, 'XRP/BNB')
print(resp)

# 주문 체결 여부 : 주문 아이디, 티커
{'info': {'symbol': 'EOSUSDT', 'orderId': 1349119939, 'orderListId': -1,
    'clientOrderId': 'Clwyenvx6fu0QMo065gBkI', 'price': '2.46930000',
    'origQty': '5.48000000', 'executedQty': '5.48000000',
    'cummulativeQuoteQty': '13.51751600', 'status': 'FILLED',
    'timeInForce': 'GTC', 'type': 'LIMIT', 'side': 'BUY',
    'stopPrice': '0.00000000', 'icebergQty': '0.00000000', 'time': 1610382512720,
    'updateTime': 1610382512720, 'isWorking': True,
    'origQuoteOrderQty': '0.00000000'}, 'id': '1349119939',
    'clientOrderId': 'Clwyenvx6fu0QMo065gBkI', 'timestamp': 1610382512720,
    'datetime': '2021-01-11T16:28:32.720Z', 'lastTradeTimestamp': None,
    'symbol': 'EOS/USDT', 'type': 'limit', 'timeInForce': 'GTC', 'side': 'buy',
    'price': 2.4693, 'amount': 5.48, 'cost': 13.517516, 'average': 2.4667, 'filled': 5.48,
    'remaining': 0.0, 'status': 'closed', 'fee': None, 'trades': None}
"""


"""""
# BackTrader 예제
from datetime import datetime
import backtrader as bt


# Create a subclass of Strategy to define the indicators and logic

class SmaCross(bt.Strategy):
# list of parameters which are configurable for the strategy
params = dict(
    pfast=14,  # period for the fast moving average
    pslow=25  # period for the slow moving average
)
def __init__(self):
    sma1 = bt.ind.SMA(period=self.p.pfast)  # fast moving average
    sma2 = bt.ind.SMA(period=self.p.pslow)  # slow moving average
    self.crossover = bt.ind.CrossOver(sma1, sma2)  # crossover signal
def next(self):
    if not self.position:  # not in the market
        if self.crossover > 0:  # if fast crosses slow to the upside
            self.buy()  # enter long

    elif self.crossover < 0:  # in the market & cross to the downside
        self.close()  # close long position
"""

"""
cerebro = bt.Cerebro()  # create a "Cerebro" engine instance
 삼성전자의 '005930.KS' 코드를 적용하여 데이터 획득
data = bt.feeds.YahooFinanceData(dataname='BTC-USD',
                                 fromdate=datetime(2015, 1, 1),
                                 todate=datetime(2020, 12, 31))
cerebro.adddata(data)
cerebro.broker.setcash(1000000)  # 초기 자본 설정
cerebro.broker.setcommission(commission=0.001)  # 매매 수수료는 0.1% 설정
cerebro.addstrategy(SmaCross)  # 자신만의 매매 전략 추가
cerebro.run()  # 백테스팅 시작
cerebro.plot()  # 그래프로 보여주기
"""
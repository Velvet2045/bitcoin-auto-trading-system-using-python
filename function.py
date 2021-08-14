from coinmarketcapapi import CoinMarketCapAPI
from datetime import datetime
import configparser
import re
import requests
import json
import math

def get_coin_rank():
    cmc = CoinMarketCapAPI('f9c2206e-7471-4e81-b372-cbac7ebe0a73')

    coin_list = cmc.cryptocurrency_listings_latest()

    pat = r'\'symbol\': \'(.+?)\', \'slug\''
    regex = re.compile(pat)
    rank_list = regex.findall(str(coin_list))

    try:
        rank = rank_list.index('USDT')
    except ValueError:
        rank = -1

    if rank > -1:
        rank_list.remove('USDT')

    new_rank_list = []
    for r in rank_list:
        if r not in new_rank_list:
            new_rank_list.append(r)

    return new_rank_list

def save_ini(path, ini):
    # 설정파일 저장
    with open(path, 'w', encoding='utf-8') as configfile:
        ini.write(configfile)

def set_ini(path, section, key, value):
    ini = configparser.ConfigParser()
    ini.read(str(path))

    if str(section) in ini:
        ini[str(section)][str(key)] = str(value)
    else:
        ini[str(section)] = {}
        ini[str(section)][str(key)] = str(value)

    # 설정파일 저장
    with open(str(path), 'w', encoding='utf-8') as configfile:
        ini.write(configfile)

    return ini

def get_ini(name, section, key, value='0'):
    ini = configparser.ConfigParser()
    ini.read(str(name))

    if str(section) in ini:
        if str(key) in ini[str(section)]:
            value = ini[str(section)][str(key)]

    return value

def get_keys_num(name, section):
    ini = configparser.ConfigParser()
    ini.read(name)

    return len(ini.items(str(section)))

def get_decimal_places(input, n=0):
    output = 0
    for i in input:
        try:
            str_dec = str(i[n]).split('.')[1]
            len_dec = len(str_dec)
            if len_dec > output:
                output = len_dec
        except IndexError:
            output = 0
            pass

    return output

def get_decimal_round_off(input, n):
    output = float(math.floor(input))
    if n > 0:
        output = float(math.floor(input * math.pow(10, n)) / math.pow(10, n))

    return output

def web_request(method_name, url, dict_data=False, is_urlencoded=True):
    """Web GET or POST request를 호출 후 그 결과를 dict형으로 반환 """
    method_name = method_name.upper()  # 메소드이름을 대문자로 바꾼다
    if method_name not in ('GET', 'POST'):
        raise Exception('method_name is GET or POST plz...')

    if method_name == 'GET':  # GET방식인 경우
        if dict_data:
            response = requests.get(url=url, params=dict_data)
        else:
            response = requests.get(url=url)
    elif method_name == 'POST':  # POST방식인 경우
        if is_urlencoded is True:
            response = requests.post(url=url, data=dict_data,
                                     headers={'Content-Type': 'application/x-www-form-urlencoded'})
        else:
            response = requests.post(url=url, data=json.dumps(dict_data), headers={'Content-Type': 'application/json'})

    dict_meta = {'status_code': response.status_code, 'ok': response.ok, 'encoding': response.encoding,
                 'Content-Type': response.headers['Content-Type']}
    if 'json' in str(response.headers['Content-Type']):  # JSON 형태인 경우
        return {**dict_meta, **response.json()}
    else:  # 문자열 형태인 경우
        return {**dict_meta, **{'text': response.text}}


def web_logging(url, level, strategy, ticker, signal, price, count, state):
    # GET방식 호출 테스트
    get_url = url + "?Level=" + str(level) + "&Strategy=" + str(strategy) + "&Ticker=" + ticker + "&Signal=" + \
              str(signal) + "&Price=" + str(price) + "&Count=" + str(count) + "&State=" + str(state)
    # data = {'uid': 'happy'}         # 요청할 데이터
    response = web_request(method_name='GET', url=get_url)  # , dict_data=data)

    if response['ok'] == True:
        return True
    else:
        return False

def time_print(strPrint):
    print(datetime.now().strftime('[%Y/%m/%d %H:%M:%S] ') + str(strPrint))
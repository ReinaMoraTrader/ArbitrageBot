import json
import numpy as np
from decimal import *
import math
import time
import sqlite3
import datetime
import logging
import sys, os
from enum import Enum
from urllib.parse import urlparse
from configparser import ConfigParser, NoSectionError

import ccxt

CONFIG = ConfigParser()
CONFIG.read('quercusbot.conf')

#logfile = datetime.now().strftime('quercusbot_%Y_%m_%d.log')
err_time = time.strftime("%Y.%m.%d")
errfile = "log\\" + err_time + ".log"

# Create LOGERR
LOGERR = logging.getLogger()
LOGERR.setLevel(logging.INFO)
# Create file handler and set level to debug
fh = logging.FileHandler(errfile, mode='a', encoding=None, delay=False)
fh.setLevel(logging.INFO)
# Create formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# Add formatter to handlers
fh.setFormatter(formatter)
# Add handlers to LOGERR
LOGERR.addHandler(fh)


class Utils(object):
    def __init__(self, exchanges, baseAsset, quoteAsset):
        self.EXCHANGES = exchanges
        self.SHAPE = len(exchanges)
        self.baseAsset = baseAsset
        self.quoteAsset = quoteAsset

    @staticmethod
    def getCoin(coin, exchange):
        if CONFIG.has_option(exchange, 'Coins'):
            s = CONFIG.get(exchange, 'Coins')
            coins = dict(item.split(":") for item in s.split(","))
            return coins.get(coin, coin.upper())
        else:
            return coin.upper()

    @staticmethod
    def getPairFormat(exchange, baseAsset, quoteAsset):
        bAsset = Utils.getCoin(baseAsset, exchange)
        qAsset = Utils.getCoin(quoteAsset, exchange)
        pairFormat = CONFIG.get(exchange, 'PairFormat')

        return(pairFormat.format(bAsset, qAsset))

    def minOrderSize(self, exchange):
        minQty = []

        # Pair Strings for accessing API responses
        bSym = Utils.getCoin(self.baseAsset, exchange)
        qSym = Utils.getCoin(self.quoteAsset, exchange)
        symbol = Utils.getPairFormat(exchange, self.baseAsset, self.quoteAsset)

        binanceInfo = binanceAPI.get_exchange_info()
        bitfinexInfo = bitfinexPublicAPI.symbols_details()
        bittrexInfo = bittrexAPI.get_markets()

        symBinance = Utils.getPairFormat('Binance', self.baseAsset, self.quoteAsset)
        symBitfinex = Utils.getPairFormat('Bitfinex', self.baseAsset, self.quoteAsset)
        symBittrex = Utils.getPairFormat('Bittrex', self.baseAsset, self.quoteAsset)

        for item in binanceInfo['symbols']:
            if item['symbol'].upper() == symBinance:
                minQty.append(float(item['filters'][1]['minQty']))

        for item in bitfinexInfo:
            if item['pair'].upper() == symBitfinex:
                minQty.append(float(item['minimum_order_size']))

        for item in bittrexInfo['result']:
            if item.get('MarketName') == symBittrex:
                minQty.append(float(item['MinTradeSize']))

        # return de minimum trade
        return float(max(minQty))


    @staticmethod
    def staticmethod_minOrderSize(baseAsset, quoteAsset):

        minQty = []

        binanceAPI = Binance('ApiKey', 'SecretKey')
        binanceBalance = binanceAPI.get_exchange_info()

        bitfinexAPI = Bitfinex.Client()
        exchangeInfo = bitfinexAPI.symbols_details()


        for item in binanceBalance['symbols']:
            if item['symbol'] == 'BTGBTC':
                print(item)
                print(item['filters'][1]['minQty'])

                minQty.append(float(item['filters'][1]['minQty']))

        for item in exchangeInfo:

            if item['pair'] == 'btgbtc':
                #print(post)
                print(item['minimum_order_size'])
                minQty.append(float(item['minimum_order_size']))

        return float(max(minQty))


    def _encode_data(self, data):
        data = json.dumps(data) if data else data
        return data


class Balance(object):
    def __init__(self, exchanges, baseAsset, quoteAsset):
        self.EXCHANGES = exchanges
        self.SHAPE = len(exchanges)
        self.baseAsset = baseAsset
        self.quoteAsset = quoteAsset
        self.trade = True

    def setTrue(self):
        self.trade = True

    def setFalse(self):
        self.trade = False

class Trade(object):
    DB_QUERCUS = 'db/quercus.db'

    def __init__(self, exchanges, baseAsset, quoteAsset):
        #self.conn = sqlite3.connect(self.DB_QUERCUS)
        #self.cur = self.conn.cursor()
        #self.cur.execute('''CREATE TABLE IF NOT EXISTS Balance(exchange text, symbol text, amount real, PRIMARY KEY(exchange, symbol))''')
        #self.conn.commit()
        self.EXCHANGES = exchanges
        self.SHAPE = len(exchanges)
        self.baseAsset = baseAsset
        self.quoteAsset = quoteAsset
        self.OrderBook = {}
        self.TICKERS = np.zeros(self.SHAPE , dtype={'names':('exchange', 'bid', 'ask'),'formats':('U16', 'f8', 'f8')})
        self.datetime_ini = datetime.datetime.now()
        self.RECV_WINDOW=10000000
        self.EXCH = {}
        self.symbol = '{0}/{1}'.format(baseAsset,quoteAsset)

        self.conn = None
        self.cursor = None
        self.open(self.DB_QUERCUS)

        params = {}
        for id in exchanges:
            # Create Exchange API Objects - Load ApiKey & SecretKey
            ApiKey=CONFIG.get(id, 'ApiKey')
            Secret=CONFIG.get(id, 'Secret')

            if id == 'Binance':
                params = {'apiKey': ApiKey,'secret': Secret,'timeout': 30000,'enableRateLimit': True,}
            else:
                params = {'apiKey': ApiKey,'secret': Secret,}

            exchange = getattr(ccxt, CONFIG.get(id, 'Class'))(params)
        
            # save it in a dictionary under its id for future use
            self.EXCH[id] = exchange


    def __del__(self):
        self.conn.close()

    def __exit__(self,exc_type,exc_value,traceback):
        if self.conn:
            self.conn.commit()
            self.cursor.close()
            self.conn.close()

    def open(self,name):
        try:
            self.conn = sqlite3.connect(name);
            self.cursor = self.conn.cursor()

        except sqlite3.Error as e:
            print("Error connecting to database!")

    def createBalance(self):
        with sqlite3.connect(self.DB_QUERCUS) as conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS Balance(exchange text, symbol text, amount real, PRIMARY KEY(exchange, symbol))")            
            conn.commit()
            #cur.close()
            #conn.close()


    def getTradePrecision(self):
        minQty = []
        maxTaker = []
        maxMaker = []
        power = []
        makers = {}
        takers = {}

        for exchange in self.EXCHANGES:

            markets = self.EXCH[exchange].load_markets() 

            try:
                value = markets[self.symbol]['limits']['amount']['min']
                cost = markets[self.symbol]['limits']['cost']['min']
                maker = markets[self.symbol]['maker']
                taker = markets[self.symbol]['taker']
            except:
                value = 0.0
                cost  = 0.0
                maker = 0.0
                taker = 0.0

            maxMaker.append(abs(float(maker)))
            maxTaker.append(abs(float(taker)))
            minQty.append(cost)

            makers[exchange] = abs(float(maker))
            takers[exchange] = abs(float(taker))

            if value != None:
                lot = round(float(value)) if float(value).is_integer() else float(value)
                

            d = Decimal(str(lot))
            power.append(abs(d.as_tuple().exponent))

        MinTradeSize = max(minQty)

        return {'MinSize':MinTradeSize,'Precision':min(power),'Maker':1-max(maxMaker),'Taker':1-max(maxTaker),'Makers':makers,'Takers':takers}

        #return {'MinSize':MinTradeSize,'Precision':min(power)}



    def getTradePrecision_Old(self):
        minQty = []
        maxTaker = []
        maxMaker = []
        power = []
        makers = {}
        takers = {}

        for exchange in self.EXCHANGES:

            markets = self.EXCH[exchange].load_markets() 

            try:
                value = markets[self.symbol]['limits']['amount']['min']
                maker = markets[self.symbol]['maker']
                taker = markets[self.symbol]['taker']
            except:
                value = None
                maker = 0.0
                taker = 0.0

            maxMaker.append(abs(float(maker)))
            maxTaker.append(abs(float(taker)))

            makers[exchange] = abs(float(maker))
            takers[exchange] = abs(float(taker))

            if value != None:
                lot = round(float(value)) if float(value).is_integer() else float(value)
                minQty.append(lot)

            d = Decimal(str(lot))
            power.append(abs(d.as_tuple().exponent))

        qty = max(minQty)
        exp = math.pow(10, min(power))

        rnd = math.ceil(qty*exp)/exp 

        MinTradeSize = round(float(rnd)) if float(rnd).is_integer() else float(rnd)

        return {'MinSize':MinTradeSize,'Precision':min(power),'Maker':1-max(maxMaker),'Taker':1-max(maxTaker),'Makers':makers,'Takers':takers}

        #return {'MinSize':MinTradeSize,'Precision':min(power)}


    # Get Book: Loads the book offers specific exchange.
    # params: exchange: string (ex: 'Bittrex')
    #             type: string (BUY|SELL)
    # return: Quantity
    def getOrderBook(self, exchange, _type):
        # Load Buy or Sell Book from Exchange, Fail Gracefully
        try:
            # Pair Strings for accessing API responses

            typeBook = 'asks' if _type == 'ask' else 'bids'
            orderBook = self.EXCH[exchange].fetch_order_book(self.symbol)

            price    = orderBook[typeBook][0][0]
            quantity = orderBook[typeBook][0][1]

            amount = 0.0 if quantity is None else float(quantity)

            #print('{:-<15} - Amount: {: >10.5f} - Time elpased: {}'.format(exchange, amount, datetime.datetime.now() - self.datetime_ini))

            try:
                self.OrderBook[exchange][_type] = [price,amount]
            except KeyError:
                self.OrderBook[exchange] = {_type: [price,amount]}

        except Exception as err:
            # The exception instance and  __str__ allows args to be printed directly.
            exc_type, exc_obj, exc_tb = sys.exc_info()
            LOGERR.error('Line {} - Failed for TypeError {} ({}).'.format(exc_tb.tb_lineno,type(err), err))

        return amount


    def getBalances(self):
        balances={}
        try:
            for row in self.cursor.execute('SELECT * FROM balance'):
                exchange = row[0]
                symbol = row[1]
                amount = row[2]
                try:
                    balances[exchange][symbol] = float(amount)
                except KeyError:
                    balances[exchange] = {symbol:float(amount)}
            return balances

        except Exception as err:
            # The exception instance and  __str__ allows args to be printed directly.
            exc_type, exc_obj, exc_tb = sys.exc_info()
            LOGERR.error('Line {} - Failed for TypeError {} ({}).'.format(exc_tb.tb_lineno,type(err), err))


    def getBalance(self, exchange, asset):
        # Get Balance Information.
        try:
            balance = self.EXCH[exchange].fetch_balance()

            try:
                amount = balance['total'][asset]
            except KeyError:
                amount = 0

            amounts = [(exchange, asset, amount),]
            print(amounts)

            return amount

        except Exception as err:
            # The exception instance and  __str__ allows args to be printed directly.
            exc_type, exc_obj, exc_tb = sys.exc_info()
            LOGERR.error('Line {} - Failed for TypeError {} ({}).'.format(exc_tb.tb_lineno,type(err), err))


    def setBalance(self, exchange, asset):
        # Get Balance Information.
        try:
            balance = self.EXCH[exchange].fetch_balance()

            try:
                amount = balance['total'][asset]
            except KeyError:
                amount = 0

            amounts = [(exchange, asset, amount),]
            print(amounts)

            # with sqlite3.connect(self.DB_QUERCUS) as conn:
            #     cur = conn.cursor()
            #     cur.execute("INSERT INTO Balance (exchange, symbol, amount) VALUES (?, ?, ?)", (exchange, asset, amount))
            #     conn.commit()
            #     cur.close()
            #     conn.close()

            self.cursor.execute("INSERT OR REPLACE INTO Balance (exchange, symbol, amount) VALUES (?, ?, ?)", (exchange, asset, amount))
            self.conn.commit()

        except Exception as err:
            # The exception instance and  __str__ allows args to be printed directly.
            exc_type, exc_obj, exc_tb = sys.exc_info()
            LOGERR.error('Line {} - Failed for TypeError {} ({}).'.format(exc_tb.tb_lineno,type(err), err))

    def setBalances(self, exchanges):
        self.trade = False
        #time.sleep(10)

        dateTime = time.strftime("%Y-%m-%d %H:%M:%S")
        SHAPE = len(exchanges)


        # Get Balance Information.
        for i in range(SHAPE):
            try:
                #exchange = self.EXCHANGES[i]
                exchange = exchanges[i]
                bQuantity = 0.0
                qQuantity = 0.0

                balance = self.EXCH[exchange].fetch_balance()

                try:
                    bQuantity = balance['total'][self.baseAsset]
                except KeyError:
                    bQuantity = 0

                try:
                    qQuantity = balance['total'][self.quoteAsset]
                except KeyError:
                    qQuantity = 0

                bQty = 0.0 if bQuantity is None else float(bQuantity)
                qQty = 0.0 if qQuantity is None else float(qQuantity)


                amounts = [(exchange, self.baseAsset, bQty),(exchange, self.quoteAsset, qQty),]

                # with sqlite3.connect(self.DB_QUERCUS) as conn:
                #     cur = conn.cursor()
                #     cur.executemany('INSERT OR REPLACE INTO balance VALUES (?,?,?)', amounts)
                #     conn.commit()
                #     cur.close()
                #     conn.close()

                self.cursor.executemany('INSERT OR REPLACE INTO balance VALUES (?,?,?)', amounts)
                self.conn.commit()

                print('Updated {} balance'.format(exchange))
                print(amounts)

                self.trade = True


            except Exception as err:
                # The exception instance and  __str__ allows args to be printed directly.
                exc_type, exc_obj, exc_tb = sys.exc_info()
                LOGERR.error('Line {} - Failed for TypeError {} ({}). Exchange: <{}>'.format(exc_tb.tb_lineno,type(err), err, exchange))




    # New Order: Send in a new order.
    # params: exchange: string (ex: 'Bittrex')
    #           symbol: string (ex: 'ETH-BTC')
    #             side: string (BUY|SELL)
    #         quantity: (float, str or decimal)
    #            price: (float, str or decimal)
    #        orderType: (str, optional): LIMIT or MARKET.
    #      timeInForce: timeInForce (str, optional): GTC or IOC.
    # return: API response
    def newOrder(self, exchange, side, quantity, price, orderType='limit'):
        # Load Buy or Sell Book from Exchange, Fail Gracefully

        try:
            # Pair Strings for accessing API responses
            bSym = Utils.getCoin(self.baseAsset, exchange)
            qSym = Utils.getCoin(self.quoteAsset, exchange)


            # exchange.create_limit_buy_order(symbol, amount, price)

            # bitcoin contract according to https://github.com/ccxt/ccxt/wiki/Manual#symbols-and-market-ids
            # Limit or 'Market', or 'Stop' or 'StopLimit'
            # sell or buy

            # extra params and overrides
            params = {'stopPx': 6000.0,}

            order = self.EXCH[exchange].create_order(self.symbol , orderType, side, quantity, price, params)
            print(order)


            # $hitbtc->create_order ('BTC/USD', 'limit', 'buy', 1, 3000, array ('clientOrderId' => '123'));


        except Exception as err:
            # The exception instance and  __str__ allows args to be printed directly.
            exc_type, exc_obj, exc_tb = sys.exc_info()
            LOGERR.error('Line {} - {} - Failed for TypeError {} ({}).'.format(exc_tb.tb_lineno,exchange,type(err), err))

        return order

    # Get Book: Loads the book offers specific exchange.
    # params: exchange: string (ex: 'Bittrex')
    #             type: string (BUY|SELL)
    # return: Quantity
    def getTicker(self, threadId, exchange):

        # Pair Strings for accessing API responses
        bSym = Utils.getCoin(self.baseAsset, exchange)
        qSym = Utils.getCoin(self.quoteAsset, exchange)
        #symbol = Utils.getPairFormat(exchange, self.baseAsset, self.quoteAsset)

        symbol = '{0}/{1}'.format(self.baseAsset, self.quoteAsset)

        try:
            ticker = self.EXCH[exchange].fetch_ticker(symbol)
            bidPrice = ticker['bid']
            askPrice = ticker['ask']

            try:
                self.TICKERS[threadId] = (exchange, float(bidPrice), float(askPrice))

            except TypeError:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                LOGERR.error('01Line {} - <{}> Failed for TypeError {} ({}).'.format(exc_tb.tb_lineno,exchange,type(err), err))
                LOGERR.error('Failed for TypeError. Object of inappropriate type. Exchange: {} -> askPrice Type:{} | bidPrice: Type:{}'.format(exchange, type(askPrice), type(bidPrice)))

        except Exception as err:
            # The exception instance and  __str__ allows args to be printed directly.
            exc_type, exc_obj, exc_tb = sys.exc_info()
            LOGERR.error('02Line {} - <{}> Failed for TypeError {} ({}).'.format(exc_tb.tb_lineno,exchange,type(err), err))
            LOGERR.error('Failed for TypeError. Object of inappropriate type. Exchange: {} -> askPrice Type:{} | bidPrice: Type:{}'.format(exchange, type(askPrice), type(bidPrice)))

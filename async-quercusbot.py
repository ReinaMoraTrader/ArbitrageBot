#!/usr/bin/env python
#Imports
import base
import json
import logging
import argparse
import time
import datetime
import sys
import threading
import ast
import math
from configparser import ConfigParser, NoSectionError

def main(argv):
	# Setup Argument Parser
	parser = argparse.ArgumentParser(description='Poloniex/Bittrex Arbitrage Bot')
	parser.add_argument('-b', '--baseAsset', default='BTC', type=str, required=False, help='symbol of your base coin [default: BTC]')
	parser.add_argument('-q', '--quoteAsset', default='USDT', type=str, required=False, help='symbol of your target coin [default: XMR]')
	parser.add_argument('-r', '--rate', default=1.05, type=float, required=False, help='minimum price difference, 1.01 is 1 percent price difference (exchanges charge .05 percent fee) [default: 1.01]')
	parser.add_argument('-m', '--max', default=1.5, type=float, required=False, help='maximum order size in target currency (0.0 is unlimited) [default: 0.0]')
	parser.add_argument('-i', '--interval', default=1, type=int, required=False, help='seconds to sleep between loops [default: 1]')
	parser.add_argument('-l', '--logfile', default='arbbot.log', type=str, required=False, help='file to output log data to [default: arbbot.log]')
	parser.add_argument('-d', '--dryrun', action='store_true', required=False, help='simulates without trading (API keys not required)')
	parser.add_argument('-v', '--verbose', action='store_true', required=False, help='enables extra console messages (for debugging)')
	parser.add_argument('-e', '--source', default='Bittrex,HitBTC,Bitfinex,Binance,Poloniex,Bitstamp', type=str, required=False, help='')
	args = parser.parse_args()


	BASE_ASSET = args.baseAsset
	QUOTE_ASSET = args.quoteAsset
	arbPair = '{0}-{1}'.format(BASE_ASSET, QUOTE_ASSET)
	dryrun = True if args.dryrun else False

	source = args.source
	src = source.split(',')


	EXCHANGES = args.source.split(',')
	SHAPE = len(EXCHANGES)

	log_time = time.strftime("%Y.%m.%d_")

	#logfile = datetime.now().strftime('quercusbot_%Y_%m_%d.log')
	logfile = "log\\" + log_time + arbPair + ".log"
	errfile = "log\\" + log_time + arbPair + "_err.log"

	# Disabled in Production mode
	#dryrun = True

	# Create Logger
	# Level: CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET
	logger = logging.getLogger()
	logger.setLevel(logging.INFO)
	# Create console handler and set level to debug
	ch = logging.StreamHandler()
	ch.setLevel(logging.INFO)
	# Create file handler and set level to debug
	fh = logging.FileHandler(logfile, mode='a', encoding=None, delay=False)
	fh.setLevel(logging.INFO)
	# Create formatter
	formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
	# Add formatter to handlers
	ch.setFormatter(formatter)
	fh.setFormatter(formatter)
	# Add handlers to logger
	logger.addHandler(ch)
	logger.addHandler(fh)

	amount = 0
	#BALANCES={}
	baseTrade = base.Trade(EXCHANGES, BASE_ASSET, QUOTE_ASSET)
	baseUtils = base.Utils(EXCHANGES, BASE_ASSET, QUOTE_ASSET)
	
	baseTrade.setBalances(EXCHANGES)
	#TICKERS = baseTrade.TICKERS

	TradePrecision  = baseTrade.getTradePrecision()
	MIN_SIZE  		= TradePrecision['MinSize']
	PRECISION 		= TradePrecision['Precision']
	MAKER 		    = TradePrecision['Maker']
	MAKERS 		    = TradePrecision['Makers']

	#print(TradePrecision)


	# Log Startup Settings
	logger.info('Arb Pair: {} | Rate: {} | Interval: {} | Min Order Size: {} | Max Order Size: {}'.format(arbPair, args.rate, args.interval, MIN_SIZE, args.max))
	if dryrun==True:
		logger.info("Dryrun Mode Enabled (will not trade)")


	class TickerThread (threading.Thread):
		def __init__(self, threadId, exchange):
			threading.Thread.__init__(self)
			self.threadId = threadId
			self.exchange = exchange
		def run(self):
			baseTrade.getTicker(self.threadId, self.exchange)

	class OrderBookThread (threading.Thread):
		def __init__(self, threadId, exchange, _type):
			threading.Thread.__init__(self)
			self.threadId = threadId
			self.exchange = exchange
			self.type = _type
		def run(self):
			QtyBook = baseTrade.getOrderBook(self.exchange, self.type)
			#print('{}:{}'.format(self.threadId,self.exchange))

	class BalanceThread (threading.Thread):
		def __init__(self, threadId, exchange, asset):
			threading.Thread.__init__(self)
			self.threadId = threadId
			self.exchange = exchange
			self.asset = asset
		def run(self):
			balance = baseTrade.getBalance(self.exchange, self.asset)
			BALANCES[self.exchange][self.asset] = balance
			#print('{}:{}'.format(self.threadId,self.exchange))

	class NewOrderThread (threading.Thread):
		def __init__(self, threadId, exchange, side, quantity, price):
			threading.Thread.__init__(self)
			self.threadId = threadId
			self.exchange = exchange
			self.side = side
			self.quantity = quantity
			self.price = price
		def run(self):
			result = baseTrade.newOrder(self.exchange, self.side, self.quantity, self.price)
			logger.info('Order {} {} -> result={}'.format(self.side ,self.exchange, result))


	def quit():
		logger.info('KeyboardInterrupt, quitting!')
		sys.exit()


	def truncate1(f, n):
		return math.floor(f * 10 ** n) / 10 ** n

	def truncate(f, n):
		# Truncates/pads a float f to n decimal places without rounding
		s = '%.12f' % f
		i, p, d = s.partition('.')
		num = '.'.join([i, (d+'0'*n)[:n]])
		if n == 0:
			return round(float(num))
		else:
			return float(num)

	# Main Loop
	while True:
		try:
			BALANCES = baseTrade.getBalances()

			datetime_ini = datetime.datetime.now()
			for i in range(SHAPE):
				exchange = EXCHANGES[i]
				thread = TickerThread(i, exchange)
				thread.start()
				thread.join()
			datetime_fin = datetime.datetime.now()

			logger.debug('Tiempo transcurrido Async: {}'.format(datetime_fin - datetime_ini))

			diffTime = str(datetime_fin - datetime_ini).split(':')[2]

			TICKERS = baseTrade.TICKERS

			minAsk=TICKERS['ask'].argmin()
			maxBid=TICKERS['bid'].argmax()


			ask=float(TICKERS[minAsk]['ask'])
			bid=float(TICKERS[maxBid]['bid'])

			qty = MIN_SIZE/bid
			exp = math.pow(10, PRECISION)
			rnd = math.ceil(qty*exp)/exp 
			MIN_TRADE_SIZE = round(float(rnd)) if float(rnd).is_integer() else float(rnd)


			try:
				exchange_buy=TICKERS[minAsk]['exchange']
				exchange_sell=TICKERS[maxBid]['exchange']

				balance_buy=BALANCES[exchange_buy][QUOTE_ASSET]
				balance_sell=BALANCES[exchange_sell][BASE_ASSET]

			except Exception as err:
				# The exception instance and  __str__ allows args to be printed directly.
				exc_type, exc_obj, exc_tb = sys.exc_info()
				logger.error('Line {} - Failed for TypeError {} ({}).'.format(exc_tb.tb_lineno,type(err), err))

				balance_buy=0.0
				balance_sell=0.0

			#INFO: Opportunity found but no trade will be generated (Demo mode)
			#WARNING: Opportunity found but no cash available. Trade canceled

			try:
				arbitrage = bid/ask
			except Exception as err:
				# The exception instance and  __str__ allows args to be printed directly.
				exc_type, exc_obj, exc_tb = sys.exc_info()
				logger.error('Line {} - Failed for TypeError {} ({}).'.format(exc_tb.tb_lineno,type(err), err))

				arbitrage = 0.0


			msgHead = '\n---- {} -------------------------  Order Size: {} Min/Max [{}/{}] ---------------- Rate/Current Rate: [{:.4f}/{:.4f}]'.format(arbPair, amount, MIN_TRADE_SIZE, args.max,args.rate, arbitrage)
			print(msgHead)

			for i in range(SHAPE):
				exchange = EXCHANGES[i]

				buy_sell = ''
				if (exchange == exchange_buy and arbitrage > 1): buy_sell = '-> BUY   {:.8f} '.format(ask) 
				if (exchange == exchange_sell and arbitrage > 1): buy_sell = '-> SELL  {:.8f} '.format(bid)

				try:
					bb = BALANCES[exchange][BASE_ASSET]
				except:
					bb=0.0

				try:
					tb = BALANCES[exchange][QUOTE_ASSET]
				except:
					tb=0.0

				# Print Prices
				msg = '@ {:d}. {:-<15} {:.5f} [BID {:.8f} | {:.8f} ASK] {: <25} Balance: {: >15.5f} {} - {:.5f} {}'.format(i,TICKERS[i]['exchange'],MAKERS[exchange],TICKERS[i]['bid'], TICKERS[i]['ask'], buy_sell,bb,BASE_ASSET,tb,QUOTE_ASSET)

				#logger.info(msg)
				print(msg)

			COND1 = '  '
			COND2 = '  '
			COND3 = '  '
			COND4 = '  '
			COND5 = '  '
			COND6 = '  '
			bidPriceBook = 0.0
			askPriceBook = 0.0
			askQtyBook = 0.0
			bidQtyBook = 0.0
			
			if arbitrage >= args.rate: COND1 = 'OK'
			if min(balance_buy/ask, balance_sell) > MIN_TRADE_SIZE:
				COND2 = 'OK'
			else:
				#logger.info('Balance buy {:.5f} @ {} or sell {:.5f} @ {} must be larger that the MinOrderSize ({:.5f}).'.format(MIN_ORDER_SIZE, balance_sell, exchange_sell, balance_buy/ask, exchange_buy))
				logger.debug('Balance buy {:.8f} @ {} or sell {:.8f} @ {} must be larger that the MinOrderSize ({:.5f}).'.format(balance_sell, exchange_sell, balance_buy/ask, exchange_buy, MIN_TRADE_SIZE))

			# Return if minumum arbitrage percentage is not met
			if float(arbitrage) >= float(args.rate) and min(balance_buy/ask, balance_sell) > MIN_TRADE_SIZE and exchange_buy != exchange_sell or dryrun==True:
			#if arbitrage >= args.rate and min(balance_buy/ask, balance_sell) > MIN_TRADE_SIZE:

				thread1 = OrderBookThread(0, exchange_buy,'ask')
				thread2 = OrderBookThread(1, exchange_sell,'bid')
				thread3 = BalanceThread(2, exchange_buy, QUOTE_ASSET)
				thread4 = BalanceThread(3, exchange_sell, BASE_ASSET)

				thread1.start()
				thread2.start()
				thread3.start()
				thread4.start()

				thread1.join()
				thread2.join()
				thread3.join()
				thread4.join()

				try:
					askQtyBook = baseTrade.OrderBook[exchange_buy]['ask'][1]
					bidQtyBook = baseTrade.OrderBook[exchange_sell]['bid'][1]
					askPriceBook = float(baseTrade.OrderBook[exchange_buy]['ask'][0])
					bidPriceBook = float(baseTrade.OrderBook[exchange_sell]['bid'][0])

					logger.debug('{:=<185}'.format('='))
					logger.debug('{} Sell(maxBID: {}) - {} Buy(minASK: {} - RATE: {:.5f}/{:.5f}'.format(exchange_sell,bid,exchange_buy,ask,bid/ask,bidPriceBook/askPriceBook))
					logger.debug('Ticker    = {}'.format(TICKERS.tolist()))
					logger.debug('OrderBook = {}'.format(baseTrade.OrderBook))

					#ask=float(askPriceBook)
					#bid=float(bidPriceBook)

					# Antes actualizo los balances con setBalance No haría falta porque ya lo actualicé !!!!!!!!!!!!
					#BALANCES = baseTrade.getBalances()

					try:
						balance_buy=BALANCES[exchange_buy][QUOTE_ASSET]
						balance_sell=BALANCES[exchange_sell][BASE_ASSET]
					except:
						balance_buy=0.0
						balance_sell=0.0

					#Find minimum order size
					tradesize = min(askQtyBook, bidQtyBook, balance_sell, balance_buy/ask) * MAKER

					logger.debug('askQtyBook:{:.5f} | bidQtyBook:{:.5f} | balance_sell: {:.5f} | balance_buy/ask: {:.5f} | MIN:{:.5f}'.format(askQtyBook, bidQtyBook, balance_sell, balance_buy/ask, tradesize))

					if args.max >= 0.0 and tradesize > args.max:
						logger.debug('Tradesize ({:.5f}) larger than maximum ({:.5f}), lowering tradesize.'.format(tradesize, args.max))
						tradesize = args.max

					if tradesize < MIN_TRADE_SIZE:
						logger.debug('Tradesize ({:.5f}) smaller than the minimum order size ({:.5f}). No trade was executed.'.format(tradesize, MIN_TRADE_SIZE))


					#Correction for price precision
					amount = truncate(tradesize,PRECISION)
					#amount = int(tradesize) if num_dec == 0 else truncate(tradesize,num_dec)

					# Print Trade Status & Balances
					msg_buy =  '{:-<15} Buy  -> Price: {:.8f} - Trade Size[{:.5f}] - ASK OrderBook[{:.5f}] - Balance {}[{:.5f}] -> {}[{:.5f}]'.format(exchange_buy, ask, tradesize, askQtyBook, QUOTE_ASSET, balance_buy, BASE_ASSET, balance_buy/ask)
					msg_sell = '{:-<15} Sell -> Price: {:.8f} - Trade Size[{:.5f}] - BID OrderBook[{:.5f}] - Balance {}[{:.5f}]'.format(exchange_sell, bid, tradesize, bidQtyBook, BASE_ASSET, balance_sell)
					print(msg_buy)
					print(msg_sell)

				except Exception as err:
					# The exception instance and  __str__ allows args to be printed directly.
					exc_type, exc_obj, exc_tb = sys.exc_info()
					logger.error('Line {} - Failed for TypeError {} ({}).'.format(exc_tb.tb_lineno,type(err), err))


				#Check if above min order size
				if bidPriceBook >= bid: COND3 = 'OK'
				if askPriceBook <= ask: COND4 = 'OK'
				if bidQtyBook > MIN_TRADE_SIZE: COND5 = 'OK'
				if askQtyBook > MIN_TRADE_SIZE: COND6 = 'OK'


				if tradesize > MIN_TRADE_SIZE and bidPriceBook >= bid and askPriceBook <= ask:

					logger.info('{:=<185}'.format('='))
					logger.info('=== OPPORTUNITY!!! === {:=<20} | Trade Size: [{:.2f}] | Min/Max Order Size: [{:.2f}/{:.2f}] | Rate/Current Rate: [{:.4f}/{:.4f}] ======================='.format(arbPair, amount, MIN_TRADE_SIZE, args.max,args.rate, arbitrage))
					logger.info('BUY  -> {:-<15} Price: {:.8f} Amount: {:.2f}'.format(exchange_buy,ask,amount))
					logger.info('SELL -> {:-<15} Price: {:.8f} Amount: {:.2f}'.format(exchange_sell,bid,amount))
					logger.info(msg_buy)
					logger.info(msg_sell)

					logger.info('{:=<120}'.format('='))
					logger.info('{} Sell(maxBID: {}) - {} Buy(minASK: {} - RATE: {:.5f}/{:.5f}'.format(exchange_sell,bid,exchange_buy,ask,bid/ask,bidPriceBook/askPriceBook))
					logger.info('Ticker    = {}'.format(TICKERS.tolist()))
					logger.info('OrderBook = {}'.format(baseTrade.OrderBook))
					#logger.info('Balance   = {}'.format(BALANCES))

					#Execute order
					if dryrun==False:

						thread4 = NewOrderThread(0, exchange_buy, 'buy', amount, '{:.8f}'.format(ask))
						thread5 = NewOrderThread(1, exchange_sell, 'sell', amount, '{:.8f}'.format(bid))

						thread4.start()
						thread5.start()

						thread4.join()
						thread5.join()

						baseTrade.setBalances(EXCHANGES)

					else:
						logger.info("Dryrun: skipping order")

					logger.info('{:=<120}'.format('='))
				else:
					logger.debug('Order size not above min order size {:.5f}, no trade was executed.'.format(MIN_TRADE_SIZE))


			print('{:-<120} Execution conditions -----'.format('-'))
			print('  1. Rate >= {:.4f}.....................[{}]  {: >10.4f} >= {:.4f} '.format(args.rate,COND1,arbitrage,args.rate))
			print('  2. Balance > MIN_TRADE................[{}]  {: >10.5f} >  {:.5f} '.format(COND2,min(balance_buy/ask, balance_sell), MIN_TRADE_SIZE))
			print('  3. OderBook-Bid >= bid................[{}]  {: >10.7f} >= {:.7f} '.format(COND3,bidPriceBook, bid))
			print('  4. OderBook-Ask <= ask................[{}]  {: >10.7f} <= {:.7f} '.format(COND4,askPriceBook, ask))
			print('  5. OderBook-bidQtyBook > {:.3f}......[{}]  {: >10.3f} > {:.3f} '.format(MIN_TRADE_SIZE,COND5,bidQtyBook, MIN_TRADE_SIZE))
			print('  6. OderBook-askQtyBook > {:.3f}......[{}]  {: >10.3f} > {:.3f} '.format(MIN_TRADE_SIZE,COND6,askQtyBook, MIN_TRADE_SIZE))


			rang = args.interval
			for x in range(rang):
			    msg = '{:-^10}'.format(rang-x-1)
			    print(msg, end='', flush=True)
			    time.sleep(1)

		except Exception as err:
			# The exception instance and  __str__ allows args to be printed directly.
			exc_type, exc_obj, exc_tb = sys.exc_info()
			logger.error('Line {} - Failed for TypeError {} ({}).'.format(exc_tb.tb_lineno,type(err), err))

if __name__ == "__main__":
	main(sys.argv[1:])

# ArbitrageBot


Coded for python2.7+

```

Arbitrage Bot
Arbitrage Trading Bot for Cryptocurrency

usage: arbbot.py [-h] [-s SYMBOL] [-b BASEASSET] [-q QUOTEASSET] [-r RATE] [-i INTERVAL]
                 [-l LOGFILE] [-d] [-v]


Use CCXT – CryptoCurrency eXchange Trading Library
The CCXT library is used to connect and trade with cryptocurrency exchanges and payment processing services worldwide. It provides quick access to market data for storage, analysis, visualization, indicator development, algorithmic trading, strategy backtesting, bot programming, and related software engineering.

optional arguments:

  -h, --help            show this help message and exit
  -s SYMBOL, --symbol SYMBOL
                        symbol of your target coin [default: XMR]
  -b BASE ASSET, --baseAsset BASEASSET
                        symbol of your base coin [default: BTC]
  -q QUOTE ASSET, --quoteAsset QUOTEASSET
                        symbol of your base coin [default: USDT]
  -m RATE, --rate RATE  minimum price difference, 1.01 is 1 percent price

  -e EXCHANGES, --source 

                        difference (exchanges charge .05 percent fee)
                        [default: 1.01]
  -i INTERVAL, --interval INTERVAL
                        seconds to sleep between loops [default: 1]
  -l LOGFILE, --logfile LOGFILE
                        file to output log data to [default: arbbot.log]
  -d, --dryrun          simulates without trading (API keys not required)
  -v, --verbose         enables extra console messages (for debugging)

Example:
  async-quercusbot.py -b BTC -q USDT -r 1.0135 -m 0.15 -d -e Binance,Bittrex,Poloniex,HitBTC,Bitfinex,Bitstamp
  async-quercusbot.py -b BTG -q BTC -r 1.009 -m 2.5 -e Bittrex,Bleutrade,HitBTC,Bitfinex,Binance -i 3
  async-quercusbot.py -b ETH -q BTC -r 1.009 -m 0.15 -e Binance,Bittrex,Poloniex,HitBTC,Bitfinex,Bitstamp -i 3
  async-quercusbot.py -b BTG -s ETH -r 1.01 -m 2.5 -e Bittrex,HitBTC,Binance -i 3


```


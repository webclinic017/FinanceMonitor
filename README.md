# FinanceMonitor
FinanceMonitor - various functionality from html tables to plotting market indicators to scraping webpages for news stories. Runs in python 3.7


```pip3 install alpaca_trade_api
pip3 install numpy
pip3 install pandas matplotlib mplfinance numpy_ext watchdog
pip3 install numpy numpy_ext pandas scipy TA-lib matplotlib alpha_vantage html5lib nltk cython zigzag --user
```


May need to install the vader libraries
```
import nltk
nltk.download('vader_lexicon')
```

For options pricing, try
https://www.barchart.com/stocks/quotes/X/options

## Runs to download earnings and stock news from the TheFly. Need to setup a daily cron job to download and run.
```
getNews.py
```

### Downloads the earnings calendar and saves it as stockEarnings.csv. Then it iterates this list and updates the daily stock prices into a database. Each stock is saved in its own table in stocksAV.db Also downloads the past earnings predictions and observations to earningsCalendar.db. Both quarterlyEarnings and company overview (short info, etc with todays date) are saved
```
getEarnings.py
```

## Downloads data to stocksAV.db and writes an html table. 
```
buildTable.py
```
## Downloads data and plots many indicators. saves histograms and
## builds a webpage
```
channelTradingAll.py
```

## Building models and saving them.
```
trainOnEarnings.py # build a NN to predict response. Mostly seems to
predict buy. It is bad at finding the tails
trainOnEarningsLogistic.py # multicategory NN training
```

### Build database with earnings info. connects earnings and market indicators into a data base called earningsCalendarForTraining.db in a table call earningsInfo
```
analyzeEarnings.py
```

## scrap the web for short data
```
shortData.py
```

# Below are mostly notes on features to add
## Interesting websites to parse
```
https://eresearch.fidelity.com/eresearch/conferenceCalls.jhtml?tab=earnings&begindate=4/29/2021
https://marketchameleon.com/Calendar/Earnings #
https://finance.yahoo.com/calendar/earnings/?day=2021-05-26
```

## Way cheaper API
```
https://financialmodelingprep.com/developer/docs#Company-Quote
```

## Has the time the data was delivered for the earnings
```
https://financialmodelingprep.com/api/v3/income-statement/AAPL?limit=120&apikey=demo
```

## Another free option. well free to start with low latency
```
https://iexcloud.io/docs/api/
```

## Interesting to read
```
https://github.com/Syakyr/My-Trading-Project/tree/master/Risk%20Management
```

## Add the data for company info and historical earnings analyze daily rates relative to the SMA. some kind of reversion to the mean. can I build a return probability  using the MA, bolanger bands, etc? Maybe do it on the 5m time scale add in fibs plotting with the zigzag 

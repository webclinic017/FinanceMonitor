from alpaca_trade_api.rest import TimeFrame
from alpaca_trade_api.rest import REST
from alpaca_trade_api.stream import Stream
#from alpaca_trade_api import StreamConn
import alpaca_trade_api
from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.fundamentaldata import FundamentalData
from techindicators import techindicators
from sklearn import preprocessing
from keras.models import load_model
import datetime,time,os,pickle,socket
import pandas as pd
import numpy as np
import requests
import sqlite3,sys
import statsmodels.api as sm1
from statsmodels.sandbox.regression.predstd import wls_prediction_std
from dateutil.parser import parse
import urllib3
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib
from matplotlib.ticker import (MultipleLocator, AutoMinorLocator)
import base as baseB
NY = 'America/New_York'
# db_name the database name
def SQL_CURSOR(db_name='stocksAV.db'):
    """ SQL_CURSOR - Retrieve sqlite data base cursor
        
         Parameters:
         db_name - str
                File name
    """
    connection = sqlite3.connect(db_name)
    #cursor = connection.cursor()
    return connection

# append this entry to the sql table
def UpdateTable(stock, ticker, sqlcursor, index_label='Date'):
    """ UpdateTable - append this entry to the sql table
        
         Parameters:
         stock - pandas dataframe 
                Stock date with adj_close
         ticker - str
                Stock ticker
         sqlcursor - sqlite cursor
         index_label - str
                Index label
    """
    if index_label!=None:
        stock.to_sql(ticker, sqlcursor,if_exists='append', index=True, index_label=index_label)
    else:
        stock.to_sql(ticker, sqlcursor,if_exists='append', index=True)        

# try to read back info. if not, then update the SQL database
def ConfigTableFromPandas(tableName, ticker, sqlcursor, earnings, index_label='Date',tickerName='ticker'):
    """ ConfigTableFromPandas - search existing database to see if the stock is already stored. If so, do not request from the API to reduce data transfers
        
         Parameters:
         tableName - str
                Table name
         ticker - str
                Stock ticker
         sqlcursor - sqlite cursor
         earnings - pandas dataframe of stock earnings from alpha vantage
         index_label - str
                Date index label name
         tickerName - str
                attribute name for the ticker symbol in this sql data base
    """
    stock = None
    try:
        stock = pd.read_sql('SELECT * FROM %s WHERE %s="%s"' %(tableName,tickerName,ticker), sqlcursor) #,index_col='Date')
        if len(stock)==0 and len(earnings)>0: # if empty, then let's fill it
            UpdateTable(earnings, tableName, sqlcursor, index_label=None)
            return earnings
        # if not empty, then we need to merge
        stock[index_label]=pd.to_datetime(stock[index_label].astype(str), format='%Y-%m-%d')
        stock[index_label]=pd.to_datetime(stock[index_label])
        stock = stock.set_index(index_label)
        stock = stock.sort_index()
        today=datetime.datetime.now()
        if len(earnings)>0:
            earnings[index_label]=pd.to_datetime(earnings[index_label])
            today = earnings.sort_values(index_label)[index_label].values[-1]
            earnings=earnings.set_index(index_label)
            #print(today)
        StartLoading = True
        if len(earnings)>0 and (today - stock.index[-1])>datetime.timedelta(days=1,hours=12) and (StartLoading):
            stockCompact=earnings
            # make sure we only add newer dates
            #print(stockCompact)
            #print(stockCompact.dtypes)
            #print((today - stock.index[-1]).days)
            stockCompact = GetTimeSlot(stockCompact, days=(today - stock.index[-1]).days)
            UpdateTable(stockCompact, tableName, sqlcursor, index_label=index_label)
            stock = pd.concat([stock,stockCompact])
            stock.sort_index()
    except:
        print('%s is a new entry to the database....' %tableName)
        stock=earnings
        UpdateTable(stock, tableName, sqlcursor, index_label=None)

    return stock

# try to read back info. if not, then update the SQL database
def ConfigTable(ticker, sqlcursor, ts, readType, j=0, index_label='Date',hoursdelay=5):
    """ ConfigTable - search existing database to see if the stock is already stored. If so, do not request from the API to reduce data transfers
        
         Parameters:
         ticker - str
                Stock ticker
         sqlcursor - sqlite cursor
         readType - str
                full or compact for the amount of data to retrieve from the alpha vantage API
         j - int
                Number of API requests made. The number is limited, so we must keep track
         index_label - str
                Date index label name
         hoursdelay - int
                number of hours of delay for the data request
    """
    stock = None
    NewEntry=False
    try:
        stock = pd.read_sql('SELECT * FROM %s' %ticker, sqlcursor) #,index_col='Date')
    except (sqlite3.OperationalError, pd.io.sql.DatabaseError, IOError, EOFError) as e:
        print("Testing multiple exceptions. {}".format(e.args[-1]))
        pass
    try:
        # if we retrieved info, then try to process it
        stock[index_label]=pd.to_datetime(stock[index_label].astype(str), format='%Y-%m-%d')
        stock[index_label]=pd.to_datetime(stock[index_label])
        stock = stock.set_index(index_label)
        stock = stock.sort_index()

        # Let's check if the stock entries that we added had any splits. If so, drop the table and reload
        if 'splitcoef' in stock and len(stock)>5:
            stock_tmp = stock[-4:]
            if len(stock_tmp[stock_tmp.splitcoef!=1.0])>0:
                print('Stock split was found for %s' %ticker)
                sqlcursor.cursor().execute('DROP TABLE %s' %ticker)
                fsplit = open('split_stocks.txt','a')
                fsplit.write('%s\n' %ticker)
                fsplit.close()
                NewEntry=True
                sys.stdout.flush()
        
        today=datetime.datetime.now()
        StartLoading = True
        if stock.index[-1].weekday()==4 and (today - stock.index[-1])<datetime.timedelta(days=4):
            StartLoading=False
        if (today - stock.index[-1])>datetime.timedelta(days=1,hours=hoursdelay) and (StartLoading):
            has_entries=False
            try:
                if len(stock)>0:
                    stock = stock.set_index(index_label)                
                    stock = stock.sort_index()
                    stock.drop_duplicates(inplace=True)
                    has_entries=True
            except:
                pass
            try:
                stockCompact=runTickerAlpha(ts,ticker,'compact')
                j+=1
            except (socket.gaierror,ValueError,urllib3.exceptions.ProtocolError,ConnectionResetError,urllib3.exceptions.NewConnectionError,requests.exceptions.ConnectionError) as e:
                print("Testing multiple exceptions. {}".format(e.args[-1]))
                print('%s could not load compact....' %ticker)
                j+=1
                if has_entries:
                    return stock,j
                
                return [],j
            # make sure we only add newer dates
            stockCompact = GetTimeSlot(stockCompact, days=(today - stock.index[-1]).days)
            if len(stockCompact)>0 and len(stock)>0 and stockCompact.index[-1]!=stock.index[-1]:
                UpdateTable(stockCompact, ticker, sqlcursor, index_label=index_label)
                stock = pd.concat([stock,stockCompact])

                # Let's check if the stock entries that we added had any splits. If so, drop the table and reload
                if 'splitcoef' in stockCompact and len(stockCompact[stockCompact.splitcoef!=1.0])>0:
                    print('Stock split was found for %s' %ticker)
                    sqlcursor.cursor().execute('DROP TABLE %s' %ticker)
                    NewEntry=True
                    sys.stdout.flush()
            stock = stock.sort_index()
            before_len = len(stock)
            stock.drop_duplicates(inplace=True)
            if abs(before_len - len(stock))>0:
                print('Note: this many duplicates %s were removed for %s' %(abs(before_len - len(stock)),ticker))
                sys.stdout.flush()
    except:
        NewEntry=True
        if type(stock)==type(None) or len(stock)==0:
            print('%s is a new entry to the database....' %ticker)
    if NewEntry:
        has_entries=False
        try:
            if len(stock)>0:
                stock = stock.set_index(index_label)                
                stock = stock.sort_index()
                stock.drop_duplicates(inplace=True)
                has_entries=True
        except:
            pass
        
        try:
            stock=runTickerAlpha(ts,ticker,'full')
            j+=1
        except (ValueError,urllib3.exceptions.ProtocolError,ConnectionResetError,urllib3.exceptions.NewConnectionError,requests.exceptions.ConnectionError) as e:
            print("Testing multiple exceptions. {}".format(e.args[-1]))
            j+=1
            print('%s could not load....' %ticker)
            if has_entries:
                return stock,j
            return [],j
        UpdateTable(stock, ticker, sqlcursor, index_label=index_label)

    return stock,j

def ALPACA_REST(paper=True):
    """ ALPACA_REST - Return alpaca api
    """
    ALPACA_ID = os.getenv('ALPACA_ID')
    ALPACA_PAPER_KEY = os.getenv('ALPACA_PAPER_KEY')
    base_url = 'https://paper-api.alpaca.markets'
    if not paper:
        base_url = 'https://api.alpaca.markets'
    api = REST(ALPACA_ID,ALPACA_PAPER_KEY,base_url = base_url)
    return api

async def trade_callback(t):
    print('trade', t)
async def quote_callback(q):
    print('quote', q)
async def bars_callback(q):
    print('bars', q)

def ALPACA_STREAM(data_feed='sip'):
    """ ALPACA_STREAM - Stream data from alpaca api. these are live quotes
        data_feed - str - iex or SIP for pro
    """
    ALPACA_ID = os.getenv('ALPACA_ID')
    ALPACA_PAPER_KEY = os.getenv('ALPACA_PAPER_KEY')
    base_url = 'https://paper-api.alpaca.markets'
    stream = Stream(ALPACA_ID,ALPACA_PAPER_KEY,base_url = base_url,data_feed=data_feed,
    websocket_params = {
    "ping_interval": 10,
    "ping_timeout": 180,
    "max_queue": 5024,})  # <- replace to SIP if you have PRO subscription, iex is for non-pro
    return stream


#def ALPACA_STREAMCONN():
#    """ ALPACA_STREAMCONN - Stream data from alpaca api. these are live quotes
#    """
#    ALPACA_ID = os.getenv('ALPACA_ID')
#    ALPACA_PAPER_KEY = os.getenv('ALPACA_PAPER_KEY')
#    base_url = 'https://paper-api.alpaca.markets'
#    stream = StreamConn(ALPACA_ID,ALPACA_PAPER_KEY,base_url = base_url)  # <- replace to SIP if you have PRO subscription, iex is for non-pro
#    return stream

# subscribing to event
#stream.subscribe_trades(trade_callback, 'AAPL')
#stream.subscribe_quotes(quote_callback, 'IBM')
#stream.run()

def IS_ALPHA_PREMIUM():
    """ IS_ALPHA_PREMIUM - Decide if we should load the premium API key
    """
    ALPHA_PREMIUM = os.getenv('ALPHA_PREMIUM')
    if ALPHA_PREMIUM=='' or ALPHA_PREMIUM==None: return False
    if int(ALPHA_PREMIUM)==1:
        ALPHA_PREMIUM=True
    else:
        ALPHA_PREMIUM=False
    return ALPHA_PREMIUM

def IS_ALPHA_PREMIUM_WAIT_ITER():
    """ IS_ALPHA_PREMIUM_WAIT_ITER - Number of requests per minute depending on the API key
    """
    if IS_ALPHA_PREMIUM():
        return 30 # can update to 75 or 74
    return 4

def ALPHA_TIMESERIES():
    """ ALPHA_TIMESERIES - Return TimeSeries API from Alpha Vantage
    """
    ALPHA_ID = os.getenv('ALPHA_ID')
    ts = TimeSeries(key=ALPHA_ID)
    return ts
 
def get_company_earnings(symbol,annual=False,debug=False):
    """
    Returns the company information, financial ratios, 
    and other key metrics for the equity specified. 
    Data is generally refreshed on the same day a company reports its latest 
    earnings and financials.
    Keyword Arguments:
    symbol:  the symbol for the equity we want to get its data
    """
    import requests    
    ALPHA_ID = os.getenv('ALPHA_ID')
    _FUNCTION_KEY = 'EARNINGS'
    url = 'https://www.alphavantage.co/query?function=%s&symbol=%s&apikey=%s' %(_FUNCTION_KEY,symbol,ALPHA_ID)
    try:
        r = requests.get(url)
        data = r.json()
        data_pandas = pd.DataFrame()
        EarningsName='quarterlyEarnings'
        if annual:
            EarningsName='annualEarnings'
        #print(data)
        if debug:
            print(data['annualEarnings'])
            print(data['quarterlyEarnings'])
            print(data.keys())
        data_array = []
        #print(data[EarningsName])
        for val in data[EarningsName]:
            if debug:
                print(val)
            data_array.append([v for _, v in val.items()])
        data_pandas = pd.DataFrame(data_array, columns=[k for k, _ in data[EarningsName][0].items()])
        data_pandas['ticker']=symbol
        #return data_pandas
        return data
    except:
        print('error collecting company earnings')
        return []


def ALPHA_FundamentalData(output_format='pandas'):#pandas, json, csv, csvpan
    """ ALPHA_FundamentalData - Return fundamental data like earnings along with the output format

         Parameters:
         output_format - str
                output format pandas, json, csv, csvpan
    """
    
    ALPHA_ID = os.getenv('ALPHA_ID')
    fd = FundamentalData(key=ALPHA_ID,output_format=output_format)
    fd.get_company_earnings = get_company_earnings
    return fd

def GetTimeSlot(stock, days=365, startDate=None, addToStart=False,minutes=0,timez=None):
    """ GetTimeSlot - Filter time slot. Handle the datatime manipulation

         Parameters:
         stock - pandas dataframe with time index
         days - int
              Number of days from the current date that is requested.
         startDate - datetime
              date for the start date. end of the series. required for delays because the APIs are delayed
    """
    today=datetime.datetime.now()
    if type(timez)!=type(None):
        today=datetime.datetime.now(tz=timez)
    if startDate!=None:
        today = startDate
    past_date = today + datetime.timedelta(days=-1*days,minutes=minutes)
    if addToStart:
        past_date = startDate + datetime.timedelta(days=1*days,minutes=minutes)
        date=stock.truncate(before=startDate, after=past_date)
        return date
    if type(stock)==type([]):
        print('error this is a list')
        return stock
    date=stock.truncate(before=past_date, after=startDate)
    #date = stock[nearest(stock.index,past_date)]
    return date

def is_date(string, fuzzy=False):
    """
    Return whether the string can be interpreted as a date.

    :param string: str, string to check for date
    :param fuzzy: bool, ignore unknown tokens in string if True
    """
    try: 
        parse(string, fuzzy=fuzzy)
        return True

    except ValueError:
        return False

# detail reads the amount of data compact or full
def runTickerAlpha(ts, ticker, detail='full'): 
    """ runTickerAlpha - Request data from alpha vantage and format into a pandas data frame from a json

         Parameters:
         ts - alpha vantage TimeSeries
         ticker - str
              Stock ticker name
         detail - str
              full or compact
    """
    a=ts.get_daily_adjusted(ticker,detail)
    a_new={}
    cols = ['Date','open','high','low','close','volume']
    cols = ['Date','open','high','low','close','adj_close','volume','dividendamt','splitcoef']
    my_floats = ['open','high','low','close']
    my_floats = ['open','high','low','close','adj_close','volume','dividendamt','splitcoef']
    
    #'5. adjusted close', '6. volume', '7. dividend amount', '8. split coefficient'
    for ki in cols:
        a_new[ki]=[]
    
    for entry in a:
        for key,i in entry.items():
            if not is_date(key):
                continue
            #print(key)
            a_new['Date']+=[key]
            ij=0
            todays_values = list(i.values())
            for j in ['open','high','low','close','adj_close','volume','dividendamt','splitcoef']:
                a_new[j]+=[todays_values[ij]]
                ij+=1
    # format
    output = pd.DataFrame(a_new)
    output['Date']=pd.to_datetime(output['Date'].astype(str), format='%Y-%m-%d')
    output['Date']=pd.to_datetime(output['Date'])
    output[my_floats]=output[my_floats].astype(float)
    output['volume'] = output['volume'].astype(np.int64)
    output = output.set_index('Date')
    output = output.sort_index()
    return output

# Alpaca info
def runTicker(api, ticker, timeframe=TimeFrame.Day, start=None, end=None, limit=500000):
    """ runTicker - Request data from alpaca

         Parameters:
         api - alpaca API
         ticker - str
              Stock ticker name
         timeframe - TimeFrame object
              TimeFrame.Day, TimeFrame.Minute, TimeFrame.Second
         start - Date time object 
              Start date of request
         end - Date time object 
              End date of request
    """
    today=datetime.datetime.now()
    trade_days=[]
    if timeframe==TimeFrame.Day and start==None and end==None:
        yesterday = today + datetime.timedelta(days=-1)
        d1 = yesterday.strftime("%Y-%m-%d")
        fouryao = (today + datetime.timedelta(days=-364*4.5)).strftime("%Y-%m-%d")
        try:
            trade_days = api.get_bars(ticker, timeframe, fouryao, d1, 'raw',limit=limit).df
        except (TypeError,requests.exceptions.HTTPError) as e:
            print("Testing multiple exceptions. {}".format(e.args[-1]))
    elif start!=None and end!=None:
        #start_date = ''
        try:
            trade_days = api.get_bars(ticker, timeframe, start=start, end=end, adjustment='raw',limit=limit).df
        except (TypeError,requests.exceptions.HTTPError) as e:
            print("Testing multiple exceptions. {}".format(e.args[-1]))
    if type(trade_days) is not None and len(trade_days)>0:
        trade_days.index = pd.to_datetime(trade_days.index,utc=True).tz_convert(NY)
    return trade_days

#Get quotes
def getQuotesTS(ts, ticker):
    """ getQuotesTS - Request data from alpaca

         Parameters:
         api - alpaca API
         ticker - str
              Stock ticker name
    """
    return_json=[]
    while 1:
        try:
            return_json = ts.get_quote_endpoint(ticker)
            break
        except (pd.io.sql.DatabaseError,KeyError):
            print('ERROR collecting quote for %s' %ticker)

    if len(return_json)>0:
        return_json = pd.DataFrame(return_json[0],index=[1])
        try:
            return_json.columns=['ticker','open','high','low','price','volume','trading_day','previous_close','change','change_percent']
            for i in ['open','high','low','price','volume','previous_close','change']:
                return_json[i] = pd.to_numeric(return_json[i],errors='coerce')
        except (ValueError,KeyError):
            print('Error processing %s' %ticker)
    return return_json

#Get quotes
def getQuotes(api, ticker, start=None, end=None, limit=500):
    """ getQuotes - Request data from alpaca

         Parameters:
         api - alpaca API
         ticker - str
              Stock ticker name
         timeframe - TimeFrame object
              TimeFrame.Day, TimeFrame.Minute, TimeFrame.Second
         start - Date time object 
              Start date of request
         end - Date time object 
              End date of request
    """
    if start==None:
        import pytz
        est = pytz.timezone('US/Eastern')
        today = datetime.datetime.now(tz=est) + datetime.timedelta(minutes=-15)
        end = today.strftime("%Y-%m-%dT%H:%M:%S-04:00")
        start = (today + datetime.timedelta(minutes=-30)).strftime("%Y-%m-%dT%H:%M:%S-04:00")
    #ask_price,bid_price?
    quotes = api.get_quotes(ticker, start, end, limit=limit).df
    if len(quotes)>0:
        quotes.index = pd.to_datetime(quotes.index,utc=True).tz_convert(NY)
    return quotes
# get various types
#   api.get_bars
#   api.get_quotes
#   api.get_trades
def runTickerTypes(api, ticker, timeframe=TimeFrame.Day, start=None, end=None, limit=None, dataType='bars'):
    """ runTickerTypes - Request data from alpaca for bars or other potential objects

         Parameters:
         api - alpaca API
         ticker - str
              Stock ticker name
         timeframe - TimeFrame object
              TimeFrame.Day, TimeFrame.Minute, TimeFrame.Second
         start - Date time object 
              Start date of request
         end - Date time object 
              End date of request
         limit - int
              Number of entries requested. 50k is the current max
         dataType - str - data request type
              bars 
    """
    today=datetime.datetime.now()
    trade_days=None
    if timeframe==TimeFrame.Day and start==None and end==None:
        yesterday = today + datetime.timedelta(days=-1)
        d1 = yesterday.strftime("%Y-%m-%d")
        fouryao = (today + datetime.timedelta(days=-364*4.5)).strftime("%Y-%m-%d")
        trade_days = api(ticker, timeframe=timeframe,
                        start=fouryao, end=d1,  limit=limit).df #adjustment='raw',
            
    elif start!=None and end!=None:
        start_date = ''
        if dataType=='bars':
            trade_days = api(ticker, timeframe=timeframe,
                            start=start, end=end, adjustment='raw', limit=limit).df 
        else:
            #print(ticker)
            trade_days = api(ticker, start=start, end=end, limit=limit).df             
    return trade_days
def AddSMA(stock):
    stock['sma10']=techindicators.sma(stock['adj_close'],10)
    stock['sma20']=techindicators.sma(stock['adj_close'],20)
    stock['sma20cen']=techindicators.sma(stock['adj_close'].shift(-10),20)
    if len(stock['adj_close'])>50:
        stock['sma50']=techindicators.sma(stock['adj_close'],50)
    else: stock['sma50']=np.zeros(len(stock['adj_close']))
    if len(stock['adj_close'])>100:
        stock['sma100']=techindicators.sma(stock['adj_close'],100)
    else: stock['sma100']=np.zeros(len(stock['adj_close']))        
    if len(stock['adj_close'])>200:
        stock['sma200']=techindicators.sma(stock['adj_close'],200)
    else: stock['sma200']=np.zeros(len(stock['adj_close']))
    return stock

# add stock data and market data to compute metrics
def AddInfo(stock,market,debug=False, AddSupport=False):
    """ AddInfo - Add data to the stock pandas data frame

         Parameters:
         stock - pandas dataframe for the stock
         market - market or comparison pandas dataframe
              Stock ticker name
         debug - Bool
              Level of printout
    """
    import talib
    # let's make sure we sort this correctly
    #stock = stock.sort_index()
    #print(stock.tail())
    # Label Volume as positive or negative
    stock['pos_volume'] = 0
    #stock.loc[stock.open>=stock.close,'pos_volume'] = stock.volume
    #stock.loc[stock.open<stock.close,'neg_volume'] = stock.volume
    stock.loc[stock.adj_close>=stock.adj_close.shift(1),'pos_volume'] = stock.volume[stock.adj_close>=stock.adj_close.shift(1)]
    stock.loc[stock.adj_close<stock.adj_close.shift(1),'neg_volume'] = stock.volume[stock.adj_close<stock.adj_close.shift(1)]
    # SMA
    stock['sma10']=techindicators.sma(stock['adj_close'],10)
    stock['sma20']=techindicators.sma(stock['adj_close'],20)
    stock['sma20cen']=techindicators.sma(stock['adj_close'].shift(-10),20)    
    if len(stock['adj_close'])>50:
        stock['sma50']=techindicators.sma(stock['adj_close'],50)
    else: stock['sma50']=np.zeros(len(stock['adj_close']))
    if len(stock['adj_close'])>100:
        stock['sma100']=techindicators.sma(stock['adj_close'],100)
    else: stock['sma100']=np.zeros(len(stock['adj_close']))        
    if len(stock['adj_close'])>200:
        stock['sma200']=techindicators.sma(stock['adj_close'],200)
    else: stock['sma200']=np.zeros(len(stock['adj_close']))

    # EMA
    stock['ema13']=techindicators.ema(stock['adj_close'],13,True)
    stock['bullPower']=stock['high'] - stock['ema13']
    stock['bearPower']=stock['low'] - stock['ema13']
    stock['rstd10']=techindicators.rstd(stock['adj_close'],10)
    stock['rsi10']=techindicators.rsi(stock['adj_close'],10)
    stock['cmf']=techindicators.cmf(stock['high'],stock['low'],stock['close'],stock['volume'],10)
    stock['BolLower'],stock['BolCenter'],stock['BolUpper']=techindicators.boll(stock['adj_close'],14,2.0,14)
    start = time.time()
    stock['KeltLower'],stock['KeltCenter'],stock['KeltUpper']=techindicators.kelt(stock['high'],stock['low'],stock['close'],20,2.0,20)
    stock['copp']=techindicators.copp(stock['close'],14,11,10)
    stock['daily_return']=stock['adj_close'].pct_change(periods=1)
    
    # add various future returns
    stock['fiveday_future_return']=stock['adj_close'].shift(-5).pct_change(periods=5)
    stock['oneday_future_return']=stock['adj_close'].shift(-1).pct_change(periods=1)
    stock['twoday_future_return']=stock['adj_close'].shift(-2).pct_change(periods=2)
    stock['thrday_future_return']=stock['adj_close'].shift(-5).pct_change(periods=3)
    stock['fiveday_prior_vix']=stock['adj_close'].rolling(5).std()
    stock['oneday_prior_vix']=stock['adj_close'].rolling(1).std()
    stock['twoday_prior_vix']=stock['adj_close'].rolling(2).std()
    stock['thrday_prior_vix']=stock['adj_close'].rolling(3).std()
    #print(stock[['adj_close','oneday_future_return','twoday_future_return']])
    
    stock['daily_return_stddev14']=techindicators.rstd(stock['daily_return'],14)
    #try:
    stock['beta']=techindicators.rollingBetav2(stock,14,market)
    #except (ValueError,KeyError,NotImplementedError) as e:
    #    print("Testing multiple exceptions. {}".format(e.args[-1]))
    #    print('Error getting info for %s' %ticker)
    #    return []
    
    stock['alpha']=techindicators.rollingAlpha(stock,14,market)
    stock['rsquare']=techindicators.rollingRsquare(stock,14,market)
    start = time.time()
    stock['mfi']=techindicators.mfi(stock.high,stock.low,stock.close,stock.volume,14) # money flow index
    end = time.time() 
    if debug: print('Process time to mfi: %s' %(end - start))
    start = time.time()
    stock['mfi_bill']=techindicators.mfi_bill(stock.high,stock.low,stock.volume)
    stock['mfi_bill_ana']=techindicators.mfi_bill_ana(stock.high,stock.low,stock.volume)
    end = time.time() 
    if debug: print('Process time to mfi bill: %s' %(end - start))
    start = time.time()    
    stock['sharpe']=techindicators.sharpe(stock['daily_return'],30) # generally above 1 is good
    end = time.time() 
    if debug: print('Process time to sharpe: %s' %(end - start))    
    start = time.time()
    stock['cci']=techindicators.cci(stock['high'],stock['low'],stock['close'],20) 
    stock['jaws'],stock['teeth'],stock['lips']=techindicators.alligator(stock['adj_close'],5,8,13)
    stock['stochK'],stock['stochD']=techindicators.stoch(stock['high'],stock['low'],stock['close'],14,3,3)    
    stock['obv']=techindicators.obv(stock['adj_close'],stock['volume'])
    stock['force']=techindicators.force(stock['adj_close'],stock['volume'],13)
    stock['macd'],stock['macdsignal']=techindicators.macd(stock['adj_close'],12,26,9)
    stock['bop']=techindicators.bop(stock['high'],stock['low'],stock['close'],stock['open'],14)
    #stock['pdmd'],stock['ndmd'],stock['adx']=techindicators.adx(stock['high'],stock['low'],stock['close'],14)
    end = time.time() 
    if debug: print('Process time to bop etc: %s' %(end - start))
    start = time.time()
    stock['HT_DCPERIOD']=talib.HT_DCPERIOD(stock['adj_close']) 
    stock['HT_DCPHASE']=talib.HT_DCPHASE(stock['adj_close']) 
    stock['HT_TRENDMODE']=talib.HT_TRENDMODE(stock['adj_close']) 
    stock['HT_SINE'],stock['HT_SINElead']=talib.HT_SINE(stock['adj_close'])
    stock['HT_PHASORphase'],stock['HT_PHASORquad']=talib.HT_PHASOR(stock['adj_close'])     
    stock['adx']=talib.ADX(stock['high'],stock['low'],stock['close'],14) 
    stock['willr']=talib.WILLR(stock['high'],stock['low'],stock['close'],14) 
    stock['ultosc']=talib.ULTOSC(stock['high'],stock['low'],stock['close'],timeperiod1=7, timeperiod2=14, timeperiod3=28) 
    stock['adx']=talib.ADX(stock['high'],stock['low'],stock['close'],14)
    stock['SAR'] = talib.SAR(stock.high, stock.low, acceleration=0.02, maximum=0.2)    
    end = time.time()
    if debug: print('Process time to talib: %s' %(end - start))
    start = time.time()
    stock['aroonUp'],stock['aroonDown'],stock['aroon']=techindicators.aroon(stock['high'],stock['low'],25)
    end = time.time()
    if debug: print('Process time to aroon: %s' %(end - start))
    start = time.time()
    stock['senkou_spna_A'],stock['senkou_spna_B'],stock['chikou_span']=techindicators.IchimokuCloud(stock['high'],stock['low'],stock['adj_close'],9,26,52)    
    stock['vwap14']=techindicators.vwap(stock['high'],stock['low'],stock['close'],stock['volume'],14)
    stock['vwap10']=techindicators.vwap(stock['high'],stock['low'],stock['close'],stock['volume'],10)
    # centering on the date in question
    stock['vwap10cen']=techindicators.vwap(stock['high'].shift(-5),stock['low'].shift(-5),stock['close'].shift(-5),stock['volume'].shift(-5),10)
    stock['vwap10diff'] = (stock['adj_close'] - stock['vwap10'])/stock['adj_close']    
    stock['vwap20']=techindicators.vwap(stock['high'],stock['low'],stock['close'],stock['volume'],20)
    
    stock['BolLowerVWAP10'],stock['BolCenterVWAP10'],stock['BolUpperVWAP10']=techindicators.boll(stock['vwap10'],14,2.0,14)
    
    stock['chosc']=techindicators.chosc(stock['high'],stock['low'],stock['close'],stock['volume'],3,10)
    stock['market'] = market['adj_close']
    stock['corr14']=stock['adj_close'].rolling(14).corr(market['market'])
    
    stock['weekly_return']=stock['adj_close'].pct_change(freq='W')
    stock['monthly_return']=stock['adj_close'].pct_change(freq='M')
    stock_1y = GetTimeSlot(stock)
    if len(stock_1y['adj_close'])<1:
        print('Ticker has no adjusted close info.')
        stock['yearly_return']=stock['adj_close']
    else:
        stock['yearly_return']=stock['adj_close']/stock_1y['adj_close'][0]-1
    end = time.time()
    if debug: print('Process time to other: %s' %(end - start))        
    #dfnew = pd.DataFrame(talib.CDLABANDONEDBABY(stock['open'],stock['high'],stock['low'],stock['close'], penetration=0),columns=['CDLABANDONEDBABY'])
    #stock = pd.concat([stock,dfnew],axis=1)
    #stock.update(dfnew)
    #print(stock)
    #stock['CDLABANDONEDBABY']=talib.CDLABANDONEDBABY(stock['open'],stock['high'],stock['low'],stock['close'], penetration=0)
    start = time.time()    
    if len(stock)>2:
        indicators = []
        for ky in talib.__dict__.keys():
            if 'CDL' in ky and not 'stream' in ky:
                #stock[ky]=talib.__dict__[ky](stock['open'],stock['high'],stock['low'],stock['close'])
                indicators+=[pd.DataFrame(talib.__dict__[ky](stock['open'],stock['high'],stock['low'],stock['close']),columns=[ky])]
                #stock.update(pd.DataFrame(talib.__dict__[ky](stock['open'],stock['high'],stock['low'],stock['close']),columns=[ky]))
        stock=pd.concat([stock]+indicators,axis=1)
    end = time.time()
    if debug: print('Process time to talib: %s' %(end - start))
    start = time.time()
    if AddSupport and  len(stock_1y['adj_close'])>0:
        # compute the last years support levels
        stock['downSL']=0
        stock['upSL']=0
        for i in [stock_1y.index.values[-1]]:
            earn_dateA = (i - np.datetime64('1970-01-01T00:00:00Z')) / np.timedelta64(1, 's')
            earn_dateA=datetime.datetime.utcfromtimestamp(earn_dateA)
            prior_year_tstock_info = GetTimeSlot(stock,startDate=earn_dateA)
            tech_levels = techindicators.supportLevels(prior_year_tstock_info,drawhlines=False)
            adj_close=1.0
            if  len(prior_year_tstock_info)>0:
                adj_close = prior_year_tstock_info.adj_close.values[-1]
            a = np.array(tech_levels,dtype=float)/adj_close-1.0
            stock.loc[stock.index==i,['downSL']] = np.max(a[a<0.0],initial=-0.25)
            stock.loc[stock.index==i,['upSL']] = np.min(a[a>0.0],initial=0.25)
    end = time.time()    
    if debug: print('Process time to support lines: %s' %(end - start))
    #print(stock)
    #print(stock.columns)
    return stock
# collect the upcoming earnings info
# fd in the fundamentals data api
# ReDownload: newly downloads the file when True.
def GetUpcomingEarnings(fd,ReDownload):
    """ GetUpcomingEarnings - collect the upcoming earnings info

         Parameters:
         fd - Alpha vantage Fundamental data
         ReDownload - Bool
              When true, downloads a new version. False uses the old version
    """
    if os.path.exists('stockEarnings.csv') and not ReDownload:
        my_3month_calendar = pd.read_csv('stockEarnings.csv')
    else:
        import csv
        CSV_URL = 'https://www.alphavantage.co/query?function=EARNINGS_CALENDAR&horizon=3month&apikey=demo'
        with requests.Session() as s:
            download = s.get(CSV_URL)
            decoded_content = download.content.decode('utf-8')
            cr = csv.reader(decoded_content.splitlines(), delimiter=',')
            filename='stockEarnings.csv'
            with open(filename, 'w') as csvfile: 
                # creating a csv writer object 
                csvwriter = csv.writer(csvfile)
                csvwriter.writerows(cr)
        my_3month_calendar = pd.read_csv('stockEarnings.csv')
        #my_3month_calendar = fd.get_earnings_calendar('3month')
        #if len(my_3month_calendar)>0:
        #    my_3month_calendar = my_3month_calendar[0]
        #    my_3month_calendar.to_csv('stockEarnings.csv')
    
    # clean up
    my_3month_calendar['reportDate']=pd.to_datetime(my_3month_calendar['reportDate'])
    my_3month_calendar['fiscalDateEnding']=pd.to_datetime(my_3month_calendar['fiscalDateEnding'])
    my_3month_calendar['estimate']=pd.to_numeric(my_3month_calendar['estimate'])
    my_3month_calendar=my_3month_calendar.set_index('reportDate')
    my_3month_calendar=my_3month_calendar.sort_index()
    return my_3month_calendar

def GetCompanyEarningsInfo(ticker, fd, connectionCal, debug=False):
    """ GetCompanyEarningsInfo - collect the upcoming earnings info

         Parameters:
         ticker - str
              Ticker stock symbol
         fd - Alpha vantage Fundamental data
         debug - Bool
              determines printout
    """
    try:
        pastEarnings = fd.get_company_earnings(ticker)
    except:
        print('Could not collect earnings for: %s' %ticker)
        return []
    quarterlyEarnings=[]
    # Loading the previous earnings!
    try:
        pastEarnings[0]
        if debug: print(pastEarnings[0].keys())
    except:
        print('pastEarnings are empty for %s' %ticker)
        return []
    if len(pastEarnings)>0 and 'annualEarnings' in pastEarnings[0]:
        annualEarnings = pd.DataFrame(pastEarnings[0]['annualEarnings'])
        try:
            annualEarnings.set_index('fiscalDateEnding')
        except (KeyError) as e:
            print("Testing multiple exceptions. {}".format(e.args[-1]))
            print('skipping missing fiscaleDate for %s' %ticker)
            return []
        if debug: print(annualEarnings.dtypes)
        # cleaning up data
        annualEarnings['ticker'] = np.array([ticker for _ in range(0,len(annualEarnings))])
        annualEarnings['fiscalDateEnding']=pd.to_datetime(annualEarnings['fiscalDateEnding'])
        for sch in ['reportedEPS']:
            if sch in annualEarnings:
                annualEarnings[sch]=pd.to_numeric(annualEarnings[sch],errors='coerce')
        totalDF = ConfigTableFromPandas('annualEarnings',ticker,connectionCal,annualEarnings,index_label='fiscalDateEnding')
        if debug:
            print(annualEarnings)
            print(totalDF)
    if len(pastEarnings)>0 and ('quarterlyEarnings' in pastEarnings[0]):
        quarterlyEarnings = pd.DataFrame(pastEarnings[0]['quarterlyEarnings'])
        # cleaning data
        if ('reportedDate' not in quarterlyEarnings.columns):
            return []
        quarterlyEarnings['ticker'] = np.array([ticker for _ in range(0,len(quarterlyEarnings))])
        quarterlyEarnings.set_index('reportedDate')
        quarterlyEarnings['reportedDate']=pd.to_datetime(quarterlyEarnings['reportedDate'])
        quarterlyEarnings['fiscalDateEnding']=pd.to_datetime(quarterlyEarnings['fiscalDateEnding'])
        for sch in ['surprise','reportedEPS','estimatedEPS','surprisePercentage']:
            if sch in quarterlyEarnings:
                quarterlyEarnings[sch]=pd.to_numeric(quarterlyEarnings[sch],errors='coerce')
        if debug:
            print(quarterlyEarnings)
            print(quarterlyEarnings.dtypes)
        qEDF = ConfigTableFromPandas('quarterlyEarnings',ticker,connectionCal,quarterlyEarnings,index_label='reportedDate')
        if debug: print(qEDF)
    return quarterlyEarnings

# Compute the support levels so that they are entries to the machine learning
def ApplySupportLevel(ex):
    """ ApplySupportLevel - returns an array of stock earnings

         Parameters:
         ex - pandas dataframe of stoack earnings
    """
    if ex['tech_levels']=='':
        return 0
    a = np.array(ex['tech_levels'].split(','),dtype=float)/ex.adj_close_daybefore-1.0
    return [np.min(a[a>0.0],initial=0.25),np.max(a[a<0.0],initial=-0.25)]

# preprocess to add the info for running the earnings NN
# input is a dataframe with daily info
# addRangeOpens returns only the most recent day and price variations
def EarningsPreprocessing(ticker, sqlcursor, ts, spy, connectionCal, j=0, ReDownload=False, debug=False, addRangeOpens=True):
    """ EarningsPreprocessing - returns an array of stock data along with added indicators. Protects against crashes
    """
    if debug:
        print(spy)
        print(ticker)
    tstock_info,j=ConfigTable(ticker, sqlcursor, ts, 'full', j, hoursdelay=23)
    
    if len(tstock_info)==0:
        return []
    try:
        if ticker=='SPY':
            tstock_info = AddInfo(tstock_info,tstock_info,debug=debug)
        else:
            tstock_info = AddInfo(tstock_info,spy,debug=debug)
    except (ValueError,KeyError) as e:
        print("Testing multiple exceptions. {}".format(e.args[-1]))
        print('Error getting info for %s' %ticker)
        return []

    # read in the earnings info
    fd = ALPHA_FundamentalData()
    my_3month_calendar = GetUpcomingEarnings(fd,ReDownload)
    estimateEPS=0.0
    try:
        estimateEPS = my_3month_calendar[my_3month_calendar['symbol']==ticker]['estimate'].dropna().values[-1]
    except (ValueError,KeyError,IndexError) as e:
        #print("Testing multiple exceptions. {}".format(e.args[-1]))
        pass
    if estimateEPS==0:
        prev_earnings = None
        overview = None
        try:
            overview = pd.read_sql('SELECT * FROM overview WHERE Symbol="%s"' %(ticker), connectionCal)
            prev_earnings = pd.read_sql('SELECT * FROM quarterlyEarnings WHERE ticker="%s"' %(ticker), connectionCal)
            estimateEPS = prev_earnings[prev_earnings['ticker']==ticker]['estimatedEPS'].dropna().values[-1]
        except:
            print('no previous info earnings info for %s' %ticker)

        # last try at getting the earnings
        if estimateEPS==0:
            try:
                quarterlyEarnings = GetCompanyEarningsInfo(ticker, fd, connectionCal, debug=debug)
                if len(quarterlyEarnings)>0:
                    estimateEPS = prev_earnings[prev_earnings['ticker']==ticker]['estimatedEPS'].dropna().values[-1]
            except:
                pass

    extrainfo = []
    for a in ['open', 'high', 'low', 'close', 'adj_close', 'volume', 'dividendamt', 'splitcoef', 'pos_volume', 'neg_volume', 'sma10', 'sma20', 'sma50', 'sma100', 'sma200', 'rstd10', 'rsi10', 'cmf', 'BolLower', 'BolCenter', 'BolUpper', 'KeltLower', 'KeltCenter', 'KeltUpper', 'copp','daily_return_stddev14', 'beta', 'alpha', 'rsquare', 'sharpe', 'cci', 'stochK', 'stochD', 'obv', 'force', 'macd', 'macdsignal', 'bop', 'HT_DCPERIOD', 'HT_DCPHASE', 'HT_TRENDMODE', 'HT_SINE', 'HT_SINElead', 'HT_PHASORphase', 'HT_PHASORquad', 'adx', 'willr', 'ultosc', 'aroonUp', 'aroonDown', 'aroon', 'senkou_spna_A', 'senkou_spna_B', 'chikou_span', 'SAR', 'vwap14', 'vwap10', 'vwap20', 'chosc', 'market', 'corr14']:
        #tstock_info[a+'_daybefore'] = tstock_info[a].shift(1)
        extrainfo+=[pd.DataFrame(tstock_info[a].shift(1),columns=[a+'_daybefore'])]
        
    # compute the last years support levels
    tstock_info['downSL']=0
    tstock_info['upSL']=0
    #extrainfo+=[pd.DataFrame(np.zeros(len(tstock_info)),columns=['downSL'])]
    prior_year_tstock_infoR = GetTimeSlot(tstock_info,800,startDate=None)
    #prior_year_tstock_infoR.index = pd.to_datetime(prior_year_tstock_infoR.index)
    for i in prior_year_tstock_infoR.index.values:
        earn_dateA = (i - np.datetime64('1970-01-01T00:00:00Z')) / np.timedelta64(1, 's')
        earn_dateA=datetime.datetime.utcfromtimestamp(earn_dateA)
        prior_year_tstock_info = GetTimeSlot(tstock_info,startDate=earn_dateA)
        tech_levels = techindicators.supportLevels(prior_year_tstock_info,drawhlines=False)
        adj_close=1.0
        if  len(prior_year_tstock_info)>0:
            adj_close = prior_year_tstock_info.adj_close.values[-1]
        a = np.array(tech_levels,dtype=float)/adj_close-1.0
        tstock_info.loc[tstock_info.index==i,['downSL']] = np.max(a[a<0.0],initial=-0.25)
        tstock_info.loc[tstock_info.index==i,['upSL']] = np.min(a[a>0.0],initial=0.25)
    #extrainfo+=[pd.DataFrame(estimateEPS,columns=['estimatedEPS'])]
    tstock_info['estimatedEPS']=estimateEPS
    # If true, then we drop all of the older earnings and add positive and negative variations of the adj_close. I think this can be iterpreted as what a buy in would be.
    if addRangeOpens:
        tstock_info = tstock_info[-1:]
        #print(tstock_info)
        tstock_info['Date'] = tstock_info.index
        tstock_info.set_index([pd.Index([0])],inplace=True)
        new_tstock_info = tstock_info[-1:]
        for i in range(-10,11):
            if i==0: continue
            new_tstock_info.set_index([pd.Index([i])],inplace=True)
            new_adj_close = float(100+i)/100.0*adj_close
            new_tstock_info.loc[new_tstock_info.index==i,'adj_close'] = new_adj_close
            a = np.array(tech_levels,dtype=float)/new_adj_close-1.0
            new_tstock_info.loc[new_tstock_info.index==i,'downSL'] = np.max(a[a<0.0],initial=-0.25)
            new_tstock_info.loc[new_tstock_info.index==i,'upSL']= np.min(a[a>0.0],initial=0.25)
            tstock_info = tstock_info.append(new_tstock_info)

        if debug: print(tstock_info)
    
    # add some extra info
    for c in ['sma50','sma20','sma200']:
        #tstock_info[c+'r']=tstock_info.adj_close/tstock_info[c]
        extrainfo+=[pd.DataFrame(tstock_info.adj_close/tstock_info[c],columns=[c+'r'])]
    for c in ['fiveday_prior_vix','thrday_prior_vix','twoday_prior_vix','SAR','estimatedEPS']:
        #tstock_info[c+'r']=tstock_info[c]/tstock_info.adj_close
        extrainfo+=[pd.DataFrame(tstock_info[c]/tstock_info.adj_close,columns=[c+'r'])]
    tstock_info = pd.concat([tstock_info]+extrainfo,axis=1)
    return tstock_info

#
# collect midair refuel
def GetMidAirRefuel(data):
    try:
        return data[((data['close']-data['open'])<0) & ((data['close'].shift(1)-data['open'].shift(1))>0) & ((data['close'].shift(2)-data['open'].shift(2))>0) & ((data['close'].shift(3)-data['open'].shift(3))<0) & (data['low']<data['low'].shift(1)) & (data['low']<data['low'].shift(2)) & (data['high']>data['high'].shift(1)) & (data['high']>data['high'].shift(2)) & (data['low'].shift(3)<data['low'].shift(1)) & (data['low'].shift(3)<data['low'].shift(2)) & (data['high'].shift(3)>data['high'].shift(1)) & (data['high'].shift(3)>data['high'].shift(2))]
    except:
        return False
# fills data with info & adds NN info
# ticker = ticker
# ts = time series from alpha
# connectionCal = SQL_CURSOR('earningsCalendar.db')
# sqlcursor = SQL_CURSOR()
# 
def GetNNSelection(ticker, ts, connectionCal, sqlcursor, spy, debug=False,j=0,
                       addRangeOpens=True,
                       training_dir='models/',
                       training_name='stockEarningsModelTestv2noEPS',
                       draw=False):
    """ GetNNSelection - draws an ML decision and adds the info to the stock dataframe
    
        Parameters:
         ticker - str
              Stock ticker name
         training_dir - str
              model input directory
         training_name - str
              NN model name
         draw - bool
              decide to draw the ML distribution
    """
    
    stock_info = EarningsPreprocessing(ticker, sqlcursor, ts, spy, connectionCal,j=j, ReDownload=False, debug=debug, addRangeOpens=addRangeOpens)
    if debug: print(stock_info)
    if len(stock_info)==0:
        return [],j
    COLS  = ['sma50r','sma20r','sma200r','copp','daily_return_stddev14',
    'beta','alpha','rsquare','sharpe','cci','cmf',
    'bop','SAR','adx','rsi10','ultosc','aroonUp','aroonDown',
    'stochK','stochD','willr',
    #'estimatedEPSr',
    'upSL','downSL','corr14',]
    
    model_filename = training_dir+'model'+training_name+'.hf'
    scaler_filename = training_dir+"scaler"+training_name+".save"
    scaler = pickle.load(open(scaler_filename, 'rb'))
    model = load_model(model_filename)
    
    X_test = stock_info[COLS] # use only COLS
    vector_y_pred = model.predict(X_test)
    stock_info['pred'] = np.argmax(vector_y_pred, axis = 1) + np.amax(vector_y_pred, axis = 1)
    if draw:
        matplotlib.use('Agg')
        stock_1y = GetTimeSlot(stock_info,800)
        plt.clf()
        fig, ax1 = plt.subplots()
        ax1.plot(stock_1y.index,stock_1y['pred'])
        ax1.set_ylabel('NN score for %s' %ticker)        
        ax2 = ax1.twinx()  
        ax2.plot(stock_1y.index,stock_1y['adj_close'],color='red')
        #ax2.plot(stock_1y.index,stock_1y['daily_return'],color='red')
        ax2.tick_params(axis='y', labelcolor='red')
        ax2.set_ylabel('Adjusted Closing Price', color='red')
        plt.gcf().autofmt_xdate()
        plt.ylabel('NN')
        plt.xlabel('date')
        plt.title('NN', fontsize=30)
        plt.savefig(baseB.outdir+'%s%s.png' %('NNscore',ticker))
    if debug: print(stock_info[['adj_close','open','pred','sma50r','sma20r','sma200r','downSL','upSL']])
    return stock_info,j

def MakePlotMulti(xaxis, yaxis=[], colors=[], labels=[], dash=[], xname='Date',yname='Beta',saveName='', hlines=[],title='',doSupport=False,my_stock_info=None,draw=False,doPDFs=False,outdir='/tmp/',doIterX=False,spy=[]):
    """ Generic plotting option for multiple plots 
         
         Parameters:
         xaxis : numpy array
            Date of stock value
         yaxis : numpy array
            Closing stock value
         xname : str
            x-axis name
         colors : array of strings
            colors compatible with matplotlib
         labels : array of str
            legend names
         yname : str
            y-axis name
         saveName : str
            Saved file name
         hlines : array of horizontal lines drawn in matplotlib
         title : str
            Title of plot    
         doSupport : bool
            Request generation of support lines on the fly
         my_stock_info : pandas data frame of stock timing and adj_close
         draw : bool - draw and wait at each figure
         doPDFs : bool - save as a PDF
         outdir : str - path to save file
         doIterX : bool - iterate over the x axis because they are not the same 
         spy : dataframe - dataframe with adj_close to overlay the prices
    """
    # plotting
    j=0
    plt.clf()
    #if len(xaxis)==0:
    fig,ax1 = plt.subplots()
    for y in yaxis:
        if len(xaxis)==0:
            if len(dash)>0:
                plt.plot(y.index,y,color=colors[j],label=labels[j],linestyle=dash[j])
            else:
                plt.plot(y.index,y,color=colors[j],label=labels[j])
        else:
            if doIterX:
                plt.plot(xaxis[j],y,color=colors[j],label=labels[j])
            else:
                plt.plot(xaxis,y,color=colors[j],label=labels[j])
        j+=1

    plt.gcf().autofmt_xdate()
    plt.ylabel(yname)
    plt.xlabel(xname)

    if title!="":
        plt.title(title, fontsize=30)
    for h in hlines:
        plt.axhline(y=h[0],color=h[1],linestyle=h[2]) #xmin=h[1], xmax=h[2],
    plt.legend(loc="upper left")

    if len(spy)>0:
        ax2 = ax1.twinx()
        ax2.set_ylabel('SPY',color='blue')
        ax2.plot(spy.index,spy.adj_close, color='blue',linewidth=4)
        ax2.tick_params(axis ='y', labelcolor = 'blue')
    
    if doSupport:
        techindicators.supportLevels(my_stock_info)
    if draw: plt.show()
    if doPDFs: plt.savefig(outdir+'%s.pdf' %(saveName))
    plt.savefig(outdir+'%s.png' %(saveName))
    if not draw: plt.close()

def MakePlot(xaxis, yaxis, xname='Date',yname='Beta',saveName='', hlines=[],title='',doSupport=False,my_stock_info=None, doScatter=False,doBox=False,doPDFs=False,draw=False,outdir='/tmp/'):
    """ Generic plotting with option to show support lines
         
         Parameters:
         xaxis : numpy array
            Date of stock value
         yaxis : numpy array
            Closing stock value
         xname : str
            x-axis name
         yname : str
            y-axis name
         saveName : str
            Saved file name
         hlines : array of horizontal lines drawn in matplotlib
         title : str
            Title of plot
         doSupport : bool
            Request generation of support lines on the fly
         my_stock_info : pandas data frame of stock timing and adj_close
         doScatter : bool - draw a scatter plot
         doBox : bool - draw a box plot for unique x-values
         draw : bool - draw and wait at each figure
         doPDFs : bool - save as a PDF
         outdir : str - path to save file
     """
    # plotting
    plt.clf()
    ax7=None
    fig7=None
    if doScatter:
        plt.scatter(xaxis,yaxis)
    elif doBox: 
        fig7, ax7 = plt.subplots()
        d1=[]
        for m in np.unique(xaxis.values):
            d1+=[yaxis.loc[xaxis==m].dropna()]
        bp = ax7.boxplot(d1,whis=[5,95],showmeans=True,notch=True)
        ax7.grid(True)
        ax7.legend([bp['medians'][0], bp['means'][0]],['median','mean'],loc="upper left")
        plt.title(saveName.replace('_',' '))
    else:
        plt.plot(xaxis,yaxis)
    plt.gcf().autofmt_xdate()
    plt.ylabel(yname)
    plt.xlabel(xname)
    if title!="":
        plt.title(title, fontsize=30)
    for h in hlines:
        plt.axhline(y=h[0],color=h[1],linestyle=h[2]) #xmin=h[1], xmax=h[2],
    if doSupport:
        techindicators.supportLevels(my_stock_info)
    if draw and ax7!=None: fig7.show()
    elif draw: plt.show()
    if doPDFs and ax7!=None: fig7.savefig(outdir+'%s.pdf' %(saveName))
    elif doPDFs: plt.savefig(outdir+'%s.pdf' %(saveName))
    if ax7!=None: fig7.savefig(outdir+'%s.png' %(saveName))
    else: plt.savefig(outdir+'%s.png' %(saveName))
    if not draw: plt.close()
    plt.close()

def POS_MARKET_PLOTS(outdir='/tmp/',debug=False,doPDFs=False,draw=False, spy=[]):
    """ Reads global market indicators read in from an sql database for percentage of stocks over a given MA
         outdir - string - of the directory to same
         debug - bool - print extra info to see if something is broken
         doPDFs - bool - save the PDFs
         draw - bool - draw and wait at each figure
         """
    sqlcursor = SQL_CURSOR(db_name='stocksPerfHistory.db')
    sc= sqlcursor.cursor()
    table_names = sc.execute("SELECT name from sqlite_master WHERE type ='table' AND name NOT LIKE 'sqlite_%';").fetchall()
    table_names_str=[]
    for tname in table_names: table_names_str+=[tname[0]]
    stockList200=[]
    stockList50=[]
    exchanges = ['SPY','NYSE','SPYonehun','NASDAQonehun','R1k','R2k','R3k']
    for exchange in exchanges:
        stockList=[]
        for MA in ['20MA','50MA','100MA','200MA']:
            tableName=exchange+MA
            if tableName not in table_names_str:
                print('Missing expected table: %s' %tableName)
                continue
            # Reading the SQL database
            stock = pd.read_sql('SELECT * FROM %s' %tableName, sqlcursor) #,index_col='Date')
            stock['Date']=pd.to_datetime(stock.Date.astype(str), format='%Y-%m-%d')
            stock['Date']=pd.to_datetime(stock['Date'])
            stock = stock.set_index('Date')
            stock = stock.sort_index()
            stockList+=[stock]
            if MA=="200MA":
                stockList200+=[stock]
            if MA=="50MA":
                stockList50+=[stock]
            
        # interesting values Low,Previous_Close,High,Last
        if len(stockList)>0:
            plotYs = []
            for s in stockList:
                plotYs+=[s['Last']]
            MakePlotMulti(stockList[0].index, yaxis=plotYs, colors=['black','green','red','cyan'], labels=['20MA','50MA','100MA','200MA'], xname='Date',yname='Percent of stocks in %s above MA' %exchange,saveName='POSITION_exchange_'+exchange, hlines=[],title=exchange,doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
        # Now compare with the same MA but different exchanges
        if len(stockList200)>0:
            plotXs=[]
            plotYs = []
            for s in stockList200:
                plotXs+=[s.index]                
                plotYs+=[s['Last']]            
            MakePlotMulti(plotXs, yaxis=plotYs, colors=['black','green','red','cyan','yellow','blue','magenta'], labels=exchanges, xname='Date',yname='Percent of stocks above 200DMA',saveName='POSITION_exchange_200MA', hlines=[],title='Perc above 200DMA',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir,doIterX=True)
        if len(stockList50)>0:
            plotXs=[]
            plotYs = []
            for s in stockList50:
                plotXs+=[s.index]
                plotYs+=[s['Last']]
            MakePlotMulti(plotXs, yaxis=plotYs, colors=['black','green','red','cyan','yellow','blue','magenta'], labels=exchanges, xname='Date',yname='Percent of stocks about 50DMA',saveName='POSITION_exchange_50MA', hlines=[],title='Perc above 50DMA',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir,doIterX=True)

    # read in the number of new lows and highs in different exchanges
    stock = pd.read_sql('SELECT * FROM summary', sqlcursor)
    stock['Date']=pd.to_datetime(stock.Date.astype(str), format='%Y-%m-%d')
    for exch in ['NYSE','NASDAQ','ETFs','PRICE_lt_$10','PRICE_gt_$10','NYSE_Arca','OVERALL','VOL_lt_100K','VOL_gt_100K','OTC-US']:

        if len(stock)==0 or 'Period' not in stock.columns:
            continue
        
        #if exch not in list(stock['Period'].unique()):
        #    print('error')
        #    continue
        
        plotXs=None
        plotYs=[]
        merge_spy=[]
        periods = ['3-Month Highs','3-Month Lows','6-Month Highs', '6-Month Lows','52-Week Highs', '52-Week Lows','5-Year Highs', '5-Year Lows']
        for per in periods:
            stock_per = stock[stock.Period==per]
            stock_per.set_index('Date',inplace=True)
            if len(spy)>0:
                merge_spy = stock_per.join(spy,on='Date',how='left')
            plotYs+=[stock_per[exch]]
        MakePlotMulti([], yaxis=plotYs, colors=['black','black','green','green','red','red','cyan','cyan','blue','yellow'], dash=['dashed','solid','dashed','solid','dashed','solid','dashed','solid'], labels=periods, xname='Date',yname='New Highs and Lows',saveName='POSITION_exchange_%s_Lows' %exch.replace('$','d'), hlines=[],title=exch,doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir,spy=merge_spy)
        
def GLOBAL_MARKET_PLOTS(outdir='/tmp/',j=0,debug=False):
    """ Reads global market indicators as json files and makes a simple plot of them
         outdir - string - of the directory to same
         debug - bool - print extra info to see if something is broken
         """
    
    ALPHA_ID = os.getenv('ALPHA_ID')

    list_of_fundamentals = ['REAL_GDP&interval=quarterly',
                                'REAL_GDP&interval=annual','REAL_GDP_PER_CAPITA',
                                'TREASURY_YIELD&interval=monthly&maturity=10year',
                                'TREASURY_YIELD&interval=monthly&maturity=3month',
                                'TREASURY_YIELD&interval=monthly&maturity=30year',
                            'CPI&interval=monthly','INFLATION','INFLATION_EXPECTATION',
                            'CONSUMER_SENTIMENT','RETAIL_SALES','DURABLES','UNEMPLOYMENT','NONFARM_PAYROLL']
    for f in list_of_fundamentals:
        if debug: print(f)
        url = 'https://www.alphavantage.co/query?function=%s&apikey=%s' %(f,ALPHA_ID) 
        r=None
        my_break = False
        while not my_break:
            j+=1
            if j%3==0:
                time.sleep(30)
            try:
                r = requests.get(url)
                my_break=True
            except (ValueError,urllib3.exceptions.ProtocolError,ConnectionResetError,urllib3.exceptions.ProtocolError,ConnectionResetError) as e:
                print("Testing multiple exceptions. {}".format(e.args[-1]))
                continue
        data = r.json()
        if debug: print(data)
        if 'data' in data and len(data['data']):
            my_data = pd.DataFrame(data['data'])
            my_data['value'] = pd.to_numeric(my_data['value'],errors='coerce')
            my_data['date'] = pd.to_datetime(my_data['date'].astype(str), format='%Y-%m-%d')
            fout_name_y = f.replace('&','_').replace('=','_')
            fout_name = f.replace('&','_').replace('=','_')+'_GLOBAL'
            MakePlot(my_data.date, my_data.value, xname='Date',yname='%s' %fout_name_y,saveName=fout_name,outdir=outdir)
        else:
            print('ERROR - %s' %url)

# Fit linear regression on close
# Return the t-statistic for a given parameter estimate.
def tValLinR(close,plot=False,extra_vars=[],debug=False):
    x = np.ones((close.shape[0],2)) # adding the constant
    x[:,1] = np.arange(close.shape[0])
    if len(extra_vars)>0:
        x = np.ones((close.shape[0],3)) # adding the constant
        x[:,1] = np.arange(close.shape[0])    
        x[:,2] = extra_vars.volume#np.arange(close.shape[0])    
    ols = sm1.OLS(close, x).fit()
    if debug: print(ols.summary())
    prstd, iv_l, iv_u = wls_prediction_std(ols)
    return ols.tvalues[1] #,today_value_predicted # grab the t-statistic for the slope

# collect the slow
def slope(p4,x=[1,2]):
    j = p4(x)
    return j[1]-j[0]

# add data for new fits
def AddData(t):
    """ AddData:
          t - dataframe of minute data for  stock
    """
    t['slope5']=0.0
    t['slope5'] = t.close.rolling(5).apply(tValLinR)
    t['slope8']=0.0
    t['slope8'] = t.close.rolling(8).apply(tValLinR)
    t['slope15']=0.0
    t['slope15'] = t.close.rolling(15).apply(tValLinR)
    t['slope30']=0.0
    t['slope30'] = t.close.rolling(30).apply(tValLinR)
    #t['slope60']=0.0
    #t['slope60'] = t.close.rolling(60).apply(tValLinR)
    #t['slope240']=0.0
    #t['slope240'] = t.close.rolling(240).apply(tValLinR)
    
    t['time']  = t.index
    t['i'] = range(0,len(t))
    #t['slope_volume'] = t.volume.rolling(8).apply(tValLinR) 
    t['signif_volume'] = (t.volume-t.volume.mean())/t.volume.std()
    t['volma20'] = t.volume.rolling(20).mean()
    t['volma10'] = t.volume.rolling(10).mean()
    t['ma50'] = t.close.rolling(50).mean()
    fivma = t['ma50'].mean()
    t['ma50_div'] = (t['ma50'] - fivma)/fivma
    t['ma50_div'] *=10.0
    t['minute_diff_now'] = (t['close']-t['open'])/t['open']
    t['minute_diff_minago'] = t['minute_diff_now'].shift(1)
    t['minute_diff_2minago'] = t['minute_diff_now'].shift(2)
    t['minute_diff_15minago'] = t['minute_diff_now'].shift(15)
    t['minute_diff_5minback'] = (t['close'].shift(5)-t['open'].shift(1))/t['open'].shift(1)
    t['minute_diff_15minback'] = (t['close'].shift(15)-t['open'].shift(1))/t['open'].shift(1)
    t['minute_diff_15minfuture'] = (t['close'].shift(-15)-t['open'].shift(-1))/t['open'].shift(-1)
    t['minute_diff_5minfuture'] = (t['close'].shift(-5)-t['open'].shift(-1))/t['open'].shift(-1)
    t['minute_diff'] = (t['close']-t['open'])/t['open']
    t['minute_diff'] *=10.0
    t['minute_diff']+=1.5
    
    t['minute_diffHL'] = (t['high']-t['low'])/t['open']
    t['minute_diffHL'] *=10.0
    t['minute_diffHL']+=1.75
    t['change'] = t.close
    t['change'] -= t.open.values[-1]
    t['change'] /= t.open.values[-1]

def PerformFit(t_in,window=5,poly_order=2):
    z4=None
    p4=None
    t = None
    try:
        #print(x,prices)
        #sys.stdout.flush()
        t = t_in[-1*window:]
        z4 = np.polyfit(t.i, t.close, poly_order)
        p4 = np.poly1d(z4)
    except (np.linalg.LinAlgError) as e:
        print("Testing multiple exceptions. {}".format(e.args[-1]))
        print(x,prices)
        sys.stdout.flush()

    return z4,p4
    
def FitWithBandMeanRev(my_index, arr_prices, doMarker=True, ticker='X',outname='', poly_order = 2, price_key='adj_close',doDateKey=False,spy_comparison=[], doRelative=False, doPlot=False, doJoin=True, debug=False):
    """
    my_index : datetime array
    price : array of prices or values
    doMarker : bool : draw markers or if false draw line
    ticker : str : ticker symbol name
    outname : str : name of histogram to save as
    poly_order : int : order of polynomial to fit
    price_key : str : name of the price to entry to fit
    spy_comparison : array : array of prices to use as a reference. don't use when None
    doRelative : bool : compute the error bands with relative changes. Bigger when there is a big change in price
    doJoin : bool : join the two arrays on matching times
"""
    prices = arr_prices[price_key]
    x=my_index.values
    #print(x)
    if not doDateKey:
        x = mdates.date2num(my_index)
    xx = x
    dd = xx
    if not doDateKey:
        xx = np.linspace(x.min(), x.max(), 1000)        
        dd = mdates.num2date(xx)

    # prepare a spy comparison
    ylabelPlot='Price for %s' %ticker 
    if len(spy_comparison)>0:
        ylabelPlot='Price for %s / SPY' %ticker
           
        if not doJoin:
            arr_prices = arr_prices.copy(True)
            spy_comparison = spy_comparison.loc[arr_prices.index,:]
            prices /= (spy_comparison[price_key] / spy_comparison[price_key][-1])
            arr_prices.loc[arr_prices.index==spy_comparison.index,'high'] /= (spy_comparison.high / spy_comparison.high[-1])
            arr_prices.loc[arr_prices.index==spy_comparison.index,'low']  /= (spy_comparison.low  / spy_comparison.low[-1])
            arr_prices.loc[arr_prices.index==spy_comparison.index,'open'] /= (spy_comparison.open / spy_comparison.open[-1])
        else:
            arr_prices = arr_prices.copy(True)
            spy_comparison = spy_comparison.copy(True)
            arr_prices = arr_prices.join(spy_comparison,how='left',rsuffix='_spy')
            for i in ['high','low','open','close',price_key]:
                if len(arr_prices[i+'_spy'])>0:
                    arr_prices[i] /= (arr_prices[i+'_spy'] / arr_prices[i+'_spy'][-1])
            prices = arr_prices[price_key]

    # perform the fit
    #print(x,prices)
    z4=None
    try:
        #print(x,prices)
        #sys.stdout.flush()
        z4 = np.polyfit(x, prices, poly_order)

    except (np.linalg.LinAlgError) as e:
        print("Testing multiple exceptions. {}".format(e.args[-1]))
        print(x,prices)
        sys.stdout.flush()
    p4 = np.poly1d(z4)

    # create an error band
    diff = prices - p4(x)
    stddev = diff.std()

    output_lines = '%s,%s,%s,%s' %(p4(x)[-1],stddev,0,prices[-1])
    output_linesn = [p4(x)[-1],stddev,0,prices[-1],p4,x[-1]]
    if stddev!=0.0:
        output_lines = '%0.3f,%0.3f,%0.3f,%s' %(p4(x)[-1],stddev,diff[-1]/stddev,prices[-1])
        output_linesn = [p4(x)[-1],stddev,diff[-1]/stddev,prices[-1],p4,x[-1]]
    if doRelative:
        diff /= p4(x)
        stddev = diff.std() #*p4(x).mean()
        
    pos_count_1sigma = len(list(filter(lambda x: (x >= 0), (abs(diff)-0.5*stddev))))
    pos_count_2sigma = len(list(filter(lambda x: (x >= 0), (abs(diff)-1.0*stddev))))
    pos_count_3sigma = len(list(filter(lambda x: (x >= 0), (abs(diff)-1.5*stddev))))
    pos_count_4sigma = len(list(filter(lambda x: (x >= 0), (abs(diff)-2.0*stddev))))
    pos_count_5sigma = len(list(filter(lambda x: (x >= 0), (abs(diff)-2.5*stddev))))
    if len(diff)>0:
        if debug: print('Time period: %s for ticker: %s' %(outname,ticker))
        coverage_txt='Percent covered\n'
        coverage = [100.0*pos_count_1sigma/len(diff) , 100.0*pos_count_2sigma/len(diff),
                        100.0*pos_count_3sigma/len(diff) , 100.0*pos_count_4sigma/len(diff),
                        100.0*pos_count_5sigma/len(diff) ]
        for i in range(0,5):
            if debug: print('Percent outside %i std. dev.: %0.2f' %(i+1,coverage[i]))
            coverage_txt+='%i$\sigma$: %0.1f\n' %(i+1,coverage[i])

    if not doPlot:
        return output_linesn
    


from alpaca_trade_api.rest import TimeFrame
from alpaca_trade_api.rest import REST
from techindicators import techindicators
#import techindicators as techindicators
import alpaca_trade_api
import pandas as pd
import numpy as np
import sys
import datetime
import base as b
import pickle
import time
import os
from scipy.stats.stats import pearsonr
import matplotlib.pyplot as plt
import mplfinance as mpf
draw=False
from alpha_vantage.timeseries import TimeSeries
from dateutil.parser import parse
outdir = b.outdir
doStocks=True
loadFromPickle=True
doETFs=True
def CandleStick(data, ticker):

    # Extracting Data for plotting
    #data = pd.read_csv('candlestick_python_data.csv')
    df = data.loc[:, ['open', 'high', 'low', 'close','volume']]
    df.columns = ['Open', 'High', 'Low', 'Close','Volume']
    df['UpperB'] = data['BolUpper']        
    df['LowerB'] = data['BolLower']
    df['KeltLower'] = data['KeltLower']        
    df['KeltUpper'] = data['KeltUpper']
    df['sma200'] = data['sma200']

    # Plot candlestick.
    # Add volume.
    # Add moving averages: 3,6,9.
    # Save graph to *.png.
    ap0 = [ mpf.make_addplot(df['UpperB'],color='g'),  # uses panel 0 by default
        mpf.make_addplot(df['LowerB'],color='b'),  # uses panel 0 by default
        mpf.make_addplot(df['sma200'],color='r'),  # uses panel 0 by default        
        mpf.make_addplot(df['KeltLower'],color='darkviolet'),  # uses panel 0 by default
        mpf.make_addplot(df['KeltUpper'],color='magenta'),  # uses panel 0 by default
      ]
    #mpf.plot(df,type='candle',volume=True,addplot=ap0) 
    fig,axes=mpf.plot(df, type='candle', style='charles',
            title=ticker,
            ylabel='Price ($) %s' %ticker,
            ylabel_lower='Shares \nTraded',
            volume=True, 
            mav=(200),
            addplot=ap0,
            returnfig=True,
            savefig=outdir+'test-mplfiance_'+ticker+'.pdf')
        # Configure chart legend and title
    axes[0].legend(['Price','Bolanger Up','Bolanger Down','SMA200','Kelt+','Kelt-'])
    #axes[0].set_title(ticker)
    # Save figure to file
    fig.savefig(outdir+'test-mplfiance_'+ticker+'.pdf')
    fig.savefig(outdir+'test-mplfiance_'+ticker+'.png')
    techindicators.plot_support_levels(ticker,df,[mpf.make_addplot(df['sma200'],color='r') ],outdir=outdir)
    # adds below as a sub-plot
    #ap2 = [ mpf.make_addplot(df['UpperB'],color='g',panel=2),  # panel 2 specified
    #        mpf.make_addplot(df['LowerB'],color='b',panel=2),  # panel 2 specified
    #    ]
    #mpf.plot(df,type='candle',volume=True,addplot=ap2)
    #plt.savefig('CandleStick.pdf')
    #mpf.plot(df,tlines=[dict(tlines=datepairs,tline_use='high',colors='g'),
    #                dict(tlines=datepairs,tline_use='low',colors='b'),
    #                dict(tlines=datepairs,tline_use=['open','close'],colors='r')],
    #     figscale=1.35
    #    )
    
def LongTermPlot(my_stock_info,market,ticker,plttext=''):
    date_diff = 5*365
    my_stock_info5y = GetTimeSlot(my_stock_info, days=date_diff)
    market5y = GetTimeSlot(market, days=date_diff)
    min_length = min(len(my_stock_info5y),len(market5y))
    max_length = max(len(my_stock_info5y),len(market5y))
    if min_length<max_length:
        my_stock_info5y = my_stock_info5y[-min_length:]
        market5y = market5y[-min_length:]

    if len(market5y['adj_close'])<1 or len(my_stock_info5y['adj_close'])<1:
        print('Ticker has no adjusted close info: %s' %ticker)
        return
    my_stock_info5y['year5_return']=my_stock_info5y['adj_close']/my_stock_info5y['adj_close'][0]-1
    market5y['year5_return']=market5y['adj_close']/market5y['adj_close'][0]-1
    # comparison to the market
    plt.plot(my_stock_info5y.index,my_stock_info5y['year5_return'],color='blue',label=ticker)    
    plt.plot(market5y.index,     market5y['year5_return'],   color='red', label='SPY')    
    # beautify the x-labels
    plt.gcf().autofmt_xdate()
    plt.ylabel('5 Year Return')
    plt.xlabel('Date')
    plt.legend(loc="upper left")
    if draw: plt.show()
    plt.savefig(outdir+'longmarket%s_%s.pdf' %(plttext,ticker))
    plt.savefig(outdir+'longmarket%s_%s.png' %(plttext,ticker))
    if not draw: plt.close()
        
def GetTimeSlot(stock, days=365):
    today=datetime.datetime.now()
    past_date = today + datetime.timedelta(days=-1*days)
    date=stock.truncate(before=past_date)
    #date = stock[nearest(stock.index,past_date)]
    return date
def DrawPlots(my_stock_info,ticker,market,plttext=''):
    #plt.plot(stock_info.index,stock_info['close'])
    techindicators.supportLevels(my_stock_info)
    if not draw:
        plt.ioff()
    plt.plot(my_stock_info.index,my_stock_info['adj_close'])
    # beautify the x-labels
    plt.gcf().autofmt_xdate()
    plt.ylabel('Closing price')
    plt.xlabel('Date')
    if draw: plt.show()
    plt.savefig(outdir+'price_support%s_%s.pdf' %(plttext,ticker))
    plt.savefig(outdir+'price_support%s_%s.png' %(plttext,ticker))
    if not draw: plt.close()
    plt.plot(my_stock_info.index,my_stock_info['copp'])    
    # beautify the x-labels
    plt.gcf().autofmt_xdate()
    plt.ylabel('Coppuck Curve')
    plt.xlabel('Date')
    plt.hlines(0.0,xmin=min(my_stock_info.index), xmax=max(my_stock_info.index),colors='black')
    if draw: plt.show()
    plt.savefig(outdir+'copp%s_%s.pdf' %(plttext,ticker))
    plt.savefig(outdir+'copp%s_%s.png' %(plttext,ticker))
    if not draw: plt.close()
    plt.plot(my_stock_info.index,my_stock_info['sharpe'])    
    # beautify the x-labels
    plt.gcf().autofmt_xdate()
    plt.ylabel('Sharpe Ratio')
    plt.xlabel('Date')
    plt.hlines(0.0,xmin=min(my_stock_info.index), xmax=max(my_stock_info.index),colors='black')
    if draw: plt.show()
    plt.savefig(outdir+'sharpe%s_%s.pdf' %(plttext,ticker))
    plt.savefig(outdir+'sharpe%s_%s.png' %(plttext,ticker))
    if not draw: plt.close()
    plt.plot(my_stock_info.index,my_stock_info['beta'])
    # beautify the x-labels
    plt.gcf().autofmt_xdate()
    plt.ylabel('Beta')
    plt.xlabel('Date')
    if draw: plt.show()
    plt.savefig(outdir+'beta%s_%s.pdf' %(plttext,ticker))
    plt.savefig(outdir+'beta%s_%s.png' %(plttext,ticker))
    if not draw: plt.close()
    plt.plot(my_stock_info.index,my_stock_info['alpha'])    
    # beautify the x-labels
    plt.gcf().autofmt_xdate()
    plt.ylabel('Alpha')
    plt.xlabel('Date')
    plt.hlines(0.0,xmin=min(my_stock_info.index), xmax=max(my_stock_info.index),colors='black')
    plt.title(' Alpha')
    if draw: plt.show()
    plt.savefig(outdir+'alpha%s_%s.pdf' %(plttext,ticker))
    plt.savefig(outdir+'alpha%s_%s.png' %(plttext,ticker))
    if not draw: plt.close()
    plt.plot(my_stock_info.index,my_stock_info['rsquare'])    
    # beautify the x-labels
    plt.gcf().autofmt_xdate()
    plt.ylabel('R-squared')
    plt.xlabel('Date')
    plt.hlines(0.7,xmin=min(my_stock_info.index), xmax=max(my_stock_info.index),colors='black')
    if draw: plt.show()
    plt.savefig(outdir+'rsquare%s_%s.pdf' %(plttext,ticker)) 
    plt.savefig(outdir+'rsquare%s_%s.png' %(plttext,ticker))
    if not draw: plt.close()
    # CMF
    plt.plot(my_stock_info.index,my_stock_info['cmf'])    
    # beautify the x-labels
    plt.gcf().autofmt_xdate()
    plt.ylabel('CMF')
    plt.xlabel('Date')
    plt.hlines(0.2,xmin=min(my_stock_info.index), xmax=max(my_stock_info.index),colors='green',linestyle='dotted')
    plt.hlines(0.0,xmin=min(my_stock_info.index), xmax=max(my_stock_info.index),colors='black')
    plt.hlines(-0.2,xmin=min(my_stock_info.index), xmax=max(my_stock_info.index),colors='red',linestyle='dotted')    
    if draw: plt.show()
    plt.savefig(outdir+'cmf%s_%s.pdf' %(plttext,ticker))
    plt.savefig(outdir+'cmf%s_%s.png' %(plttext,ticker))
    if not draw: plt.close()
    # comparison to the market
    plt.plot(my_stock_info.index,my_stock_info['yearly_return'],color='blue',label=ticker)    
    plt.plot(market.index,     market['yearly_return'],   color='red', label='SPY')    
    # beautify the x-labels
    plt.gcf().autofmt_xdate()
    plt.ylabel('Yearly Return')
    plt.xlabel('Date')
    plt.legend(loc="upper left")
    if draw: plt.show()
    plt.savefig(outdir+'market%s_%s.pdf' %(plttext,ticker))
    plt.savefig(outdir+'market%s_%s.png' %(plttext,ticker))
    if not draw: plt.close()
    # comparison to the market monthly returns
    plt.bar(my_stock_info['monthly_return'].dropna().index,my_stock_info['monthly_return'].dropna(),color='blue',label=ticker,width = 5.25)    
    plt.bar(market['monthly_return'].dropna().index,     market['monthly_return'].dropna(),   color='red', label='SPY', width = 5.25)
    # beautify the x-labels
    plt.gcf().autofmt_xdate()
    plt.ylabel('Monthly Return')
    plt.xlabel('Date')
    plt.legend(loc="upper left")
    if draw: plt.show()
    plt.savefig(outdir+'monthlymarket%s_%s.pdf' %(plttext,ticker))
    plt.savefig(outdir+'monthlymarket%s_%s.png' %(plttext,ticker))
    if not draw: plt.close()
    CandleStick(my_stock_info,ticker)
    
def AddInfo(stock,market):
    stock['sma10']=techindicators.sma(stock['adj_close'],10)
    stock['sma20']=techindicators.sma(stock['adj_close'],20)
    if len(stock['adj_close'])>100:
        stock['sma100']=techindicators.sma(stock['adj_close'],100)
    else: stock['sma100']=np.zeros(len(stock['adj_close']))
    if len(stock['adj_close'])>200:    
        stock['sma200']=techindicators.sma(stock['adj_close'],200)
    else: stock['sma200']=np.zeros(len(stock['adj_close']))
    stock['rstd10']=techindicators.rstd(stock['adj_close'],10)
    stock['rsi10']=techindicators.rsi(stock['adj_close'],10)
    stock['cmf']=techindicators.cmf(stock['high'],stock['low'],stock['close'],stock['volume'],10)
    stock['BolLower'],stock['BolCenter'],stock['BolUpper']=techindicators.boll(stock['adj_close'],20,2.0,5)
    stock['KeltLower'],stock['KeltCenter'],stock['KeltUpper']=techindicators.kelt(stock['high'],stock['low'],stock['close'],20,2.0,20)
    stock['copp']=techindicators.copp(stock['close'],14,11,10)
    stock['daily_return']=stock['adj_close'].pct_change(periods=1)
    stock['daily_return_stddev14']=techindicators.rstd(stock['daily_return'],14)
    stock['beta']=techindicators.rollingBetav2(stock,14,market)
    stock['alpha']=techindicators.rollingAlpha(stock,14,market)        
    stock['rsquare']=techindicators.rollingRsquare(stock,14,market)
    stock['sharpe']=techindicators.sharpe(stock['daily_return'],30) # generally above 1 is good
    #stock['adj_close_percent']=techindicators.sharpe(stock['daily_return'],30) # generally above 1 is good    
    stock['weekly_return']=stock['adj_close'].pct_change(freq='W')
    stock['monthly_return']=stock['adj_close'].pct_change(freq='M')
    stock_1y = GetTimeSlot(stock)
    if len(stock_1y['adj_close'])<1:
        print('Ticker has no adjusted close info: %s' %ticker)
        stock['yearly_return']=stock['adj_close']
    else:
        stock['yearly_return']=stock['adj_close']/stock_1y['adj_close'][0]-1

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
    
def runTickerAlpha(ts, ticker):
    
    #a=ts.get_daily(ticker,'full')
    a=ts.get_daily_adjusted(ticker,'full')
    #print(a)
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
    #print(output)
    return output
    
def runTicker(api, ticker):
    today=datetime.datetime.now()
    yesterday = today + datetime.timedelta(days=-1)
    d1 = yesterday.strftime("%Y-%m-%d")
    fouryao = (today + datetime.timedelta(days=-364*4.5)).strftime("%Y-%m-%d")  
    trade_days = api.get_bars(ticker, TimeFrame.Day, fouryao, d1, 'raw').df
    return trade_days
    #print(ticker)
    #print(trade_days)
ALPACA_ID = os.getenv('ALPACA_ID')
ALPACA_PAPER_KEY = os.getenv('ALPACA_PAPER_KEY')
ALPHA_ID = os.getenv('ALPHA_ID')
api = REST(ALPACA_ID,ALPACA_PAPER_KEY)
ts = TimeSeries(key=ALPHA_ID)
spy = runTicker(api,'SPY')
ticker='TSLA'
#ticker='TSLA'
stock_info=None
spy=None
if loadFromPickle and os.path.exists("%s.p" %ticker):
    stock_info = pickle.load( open( "%s.p" %ticker, "rb" ) )
    spy = pickle.load( open( "SPY.p", "rb" ) )
else:
    #stock_info = runTicker(api,ticker)
    stock_info=runTickerAlpha(ts,ticker)
    spy=runTickerAlpha(ts,'SPY')
    pickle.dump( spy, open( "SPY.p", "wb" ) )
    pickle.dump( stock_info, open( "%s.p" %ticker, "wb" ) )
# add info
if len(stock_info)==0:
    print('ERROR - empy info %s' %ticker)
spy['daily_return']=spy['adj_close'].pct_change(periods=1)
AddInfo(spy, spy)
spy_1year = GetTimeSlot(spy)
DrawPlots(spy_1year,'SPY',spy_1year)

j=0
cdir = os.getcwd()
if doStocks:
    for s in b.stock_list:
        if s[0]=='SPY':
            continue
        if s[0].count('^'):
            continue
        if j%4==0 and j!=0:
            time.sleep(56)
        print(s[0])
        sys.stdout.flush()
        tstock_info=None
        #if j>2:
        #    break
        try:
            tstock_info=runTickerAlpha(ts,s[0])
        except ValueError:
            j+=1
            continue
        try:
            AddInfo(tstock_info, spy)
        except ValueError:
            print('Error processing %s' %s[0])
            j+=1
            continue
        tstock_info = GetTimeSlot(tstock_info) # gets the one year timeframe
        DrawPlots(tstock_info,s[0],spy_1year)
        os.chdir(outdir)
        b.makeHTML('%s.html' %s[0],s[0],filterPattern='*_%s' %s[0],describe=s[4])
        os.chdir(cdir)    
        j+=1
if doETFs:
    j=0
    for s in b.etfs:
        if s[0].count('^'):
            continue
        if j%4==0 and j!=0:
            time.sleep(56)
        print(s[0])
        sys.stdout.flush()
        estock_info=None
        try:
            if loadFromPickle and os.path.exists("%s.p" %s[0]):
                estock_info = pickle.load( open( "%s.p" %s[0], "rb" ) )
            else:
                estock_info=runTickerAlpha(ts,s[0])
                pickle.dump( estock_info, open( "%s.p" %s[0], "wb" ) )
                j+=1
        except ValueError:
            print('ERROR processing...ValueError %s' %s[0])
            j+=1
            continue
        LongTermPlot(estock_info,spy,ticker=s[0])

        try:
            AddInfo(estock_info, spy)
        except ValueError:
            print('Error processing %s' %s[0])
            continue
        estock_info = GetTimeSlot(estock_info) # gets the one year timeframe 
        DrawPlots(estock_info,s[0],spy_1year)
        os.chdir(outdir)
        b.makeHTML('%s.html' %s[0],s[0],filterPattern='*_%s' %s[0],describe=s[4],linkIndex=0)
        os.chdir(cdir)

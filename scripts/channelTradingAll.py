from techindicators import techindicators
#import techindicators as techindicators
from ReadData import ALPACA_REST,ALPHA_TIMESERIES,is_date,runTickerAlpha,runTicker,SQL_CURSOR,ConfigTable,GetTimeSlot,AddInfo,IS_ALPHA_PREMIUM_WAIT_ITER,GLOBAL_MARKET_PLOTS,MakePlotMulti,MakePlot,POS_MARKET_PLOTS,AddSMA,GetMidAirRefuel
import pandas as pd
import numpy as np
import sys
import datetime
import base as b
import pickle
import time
import os,copy
from scipy.stats.stats import pearsonr
import matplotlib.pyplot as plt
import matplotlib
#matplotlib.use('Agg')
#matplotlib.use('GTK3Agg')
matplotlib.use('cairo') 
import mplfinance as mpf
import argparse
from zigzag import *
import matplotlib.dates as mdates
from scipy.stats.mstats import gmean
import yfinance as yf

my_parser = argparse.ArgumentParser()
#my_parser.add_argument('--input', default='', type=str, required=True)
my_parser.add_argument('--filter', default='', type=str) # filter by ticker
my_parser.add_argument('--add', default='', type=str) # filter by ticker
my_parser.add_argument('--skip', default=False, action='store_true' ) # filter by ticker
args = my_parser.parse_args()

draw=False
outdir = b.outdir
doStocks=True
loadFromPickle=True
doETFs=True
doPDFs=False
debug=False
loadSQL=True
readType='full'

def GetMonthlyReturns(stockdatain,ticker):
    """stockdatain : array of stock prices by date
    ticker : str : stock ticker symbol
"""
    # add info
    if len(stockdatain)==0:
        print('ERROR - empy info %s' %ticker)

    startMR = time.time()        
    stockdata = stockdatain.copy(True)
    stockdata['daily_return']=stockdata['adj_close'].pct_change(periods=1)+1
    stockdata['openclosepct'] = (stockdata.close-stockdata.open)/stockdata.open+1
    stockdata['closeopenpct'] = (stockdata.open-stockdata.shift(1).close)/stockdata.shift(1).close+1
    stockdata['afterhourspct'] = (stockdata.shift(-1).open-stockdata.close)/stockdata.close+1
    stockdata['year']=stockdata.index.year
    stockdata['day']=stockdata.index.day
    stockdata['month']=stockdata.index.month
    stockdata['dayofyear']=stockdata.index.dayofyear
    stockdata['dayofweek']=stockdata.index.dayofweek
    stockdata['weekofyear']=stockdata.index.isocalendar().week
    stockdata['is_month_end']=stockdata.index.is_month_end
    if debug: print(stockdata[['open','close','daily_return','adj_close','openclosepct','closeopenpct']])
    endMR = time.time()
    if debug: print('Process time to GetMonthlyReturns preprocessing: %s' %(endMR - startMR))
    
    # compute monthly returns first for the mid month
    startMR = time.time()
    stockdata15 = stockdata[stockdata.day<16]
    stockdata15_month_grouped = stockdata15.groupby(['year','month'])
    end_of_month15_idx = stockdata15_month_grouped.day.transform(max) == stockdata15['day']
    stockdata15_end_of_month = stockdata15[end_of_month15_idx].copy(True)
    stockdata15_end_of_month.loc[:,'monthly_return'] = stockdata15_end_of_month.adj_close.pct_change(periods=1)
    # for the first of the month
    stockdata_month_grouped = stockdata.groupby(['year','month'])
    end_of_month_idx = stockdata_month_grouped.day.transform(max) == stockdata['day']
    stockdata_end_of_month = stockdata[end_of_month_idx].copy(True)
    endMR = time.time()
    if debug: print('Process time to GetMonthlyReturns groupby: %s' %(endMR - startMR))    
    startMR = time.time()
    MakePlotMulti(stockdata_end_of_month.index, yaxis=[(stockdata_month_grouped['openclosepct']).apply(gmean)-1,(stockdata_month_grouped['closeopenpct']).apply(gmean)-1,(stockdata_month_grouped['daily_return']).apply(gmean)-1], colors=['black','green','red'], labels=['trading hours','overnight','close to close'], xname='Date',yname='Returns',saveName='RETURNS_returns_daynight_monthly_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    endMR = time.time()
    if debug: print('Process time to GetMonthlyReturns draw: %s' %(endMR - startMR))
    
    stockdata_end_of_month.loc[:,'monthly_return'] = stockdata_end_of_month.adj_close.pct_change(periods=1)
    stockdata_end_of_month_avg = stockdata_end_of_month.groupby('month').mean()
    stockdata_end_of_month_std = stockdata_end_of_month.groupby('month').std()
    stockdata_end_of_month_avg.loc[:,'signif'] = stockdata_end_of_month_avg.monthly_return / stockdata_end_of_month_std.monthly_return
    MakePlot(stockdata_end_of_month_avg.index, stockdata_end_of_month_avg.monthly_return, xname='Month',yname='Avg. Monthly Returns',saveName='RETURNS_avg_monthly_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(stockdata_end_of_month_std.index, stockdata_end_of_month_std.monthly_return, xname='Month',yname='Std Dev. Monthly Returns',saveName='RETURNS_stddev_monthly_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(stockdata_end_of_month_avg.index, stockdata_end_of_month_avg.signif, xname='Month',yname='Signif. Monthly Returns',saveName='RETURNS_signif_monthly_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    
    # scatter plot
    MakePlot(stockdata_end_of_month.month, stockdata_end_of_month.monthly_return, xname='Month',yname='Monthly Returns',saveName='RETURNS_scatter_monthly_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,doScatter=True,draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(stockdata_end_of_month.month, stockdata_end_of_month.monthly_return, xname='Month on the 1st',yname='Monthly Returns',saveName='RETURNS_box_monthly_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,doBox=True,draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(stockdata15_end_of_month.month, stockdata15_end_of_month.monthly_return, xname='Month on the 15th',yname='Monthly Returns',saveName='RETURNS_box_monthly15_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,doBox=True,draw=draw,doPDFs=doPDFs,outdir=outdir)
    
    ## remove unity
    stockdata['daily_return'] -=1
    stockdata['openclosepct'] -=1
    stockdata['closeopenpct'] -=1
    
    # Compare returns
    if debug: print(stockdata[['openclosepct','daily_return','closeopenpct']].describe())
    if debug: print(stockdata[['openclosepct','daily_return','closeopenpct']].corr())
    
    # compute weekly returns
    stockdata_yearly_grouped = stockdata.groupby(['year','weekofyear'])
    end_of_week_idx = stockdata_yearly_grouped.dayofyear.transform(max)==stockdata.dayofyear
    stockdata_end_of_week = stockdata.loc[end_of_week_idx,:].copy(True)
    stockdata_end_of_week.loc[:,'weekly_return'] = stockdata_end_of_week['adj_close'].pct_change(periods=1)
    stockdata_end_of_week_avg = stockdata_end_of_week.groupby('weekofyear').mean()
    stockdata_end_of_week_std = stockdata_end_of_week.groupby('weekofyear').std()
    stockdata_end_of_week_avg['signif'] = stockdata_end_of_week_avg.weekly_return / stockdata_end_of_week_std.weekly_return

    
    MakePlot(stockdata_end_of_week_avg.index, stockdata_end_of_week_avg.weekly_return, xname='Week of year',yname='Avg. Weekly Returns',saveName='RETURNS_avg_weekly_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(stockdata_end_of_week_std.index, stockdata_end_of_week_std.weekly_return, xname='Week of year',yname='Std Dev. Weekly Returns',saveName='RETURNS_stddev_weekly_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(stockdata_end_of_week_avg.index, stockdata_end_of_week_avg.signif, xname='Week of year',yname='Signif. Weekly Returns',saveName='RETURNS_signif_weekly_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    
    # compute day of week return.
    stockdata_day_of_week_avg = stockdata.groupby('dayofweek').mean()
    stockdata_day_of_week_std = stockdata.groupby('dayofweek').std()
    stockdata_day_of_week_avg['signif'] = stockdata_day_of_week_avg.daily_return / stockdata_day_of_week_std.daily_return
    MakePlot(stockdata_day_of_week_avg.index, stockdata_day_of_week_avg.daily_return, xname='Day of week',yname='Avg. Daily Returns',saveName='RETURNS_avg_daily_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(stockdata_day_of_week_std.index, stockdata_day_of_week_std.daily_return, xname='Day of week',yname='Std Dev. Daily Returns',saveName='RETURNS_stddev_daily_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(stockdata_day_of_week_std.index, stockdata_day_of_week_avg.signif, xname='Day of week',yname='Signif. Daily Returns',saveName='RETURNS_signif_daily_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    
    # compute day of month return.
    startMR = time.time()
    stockdata_day_of_month_avg = stockdata.groupby('day').mean()
    stockdata_day_of_month_std = stockdata.groupby('day').std()
    stockdata_day_of_month_avg['signif'] = stockdata_day_of_month_avg.daily_return / stockdata_day_of_month_std.daily_return
    MakePlot(stockdata_day_of_month_avg.index, stockdata_day_of_month_avg.daily_return, xname='Day of month',yname='Avg. Daily Returns',saveName='RETURNS_avg_day_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(stockdata_day_of_month_std.index, stockdata_day_of_month_std.daily_return, xname='Day of month',yname='Std Dev. Daily Returns',saveName='RETURNS_stddev_day_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(stockdata_day_of_month_avg.index, stockdata_day_of_month_avg['signif'], xname='Day of month',yname='Signif. Daily Returns',saveName='RETURNS_signif_day_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    endMR = time.time()
    if debug: print('Process time to GetMonthlyReturns plots day of month: %s' %(endMR - startMR))
    
    # overnight vs daily ...gmean is slow, so could be improved!
    startMR = time.time()
    stockdata['openclosepctma20'] = ((stockdata['openclosepct']+1).rolling(20).apply(gmean)-1)
    stockdata['closeopenpctma20'] = ((stockdata['closeopenpct']+1).rolling(20).apply(gmean)-1)
    stockdata['daily_returnma20'] = ((stockdata['daily_return']+1).rolling(20).apply(gmean)-1)
    #stockdata['openclosepctma5'] = ((stockdata['openclosepct']+1).rolling(5).apply(gmean)-1)
    #stockdata['closeopenpctma5'] = ((stockdata['closeopenpct']+1).rolling(5).apply(gmean)-1)
    #stockdata['daily_returnma5'] = ((stockdata['daily_return']+1).rolling(5).apply(gmean)-1)
    endMR = time.time()
    if debug: print('Process time to GetMonthlyReturns gmean: %s' %(endMR - startMR))
    #stockdata['openclosepctmavg20'] = stockdata['openclosepct'].rolling(20).mean()
    #stockdata['closeopenpctmavg20'] = stockdata['closeopenpct'].rolling(20).mean()
    #stockdata['daily_returnmavg20'] = stockdata['daily_return'].rolling(20).mean()
    #stockdata['openclosepctmag5'] = stockdata['openclosepct'].rolling(5).mean()
    #stockdata['closeopenpctmag5'] = stockdata['closeopenpct'].rolling(5).mean()
    #stockdata['daily_returnmag5'] = stockdata['daily_return'].rolling(5).mean()

    stockdata_1y = GetTimeSlot(stockdata, days=365)
    MakePlotMulti(stockdata.index, yaxis=[stockdata['openclosepctma20'],stockdata['closeopenpctma20'],stockdata['daily_returnma20']], colors=['black','green','red'], labels=['trading hours','overnight','close to close'], xname='Date',yname='Returns Geo MA20',saveName='RETURNS_returns_daynight_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlotMulti(stockdata_1y.index, yaxis=[stockdata_1y['openclosepctma20'],stockdata_1y['closeopenpctma20'],stockdata_1y['daily_returnma20']], colors=['black','green','red'], labels=['trading hours','overnight','close to close'], xname='Date',yname='Returns Geo MA20',saveName='RETURNS_returns_daynight_oneyear_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    #MakePlotMulti(stockdata_1y.index, yaxis=[stockdata_1y['openclosepctma5'],stockdata_1y['closeopenpctma5'],stockdata_1y['daily_returnma5']], colors=['black','green','red'], labels=['trading hours','overnight','close to close'], xname='Date',yname='Returns Geo MA5',saveName='RETURNS_returns_daynight_oneyear_ma5_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    
    MakePlotMulti(stockdata_1y.index, yaxis=[stockdata_1y['openclosepct'],stockdata_1y['closeopenpct'],stockdata_1y['daily_return']], colors=['black','green','red'], labels=['trading hours','overnight','close to close'], xname='Date',yname='Returns',saveName='RETURNS_returns_daynight_oneyear_noMA_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,draw=draw,doPDFs=doPDFs,outdir=outdir)
    
    # Compare returns
    if debug:
        print(stockdata[['openclosepct','closeopenpct','open','close']])
        print(stockdata_1y[['openclosepct','daily_return','closeopenpct','afterhourspct']].describe())
        print(stockdata_1y[['openclosepct','daily_return','closeopenpct','afterhourspct']].corr())
    MakePlot(stockdata_1y['openclosepct'], stockdata_1y['afterhourspct'], xname='During trading hours',yname='After hours night after',saveName='RETURNS_trading_vs_nightafter_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,doScatter=True,draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(stockdata_1y['openclosepct'], stockdata_1y['closeopenpct'], xname='During trading hours',yname='After hours night before',saveName='RETURNS_trading_vs_nightbefore_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,doScatter=True,draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(stockdata_1y['openclosepct'], stockdata_1y['daily_return'], xname='During trading hours',yname='Returns',saveName='RETURNS_trading_vs_returns_'+ticker, hlines=[],title='',doSupport=False,my_stock_info=None,doScatter=True,draw=draw,doPDFs=doPDFs,outdir=outdir)

# https://www.investopedia.com/terms/z/zig_zag_indicator.asp
def plot_pivots(xaxis, yaxis, saveName='zigzag', xname='Date', yname='Beta',title='ZigZag'):
    """Plotting the pivot points - when a stock changes direction
         
         Parameters:
         xaxis : numpy array
            Date of stock value
         yaxis : numpy array
            Closing stock value
         saveName : str
            Saved file name
         xname : str
            x-axis name
         yname : str
            y-axis name
         title : str
            Title of plot"""
    #modes = pivots_to_modes(pivots) # 1 for valley to peak and -1 for peak to valley
    #pd.Series(X).pct_change().groupby(modes).describe().unstack()
    #compute_segment_returns(X, pivots)
    #max_drawdown(X) = (trough value - peak)/peak -> look for a small value

    plt.clf()
    
    pivots = peak_valley_pivots(yaxis.values, 0.05, -0.05)
    ts_pivots = yaxis #pd.Series(yaxis, index=xaxis)
    ts_pivots = ts_pivots[pivots != 0]
    yaxis.plot(color='black',alpha=0.8)
    
    plt.ylim(yaxis.min()*0.99, yaxis.max()*1.01)
    plt.plot(yaxis[pivots != 0].index, yaxis[pivots != 0], 'b-',alpha=0.5)
    plt.scatter(yaxis[pivots == 1].index, yaxis[pivots == 1], color='g')
    plt.scatter(yaxis[pivots == -1].index, yaxis[pivots == -1], color='r')
    axb = plt.gca()
    
    # compute the most recent zigzag for fibs
    last_range = 0.0
    last_price=0
    fibsL=[0,0.236,0.382,0.5,0.618,0.764,1.0,1.618]    
    fibs=[0,0.236,0.382,0.5,0.618,0.764,1.0,1.618]
    xpos = 0
    if len( yaxis[pivots == -1])>0 and len(yaxis[pivots == 1])>0:
        yaxisimportant = pd.concat([yaxis[pivots == -1],yaxis[pivots == 1]])
        yaxisimportant = yaxisimportant.sort_index()
        last_range = yaxisimportant[-1] - yaxisimportant[-2]
            
        if last_range < 0:
            last_price = yaxisimportant[-1]
            xpos = yaxis[pivots == -1].index[-1]
            fibsL = fibsL[::-1]
        else:
            last_price = yaxisimportant[-1]
            xpos = yaxis[pivots == 1].index[-1]
            
        for f in range(0,len(fibs)):
            if last_range<0:
                fibs[f] = last_range*fibs[f]+last_price
            else:
                fibs[f] = -last_range*fibs[f]+last_price    
        #print(yaxis[pivots == -1].index)
    if debug: print('last range: %s %s' %(last_range,last_price))
    
    plt.gcf().autofmt_xdate()
    #ts_pivots.plot(style='g-o');
    plt.ylabel(yname)
    plt.xlabel(xname)
    l=0
    for level in fibs:
        mylim = axb.get_xlim()
        mylimy = axb.get_ylim()
        axb.axhline(y=level,  color='grey',linewidth=0.5,linestyle='-') #xpos-20,xpos+10,level, #xmin=mylimy[0]+10, xmax=mylimy[1]-10, xmin=mylim[1]-20, xmax=mylim[1]-2,
        #plt.axhline(xpos-20,xpos+10,level,color='blue',linewidth=0.5,linestyle='-')
        axb.text(mylim[1]+1, level, ' %0.2f fib%0.1f' %(level,fibsL[l]*100), fontsize=4) #xpos+
        l+=1
    if title!="":
        plt.title(title, fontsize=30)
    if draw: plt.show()
    if doPDFs: plt.savefig(outdir+'%s.pdf' %(saveName))
    plt.savefig(outdir+'%s.png' %(saveName))
    if not draw: plt.close()
    plt.close()
    
# Draw the timing indices
def PlotTiming(data, ticker):
    """ Plot timing indicators including moving averages as well as Fourier Transforms
        
         Parameters:
         data - pandas data frame with time plus adj_close price
         ticker - string
                ticker symbol for the stock
    """
    if len(data)<1:
        return
    plt.clf()
    fig8 = plt.figure(constrained_layout=False)
    gs1 = fig8.add_gridspec(nrows=3, ncols=1, left=0.07, right=0.95, wspace=0.05)
    top_plt = fig8.add_subplot(gs1[:-1, :])
    top_plt.plot(data.index, data["adj_close"],color='black',label='Adj Close')
    top_plt.plot(data.index, data["sma200"],color='magenta',label='SMA200')
    top_plt.plot(data.index, data["sma100"],color='cyan',label='SMA100')
    top_plt.plot(data.index, data["sma50"],color='yellow',label='SMA50')
    top_plt.plot(data.index, data["sma20"],color='green',label='SMA20')
    top_plt.plot(data.index, data["ema13"],color='blue',label='EMA13')
    # add a vertical line when the coppuck changes from negative to positive
    #data['copp1']=data.copp.shift(1)
    #print(data[['copp','copp1']])
    #print(data[((data['copp']-data['copp'].shift(1))>data['copp']) & (data['copp']*data['copp'].shift(1)<0)][['copp','adj_close']])
    #print(data[((data['copp']-data['copp'].shift(1))<data['copp']) & (data['copp']*data['copp'].shift(1)<0)][['copp','adj_close']])    
    #print(data[((data['copp']-data['copp'].shift(1))>0) & (data['copp']<-10)][['copp','adj_close']])
    midair = GetMidAirRefuel(data)
    if len(midair)>0:
        print('Midair refuel')
        print(GetMidAirRefuel(data))
    plt.legend(loc="upper center")
    techindicators.supportLevels(data)
    top_plt.grid(1)
    top_plt.set_ylabel('Closing Price')
    bottom_plt = fig8.add_subplot(gs1[-1, :])
    maxHT_DCPERIOD = max(max(data['HT_DCPERIOD']),1.0)/3.0
    maxHT_DCPHASE = max(max(data['HT_DCPHASE']),1.0)/3.0
    bottom_plt.plot(data.index, data['HT_DCPERIOD']/maxHT_DCPERIOD,color='red',label='Dominant Cycle Period')
    bottom_plt.plot(data.index, data['HT_DCPHASE']/maxHT_DCPHASE,color='green',label='Dominant Cycle Phase')
    bottom_plt.bar(data.index, data['HT_TRENDMODE'],color='blue',label='Trend vs Cycle Mode')
    bottom_plt.set_xlabel('%s Date' %ticker)
    bottom_plt.set_ylabel('Timing')
    plt.legend(loc="upper left")
    bottom_plt.grid(1)
    top_plt.set_title('HT Dominant cycle', fontsize=40)
    plt.gcf().set_size_inches(11,8)
    if doPDFs: plt.savefig(outdir+'timing_'+ticker+'.pdf')
    plt.savefig(outdir+'timing_'+ticker+'.png')

    top_plt.set_title('HTSine', fontsize=40)
    bottom_plt.clear()
    bottom_plt.plot(data.index, data['HT_SINE'],color='red',label='HTSine Slow')
    bottom_plt.plot(data.index, data['HT_SINElead'],color='green',label='HTSine Lead')
    bottom_plt.set_xlabel('%s Date' %ticker)
    bottom_plt.set_ylabel('HTSine')
    plt.legend(loc="upper left")
    bottom_plt.grid(1)

    plt.gcf().set_size_inches(11,8)
    if doPDFs: plt.savefig(outdir+'HTSine_'+ticker+'.pdf')
    plt.savefig(outdir+'HTSine_'+ticker+'.png')
    if not draw: plt.close()
        
# Draw the volume and the price by volume with various inputs
def PlotVolume(data, ticker):
    """ Plot Volume indicators along with moving averages 
        
         Parameters:
         data - pandas data frame with time plus adj_close price
         ticker - string
                ticker symbol for the stock
    """
    if len(data)<1:
        return
    # group the volume by closing price by the set division
    bucket_size = 0.025 * (max(data['adj_close']) - min(data['adj_close']))    
    volprofile  = data['volume'].groupby(data['adj_close'].apply(lambda x: bucket_size*round(x/bucket_size,0))).sum()/1.0e6
    posvolprofile  = data['pos_volume'].groupby(data['adj_close'].apply(lambda x: bucket_size*round(x/bucket_size,0))).sum()/1.0e6
    negvolprofile  = data['neg_volume'].groupby(data['adj_close'].apply(lambda x: bucket_size*round(x/bucket_size,0))).sum()/1.0e6
    
    plt.clf()
    fig8 = plt.figure(constrained_layout=False)
    gs1 = fig8.add_gridspec(nrows=3, ncols=1, left=0.07, right=0.95, wspace=0.05)
    top_plt = fig8.add_subplot(gs1[:-1, :])
    top_plt.set_title('Price by Volume',fontsize=40)    
    top_plt.plot(data.index, data["adj_close"],color='black',label='Adj Close')
    top_plt.plot(data.index, data["sma200"],color='magenta',label='SMA200')
    top_plt.plot(data.index, data["sma100"],color='cyan',label='SMA100')
    top_plt.plot(data.index, data["sma50"],color='yellow',label='SMA50')
    top_plt.plot(data.index, data["sma20"],color='peru',label='SMA20')
    top_plt.plot(data.index, data["ema13"],color='teal',label='EMA13')
    plt.legend(loc="upper center")
    techindicators.supportLevels(data)
    # normalize this bar chart to have half of the width. Need to get this because matplotlib doesn't use
    # timestamps. It converts them to an internal float.
    # Then we stack the negative and positive values
    xmin, xmax, ymin, ymax = top_plt.axis()
    normalize_vol=1.0
    try:
        normalize_vol = 0.5*(xmax - xmin)/max(volprofile.values)
    except:
        pass
    volprofile*=normalize_vol;   posvolprofile*=normalize_vol;     negvolprofile*=normalize_vol;
    plt.barh(posvolprofile.index.values, posvolprofile.values, height=0.9*bucket_size, align='center', color='green', alpha=0.45,left=xmin+(xmax-xmin)*0.001)
    leftStart = np.full(len(posvolprofile), xmin+(xmax-xmin)*0.001) + posvolprofile.values
    plt.barh(negvolprofile.index.values, negvolprofile.values, height=0.9*bucket_size, align='center', color='red', alpha=0.45,left=leftStart)
    top_plt.grid(1)
    top_plt.set_ylabel('Closing Price')
    bottom_plt = fig8.add_subplot(gs1[-1, :])
    bottom_plt.bar(data.index, data['neg_volume'],color='red')
    bottom_plt.bar(data.index, data['pos_volume'],color='green')
    bottom_plt.set_xlabel('%s Trading Volume' %ticker)
    bottom_plt.set_ylabel('Volume')
    bottom_plt.grid(1)

    plt.gcf().set_size_inches(11,8)
    if doPDFs: plt.savefig(outdir+'vol_'+ticker+'.pdf')
    plt.savefig(outdir+'vol_'+ticker+'.png')
    if not draw: plt.close()

def CandleStick(data, ticker):
    """ Plot candle stock plot of stock prices along with Bolanger Bands and Keltner ranges
        
         Parameters:
         data - pandas data frame with time plus adj_close price
         ticker - string
                ticker symbol for the stock
    """
    # Extracting Data for plotting
    #data = pd.read_csv('candlestick_python_data.csv')
    df = data.loc[:, ['open', 'high', 'low', 'close','volume']]
    df.columns = ['Open', 'High', 'Low', 'Close','Volume']
    df['UpperB'] = data['BolUpper']        
    df['LowerB'] = data['BolLower']
    df['KeltLower'] = data['KeltLower']
    df['KeltUpper'] = data['KeltUpper']
    df['sma200'] = data['sma200']
    df['sma50'] = data['sma50']
    df['sma20'] = data['sma20']

    if len(df['Open'])<1:
        return
    # Plot candlestick.
    # Add volume.
    # Add moving averages: 3,6,9.
    # Save graph to *.png.
    ap0 = [ mpf.make_addplot(df['UpperB'],color='g',secondary_y=False,alpha=0.5,y_on_right=False),  # uses panel 0 by default
        mpf.make_addplot(df['LowerB'],color='b',secondary_y=False,alpha=0.5,y_on_right=False),  # uses panel 0 by default
        mpf.make_addplot(df['sma200'],color='r',secondary_y=False,alpha=0.5,y_on_right=False),  # uses panel 0 by default        
        mpf.make_addplot(df['KeltLower'],color='darkviolet',secondary_y=False,alpha=0.5,y_on_right=False),  # uses panel 0 by default
        mpf.make_addplot(df['KeltUpper'],color='magenta',secondary_y=False,alpha=0.5,y_on_right=False),  # uses panel 0 by default
        mpf.make_addplot(df['sma50'],color='teal',secondary_y=False,alpha=0.5,y_on_right=False),  # uses panel 0 by default        
        mpf.make_addplot(df['sma20'],color='peru',secondary_y=False,alpha=0.5,y_on_right=False),  # uses panel 0 by default        
      ]
    fig,axes=mpf.plot(df, type='candle', style='charles',
            title=ticker,
            ylabel='Price ($) %s' %ticker,
            ylabel_lower='Shares \nTraded',
            volume=True, 
            mav=(200),
            addplot=ap0,
            returnfig=True) #,
            #savefig=outdir+'test-mplfiance_'+ticker+'.png')
    

        # Configure chart legend and title
    #for 
    axes[0].legend(['Price','Bolanger Up','Bolanger Down','SMA200','Kelt+','Kelt-','SMA50','SMA20'])
    #axes[0].set_title(ticker)
    # Save figure to file
    if doPDFs: fig.savefig(outdir+'test-mplfiance_'+ticker+'.pdf')
    fig.savefig(outdir+'test-mplfiance_'+ticker+'.png')
    techindicators.plot_support_levels(ticker,df,[mpf.make_addplot(df['sma200'],color='r') ],outdir=outdir,doPDF=doPDFs)
    del fig
    del axes
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

def LongTermTrendLine(my_stock,ticker):
    """ Plot 5 year time window
        
         Parameters:
         my_stock      - pandas data frame with time plus adj_close price
         ticker - str - ticker name
    """
    
    FitWithBand(my_stock.index, my_stock  [['adj_close','high','low','open','close']],ticker=ticker,outname='lifetime', poly_order=1)

    if ticker in ['SPY','QQQ','VPU','VYM']:
        FitWithBand(my_stock.index, my_stock  [['adj_close','high','low','open','close']],ticker=ticker,outname='lifetime', poly_order=1)

        # Load the GDP and divide it from SPY
        gdp = pd.read_csv('data/united-states-gdp-gross-domestic-product.csv',delimiter=',')
        gdp['date'] = pd.to_datetime(gdp.date)
        hist=None
        # special longer term look up
        if ticker=='SPY':
            msft = yf.Ticker("^GSPC")
            hist = msft.history(period="max")
            hist.columns = ['open','high','low','close','volume','dividens','splits']
            hist['adj_close']= hist['close']
        else:
            hist = my_stock.copy(True)

        # Draw the longest periods possible
        FitWithBand(hist.index, hist  [['adj_close','high','low','open','close']],ticker=ticker,outname='lifetimev2', poly_order=2)

        # join the gdp info
        hist['mydate'] = pd.to_datetime(hist.index)
        hist['gdp'] = 543.0
        for year in gdp.date.dt.year.unique():
            hist.loc[hist.mydate.dt.year==year,'gdp'] = gdp[gdp.date.dt.year==year][' GDP ( Billions of US $)'].values[0]

        # normalize out by the latest GDP
        hist['gdp']/=hist['gdp'].values[-1]
        
        for h in ['adj_close','high','low','open','close']:
            hist[h]/=hist['gdp']
        FitWithBand(hist.index, hist  [['adj_close','high','low','open','close']],ticker=ticker,outname='POSITION_exchange_lifetimevGDP', poly_order=1)

def getPEShiller():
    URL = 'https://www.multpl.com/shiller-pe/table/by-month'
    filename = '/tmp/shiller.html'
    os.system('wget -q -O %s %s' %(filename,URL))

    table_MN = pd.read_html(filename)
    try:
    
        if len(table_MN)>0:
            if debug: print(table_MN[0])
            table_MN = table_MN[0]
            table_MN.columns = ['Date','P/E10']
            if debug: print(table_MN['Date'])
            table_MN['Date'] = pd.to_datetime(table_MN['Date'],infer_datetime_format=True)#format='%b %d, %Y')
            FitWithBand(table_MN['Date'], table_MN, doMarker=True, ticker='P/E10',outname='', poly_order = 1, price_key='P/E10')
        
    except:
        print('Failed to collect the Shiller P/E10 ratio')
        
def LongTermPlot(my_stock_info_cp,market,ticker,plttext='',ratioName='SPY'):
    print('Long term for ',ticker)
    """ Plot 5 year time window
        
         Parameters:
         my_stock_info - pandas data frame with time plus adj_close price
         market - pandas data frame with the S&P
         ticker - string
                ticker symbol for the stock
         plttext - string
                Label for the plot
    """
    try:
        AddSMA(my_stock_info_cp)
    except ValueError:
        print('cleaning table')
    input_keys = ['adj_close','high','low','open','close','sma200','sma100','sma50','sma20']
    startM = time.time()    
    GetMonthlyReturns(my_stock_info_cp,ticker)
    endM = time.time()
    if debug: print('Process time to process LongTermPlots Monthly returns: %s' %(endM - startM))
    startM = time.time()        
    my_stock_info = my_stock_info_cp.copy(True)
    date_diff = 5*365
    my_stock_info5y = GetTimeSlot(my_stock_info, days=date_diff)
    market5y = GetTimeSlot(market, days=date_diff)
    min_length = min(len(my_stock_info5y),len(market5y))
    max_length = max(len(my_stock_info5y),len(market5y))
    if min_length<max_length:
        my_stock_info5y = my_stock_info5y[-min_length:]
        market5y = market5y[-min_length:]

    try:
        if len(market5y['adj_close'])<1 or len(my_stock_info5y['adj_close'])<1:
            print('Ticker has no adjusted close info: %s' %ticker)
            return
    except Exception as e:
        print(f'error could not load the 5y info...leaving function LongTermPlot with error {e}')
    my_stock_info5y['year5_return']=my_stock_info5y['adj_close']/my_stock_info5y['adj_close'][0]-1
    market5y['year5_return']=market5y['adj_close']/market5y['adj_close'][0]-1
    # comparison to the market
    plt.clf()
    plt.title('5y Return', fontsize=30)
    plt.plot(my_stock_info5y.index,my_stock_info5y['year5_return'],color='blue',label=ticker)    
    plt.plot(market5y.index,     market5y['year5_return'],   color='red', label='SPY')    
    # beautify the x-labels
    plt.gcf().autofmt_xdate()
    plt.ylabel('5 Year Return')
    plt.xlabel('Date')
    plt.legend(loc="upper left")
    if draw: plt.show()
    if doPDFs: plt.savefig(outdir+'longmarket%s_%s.pdf' %(plttext,ticker))
    plt.savefig(outdir+'longmarket%s_%s.png' %(plttext,ticker))
    if not draw: plt.close()

    daily_prices_60d  = GetTimeSlot(my_stock_info, days=60)
    daily_prices_180d = GetTimeSlot(my_stock_info, days=180)
    daily_prices_365d = GetTimeSlot(my_stock_info, days=365)
    daily_prices_3y   = GetTimeSlot(my_stock_info, days=3*365)
    endM = time.time()
    if debug: print('Process time to process LongTermPlots draw: %s' %(endM - startM))
    startM = time.time()
    if len(daily_prices_60d)>10:
        FitWithBand(daily_prices_60d.index, daily_prices_60d [input_keys],ticker=ticker,outname='60d')
        FitWithBand(daily_prices_180d.index,daily_prices_180d[input_keys],ticker=ticker,outname='180d')
        FitWithBand(daily_prices_365d.index,daily_prices_365d[input_keys],ticker=ticker,outname='365d')
        FitWithBand(daily_prices_3y.index,  daily_prices_3y  [input_keys],ticker=ticker,outname='3y')
        FitWithBand(my_stock_info5y.index,  my_stock_info5y  [input_keys],ticker=ticker,outname='5y')
        filter_shift_days=0
        spy_daily_prices_60d  = GetTimeSlot(market, days=60+filter_shift_days)
        spy_daily_prices_365d = GetTimeSlot(market, days=365+filter_shift_days)
        spy_daily_prices_5y   = GetTimeSlot(market, days=5*365+filter_shift_days)
        if len(spy_daily_prices_60d)>0:
            FitWithBand(daily_prices_365d.index,daily_prices_365d[input_keys],
                        ticker=ticker,outname='365dsandpcomparison'+ratioName,spy_comparison = spy_daily_prices_365d[['adj_close','high','low','open','close']],ratioName=ratioName)
            FitWithBand(daily_prices_60d.index,daily_prices_60d[input_keys],
                        ticker=ticker,outname='60dsandpcomparison'+ratioName,spy_comparison = spy_daily_prices_60d[['adj_close','high','low','open','close']],ratioName=ratioName)
            FitWithBand(my_stock_info5y.index,my_stock_info5y[input_keys],
                        ticker=ticker,outname='5ysandpcomparison'+ratioName,spy_comparison = spy_daily_prices_5y[['adj_close','high','low','open','close']],ratioName=ratioName)
        else: print('ERROR missing data for spy')
    else: print('ERROR missing data for ',ticker)        
    endM = time.time()
    if debug: print('Process time to process LongTermPlots bands: %s' %(endM - startM))
def FitWithBand(my_index, arr_prices, doMarker=True, ticker='X',outname='', poly_order = 2, price_key='adj_close',spy_comparison=[],ratioName='SPY'):
    """
    my_index : datetime array
    price : array of prices or values
    doMarker : bool : draw markers or if false draw line
    ticker : str : ticker symbol name
    outname : str : name of histogram to save as
    poly_order : int : order of polynomial to fit
    price_key : str : name of the price to entry to fit
    spy_comparison : array : array of prices to use as a reference. don't use when None
    ratioName : str : ratio stock ticker  
"""
    startBa = time.time()    
    prices = arr_prices[price_key]
    x = mdates.date2num(my_index)
    xx = np.linspace(x.min(), x.max(), min(200,len(arr_prices)))
    dd = mdates.num2date(xx)
    endBa = time.time()
    if debug: print('Process time to process FitWithBand line space: %s' %(endBa - startBa))

    startBa = time.time()
    # prepare a spy comparison
    if len(spy_comparison)>0:
        arr_prices = arr_prices.copy(True)
        spy_comparison = spy_comparison.copy(True)
        for i in [price_key,'high','low','open','close']:
            spy_comparison[i+'_spy'] = spy_comparison[i]
        arr_prices = arr_prices.join(spy_comparison[[price_key+'_spy','high'+'_spy','low'+'_spy','open'+'_spy','close'+'_spy']],how='left')
        prices = arr_prices[price_key]
        prices /= (arr_prices[price_key+'_spy'] / arr_prices[price_key+'_spy'][-1])
        arr_prices.loc[:,'high'] /= (arr_prices.high_spy / arr_prices.high_spy[-1])
        arr_prices.loc[:,'low'] /= (arr_prices.low_spy / arr_prices.low_spy[-1])
        arr_prices.loc[:,'open'] /= (arr_prices.open_spy / arr_prices.open_spy[-1])
    endBa = time.time()
    if debug: print('Process time to process FitWithBand normalization: %s' %(endBa - startBa))

    # perform the fit
    startBa = time.time()
    if len(x)!=len(prices):
        print('Error fitting ',ticker,len(x),len(prices),' ',outname)
        return
    z4 = np.polyfit(x, prices, poly_order)
    p4 = np.poly1d(z4)
    endBa = time.time()
    if debug: print('Process time to process FitWithBand fit: %s' %(endBa - startBa))

    # create an error band
    diff = prices - p4(x)
    stddev = diff.std()

    startBa = time.time()
    pos_count_1sigma = len(list(filter(lambda x: (x >= 0), (abs(diff)-0.5*stddev))))
    pos_count_2sigma = len(list(filter(lambda x: (x >= 0), (abs(diff)-1.0*stddev))))
    pos_count_3sigma = len(list(filter(lambda x: (x >= 0), (abs(diff)-1.5*stddev))))
    pos_count_4sigma = len(list(filter(lambda x: (x >= 0), (abs(diff)-2.0*stddev))))
    pos_count_5sigma = len(list(filter(lambda x: (x >= 0), (abs(diff)-2.5*stddev))))
    endBa = time.time()
    if debug: print('Process time to process FitWithBand bands: %s' %(endBa - startBa))
    startBa = time.time()        
    if len(diff)>0:
        if debug: print('Time period: %s for ticker: %s' %(outname,ticker))
        coverage_txt='Percent covered\n'
        coverage = [100.0*pos_count_1sigma/len(diff) , 100.0*pos_count_2sigma/len(diff),
                        100.0*pos_count_3sigma/len(diff) , 100.0*pos_count_4sigma/len(diff),
                        100.0*pos_count_5sigma/len(diff) ]
        for i in range(0,5):
            if debug: print('Percent outside %i std. dev.: %0.2f' %(i+1,coverage[i]))
            coverage_txt+='%i$\sigma$: %0.1f\n' %(i+1,coverage[i])
    endBa = time.time()
    if debug: print('Process time to process FitWithBand bands array: %s' %(endBa - startBa))

    startBa = time.time()        
    fig, cx = plt.subplots()
    #looks nice but very slow 
    plt.fill_between(dd, p4(xx), p4(xx)+ np.ones(len(dd))*2.0*stddev,
                 color='y', alpha=0.25)
    plt.fill_between(dd, p4(xx), p4(xx)- np.ones(len(dd))*2.0*stddev,
                 color='y', alpha=0.25)
    plt.fill_between(dd, p4(xx), p4(xx)+ np.ones(len(dd))*1.5*stddev,
                 color='y', alpha=0.45)
    plt.fill_between(dd, p4(xx), p4(xx)- np.ones(len(dd))*1.5*stddev,
                 color='y', alpha=0.45)
    plt.fill_between(dd, p4(xx), p4(xx)+ np.ones(len(dd))*1.0*stddev,
                 color='g', alpha=0.25)
    plt.fill_between(dd, p4(xx), p4(xx)- np.ones(len(dd))*1.0*stddev,
                 color='g', alpha=0.25)
    plt.fill_between(dd, p4(xx), p4(xx)+ np.ones(len(dd))*0.5*stddev,
                 color='g', alpha=0.45)
    plt.fill_between(dd, p4(xx), p4(xx)- np.ones(len(dd))*0.5*stddev,
                 color='g', alpha=0.45)

   #linescale=1.0
    #if len(dd)<100:
    #    linescale=10.0
    #cx.errorbar(dd, p4(xx),
    #         np.ones(len(dd))*2.0*stddev,
    #         color='y',
    #         ecolor='y',
    #         alpha=0.05,
    #            elinewidth=linescale*(xx[1]-xx[0]),
    #         #label="4 sigma "
    #                )
    #cx.errorbar(dd, p4(xx),
    #         np.ones(len(dd))*1.5*stddev,
    #         color='y',
    #         ecolor='y',
    #         alpha=0.1,
    #            elinewidth=linescale*(xx[1]-xx[0]),
    #         #label="3 sigma "
    #                )
    #cx.errorbar(dd, p4(xx),
    #         np.ones(len(dd))*1.0*stddev,
    #         marker='.',
    #         color='g',
    #         ecolor='g',
    #         alpha=0.15,
    #         markerfacecolor='b',
    #         #label="2 sigma",
    #         capsize=0,
    #            elinewidth=linescale*(xx[1]-xx[0]),
    #         linestyle='')
    #cx.errorbar(dd, p4(xx),
    #         np.ones(len(dd))*0.5*stddev,
    #         marker='.',
    #         color='g',
    #         ecolor='g',
    #         alpha=0.2,
    #         markerfacecolor='b',
    #            elinewidth=linescale*(xx[1]-xx[0]),
    #         #label="1 sigma",
    #         capsize=0,
    #         linestyle='')
    if poly_order==2:
        cx.plot(dd, p4(xx), '-g',label='Quadratic fit')
    elif poly_order==1:
        cx.plot(dd, p4(xx), '-g',label='Linear fit')
    else:
        cx.plot(dd, p4(xx), '-g',label='Fit')

    if 'high' in arr_prices.columns:
        plt.plot(arr_prices.high,color='red',label='High')
        plt.plot(arr_prices.low,color='cyan',label='Low')
        plt.plot(my_index,arr_prices.open, '+',color='orange',label='Open')

    if  len(spy_comparison)==0 and 'sma200' in arr_prices.columns: 
        plt.plot(arr_prices["sma200"],color='magenta',label='SMA200')
        plt.plot(arr_prices["sma100"],color='cyan',label='SMA100')
        plt.plot(arr_prices["sma50"],color='yellow',label='SMA50')
        plt.plot(arr_prices["sma20"],color='green',label='SMA20')
        #plt.plot(data.index, data["ema13"],color='blue',label='EMA13')
        #print(arr_prices['sma200'])

    if len(spy_comparison)>0:  cx.set_ylabel('Price / '+ratioName)
    elif ticker.count('P/E10'): cx.set_ylabel(ticker)
    else: cx.set_ylabel('Price')
    if 'GDP' in outname:
        cx.set_ylabel(ticker+' /  GDP')
    #cx.set_xlabel('Date')
    
    if doMarker:
        cx.plot(my_index, prices, '+', color='b', label=price_key)
    else:
        plt.plot(prices, label=price_key)  
    plt.title("Fit - mean reversion %s for time period: %s" %(ticker,outname))
    plt.legend()
    plt.text(x.min(), max(prices), coverage_txt, ha='left', wrap=True)
    ticker = ticker.replace('/','_')
    if ticker.count('P_E10'):
        ticker = 'POSITION_exchange_'+ ticker
    if draw: plt.show()
    if doPDFs: fig.savefig(outdir+'meanrev%s_%s.pdf' %(outname,ticker))
    fig.savefig(outdir+'meanrev%s_%s.png' %(outname,ticker))
    if not draw: plt.close()
    endBa = time.time()
    if debug: print('Process time to process FitWithBand', ticker,' drawing: %s' %(endBa - startBa))    
        
def DrawPlots(my_stock_info,ticker,market,plttext='',fullhist=[]):
    """ DrawPlots - Draw all plots of the stock along with market comparisons
        
         Parameters:
         my_stock_info - pandas data frame with time plus adj_close price
         market - pandas data frame with the S&P
         ticker - string
                ticker symbol for the stock
         plttext - string
                Common label for the plot
    """
    #plt.plot(stock_info.index,stock_info['close'])

    if not draw:
        plt.ioff()
    startC = time.time()    
    MakePlotMulti(my_stock_info.index, yaxis=[my_stock_info['adj_close'],my_stock_info['sma50'],my_stock_info['sma200']],colors=['black','green','red'], labels=['Closing','SMA50','SMA200'], xname='Date',yname='Closing price',saveName='price_support%s_%s' %(plttext,ticker), doSupport=True,my_stock_info=my_stock_info,title='Support Lines',draw=draw,doPDFs=doPDFs,outdir=outdir)
    startE = time.time()    
    MakePlot(my_stock_info.index, my_stock_info['copp'], xname='Date',yname='Coppuck Curve',saveName='copp%s_%s' %(plttext,ticker),hlines=[(0.0,'black','-')],title='Coppuck Curve',draw=draw,doPDFs=doPDFs,outdir=outdir)
    if len(fullhist)>0:
        MakePlot(fullhist.index, fullhist['copp'], xname='Date',yname='Coppuck Curve',saveName='copp%s_%s_lifetime' %(plttext,ticker),hlines=[(0.0,'black','-')],title='Coppuck Curve',draw=draw,doPDFs=doPDFs,outdir=outdir)    
    endE = time.time()
    if debug: print('Process time to copp: %s' %(endE - startE))
    MakePlot(my_stock_info.index, my_stock_info['sharpe'], xname='Date',yname='Sharpe Ratio',saveName='sharpe%s_%s' %(plttext,ticker),title='Sharpe Ratio',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(my_stock_info.index, my_stock_info['beta'], xname='Date',yname='Beta',saveName='beta%s_%s' %(plttext,ticker),title='Beta',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(my_stock_info.index, my_stock_info['alpha'], xname='Date',yname='Alpha',saveName='alpha%s_%s' %(plttext,ticker), hlines=[(0.0,'black','-')],title='Alpha',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(my_stock_info.index, my_stock_info['adx'], xname='Date',yname='ADX',saveName='adx%s_%s' %(plttext,ticker), hlines=[(25.0,'black','dotted')],title='ADX',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(my_stock_info.index, my_stock_info['willr'], xname='Date',yname='Will %R',saveName='willr%s_%s' %(plttext,ticker), hlines=[(-20.0,'red','dotted'),(-80.0,'green','dotted')],title='Will %R',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(my_stock_info.index, my_stock_info['ultosc'], xname='Date',yname='Ultimate Oscillator',saveName='ultosc%s_%s' %(plttext,ticker), hlines=[(30.0,'green','dotted'),(70.0,'green','dotted')],title='Ultimate Oscillator',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(my_stock_info.index, my_stock_info['rsquare'], xname='Date',yname='R-squared',saveName='rsquare%s_%s' %(plttext,ticker), hlines=[(0.7,'black','-')],title='R-squared',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(my_stock_info.index, my_stock_info['cmf'], xname='Date',yname='CMF',saveName='cmf%s_%s' %(plttext,ticker), hlines=[(0.2,'green','dotted'),(0.0,'black','-'),(-0.2,'red','dotted')],title='Chaikin Money Flow',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(my_stock_info.index, my_stock_info['mfi_bill_ana'], xname='Date',yname='MFI = 4 is buy',saveName='mfi_bill_ana%s_%s' %(plttext,ticker), hlines=[(4.0,'green','dotted'),(0.0,'black','dotted'),(3.0,'red','dotted')],title='Market Fluctuation index',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(my_stock_info.index, my_stock_info['mfi'], xname='Date',yname='MFI',saveName='mfi%s_%s' %(plttext,ticker), hlines=[(20.0,'green','dotted'),(50.0,'black','-'),(80.0,'red','dotted')],title='Money Flow Index',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(my_stock_info.index, my_stock_info['cci'], xname='Date',yname='Commodity Channel Index',saveName='cci%s_%s' %(plttext,ticker),title='Commodity Channel Index',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(my_stock_info.index, my_stock_info['obv'], xname='Date',yname='On Balanced Volume',saveName='obv%s_%s' %(plttext,ticker),title='On Balanced Volume',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(my_stock_info.index, my_stock_info['force'], xname='Date',yname='Force Index',saveName='force%s_%s' %(plttext,ticker),title='Force Index',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(my_stock_info.index, my_stock_info['bop'], xname='Date',yname='Balance of Power',saveName='bop%s_%s' %(plttext,ticker),  hlines=[(0.0,'black','dotted')],title='Balance of Power',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(my_stock_info.index, my_stock_info['chosc'], xname='Date',yname='Chaikin Oscillator',saveName='chosc%s_%s' %(plttext,ticker),title='Chaikin Oscillator',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlot(my_stock_info.index, my_stock_info['corr14'], xname='Date',yname='14d Correlation with SPY',saveName='corr%s_%s' %(plttext,ticker),hlines=[(0.0,'black','dotted')],title='14d Correlation with SPY',draw=draw,doPDFs=doPDFs,outdir=outdir)

    MakePlotMulti(my_stock_info.index, yaxis=[my_stock_info['macd'],my_stock_info['macdsignal']], colors=['red','blue'], labels=['MACD','Signal'], xname='Date',yname='MACD',saveName='macd%s_%s' %(plttext,ticker),title='MACD',draw=draw,doPDFs=doPDFs,outdir=outdir)
    if 'aroon' in my_stock_info:
        MakePlotMulti(my_stock_info.index, yaxis=[my_stock_info['aroonUp'],my_stock_info['aroonDown']], colors=['red','blue'], labels=['Up','Down'], xname='Date',yname='AROON',saveName='aroon%s_%s' %(plttext,ticker),title='AROON',draw=draw,doPDFs=doPDFs,outdir=outdir)
    if 'jaws' in my_stock_info:
        MakePlotMulti(my_stock_info.index, yaxis=[my_stock_info['adj_close'],my_stock_info['jaws'],my_stock_info['teeth'],my_stock_info['lips']], colors=['black','blue','red','green'], labels=['Closing','Jaws','teeth','lips'], xname='Date',yname='Closing Price',saveName='alligator%s_%s' %(plttext,ticker),title='Alligator',draw=draw,doPDFs=doPDFs,outdir=outdir)
    if 'bullPower' in my_stock_info:
        MakePlotMulti(my_stock_info.index, yaxis=[my_stock_info['bullPower'],my_stock_info['bearPower']], colors=['green','red'], labels=['Bull Power','Bear Power'], xname='Date',yname='Bull/Bear Power',saveName='bullbear%s_%s' %(plttext,ticker),title='Bull/Bear Power',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlotMulti(my_stock_info.index, yaxis=[my_stock_info['adj_close'],my_stock_info['vwap10'],my_stock_info['vwap14'],my_stock_info['vwap20'],my_stock_info['BolLower'],my_stock_info['BolUpper']], colors=['red','blue','green','magenta','cyan','cyan'], labels=['Close Price','VWAP10','VWAP14','VWAP20','VWAPBol-','VWAPBol+'], xname='Date',yname='Price',saveName='vwap10%s_%s' %(plttext,ticker),title='Volume Weighted AP',draw=draw,doPDFs=doPDFs,outdir=outdir)
    MakePlotMulti(my_stock_info.index, yaxis=[my_stock_info['stochK'],my_stock_info['stochD']], colors=['red','blue'], labels=['%K','%D'], hlines=[(80.0,'green','dotted'),(20.0,'red','dotted')], xname='Date',yname='Price',saveName='stoch%s_%s' %(plttext,ticker),title='Stochastic',draw=draw,doPDFs=doPDFs,outdir=outdir)
    endC = time.time()
    if debug: print('Process time to start plots: %s' %(endC - startC))
    startC = time.time()
    # plot volume
    PlotVolume(my_stock_info, ticker)
    # Plot timing indicators
    PlotTiming(my_stock_info, ticker)
    endC = time.time()
    if debug: print('Process time to volume: %s' %(endC - startC))
    
    # plot the zigzag
    start = time.time()
    if len(my_stock_info.adj_close)>1:
        plot_pivots(my_stock_info.index, my_stock_info.adj_close, saveName='zigzag%s_%s' %(plttext,ticker), xname='Date', yname='Closing Price')
    end = time.time()
    if debug: print('Process time to find pivots: %s' %(end - start))
    startC = time.time()        
    # plot Ichimoku Cloud
    plt.cla()
    # Plot closing price and parabolic SAR
    komu_cloud = my_stock_info[['adj_close','SAR']].plot()
    plt.ylabel('Price')
    plt.xlabel('Date')
    komu_cloud.fill_between(my_stock_info.index, my_stock_info.senkou_spna_A, my_stock_info.senkou_spna_B,
    where=my_stock_info.senkou_spna_A >= my_stock_info.senkou_spna_B, color='lightgreen')
    komu_cloud.fill_between(my_stock_info.index, my_stock_info.senkou_spna_A, my_stock_info.senkou_spna_B,
    where=my_stock_info.senkou_spna_A < my_stock_info.senkou_spna_B, color='lightcoral')
    plt.grid(True)
    plt.legend()
    if draw: plt.show()
    if doPDFs: plt.savefig(outdir+'komu%s_%s.pdf' %(plttext,ticker))
    plt.savefig(outdir+'komu%s_%s.png' %(plttext,ticker))
    if not draw: plt.close()
    
    # comparison to the market
    plt.plot(my_stock_info.index,my_stock_info['yearly_return'],color='blue',label=ticker)    
    plt.plot(market.index,     market['yearly_return'],   color='red', label='SPY')    
    # beautify the x-labels
    plt.gcf().autofmt_xdate()
    plt.ylabel('Yearly Return')
    plt.xlabel('Date')
    plt.legend(loc="upper left")
    plt.title('Yearly Return',fontsize=30)
    if draw: plt.show()
    if doPDFs: plt.savefig(outdir+'market%s_%s.pdf' %(plttext,ticker))
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
    if doPDFs: plt.savefig(outdir+'monthlymarket%s_%s.pdf' %(plttext,ticker))
    plt.savefig(outdir+'monthlymarket%s_%s.png' %(plttext,ticker))
    if not draw: plt.close()
    endC = time.time()
    if debug: print('Process time to draw monthy: %s' %(endC - startC))        
    startC = time.time()        
    CandleStick(my_stock_info,ticker)
    endC = time.time()
    if debug: print('Process time to candlestick: %s' %(endC - startC))    
    # collect all of the chart signals
    chartSignals = []
    if len(my_stock_info)>0:
        for col in my_stock_info.columns:
            if 'CDL' in col:
                if my_stock_info[col][-1]>0:
                    chartSignals+=[[col[3:],1,0,0]]
                    if debug: print('%s signal buy: %s' %(col,ticker))
                    if col.count('CDLABANDONEDBABY'):  print('%s Abandoned Baby by signal: %s' %(col,ticker))
                if my_stock_info[col][-2]>0:
                    if debug: print('%s signal buy 2days ago: %s' %(col,ticker))
                    chartSignals+=[[col[3:],0,1,0]]
                if my_stock_info[col][-5:].sum()>0:
                    if debug: print('%s signal buy in last 5 days: %s' %(col,ticker))
                    chartSignals+=[[col[3:],0,0,1]]
    return chartSignals
        #if my_stock_info['CDLHAMMER'][-1]>0:
        #    print('Abandoned baby signal buy: %s' %ticker)
    
def SARTradingStategy(stock):
    """ SARTradingStategy - Back testing of the SAR trading model. Shows the cumulative return from the strategy
        
         Parameters:
         stock - pandas data frame with time plus adj_close price
    """
    # Trade strategy from SAR
    stock['signal'] = 0
    stock.loc[(stock.close > stock.senkou_spna_A) & (stock.close >stock.senkou_spna_B) & (stock.close > stock.SAR), 'signal'] = 1
    stock.loc[(stock.close < stock.senkou_spna_A) & (stock.close < stock.senkou_spna_B) & (stock.close < stock.SAR), 'signal'] = -1
    stock['signal'].value_counts()
    # Calculate daily returns
    daily_returns = stock.Close.pct_change()
    # Calculate strategy returns
    strategy_returns = daily_returns *stock['signal'].shift(1)
    # Calculate cumulative returns
    (strategy_returns+1).cumprod().plot(figsize=(10,5))
    # Plot the strategy returns
    plt.xlabel('Date')
    plt.ylabel('Strategy Returns (%)')
    plt.grid()
    plt.show()
        
#api = ALPACA_REST()
ts = ALPHA_TIMESERIES()
#from alpaca_trade_api.rest import TimeFrame
#import pytz
#import datetime
#est = pytz.timezone('US/Eastern')
#filter_shift_days = 0
#today = datetime.datetime.now(tz=est) #+ datetime.timedelta(minutes=5)
#todayFilter = (today + datetime.timedelta(days=-1*filter_shift_days))
#d1 = todayFilter.strftime("%Y-%m-%dT%H:%M:%S-05:00")
#thirty_days = (todayFilter + datetime.timedelta(days=-720)).strftime("%Y-%m-%dT%H:%M:%S-05:00")
#spy = runTicker(api,'SPY',timeframe=TimeFrame.Hour,start=thirty_days,end=d1)
#print(GetMidAirRefuel(spy)[['high','low']])
ticker='TSLA'
#ticker='TSLA'
stock_info=None
spy=None
sqlcursor = SQL_CURSOR()
j=0
spy,j = ConfigTable('SPY', sqlcursor,ts,readType,j, hoursdelay=15)
gld,j = ConfigTable('GLD', sqlcursor,ts,readType,j, hoursdelay=15)
slv,j = ConfigTable('SLV', sqlcursor,ts,readType,j, hoursdelay=15)
labu,j = ConfigTable('LABU', sqlcursor,ts,readType,j, hoursdelay=15)
labd,j = ConfigTable('LABD', sqlcursor,ts,readType,j, hoursdelay=15)
bib,j = ConfigTable('BIB', sqlcursor,ts,readType,j, hoursdelay=15)
gush,j = ConfigTable('GUSH', sqlcursor,ts,readType,j, hoursdelay=15)
drip,j = ConfigTable('DRIP', sqlcursor,ts,readType,j, hoursdelay=15)
print('spy')
#print(spy.to_string())
print(spy)
print(GetMidAirRefuel(spy))
#if loadFromPickle and os.path.exists("%s.p" %ticker):
#    stock_info = pickle.load( open( "%s.p" %ticker, "rb" ) )
#    #spy = pickle.load( open( "SPY.p", "rb" ) )
#    #spy.to_sql('SPY',sqlcursor,if_exists='append',index=True)
#else:
#    #stock_info = runTicker(api,ticker)
#    stock_info=runTickerAlpha(ts,ticker,readType)
#    spy=runTickerAlpha(ts,'SPY',readType)
#    pickle.dump( spy, open( "SPY.p", "wb" ) )
#    pickle.dump( stock_info, open( "%s.p" %ticker, "wb" ) )
# add info
if len(spy)==0:
    print('ERROR - empy info %s' %ticker)
spy['daily_return']=spy['adj_close'].pct_change(periods=1)
try:
    spy = AddInfo(spy, spy)
except ValueError:
    print('cleaning table')
    sqlcursor.cursor().execute('DROP TABLE SPY')
    spy,j = ConfigTable('SPY', sqlcursor,ts,readType, hoursdelay=15)
    spy = AddInfo(spy, spy)
spy_1year = GetTimeSlot(spy)
DrawPlots(spy_1year,'SPY',spy_1year,fullhist=spy)
n_ALPHA_PREMIUM_WAIT_ITER = IS_ALPHA_PREMIUM_WAIT_ITER()
j=0
cdir = os.getcwd()

# Generate global market plots
if not args.skip:
    GLOBAL_MARKET_PLOTS(outdir,j)
    os.chdir(outdir)
    b.makeHTML('GLOBAL.html' ,'GLOBAL',filterPattern='*_GLOBAL',describe='Global market metrics')
    os.chdir(cdir)
    
getPEShiller()
try:
    POS_MARKET_PLOTS(outdir,debug,doPDFs,spy=spy)
except:
    print('could not do position market plots')
os.chdir(outdir)
b.makeHTML('POSITION.html' ,'POSITION',filterPattern='*POSITION_exchange_*',describe='Position of stocks relative to moving averages')
os.chdir(cdir)    

# Run individual stocks
if doStocks:
    runList =  b.stock_list
    if args.filter!='':
        runList+=[[args.filter,0,0,'NYSE','']]
    if args.add!='':
        addt = args.add.split(',')
        runList=[]        
        for at in addt:
            runList+=[[at,0,0,'NYSE','']]
    for s in runList:
        startT = time.time()
        if args.filter!='':
            if s[0]!=args.filter:
                continue
        #if s[0]=='SPY':
        #    continue
        if s[0].count('^'):
            continue
        if j%n_ALPHA_PREMIUM_WAIT_ITER==0 and j!=0:
            time.sleep(56)
        print('making plots: ',s[0])
        sys.stdout.flush()

        startR = time.time()
        tstock_info,j=ConfigTable(s[0], sqlcursor,ts,readType, j, hoursdelay=15)
        endR = time.time()
        if debug: print('Process time to read SQL: %s' %(endR - startR))
        
        if len(tstock_info)==0:
            continue
        # shorten the info
        #tstock_info = GetTimeSlot(tstock_info, days=6*365)
        try:
            # draw before we shorten this to 1 year
            startL = time.time()
            LongTermPlot(tstock_info,spy,ticker=s[0])
            LongTermTrendLine(tstock_info,ticker=s[0])
            endL = time.time()
        except (ValueError,KeyError,NotImplementedError) as e:
            print("Testing multiple exceptions. {}".format(e.args[-1]))            
            print('Error processing %s' %(s[0]))
            #clean up
            print('Removing: ',s[0])
            sqlcursor.cursor().execute('DROP TABLE %s' %s[0])
            j+=1
            continue            
        if debug: print('Process time to add long term info: %s' %(endL - startL))
        if s[0] in ['SPY','SLV','GLD' ]:
            LongTermPlot(tstock_info,gld,ticker=s[0],ratioName='GLD')
            LongTermPlot(tstock_info,slv,ticker=s[0],ratioName='SLV')
        if s[0] in ['LABD' ]:
            LongTermPlot(tstock_info,bib,ticker=s[0],ratioName='BIB')
            LongTermPlot(tstock_info,labu,ticker=s[0],ratioName='LABU')
        if s[0] in ['LABU' ]:
            LongTermPlot(tstock_info,bib,ticker=s[0],ratioName='BIB')
            LongTermPlot(tstock_info,labd,ticker=s[0],ratioName='LABD')
        if s[0] in ['BIB' ]:
            LongTermPlot(tstock_info,labd,ticker=s[0],ratioName='LABD')
            LongTermPlot(tstock_info,labu,ticker=s[0],ratioName='LABU')            
        if s[0] in ['GUSH' ]:
            LongTermPlot(tstock_info,drip,ticker=s[0],ratioName='DRIP')
        if s[0] in ['DRIP' ]:
            LongTermPlot(tstock_info,gush,ticker=s[0],ratioName='GUSH')            
        #if j>2:
        #    break
        #try:
        #    if loadFromPickle and os.path.exists("%s.p" %s[0]):
        #        start = time.time()
        #        tstock_info = pickle.load( open( "%s.p" %s[0], "rb" ) )
        #        tstock_info.to_sql(s[0],sqlcursor,if_exists='append',index=True)
        #        end = time.time()
        #        if debug: print('Process time to load file: %s' %(end - start))
        #    else:
        #        tstock_info=runTickerAlpha(ts,s[0],readType)
        #        pickle.dump( tstock_info, open( "%s.p" %s[0], "wb" ) )
        #        tstock_info.to_sql(s[0],sqlcursor,if_exists='append',index=True)
        #        j+=1
        #except ValueError:
        #    print('ERROR processing...ValueError %s' %s[0])
        #    j+=1
        #    continue
        print(tstock_info)
        try:
            start = time.time()
            tstock_info = AddInfo(tstock_info, spy, debug=debug)
            end = time.time()
            if debug: print('Process time to add info: %s' %(end - start))
        except (ValueError,KeyError,NotImplementedError) as e:
            print("Testing multiple exceptions. {}".format(e.args[-1]))            
            print('Error processing %s' %(s[0]))
            #clean up
            print('Removing: ',s[0])
            sqlcursor.cursor().execute('DROP TABLE %s' %s[0])
            j+=1
            continue

        tstock_info_hist = copy.deepcopy(tstock_info)
        tstock_info = GetTimeSlot(tstock_info) # gets the one year timeframe
        start = time.time()
        chartSignals =DrawPlots(tstock_info,s[0],spy_1year,fullhist=tstock_info_hist)
        if len(chartSignals)>0.0:
            chartSignals = pd.DataFrame(chartSignals,columns=['Chart Signal', 'Yesterday','Two Days Ago','In Last 5 days'])
            chartSignals = chartSignals.groupby(chartSignals['Chart Signal']).sum().reset_index()

        end = time.time()
        if debug: print('Process time to add draw: %s' %(end - start))
        print('Process time to add process: %s' %(end - startT))        
        os.chdir(outdir)
        b.makeHTML('%s.html' %s[0],s[0],filterPattern='*_%s' %s[0],describe=s[4], chartSignals=chartSignals)
        os.chdir(cdir)    
        del tstock_info;
if doETFs:
    j=0
    for s in b.etfs:
        if s[0].count('^'):
            continue
        if j%n_ALPHA_PREMIUM_WAIT_ITER==0 and j!=0:
            time.sleep(56)
        print(s[0])
        sys.stdout.flush()
        estock_info=None
        estock_info,j=ConfigTable(s[0], sqlcursor,ts,readType, j, hoursdelay=15)
        if len(estock_info)==0:
            continue
        #try:
        #    if loadFromPickle and os.path.exists("%s.p" %s[0]):
        #        start = time.time()
        #        estock_info = pickle.load( open( "%s.p" %s[0], "rb" ) )
        #        estock_info.to_sql(s[0],sqlcursor,if_exists='append',index=True)
        #        end = time.time()
        #        if debug: print('Process time to load file: %s' %(end - start))
        #    else:
        #        estock_info=runTickerAlpha(ts,s[0],readType)
        #        pickle.dump( estock_info, open( "%s.p" %s[0], "wb" ) )
        #        estock_info.to_sql(s[0],sqlcursor,if_exists='append',index=True)
        #        j+=1
        #except ValueError:
        #    print('ERROR processing...ValueError %s' %s[0])
        #    j+=1
        #    continue
        try:        
            LongTermPlot(estock_info,spy,ticker=s[0])
            LongTermTrendLine(estock_info,ticker=s[0])

            if s[0] in ['SPY','SLV','GLD' ]:
                LongTermPlot(estock_info,gld,ticker=s[0],ratioName='GLD')
                LongTermPlot(estock_info,slv,ticker=s[0],ratioName='SLV')
            if s[0] in ['LABD' ]:
                LongTermPlot(estock_info,bib,ticker=s[0],ratioName='BIB')
                LongTermPlot(estock_info,labu,ticker=s[0],ratioName='LABU')
            if s[0] in ['LABU' ]:
                LongTermPlot(estock_info,bib,ticker=s[0],ratioName='BIB')
                LongTermPlot(estock_info,labd,ticker=s[0],ratioName='LABD')
            if s[0] in ['BIB' ]:
                LongTermPlot(estock_info,labd,ticker=s[0],ratioName='LABD')
                LongTermPlot(estock_info,labu,ticker=s[0],ratioName='LABU')            
            if s[0] in ['GUSH' ]:
                LongTermPlot(estock_info,drip,ticker=s[0],ratioName='DRIP')
            if s[0] in ['DRIP' ]:
                LongTermPlot(estock_info,gush,ticker=s[0],ratioName='GUSH') 
        

            start = time.time()
            estock_info = AddInfo(estock_info, spy)
            end = time.time()
            if debug: print('Process time to add info: %s' %(end - start))
        except (ValueError,KeyError,NotImplementedError) as e:
            print("Testing multiple exceptions. {}".format(e.args[-1]))            
            print('Error processing %s' %s[0])
            #clean up
            print('Removing: ',s[0])
            sqlcursor.cursor().execute('DROP TABLE %s' %s[0])
            continue
        start = time.time()
        estock_info = GetTimeSlot(estock_info) # gets the one year timeframe
        end = time.time()
        if debug: print('Process time to get time slot: %s' %(end - start))
        start = time.time()
        DrawPlots(estock_info,s[0],spy_1year)
        end = time.time()
        if debug: print('Process time to draw plots: %s' %(end - start))
        os.chdir(outdir)
        b.makeHTML('%s.html' %s[0],s[0],filterPattern='*_%s' %s[0],describe=s[4],linkIndex=0)
        os.chdir(cdir)
        del estock_info

# -*- coding: utf-8 -*-
"""
* Updated on 2020/03/20
* python3
"""
import pandas as pd
import numpy as np

#find next buy or sell point
def singleBuySellPoint(df_short, df_long, status, startDate, endDate, df_behavior = pd.DataFrame()):
	df_bs = pd.DataFrame()
	df_bs['short'] = df_short
	df_bs['long'] = df_long
	df_bs.dropna(inplace=True)
	if df_behavior.empty:
		df_bs['behavior'] = np.nan
	else:
		df_bs['behavior'] = df_behavior['behavior']
	df_bs = df_bs[startDate:]
	df_bs['gt_mark'] = df_bs.iloc[:,0] > df_bs.iloc[:,1]
	if status == 'nonholder':
		df_bs['bs_mark'] = 'B'
		df_bs['behavior'] = df_bs['bs_mark'].where((df_bs['gt_mark'] == True) & (df_bs['gt_mark'].shift(1) == False))
		df_bs.dropna(subset=['behavior'],inplace=True)
		if len(df_bs.index) > 0:
			behaviorDate = df_bs.index[0]
			status = 'holder'
			df_temp = df_bs.head(1)
		else:
			behaviorDate = endDate
			df_temp = pd.DataFrame()
	elif status == 'holder':
		df_bs['bs_mark'] = 'S'
		df_bs['behavior'] = df_bs['bs_mark'].where((df_bs['gt_mark'] == False) & (df_bs['gt_mark'].shift(1) == True))
		df_bs.dropna(subset=['behavior'],inplace=True)
		if len(df_bs.index) > 0:
			behaviorDate = df_bs.index[0]
			status = 'nonholder'
			df_temp = df_bs.head(1)
		else:
			behaviorDate = endDate
			df_temp = pd.DataFrame()
	if behaviorDate > endDate:
		behaviorDate = endDate
		df_temp = pd.DataFrame()
	df_behavior = pd.concat([df_behavior,df_temp])
	return status, behaviorDate, df_behavior

# find all buy-sell points in a period
def allBuySellPoints(df_short, df_long, status, startDate, endDate, df_behavior = pd.DataFrame()):
	if startDate < df_short.index.min(): startDate = df_short.index.min()
	if endDate > df_short.index.max(): endDate = df_short.index.max()
	if df_behavior.empty:
		status, startDate, df_behavior = singleBuySellPoint(df_short, df_long, status, startDate, endDate)
	else:
		status, startDate, df_behavior = singleBuySellPoint(df_short, df_long, status, startDate, endDate, df_behavior)
	if startDate < endDate:
		return allBuySellPoints(df_short, df_long, status, startDate, endDate, df_behavior)
	else:
		return df_behavior.drop(['short', 'long', 'behavior'], axis=1)

#query the company name and IPO date based on stock code
def query(code,url):
	merge = pd.read_csv(url)
	#response = merge[merge['公司代码'].str.match(code)]
	response = merge[merge.iloc[:,0].str.match(code)]
	#print(code,url)
	#print(response)
	info = {'code':code,
					'name':response.iloc[0,1],
					'ipoDate':response.iloc[0,2]}
	return info
def queryStock(code):
	url = 'https://raw.githubusercontent.com/longavailable/datarepo02/master/data/stock/stocks.list'
	return query(code,url)
def queryFund(code):
	url = 'https://raw.githubusercontent.com/longavailable/datarepo02/master/data/stock/funds.list'
	return query(code,url)
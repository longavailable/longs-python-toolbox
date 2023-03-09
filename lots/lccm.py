# -*- coding: utf-8 -*-
"""
* Updated on 2020/07/31
* python3
"""

#from .longsgee import *			#import functions for gee
#from .longspyfuncs import *	#import general functions
from .gee import *
from .util import *

try:
	import ee; ee.Initialize()
except:
	proxy()		# set a proxy for 'earthengineapi'
	import ee; ee.Initialize()
import pandas as pd
import numpy as np
import ast, math, pathlib, time, traceback

#published personal function
from longscurvefitting import queryModel

def queryModelnameParameters(lcType0, lcType1, percentile, gbtcFile):
	'''Query the modelname and parameters from GBTC (global builtup-transition curves).

	Parameters:
		lcType0: the landuse / landcover type from
			Type: integer
		lcType1: the landuse / landcover type to
			Type: integer
		percentile: one of ['min', '25%', '50%', '75%', 'max']
			Type: string
		gtbcFile: the filename of GBTC
			Type: string, pathlib.Path object
	Returns:
		modelname: queryed model (modelname)
			Type: string
		paras:
			Type: list
	'''
	dataFile = pathlib.Path(gbtcFile)
	data_gbtc = pd.read_csv(dataFile)
	expr = 'type0==%d and type1==%d and percentile=="%s"' % (lcType0, lcType1, percentile)
	data_part = data_gbtc.query(expr)
		
	#get model and parameter
	modelname = data_part['modelname'].iloc[0]
	paras = ast.literal_eval(data_part['parameters'].iloc[0])
	return modelname, paras

def interpolateGBTC(builtupArea, builtupArea_reference, transitionRate_reference, lcType0, lcType1, gbtcFile):
	'''Query builtup-transition curve from GBTC (global builtup-transition curves).

	Parameters:
		builtupArea: the area to interpolate
			Type: float
		builtupArea_reference: the area refered to query
			Type: float
		transitionRate_reference: the transition rate refered to query
			Type: float
		lcType0, lcType1, gbtcFile: see function `queryModelnameParameters`.
	Returns:
		interpolated transition rate corresponding to "builtupArea"
			Type: float
	'''
	xdata = np.array([builtupArea, builtupArea_reference])
	percentiles = ['min', '25%', '50%', '75%', 'max']
	trba_perc = []	#trba_perc, transition rates of percentiles at spot of `builtupArea`
	trbar_perc = []	#trbar_perc, transition rates of percentiles at spot of `builtupArea_reference`
	for percentile in percentiles:
		modelname, paras = queryModelnameParameters(lcType0=lcType0, lcType1=lcType1, percentile=percentile, gbtcFile=gbtcFile)
		model = queryModel(modelname)
		transition = model(xdata, *paras)
		trba_perc.append(min(max(transition[0],0),1))	#reasonability setting -- between 0 and 1
		trbar_perc.append(min(max(transition[1],0),1))
	
	#reasonability setting 2 -- non-decreasing
	for i in range(4):
		if trbar_perc[i] > trbar_perc[i+1]: trbar_perc[i+1] = trbar_perc[i]
		if trba_perc[i] > trba_perc[i+1]: trba_perc[i+1] = trba_perc[i]
	
	#overbounds
	if transitionRate_reference <= trbar_perc[0]:
		print('Warning - "transitionRate_reference" was less than "min" percentile, then replace by "min" percentile')
		return trba_perc[0]
	elif transitionRate_reference >= trbar_perc[-1]:
		print('Warning - "transitionRate_reference" was great than "max" percentile, then replace by "max" percentile')
		return trba_perc[-1]
	#approximation
	for i in range(5):
		if math.isclose(trbar_perc[i], transitionRate_reference, rel_tol=0.05):
			return trba_perc[i]
	#middle
	for i in range(4):
		if trbar_perc[i] < transitionRate_reference < trbar_perc[i+1]:
			ratio = ( transitionRate_reference - trbar_perc[i] ) / (trbar_perc[i+1] - trbar_perc[i])
			return trba_perc[i] + ratio * (trba_perc[i+1] - trba_perc[i])

def generateUrbanSubregions(eeImage, urbanPiexelValue, scale=100, region=None, areaThreshold=1e7, bufferDistance=5000, mark='urban'):
	'''Generate urban subregions from source image.
	
	Note that `area` property of returned `urbanSubregions` is the area of builtup inside, NOT the buffered urban.
	
	Parameters:
		eeImage: source image
			Type: ee.Image object
		urbanPiexelValue: the pixel value for urban type
			Type: integer, float
		scale, region: see `vectorize` function
		areaThreshold: the threshold for builtup area
			Type: integer, float
			Default: 1e7
		bufferDistance: the buffer distance to expand the builtup areas
			Type: integer
			Default: 5000
		mark: a `lc_type` mark property
			Type: string
			Default: 'urban'
	Returns:
		urbanSubregions: expanded builtup areas as urban subregions
			Type: ee.FeatureCollection object
	'''
	#vectorize builtup type (3)
	urban_featColl = vectorize(eeImage, pixelValue=urbanPiexelValue, scale=scale, region=region, addAreaProperty=True, areaThreshold=areaThreshold)

	#add bufferZones and make a reasonability check
	#keys: 1) union if intersected, 2) not break bounds, 3) builtup area based on the original `urban_featColl`
	urbanSubregions = ( multigeometryToFeatureCollection(urban_featColl.geometry().buffer(bufferDistance).intersection(region))
		.map(lambda f: f.set({'area': f.geometry().intersection(urban_featColl.geometry()).area(1e3), 'lc_type':mark}))	)
	return urbanSubregions

def featCollTransitionMatrix(eeImage0, eeImage1, eeFeatColl, scale=30, additional=None, upperLevelSubregion=None):
	'''A non-general transitionMatrix calculator for ee.FeatureCollection.
	
	Parameters:
		eeImage0: initial image
			Type: ee.Image object
		eeImage1: final image
			Type: ee.Image object
		eeFeatColl:
			Type: ee.FeatureCollection
		scale: a nominal scale in meters of the projection to work in.
			Type: float
			Default: 30
		additional: add additional key-value pairs to results
			Type: dictionary
			Default: None
		upperLevelSubregion:
			Type: ee.FeatureCollection
			Default: None
	Returns:
		List of dictionaries
	'''
	len = eeFeatColl.size().getInfo()
	transitions = []
	for i in range(len):
		feature = getFeatureByIndex(eeFeatColl, i)
		geometry = feature.geometry()
		#non-general practice
		if not upperLevelSubregion:
			#ydm urban case
			additional.update({'builtupArea':feature.get('area').getInfo()}) #non-general practice
		else:
			#ydm nonurban case
			mark_sr = ee.Feature(upperLevelSubregion.filterBounds(geometry.buffer(-5000)).first()).get('code').getInfo()
			additional.update({'code':mark_sr})
		re = transitionMatrix(eeImage0, eeImage1, geometry=geometry, scale=scale, additional=additional)
		transitions = transitions + re
	return transitions

def historicalUrbanTransitionRate(startYear, endYear, typePairs, deltaYear=5,  region=None, builtupAreaPieces=None, 
	filenameUrban=None, filenameUrbanPiece=None, redo=False):
	'''Calculate historical transition rates for urban subregions.
	
	Parameters:
		startYear: initial year
			Type: integer
		endYear: final year
			Type: integer
		typePairs: type pairs of land use/cover types
			Type: list of set
		deltaYear:
			Type: integer
			Default: 5
		region: 
			Type: ee.Geometry object
			Default: None
		builtupAreaPieces: if None, won't make a further processing
			Type: list
			Default: None
		filenameUrban: file to save output of all transitions
			Type: string
			Default: None
		filenameUrbanPiece: file to save output of further processing
			Type: string
			Default: None
		redo: if file of `filenameUrban` exists and redo is `False`, then skip calculating of transition rates (this process cost too much)
			Type: boolean
			Default: False
	Returns:
		None
	'''
	endYear = endYear - deltaYear + 1
	filenameUrban = filenameUrban if filenameUrban else 'urban_transitions_all.csv'
	filenameUrban = pathlib.Path(filenameUrban)
	filecheck = fileIsValid(filenameUrban)
	if filecheck and not redo:
		pass
	elif filecheck and redo:
		filenameUrban.rename(pathlib.Path(str(filenameUrban).replace('.csv', '_bak%s.csv' % str(int(time.time()*1e6)))))
	else:
		filenameUrban.parent.mkdir(parents=True, exist_ok=True)
		redo = True
	
	if redo:
		for year in range(startYear, endYear):
			year0, year1 = year, year + deltaYear
			assetId0 = 'users/XiaolongLiu/mega/cn/ydm/ydm_esa/ydm_esa_%d' % year0
			assetId1 = 'users/XiaolongLiu/mega/cn/ydm/ydm_esa/ydm_esa_%d' % year1
			image0 = ee.Image(assetId0)
			image1 = ee.Image(assetId1)
			
			#generate urban subregions
			assetId_usr = 'users/XiaolongLiu/mega/cn/ydm/lccm/ydm_urban_subregion_%d' % year0
			if not ee.data.getInfo(assetId_usr): 
				urban_sr = generateUrbanSubregions(image0, urbanPiexelValue=3, scale=100, region=region)
				downUpload2Asset(urban_sr, assetId_usr, overwrite=True, wait=True)
			urban_sr = ee.FeatureCollection(assetId_usr)
			
			#calculate transition rates
			properties = {'year0':year0, 'year1':year1}
			re = featCollTransitionMatrix(image0, image1, urban_sr, scale=30, additional=properties)
			#export
			writeLogsDicts2csv(filenameUrban, re)
		
	#further process
	filenameUrbanPiece = filenameUrbanPiece if filenameUrbanPiece else 'urban_transitions_piecewise.csv'
	filenameUrbanPiece = pathlib.Path(filenameUrbanPiece)
	if fileIsValid(filenameUrbanPiece):
		filenameUrbanPiece.rename(pathlib.Path(str(filenameUrbanPiece).replace('.csv', '_bak%s.csv' % str(int(time.time()*1e6)))))
	filenameUrbanPiece.parent.mkdir(parents=True, exist_ok=True)
	if builtupAreaPieces:
		data = pd.read_csv(filenameUrban)
		pieces = []
		for i in range(len(builtupAreaPieces)-1):
			area0, area1 = builtupAreaPieces[i], builtupAreaPieces[i+1]
			
			#calculate mean builtup area
			expr_area = 'builtupArea>=%s and builtupArea<%s' % (area0, area1)
			area = data.query(expr_area).mean()['builtupArea']
			piece = {'builtupArea': area}
			
			#calculate mean transition rate for each typePair
			for typePair in typePairs:
				type0, type1 = typePair
				typePair_string = '%d-%d' %(type0,type1)
				#filter -- type-pair, builtup area
				expr = ( 'type0==%d and type1==%d and builtupArea>=%s and builtupArea<%s' 
					% (type0, type1, area0, area1) )
				rate = data.query(expr).mean()['proportion']
				piece_current = {typePair_string: rate}
				piece.update(piece_current)
			pieces.append(piece)
		#export
		writeLogsDicts2csv(filenameUrbanPiece, pieces)
		
def historicalNonurbanTransitionRate(startYear, endYear, typePairs, deltaYear=5, region=None,
	upperLevelSubregion=None,	filenameNonurban=None, filenameNonurbanMean=None, redo=False):
	'''Calculate historical transition rates for nonurban subregions.
	
	Parameters:
		startYear: initial year
			Type: integer
		endYear: final year
			Type: integer
		typePairs: type pairs of land use/cover types
			Type: list of set
		deltaYear:
			Type: integer
			Default: 5
		region: 
			Type: ee.Geometry object
			Default: None
		upperLevelSubregion: subregion level 2 
			Type: ee.FeatureCollection object
			Default: None
		filenameNonurban: file to save output of all transitions
			Type: string
			Default: None
		filenameNonurbanMean: file to save output of further processing
			Type: string
			Default: None
		redo: if file of `filenameNonurban` exists and redo is `False`, then skip calculating of transition rates (this process cost too much)
			Type: boolean
			Default: False
	Returns:
		None
	'''
	endYear = endYear - deltaYear + 1
	filenameNonurban = filenameNonurban if filenameNonurban else 'nonurban_transitions_all.csv'
	filenameNonurban = pathlib.Path(filenameNonurban)
	filecheck = fileIsValid(filenameNonurban)
	if filecheck and not redo:
		pass
	elif filecheck and redo:
		filenameNonurban.rename(pathlib.Path(str(filenameNonurban).replace('.csv', '_bak%s.csv' % str(int(time.time()*1e6)))))
	else:
		filenameNonurban.parent.mkdir(parents=True, exist_ok=True)
		redo = True
	
	if redo:
		for year in range(startYear, endYear):
			year0, year1 = year, year + deltaYear
			assetId0 = 'users/XiaolongLiu/mega/cn/ydm/ydm_esa/ydm_esa_%d' % year0
			assetId1 = 'users/XiaolongLiu/mega/cn/ydm/ydm_esa/ydm_esa_%d' % year1
			image0 = ee.Image(assetId0)
			image1 = ee.Image(assetId1)
			
			assetId_nsr = 'users/XiaolongLiu/mega/cn/ydm/lccm/ydm_nonurban_subregion_%d' % year0
			if not ee.data.getInfo(assetId_nsr):
				#generate urban subregions -- base of nonurban / unincluded subregions
				assetId_usr = 'users/XiaolongLiu/mega/cn/ydm/lccm/ydm_urban_subregion_%d' % year0
				if not ee.data.getInfo(assetId_usr): 
					urban_sr = generateUrbanSubregions(image0, urbanPiexelValue=3, scale=100, region=region)
					downUpload2Asset(urban_sr, assetId_usr, overwrite=True, wait=True)
				urban_sr = ee.FeatureCollection(assetId_usr)
				
				#generate nonurban subregions
				featColl_scr = ee.FeatureCollection(upperLevelSubregion) if upperLevelSubregion else ee.FeatureCollection(region)
				nonurban_sr = ( featColl_scr.map(lambda f: ee.Feature(f.geometry().difference(urban_sr.geometry())))
					.map(lambda f: f.set({'area':f.area(1e3), 'lc_type':'nonurban'})) )
				downUpload2Asset(nonurban_sr, assetId_nsr, overwrite=True, wait=True)
			nonurban_sr = ee.FeatureCollection(assetId_nsr)
			
			#calculate transition rates
			properties = {'year0':year0, 'year1':year1}
			re = featCollTransitionMatrix(image0, image1, nonurban_sr, scale=30, additional=properties, upperLevelSubregion=upperLevelSubregion)
			#export
			writeLogsDicts2csv(filenameNonurban, re)
	
	#further process
	if not upperLevelSubregion:
		#single output
		data = pd.read_csv(filenameNonurban)
		transitions = []
		for typePair in typePairs:
			type0, type1 = typePair
			typePair_string = '%d-%d' %(type0,type1)
			#filter -- type-pair
			expr = 'type0==%d and type1==%d' % (type0, type1)
			mean = data.query(expr).mean()
			if not pd.isna(mean['proportion']):
				transition = { 'From*': type0, 'To*':type1, 'Rate':mean['proportion'],}
				transitions.append(transition)
		
		#reasonability check
		for i_type in range(1, 5):
			rates = [dict['Rate'] for dict in transitions if dict['From*'] == i_type]
			ratio = sum(rates)
			if ratio != 1:
				for dict in transitions:
					if dict['From*'] == i_type: dict['Rate'] = dict['Rate']/ratio
		
		#filter out type0 = type1
		transitions = [dict for dict in transitions if dict['From*'] != dict['To*']]
		#export
		filenameNonurbanMean = filenameNonurbanMean if filenameNonurbanMean else 'nonurban_transitions_mean.csv'
		filenameNonurbanMean = pathlib.Path(filenameNonurbanMean)
		if fileIsValid(filenameNonurbanMean):
			filenameNonurbanMean.rename(pathlib.Path(str(filenameNonurbanMean).replace('.csv', '_bak%s.csv' % str(int(time.time()*1e6)))))
		filenameNonurbanMean.parent.mkdir(parents=True, exist_ok=True)
		writeLogsDicts2csv(filenameNonurbanMean, transitions)
	else:
		#multi-output
		data = pd.read_csv(filenameNonurban)
		for code in range(1001, 1007):
			transitions = []
			for typePair in typePairs:
				type0, type1 = typePair
				typePair_string = '%d-%d' %(type0,type1)
				#filter -- type-pair
				expr = 'type0==%d and type1==%d and code==%d' % (type0, type1, code)
				mean = data.query(expr).mean()
				if not pd.isna(mean['proportion']):
					transition = { 'From*': type0, 'To*':type1, 'Rate':mean['proportion'],}
					transitions.append(transition)
			
			#reasonability check
			for i_type in range(1, 5):
				rates = [dict['Rate'] for dict in transitions if dict['From*'] == i_type]
				ratio = sum(rates)
				if ratio != 1:
					for dict in transitions:
						if dict['From*'] == i_type: dict['Rate'] = dict['Rate']/ratio
			
			#filter out type0 = type1
			transitions = [dict for dict in transitions if dict['From*'] != dict['To*']]
			#export
			filename = ( str(filenameNonurbanMean).replace('.csv', '_%d.csv'%code) 
				if filenameNonurbanMean else 'nonurban_transitions_mean_%d.csv' % code )
			filename = pathlib.Path(filename)
			if fileIsValid(filename):
				filename.rename(pathlib.Path(str(filename).replace('.csv', '_bak%s.csv' % str(int(time.time()*1e6)))))
			filename.parent.mkdir(parents=True, exist_ok=True)
			writeLogsDicts2csv(filename, transitions)
	
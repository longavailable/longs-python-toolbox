# -*- coding: utf-8 -*-
"""
* Updated on 2022/08/06
* python3 + GEE
"""

from .util import *
try:
	import ee; ee.Initialize()
except:
	proxy()		# set a proxy for 'earthengineapi'
	import ee; ee.Initialize()
import numpy as np
import math
import json, csv
import pathlib
import time
import subprocess
import traceback
import requests
import random
from zipfile import ZipFile as zfile

#return a image form ee.ImageCollection
def getImageByIndex(imageCollection, index):
	'''Extract an image from an imageCollection by index
	
	Parameters:
		imageCollection: source ee.ImageCollection
			Type: ee.ImageCollection object
		index: index for image to extract
			Type: integer
	Returns:
		an extracted ee.Image object
	'''
	return ee.Image(imageCollection.toList(1, index).get(0))

def getFeatureByIndex(featureCollection, index):
	'''Extract a feature from a featureCollection by index
	
	Parameters:
		featureCollection: source ee.FmageCollection
			Type: ee.FmageCollection object
		index: index for feature to extract
			Type: integer
	Returns:
		an extracted ee.Feature object
	'''
	return ee.Feature(featureCollection.toList(1, index).get(0))

#split a over-5000-object ee.FeatureCollection to some ee.FeatureCollection
#return a python list conposed of ee.FeatureCollection
def spitFeatureCollection(eeFeatColl, length, splitNumber = 4000):
	parts = math.ceil( length / splitNumber )
	list = []
	for i in range(parts):
		eelist = eeFeatColl.toList(splitNumber, i * splitNumber)
		eeFeatCollPart = ee.FeatureCollection(eelist)
		list.append(eeFeatCollPart)
	return parts, list

#convert an MultiGeometry to an ee.FeatureCollection, each geometry as a feature
def multigeometryToFeatureCollection(multigeometry):
	geometries = multigeometry.geometries()	# a ee.List for geometries
	featureCollection = ee.FeatureCollection(geometries.map(lambda g: ee.Feature(ee.Geometry(g))))
	return featureCollection

#convert an multibands image to an ee.ImageCollection, each band as an image
def multibandsImageToImageCollection(multibandsImage):
	bands = multibandsImage.bandNames()
	imageCollection = ee.ImageCollection(bands.map(lambda b: ee.Image(multibandsImage.select([b]).set({'bandName': b}))))
	return imageCollection

#
#property is a string, format as ['string']
def propertyToList(eeFeatColl, propertyField):
	'''Convert the specified field of all features in a ee.FeatureCollection to a list
	
	Parameters:
		eeFeatColl: the ee.FeatureCollection to ingest
			Type: ee.FeatureCollection object
		propertyField: field/key of properties for feature in eeFeatColl
			Type: string or one string-item list
	Return:
		ee.List object
	'''
	propertyField = [propertyField] if isinstance(propertyField, str) else propertyField
	def featurePropertyToList(feature, list):
		featureList = ee.Feature(feature).toArray(propertyField).toList()
		return ee.List(list).cat(featureList)
	return ee.FeatureCollection(eeFeatColl).iterate(featurePropertyToList, ee.List([]))

#generate grid for a rectangle region
#unit - decimal degree
'''
def generateGridForGeometry(region, dx, dy):
	bounds = region.bounds().coordinates().get(0).getInfo()
	#print(bounds)
	xmin = bounds[0][0]
	xmax = bounds[1][0]
	ymin = bounds[0][1]
	ymax = bounds[2][1]
	#print(xmin,xmax,ymin,ymax)
	xx = np.arange(xmin, xmax, dx)
	yy = np.arange(ymin, ymax, dy)

	cells = ee.FeatureCollection([])
	for x in xx:
		for y in yy:
			x1 = ee.Number(x).subtract(ee.Number(dx).multiply(0.5))
			x2 = ee.Number(x).add(ee.Number(dx).multiply(0.5))
			y1 = ee.Number(y).subtract(ee.Number(dy).multiply(0.5))
			y2 = ee.Number(y).add(ee.Number(dy).multiply(0.5))
			coords = ee.List([x1, y1, x2, y2])
			#pprint(coords.getInfo())
			rect = ee.Algorithms.GeometryConstructors.Rectangle(coords)
			rect = ee.FeatureCollection(ee.Feature(rect))
			cells = cells.merge(rect)

	return ee.FeatureCollection(cells)
'''
def generateGrid(xmin,ymin,xmax,ymax,dx,dy):
	cells = ee.FeatureCollection([])
	xmin,ymin,xmax,ymax,dx,dy = float(xmin),float(ymin),float(xmax),float(ymax),float(dx),float(dy)
	xx = np.arange(xmin, xmax, dx) #range only for integer, np.arange works for float
	yy = np.arange(ymin, ymax, dy)
	for x in xx:
		for y in yy:
			coords = [x+0.0, y+0.0, x+dx, y+dy]
			rect = ee.Algorithms.GeometryConstructors.Rectangle(coords)
			rect = ee.FeatureCollection(ee.Feature(rect))
			cells = cells.merge(rect)
	return ee.FeatureCollection(cells)

#extend general grids 'multiple' rounds around
#default 'ouput' is for extension part; if need all, then assign it 'all'
def extendGrid(xmin,ymin,xmax,ymax,dx,dy,left=1,bottom=1,right=1,top=1,multiple=None,output='ex'):
	cells = ee.FeatureCollection([])
	xmin,ymin,xmax,ymax,dx,dy = float(xmin),float(ymin),float(xmax),float(ymax),float(dx),float(dy)
	
	if multiple and multiple >=0:
		left = bottom = right = top = multiple
	
	xmin_new = xmin - left * dx
	xmax_new = xmax + right * dx
	ymin_new = ymin - bottom * dy
	ymax_new = ymax + top * dy
	
	xx = np.arange(xmin_new, xmax_new, dx) #range only for integer, np.arange works for float
	yy = np.arange(ymin_new, ymax_new, dy)
	for x in xx:
		for y in yy:
			if 'EX' in output.upper():
				if xmin <= x < xmax and ymin <= y < ymax: continue
			coords = [x, y, x + dx, y + dy]
			rect = ee.Algorithms.GeometryConstructors.Rectangle(coords)
			rect = ee.FeatureCollection(ee.Feature(rect))
			cells = cells.merge(rect)
	return ee.FeatureCollection(cells)

def gridThePlanet(dx, dy):
	xmin, xmax, ymin, ymax = -180, 180, -90, 90		# coordinates of the planet
	return generateGrid(xmin,ymin,xmax,ymax,dx,dy)
def generateGridForGeometry(eeGeometry, dx, dy):
	bounds = eeGeometry.bounds().coordinates().get(0).getInfo()
	#print(bounds)
	xmin = bounds[0][0] - 0.05 * dx		# add a 0.05dx distance buffer
	xmax = bounds[1][0] + 0.05 * dx
	ymin = bounds[0][1] - 0.05 * dy
	ymax = bounds[2][1] + 0.05 * dy  
	return generateGrid(xmin,ymin,xmax,ymax,dx,dy)
def generateGridForGeometryByParts(eeGeometry, parts):
	if isinstance(parts, int):
		xparts, yparts = parts, parts
	elif isinstance(parts, list) and len(parts)==1:
		xparts, yparts = parts[0], parts[0]
	elif isinstance(parts, list) and len(parts)==2:
		xparts, yparts = parts[0], parts[1]
	
	bounds = eeGeometry.bounds().coordinates().get(0).getInfo()
	#orginal boundary
	xmin = bounds[0][0]
	xmax = bounds[1][0]
	ymin = bounds[0][1]
	ymax = bounds[2][1]
	dx = (xmax - xmin)/xparts
	dy = (ymax - ymin)/yparts
	#enlarged boundary
	xmin = xmin - 0.05 * dx			#add 0.05dx buffer
	xmax = xmax + 0.05 * dx
	ymin = ymin - 0.05 * dy
	ymax = ymax + 0.05 * dy
	dx = (xmax - xmin)/xparts
	dy = (ymax - ymin)/yparts	#notice: dx and dy maybe have a big difference
	return generateGrid(xmin,ymin,xmax,ymax,dx,dy)
def featureCollectionGridding(eeFeatColl, dx, dy):
	eeGeometry = eeFeatColl.geometry()
	eeGeometryGridding = generateGridForGeometry(eeGeometry, dx, dy)
	return featureCollectionIntersection(eeFeatColl,eeGeometryGridding)
def featureCollectionGriddingByParts(eeFeatColl, parts):
	eeGeometry = eeFeatColl.geometry()
	eeGeometryGridding = generateGridForGeometryByParts(eeGeometry, parts)
	return featureCollectionIntersection(eeFeatColl,eeGeometryGridding)

def addArea(feature):
  return feature.set({'area': feature.area(1e3)})

#Return the intersection of two ee.FeatureCollection objects
#Both input and return are ee.FeatureCollection
def featureCollectionIntersection(featColl01,featColl02):
	featCollNew = ee.FeatureCollection([])
	def featureIntersection(feature,featCollInit):
		featureNew = feature.intersection(feature01)
		return ee.FeatureCollection(featCollInit).merge(ee.FeatureCollection(featureNew))
	lens = featColl01.size().getInfo()
	for i in range(0,lens):
		feature01 = getFeatureByIndex(featColl01,i)
		featColl02Slimmed = featColl02.filterBounds(feature01.geometry())
		featCollNew02 = featColl02Slimmed.iterate(featureIntersection,ee.FeatureCollection([]))
		featCollNew = featCollNew.merge(featCollNew02)
	return featCollNew
#the following cost much more runtime than the one above, due to using too many getInfo()
def featureCollectionIntersection01(featColl01,featColl02):
	featCollNew = ee.FeatureCollection([])
	lens01 = featColl01.size().getInfo()
	for i in range(0,lens01):
		feature01 = getFeatureByIndex(featColl01,i)
		featColl02Slimmed = featColl02.filterBounds(feature01.geometry())
		lens02 = featColl02Slimmed.size().getInfo()
		for j in range(0,lens02):
			feature02 = getFeatureByIndex(featColl02Slimmed,j)
			feature = feature02.intersection(feature01)
			featCollNew = featCollNew.merge(ee.FeatureCollection(feature))
	return featCollNew
#get download url for a talbe, only has geometry information
def tableDownloadUrl(assetId,format):
	table = ee.FeatureCollection(assetId)
	url = table.getDownloadURL(filetype = format, selectors='.geo')
	return url
#download an eeFeatColl as a geojson-format file with full information
#works for ee.FeatureCollection, ee.Feature, and ee.Geometry
def downloadTableToGeoJson(eeFeatColl,fileName):
	dict = eeFeatColl.getInfo()
	json_dict = json.dumps(dict)
	with open(fileName,'w') as f:
		f.write(json_dict)
#download an eeFeatColl as a csv-format file with '.geo' information
def downloadTableToCsv(eeFeatColl,fileName):
	dict = eeFeatColl.getInfo()
	features = dict['features']		#list
	geometries = [feature['geometry'] for feature in features]
	#write a header line
	with open(fileName,'w') as f:
		f.write('.geo')
	for geometry in geometries:
		text = '"' + json.dumps(geometry) + '"'
		with open(fileName,'a+') as f:
			f.write(f.read() + '\n' + text)

#download an eeFeatColl as a custom format file
#geojson(default), csv or both
def downloadTable(eeFeatColl,fileNameGeoJson=None,fileNameCSV=None,filetype=None):
	if not fileNameGeoJson and not fileNameCSV:
		print('These is no output file')
		return
	dict = eeFeatColl.getInfo()
	if fileNameGeoJson and ( not filetype or 'JSON' in filetype.upper()):
		json_dict = json.dumps(dict)
		with open(fileNameGeoJson,'w') as f:
			f.write(json_dict)
	if fileNameCSV and ( not filetype or 'CSV' in filetype.upper()):
		features = dict['features']		#list
		geometries = [feature['geometry'] for feature in features]
		#write a header line
		with open(fileNameCSV,'w') as f:
			f.write('.geo')
		for geometry in geometries:
			text = '"' + json.dumps(geometry) + '"'
			with open(fileNameCSV,'a+') as f:
				f.write(f.read() + '\n' + text)

#a wrapper for downloadTable to file, only for geojson-format at present
def downloader4File(eeFeatColl,filename,attempts):
	while attempts > 0:
		downloadTable(eeFeatColl,filename)
		#time.sleep(5)
		if downloadIsSuccess(filename):
			print('Succeeded -- Download -- %s' % pathlib.Path(filename).name)
			attempts = 0
		else:
			pathlib.Path(filename).unlink()	#remove file if failed-download
			attempts = attempts - 1
			if attempts == 0:
				print('Failed -- Download -- ' % pathlib.Path(filename).name)

#a wrapper for downloadTable to zipfile, only for geojson-format at present
def downloader4Zip(eeFeatColl,filename,zipFile,attempts):
	while attempts > 0:
		downloadTable(eeFeatColl,filename)
		#time.sleep(5)
		if downloadIsSuccess(filename):
			comp_re = compress2zip(filename,zipFile,str(filename)[-12:])
			if comp_re:	#2nd time check
				print('Succeeded -- Download -- %s' % pathlib.Path(filename).name)
				attempts = 0
		else:
			attempts = attempts - 1
			if attempts == 0:
				print('Failed -- Download -- %s' % pathlib.Path(filename).name)
		pathlib.Path(filename).unlink()		#remove file after compress or faided-download

def downloader(eeFeatColl, filename, zipFile=None, attempts=3):
	'''A wrapper for downloader4File, downloader4Zip, only for geojson-format at present.
	- only for table
	- only for `EPSG:4326`
	
	Todo: merge with `imageDownloader`
	
	Parameters:
		eeFeatColl: ee.FeatureCollection object to download
			Type: ee.FeatureCollection
		filename: `.geojson` filename; it should be `path + basename` for `downloader4File`; it should be `path + basename` in-place for `downloader4Zip`
			Type: string, pathlib.Path object
		zipFile: `.zip` filename
			Type: string, pathlib.Path object
			Default: None
		attempts: 
			Type: integer
			Default: 3
	'''
	if not zipFile:
		downloader4File(eeFeatColl,filename,attempts)
	else:
		downloader4Zip(eeFeatColl,filename,zipFile,attempts)

def parseGeometriesFromZip(zipObject, fileNameGeoJson):
	'''parse .geo data from geojson in zip to a list
	Deprecated. Replaced by 'parseFeatureDictsFromGeoJsonInZip' function.
	'''
	#open a file in a zipfile object
	with zipObject.open(fileNameGeoJson) as f:
		dict = json.loads(f.read())
	features = dict['features']		#list
	geometries = [feature['geometry'] for feature in features]
	return geometries


def pendingTasksLength(last='ALL'):
	'''Check the pending tasks, including 'READY' and 'RUNNING'.
	Parameters:
		last: check limits. Default 'ALL', then check 'all' tasks, it is suitable for a large number of tasks situation. It's better to check last few tasks if not too much but each task takes a long time.
			Type: string, integer
			Default: 'ALL'
	Returns:
		Length of pendingTasks: integer
		Or Boolean/False
	'''
	if isinstance(last, str):
		if 'ALL' in last.upper():
			tasks = ee.data.getTaskList()
		else:
			return False
	elif isinstance(last, int):
		if last > 0:
			tasks = ee.data.getTaskList()[0:last]
		else:
			return False
	else:
		return False
	pendingTasks = [task for task in tasks if task['state'].upper() in ['READY', 'RUNNING']]
	return len(pendingTasks)

#based on buffer to realize closing operation
#geometry is an ee.Geometry object
def morphClosing(geometry, bufferDistance, maxError = 100):
	buffer_positive = geometry.buffer(bufferDistance, maxError)
	buffer_negative = ee.FeatureCollection(buffer_positive).geometry().buffer(-bufferDistance, maxError)	#casting to an ee.FeatureCollection object make things right
	return buffer_negative.dissolve(maxError)

#parse data from geojson-format file to an ee.Feature
#geojson file should be an ee.Feature object or an ee.FeatureCollection with one element (ee.Feature)
#reture False for bad cases
def parseFeatureFromGeoJson(fileNameGeoJson):
	with open(fileNameGeoJson) as f:
		geodict = json.loads(f.read())
	if geodict['type'] == 'Feature': 
		return ee.Feature(geodict)
	elif geodict['type'] == 'FeatureCollection':
		if len(geodict['features']) == 1:
			return ee.Feature(geodict['features'][0])
		else:
			print('Failed -- Parsing -- check length of "feature" in %s' % fileNameGeoJson)
			return False
	else:
		print('Failed -- Parsing -- check "type" in %s' % fileNameGeoJson)
		return False

#parse data from geojson-format file to an ee.FeatureCollection
def parseFeatureCollectionFromGeoJson(fileNameGeoJson):
	with open(fileNameGeoJson) as f:
		geodict = json.loads(f.read())
	return ee.FeatureCollection(tuple(geodict['features']))

def calculateArea(feature, reference, threshold = 5e9):
	'''Split and calculate area. Notice: has never been used.
	'''
	if reference <= threshold:
		area = ee.Feature(feature).area(1e3)
	else:
		parts = 1 + reference//threshold
		grids = featureCollectionGriddingByParts(ee.FeatureCollection(ee.Feature(feature)),parts)
		area = grids.map(lambda f: f.set({'area': f.area(1e3)})).aggregate_sum('area')
	return area

def adjustFeatureDict4csv(featureDict, geometry = '.geo', properties = None):
	'''Customize original nested dictionary to a dictionary which can be save to geocsv directly.
	
	Parameters:
		featureDict: the original nested dictionary
			Type: dictionary (nested)
		geometry: optinal, field for geometry, it is a must for geocsv file. Although it can be ignored be set to other assignment.
			Type: string
			Default: '.geo', is equivalent to 'None'
		properties: optional, need all then assign 'all'
			Type: string, list
			Default: None
	Returns:
		Dictionary
	'''
	newdict = {}
	if properties:
		if isinstance(properties, str):
			if 'ALL' in properties.upper():
				newdict.update(featureDict['properties'])
			else:
				try:
					newdict[properties] = featureDict['properties'][properties]
				except:
					print('Warning -- check keyword "%s"' % properties)
		elif isinstance(properties, list):
			for property in properties:
				try:
					newdict[property] = featureDict['properties'][property]
				except:
					print('-'*60); traceback.print_exc(); print('-'*60)
					print('Warning -- check keyword "%s" in list "properties"' % property)
	
	if not geometry or geometry == '.geo':
		if featureDict['geometry'] ==  None:	#'null' will be 'None' in python
			newdict[geometry] = ''
		else:
			newdict[geometry] = json.dumps(featureDict['geometry'])
	else:
		print('Warning -- check keyword "%s"' % geometry)
	
	return newdict

def parseFeatureDictsFromGeoJson(fileNameGeoJson, geometry = '.geo', properties = None):
	'''	Get the original nested dictionary for ee.Feature(s) from input geojson file, then convert to direct-dictionary for geocsv by invoking 'adjustFeatureDict4csv' function.
	
	Parameters:
		fileNameGeoJson: input filename
			Type: string, pathlib.PosixPath
		geometry: see function 'adjustFeatureDict4csv'
		properties: see function 'adjustFeatureDict4csv'
	Returns:
		List or Boolean/False
	'''
	with open(fileNameGeoJson) as f:
		geodict = json.loads(f.read())
	if geodict['type'] == 'FeatureCollection':
		features = geodict['features']		#list
		return [adjustFeatureDict4csv(feature, geometry, properties) for feature in features]
	elif geodict['type'] == 'Feature':
		return [adjustFeatureDict4csv(geodict, geometry, properties)]
	else:
		print('Failed -- Parsing -- check "type" in %s' % fileNameGeoJson)
		return False

def parseFeatureDictsFromGeoJsonInZip(fileNameZip, fileNameGeoJson, geometry = '.geo', properties = None):
	'''	Get the original nested dictionary for ee.Feature(s) from input geojson file in a compressed zipfile, then convert to direct-dictionary for geocsv by invoking 'adjustFeatureDict4csv' function.
	
	Parameters:
		fileNameZip: input zip filename
			Type: string, pathlib.PosixPath
		fileNameGeoJson: input filename, it is the filename with its inside path in ZipFile. It's different with 'fileNameGeoJson' in 'parseFeatureDictsFromGeoJson' function.
			Type: string
		geometry: see function 'adjustFeatureDict4csv'
		properties: see function 'adjustFeatureDict4csv'
	Returns:
		List or Boolean/False
	'''

	#open a file in a zipfile object
	with zfile(fileNameZip) as myzip:
		with myzip.open(fileNameGeoJson) as f:
			geodict = json.loads(f.read())
	if geodict['type'] == 'FeatureCollection':
		features = geodict['features']		#list
		return [adjustFeatureDict4csv(feature, geometry, properties) for feature in features]
	elif geodict['type'] == 'Feature':
		return [adjustFeatureDict4csv(geodict, geometry, properties)]
	else:
		print('Failed -- Parsing -- check "type" in %s' % fileNameGeoJson)
		return False

def writeFeatureDicts2csv(features, fileNameCSV):
	'''	Write a list of featureDicts to a geocsv file. See `writeLogsDicts2csv` in longspyfuncs module.
	
	Parameters:
		features: output list of dictionaries
			Type: list of featureDict
		fileNameCSV: output filename
			Type: string, pathlib.PosixPath
	Returns:
		Boolean
	'''
	return writeLogsDicts2csv(fileNameCSV, features)

def sortDictList(dictList, sortField=None, sortReverse=False, addSortOrder=False):
	'''Sort a list of dicts by specific field.
	
	Parameters:
		dictList: the list of dicts to sort.
			Type: list
		sortField: the field/key used to sort
			Type: string
			Default: None
		sortReverse: reverse or not; reverse means descending order, not means ascending.
			Type: boolean
			Default: False
		addSortOrder: add a field to index current sorting; 
				if it's a string, then it is the field/key to add; 
				if it's `True`, sortField + `_order`; `False`, do nothing.
			Type: boolean, string
			Default: False
	Returns:
		dictList: original or sorted list of dictionaries
			Type: list
	'''
	try:
		assert sortField in dictList[0]
		dictList.sort(key = lambda d: d[sortField], reverse = sortReverse)
		if addSortOrder:
			field_order = addSortOrder if isinstance(addSortOrder, str) else '%s_order' % sortField
			for d in dictList: d[field_order] = dictList.index(d)
	except:
		print('-'*60); traceback.print_exc(); print('-'*60)
		print('Warning -- sorting failed -- function "sortDictList"')
	finally: return dictList
	
def geojson2csv(fileNameGeoJson, fileNameCSV, geometry = '.geo', properties = None,
	sortField=None, sortReverse=False, addSortOrder=False):
	'''A wrapper to convert ee.Feature(s) from geojson file(s) to a geocsv file.
	
	Parameters:
		fileNameGeoJson: input filename(s)
			Type: string, pathlib.PosixPath or list of strings, pathlib.PosixPath objects
		fileNameCSV: output filename
			Type: string, pathlib.PosixPath
		geometry: see function 'adjustFeatureDict4csv'
		properties: see function 'adjustFeatureDict4csv'
		sortField, sortReverse, addSortOrder: see function 'sortDictList'
	Returns:
		Boolean
	'''
	if isinstance(fileNameGeoJson, (str, pathlib.PosixPath)):
		features = parseFeatureDictsFromGeoJson(fileNameGeoJson, geometry, properties)
	elif isinstance(fileNameGeoJson, list):
		features = []
		for file in fileNameGeoJson:
			features_part = parseFeatureDictsFromGeoJson(file, geometry, properties)
			if features_part:
				features = features + features_part
	if features:
		if sortField:
			features = sortDictList(features, sortField=sortField, sortReverse=sortReverse, addSortOrder=addSortOrder)
		return writeFeatureDicts2csv(features, fileNameCSV)

def geojsonInZip2csv(fileNameZip, fileNameGeoJson, fileNameCSV, geometry = '.geo', 
	properties = None, sortField=None, sortReverse=False, addSortOrder=False):
	'''A wrapper to convert ee.Feature(s) from a geojson file in compressed zipfile to a geocsv file.
	
	Parameters:
		fileNameZip: input zip filename
			Type: string, pathlib.PosixPath
		fileNameGeoJson: see function 'parseFeatureDictsFromGeoJsonInZip'
			Type: string
		fileNameCSV: output filename
			Type: string, pathlib.PosixPath
		geometry: see function 'adjustFeatureDict4csv'
		properties: see function 'adjustFeatureDict4csv'
		sortField, sortReverse, addSortOrder: see function 'sortDictList'
	Returns:
		Boolean
	'''
	features = parseFeatureDictsFromGeoJsonInZip(fileNameZip, fileNameGeoJson, geometry, properties)
	if features:
		if sortField:
			features = sortDictList(features, sortField=sortField, sortReverse=sortReverse, addSortOrder=addSortOrder)
		return writeFeatureDicts2csv(features, fileNameCSV)

def exportTable2Asset(eeFeatColl, assetId, properties=None, overwrite=True, wait=True):
	'''A wrapper to execute a ee.batch.Export.table.toAsset() task.
	
	Parameters:
		eeFeatColl: ee.FeatureCollection to export
			Type: ee.FeatureCollection object
		assetId: 
			Type: string
		properties: set as asset properties
			Type: dictionary
			Default: None
		overwrite: 
			Type: boolean
			Default: True
		wait:
			Type: boolean
			Default: True
	Returns:
		Boolean
	'''
	'''
	#remove existed asset at beginning, a little risky
	if overwrite:
		while ee.data.getInfo(assetId):
			try:
				ee.data.deleteAsset(assetId)
			except:
				time.sleep(5)
	else:
		if ee.data.getInfo(assetId):
			print('Reminding -- %s exist -- keyword "overwrite" is False' %assetId )
			return False
	assetId_export = assetId
	'''
	randomStr = 'temp%s' % str(int(time.time()*1e6))
	if ee.data.getInfo(assetId):
		if overwrite:
			assetId_export = '%s_%s' % (assetId,randomStr)
			#if ee.data.getInfo(assetId_export): ee.data.deleteAsset(assetId_export)
			eeDataDeleteAsset(assetId_export, wait=True)
			wait = True
		else:
			print('Reminding -- %s exist -- keyword "overwrite" is False' %assetId )
			return True
	else:
		assetId_export = assetId
	
	task = ( ee.batch.Export.table.toAsset(
		collection= ee.FeatureCollection(eeFeatColl), 
		description= 'export_%s' % assetId.split('/')[-1],
		assetId= assetId_export ) )
	task.start()
	if wait:
		while task.active():
			time.sleep(30)
		if task.status()['state'] == 'COMPLETED':
			#ensure the asset exists
			while not ee.data.getInfo(assetId_export):
				time.sleep(5)
			#remove existed and rename the new completed asset
			if assetId_export.endswith(randomStr):
				#ee.data.deleteAsset(assetId)
				eeDataDeleteAsset(assetId, wait=True)
				ee.data.renameAsset(assetId_export, assetId)
				#ensure renameAsset successful
				while not ee.data.getInfo(assetId):
					time.sleep(5)
			if properties:
				#ee.data.setAssetProperties(assetId, properties)
				ee.data.updateAsset(assetId,{'properties':properties},'properties')
				#ensure updateAsset successful
				#since asset exported has no properties key, so just check if the key exists.
				while 'properties' not in ee.data.getInfo(assetId):
					time.sleep(5)
			print('Succeeded -- export task %s' %assetId )
			return True
		else:
			print('Failed -- export task %s' %assetId )
			return False
	else:
		print('Reminding -- export task %s has been submitted -- keyword "wait" is False' %assetId )
		return True

def mergeAssets(assetIds, eeFeatColl0):
	'''A merger for assets.
	
	Parameters:
		assetIds: assets to merge
			Type: list
		eeFeatColl0: which merge to
			Type: ee.FeatureCollection object
	Returns:
		merged ee.FeatureCollection object
	'''
	def mergeFeatColl(eeFeatColl, eeFeatColl0):
		return ee.FeatureCollection(eeFeatColl0).merge(ee.FeatureCollection(eeFeatColl))
	eeFeatColls = ee.List([ee.FeatureCollection(assetId) for assetId in assetIds])
	return ee.FeatureCollection(eeFeatColls.iterate(mergeFeatColl,eeFeatColl0))

def eeDataDeleteAsset(assetId, wait=True):
	'''A wrapper to remove an asset and provide a 'wait' option.
	Since 'ee.data.deleteAsset' will just send command to sever without a return, and the delete operation is NOT in real time. This may raise some conflicts with following scripts which use a asset with the same ID.
	
	Parameters:
		assetId: ID of asset to remove
			Type: string
		wait: till the delete operation finishs
			Type: boolean
			Default: True
	'''
	if ee.data.getInfo(assetId):
		ee.data.deleteAsset(assetId)
		if wait:
			while ee.data.getInfo(assetId):
				time.sleep(5)
			print('Succeeded -- delete an asset -- %s' %assetId )
		else:
			print('Reminding -- deleteAsset task has been submitted without "wait" -- %s' %assetId )

def batchDeleteAssets(location, startswith_str='', contains_str='', endswith_str='', wait=False):
	'''A wrapper to remove assets in batch.
	
	Parameters:
		location: parentpath of assets to remove
			Type: string
		startswith_str: 
			Type: string
			Default: ''
		endswith_str: 
			Type: string
			Default: ''
		contains_str: 
			Type: string
			Default: ''
		wait: till the delete operation finishs
			Type: boolean
			Default: False
	Returns:
		Boolean
	'''
	prefixes = 'projects/earthengine-legacy/assets/'
	if location.startswith(prefixes):
		fullLocation = location
	elif location.startswith('users/'):
		fullLocation = prefixes + location
	else:
		print('Failed -- Assets removing -- check "location" of %s' % location)
		return False
	
	assets = ee.data.listAssets({'parent': fullLocation})
	for asset in assets['assets']:
		assetId = asset['id']
		assetBasename = assetId.split('/')[-1]
		#if assetBasename.startswith(startswith_str) or assetBasename.endswith(endswith_str) or contains_str in assetBasename:
		if assetBasename.startswith(startswith_str) and assetBasename.endswith(endswith_str) and contains_str in assetBasename:
			eeDataDeleteAsset(assetId, wait=wait)
			'''
			ee.data.deleteAsset(assetId)
			if wait:
				while ee.data.getInfo(assetId):
					time.sleep(5)
			'''
	return True
	
	
def exportImage2Asset(eeImage, assetId, scale=1000, region=None, overwrite=True, wait=True):
	'''A wrapper to execute a ee.batch.Export.image.toAsset() task.
	
	Parameters:
		eeImage: ee.Image to export
			Type: ee.Image object
		assetId: 
			Type: string
		scale: resolution in meters per pixel
			Type: integer
			default: 1000
		region:
			Type: ee.Geometry or coordinates serialized as a string
			default: None
		overwrite: 
			Type: boolean
			Default: True
		wait:
			Type: boolean
			Default: True
	Returns:
		Boolean
	'''
	randomStr = 'temp%s' % str(int(time.time()*1e6))
	if ee.data.getInfo(assetId):
		if overwrite:
			assetId_export = '%s_%s' % (assetId,randomStr)
			#if ee.data.getInfo(assetId_export): ee.data.deleteAsset(assetId_export)
			eeDataDeleteAsset(assetId_export, wait=True)
			wait = True
		else:
			print('Reminding -- %s exist -- keyword "overwrite" is False' %assetId )
			return True
	else:
		assetId_export = assetId
	
	region = region if region else eeImage.geometry()
	
	task = ( ee.batch.Export.image.toAsset(
		image= eeImage,
		description= 'export_%s' % assetId.split('/')[-1],
		assetId= assetId_export,
		scale= scale,
		region= region) )
	task.start()
	if wait:
		while task.active():
			time.sleep(30)
		if task.status()['state'] == 'COMPLETED':
			#ensure the asset exists
			while not ee.data.getInfo(assetId_export):
				time.sleep(5)
			#remove existed and rename the new completed asset
			if assetId_export.endswith(randomStr):
				#ee.data.deleteAsset(assetId)
				eeDataDeleteAsset(assetId, wait=True)
				ee.data.renameAsset(assetId_export, assetId)
				#ensure renameAsset successful
				while not ee.data.getInfo(assetId):
					time.sleep(5)
			print('Succeeded -- export task %s' %assetId )
			return True
		else:
			print('Failed -- export task %s' %assetId )
			return False
	else:
		print('Reminding -- export task %s has been submitted -- keyword "wait" is False' %assetId )
		return True

def binarize(eeImage, pixelValue, binary=True):
	'''Binarizing / extracting a specifid pixel value (land use type etc) in a source image.
	
	Parameters:
		eeImage: source image
			Type: ee.Image object
		pixelValue: specified pixel value to binarize
			Type: integer, float
		binary: if `True`, the pixelValue in returned image will be constant 1; if `False`, it will be the same as `pixelValue`
			Type: boolean
			Default: True
	Returns:
		a binarized / extracted ee.Image 
	'''
	if binary:
		return eeImage.eq(pixelValue).updateMask(eeImage.eq(pixelValue))
	else:
		return eeImage.mask(eeImage.eq(pixelValue))

def stateVector(eeImage, geometry=None, scale=30, additional=None):
	'''Calculating a state vector of a categorized image.
	
	Parameters:
		eeImage: image to calculate
			Type: ee.Image object
		geometry: the region over which to reduce data.
			Type: ee.Geometry
			default: None
		scale: a nominal scale in meters of the projection to work in.
			Type: float
			default: 30
		additional: add additional key-value pairs to results
			Type: dictionary
			default: None
		
	Returns:
		List of dictionaries
	'''
	geometry = geometry if geometry else eeImage.geometry()
	if isinstance(geometry, (ee.featurecollection.FeatureCollection, ee.feature.Feature)): geometry = geometry.geometry()
	
	areaImage = ee.Image.pixelArea()
	imageNew = areaImage.addBands(eeImage)
	try:
		classArea = ( imageNew.reduceRegion(
			reducer = ee.Reducer.sum().group(groupField=1, groupName='class'),
			geometry = geometry,
			scale = scale,
			maxPixels = 1e13).getInfo()['groups'] )
	except:
		classArea = ( imageNew.reduceRegion(
			reducer = ee.Reducer.sum().group(groupField=1, groupName='class'),
			geometry = geometry,
			scale = scale,
			bestEffort = True).getInfo()['groups'] )
		
	total = sum([dict['sum'] for dict in classArea])
	for dict in classArea:
		#dict['proportion'] = round(dict['sum'] / total,5)
		dict['proportion'] = dict['sum'] / total
		dict['area'] = dict.pop('sum')
		if additional: dict.update(additional)
	return classArea

def transitionMatrix(eeImage0, eeImage1, geometry=None, scale=30, additional=None):
	'''Calculating a transition matrix between two categorized images.
	
	Parameters:
		eeImage0: initial image
			Type: ee.Image object
		eeImage1: final image
			Type: ee.Image object
		geometry: the region over which to reduce data.
			Type: ee.Geometry
			Default: None
		scale: a nominal scale in meters of the projection to work in.
			Type: float
			Default: 30
		additional: add additional key-value pairs to results
			Type: dictionary
			Default: None
		
	Returns:
		List of dictionaries
	'''
	geometry = geometry if geometry else eeImage.geometry()
	if isinstance(geometry, (ee.featurecollection.FeatureCollection, ee.feature.Feature)): geometry = geometry.geometry()
	
	areaImage = ee.Image.pixelArea()
	#get LULC types
	count= ( eeImage0.addBands(areaImage).reduceRegion(
		reducer = ee.Reducer.count().group(),
		geometry = geometry,
		scale = scale,
		bestEffort = True).getInfo()['groups'] )
	types = [dict['group'] for dict in count]
	transition = []
	for type in types:
		mask = binarize(eeImage0,type)
		image_masked = eeImage1.updateMask(mask)
		re = stateVector(image_masked, geometry=geometry, scale=scale)
		for dict in re:
			dict['type0'] = type
			dict['type1'] = dict.pop('class')
			if additional: dict.update(additional)
		transition = transition + re
	return transition

def upload2Asset(filename, assetId, overwrite=True, wait=True):
	'''A wrapper to upload a geojson (.geojson, .json), geocsv (.csv), or geotiff (.tif, .tiff) file to GEE asset.
	
	Parameters:
		filename: file to upload, should be a GeoJSON (.geojson, .json), GeoCSV (.csv) or GeoTIFF (.tif, .tiff) file
			Type: string, pathlib.PosixPath
		assetId: 
			Type: string
		overwrite: 
			Type: boolean
			Default: True
		wait: 
			Type: boolean
			Default: True
	Returns:
		Boolean
	'''
	try:
		#gcs need credentials
		#from longsgeegcs import upload2AssetViaGCS
		from .geegcs import upload2AssetViaGCS
		print('Status -- uploadMode=0 -- via Google Cloud Storage')
		return upload2AssetViaGCS(filename, assetId, overwrite=overwrite, wait=wait)
	except:
		#requests need help from selenium
		#from longsgee_requests import upload2AssetByRequests
		from .gee_requests import upload2AssetByRequests
		print('Status -- uploadMode=1 -- by requests')
		return upload2AssetByRequests(filename, assetId, overwrite=overwrite, wait=wait)

def uploadTable2Asset(filename, assetId, overwrite=True, wait=True):
	'''This function is for keeping compatible. See 'upload2Asset'.	
	'''
	return upload2Asset(filename, assetId, overwrite=overwrite, wait=wait)

def uploadImage2Asset(filename, assetId, overwrite=True, wait=True):
	'''This function is for keeping compatible. See 'upload2Asset'.	
	'''
	return upload2Asset(filename, assetId, overwrite=overwrite, wait=wait)

def reclassESACCILC(year, geometry):
	'''Reclass ESA-CCI-LC to custum LULC.
	Note, source data is `ee.ImageCollection("users/XiaolongLiu/lc/esacci_lc")` and reclass rules is fixed.
	
	Parameters:
		year: 
			Type: integer
		geometry: domain to reclass
			Type: ee.Geometry
	Returns:
		Reclassed ee.Image.
	'''
	esacci_lc = ee.Image('users/XiaolongLiu/lc/esacci_lc/esacci_lc_%d' % year)
	#reclass rules
	'''
	#bandname
	basic = (
		"( b('field') == 10 || b('field') == 20 || b('field') == 30 ) ? 1"+  #cropland
		": ( ( b('field') >= 11 && b('field') <= 12) || (b('field') >= 40 && b('field') <= 180) ) ? 2"+ #greespace
		": (  b('field') >= 190 && b('field') <= 202 ) ? 3"+ #urban areas
		": (  b('field') >= 210 && b('field') <= 220 ) ? 4"+ #water bodies
		": 0" )	#No data
	if 1992 < year <= 2015:
		field = 'b' + str( year - 1992 + 1)
	else:
		field = 'b1'
	expression = basic.replace('field',field)
	'''
	#index
	expression = (
		"( b(0) == 10 || b(0) == 20 || b(0) == 30 ) ? 1"+  #cropland
		": ( ( b(0) >= 11 && b(0) <= 12) || (b(0) >= 40 && b(0) <= 180) ) ? 2"+ #greespace
		": (  b(0) >= 190 && b(0) <= 202 ) ? 3"+ #urban areas
		": (  b(0) >= 210 && b(0) <= 220 ) ? 4"+ #water bodies
		": 0" )	#No data
	lulc = ( esacci_lc.clip(geometry)
		.expression(expression)
		.clip(geometry)
		.set({'year': year})	)
	return ee.Image(lulc)

class geometryOperation:
	'''
	Parameters:
		g1, g2: 
			Type: ee.Geometry object
	Returns:
		ee.Geometry
	'''
	
	@staticmethod
	def union(g1, g2):
		'''All
		A ∪ B, https://en.wikipedia.org/wiki/File:Venn0111.svg
		A or B
		'''
		return ee.Geometry(g1.union(g2))
	
	@staticmethod
	def intersection(g1, g2):
		'''Common part
		A ∩ B, https://en.wikipedia.org/wiki/File:Venn0001.svg
		A and B
		'''
		return ee.Geometry(g1.intersection(g2))
		#return ee.Geometry(g1.difference(g1.difference(g2)))
	
	@staticmethod
	def difference(g1, g2):
		'''Unique part of g1
		A − B, https://en.wikipedia.org/wiki/File:Venn0100.svg
		A and not B
		'''
		return ee.Geometry(g1.difference(g2))
	
	@staticmethod
	def symmetricDifference(g1, g2):
		'''Non-common part
		A △ B, https://en.wikipedia.org/wiki/File:Venn0110.svg
		(A and not B) and (B and not A)
		'''
		return ee.Geometry(g1.difference(g2))
		#return ee.Geometry(difference(g1, g2).union(difference(g2, g1)))

def downUpload2Asset(eeFeatColl, assetId, overwrite=True, wait=True, filename=None, zipFile=None, attempts=3, 
	sortField=None, sortReverse=False, addSortOrder=False):
	'''Download to local, then upload to GEE assets.
	
	Parameters:
		eeFeatColl, zipFile, attempts: see function `downloader`.
		assetId, overwrite, wait: see function `upload2Asset`.
		sortField, sortReverse, addSortOrder: see function `sortDictList`
	'''
	if not filename: filename = pathlib.Path('temp%s.geojson' % str(int(time.time()*1e6)))
	try:
		filename2 = pathlib.Path('temp%s.csv' % str(int(time.time()*1e6)))	#assign a temporary file before potential except happening
		downloader(eeFeatColl, filename, zipFile=zipFile, attempts=attempts)
		if not sortField:
			return upload2Asset(filename, assetId, overwrite=overwrite, wait=wait)
		else:
			geojson2csv(filename, filename2, properties = 'all', sortField=sortField, sortReverse=sortReverse, addSortOrder=addSortOrder)
			return upload2Asset(filename2, assetId, overwrite=overwrite, wait=wait)
	except:
		print('-'*60); traceback.print_exc(); print('-'*60)
		return False
	finally:
		if filename.name.startswith('temp') and fileIsValid(filename): pathlib.Path(filename).unlink()
		if fileIsValid(filename2): pathlib.Path(filename2).unlink()

def featurePropertyNames(feature):
	'''Get the fields/keys of feature.
	
	Parameters:
		feature:
			Type: ee.Feature object
	Returns:
	 list
	'''
	return feature.propertyNames().getInfo()

def featurePropertyNamesInTable(eeFeatColl):
	'''Get the fields/keys of features in an ee.FeatureCollection.
	
	Parameters:
		eeFeatColl:
			Type: ee.FeatureCollection object
	Returns:
	 list
	'''
	return featurePropertyNames(ee.Feature(eeFeatColl.first()))

def table2image(eeFeatColl, boundary=None, pixelValues=None, pixelField=None, pixelPrefix=None, pixelValueFeedback=False):
	'''Rasterize a vector/featureCollection to image.
		
	Default case:
	- index of features
	
	Four optinal cases:
		- pixelValue: specify the pixelValues list, highest priority
		- pixelField: values of specifid pixelField
		- pixelPrefix: prefix + feature index
		- pixelField, pixelPrefix: prefix + value of specifid pixelField
	
	Note that `pixelValues` and (`pixelField` or `pixelPrefix`) should not assgined at the same time.
	
	To avoid conflicts with default value (0) for `Null`, all values were shifted to positive numbers, starting from 1.
	
	Parameters:
		eeFeatColl:
			Type: ee.FeatureCollection object
		boundary:
			Type: ee.FeatureCollection object
		pixelValues: custom pixel values, the length should equal size of eeFeatColl
			Type: list
			Default: None
		pixelField: pixel value from field/key in properties
			Type: string
			Default: None
		pixelPrefix: custom prefix of pixelValue, eg: '500', then pixelValue equal '500***'
			Type: integer
			Default: None
		pixelValueFeedback: if `True`, return image and list of actual pixelValues
			Type: boolean
			Default: False
	Returns:
		image and list
	'''
	
	if not boundary:
		boundary = ee.FeatureCollection(eeFeatColl)
	
	lens = eeFeatColl.size().getInfo()
	if pixelValues and len(pixelValues) != lens:
		print('Warning -- length of "pixelValues" did NOT match input eeFeatColl -- %d, %d' %(len(pixelValues), lens))
		pixelValues = None
	
	if pixelField:
		properties = featurePropertyNamesInTable(eeFeatColl)
		if pixelField not in properties:
			print('Warning -- %s was NOT in properties' % pixelField)
			pixelField = None
		valueList_pixelField = propertyToList(eeFeatColl, pixelField).getInfo()
		integerList = integerize(valueList_pixelField, check=True)
		if integerList:
			minimum = min(integerList)
			base_pixelField = max(1 - minimum, 0)
	
	if pixelPrefix:
		base_pixelPrefix = int(pixelPrefix * 10 ** max(3, len(str(lens))))	#at least 4 digits
	
	if pixelValues and ( pixelField or pixelPrefix):
		print('Warning -- "pixelValues" and ( "pixelField" or "pixelPrefix") can NOT work at the same time, the former would be used')
		pixelField = None

	image = ee.Image(0)
	pixelValues_new = []
	for i in range(lens):
		potential_region = ee.Image(image).eq(0)
		feat = getFeatureByIndex(eeFeatColl, i )
		feat_fc = ee.FeatureCollection(feat)	#target feature in ee.FeatureCollection form
		if pixelValues:
			pixelValue = pixelValues[i]
		elif pixelField and not pixelPrefix:
			pixelValue = feat.get(pixelField).getInfo() + base_pixelField
		elif pixelPrefix and not pixelField:
			pixelValue = base_pixelPrefix + i + 1
		elif pixelPrefix and pixelField:
			pixelValue = base_pixelPrefix + feat.get(pixelField).getInfo() + base_pixelField
		else:
			pixelValue = i + 1	#feature index + 1, can not be 0
		pixelValues_new.append(pixelValue)
		
		assigned = ee.Image(pixelValue).clip(feat_fc)
		unMaskImage = assigned.updateMask(potential_region).unmask().clip(boundary)
		image = ee.Image(image).add(unMaskImage)
	return image.cast({'constant':'int16'}) if not pixelValueFeedback else image.cast({'constant':'int16'}), pixelValues_new
	
def imageDownloadUrl(eeImage, scale=1000, crs='EPSG:4326', crs_transform=None, region=None, filePerBand=False):
	'''Get the downloadUrl of an ee.Image
	
	Parameters:
		eeImage: ee.Image to download
			Type: ee.Image object
		scale: resolution in meters per pixel
			Type: integer
			Default: 1000
		crs:
			Type: string, default WGS1984, https://epsg.io/4326
			Default: 'EPSG:4326'
		crs_transform: an array of 6 numbers specifying an affine transform from the specified CRS, 
				in the order: xScale, yShearing, xShearing, yScale, xTranslation and y Translation
			Type: list
			Default: None
		region:
			Type: ee.Geometry or coordinates serialized as a string
			Default: None
		filePerBand: whether to produce a different GeoTIFF per band.
			Type: boolean
			Default: False
	Returns:
		url:
			Type: string
	'''
	region = region if region else eeImage.geometry()
	if crs_transform:
		# NOT WORKING
		url = eeImage.clip(region).getDownloadURL({
				'crs': crs,
				'crs_transform': crs_transform,
				'filePerBand': filePerBand
			})
	else:
		url = eeImage.getDownloadURL({
				'scale': scale,
				'crs': crs,
				'region': region,
				'filePerBand': filePerBand
			})
	return url

def imageDownloader(eeImage, scale=1000, crs='EPSG:4326', crs_transform=None, region=None, filename=None, filePerBand=False):
	'''Download an ee.Image to an GeoTIFF (.tif) file.
	
	Parameters: 
		eeImage: ee.Image to download
			Type: ee.Image object
		scale, crs, crs_transform, region, filePerBand: parameters of `imageDownloadUrl`
		filename: the name of downloaded file
			Type: string, pathlib.Path orbject
			Default: None
	'''
	url = imageDownloadUrl(eeImage, scale=scale, crs=crs, crs_transform=crs_transform, region=region, filePerBand=filePerBand)
	
	#download and save to local. Note that `.zip` is the specified format from the downloadUrl
	r = requests.get(url)
	filenameZip = pathlib.Path('temp%s.zip' % str(int(time.time()*1e6)))
	with open(filenameZip, 'wb') as f:
		f.write(r.content)
	
	#extract
	with zfile(filenameZip) as myzip:
		file = myzip.namelist()[0]
		myzip.extractall()
	
	if filename: pathlib.Path(file).rename(pathlib.Path(filename))
	if filenameZip.name.startswith('temp'): pathlib.Path(filenameZip).unlink()

def vectorize(eeImage, pixelValue, scale=100, region=None, addAreaProperty=False, areaThreshold=0):
	'''Vectorize a specifid pixel value (land use type etc) in a source image.
	
	Parameters:
		eeImage: source image
			Type: ee.Image object
		pixelValue: specified pixel value to vectorize
			Type: integer, float
		scale: resolution in meters per pixel
			Type: integer
			Default: 100
		region:
			Type: ee.Geometry or coordinates serialized as a string
			default: None
		addAreaProperty: if add a `area` property
			Type: boolean
			Default: False
		areaThreshold: if filter by a minimum area
			Type: float, integer
			Default: 0
	Returns:
		eeFeatColl: vectorized feature collection
			Type: ee.FeatureCollection
	'''
	region = region if region else eeImage.geometry()
	#extract specified pixelValue
	extracted = binarize(eeImage, pixelValue=pixelValue, binary=False)
	#vectorize
	eeFeatColl_raw = ( extracted
		.reduceToVectors(
			geometry= region,
			geometryType= 'polygon',
			scale= scale,
			maxPixels= 1e13) )
	
	#add `area` property or not
	if addAreaProperty or areaThreshold:
		eeFeatColl = ( eeFeatColl_raw.map(lambda f: f.set({'area': f.area(1e3)}))
			.filter(ee.Filter.gt('area', areaThreshold)) )
	else:
		eeFeatColl = eeFeatColl_raw
	return eeFeatColl


def downloadIsSuccess(filename):
	'''Check if a file (csv) downloaded from GEE assets is valid
	
	Parameters:
		filename: the name of downloaded file
			Type: string, pathlib.Path orbject
	Returns:
		boolean
	'''
	filename = pathlib.Path(filename)
	if fileIsValid(filename):
		with open(filename) as f:
			firstRecord = f.readline().rstrip()
		fileSize = filename.stat().st_size
		if fileSize >= 50 and firstRecord != 'Internal Earth Engine error.':
			return True
	return False


def taskWaiting(threshold=20, wait_time_random=300):
	'''Since the tasks submitted on GEE server runs one by one, it's NOT a good practice to run too many tasks at same time.
	This function is applied to monitor the status of task list.
	
	Parameters:
		threshold: the number of allowed tasks. If there is more tasks than it, wait; if less than it, continue.
			Type: integer
			Default: 20
		wait_time_random: wait in random seconds to avoid scripts runs at same time. It won't wait, if set it a 'False'.
			Type: integer, boolean
			Default: 300
	'''
	while True:
		tasks = ee.data.getTaskList()[0:100]	# first hundreds tasks
		pendingTasks = [task for task in tasks if task['state'].upper() in ['READY', 'RUNNING']]
		if len(pendingTasks) < threshold:
			print('Info -- number of tasks is less than %d' % threshold)
			break
		else:
			if wait_time_random:
				print('Waiting ...')
				time.sleep(random.randint(0,wait_time_random))

def eeDataCreateAsset(assetId, type='ImageCollection', wait=True):
	'''A wrapper to create an empty ImageCollection or folder and provide a 'wait' option.
	
	Parameters:
		assetId: ID of asset to create
			Type: string
		type: 
			Type: string, one of 'ImageCollection' or 'Folder'
			Default: 'ImageCollection'
		wait: check if it works
			Type: boolean
			Default: True
	'''
	if not ee.data.getInfo(assetId):
		ee.data.createAsset({'type':type}, assetId)
		if wait:
			while not ee.data.getInfo(assetId):
				time.sleep(5)
			print('Succeeded -- create a(n) %s -- %s' % (type, assetId) )
		else:
			print('Reminding -- createAsset task has been submitted without "wait" -- %s' %assetId )

def exportImage2Drive(eeImage, fileNamePrefix, folder ='GEE_outputs',scale=1000,crs='EPSG:4326',region=None,wait=True):
	'''A wrapper to execute a ee.batch.Export.image.toDrive() task.
	
	Parameters:
		eeImage: ee.Image to export
		overwrite: 
			Type: boolean
			Default: True
		wait:
			Type: boolean
			Default: True
	Returns:
		Boolean
	'''
	region = region if region else eeImage.geometry()
	task = ( ee.batch.Export.image.toDrive(
		image= ee.Image(eeImage),
		folder=folder,
		fileNamePrefix=fileNamePrefix,
		description= 'export-%s' % fileNamePrefix,
		crs=crs,
		scale=scale,
		maxPixels=1e13,
		region=region) )
	task.start()
	if wait:
		while task.active():
			time.sleep(30)
		if task.status()['state'] == 'COMPLETED':
			print('Succeeded -- export task %s' % fileNamePrefix )
			return True
		else:
			print('Failed -- export task %s' % fileNamePrefix )
			return False
	else:
		print('Reminding -- export task %s has been submitted -- keyword "wait" is False' % fileNamePrefix )
		return True
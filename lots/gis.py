# -*- coding: utf-8 -*-
"""
* Updated on 2022/12/13
* python3
**
* Geoprocessing in Python
"""
import geopandas as gpd
import numpy as np

import shapely
from shapely.ops import voronoi_diagram as svd
from shapely.ops import transform
from shapely.geometry import Point, Polygon, MultiPolygon
from osgeo import gdal, gdal_array
from collections import Counter
import pyproj
import rioxarray as rxr

import pathlib, subprocess, time, traceback, os, sys

from .util import fileIsValid

from longsgis.longsgis import voronoiDiagram4plg, dropHolesBase, dropHoles

def assignNodataValue(rasterFile, noDataValue):
	'''Assign a specified nodata value by invoking `gdal_edit`.
	
	Parameters:
		rasterFile:
			Type: string, pathlib.PosixPath
		noDataValue: pixel value
			Type: digit, or string of digit
	'''
	rasterFile = pathlib.Path(rasterFile)
	noDataValue = str(noDataValue)
	#subprocess.run(['gdal_edit.py', '-a_nodata', noDataValue, rasterFile])	# works in Ubuntu, but Windows
	gdal_edit_script = pathlib.Path(os.getenv('CONDA_EXE')).parent / 'gdal_edit.py'		# in conda environment
	command = [	sys.executable, gdal_edit_script,
				'-a_nodata', noDataValue,
				rasterFile
				]
	subprocess.run(command)

def gdalBinarize(inputRaster, outputRaster, specifiedPixel, noDataValue=0):
	'''Binarizing a specifid pixel value (land use type etc) in a source raster image by invoking `gdal_calc`.
	
	Parameters:
		inputRaster:
			Type: string, pathlib.PosixPath
		outputRaster:
			Type: string, pathlib.PosixPath
		specifiedPixel: specified pixel to polygonize
			Type: digit, or string of digit
	'''
	inputRaster = pathlib.Path(inputRaster)
	outputRaster = pathlib.Path(outputRaster)
	
	#expression references: https://gdal.org/programs/gdal_calc.html#example , https://gis.stackexchange.com/a/200972
	expression = 'logical_and(A>=%s,A<=%s)' % (specifiedPixel, specifiedPixel)
	gdal_calc_script = pathlib.Path(os.getenv('CONDA_EXE')).parent / 'gdal_calc.py'		# in conda environment
	command = [	sys.executable, gdal_calc_script,
				'-A', inputRaster,
				'--calc=%s' % expression,
				'--outfile=%s' % str(outputRaster),
				'--type=Byte',
				'--NoDataValue=%s' % noDataValue,
				'--co=COMPRESS=LZW',
				'--quiet' #quiet unless error
				]
	subprocess.run(command)

def gdalVectorize(inputRaster, outputVector, specifiedPixel):
	'''Vectorize a specifid pixel value (land use type etc) in a source raster image by invoking `gdal_calc` and `gdal_polygonize`.
	
	Parameters:
		inputRaster:
			Type: string, pathlib.PosixPath
		outputVector:
			Type: string, pathlib.PosixPath
		specifiedPixel: specified pixel to polygonize
			Type: digit, or string of digit	
	'''
	inputRaster = pathlib.Path(inputRaster)
	outputVector = pathlib.Path(outputVector)
	if fileIsValid(outputVector): pathlib.Path(outputVector).unlink()

	tempRaster = pathlib.Path('temp%s.tif' % (str(int(time.time()*1e6))))
	gdalBinarize(inputRaster, tempRaster, specifiedPixel)

	gdal_polygonize_script = pathlib.Path(os.getenv('CONDA_EXE')).parent / 'gdal_polygonize.py'		# in conda environment
	command = [	sys.executable, gdal_polygonize_script,
				'-mask', tempRaster,	# mask option and mask file
				'-q', # quiet unless error
				'-f', 'GeoJSON',	# output format - 'GeoJSON' driver
				tempRaster, 
				outputVector
				]
	subprocess.run(command)
	
	try:
		if fileIsValid(tempRaster): pathlib.Path(tempRaster).unlink()
	except:
		print('-'*60); traceback.print_exc(); print('-'*60)

def gdalRasterize(inputVector, outputRaster, attributeField):
	'''Burns vector geometries into a raster by invoking `gdal_rasterize`.
	
	Parameters:
		inputVector:
			Type: string, pathlib.PosixPath
		outputRaster:
			Type: string, pathlib.PosixPath
		attributeField: specified field to be used for a burn-in value.
			Type: digit, or string of digit	
	'''
	inputVector = pathlib.Path(inputVector)
	outputRaster = pathlib.Path(outputRaster)
	if fileIsValid(outputRaster): pathlib.Path(outputRaster).unlink()
	
	command = [	'gdal_rasterize',		# gdal_rasterize is NOT a script.
				'-ot', 'Int16',
				'-a', attributeField,
				'-tr', '300', '300',
				'-a_nodata', '0',
				'-co', 'COMPRESS=LZW',	# different syntax with `gdal_calc.py`
				'-q', #quiet unless error
				inputVector,
				outputRaster
				]
	subprocess.run(command)

def calcArea(inputVector, outputVector, vectorDriver='GeoJSON', crs='EPSG:4326', areaThreshold=0, sortAscending=False):
	'''For a vector dataset, calculate area and add an `area` key/field, then sort it.
	
	Parameters:
		inputVector:
			Type: string, pathlib.PosixPath
		outputVector:
			Type: string, pathlib.PosixPath
		vectorDriver: format to export, https://gdal.org/drivers/vector/index.html
			Type: string
			Default: 'GeoJSON'
		crs: coordinate reference system to export
			Type: string
			Default: 'EPSG:4326'
		areaThreshold: minimum area when filtering
			Type: float, integer
			Default: 0
		sortAscending: ascending or descending when sorting
			Type: boolean
			Default: False
	'''
	inputVector = pathlib.Path(inputVector)
	outputVector = pathlib.Path(outputVector)
	
	#import data
	vectors = gpd.read_file(inputVector)
	#drop useless columns
	vectors = vectors[['geometry']]
	#calculate and add `area` key/field
	vectors['area'] = vectors.area
	#filter
	vectors = vectors[vectors['area']>areaThreshold]
	#sort by `area`
	vectors = vectors.sort_values(by='area', ascending=sortAscending)
	#re-project
	if vectors.crs != crs: vectors = vectors.to_crs(crs)	#`.crs`, `.set_crs()`, `.to_crs()`
	#export
	vectors.to_file(outputVector, driver=vectorDriver)

def bufferDissolve(gdf, distance, join_style=3):
	'''Create buffer and dissolve thoese intersects.
	
	Parameters:
		gdf: 
			Type: geopandas.GeoDataFrame
		distance: radius of the buffer
			Type: float
	Returns:
		gdf_bf: buffered and dissolved GeoDataFrame
			Type: geopandas.GeoDataFrame
	'''
	#create buffer and dissolve by invoking `unary_union`
	smp = gdf.buffer(distance, join_style).unary_union
	#convert to GeoSeries and explode to single polygons
	gs = gpd.GeoSeries([smp]).explode()
	#convert to GeoDataFrame
	gdf_bf = gpd.GeoDataFrame(geometry=gs, crs=gdf.crs).reset_index(drop=True)
	return gdf_bf

def gdal_clipByMask(inputRaster, outputRaster, mask):
	'''Clipping / extracting a raster by mask.
	
	Parameters:
		inputRaster:
			Type: string, pathlib.PosixPath
		outputRaster:
			Type: string, pathlib.PosixPath
		mask: 
			Type: string, pathlib.PosixPath
	'''
	
	inputRaster = str(pathlib.Path(inputRaster).resolve())
	outputRaster = str(pathlib.Path(outputRaster).resolve())
	mask = str(pathlib.Path(mask).resolve())
	
	outTile = gdal.Warp(
		srcDSOrSrcDSTab = inputRaster,
		destNameOrDestDS = outputRaster,
		cutlineDSName = mask,
		cropToCutline = True
		)
	assert outTile is not None

def stateVector(inputRaster, bandNumber=1):
	'''Calculating a state vector of a categorized image.
	
	Parameters:
		inputRaster:
			Type: string, pathlib.PosixPath
		bandNumber:
			Type: integer
			Default: 1
	Returns:
		List of dictionaries
	'''
	
	inputRaster = str(pathlib.Path(inputRaster).resolve())
	
	# get the pixel size
	rasterData = gdal.Open(inputRaster)
	geotr = rasterData.GetGeoTransform()
	pixelWidth, pixelHeight = abs(geotr[1]), abs(geotr[5])
	unitArea = pixelHeight * pixelWidth
	
	# get the NoDataValue
	band = rasterData.GetRasterBand(bandNumber)	# default '1'
	noDataValue = band.GetNoDataValue()
	
	# calculate proportion
	rasterArray = gdal_array.LoadFile(inputRaster)
	pixelCount = dict(Counter(rasterArray.flatten()))
	listPixel = [{'class': classType, 'area': counts * unitArea }
		for classType, counts in pixelCount.items()
		if classType != noDataValue ]
	total = sum([item['area'] for item in listPixel])
	for item in listPixel:
		item['proportion'] = item['area'] / total
	return listPixel

def transformPoint(crs_original, crs_target, pointCoords):
	'''Transform a geometry of point from original crs to target crs.
	
	Parameters:
		crs_original:
			Type: string of 'EPSG:****'
		crs_target:
			Type: string of 'EPSG:****'
		pointCoords:
			Type: list or shapely.geometry.point.Point
	Returns:
		List of updated coordinates.
	'''
	
	pointCoords = Point(pointCoords)
	crs0 = pyproj.CRS(crs_original)
	crs1 = pyproj.CRS(crs_target)
	project = pyproj.Transformer.from_crs(crs0, crs1, always_xy=True).transform
	return list(transform(project, pointCoords).coords[0])

def segmentedVolume(rasterFile, start = None, stop = None, step = None):
	'''Calculate the elevation-area and elevation-volume curves.
	
	Parameters:
		rasterFile:
			Type: string, pathlib.PosixPath
		start, stop, step: range and interval for elevation
			Type: real, integer
	Returns:
		List of updated coordinates.
	'''
	rasterFile = pathlib.Path(rasterFile)
	dem = rxr.open_rasterio(rasterFile, masked=True).squeeze()
	resolution0 = dem.rio.resolution()[0]	# edge length of grid
	dem = dem.data
	data = dem[~np.isnan(dem)]
	
	start = start if start else data.min()
	stop = stop if stop else data.max()
	step = step if step else (data.max() - data.min())/100.
	
	newData = []
	for stage in np.arange(start, stop + step, step):
		tmp = stage - data
		tmp = tmp[tmp>0]
		area = len(tmp) * resolution0 * resolution0
		volume = tmp.sum() * resolution0 * resolution0
		line = {
					'stage': stage,
					'area': area,
					'volume': volume,
				}
		newData.append(line)
	return newData



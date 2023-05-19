# -*- coding: utf-8 -*-
"""
* Updated on 2023/05/19
* python3 + GEE + GCS
**
* Due to Google Cloud Storage need stand alone credential, so put those functions imported both ee and google.cloud in a stand alone file.
"""

from .util import *
try:
	import ee; ee.Initialize()
except:
	proxy()		# set a proxy for 'earthengineapi'
	import ee; ee.Initialize()

import pathlib, subprocess, time, traceback
import magic

from .gcs import *
from .gee import *

def upload2AssetViaGCS_core(filename, assetId, crs=None, overwrite=True, wait=True):
	'''Upload a geocsv, geotiff file to GEE asset via GCS (Google Cloud Storage).
	
	Parameters:
		filename: file to upload, should has one of 'csv', 'tif' or 'tiff' extensions
			Type: string, pathlib.PosixPath
		assetId: 
			Type: string
		crs:
			Type: string, eg. 'ESPG:4326'
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
	
	filename = pathlib.Path(filename)
	filetype = magic.from_file(str(filename), mime=True)
	if '.CSV' == filename.suffix.upper() and filetype in ['text/plain', 'text/csv', 'application/vnd.ms-excel', 'application/csv']:
		upload_object = 'table'
	elif '.TIF' in filename.suffix.upper() and filetype == 'image/tiff':
		upload_object = 'image'
	else:
		print(type(filetype))
		print(filename, filetype)
		print('Failed -- type error -- current extension: %s, type: %s' % (filename.suffix, filetype))
		return False
	
	if not crs: crs = 'ESPG:4326'	# default crs
	
	fileNameGCS = 'temp' + str(int(time.time()*1e6)) + filename.suffix	#temporaty
		
	try:
		if not overwrite and ee.data.getInfo(assetId):
			print('Failed -- upload -- %s exists' % assetId)
			return False
		else:
			#upload to gcs
			upload_blob(str(filename),fileNameGCS)		#upload; if exist, overwrite
			
			#upload to gee assets
			if not wait:
				subprocess.call(['earthengine', 'upload', upload_object, '--force', 
					'--asset_id=' + assetId, '--crs=' + crs, 'gs://longlovemyu.appspot.com/' + fileNameGCS])
				print('Reminding -- upload task %s has been submitted -- keyword "wait" is False' %assetId )
				return True
			else:							
				subprocess.call(['earthengine', 'upload', upload_object, '--wait', '--force', 
					'--asset_id=' + assetId, '--crs=' + crs, 'gs://longlovemyu.appspot.com/' + fileNameGCS])
			
				#get current task object
				tasks = ee.batch.Task.list()
				task = tasks[0]
				while task.active():
					time.sleep(30)
				if task.status()['state'] == 'COMPLETED':
					#check if the uploaded asset success
					while not ee.data.getInfo(assetId):
						time.sleep(5)
					print('Succeeded -- upload task %s' %assetId )
					return True
				else:
					print('Failed -- upload task %s' %assetId )
					return False
	except:
		print('-'*60); traceback.print_exc(); print('-'*60)
		return False
	finally:
		#remove temporary
		if blob_exists(fileNameGCS): delete_blob(fileNameGCS)

def upload2AssetViaGCS(filename, assetId, crs=None, overwrite=True, wait=True):
	'''A wrapper / preprocessing to upload an image or table to GEE asset via GCS (Google Cloud Storage).

	Parameters:
		filename: file to upload, should be a GeoJSON (.geojson, .json), GeoCSV (.csv) or GeoTIFF (.tif, .tiff) file
			Type: string, pathlib.PosixPath
		assetId: 
			Type: string
		crs:
			Type: string, eg. 'ESPG:4326'
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
	filename = pathlib.Path(filename)
	filetype = magic.from_file(str(filename), mime=True)
	if 'JSON' in filename.suffix.upper() and filetype in ['text/plain', 'application/json']:
		#case - table in geojson format (.geojson, .json)
		filename2 = pathlib.Path('temp%s.csv' % str(int(time.time()*1e6)))
		geojson2csv(filename, filename2, properties = 'all')
	elif '.CSV' == filename.suffix.upper() and filetype in ['text/plain', 'text/csv', 'application/vnd.ms-excel', 'application/csv']:
		#case - table in geocsv format (.csv)
		filename2 = filename
	elif '.TIF' in filename.suffix.upper() and filetype == 'image/tiff':
		#case - image in geotiff format (.tif, .tiff)
		filename2 = filename
	else:
		print('Failed -- type error -- current extension: %s, type: %s' % (filename.suffix, filetype))
		return False
		
	try:
		return upload2AssetViaGCS_core(filename2, assetId, crs=crs, overwrite=overwrite, wait=wait)
	except:
		print('-'*60); traceback.print_exc(); print('-'*60)
		return False
	finally:
		#remove temporary
		if filename2.name.startswith('temp'): pathlib.Path(filename2).unlink()

def downloadImage2GCS(eeImage, description=None, bucket='longlovemyu.appspot.com', scale=500, region=None, 
					crs='EPSG:32650', maxPixels=1.3e11, fileNamePrefix=None, fileFormat='GeoTIFF',
					overwrite=True, wait=True):
	'''
	Parameters:
		eeImage: ee.Image() object to download
			Type: ee.Image object
		description: 
			Type: string
		bucket: Google Cloud Storage bucket
			Type: string
			Default: 'longlovemyu.appspot.com'
		scale: resolution in meters per pixel
			Type: integer
			Default: 500
		region: 
			Type: ee.Geometry
			Default: None
		crs: coordinate reference system
			Type: string
			Default: 'EPSG:32650'
		maxPixels: restrict the number of pixels in the export
			Type: Number
			Default: 1.3e11
		fileNamePrefix: the string used as the output's prefix. A trailing '/' indicates a path.
			Type: string
			Default: None
		fileFormat: one of 'GeoTIFF' and 'TFRecord'
			Type: string
			Default: 'GeoTIFF'
		overwrite:
			Type: boolean
			Default: True
		wait: 
			Type: boolean
			Default: True
	Returns:
		Boolean
	'''
	
	filename = fileNamePrefix + '.tif'
	region = region if region else eeImage.geometry()
	
	if not overwrite and blob_exists(filename):
		print('Failed -- download -- %s exists' % fileNamePrefix)
		return False
	else:
		task = ee.batch.Export.image.toCloudStorage(
						image = eeImage,
						description = description,
						bucket = bucket,
						fileNamePrefix = fileNamePrefix,
						fileFormat = fileFormat,
						scale = scale,
						crs = crs,
						maxPixels = maxPixels,
						region = region	)
		task.start()
		
		if wait:
			#get current task object
			tasks = ee.batch.Task.list()
			current_task = tasks[0]
			
			while current_task.active():
				time.sleep(30)
			
			if current_task.status()['state'] == 'COMPLETED':
				#check if the downloaded file exists
				while not blob_exists(filename):
					time.sleep(5)
				print('Succeeded -- download task %s' %fileNamePrefix )
				return True
			else:
				print('Failed -- download task %s' %fileNamePrefix )
				return False
	
	
			
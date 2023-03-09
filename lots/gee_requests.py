# -*- coding: utf-8 -*-
"""
* Updated on 2020/06/23
* python3 + GEE
"""

from .util import *
try:
	import ee; ee.Initialize()
except:
	proxy()		# set a proxy for 'earthengineapi'
	import ee; ee.Initialize()

import json, pathlib, time, traceback

from copyheaders import headers_raw_to_dict as hr2d
from requests_toolbelt import MultipartEncoder
import requests
import magic

from .gee import *

def upload2AssetByRequests_core(filename, assetId, overwrite=True, wait=True):
	'''Upload a geocsv, geotiff file to GEE asset by an integrated requests and ingesting method based on cookies acquired by Selenium.
	
	Parameters:
		filename: file to upload, should has one of 'csv', 'tif' or 'tiff' extensions
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
	filename = pathlib.Path(filename)
	filetype = magic.from_file(str(filename), mime=True)
	if '.CSV' == filename.suffix.upper() and filetype in ['text/plain', 'text/csv', 'application/vnd.ms-excel', 'application/csv']:
		upload_object = 'table'
		formData_contentType = 'application/vnd.ms-excel'
	elif '.TIF' in filename.suffix.upper() and filetype == 'image/tiff':
		upload_object = 'image'
		formData_contentType = 'image/tiff'
	else:
		print('Failed -- type error -- current extension: %s, type: %s' % (filename.suffix, filetype))
		return False
	
	username = assetId.split('/')[1]
	
	#it will assign onece when globally; so put it locally
	with open('gee_cookies.csv','r') as f:
		cookies = json.loads(f.read())
	
	assert username in cookies
	s = requests.Session()
	for cookie in cookies[username]:
		s.cookies.set(cookie['name'], cookie['value'])

	#STEP1 - request a temporary url for uploading file to GCS
	url_geturl = 'https://code.earthengine.google.com/assets/upload/geturl'
	re=s.get(url_geturl)
	if re.ok:
		'''
		print(re.ok)
		print(re.status_code)
		print(re.content)
		print(repr(re.content))
		print(re.json())
		'''
		url4upload = re.json()['url']
		#print(url4upload)
		print('Succeeded -- request a url to upload file to GCS')
	else:
		print('Failed -- requests.get "geturl"')

	#STEP2 - upload file to GCS and return gs uri / Google Cloud Storage URI
	#print('upload...')
	with open(filename, 'rb') as f:
		file2upload = {'file': (filename.name, f, formData_contentType)}
		#file2upload = {'file': ('001.csv', open('./001.csv', 'rb'),'application/vnd.ms-excel')}
		data = MultipartEncoder(fields=file2upload, boundary='----WebKitFormBoundaryy5ECxxzNHoyR0Tud')
		headers={'Content-Type': data.content_type}	#'formData_contentType' and 'data.content_type' are different
		re = s.post(url4upload, data=data, headers=headers)
	#print(re,'upload finish..')
	if re.ok:
		uri = re.json()
		#print(uri)
		print('Succeeded -- upload file to GCS and get its gs uri')
	else:
		print('Failed -- requests.post file to gs')

	#STEP3 - ingest to Assets
	#assetId = 'users/%s/003' % username
	if upload_object == 'table':
		paras ={
			'id':'projects/earthengine-legacy/assets/%s' % assetId,
			'sources':[{
				'charset':'UTF-8',
				'maxErrorMeters':1,
				'uris':uri
			}]
		}
		resp=ee.data.startTableIngestion(ee.data.newTaskId()[0], paras, allow_overwrite=overwrite)
	elif upload_object == 'image':
		paras ={
			'id': 'projects/earthengine-legacy/assets/%s' % assetId,
			'pyramidingPolicy': 'MEAN',
			'bands':[],
			'maskBands':[],
			'tilesets':[{
				"sources":[{
					"uris":uri
				}]
			}]
		}
		resp=ee.data.startIngestion(ee.data.newTaskId()[0], paras, allow_overwrite=overwrite)
	
	#print(resp)
	if wait:
		task_id = resp['id']
		#print(task_id)
		# find out the task object
		tasks = ee.batch.Task.list()
		#print(tasks[0].id)
		for task in tasks:
			if task.id == task_id: 
				task = task
				break
		#print(task.id)
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
	else:
		print('Reminding -- upload task %s has been submitted -- keyword "wait" is False' %assetId )
		return True

def upload2AssetByRequests(filename, assetId, overwrite=True, wait=True):
	'''A wrapper / preprocessing to upload an image or table to GEE asset by an integrated requests and ingesting method based on cookies acquired by Selenium.

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
		return upload2AssetByRequests_core(filename2, assetId, overwrite=overwrite, wait=wait)
	except:
		print('-'*60); traceback.print_exc(); print('-'*60)
		return False
	finally:
		#remove temporary file
		if filename2.name.startswith('temp'): pathlib.Path(filename2).unlink()
	
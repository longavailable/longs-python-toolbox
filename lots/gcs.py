# -*- coding: utf-8 -*-
"""
* Updated on 2023/03/07
* python3 + Goolgle Cloud Storage
"""

import os
from google.cloud import storage

bucket_name = os.environ['GOOGLE_CLOUD_STORAGE_BUCKET']
storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name)

def upload_blob(source_file_name, destination_blob_name):
	blob = bucket.blob(destination_blob_name)
	blob.upload_from_filename(source_file_name)
	print('Succeeded -- Upload 2 GCS -- %s -> %s' %(source_file_name, destination_blob_name))

def blob_exists(filename):
	blob = bucket.blob(filename)
	if blob.exists():
		print('Succeeded -- GCS -- %s exists' %filename)
	return blob.exists()

def list_blobs(prefix=None):
	'''
	Parameters:
		prefix:
			Type: string
			Default: None
	'''
	blobs = storage_client.list_blobs(bucket_name, prefix=prefix)
	return blobs
	'''
	for blob in blobs:
		print(blob.name)
	'''

def delete_blob(blob_name):
	blob = bucket.blob(blob_name)
	blob.delete()
	print('Succeeded -- Delete from GCS -- %s' % blob_name)

def download_blob(source_blob_name, destination_file_name):
	blob = bucket.blob(source_blob_name)
	blob.download_to_filename(destination_file_name)
	print('Succeeded -- Download from GCS -- %s -> %s' %(source_blob_name, destination_file_name))

def rename_blob(blob_name, new_name):
    blob = bucket.blob(blob_name)
    new_blob = bucket.rename_blob(blob, new_name)
    print('Succeeded -- Blob %s has been renamed to %s' %(blob_name, new_name))
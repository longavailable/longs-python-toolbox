# -*- coding: utf-8 -*-
"""
* Updated on 2023/03/06
* python3
* Usefull tips:
* Add this following line to a script which want to invoke these exporting functions: 
		#invoke custom functions
		import sys
		sys.path.insert(1, '/mnt/d/git/assistants/python/funcs') #WSL linux
		from longspyfuncs import *
* Use <function name> to invoke the specific function directly
"""

import csv, math, os, platform
import pathlib, shutil, traceback, zipfile
from datetime import datetime, date, timedelta
from multiprocessing.dummy import Pool as ThreadPool
from itertools import repeat

import matplotlib as mpl
import pandas as pd

def fileIsValid(filename):
	'''Check if a file exist and non-empty
	
	Parameters:
		filename: file to check
			Type: string, pathlib.Path
	Returns:
		boolean
	'''
	filename = pathlib.Path(filename)
	return True if filename.is_file() and filename.stat().st_size > 0 else False
	'''
	#out-of-date version
	if not os.path.isfile(filename) or os.path.getsize(filename) == 0:
		return False
	else:
		return True
	'''

def clearDir(dirname):
	'''Clear all subs in a dirctory. Create a dirctory if it doesn't exist.
	
	Parameters:
		dirname: dirctory to clear.
			Type: string, pathlib.Path
	'''
	dirname = pathlib.Path(dirname)
	if dirname.is_dir():
		shutil.rmtree(dirname)
	dirname.mkdir(parents=True, exist_ok=True)

#check if a record/log in a file
def recordExist(fileName, record):
	if fileIsValid(fileName):
		with open(fileName) as f:
			records = [line.rstrip() for line in f]
		if str(record) in records:	return True
	return False

def recordExist_dict(filename, filterDict, operator='and'):
	'''Check if a record in a multi columns file.
	
	Parameters:
		filename: base file with headers
			Type: string, pathlib.Path
		filterDict: filters
			Type: dict
		operater: relation between filters, one of 'and', 'or'
			Type: string
			Default: 'and'
	Returns:
		boolean
	'''
	if not fileIsValid(filename): return False
	filterPairs = ['%s==%s' % (str(key), str(value)) for key, value in filterDict.items()]
	expr = (' %s ' % operator).join(filterPairs)
	records = pd.read_csv(filename, low_memory=False)
	return False if records.query(expr).empty else True

#write a record/log or list into a file
def writeLogs(fileName, text):
	if not fileIsValid(fileName):
		if isinstance(text, (str, float, int)):	#single record
			with open(fileName,'w') as f:
				f.write(str(text))
		elif isinstance(text, (list)) and text:	#list-format record(s)
			with open(fileName,'w') as f:
				f.write(str(text[0]))
			if len(text) > 1:
				subText = ['\n' + str(t) for t in text[1:]]
				with open(fileName,'a') as f:
					f.writelines(subText)
	else:
		if isinstance(text, (str, float, int)):	#single record
			with open(fileName,'a') as f:
				f.write('\n' + str(text))
		elif isinstance(text, (list)) and text:	#list-format record(s)
			textNew = ['\n' + str(t) for t in text]
			with open(fileName,'a') as f:
				f.writelines(textNew)
		'''
		with open(fileName,'a+') as f:
			f.write(f.read() + '\n' + text)
		'''

def writeLogsDicts2csv(fileName, dicts):
	'''	Write a list of dictionaries to a csv-format file.
	
	Parameters:
		fileName: output filename
			Type: string, pathlib.PosixPath
		dicts: output list of dictionaries
			Type: list, dictionary
	Returns:
		Boolean
	'''
	try:
		if dicts:
			if not isinstance(dicts, (dict, list)):
				print('Failed -- check if type of object "dict" or "list" of dictionaries')
				return False
			if isinstance(dicts, dict):
				dicts = [dicts]
			headers = dicts[0].keys()
			if not fileIsValid(fileName):
				with open(fileName, 'w', newline='') as f:
					writer = csv.DictWriter(f, fieldnames=headers)
					writer.writeheader()
					writer.writerows(dicts)
					#for d in dicts:
					#	writer.writerow(d)
			else:					
				with open(fileName, 'a', newline='') as f:
					writer = csv.DictWriter(f, fieldnames=headers)
					writer.writerows(dicts)
					#for d in dicts:
					#	writer.writerow(d)
			return True
	except:
		return False

#overwrite a record/log or list into a file
def overwriteLogs(fileName, text):
	if isinstance(text, (str, float, int)):	#single record
		with open(fileName,'w') as f:
			f.write(str(text))
	elif isinstance(text, (list)) and text:	#list-format record(s)
		with open(fileName,'w') as f:
			f.write(str(text[0]))
		if len(text) > 1:
			subText = ['\n' + str(t) for t in text[1:]] + ['\n']
			with open(fileName,'a') as f:
				f.writelines(subText)

#remove a record/log from a file
def removeALog(fileName, text):
	with open(fileName,'r') as f:
		records = [line.rstrip() for line in f]	
	records.remove(text)
	overwriteLogs(fileName, records)

def removeLogs(fileName, text, headers=False):
	'''Remove a record/log or list from a file
	
	Parameters:
		fileName: file to check
			Type: string, pathlib.PosixPath
		text: record(s) to remove
			Type: string, float, int, or list
		headers: if the first line is headers
			Type: bool
	'''
	with open(fileName,'r') as f:
		records = [line.rstrip() for line in f]
	if isinstance(text, (str, float, int)):	#single record
		records.remove(text)
		overwriteLogs(fileName, records)
	elif isinstance(text, (list)) and text:	#list-format record(s)
		if headers:
			records = [records[0]] + list(set(records[1:])-set(text))
		else:
			records = list(set(records)-set(text))
		overwriteLogs(fileName, records)

def hasDuplicates(fileName):
	'''Check if a file has repeated record(s)
	
	Parameters:
		fileName: file to check
			Type: string, pathlib.PosixPath
	Returns: if duplicate(s) exists, then reture duplicate(s), or return False
		Boolean, list
	'''
	with open(fileName,'r') as f:
		records = [line.rstrip() for line in f]
	duplicates = list(set([record for record in records if records.count(record) > 1]))	
	if duplicates:
		print('%s has %d repeated record(s)' % (fileName, len(duplicates)))
		return duplicates
	else:
		print('%s has NO duplicates' % fileName)
		return False

#remove repeated record(s) in a file
def removeDuplicatesRecords(fileName):
	if not fileIsValid(fileName):
		print('%s does NOT exist or is empty' % fileName)
	else:
		if hasDuplicates(fileName):
			with open(fileName,'r') as f:
				records = [line.rstrip() for line in f]	
			recordsWithoutDuplicates = list(dict.fromkeys(records))
			overwriteLogs(fileName, recordsWithoutDuplicates)
			print('Duplicates has been removed')
		else:
			print('Nothing has been removed')

# merge files
def mergeFiles(outputfile,inputfileList):
	if fileIsValid(outputfile):
		with open(outputfile,'a') as fdst:
			for inputfile in inputfileList:
				fdst.write(os.linesep)	#add newline
				if fileIsValid(inputfile):
					with open(inputfile,'r') as fsrc:
						shutil.copyfileobj(fsrc, fdst)
	else:
		with open(outputfile,'w') as fdst:
			for inputfile in inputfileList:
				if fileIsValid(inputfile):
					with open(inputfile,'r') as fsrc:
						shutil.copyfileobj(fsrc, fdst)
				fdst.write(os.linesep)	#add newline
	removeDuplicatesAndEmptyLines(outputfile)
	
def removeEmptyLines(fileName):
	if fileIsValid(fileName):
		with open(fileName,'r') as f:
			records = [line.rstrip() for line in f]
		recordsWithoutDuplicates = list(filter(None, records))
		overwriteLogs(fileName, recordsWithoutDuplicates)

# remove duplicates and empty lines
def removeDuplicatesAndEmptyLines(fileName):
	removeEmptyLines(fileName)
	removeDuplicatesRecords(fileName)

#split a long date interval to a few subinterval by the first day of inside-years
def dateSubintervals(startDate, endDate):
	intervals = []
	
	# to avoid the short subinterval, if it is less than 100days, join to nearby
	daysThreshold = 100
	totalDays = endDate - startDate
	firstYearDays = datetime(startDate.year,12,31) - startDate
	if totalDays.days <= 570:
		year = startDate.year
		if firstYearDays.days < totalDays.days * 0.5:
			year = year + 1
		subinterval = [year, startDate, endDate]
		intervals.append(subinterval)
		return intervals
	else:	
		delta_left = datetime(startDate.year+1,1,1) - startDate
		if delta_left.days > daysThreshold:
			firstYear = startDate.year
		else:
			firstYear = startDate.year + 1
		delta_right = endDate - datetime(endDate.year,1,1)
		if delta_right.days > daysThreshold:
			lastYear = endDate.year + 1
		else:
			lastYear = endDate.year
		
		for year in range(firstYear,lastYear):
			if year == firstYear:
				leftBound = startDate
				rightBound = datetime(year+1,1,1)
			elif year in range(firstYear+1,lastYear-1):
				leftBound = datetime(year,1,1)
				rightBound = datetime(year+1,1,1)
			elif year == lastYear-1:
				leftBound = datetime(year,1,1)
				rightBound = endDate
			subinterval = [year, leftBound, rightBound]
			intervals.append(subinterval)
		return intervals

#convert datetime64 to datetime
def dt64ToDatetime(datetime64):
	ns = 1e-9
	ts = datetime64.astype(int) * ns
	dt = datetime.utcfromtimestamp(ts)
	return dt
#convert pandas datetime(datetime64) to mplDates
def pdDatetime2mplDates(pdDatetime):
	dt = dt64ToDatetime(pdDatetime)
	mplDates = mpl.dates.date2num(dt)
	return mplDates

#read file without comment lines (#)
#return a list
def readFile(fileName):
	if fileIsValid(fileName):
		with open(fileName) as f:
			records = [line.rstrip() for line in f if not line.startswith('#')]
	return records

#compress file to zipfile and check by size
def compress2zip(sourceFile,zipFile,destinationFile):
	if not fileIsValid(zipFile):
		pathlib.Path(zipFile).parent.mkdir(parents=True, exist_ok=True)
		with zipfile.ZipFile(zipFile,'w',compression=zipfile.ZIP_DEFLATED) as myzip:
			myzip.write(sourceFile,destinationFile)
			dest_size = myzip.getinfo(destinationFile).file_size
	else:
		with zipfile.ZipFile(zipFile,'a',compression=zipfile.ZIP_DEFLATED) as myzip:
			if not destinationFile in myzip.namelist():
				myzip.write(sourceFile,destinationFile)
			dest_size = myzip.getinfo(destinationFile).file_size
	source_size = pathlib.Path(sourceFile).stat().st_size
	if source_size == dest_size:
		print('Succeeded -- compress -- %s' % str(destinationFile))
		return True
	else:
		print('Failed -- compress -- %s' %str(destinationFile))
		return False

#check if a file downloaded from GEE assets is valid
def fileInZip(zipFile, fileName):
	if fileIsValid(zipFile):	#zipFile exists
		with zipfile.ZipFile(zipFile) as myzip:
			if fileName in myzip.namelist():	#file exists in zip
				fileSize = myzip.getinfo(fileName).file_size
				if fileSize >= 50:	#filesize check
					return True
	return False

def filelistInZip(zipFile, startswith_str='', contains_str='', endswith_str='', extension=''):
	'''Get filelist in a `.zip` file.
	
	Parameters:
		zipFile: the `.zip` file to request
			Type: string, pathlib.Path object
		startswith_str: 
			Type: string
			Default: ''
		contains_str: 
			Type: string
			Default: ''
		endswith_str: 
			Type: string
			Default: ''
		extension: 
			Type: string
			Default: ''
	Returns:
		list
	'''
	if fileIsValid(zipFile):	#zipFile exists
		with zipfile.ZipFile(zipFile) as myzip:
			return ( [f for f in myzip.namelist() 
				if f.startswith(startswith_str) 
					and f.endswith(endswith_str)
					and f.endswith(extension)
					and contains_str in f]	)

def ordinal(n):
	'''Convert an integer to an orinal.
	'''
	return '%d%s' % (n,'tsnrhtdd'[(math.floor(n/10)%10!=1)*(n%10<4)*n%10::4])

def allAreIntegers(listInput):
	'''Check if all items in a list are integers or integer strings.
	
	This function addressed four cases:
	- [1, 2, 3]
	- [1.0, 2.0, 3.0]
	- ['1', '2', '3']
	- ['1.0', '2.0', '3.0']
	
	Parameters:
		listInput: the list to check
			Type: list
	Returns:
		boolean
	'''
	if isinstance(listInput, list):
		try:
			#case 1 -- list of integers, eg, [1, 2, 3]
			bool01 = [isinstance(l, int) for l in listInput]
			if all(bool01): return True
			
			#case 2 -- list of integers in float form, eg, [1.0, 2.0, 3.0]
			bool02 = [isinstance(l, float) for l in listInput]
			if all(bool02):
				bool0201 = [int(l) == l for l in listInput]
				if all(bool0201): return True
			
			#case 3 -- list of strings, eg, 
			#string of integers ['1', '2', '3']
			#string of integers in float form ['1.0', '2.0', '3.0']
			bool03 = [isinstance(l, str) for l in listInput]
			if all(bool03):
				bool0301 = [int(float(l)) == float(l) for l in listInput]
				if all(bool0301): return True
			
			#unmentioned cases
			return False
		except:
			print('-'*60); traceback.print_exc(); print('-'*60)
			return False
	else:
		return False

def integerize(listInput, check=True):
	'''Convert a list of four cases mentioned in `allAreIntegers` function to a list of integers.
	
	Parameters:
		listInput: the list to convert
			Type: list
		check: do the `allAreIntegers` check
			Type: boolean
			Default: True
	Returns:
		list or boolean (False)
	'''
	if check:
		if allAreIntegers(listInput):
			return [int(float(l)) for l in listInput]
	try:
		return [int(float(l)) for l in listInput]	#more than four cases, eg, mixed, and general floats -- '1.012' will return 1
	except:
		print('-'*60); traceback.print_exc(); print('-'*60)
		return False

def proxy(ip='', port='10809'):
	'''A proxy setting fuction.
	
	Parameters:
		ip: 
			Type: string
		port: 
			Type: strong, integer
			Default: '10809'
	Returns:
		None
	'''
	if ip:
		os.environ['HTTP_PROXY'] = 'http://%s:%s' % (ip, port)
		os.environ['HTTPS_PROXY'] = 'http://%s:%s' % (ip, port)
	else:
		if platform.system()=='Windows':
			import socket
			hostip = socket.gethostbyname(socket.gethostname())
			os.environ['HTTP_PROXY'] = 'http://%s:%s' % (hostip, port)
			os.environ['HTTPS_PROXY'] = 'http://%s:%s' % (hostip, port)
		if platform.system()=='Linux': # wsl2
			import subprocess
			winip = ( subprocess.run(['grep', 'nameserver', '/etc/resolv.conf'], capture_output=True)	# get nameserver
				.stdout					# get output
				.decode('utf-8')		# convert byte-like object to string
				.rstrip()				# remove '\n'
				.split(' ')[-1]	)		# get the ip
			os.environ['HTTP_PROXY'] = 'http://%s:%s' % (winip, port)
			os.environ['HTTPS_PROXY'] = 'http://%s:%s' % (winip, port)
		
def addDays(startDate, n, skip_leap_days=False):
	'''A function to operate addition for a date.
	
	Parameters:
		startDate:
			Type: datetime.date
		n:
			Type: int
		skip_leap_days:
			Type: boolean
			Default: False
	Returns:
		A datetime.date object
	'''
	d = startDate + timedelta(n)
	if skip_leap_days and d.month==2 and d.day==29: return None
	return d

def daterange(startDate, endDate, skip_leap_days=False):
	'''A function to abstract the iteration over the range of dates.
	
	Parameters:
		startDate:
			Type: datetime.date
		endDate:
			Type: datetime.date
		skip_leap_days:
			Type: boolean
			Default: False
	Returns:
		A list
	'''
	
	'''
	for n in range(int((endDate - startDate).days)):
		yield startDate + timedelta(n)
	'''
	
	'''
	# single thread version
	dates = []
	for n in range(int((endDate - startDate).days)):
		d = addDays(startDate, n, skip_leap_days)
		dates = dates + [d]
	return dates
	'''
	# parallel
	pool = ThreadPool(4)
	dates = pool.starmap(addDays, zip(repeat(startDate), list(range(int((endDate - startDate).days))), repeat(skip_leap_days)))
	pool.close()
	pool.join()
	return list(filter(lambda d: d is not None, dates))

def is_number(string):
	'''Check if the string is number.
	'''
	try:
		float(string)
		return True
	except ValueError:
		pass

	try:
		int(string)
		return True
	except ValueError:
		return False

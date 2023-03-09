# -*- coding: utf-8 -*-
"""
* Updated on 2022/12/13
* python3
**
* test of segmentedVolume
"""
import pathlib
from lots.util import fileIsValid, writeLogsDicts2csv
from lots.gis import segmentedVolume

file_dem = pathlib.Path('gis/dem.gpkg')
filename = 	pathlib.Path('segmented-volume.csv')
if not fileIsValid(filename):
	start, stop, step = 0.5, 2, 0.05
	#data = segmentedVolume(file_dem)	# default range and interval for segmentation
	data = segmentedVolume(file_dem, start, stop, step)
	writeLogsDicts2csv(filename, data)
else:
	print('%s exists' % filename.name)

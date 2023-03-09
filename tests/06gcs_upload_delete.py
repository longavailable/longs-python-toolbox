# -*- coding: utf-8 -*-
"""
*2020/08/01
*test for GCS
"""
import pathlib
from lots.gcs import *

file = pathlib.Path('gis/input.geojson')
filename_gcs = 'mega/test000.geojson'
upload_blob(str(file),filename_gcs)
delete_blob(filename_gcs)
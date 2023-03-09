# -*- coding: utf-8 -*-
"""
*2020/08/01
*test for invoking gee function
"""

import ee; ee.Initialize()
from lots.gee import *

ydm = ee.FeatureCollection('users/XiaolongLiu/mega/cn/ydm/vector/YDM_domain_buffer10_pcs')
filename = 'gis/ydm.geojson'
downloader(ydm, filename)
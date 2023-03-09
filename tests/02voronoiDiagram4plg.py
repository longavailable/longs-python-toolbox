"""
*2020/08/01
*test for invoke published package -- voronoi-diagram-for-polygons
"""

import geopandas as gpd
from lots.gis import voronoiDiagram4plg

builtup = gpd.read_file('gis/input.geojson')
boundary = gpd.read_file('gis/boundary.geojson')
vd = voronoiDiagram4plg(builtup, boundary)
vd.to_file('gis/output.geojson', driver='GeoJSON')
import os
import trimesh
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
import numpy as np

from shapely.geometry import LineString
from shapely.affinity import rotate
from slice_topology import boundaries_and_holes


import heapq
from shapely import Point


def create_infill_lines(xline_min,xline_max,yline_min,yline_max,centroid, D,W,line_angle):
    line_spacing=W/D
    infill_lines=[]
    x=xline_min
    while x<xline_max:
        line=LineString([(x,yline_min),(x,yline_max)])
        line=rotate(line,line_angle,origin=centroid)
        infill_lines.append(line)
        x+=line_spacing

    rotated_infill_lines=[]
    for line in infill_lines:
        line=rotate(line,90,origin=centroid)
        rotated_infill_lines.append(line)
    return infill_lines,rotated_infill_lines




def find_infill_segments(slice,infill_lines,buffer_offset=0.4):
    
    slice_infill_segments=[]
    slice_scanline_indices = []
    printable_region=Polygon()
    full_region=Polygon()
    
    all_polygons=slice["outer"]+slice["inner"]
    all_polygons=sorted(all_polygons,key=lambda x:x.area,reverse=True)

    for poly in all_polygons:
        if poly in slice["outer"]:
            bufferpoly = poly.buffer(-buffer_offset)
            full_region=full_region.union(poly)
            printable_region=printable_region.union(bufferpoly)
        else:
            bufferpoly = poly.buffer(buffer_offset)
            full_region=full_region.difference(poly)
            printable_region=printable_region.difference(bufferpoly)

    for scanline_index,line in enumerate(infill_lines):
        segment=line.intersection(printable_region)
        if not segment.is_empty:
            slice_infill_segments.append(segment)
            slice_scanline_indices.append(scanline_index)

    return [slice_infill_segments,all_polygons,full_region,printable_region,slice_scanline_indices]




        
def generate_infill(stl_path,D,W,line_angle):
    
    mesh=trimesh.load_mesh(stl_path)
    slices=boundaries_and_holes(stl_path ,z_increment=0.4,threshold_area=0)

    extremes=mesh.bounds
    x_min,y_min,z_min=extremes[0][:]
    x_max,y_max,z_max=extremes[1][:]
    length=x_max-x_min
    width=y_max-y_min
    diag=np.sqrt(length**2+width**2)

    xline_min=x_min-diag
    xline_max=x_max+diag
    yline_min=y_min-diag
    yline_max=y_max+diag

    centroid=((x_min+x_max)/2,(y_min+y_max)/2)

    infill_lines,rotated_infill_lines=create_infill_lines(xline_min,xline_max,yline_min,yline_max,centroid,D,W,line_angle)

    infill={}

    for level,slice in enumerate(slices.values()):
        if level%2==0:
            infill[level]=find_infill_segments(slice,infill_lines)
        else:
            infill[level]=find_infill_segments(slice,rotated_infill_lines)
    return infill
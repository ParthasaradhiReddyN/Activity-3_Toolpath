from shapely.ops import substring


from infill import generate_infill

import os
import trimesh
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
import numpy as np

from shapely.geometry import LineString,MultiLineString
from shapely.affinity import rotate
from slice_topology import boundaries_and_holes


from shapely.ops import substring
import heapq
from shapely import Point
import matplotlib.pyplot as plt

import shutil

def list_idx_segment(slice_scanline_indices, infill_segments):
    segments=[]    #store idx and Line strings. if multi split into line string and give same idx for them
    
    for scanline_index, geometry in zip(slice_scanline_indices, infill_segments):

        if geometry.geom_type == "LineString":
            segments.append({
                "scanline": scanline_index,
                "geometry": geometry
            })

        elif geometry.geom_type == "MultiLineString":
            for line in geometry.geoms:
                segments.append({
                    "scanline": scanline_index,
                    "geometry": line
                })
    return segments


def dict_idx_segments(segments):
    remaining = {}
            
    for item in segments:
            if item["scanline"] not in remaining:
                remaining[item["scanline"]]=[item["geometry"]]
            else:
                remaining[item["scanline"]].append(item["geometry"])
    return remaining



def boundary_connector(start, end, final_region, slice_polygon):

    start = Point(start)
    end = Point(end)
   
    # Get all polygons
    if final_region.geom_type == "Polygon":
        polygons = [final_region]
    else:
        polygons = list(final_region.geoms)

    for poly in polygons:

        # Get exterior and interior rings
        rings = [poly.exterior] + list(poly.interiors)

        for ring in rings:

            ring_line = LineString(ring.coords)

            # Both points must lie on the same boundary ring
            if ring_line.distance(start) > 1e-6:
                continue

            if ring_line.distance(end) > 1e-6:
                continue

            # Get distances along the ring
            d1 = ring_line.project(start)
            d2 = ring_line.project(end)

            length = ring_line.length
            lo, hi = sorted((d1, d2))

            # Calculate both possible paths
            path1 = list(substring(ring_line, lo, hi).coords)

            path2 = (
                list(substring(ring_line, hi, length).coords)
                + list(substring(ring_line, 0, lo).coords)[1:]
            )
            # Select the shorter path
            if (hi - lo) <= (length - (hi - lo)):
                coords = path1
                forward = d1 <= d2
            else:
                coords = path2
                forward = d1 >= d2

            if not forward:
                coords.reverse()

            if len(coords) < 2:
                continue

            coords[0] = (start.x, start.y)
            coords[-1] = (end.x, end.y)

            path = LineString(coords)

            if slice_polygon.covers(path):
                return path
    return None



def plot(z,all_polygons,toolpath):
    # Plot toolpath
    fig, ax = plt.subplots(figsize=(10, 10))

    # Plot actual outer and inner boundaries
    for poly in all_polygons:

        # Exterior boundary
        x, y = poly.exterior.xy
        ax.plot(
            x, y,
            color="black",
            linewidth=1.5,
            label="Actual boundary"
        )

        # Interior holes
        for hole in poly.interiors:
            x, y = hole.xy
            ax.plot(
                x, y,
                color="black",
                linewidth=1.2
            )

    # Plot generated toolpath
    for item in toolpath:

        geometry = item["geometry"]

        if geometry.is_empty:
            continue

        x, y = geometry.xy

        if item["type"] == "INFILL":
            ax.plot(
                x, y,
                color="blue",
                linewidth=1,
                label="Infill"
            )

        elif item["type"] == "EXTRUSION":
            ax.plot(
                x, y,
                color="green",
                linewidth=1.5,
                label="Extrusion connector"
            )

        elif item["type"] == "TRAVEL":
            ax.plot(
                x, y,
                color="red",
                linewidth=1.2,
                linestyle="--",
                label="Travel connector"
            )

    # Plot start and end points only once
    if toolpath:

        start_point = toolpath[0]["geometry"].coords[0]
        end_point = toolpath[-1]["geometry"].coords[-1]

        ax.scatter(
            *start_point,
            color="lime",
            edgecolors="black",
            s=70,
            zorder=5,
            label="Start point"
        )

        ax.scatter(
            *end_point,
            color="red",
            edgecolors="black",
            s=70,
            zorder=5,
            label="End point"
        )

    # Formatting
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(f"Toolpath Visualization - Z = {z}")
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.grid(True, linestyle=":", alpha=0.5)

    # Remove duplicate legend entries
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))

    ax.legend(
        by_label.values(),
        by_label.keys(),
        loc="best"
    )

    plt.tight_layout()

    # Save image
    os.makedirs("toolpath", exist_ok=True)

    plt.savefig(
        f"toolpath/toolpath_Z_{z}.png",
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()

    print(f"Toolpath image saved: toolpath/toolpath_Z_{z}.png")



def check_connectors(line,all_infill_lines,printed_connectors):
    clear=True
    for infill_line in all_infill_lines:
        if line.intersects(infill_line):
            clear = False
            break

    if clear:
        for previous_connector in printed_connectors:
            if line.intersects(previous_connector):
                clear = False
                break
    return clear



def check_infill_endpoint_collision(connector,all_infill_lines,selected_point,tolerance=1e-5):
    for infill_line in all_infill_lines:

        endpoints = [
            Point(infill_line.coords[0]),
            Point(infill_line.coords[-1])
        ]

        for endpoint in endpoints:

            # Allow the intended destination endpoint
            if endpoint.distance(Point(selected_point)) <= tolerance:
                continue

            # Reject contact with other infill endpoints
            if connector.distance(endpoint) <= tolerance:
                return False

    return True

def generate_toolpath(stl_path="models/benchy.stl",D=0.25,W=0.4,line_angle=0):
    shutil.rmtree("toolpath", ignore_errors=True)
    all_toolpaths={}
    line_spacing=W/D
    # Connector limits
    max_connector_length = 1.5* line_spacing
    # max_arc_length = 4 * line_spacing
    line_offset = 1e-4
    infill=generate_infill(stl_path,D,W,line_angle)
    for z, data in infill.items():
        infill_segments=data[0]
        all_polygons=data[1]
        slice_polygon=data[2]
        final_region=data[3]
        slice_scanline_indices = data[4]

        segments=list_idx_segment(slice_scanline_indices, infill_segments)


        remaining = dict_idx_segments(segments)
    
        all_infill_lines = [item["geometry"] for item in segments]   #all linestrings -to check for crossings
    
        
        printed_connectors = []  #store printed connectors
    
        first_scanline = min(remaining.keys())
        first_segment = remaining[first_scanline].pop(0)
        toolpath = []    #initialize toolpath
        position = first_segment.coords[-1]
    
        # Store first infill segment
        toolpath.append({"type": "INFILL", "geometry": first_segment})
    
        current_scanline = first_scanline

        #Repeating until all segments are processed
        while sum(len(v) for v in remaining.values()) > 0:
            selected_segment_index = None
            selected_point = None
            selected_scanline = None
            selected_connector = None
            connector_type = None
    
            #Search scanlines by increasing distance
            active_scanlines = [s for s,v in remaining.items() if v]
    
            levels = sorted(set(abs(s - current_scanline) for s in active_scanlines))
    
            for diff in levels:
                if diff==0:
                    scanlines_to_check =[current_scanline]
                else:
                    scanlines_to_check =[
                        current_scanline - diff,
                        current_scanline + diff
                    ]
    
                nearest_points = []
    
                for scanline in scanlines_to_check:
    
                    if scanline not in remaining:
                        continue
    
                    for i, segment in enumerate(remaining[scanline]):
                        nearest_points.append((scanline, i, segment.coords[0]))
                        nearest_points.append((scanline, i, segment.coords[-1]))
    
                # Check  nearest_points first
                nearest_points.sort(
                    key=lambda x: Point(position).distance(Point(x[2]))
                )
    
                for scanline, segment_index, point in nearest_points:
    
                    connector = LineString([position, point])

                    clear = False
                    selected_connector = None
                    connector_type = None

                    # STEP 1: Try direct connector
                    if (connector.length <= max_connector_length
                            and final_region.buffer(1e-6).covers(connector)):

                        if connector.length > 2 * line_offset:

                            core = substring(connector,line_offset,connector.length - line_offset)
                            clear = check_connectors(core,all_infill_lines,printed_connectors)

                        if clear:
                            selected_connector = connector
                            connector_type = "EXTRUSION"
                            

                    # STEP 2: Try boundary connector if direct fails
                    if not clear:
                        boundary_path = boundary_connector(position,point,final_region,slice_polygon)

                        # if (boundary_path is not None and boundary_path.length <= max_arc_length)):
                        if (boundary_path is not None):
                            if boundary_path.length > 2 * line_offset:
                                
                                core = substring(boundary_path,line_offset,boundary_path.length - line_offset)
                                clear = check_connectors(core,all_infill_lines,printed_connectors)
                            else:
                                clear = False

                            if clear:
                                selected_connector = boundary_path
                                connector_type = "EXTRUSION"

                    if clear:
                        clear = check_infill_endpoint_collision(
                                core,
                                all_infill_lines,
                                point
                            )

                    # STEP 3: Reject this candidate if both fail
                    if not clear:
                        continue

                    # Valid extrusion connector
                    selected_segment_index = segment_index
                    selected_point = point
                    selected_scanline = scanline
                    break
    
                if selected_segment_index is not None:
                    break
    
            # If no valid extrusion connector exists, use nearest endpoint for travel
            if selected_segment_index is None:
                nearest_points = []
                for scanline in remaining:
                    for i, segment in enumerate(remaining[scanline]):
                        nearest_points.append((scanline, i, segment.coords[0]))
                        nearest_points.append((scanline, i, segment.coords[-1]))
    
                selected_scanline, selected_segment_index, selected_point = min(
                    nearest_points,
                    key=lambda x: Point(position).distance(Point(x[2]))
                )
    
                connector = LineString([position, selected_point])
                connector_type = "TRAVEL"
    
            # Select the segment
            selected_segment = remaining[selected_scanline].pop(selected_segment_index)
    
            # Reverse if entering from the last endpoint
            if selected_point == selected_segment.coords[-1]:
                selected_segment = LineString(list(selected_segment.coords)[::-1])
    
            # Store connector
            if connector_type == "EXTRUSION":
                connector = selected_connector
                printed_connectors.append(connector)
                
    
            toolpath.append({"type": connector_type,"geometry": connector})
            toolpath.append({"type": "INFILL","geometry": selected_segment})

            # Update current position
            position = selected_segment.coords[-1]
            current_scanline = selected_scanline
        plot(z,all_polygons,toolpath)
        all_toolpaths[z]=toolpath
    return all_toolpaths

print(generate_toolpath())
import os
import trimesh
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient


from H_slicing import slice


#Creating shapely geometries
#input: slices
#output: Dictionary of slice wise shapely geometries
def create_shapely_geometries(slices):
    shapely_geometries={}

    for slice in slices:
        geometry=[]
        projected_geometry = slice["projected_geometry"]

        for curve in projected_geometry:
            polygon=Polygon(curve)
            geometry.append(polygon)
        shapely_geometries[slice["z_height"]]=geometry

    return shapely_geometries

#Identification of inner holes and outer boundaries
#input: shapely geometries, threshold area
#output: slice wise inner holes, outer boundaries and outer with holes

def classify_inner_outer(shapely_geometries,threshold_area):
    classified_contours={}
    for slice_key,polygons in shapely_geometries.items():

        valid_polygons=[]                    #degenrate contours and removing contours with area less than threshold area
        for polygon in polygons:
            if not polygon.is_valid:
                continue
            if polygon.area < threshold_area:
                continue

            valid_polygons.append(polygon)
            
        n_polygons=len(valid_polygons)

        parent=[-1 for i in range(n_polygons)]
        valid_polygons=sorted(valid_polygons,key=lambda x:x.area,reverse=True)

        #Depth based classification of contours
        containment_matrix=[[0]*n_polygons for i in range(n_polygons)]

        for i in range(n_polygons):
            for j in range(i+1,n_polygons):
                if valid_polygons[i].contains(valid_polygons[j]):
                    containment_matrix[j][i]=-1
                    parent[j]=i
        
        outer=[]
        inner=[]
        outer_with_holes={}

        for i,polygon in enumerate(valid_polygons):
            depth=-sum(containment_matrix[i])
            if depth%2==0:
                polygon= orient(polygon,sign=1.0)
                outer.append(polygon) 
            else:
                polygon=orient(polygon,sign=-1.0)
                inner.append(polygon)

        #polygons is original un-oriented list.so while checking need to check orientation also

        for i,polygon in enumerate(valid_polygons):
                if orient(polygon,sign=-1) in inner:
                    parent_polygon=orient(valid_polygons[parent[i]],sign=1)
                    if parent_polygon not in outer_with_holes:
                        outer_with_holes[parent_polygon] = [orient(polygon,sign=-1)]
                    else:
                        outer_with_holes[parent_polygon].append(orient(polygon,sign=-1))

        classified_contours[slice_key]={"outer":outer,"inner":inner,"outer_with_holes":outer_with_holes}
    # print(classified_contours)
    return classified_contours



def boundaries_and_holes(stl_path="models/1squares.stl",z_increment=0.4,threshold_area=1):
    #Get slices
    slices=slice(stl_path, z_increment)

    shapely_geometries=create_shapely_geometries(slices)
    classified_contours=classify_inner_outer(shapely_geometries,threshold_area)
    
    return classified_contours

# print(boundaries_and_holes(stl_path="3DBenchyRepaired.stl",z_increment=0.4,threshold_area=0))





        


import os
import trimesh

#Create horizontal slicing planes (Z=z) parallel to XY plane
#input: Z min , Z max , plane spacing
#output: List of slicing planes
def create_z_planes(z_min,z_max,z_increment):
    z_planes=[]
    z=z_min
    while z<=z_max:
        z_planes.append(z)
        z+=z_increment
    return z_planes


#Finding mesh plane intersections
#input: slicing planes, mesh
#output: Slice wise interesections Dictionary
def mesh_plane_intersections(z_planes,mesh,z_increment):
    intersections={}
    for z in z_planes:
        plane_normal=[0,0,1]
        plane_origin=[0,0,z]
        intersection=mesh.section(plane_normal=plane_normal,plane_origin=plane_origin)
        if intersection==None:
            intersection=mesh.section(plane_normal=plane_normal,plane_origin=[0,0,z-z_increment])
            if intersection==None:
                        intersection=mesh.section(plane_normal=plane_normal,plane_origin=[0,0,z+z_increment])

        intersections[z]=intersection

    return intersections



#Convert 3D to 2D coordinates
#input: intersections
#output: List [{Z_height:z,raw_curves:[], 2d_projected_geometry:[]}]
def final_3d_2d_curves(intersections):
    slices=[]
    use_2d=[]
    for i in intersections:
        if intersections[i] ==None:
            slices.append({"z_height":i,"raw_curves":[],"projected_geometry":[]})
            continue
        raw_curves=intersections[i].discrete
        projected_geometry = [curve[:, :2] for curve in raw_curves]
        slices.append({"z_height":i,
                       "raw_curves":raw_curves,
                       "projected_geometry":projected_geometry})

    return slices



def slice(stl_path="models/1squares.stl",z_increment=0.4):
    mesh=trimesh.load_mesh(stl_path)   #Load STL

    bound_box = mesh.bounding_box      #Calculate axis aligned bounding box

    extremes=mesh.bounds               #Find X,Y,Z extremes
    x_min = extremes[0][0]
    y_min = extremes[0][1]
    z_min = extremes[0][2]
    x_max = extremes[1][0]
    y_max = extremes[1][1]
    z_max = extremes[1][2]
    print("Z min:", z_min, "Z max:", z_max)

    #creating z_planes
    z_planes=create_z_planes(z_min,z_max,z_increment)

    #find mesh and plane intersection
    intersections=mesh_plane_intersections(z_planes,mesh,z_increment)

    #find raw_curves,2d_curves for each z
    slices=final_3d_2d_curves(intersections)

    return slices


# print(slice(stl_path="models/tetra.stl",z_increment=0.4))








    




"""For reading, writing and manipulating MULgraph geometry grids."""

"""
Copyright 2011 University of Auckland.

This file is part of PyTOUGH.

PyTOUGH is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

PyTOUGH is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with PyTOUGH.  If not, see <http://www.gnu.org/licenses/>."""

from string import ljust,rjust,lowercase,uppercase
from geometry import *

def padstring(string,length=80): return ljust(string,length)
def IntToLetters(i,st='',casefn=lowercase):
    """Converts a number into a string of letters, either lower or upper case."""
    if i==0: return st
    else: return IntToLetters((i-1)/26,casefn[(i-1)%26]+st,casefn)
def LettersToInt(st):
    """Converts a string into a number equivalent- the inverse of IntToLetters."""
    lst=st.lower()
    ord0=ord('a')-1
    def myord(s):
        if s==' ': return 0
        else: return ord(s)-ord0
    n=len(st)
    return sum([myord(s)*(26**(n-i-1)) for i,s in enumerate(lst)])

def fix_blockname(name):
    """Fixes blanks in 4th column of block names, caused by TOUGH2 treating names as (a3,i2)"""
    if name[2].isdigit() and name[4].isdigit() and name[3]==' ': char4='0'
    else: char4=name[3]
    return name[0:3]+char4+name[4:5]

def unfix_blockname(name):
    """The inverse of fix_blockname()."""
    return name[0:3]+"%2d"%int(name[3:5])

def fortran_float(s):
    """Returns float of a string written by Fortran.  Sometimes when Fortran writes out very small values,
    and encounters underflow, it appears to drop the 'E' exponent. This functions traps such errors."""
    try: v=float(s)
    except ValueError:
        try: # underflow in exponent sometimes deletes 'e':
            v=float(s.replace('-','e-'))
        except ValueError: # give up
            v=0.0
    return v

class quadtree(object):
    """Quadtree for spatial searching in 2D grids."""
    def __init__(self,bounds,elements,parent=None):
        self.parent=parent
        if self.parent: self.generation=self.parent.generation+1
        else: self.generation=0
        self.bounds=bounds
        self.elements=elements
        self.child=[]
        if self.num_elements>1:
            rects=sub_rectangles(self.bounds)
            rect_elements=[[],[],[],[]]
            for elt in self.elements:
                for irect,rect in enumerate(rects):
                    if in_rectangle(elt.centre,rect):
                        rect_elements[irect].append(elt)
                        break
            for rect,elts in zip(rects,rect_elements):
                if len(elts)>0: self.child.append(quadtree(rect,elts,self))
    def __repr__(self): return self.bounds.__repr__()
    def get_num_elements(self): return len(self.elements)
    num_elements=property(get_num_elements)
    def get_num_children(self): return len(self.child)
    num_children=property(get_num_children)
    def search_wave(self,pos):
        from copy import copy
        todo=copy(self.elements)
        done=[]
        while len(todo)>0:
            elt=todo.pop(0)
            if elt.contains_point(pos): return elt
            done.append(elt)
            for nbr in elt.neighbour:
                if rectangles_intersect(nbr.bounding_box,self.bounds) and not ((nbr in done) or (nbr in todo)):
                    todo.append(nbr)
        return None
    def search(self,pos):
        leaf=self.leaf(pos)
        if leaf: return leaf.search_wave(pos)
        else: return None
    def leaf(self,pos):
        if in_rectangle(pos,self.bounds):
            for child in self.child:
                childleaf=child.leaf(pos)
                if childleaf: return childleaf
            return self
        else: return None
    def plot(self,plt=None):
        if plt==None: import matplotlib.pyplot as plt
        x=[self.bounds[0][0],self.bounds[1][0],self.bounds[1][0],self.bounds[0][0],self.bounds[0][0]]
        y=[self.bounds[0][1],self.bounds[0][1],self.bounds[1][1],self.bounds[1][1],self.bounds[0][1]]
        plt.plot(x,y,'.--')
        for child in self.child: child.plot(plt)
    
class node(object):
    """Grid node class"""
    def __init__(self,name='   ',pos=np.array([0.0,0.0])):
        self.name=name
        if isinstance(pos,list) or isinstance(pos,tuple): pos=np.array(pos)
        self.pos=pos
        self.column=set([])
    def __repr__(self): return self.name

class column(object):
    """Grid column class"""
    def __init__(self,name='   ',node=[],centre=None,surface=None):
        self.name=name
        self.node=node
        if centre==None:
            self.centre_specified=0
            if self.num_nodes>0: self.centre=self.centroid
            else: self.centre=None
        else:
            self.centre_specified=1
            self.centre=centre
        self.surface=surface
        self.get_area()
        if self.area<0.: # check node numbering orientation
            self.node.reverse()
            self.area=-self.area
        self.neighbour=set([])
        self.connection=set([])
        self.num_layers=0

    def get_num_nodes(self): return len(self.node)
    num_nodes=property(get_num_nodes)
    def get_num_neighbours(self): return len(self.neighbour)
    num_neighbours=property(get_num_neighbours)

    def get_surface(self): return self._surface
    def set_surface(self,val):
        self._surface=val
        if val==None: self.default_surface=True
        else: self.default_surface=False
    surface=property(get_surface,set_surface)
        
    def is_against(self,col):
        """Returns True if the column is against the specified other column- that is, if it shares more than one node with it."""
        return len(set(self.node).intersection(set(col.node)))>1

    def get_polygon(self):
        """Returns polygon formed by node positions."""
        return [node.pos for node in self.node]
    polygon=property(get_polygon)

    def get_area(self):
        """Calculates column area"""
        self.area=polygon_area(self.polygon)

    def get_centroid(self):
        """Returns column centroid"""
        return sum(self.polygon)/self.num_nodes
    centroid=property(get_centroid)

    def get_bounding_box(self):
        """Returns (horizontal) bounding box of the column."""
        return bounds_of_points([node.pos for node in self.node])
    bounding_box=property(get_bounding_box)
        
    def near_point(self,pos):
        """Returns True if pos is within the bounding box of the column."""
        return in_rectangle(pos,self.bounding_box)

    def contains_point(self,pos):
        """Determines if specified point is inside the column."""
        return in_polygon(pos,self.polygon)

    def in_polygon(self,polygon):
        """Returns true if the centre of the column is inside the specified polygon."""
        return in_polygon(self.centre,polygon)

    def get_exterior_angles(self):
        """Returns list of exterior angle for each node in the column."""
        side=[self.node[i].pos-self.node[i-1].pos for i in xrange(self.num_nodes)]
        h=[vector_heading(s) for s in side]
        angles=[np.pi-(h[(i+1)%self.num_nodes]-h[i]) for i in xrange(self.num_nodes)]
        angles=[a%(2*np.pi) for a in angles]
        return angles
    exterior_angles=property(get_exterior_angles)
    def get_interior_angles(self):
        return [2.*np.pi-a for a in self.exterior_angles]
    interior_angles=property(get_interior_angles)

    def get_angle_ratio(self):
        """Returns the angle ratio for the column, defined as the ratio of the largest interior angle to 
        the smallest interior angle."""
        angles=self.interior_angles
        return max(angles)/min(angles)
    angle_ratio=property(get_angle_ratio)

    def get_side_ratio(self):
        """Returns the side ratio for the column, defined as the ratio of the largest side length to 
        the smallest side length (a generalisation of the aspect ratio for quadrilateral columns)."""
        l=[norm(self.node[i].pos-self.node[i-1].pos) for i in xrange(self.num_nodes)]
        return max(l)/min(l)
    side_ratio=property(get_side_ratio)

    def basis(self,xi):
        """Returns bilinear 2D finite element basis functions for the column at the specified local coordinate."""
        if self.num_nodes==3: return np.array([xi[0],xi[1],1.-xi[0]-xi[1]])
        elif self.num_nodes==4: # over [-1,1]
            a0,a1,b0,b1=1.-xi[0],1.+xi[0],1.-xi[1],1.+xi[1]
            return 0.25*np.array([a0*b0,a1*b0,a1*b1,a0*b1])
        else: return None

    def basis_derivatives(self,xi):
        """Returns bilinear 2D finite element basis function derivatives for the column at the specified local coordinate."""
        if self.num_nodes==3: return np.array([[1.,0.],[0.,1.],[-1.,-1.]])
        elif self.num_nodes==4:
            a0,a1,b0,b1=1.-xi[0],1.+xi[0],1.-xi[1],1.+xi[1]
            return 0.25*np.array([[-b0,-a0],[b0,-a1],[b1,a1],[-b1,a0]])
        else: return None

    def Jacobian(self,xi):
        """Returns bilinear 2D finite element Jacobian matrix for the column at the specified local coordinate."""
        dpsi=self.basis_derivatives(xi)
        J=np.zeros((2,2))
        for i in xrange(2):
            for j in xrange(2):
                for k,nodek in enumerate(self.node): J[i,j]+=dpsi[k,j]*nodek.pos[i]
        return J

    def global_pos(self,xi):
        """Returns global coordinates of the local point xi in the column."""
        psi=self.basis(xi)
        return sum([psi[i]*nodei.pos for i,nodei in enumerate(self.node)])

    def local_inside(self,xi):
        """Returns true if a local point is inside the column."""
        if self.num_nodes==3: return all([x>=0. for x in xi]) and (np.sum(xi)<=1.)
        elif self.num_nodes==4: return all([abs(x)<=1. for x in xi])
        else: return None

    def local_pos(self,x):
        """Finds local coordinates of global point x in the column."""
        if self.num_nodes in [3,4]:
            tolerance,max_iterations=1.e-8,15
            if self.num_nodes==3: xi=np.array([1/3.,1/3.])
            else: xi=np.zeros(2)
            found=False
            for n in xrange(max_iterations): # Newton iteration
                dx=self.global_pos(xi)-x
                if np.linalg.norm(dx)<=tolerance:
                    found=True
                    break
                else:
                    J=self.Jacobian(xi)
                    try:
                        xi-=np.linalg.solve(J,dx)
                    except np.linalg.LinAlgError: break
            if not found: return None
            else:
                if self.local_inside(xi): return xi
                else: return None
        else: return None

    def __repr__(self): return self.name

class connection(object):
    """Column connection class"""
    def __init__(self,col=[column(),column()],nod=[node(),node()]):
        self.column=col
        self.node=nod
    def __repr__(self): return self.column[0].name+':'+self.column[1].name
    def get_angle_cosine(self):
        """Returns cosine of angle between the connection face and the line joining the two columns in the connection.
        Ideally want this to be zero, i.e. connecting line perpendicular to the face."""
        n=self.node[1].pos-self.node[0].pos
        n=n/norm(n)
        dcol=self.column[1].centre-self.column[0].centre
        d=dcol/norm(dcol)
        return np.dot(n,d)
    angle_cosine=property(get_angle_cosine)

class layer(object):
    """Grid layer class"""
    def __init__(self,name='  ',bottom=0.0,centre=0.0,top=0.0):
        self.name=name
        self.bottom=bottom
        self.centre=centre
        self.top=top
    def __repr__(self): return self.name+'('+str(self.bottom)+':'+str(self.top)+')'
    def contains_elevation(self,z): return self.bottom<=z<=self.top
    def translate(self,shift):
        """Translates a layer up or down by specified distance"""
        self.top+=shift
        self.bottom+=shift
        self.centre+=shift
    def get_thickness(self): return self.top-self.bottom
    thickness=property(get_thickness)

class well(object):
    """Well class"""
    def __init__(self,name='  ',pos=[]):
        self.name=name
        for i,p in enumerate(pos):
            if isinstance(p,list) or isinstance(p,tuple): pos[i]=np.array(p)
        self.pos=pos
    def __repr__(self): return self.name
    def get_num_deviations(self): return len(self.pos)-1
    num_deviations=property(get_num_deviations)
    def get_head(self): return self.pos[0]
    head=property(get_head)
    def get_bottom(self): return self.pos[-1]
    bottom=property(get_bottom)
    def elevation_pos(self,z):
        """Returns 3D position in well, given an elevation."""
        wellz=np.array([pos[2] for pos in self.pos])
        iarr=np.argwhere(wellz<=z)
        if (len(iarr)>0):
            i=iarr[0][0]
            if i==0: return None  # z is above the wellhead
            else:
                f=(z-wellz[i-1])/(wellz[i]-wellz[i-1])
                return (1.-f)*self.pos[i-1]+f*self.pos[i]
        else: return None # z is below the bottom

class mulgrid(object):
    """MULgraph grid class"""
    def __init__(self,filename='',type='GENER',convention=0,atmos_type=0,atmos_volume=1.e25,atmos_connection=1.e-6,unit_type='',permeability_angle=0.0):
        self.filename=filename
        self.type=type  # geometry type- only GENER supported
        self._convention=convention  # naming convention
        self._atmosphere_type=atmos_type  # atmosphere type
        self.set_secondary_variables()
        self.atmosphere_volume=atmos_volume
        self.atmosphere_connection=atmos_connection
        self.unit_type=unit_type
        self.permeability_angle=permeability_angle
        self.empty()
        if self.filename: self.read(filename)

    def set_secondary_variables(self):
        """Sets variables dependent on naming convention and atmosphere type"""
        if self.atmosphere_type==0: self.atmosphere_column_name=['ATM',' 0','  0'][self.convention]
        self.colname_length=[3,2,3][self.convention]
        self.layername_length=[2,3,2][self.convention]

    def get_convention(self):
        """Get naming convention"""
        return self._convention
    def set_convention(self,convention):
        """Set naming convention"""
        self._convention=convention
        self.set_secondary_variables()
    convention=property(get_convention,set_convention)

    def get_atmosphere_type(self):
        """Get atmosphere type"""
        return self._atmosphere_type
    def set_atmosphere_type(self,atmos_type):
        """Set atmosphere type"""
        self._atmosphere_type=atmos_type
        self.set_secondary_variables()
    atmosphere_type=property(get_atmosphere_type,set_atmosphere_type)

    def get_unit_type(self):
        """Get unit type"""
        return self._unit_type
    def set_unit_type(self,unit_type):
        """Set unit type"""
        self._unit_type=unit_type
        self.unit_scale={'':1.0,'FEET ':0.3048}[unit_type]
    unit_type=property(get_unit_type,set_unit_type)

    def get_area(self):
        """Grid area- sum of column areas"""
        return sum([col.area for col in self.columnlist])
    area=property(get_area)

    def get_centre(self):
        """Returns grid centre- approximated as area-weighted average of column centres"""
        if self.num_columns>0:  return sum([col.area*col.centre for col in self.columnlist])/self.area
        else: return None
    centre=property(get_centre)

    def get_num_blocks(self):
        """Returns number of blocks in the tough2 grid represented by the geometry."""
        return len(self.block_name_list)
    num_blocks=property(get_num_blocks)

    def get_num_atmosphere_blocks(self):
        """Returns number of atmosphere blocks in the tough2 grid represented by the geometry."""
        return [1,self.num_columns,0][self.atmosphere_type]
    num_atmosphere_blocks=property(get_num_atmosphere_blocks)

    def get_num_underground_blocks(self):
        """Returns number of blocks under the ground surface (i.e. non-atmosphere blocks) in the tough2 grid
        represented by the geometry."""
        return self.num_blocks-self.num_atmosphere_blocks
    num_underground_blocks=property(get_num_underground_blocks)

    def get_column_angle_ratio(self):
        """Returns an array of angle ratios for each column."""
        return np.array([col.angle_ratio for col in self.columnlist])
    column_angle_ratio=property(get_column_angle_ratio)

    def get_column_side_ratio(self):
        """Returns an array of side ratios for each column."""
        return np.array([col.side_ratio for col in self.columnlist])
    column_side_ratio=property(get_column_side_ratio)

    def get_connection_angle_cosine(self):
        """Returns an array of connection angle cosines, for each connection."""
        return np.array([con.angle_cosine for con in self.connectionlist])
    connection_angle_cosine=property(get_connection_angle_cosine)

    def empty(self):
        """Empties grid contents"""
        self.nodelist=[]
        self.columnlist=[]
        self.layerlist=[]
        self.connectionlist=[]
        self.welllist=[]
        self.node={}
        self.column={}
        self.layer={}
        self.connection={}
        self.well={}
        self.block_name_list,self.block_name_index=[],{}

    def __repr__(self):
        conventionstr=['3 characters for column, 2 digits for layer','3 characters for layer, 2 digits for column','2 characters for layer, 3 digits for column'][self.convention]
        atmstr=['single atmosphere block','one atmosphere block over each column','no atmosphere blocks'][self.atmosphere_type]
        return str(self.num_nodes)+' nodes; '+str(self.num_columns)+' columns; '+str(self.num_layers)+' layers; '+str(self.num_blocks)+' blocks; '+str(self.num_wells)+' wells'+'\n'+'Naming convention: '+conventionstr+'\n'+'Atmosphere type: '+atmstr

    def get_default_surface(self):
        return all([col.default_surface for col in self.columnlist])
    default_surface=property(get_default_surface)

    def get_num_nodes(self):
        return len(self.node)
    num_nodes=property(get_num_nodes)

    def get_num_columns(self):
        return len(self.column)
    num_columns=property(get_num_columns)

    def get_num_layers(self):
        return len(self.layer)
    num_layers=property(get_num_layers)

    def get_num_connections(self):
        return len(self.connectionlist)
    num_connections=property(get_num_connections)

    def get_num_wells(self):
        return len(self.well)
    num_wells=property(get_num_wells)

    def get_layer_index(self):
        return dict([(lay.name,i) for i,lay in enumerate(self.layerlist)])
    layer_index=property(get_layer_index)
    def get_column_index(self):
        return dict([(col.name,i) for i,col in enumerate(self.columnlist)])
    column_index=property(get_column_index)

    def connects(self,col1,col2):
        """Returns True if the geometry contains a connection connecting the two specified columns."""
        return any([(col1 in con.column) and (col2 in con.column) for con in self.connectionlist])

    def setup_block_name_index(self):
        """Sets up list and dictionary of block names and indices for the tough2 grid represented by the geometry."""
        self.block_name_list=[]
        if self.atmosphere_type==0: # one atmosphere block
            self.block_name_list.append(self.block_name(self.layerlist[0].name,self.atmosphere_column_name))
        elif self.atmosphere_type==1: # one atmosphere block per column
            for col in self.columnlist: self.block_name_list.append(self.block_name(self.layerlist[0].name,col.name))
        for lay in self.layerlist[1:]:
            for col in [col for col in self.columnlist if col.surface>lay.bottom]:
                self.block_name_list.append(self.block_name(lay.name,col.name))
        self.block_name_index=dict([(blk,i) for i,blk in enumerate(self.block_name_list)])

    def column_name(self,blockname):
        """Returns column name of block name."""
        if self.convention==0: return blockname[0:3]
        elif self.convention==1: return blockname[3:5]
        elif self.convention==2: return blockname[2:5]
        else: return None

    def layer_name(self,blockname):
        """Returns layer name of block name."""
        if self.convention==0: return blockname[3:5]
        elif self.convention==1: return blockname[0:3]
        elif self.convention==2: return blockname[0:2]
        else: return None

    def column_name_from_number(self,num,justfn=rjust,casefn=lowercase):
        """Returns column name based on column number. """
        if self.convention==0: return justfn(IntToLetters(num,casefn=casefn),self.colname_length)
        else: return rjust(str(num),self.colname_length)
    def column_number_from_name(self,name):
        if self.convention==0: return LettersToInt(name)
        else: return int(name)

    def get_uppercase_names(self):
        """Returns True if character part of block names are uppercase."""
        return all([(blkname[0:3]==blkname[0:3].upper()) for blkname in self.block_name_list])
    uppercase_names=property(get_uppercase_names)

    def get_right_justified_names(self):
        """Returns True if character part of block names are right-justified."""
        return all([(blkname[0:3]==blkname[0:3].rjust(3)) for blkname in self.block_name_list])
    right_justified_names=property(get_right_justified_names)

    def get_bounds(self):
        """Returns horizontal bounding box for grid"""
        return bounds_of_points([node.pos for node in self.nodelist])
    bounds=property(get_bounds)

    def add_node(self,nod=node()):
        """Adds node to the grid"""
        self.nodelist.append(nod)
        self.node[nod.name]=self.nodelist[-1]

    def delete_node(self,nodename):
        node=self.node[nodename]
        del self.node[nodename]
        self.nodelist.remove(node)

    def add_column(self,col=column()):
        """Adds column to the grid"""
        self.columnlist.append(col)
        self.column[col.name]=self.columnlist[-1]
        for node in col.node: node.column.add(col)

    def delete_column(self,colname):
        col=self.column[colname]
        cons=[con for con in self.connectionlist if col in con.column]
        for con in cons:
            self.delete_connection(tuple([c.name for c in con.column]))
        for nbr in col.neighbour: nbr.neighbour.remove(col)
        for node in col.node: node.column.remove(col)
        del self.column[colname]
        self.columnlist.remove(col)
            
    def add_layer(self,lay=layer()):
        """Adds layer to the grid"""
        self.layerlist.append(lay)
        self.layer[lay.name]=self.layerlist[-1]

    def delete_layer(self,layername):
        layer=self.layer[layername]
        del self.layer[layername]
        self.layerlist.remove(layer)

    def rename_layer(self,oldlayername,newlayername):
        """Renames a layer."""
        try:
            i=self.layerlist.index(self.layer[oldlayername])
            self.layerlist[i].name=newlayername
            self.layer[newlayername]=self.layer.pop(oldlayername)
            return True
        except ValueError: return False
            
    def add_connection(self,con=connection()):
        """Adds connection to the grid"""
        self.connectionlist.append(con)
        self.connection[(con.column[0].name,con.column[1].name)]=self.connectionlist[-1]
        self.connectionlist[-1].node=list(set(con.column[0].node).intersection(set(con.column[1].node)))
        for col in self.connectionlist[-1].column: col.connection.add(self.connectionlist[-1])

    def delete_connection(self,colnames):
        """Deletes a connection from the grid."""
        con=self.connection[colnames]
        for col in con.column: col.connection.remove(con)
        del self.connection[colnames]
        self.connectionlist.remove(con)
            
    def add_well(self,wl=well()):
        """Adds well to the grid"""
        self.welllist.append(wl)
        self.well[wl.name]=self.welllist[-1]

    def delete_well(self,wellname):
        """Deletes a well from the grid."""
        well=self.well[wellname]
        del self.well[wellname]
        self.welllist.remove(well)
            
    def delete_orphan_wells(self):
        """Deletes any wells with wellheads not inside the grid."""
        delwells=[]
        for well in self.welllist:
            wh=well.pos[0][0:2]
            if self.column_containing_point(wh)==None: delwells.append(well.name)
        for wellname in delwells: self.delete_well(wellname)

    def identify_neighbours(self):
        """Identify neighbour columns"""
        for con in self.connectionlist:
            for i in xrange(2): con.column[i].neighbour.add(con.column[not i])

    def identify_layer_tops(self):
        """Identifies top elevations of grid layers"""
        self.layerlist[0].top=self.layerlist[0].bottom
        for i,this in enumerate(self.layerlist[1:]):
            above=self.layerlist[i]
            this.top=above.bottom

    def set_default_surface(self):
        """Sets default column surface elevations"""
        ground=self.layerlist[0].bottom
        for col in self.columnlist:
            col.surface=ground
            col.default_surface=True
            col.num_layers=self.num_layers-1

    def columns_in_polygon(self,polygon):
        """Returns a list of all columns with centres inside the specified polygon."""
        return [col for col in self.columnlist if col.in_polygon(polygon)]

    def nodes_in_polygon(self,polygon):
        """Returns a list of all nodes inside the specified polygon."""
        return [node for node in self.nodelist if in_polygon(node.pos,polygon)]

    def read_header(self,header):
        """Reads grid header info from file geo"""
        self.type=header[0:5]
        def getval(i1,i2,fn):
            valstr=header[i1:i2].replace('\n',' ')
            if valstr.strip(): return fn(valstr)
            else:
                if fn==str: return ''
                else: return fn('0')
        self.convention=getval(5,6,int)
        self.atmosphere_type=getval(6,7,int)
        self.atmosphere_volume=getval(7,17,float)
        self.atmosphere_connection=getval(17,27,float)
        self.unit_type=getval(27,32,str)
        gdcx,gdcy=getval(32,42,float),getval(42,52,float)
        if gdcx<>0.0 or gdcy<>0.0: print 'GDCX,GDCY options not supported.'
        cntype=getval(52,53,int)
        if cntype<>0: print 'CNTYPE option not supported.'
        self.permeability_angle=getval(53,63,float)

    def read_nodes(self,geo):
        """Reads grid nodes from file geo"""
        line=padstring(geo.readline())
        while line.strip():
            nodename=line[0:3].strip().rjust(self.colname_length)
            pos=np.array([float(line[3:13]),float(line[13:23])])*self.unit_scale
            newnode=node(nodename,pos)
            self.add_node(newnode)
            line=geo.readline()

    def read_columns(self,geo):
        """Reads grid columns from file geo"""
        line=padstring(geo.readline())
        while line.strip():
            colname,centre_specified,nnodes=line[0:3].strip().rjust(self.colname_length),line[3:4].strip(),int(line[4:6])
            if centre_specified: 
                if int(centre_specified)>0: centre=np.array([float(line[6:16]),float(line[16:26])])*self.unit_scale
                else: centre=None
            else: centre=None
            nodes=[]
            for each in xrange(nnodes):
                line=padstring(geo.readline())
                nodename=line[0:3].strip().rjust(self.colname_length)
                colnode=self.node[nodename]
                nodes.append(colnode)
            self.add_column(column(colname,nodes,centre))
            line=geo.readline()

    def read_connections(self,geo):
        """Reads grid connections from file geo"""
        line=padstring(geo.readline())
        while line.strip():
            names=[line[0:3].strip().rjust(self.colname_length),line[3:6].strip().rjust(self.colname_length)]
            cols=[self.column[name] for name in names]
            self.add_connection(connection(cols))
            line=geo.readline()
        self.identify_neighbours()

    def read_layers(self,geo):
        """Reads grid layers from file geo"""
        line=padstring(geo.readline())
        while line.strip():
            name,bottom=line[0:self.layername_length],float(line[3:13])*self.unit_scale
            newlayer=layer(name,bottom)
            self.add_layer(newlayer)
            if len(line)>13 and line[13:23].strip(): centre=float(line[13:23])*self.unit_scale
            else:
                nlayers=len(self.layer)
                if nlayers>1: centre=0.5*(newlayer.bottom+self.layerlist[nlayers-2].bottom)
                else: centre=newlayer.bottom
            newlayer.centre=centre
            line=geo.readline()
        self.identify_layer_tops()
        self.set_default_surface()

    def read_surface(self,geo):
        """Reads grid surface from file geo"""
        line=padstring(geo.readline())
        while line.strip():
            name,surface=line[0:3].strip().rjust(self.colname_length),float(line[3:13])*self.unit_scale
            col=self.column[name]
            col.surface=surface
            col.num_layers=len([layer for layer in self.layerlist[1:] if layer.bottom<col.surface])
            line=geo.readline()

    def read_wells(self,geo):
        """Reads grid wells from file geo"""
        line=padstring(geo.readline())
        while line.strip():
            name=line[0:5]
            p=np.array([float(line[5:15]),float(line[15:25]),float(line[25:35])])*self.unit_scale
            if name in self.well: self.well[name].pos.append(p)
            else: self.add_well(well(name,[p]))
            line=geo.readline()

    def read(self,filename):
        """Reads MULgraph grid from file"""
        self.empty()
        geo=open(filename)
        line=padstring(geo.readline())
        self.read_header(line)
        if self.type=='GENER':
            read_fn={'VERTI':self.read_nodes, 'GRID': self.read_columns, 'CONNE': self.read_connections,
                     'LAYER': self.read_layers, 'SURFA': self.read_surface, 'SURF': self.read_surface,
                     'WELLS': self.read_wells}
            more=True
            while more:
                line=geo.readline().strip()
                if line:
                    keyword=line[0:5]
                    read_fn[keyword](geo)
                else: more=False
            self.setup_block_name_index()
        else: print 'Grid type',self.type,'not supported.'
        geo.close()
        return self

    def block_surface(self,lay,col):
        """Returns elevation of top of block for given layer and column"""
        if lay.name==self.layerlist[0].name:
            if self.atmosphere_type==1: return lay.top # atmosphere block
            else: return None
        else:
            if col.surface<lay.top:
                if lay.bottom<col.surface: return col.surface # surface layer with surface below layer top
                else: return None # outside grid
            elif col.surface>self.layerlist[0].top: return col.surface # surface layer with surface above layer top
            else: return lay.top # subsurface layer

    def block_volume(self,lay,col):
        """Returns volume of block at specified layer and column"""
        if lay.name==self.layerlist[0].name:
            if (self.atmosphere_type==0) and (col.name==self.atmosphere_column_name): return self.atmosphere_volume
            elif self.atmosphere_type==1: return self.atmosphere_volume
            else: return None
        else:
            surf=self.block_surface(lay,col)
            if surf<>None: return (surf-lay.bottom)*col.area
            else: return None

    def block_centre(self,lay,col):
        """Returns centre of block at specified layer and column.  The vertical centre is always the layer centre,
        except for surface blocks with column surface lower than the layer top.  For surface blocks with column surface
        higher than the layer top, the vertical centre is still the layer centre, to give a uniform pressure reference,
        even though this is not geometrically correct."""
        if lay.name==self.layerlist[0].name:
            if self.atmosphere_type==1: midelev=lay.centre
            else: return None
        else:
            if (lay.bottom<col.surface<=lay.top): midelev=0.5*(lay.bottom+col.surface)
            else: 
                if col.surface<=lay.bottom: return None # outside grid
                else: midelev=lay.centre
        return np.array([col.centre[0],col.centre[1],midelev])

    def connection_params(self,con,lay):
        """Returns connection parameters (distances, interface area) between specified columns, for the given layer"""
        if con in self.connectionlist:
            sidelength=norm(con.node[0].pos-con.node[1].pos)
            height=min([self.block_surface(lay,c)-lay.bottom for c in con.column])
            area=sidelength*height
            nodeline=[node.pos for node in con.node]
            dist=[norm(line_projection(c.centre,nodeline)-c.centre) for c in con.column]
            return [dist,area]
        else: return [[0.0,0.0],0.0] # no connection

    def block_name(self,layername,colname):
        """Returns block name from layer and column names, depending on the naming convention"""
        return [colname[0:3]+layername[0:2],layername[0:3]+colname[0:2],layername[0:2]+colname[0:3]][self.convention]

    def write(self,filename=''):
        """Writes a MULgraph grid to file"""
        if filename: self.filename=filename
        if self.filename=='': self.filename='geometry.dat'
        geo=open(self.filename,'w')
        self.write_header(geo)
        self.write_nodes(geo)
        self.write_columns(geo)
        self.write_connections(geo)
        self.write_layers(geo)
        if not self.default_surface: self.write_surface(geo)
        if self.num_wells>0: self.write_wells(geo)
        geo.write('\n')
        geo.close()

    def write_header(self,geo):
        """Writes MULgraph grid header to file"""
        geo.write("%s%1d%1d%10.2e%10.2e%5s%21s%10.2f\n" % (self.type,self.convention,self.atmosphere_type,self.atmosphere_volume,self.atmosphere_connection,self.unit_type,' '*21,self.permeability_angle))

    def write_nodes(self,geo):
        """Writes MULgraph grid nodes to file"""
        geo.write('VERTICES\n')
        for node in self.nodelist:
            geo.write("%s%10.2f%10.2f\n" % (node.name,node.pos[0]/self.unit_scale,node.pos[1]/self.unit_scale))
        geo.write('\n')
        
    def write_columns(self,geo):
        """Writes MULgraph grid columns to file"""
        geo.write('GRID\n')
        for col in self.columnlist:
            geo.write("%s%1d%2d" % (col.name,col.centre_specified,col.num_nodes))
            if col.centre_specified:
                geo.write("%10.2f%10.2f\n" % (col.centre[0]/self.unit_scale,col.centre[1]/self.unit_scale))
            else: geo.write('\n')
            for node in col.node: geo.write("%s\n" % node.name)
        geo.write('\n')
            
    def write_connections(self,geo):
        """Writes MULgraph grid connections to file"""
        geo.write('CONNECTIONS\n')
        for con in self.connectionlist:
            geo.write("%s%s\n" % (con.column[0].name,con.column[1].name))
        geo.write('\n')

    def write_layers(self,geo):
        """Writes MULgraph grid layers to file"""
        geo.write('LAYERS\n')
        for lay in self.layerlist:
            geo.write("%s%10.2f%10.2f\n" % (lay.name,lay.bottom/self.unit_scale,lay.centre/self.unit_scale))
        geo.write('\n')
        
    def write_surface(self,geo):
        """Writes MULgraph grid surface to file"""
        geo.write('SURFA\n')
        for col in [col for col in self.columnlist if not col.default_surface]:
            geo.write("%s%10.2f\n" % (col.name,col.surface/self.unit_scale))
        geo.write('\n')

    def write_wells(self,geo):
        """Writes MULgraph wells to file"""
        geo.write('WELLS\n')
        for wl in self.welllist:
            for pos in wl.pos:
                geo.write("%s%10.1f%10.1f%10.1f\n" % (wl.name,pos[0]/self.unit_scale,pos[1]/self.unit_scale,
                                                      pos[2]/self.unit_scale))
        geo.write('\n')
        
    def rectangular(self,xblocks,yblocks,zblocks,convention=0,atmos_type=2,origin=[0.,0.,0.],justify='r',case='l'):
        """Returns a rectangular MULgraph grid with specified block sizes.
        The arguments are arrays of the block sizes in each dimension (x,y,z).
        Naming convention, atmosphere type and origin can optionally be specified.
        The optional justify and case parameters specify the format of the character part of the block names
        (whether they are right or left justified, and lower or upper case)."""
        if isinstance(xblocks,list): xblocks=np.array(xblocks)
        if isinstance(yblocks,list): yblocks=np.array(yblocks)
        if isinstance(zblocks,list): zblocks=np.array(zblocks)
        if isinstance(origin,list): origin=np.array(origin)
        grid=mulgrid(type='GENER',convention=convention,atmos_type=atmos_type)
        grid.empty()
        xverts=np.array([0.]+np.cumsum(xblocks).tolist())+origin[0]
        yverts=np.array([0.]+np.cumsum(yblocks).tolist())+origin[1]
        nxv=len(xverts)
        nxb,nyb=len(xblocks),len(yblocks)
        justfn=[rjust,ljust][justify=='l']
        casefn=[uppercase,lowercase][case=='l']
        # create nodes:
        num=1
        y=origin[1]
        for y in yverts:
            for x in xverts:
                name=grid.column_name_from_number(num,justfn,casefn)
                grid.add_node(node(name,np.array([x,y])))
                num+=1
        # create columns:
        num=1
        for j in xrange(nyb):
            for i in xrange(nxb):
                colname=grid.column_name_from_number(num,justfn,casefn)
                colverts=[j*nxv+i+1,(j+1)*nxv+i+1,(j+1)*nxv+i+2,j*nxv+i+2]
                nodenames=[grid.column_name_from_number(v,justfn,casefn) for v in colverts]
                colnodes=[grid.node[name] for name in nodenames]
                grid.add_column(column(colname,colnodes))
                num+=1
        # x-connections:
        for j in xrange(nyb):
            for i in xrange(nxb-1):
                num1,num2=j*nxb+i+1,j*nxb+i+2
                name1,name2=grid.column_name_from_number(num1,justfn,casefn),grid.column_name_from_number(num2,justfn,casefn)
                grid.add_connection(connection([grid.column[name1],grid.column[name2]]))
        # y-connections:
        for i in xrange(nxb):
            for j in xrange(nyb-1):
                num1,num2=j*nxb+i+1,(j+1)*nxb+i+1
                name1,name2=grid.column_name_from_number(num1,justfn,casefn),grid.column_name_from_number(num2,justfn,casefn)
                grid.add_connection(connection([grid.column[name1],grid.column[name2]]))
        # create layers:
        grid.add_layers(zblocks,origin[2],justify,case)
        grid.set_default_surface()
        grid.identify_neighbours()
        grid.setup_block_name_index()
        return grid

    def add_layers(self,thicknesses,top_elevation=0,justify='r',case='l'):
        """Adds layers of specified thicknesses and top elevation."""
        justfn=[rjust,ljust][justify=='l']
        casefn=[uppercase,lowercase][case=='l']
        def get_layername(num):
            """Returns layer name, based on naming convention"""
            if self.convention==0: return rjust(str(num),self.layername_length)
            else: return justfn(IntToLetters(num,casefn=casefn),self.layername_length)
        num=0
        z=top_elevation
        surfacelayername=[' 0','atm','at'][self.convention]
        self.add_layer(layer(surfacelayername,z,z))
        for thickness in thicknesses:
            z-=thickness
            centre=z+0.5*thickness
            name=surfacelayername
            while name==surfacelayername: # make sure layer name is different from surface layer name
                num+=1
                name=rjust(get_layername(num),self.layername_length)
            self.add_layer(layer(name,z,centre))
        self.identify_layer_tops()

    def from_gmsh(self,filename,layers,convention=0,atmos_type=2,top_elevation=0):
        """Returns a MULgraph grid constructed from a 2D gmsh grid and the specified layer structure."""
        grid=mulgrid(type='GENER',convention=convention,atmos_type=atmos_type)
        grid.empty()
        gmsh=open(filename)
        line=''
        while not '$Nodes' in line: line=gmsh.readline()
        num_nodes=int(gmsh.readline().strip())
        for i in xrange(num_nodes):
            items=gmsh.readline().strip().split(' ')
            name,x,y=items[0],float(items[1]),float(items[2])
            name=[IntToLetters(int(name)),name][convention>0]
            name=rjust(name,grid.colname_length)
            grid.add_node(node(name,np.array([x,y])))
        while not '$Elements' in line: line=gmsh.readline()
        num_elements=int(gmsh.readline().strip())
        for i in xrange(num_elements):
            items=gmsh.readline().strip().split(' ')
            element_type=int(items[1])
            if element_type in [2,3]: # triangle or quadrilateral
                name=items[0]
                name=[IntToLetters(int(name)),name][convention>0]
                name=rjust(name,grid.colname_length)
                ntags=int(items[2])
                colnodenumbers=items[3+ntags:]
                colnodenames=[[IntToLetters(int(nodeno)),nodeno][convention>0] for nodeno in colnodenumbers]
                colnodes=[grid.node[rjust(v,grid.colname_length)] for v in colnodenames]
                grid.add_column(column(name,colnodes))
        gmsh.close()
        for con in grid.missing_connections: grid.add_connection(con)
        grid.delete_orphans()
        grid.add_layers(layers,top_elevation)
        grid.set_default_surface()
        grid.identify_neighbours()
        grid.setup_block_name_index()
        return grid

    def translate(self,shift):
        """Translates a grid by specified shift."""
        for node in self.nodelist: node.pos+=shift[0:2]
        for col in self.columnlist: col.centre+=shift[0:2]
        for layer in self.layerlist: layer.translate(shift[2])
        for well in self.welllist:
            for pos in well.pos: pos+=shift

    def rotate(self,angle,centre=None):
        """Rotates grid horizontally by specified angle (degrees clockwise).
        If centre is not specified, the centre of the grid is used."""
        if centre: c=centre
        else: c=self.centre
        R=linear_trans2().rotation(angle,c)
        for node in self.nodelist: node.pos=R(node.pos)
        for col in self.columnlist: col.centre=R(col.centre)
        for well in self.welllist:
            for pos in well.pos: pos[0:2]=R(pos[0:2])

    def get_missing_connections(self):
        """Returns a set of connections for columns that have shared faces but don't have a connection defined between them."""
        missing=set([])
        for node in self.nodelist:
            nodecols=list(node.column)
            for i,coli in enumerate(nodecols[0:-1]):
                for colj in nodecols[i+1:]:
                    if coli.is_against(colj) and not self.connects(coli,colj):
                        if coli.name<=colj.name: mincol,maxcol=coli,colj
                        else: mincol,maxcol=colj,coli
                        missing.add((mincol.name,maxcol.name))
        return set([connection(tuple([self.column[colname] for colname in m])) for m in missing])
    missing_connections=property(get_missing_connections)

    def get_extra_connections(self):
        """Returns a set of pairs of column names defined between columns that aren't against each other."""
        extra=set([])
        for con in self.connectionlist:
            if not con.column[0].is_against(con.column[1]): extra.add(tuple([col.name for col in con.column]))
        return extra
    extra_connections=property(get_extra_connections)

    def get_orphans(self):
        """Returns a set of 'orphaned' nodes, i.e. nodes that do not belong to any column."""
        return set([node for node in self.nodelist if len(node.column)==0])
    orphans=property(get_orphans)

    def delete_orphans(self):
        """Deletes any orphaned nodes."""
        for node in self.orphans: self.delete_node(node.name)

    def get_bad_columns(self):
        """Returns a set of columns that do not contain their own centres."""
        return set([col for col in self.columnlist if not col.contains_point(col.centre)])
    bad_columns=property(get_bad_columns)

    def get_bad_layers(self):
        """Returns a set of layers that do not contain their own centres."""
        return set([layer for layer in self.layerlist[1:] if not layer.bottom<=layer.centre<=layer.top])
    bad_layers=property(get_bad_layers)

    def check(self,fix=False,silent=False):
        """Checks a grid for errors, and optionally fixes them.  Errors checked for are:
        - missing connections
        - extra connections
        - orphaned nodes
        - columns and layers that do not contain their own centres.
        Returns True if no errors were found, and False otherwise.  If silent is True, there is no printout."""
        ok=True
        mc=self.missing_connections
        if len(mc)>0:
            ok=False
            if not silent: print 'Missing connections:',list(mc)
            if fix:
                for c in mc: self.add_connection(c)
                if not silent: print 'Missing connections fixed.'
        ec=self.extra_connections
        if len(ec)>0:
            ok=False
            if not silent: print 'Extra connections:',list(ec)
            if fix:
                for c in ec: self.delete_connection(c)
                if not silent: print 'Extra connections fixed.'
        orphans=self.orphans
        if len(orphans)>0:
            ok=False
            if not silent: print 'Orphaned nodes:',list(orphans)
            if fix:
                self.delete_orphans()
                if not silent: print 'Orphaned nodes deleted.'
        bc=self.bad_columns
        if len(bc)>0:
            ok=False
            if not silent: print 'Bad columns:',list(bc)
            if fix:
                for c in bc: c.centre=sum([n.pos for n in c.node])/c.num_nodes
                if not silent: print 'Columns fixed.'
        bl=self.bad_layers
        if len(bl)>0:
            ok=False
            if not silent: print 'Bad layers:',list(bl)
            if fix:
                for layer in bl:
                    layer.bottom,layer.top=min(layer.bottom,layer.top),max(layer.bottom,layer.top)
                    layer.centre=0.5*(layer.bottom+layer.top)
                if not silent: print 'Layers fixed.'
        if ok and not silent: print 'No problems found.'
        return ok

    def column_values_to_block(self,x):
        """Takes an array of values for each column and extends it into an array of values for each block."""
        blkval=np.zeros(self.num_blocks,float64)
        colindex=self.column_index
        for i,blk in enumerate(self.block_name_list):
            colname=self.column_name(blk)
            if colname in self.column:
                ci=colindex[colname]
                blkval[i]=x[ci]
        return blkval

    def column_containing_point(self,pos,columns=None,guess=None,bounds=None,qtree=None):
        """Returns column containing the specified horizontal position (or None if not found).  If the columns
        parameter is specified, search only within the given list of columns.  A starting guess of the column
        can also be optionally provided, in which case that column and (if necessary) its neighbours will be 
        searched first.  A bounding polygon for searching within can also optionally be supplied- this can, for
        example, be specified as the boundary polygon of the grid.  A quadtree for searching the columns can
        also optionally be specified."""
        target=None
        if bounds<>None: inbounds=in_polygon(pos,bounds)
        else: inbounds=True
        if inbounds:
            if columns==None: searchcols=self.columnlist
            else: searchcols=columns
            donecols=set([])
            if guess<>None: 
                if guess.contains_point(pos): return guess
                else: # search neighbours of guess, sorted by distance from pos:
                    donecols.add(guess)
                    from copy import copy
                    nbrcols=list(copy(guess.neighbour))
                    nearnbrcols=[col for col in nbrcols if col.near_point(pos)]
                    sortindex=np.argsort([norm(col.centre-pos) for col in nearnbrcols])
                    for i in sortindex:
                        if nearnbrcols[i].contains_point(pos): return nearnbrcols[i]
                    donecols.update(set(nearnbrcols))
            # guess was no good- do full search on remaining columns:
            if qtree: return qtree.search(pos)
            else:
                nearcols=list(set([col for col in searchcols if col.near_point(pos)])-donecols)
                sortindex=np.argsort([norm(col.centre-pos) for col in nearcols])
                for i in sortindex:
                    if nearcols[i].contains_point(pos):
                        target=nearcols[i]
                        break
        return target

    def layer_containing_elevation(self,z):
        """Returns layer containing the specified vertical elevation (or None if not found)."""
        target=None
        for layer in self.layerlist[1:]:
            if layer.contains_elevation(z):
                target=layer
                break
        return target

    def column_mapping(self,geo):
        """Returns a dictionary mapping each column name in a geometry object geo to the name of the nearest column in self."""
        if self.atmosphere_type==geo.atmosphere_type==0:
            mapping={geo.atmosphere_column_name:self.atmosphere_column_name}
        else: mapping={}
        for col in geo.columnlist:
            coldist=np.array([norm(selfcol.centre-col.centre) for selfcol in self.columnlist])
            closest=self.columnlist[np.argmin(coldist)]
            mapping[col.name]=closest.name
        return mapping

    def layer_mapping(self,geo):
        """Returns a dictionary mapping each layer name in a geometry object geo to the name of the nearest layer in self."""
        mapping={geo.layerlist[0].name: self.layerlist[0].name}  # surface mapped to surface
        for layer in geo.layerlist[1:]:
            laydist=np.array([abs(selflay.centre-layer.centre) for selflay in self.layerlist[1:]])
            closest=self.layerlist[1+np.argmin(laydist)]  # (1 added for surface layer, omitted from search)
            mapping[layer.name]=closest.name
        return mapping
    
    def block_mapping(self,geo,column_mapping=False):
        """Returns a dictionary mapping each block name in a geometry object geo to the name of the nearest block in self.
        Columns are given priority over layers, i.e. first the nearest column is found, then the nearest layer for blocks
        in that column.  The associated column mapping can also optionally be returned."""
        mapping={}
        col_mapping=self.column_mapping(geo)
        layer_mapping=self.layer_mapping(geo)
        for dest in geo.block_name_list:
            destcol,destlayer=geo.column_name(dest),geo.layer_name(dest)
            sourcecol,sourcelayer=col_mapping[destcol],layer_mapping[destlayer]
            if destlayer==geo.layerlist[0].name:
                sourcelayer=self.layerlist[0].name # atmosphere layer
                if self.atmosphere_type==0: sourcecol=self.atmosphere_column_name
            else:
                # if source block is above surface in column, use first layer below surface instead:
                if self.column[sourcecol].surface<=self.layer[sourcelayer].bottom:
                    toplayer_index=self.num_layers-self.column[sourcecol].num_layers
                    sourcelayer=self.layerlist[toplayer_index].name
            mapping[dest]=self.block_name(sourcelayer,sourcecol)
        if column_mapping: return (mapping,col_mapping)
        else: return mapping

    def block_name_containing_point(self,pos):
        """Returns name of grid block containing 3D point (or None if the point is outside the grid)."""
        blkname=None
        col=self.column_containing_point(pos[0:2])
        if col:
            layer=self.layer_containing_elevation(pos[2])
            if layer and (col.surface>layer.bottom): blkname=self.block_name(layer.name,col.name)
        return blkname

    def column_track(self,line):
        """Returns a list of tuples of (column,entrypoint,exitpoint) representing the horizontal track traversed by the
        specified line through the grid.  Line is a tuple of two 2D arrays.  The resulting list is ordered by distance
        from the start of the line."""
        track=[]
        for col in self.columnlist:
            polygon=[n.pos for n in col.node]
            crossings=line_polygon_intersections(polygon,line)
            if crossings: track.append(tuple([col]+crossings))
        sortindex=np.argsort([norm(t[1]-line[0]) for t in track])
        return [track[i] for i in sortindex]

    def layer_plot(self,layer,variable=None,variable_name=None,unit=None,column_names=None,node_names=None,column_centres=None,nodes=None,colourmap=None,linewidth=0.2,aspect='equal',plt=None,subplot=111,title=None,xlabel='x (m)',ylabel='y (m)',contours=False,contour_label_format='%3.0f',contour_grid_divisions=(100,100)):
        """Produces a layer plot of a Mulgraph grid, shaded by the specified variable (an array of values for each block).
       A unit string can be specified for annotation.  Column names, node names, column centres and nodes can be optionally
       superimposed, and the colour map, linewidth and aspect ratio specified.
       If no variable is specified, only the grid is drawn, without shading. If an elevation (float) is given instead
       of a layer name, the layer containing that elevation is plotted."""
        import matplotlib
        if plt==None: 
            import matplotlib.pyplot as plt
            loneplot=True
        else: loneplot=False
        matplotlib.rcParams.update({'mathtext.default': 'regular','figure.figsize':(12,9)})
        ax=plt.subplot(subplot,aspect=aspect)
        if isinstance(layer,float) or isinstance(layer,int):
            l=self.layer_containing_elevation(float(layer))
            if l: layername=l.name
            else: layername=''
            default_title='layer '+layername+' (elevation '+("%4.0f"%float(layer)).strip()+' m)'
        else:
            layername=layer
            default_title='layer '+layername
        if layername in self.layer:
            if variable<>None:
                if len(variable)==self.num_columns: variable=self.column_values_to_block(variable)
            if variable_name: varname=variable_name
            else: varname='Value'
            if column_names:
                if not isinstance(column_names,list): column_names=self.column.keys()
            else: column_names=[]
            if node_names:
                if not isinstance(node_names,list): node_names=self.node.keys()
            else: node_names=[]
            if column_centres:
                if not isinstance(column_centres,list): column_centres=self.column.keys()
            else: column_centres=[]
            if nodes:
                if not isinstance(nodes,list): nodes=self.node.keys()
            else: nodes=[]
            verts,vals=[],[]
            if not isinstance(contours,bool): contours=list(contours)
            if contours<>False: xc,yc=[],[]
            for col in self.columnlist:
                blkname=self.block_name(layername,col.name)
                if blkname in self.block_name_list:
                    if contours<>False:
                        xc.append(col.centre[0])
                        yc.append(col.centre[1])
                    if variable<>None: val=variable[self.block_name_index[blkname]]
                    else: val=0
                    vals.append(val)
                    verts.append(tuple([tuple([p for p in n.pos]) for n in col.node]))
                    if col.name in column_names:
                        ax.text(col.centre[0],col.centre[1],col.name,clip_on=True,horizontalalignment='center')
                    if col.name in column_centres:
                        ax.text(col.centre[0],col.centre[1],'+',color='red',clip_on=True,
                                horizontalalignment='center',verticalalignment='center')
            for node in [self.node[name] for name in node_names]:
                    ax.text(node.pos[0],node.pos[1],node.name,clip_on=True,horizontalalignment='center')
            for node in [self.node[name] for name in nodes]:
                    ax.text(node.pos[0],node.pos[1],'+',color='red',clip_on=True,
                            horizontalalignment='center',verticalalignment='center')
            import matplotlib.collections as collections
            if variable<>None: facecolors=None
            else: facecolors=[]
            col=collections.PolyCollection(verts,cmap=colourmap,linewidth=linewidth,facecolors=facecolors)
            if variable<>None: col.set_array(np.array(vals))
            ax.add_collection(col)
            ax.autoscale_view()
            if contours<>False:
                from matplotlib.mlab import griddata
                xc,yc=np.array(xc),np.array(yc)
                valc=np.array(vals)
                bds=self.bounds
                xgrid=np.linspace(bds[0][0],bds[1][0],contour_grid_divisions[0])
                ygrid=np.linspace(bds[0][1],bds[1][1],contour_grid_divisions[1])
                valgrid=griddata(xc,yc,valc,xgrid,ygrid)
                if isinstance(contours,list): cvals=contours
                else: cvals=False
                CS=plt.contour(xgrid,ygrid,valgrid,cvals,colors='k')
                if contour_label_format<>None: plt.clabel(CS, inline=1,fmt=contour_label_format)
            plt.xlabel(xlabel)
            plt.ylabel(ylabel)
            scalelabel=varname
            if unit: scalelabel+=' ('+unit+')'
            if variable<>None:
                cbar=plt.colorbar(col)
                cbar.set_label(scalelabel)
                default_title=varname+' in '+default_title
            if title==None: title=default_title
            plt.title(title)
            if loneplot: plt.show()

    def slice_plot(self,line=None,variable=None,variable_name=None,unit=None,block_names=None,colourmap=None,linewidth=0.2,aspect='auto',plt=None,subplot=111,title='',xlabel=None,ylabel='elevation (m)',contours=False,contour_label_format='%3.0f',contour_grid_divisions=(100,100)):
        """Produces a vertical slice plot of a Mulgraph grid, shaded by the specified variable (an array of values for each block).
       A unit string can be specified for annotation.  Block names can be optionally superimposed, and the colour 
       map, linewidth and aspect ratio specified.
       If no variable is specified, only the grid is drawn, without shading.  If no line is specified, a slice
       through the grid bounds is made (bottom left to top right).
       If a string 'x' or 'y' is passed in instead of a line, a plot is made through the centre of the grid along
       the x- or y-axes, and the coordinate along the slice represents the actual x- or y- coordinate.  If a northing
       (float, in degrees) is passed instead of a line, a plot is made through the centre along the specified northing direction."""
        if line==None:
            l=self.bounds
            default_title='vertical slice across grid bounds'
        elif isinstance(line,str):
            axislines={'x':[np.array([self.bounds[0][0],self.centre[1]]),np.array([self.bounds[1][0],self.centre[1]])],
                       'y':[np.array([self.centre[0],self.bounds[0][1]]),np.array([self.centre[0],self.bounds[1][1]])]}
            if line in axislines:
                l=axislines[line]
                default_title='vertical slice along '+line+' axis'
            else:
                l=self.bounds
                default_title='vertical slice across grid bounds'
        elif isinstance(line,float) or isinstance(line,int):
            r=0.5*norm(self.bounds[1]-self.bounds[0])
            from math import radians,cos,sin
            theta=radians(line)
            d=r*np.array([sin(theta),cos(theta)])
            l=[self.centre-d,self.centre+d]
            default_title='vertical slice '+("%3.0f"%float(line)).strip()+'$^o$N'
        else:
            l=line
            default_title='vertical slice from ('+("%7.0f"%l[0][0]).strip()+','+("%7.0f"%l[0][1]).strip()+') to ('+("%7.0f"%l[1][0]).strip()+','+("%7.0f"%l[1][1]).strip()+')'
        if norm(l[1]-l[0])>0.0:
            import matplotlib
            if plt==None:
                import matplotlib.pyplot as plt
                loneplot=True
            else: loneplot=False
            matplotlib.rcParams.update({'mathtext.default': 'regular','figure.figsize':(12,9)})
            ax=plt.subplot(subplot,aspect=aspect)
            if variable<>None:
                if len(variable)==self.num_columns: variable=self.column_values_to_block(variable)
            if variable_name: varname=variable_name
            else: varname='Value'
            if block_names:
                if not isinstance(block_names,list): block_names=self.block_name_list
            else: block_names=[]
            track=self.column_track(l)
            if line=='x':
                x0=track[0][1][0]
                for tp in track:
                    tp[1][0]+=x0
                    tp[2][0]+=x0
                if xlabel==None: xlabel='x (m)'
                plt.xlabel(xlabel)
            elif line=='y':
                y0=track[0][1][1]
                for tp in track:
                    tp[1][1]+=y0
                    tp[2][1]+=y0
                if xlabel==None: xlabel='y (m)'
                plt.xlabel(xlabel)
            else:
                if xlabel==None:xlabel='distance (m)'
                plt.xlabel(xlabel)
            verts,vals=[],[]
            if not isinstance(contours,bool): contours=list(contours)
            if contours<>False: xc,yc=[],[]
            for col,inpoint,outpoint in track:
                din,dout=norm(inpoint-l[0]),norm(outpoint-l[0])
                for lay in self.layerlist[1:]:
                    if col.surface>lay.bottom:
                        blkname=self.block_name(lay.name,col.name)
                        if variable<>None: val=variable[self.block_name_index[blkname]]
                        else: val=0
                        vals.append(val)
                        top=self.block_surface(lay,col)
                        verts.append(((din,lay.bottom),(din,top),(dout,top),(dout,lay.bottom)))
                        if blkname in block_names:
                            ax.text(0.5*(din+dout),lay.centre,blkname,clip_on=True,horizontalalignment='center')
                        if contours<>False:
                            xc.append(0.5*(din+dout))
                            yc.append(lay.centre)
            import matplotlib.collections as collections
            if variable<>None: facecolors=None
            else: facecolors=[]
            col=collections.PolyCollection(verts,cmap=colourmap,linewidth=linewidth,facecolors=facecolors)
            if variable<>None: col.set_array(np.array(vals))
            ax.add_collection(col)
            ax.autoscale_view()
            if contours<>False:
                from matplotlib.mlab import griddata
                xc,yc=np.array(xc),np.array(yc)
                valc=np.array(vals)
                bds=((np.min(xc),np.min(yc)),(np.max(xc),np.max(yc)))
                xgrid=np.linspace(bds[0][0],bds[1][0],contour_grid_divisions[0])
                ygrid=np.linspace(bds[0][1],bds[1][1],contour_grid_divisions[1])
                valgrid=griddata(xc,yc,valc,xgrid,ygrid)
                if isinstance(contours,list): cvals=contours
                else: cvals=False
                CS=plt.contour(xgrid,ygrid,valgrid,cvals,colors='k')
                if contour_label_format<>None: plt.clabel(CS, inline=1,fmt=contour_label_format)
            plt.ylabel(ylabel)
            scalelabel=varname
            if unit: scalelabel+=' ('+unit+')'
            if variable<>None:
                cbar=plt.colorbar(col)
                cbar.set_label(scalelabel)
                default_title=varname+' in '+default_title
            if title==None: title=default_title
            plt.title(title)
            if loneplot: plt.show()

    def line_values(self,start,end,variable,divisions=100,coordinate=False):
        """Gets values of variable along specified line through geometry.  Returns two arrays for
        distance along line (or specified coordinate) and value at each position."""
        if isinstance(start,list): start=np.array(start)
        if isinstance(end,list): end=np.array(end)
        x,y=[],[]
        line_length=norm(end-start)
        if line_length>0.0:
            for i in xrange(divisions+1):
                xi=float(i)/(divisions+1)
                pos=(1.-xi)*start+xi*end
                dist=xi*line_length
                blkname=self.block_name_containing_point(pos)
                if blkname:
                    if coordinate: x.append(pos[coordinate])
                    else: x.append(dist)
                    y.append(variable[self.block_name_index[blkname]])
        return np.array(x),np.array(y)

    def polyline_values(self,polyline,variable,divisions=100,coordinate=False):
        """Gets values of a variable along a specified polyline, returning two arrays for distance along the polyline and value."""
        x,y=[],[]
        for i in xrange(len(polyline)-1):
            start,end=polyline[i],polyline[i+1]
            xi,yi=self.line_values(start,end,variable,divisions,coordinate)
            if not coordinate:
                if len(x)>0: xi+=x[-1]  # add end distance from last segment
            x+=list(xi)
            y+=list(yi)
        return np.array(x),np.array(y)

    def well_values(self,well_name,variable,divisions=1,elevation=False):
        """Gets values of a variable down a specified well, returning distance down the well 
        (or elevation) and value."""
        if elevation: coordinate=2  # return coordinate 2 (i.e. z)
        else: coordinate=False
        if well_name in self.well: return self.polyline_values(self.well[well_name].pos,variable,divisions,coordinate)
        else: return None
            
    def line_plot(self,start=None,end=None,variable=None,variable_name=None,unit=None,divisions=100,plt=None,subplot=111,title='',xlabel='distance (m)'):
        """Produces a line plot of the specified variable through a Mulgraph grid."""
        if (start==None) or (end==None):
            [start,end]=self.bounds
            default_title='line plot across grid bounds'
        else:
            if isinstance(start,list): start=np.array(start)
            if isinstance(end,list): end=np.array(end)
            default_title='line plot from ('+("%7.0f"%start[0]).strip()+','+("%7.0f"%start[1]).strip()+','+("%7.0f"%start[2]).strip()+') to ('+("%7.0f"%end[0]).strip()+','+("%7.0f"%end[1]).strip()+','+("%7.0f"%end[2]).strip()+')'
        x,y=self.line_values(start,end,variable,divisions)
        import matplotlib
        if plt==None:
            import matplotlib.pyplot as plt
            loneplot=True
        else: loneplot=False
        matplotlib.rcParams.update({'mathtext.default': 'regular','figure.figsize':(12,9)})
        plt.subplot(subplot)
        if variable<>None:
            if len(variable)==self.num_columns: variable=self.column_values_to_block(variable)
        if variable_name: varname=variable_name
        else: varname='Value'
        plt.plot(x,y)
        plt.xlabel(xlabel)
        ylabel=varname
        if unit: ylabel+=' ('+unit+')'
        plt.ylabel(ylabel)
        default_title+=' of '+varname
        if title==None: title=default_title
        plt.title(title)
        if loneplot: plt.show()

    def optimize(self,nodenames=None,connection_angle_weight=1.0,column_aspect_weight=0.0,column_skewness_weight=0.0,pest=False):
        """Adjusts positions of specified nodes to optimize grid.  If nodenames list is not specified,
        all node positions are optimized.  Grid quality can be defined as a combination of connection
        angle cosine, column aspect ratio and column skewness.  Increasing the weight for any of these
        increases its importance in the evaluation of grid quality.
        Note that an error will result if the connection angle weight and either of the other weights is set to zero- in
        this case there are not enough constraints to fit the parameters.
        If pest is set to True, the PEST parameter estimation software is used to perform the optimization."""
        if nodenames==None: nodenames=self.node.keys()
        # identify which columns are affected:
        colnames=[col.name for col in self.columnlist if (set(nodenames) & set([node.name for node in col.node]))]
        for colname in colnames:
            if self.column[colname].centre_specified: self.column[colname].centre_specified=0
        if connection_angle_weight>0.0: # identify which connections are affected:
            cons=[con for con in self.connectionlist if (set(col.name for col in con.column) & set(colnames))]
        if pest:
            gridfilename='gpestmesh.dat'
            self.write(gridfilename)
            obsgroups=['angle','aspect','skew']
            obsweight={}
            nobs=0
            if connection_angle_weight>0.0:
                obsweight['angle']=connection_angle_weight
                nobs+=len(cons)
            if column_aspect_weight>0.0:
                obsweight['aspect']=column_aspect_weight
                nobs+=len(colnames)
            if column_skewness_weight>0.0:
                obsweight['skew']=column_skewness_weight
                nobs+=len(colnames)
            def write_pest_control_file():
                pst=open('pestmesh.pst','w')
                pst.write('\n'.join([
                            'pcf','* control data','restart estimation',
                            str(2*len(nodenames))+' '+str(nobs)+' 1 0 '+str(len(obsweight)),
                            '    1     1 single point   1   0   0',
                            '5.0   2.0   0.3  0.03    10',
                            '3.0   3.0 0.001  0',
                            '0.1',
                            '30  0.01     3     3  0.01     3',
                            '1     1     1',
                            '* parameter groups',
                            'pos           absolute 0.01  0.0  switch  2.0 parabolic',
                            '* parameter data\n']))
                for name in nodenames:
                    parname='node_'+name.strip()+'_'
                    for i in xrange(2):
                        pst.write(parname+str(i)+' none relative '+'%12.3f'%self.node[name].pos[i]+' '+'%12.3f'%self.bounds[0][i]+
                                  ' '+'%12.3f'%self.bounds[1][i]+' pos 1.0 0.0 1\n')
                pst.write('* observation groups\n')
                for group in obsweight: pst.write(group+'\n')
                pst.write('* observation data\n')
                for group in obsgroups:
                    if group in obsweight:
                        if group=='angle':
                            n=len(cons)
                            target=0.0
                        else:
                            n=len(colnames)
                            target=1.0
                        for i in xrange(n): pst.write(group+str(i)+' %5.2f'%target+' %5.2f'%obsweight[group]+' '+group+'\n')
                pst.write('\n'.join([
                            '* model command line','python pestmesh_model.py',
                            '* model input/output','pestmesh.tpl  pestmesh.in',
                            'pestmesh.ins  pestmesh.out','* prior information\n']))
                pst.close()
            def write_pest_model_file():
                mod=open('pestmesh_model.py','w')
                mod.write('\n'.join([
                        "from mulgrids import *",
                        "geo=mulgrid('"+gridfilename.strip()+"')",
                        "nodenames=[node.replace('\\n','') for node in open('pestmesh_nodes.txt').readlines()]",
                        "dat=open('pestmesh.in').readlines()",
                        "nnodes=len(dat)/2",
                        "for i in xrange(nnodes):",
                        "    x,y=float(dat[2*i][0:20]),float(dat[2*i+1][0:20])",
                        "    nodename=nodenames[i]",
                        "    geo.node[nodename].pos=np.array([x,y])",
                        "colnames=[col.replace('\\n','') for col in open('pestmesh_columns.txt').readlines()]",
                        "for colname in colnames:",
                        "    geo.column[colname].centre_specified=0",
                        "    geo.column[colname].centre=geo.column[colname].centroid",
                        "result=[]\n"]))
                if 'angle' in obsweight:
                    mod.write("connames=[tuple(names.replace('\\n','').split(',')) for names in open('pestmesh_connections.txt').readlines()]\n")
                    mod.write("result+=[geo.connection[conname].angle_cosine for conname in connames]\n")
                if 'aspect' in obsweight:
                    mod.write("result+=[geo.column[colname].side_ratio for colname in colnames]\n")
                if 'skew' in obsweight:
                    mod.write("result+=[geo.column[colname].angle_ratio for colname in colnames]\n")
                mod.write('\n'.join([
                            "f=open('pestmesh.out','w')",
                            "for r in result:",
                            "    f.write('%20.5f\\n'%r)",
                            "f.close()"]))
                mod.close()
            def write_pest_templates():
                tpl=open('pestmesh.tpl','w')
                tpl.write("ptf $\n")
                for name in nodenames:
                    parname='node_'+name.strip()+'_'
                    for i in xrange(2): tpl.write("$"+'%18s'%(parname+str(i))+"$\n")
                tpl.close()
                ins=open('pestmesh.ins','w')
                ins.write("pif #\n")
                for group in obsgroups:
                    if group in obsweight:
                        if group=='angle': n=len(cons)
                        else: n=len(colnames)
                        for i in xrange(n): ins.write("l1 ["+group+str(i)+"]1:20\n")
                ins.close()
            file('pestmesh_nodes.txt','w').write('\n'.join(nodenames))
            file('pestmesh_columns.txt','w').write('\n'.join(colnames))
            if 'angle' in obsweight:
                file('pestmesh_connections.txt','w').write('\n'.join([','.join([col.name for col in con.column]) for con in cons]))
            write_pest_control_file()
            write_pest_templates()
            write_pest_model_file()
            from os import system
            system('pest pestmesh.pst')
            dat=open('pestmesh.in').readlines()
            for i,nodename in enumerate(nodenames):
                x,y=float(dat[2*i][0:20]),float(dat[2*i+1][0:20])
                self.node[nodename].pos=np.array([x,y])
            for colname in colnames:
                self.column[colname].centre=self.column[colname].centroid
        else:
            from scipy.optimize import leastsq
            def update_grid(xnode):
                for xn,nodename in zip(xnode,nodenames): self.node[nodename].pos=xn
                for colname in colnames: self.column[colname].centre=self.column[colname].centroid
            def f(x):
                xpos=[np.array([x[2*i],x[2*i+1]]) for i in xrange(len(nodenames))]
                update_grid(xpos)
                if connection_angle_weight: con_angle=[connection_angle_weight*con.angle_cosine for con in cons]
                else: con_angle=[]
                if column_aspect_weight: col_aspect=[column_aspect_weight*(self.column[colname].side_ratio-1.0) for colname in colnames]
                else: col_aspect=[]
                if column_skewness_weight: col_skewness=[column_skewness_weight*(self.column[colname].angle_ratio-1.0) for colname in colnames]
                else: col_skewness=[]
                return np.array(con_angle+col_aspect+col_skewness)
            x0=[]
            for nodename in nodenames: x0+=list(self.node[nodename].pos)
            leastsq(f,np.array(x0))

    def connection_with_nodes(self,nodes):
        """Returns a connection, if one exists, containing the specified two nodes."""
        for con in self.connectionlist:
            if all([node in con.node for node in nodes]): return con
        return None

    def get_boundary_nodes(self):
        """Returns an ordered list of the nodes on the outer boundary of the grid."""
        def next_bdy_node(n):
            for col in n.column:
                i=col.node.index(n)
                n2=col.node[(i+1)%col.num_nodes]
                con=self.connection_with_nodes([n,n2])
                if not con: return n2
            return None
        # look for a starting node along the left-hand edge of the grid (this avoids
        # picking up any interior boundaries):
        startnode=None
        xmin=self.bounds[0][0]
        leftnodes=[node for node in self.nodelist if node.pos[0]==xmin]
        for node in leftnodes:
            nextnode=next_bdy_node(node)
            if nextnode:
                startnode=node
                break
        if startnode:
            bdynodes=[]
            node=startnode
            back=False
            while not back:
                bdynodes.append(node)
                node=next_bdy_node(node)
                back=node.name==startnode.name
            return bdynodes
        else: return []
    boundary_nodes=property(get_boundary_nodes)

    def get_boundary_polygon(self):
        """Returns the simplest polygon representing the boundary of the grid."""
        return simplify_polygon([node.pos for node in self.boundary_nodes])
    boundary_polygon=property(get_boundary_polygon)

    def get_boundary_columns(self):
        """Returns a set of columns on the outer boundary of the grid- those columns that contain at least
        two boundary nodes."""
        bdynodes=set(self.boundary_nodes)
        return set([col for col in self.columnlist if len(set(col.node) & bdynodes)>=2])
    boundary_columns=property(get_boundary_columns)

    def get_grid3d(self):
        """Returns 3D nodes and elements for the grid, and a dictionary of 'extra nodes' needed
        at the top surface from varying surface elevation.  """
        node3d={}
        index=0
        # create subsurface nodes
        for lay in self.layerlist[1:]:
            for node in self.nodelist:
                if any([col.surface>lay.bottom for col in node.column]):
                    pos3d=np.array(list(node.pos)+[lay.bottom])
                    node3d[lay.name,node.name]=(index,pos3d)
                    index+=1
        # identify where 'extra' nodes are needed
        extra_node={}
        for col in [c for c in self.columnlist if c.surface<>None]:
            for node in col.node:
                if node.name in extra_node: extra_node[node.name].append(col.name)
                else: extra_node[node.name]=[col.name]
        # create surface nodes
        for node in self.nodelist:
            if any([(col.surface==None) for col in node.column]):
                pos3d=np.array(list(node.pos)+[self.layerlist[0].bottom])
                node3d[self.layerlist[0].name,node.name]=(index,pos3d)
                index+=1
            elif node.name in extra_node:
                for colname in extra_node[node.name]:
                    pos3d=np.array(list(node.pos)+[self.column[colname].surface])
                    node3d[self.layerlist[0].name,node.name,colname]=(index,pos3d)
                    index+=1
        # create elements
        elt3d=[]
        atmlayer=self.layerlist[0]
        for ilayer,lay in enumerate(self.layerlist[1:]):
            for col in [c for c in self.columnlist if c.surface>lay.bottom]:
                elt=[]
                if col.num_nodes>4: # funny-shaped columns- remove nodes with largest angles
                    angles=np.array(col.interior_angles)
                    bad_index=list(np.argsort(-angles))[0:col.num_nodes-4] # indices of corners to remove
                    icorner=range(col.num_nodes)
                    for a in bad_index: icorner.remove(a)
                    corners=[col.node[ic] for ic in icorner]
                else: corners=col.node
                for node in corners: elt.append(node3d[lay.name,node.name][0])
                if ilayer==self.num_layers-col.num_layers-1: # top block
                    for node in corners:
                        if node.name in extra_node: elt.append(node3d[atmlayer.name,node.name,col.name][0])
                        else: elt.append(node3d[atmlayer.name,node.name][0])
                else:
                    for node in corners: elt.append(node3d[self.layerlist[ilayer].name,node.name][0])
                elt3d.append((lay,col,elt))
        return node3d,extra_node,elt3d
    grid3d=property(get_grid3d)

    def get_vtk_grid(self,arrays={}):
        """Returns a vtkUnstructuredGrid object (for visualisation with VTK) corresponding to the grid in 3D. 
        VTK data arrays may optionally be added."""
        from vtk import vtkUnstructuredGrid,vtkPoints,vtkIdList
        node3d,extra_node,elt3d=self.grid3d
        # construct the vtk grid
        nele=len(elt3d)
        grid=vtkUnstructuredGrid()
        pts=vtkPoints()
        pts.SetNumberOfPoints(len(node3d))
        for (key,(i,node)) in node3d.items(): pts.SetPoint(i,node)
        grid.SetPoints(pts)
        # create and add cells
        VTK_HEXAHEDRON,VTK_WEDGE=12,13
        celltype={6:VTK_WEDGE,8:VTK_HEXAHEDRON}
        for ielt,(lay,col,elt) in enumerate(elt3d):
            ids=vtkIdList()
            for i in elt: ids.InsertNextId(i)
            grid.InsertNextCell(celltype[len(elt)],ids)
        for array_type,array_dict in arrays.items():
            sortedkeys=array_dict.keys()
            sortedkeys.sort()
            if array_type=='Block':
                for key in sortedkeys: grid.GetCellData().AddArray(array_dict[key])
            elif array_type=='Node':
                for key in sortedkeys: grid.GetPointData().AddArray(array_dict[key])
        return grid

    def get_vtk_data(self):
        """Returns a dictionary of VTK data arrays from the grid (layer and column indices (zero-based), column areas, 
        block numbers and volumes for each block."""
        from vtk import vtkFloatArray,vtkIntArray,vtkCharArray
        arrays={'Block':{'Name':vtkCharArray(),'Layer index':vtkIntArray(),'Column index':vtkIntArray(),'Column area':vtkFloatArray(),'Column elevation':vtkFloatArray(),'Block number':vtkIntArray(),'Volume':vtkFloatArray()},'Node':{}}
        nele=self.num_underground_blocks
        string_properties=['Name']
        string_length=5
        array_length={'Block':nele,'Node':0}
        for array_type,array_dict in arrays.items():
            for name,array in array_dict.items():
                array.SetName(name)
                if name in string_properties:
                    array.SetNumberOfComponents(string_length)
                    array.SetNumberOfTuples(array_length[array_type])
                else:
                    array.SetNumberOfValues(array_length[array_type])
                    array.SetNumberOfComponents(1)
        layerindex=self.layer_index
        colindex=self.column_index
        for iblk,blockname in enumerate(self.block_name_list[self.num_atmosphere_blocks:]):
            layname,colname=self.layer_name(blockname),self.column_name(blockname)
            lay,col=self.layer[layname],self.column[colname]
            arrays['Block']['Name'].SetTupleValue(iblk,blockname)
            arrays['Block']['Layer index'].SetValue(iblk,layerindex[layname])
            arrays['Block']['Column index'].SetValue(iblk,colindex[colname])
            arrays['Block']['Column area'].SetValue(iblk,col.area)
            arrays['Block']['Column elevation'].SetValue(iblk,col.surface)
            arrays['Block']['Block number'].SetValue(iblk,self.block_name_index[blockname]+1)
            arrays['Block']['Volume'].SetValue(iblk,self.block_volume(lay,col))
        return arrays
    vtk_data=property(get_vtk_data)
        
    def write_bna(self,filename=''):
        """Writes grid to Atlas BNA file."""
        from os.path import splitext
        if filename=='':
            if self.filename=='': filename='geometry.bna'
            else:
                base,ext=splitext(self.filename)
                filename=base+'.bna'
        f=open(filename,'w')
        headerfmt='"%3s","",%1d\n'
        nodefmt='%10.2f,%10.2f\n'
        for col in self.columnlist:
            f.write(headerfmt% (col.name,col.num_nodes+1))
            for node in col.node+[col.node[0]]:
                f.write(nodefmt%(node.pos[0],node.pos[1]))
        f.close()
    def export_surfer(self,filename=''): self.write_bna(filename) # for backwards compatibility

    def write_vtk(self,filename='',arrays=None,wells=False):
        """Writes *.vtu file for a vtkUnstructuredGrid object corresponding to the grid in 3D, with the specified filename,
        for visualisation with VTK."""
        from vtk import vtkXMLUnstructuredGridWriter
        from os.path import splitext
        if filename=='':
            if self.filename=='': filename='geometry.vtu'
            else:
                base,ext=splitext(self.filename)
                filename=base+'.vtu'
        if wells:
            base,ext=splitext(filename)
            self.write_well_vtk(base+'_wells.vtu')
        if arrays==None: arrays=self.vtk_data
        vtu=self.get_vtk_grid(arrays)
        writer=vtkXMLUnstructuredGridWriter()
        writer.SetFileName(filename)
        writer.SetInput(vtu)
        writer.Write()
        
    def get_well_vtk_grid(self):
        """Returns a VTK grid corresponding to the wells in the geometry."""
        from vtk import vtkUnstructuredGrid,vtkPoints,vtkIdList,vtkCharArray
        grid=vtkUnstructuredGrid()
        num_deviations=sum([well.num_deviations+1 for well in self.welllist])
        pts=vtkPoints()
        pts.SetNumberOfPoints(num_deviations)
        i=0
        for well in self.welllist:
            for p in well.pos:
                pts.SetPoint(i,list(p))
                i+=1
        grid.SetPoints(pts)
        VTK_POLY_LINE=4
        i=0
        for well in self.welllist:
            ids=vtkIdList()
            for p in well.pos:
                ids.InsertNextId(i)
                i+=1
            grid.InsertNextCell(VTK_POLY_LINE,ids)
        namearray=vtkCharArray()
        string_length=5
        namearray.SetName('Name')
        namearray.SetNumberOfComponents(string_length)
        namearray.SetNumberOfTuples(self.num_wells)
        for i,well in enumerate(self.welllist):
            namearray.SetTupleValue(i,well.name)
        grid.GetCellData().AddArray(namearray)
        return grid

    def write_well_vtk(self,filename=''):
        from vtk import vtkXMLUnstructuredGridWriter
        if filename=='':
            if self.filename=='': filename='geometry_wells.vtu'
            else:
                from os.path import splitext
                base,ext=splitext(self.filename)
                filename=base+'_wells.vtu'
        vtu=self.get_well_vtk_grid()
        writer=vtkXMLUnstructuredGridWriter()
        writer.SetFileName(filename)
        writer.SetInput(vtu)
        writer.Write()

    def fit_surface(self,data,alpha=0.1,beta=0.1,columns=[],min_columns=[],grid_boundary=False):
        """Fits column surface elevations to the grid from the data, using least-squares bilinear finite element fitting with
        Sobolev smoothing.  The parameter data should be in the form of a 3-column array with x,y,z data in each row.
        The smoothing parameters alpha and beta control the first and second derivatives of the surface.
        If the parameter columns is specified, elevations will only be fitted for the specified column names.
        For columns with names in min_columns, column elevations will be calculated as the minimum of the fitted nodal
        elevations.  For all other columns, the average of the nodal values is used.  If grid_boundary is True, only data
        inside the bounding polygon of the grid are used- this can speed up the fitting if there are many data outside the 
        grid, and the grid has a simply-shaped boundary."""

        if columns==[]: columns=self.columnlist
        else: 
            if isinstance(columns[0],str): columns=[self.column[col] for col in columns]
        if min_columns<>[]:
            if not isinstance(min_columns[0],str): min_columns=[col.name for col in min_columns]
        if all([col.num_nodes in [3,4] for col in columns]):
            nodes=set([])
            for col in columns: nodes=nodes | set(col.node)
            nodes=list(nodes)
            node_index=dict([(node.name,i) for i,node in enumerate(nodes)])
            num_nodes=len(nodes)
            bbox=bounds_of_points([node.pos for node in nodes])
            # assemble least squares FEM fitting system:
            from scipy import sparse
            A=sparse.lil_matrix((num_nodes,num_nodes))
            b=np.zeros(num_nodes)
            guess=None
            if grid_boundary: bounds=self.boundary_polygon
            else: bounds=None
            qtree=quadtree(bbox,columns)
            import sys
            nd=len(data)
            for idata,d in enumerate(data):
                col=self.column_containing_point(d[0:2],columns,guess,bounds,qtree)
                percent=100.*idata/nd
                ps='fit_surface %3.0f%% done'% percent
                sys.stdout.write('%s\r' % ps)
                sys.stdout.flush()
                if col:
                    xi=col.local_pos(d[0:2])
                    if xi<>None:
                        guess=col
                        psi=col.basis(xi)
                        for i,nodei in enumerate(col.node):
                            I=node_index[nodei.name]
                            for j,nodej in enumerate(col.node):
                                J=node_index[nodej.name]
                                A[I,J]+=psi[i]*psi[j]
                            b[I]+=psi[i]*d[2]
            # add smoothing:
            smooth={3: 0.5*alpha*np.array([[1.,0.,-1.],[0.,1.,-1.],[-1.,-1.,2.]]),
                    4: alpha/6.*np.array([[4.,-1.,-2.,-1.],[-1.,4.,-1.,-2.],[-2.,-1.,4.,-1.],[-1.,-2.,-1.,4.]])+
                    beta*np.array([[1.,-1.,1.,-1.],[-1.,1.,-1.,1.],[1.,-1.,1.,-1.],[-1.,1.,-1.,1.]])}
            for col in columns:
                for i,nodei in enumerate(col.node):
                    I=node_index[nodei.name]
                    for j,nodej in enumerate(col.node):
                        J=node_index[nodej.name]
                        A[I,J]+=smooth[col.num_nodes][i,j]
            A=A.tocsr()
            from scipy.sparse.linalg import spsolve
            z=spsolve(A,b)
            # assign nodal elevations to columns:
            for i,col in enumerate(columns):
                nodez=[z[node_index[node.name]] for node in col.node]
                if col.name in min_columns: col.surface=min(nodez)
                else: col.surface=(sum(nodez))/col.num_nodes
                col.num_layers=len([layer for layer in self.layerlist[1:] if layer.bottom<col.surface])
            self.setup_block_name_index()
        else: print 'Grid selection contains columns with more than 4 nodes: not supported.'

    def refine(self,columns=[]):
        """Refines selected columns in the grid by a factor of two.  If no columns are specified, all columns are refined.
        Refinement is carried out by splitting: each column is divided into four.  Triangular transition columns are
        added around the edge of the refinement region as needed.  Only 3 and 4-sided columns are supported."""
        if columns==[]: columns=self.columnlist
        else: 
            if isinstance(columns[0],str): columns=[self.column[col] for col in columns]
        connections=set([])
        for col in columns: connections=connections | col.connection
        columns_plus_edge=set([])
        for con in connections: columns_plus_edge=columns_plus_edge | set(con.column)
        if all([col.num_nodes in [3,4] for col in columns_plus_edge]):
            edge=columns_plus_edge-set(columns)
            next_nodeno=max([self.column_number_from_name(n.name) for n in self.nodelist])+1
            next_colno=max([self.column_number_from_name(col.name) for col in self.columnlist])+1
            casefn=[lowercase,uppercase][self.uppercase_names]
            justfn=[ljust,rjust][self.right_justified_names]
            def create_mid_node(node1,node2,sidenodes,next_nodeno,justfn,casefn):
                midpos=0.5*(node1.pos+node2.pos)
                nodenames=(node1.name,node2.name)
                name=self.column_name_from_number(next_nodeno,justfn,casefn); next_nodeno+=1
                self.add_node(node(name,midpos))
                sidenodes[nodenames]=self.nodelist[-1]
                sidenodes[nodenames[1],nodenames[0]]=sidenodes[nodenames]
                return sidenodes,next_nodeno
            # create midside nodes at connections:
            sidenodes={}
            for con in connections:
                sidenodes,next_nodeno=create_mid_node(con.node[0],con.node[1],sidenodes,next_nodeno,justfn,casefn)
            # create midside nodes on grid boundaries in the refinement area:
            bdy=self.boundary_nodes
            for col in columns_plus_edge:
                nn=col.num_nodes
                for i,corner in enumerate(col.node):
                    next_corner=col.node[(i+1)%nn]
                    if (corner in bdy) and (next_corner in bdy):
                        sidenodes,next_nodeno=create_mid_node(corner,next_corner,sidenodes,next_nodeno,justfn,casefn)
            def transition_type(nn,sides):
                # returns transition type- classified by how many refined sides, starting side, and range
                nref=len(sides)
                missing=list(set(range(nn))-set(sides))
                nunref=len(missing)
                if nref==1: return 1,sides[0],0
                elif nref==nn: return nn,0,nn-1
                elif nunref==1: return nref,(missing[0]+1)%nn,nn-2
                elif nn==4 and nref==2:
                    diff=sides[1]-sides[0]
                    if diff<3: return nref,sides[0],diff
                    else: return nref,sides[1],1
                print 'Error in refine()- unrecognised transition type:',nref,'of',nn,'sides refined.'
            transition_column={3:{(1,0): ((0,(0,1),2),((0,1),1,2)),  # how to subdivide, based on no. of nodes, no. of
                                  (2,1): ((0,(0,1),(1,2),2),((0,1),1,(1,2))), # refined sides and range of refined sides
                                  (3,2): ((0,(0,1),(2,0)),((0,1),1,(1,2)),((1,2),2,(2,0)),((0,1),(1,2),(2,0)))},
                               4:{(1,0): ((0,(0,1),3),((0,1),1,2),((0,1),2,3)),
                                  (2,1): ((0,(0,1),'c'),((0,1),1,(1,2),'c'),((1,2),2,'c'),(2,3,'c'),(0,'c',3)),
                                  (2,2): ((0,(0,1),(2,3),3),((0,1),1,2,(2,3))),
                                  (3,2): ((0,(0,1),(2,3),3),((0,1),1,(1,2)),((1,2),2,(2,3)),((0,1),(1,2),(2,3))),
                                  (4,3): ((0,(0,1),'c',(3,0)),((0,1),1,(1,2),'c'),((1,2),2,(2,3),'c'),((2,3),3,(3,0),'c'))}}
            # create refined columns (and centre nodes for quadrilaterals that need them):
            centrenodes={}
            for col in columns_plus_edge:
                nn=col.num_nodes
                refined_sides=[]
                for i,corner in enumerate(col.node):
                    if (corner.name,col.node[(i+1)%nn].name) in sidenodes: refined_sides.append(i)
                nrefined,istart,irange=transition_type(nn,refined_sides)
                if (col.num_nodes==4) and ((nrefined==4) or ((nrefined==2) and (irange==1))):
                    # create quadrilateral centre node:
                    name=self.column_name_from_number(next_nodeno,justfn,casefn); next_nodeno+=1
                    self.add_node(node(name,col.centre))
                    centrenodes[col.name]=self.nodelist[-1]
                for subcol in transition_column[nn][nrefined,irange]:
                    name=self.column_name_from_number(next_colno,justfn,casefn); next_colno+=1
                    nodes=[]
                    for vert in subcol:
                        if isinstance(vert,int): n=col.node[(istart+vert)%nn]
                        elif vert=='c': n=centrenodes[col.name]
                        else: n=sidenodes[tuple([col.node[(istart+i)%nn].name for i in vert])]
                        nodes.append(n)
                    self.add_column(column(name,nodes,surface=col.surface))
                    self.columnlist[-1].num_layers=col.num_layers
            # clean up:
            for col in columns_plus_edge: self.delete_column(col.name)
            for con in self.missing_connections: self.add_connection(con)
            self.identify_neighbours()
            self.setup_block_name_index()
        else: print 'Grid selection contains columns with more than 4 nodes: not supported.'
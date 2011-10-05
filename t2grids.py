"""For manipulating TOUGH2 grids."""

"""
Copyright 2011 University of Auckland.

This file is part of PyTOUGH.

PyTOUGH is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

PyTOUGH is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with PyTOUGH.  If not, see <http://www.gnu.org/licenses/>."""

from mulgrids import *

class rocktype(object):
    """Rock type"""
    def __init__(self,name="dfalt",nad=0,density=2600.0,porosity=0.1,permeability=np.array([1.0e-15,1.0e-15,1.0e-15]),conductivity=1.5,specific_heat=900.0):
        self.name=name
        self.nad=nad
        self.density=density
        self.porosity=porosity
        if isinstance(permeability,list): permeability=np.array(permeability)
        self.permeability=permeability
        self.conductivity=conductivity
        self.specific_heat=specific_heat
        self.compressibility=0.0
        self.expansivity=0.0
        self.dry_conductivity=0.0
        self.tortuosity=0.0
        self.relative_permeability={}
        self.capillarity={}
    def __repr__(self):
        return self.name

class t2block(object):
    """Grid block"""
    def __init__(self,name='     ',volume=1.0,blockrocktype=rocktype(),centre=None,atmosphere=False,ahtx=None,pmx=None):
        self.name=name
        self.nseq,self.nadd=None,None
        self.volume=volume
        self.rocktype=blockrocktype
        if isinstance(centre,list): centre=np.array(centre)
        self.centre=centre
        self.atmosphere=atmosphere
        self.ahtx=ahtx
        self.pmx=pmx
        self.connection_name=set([])
    def __repr__(self): return self.name
    def get_num_connections(self): return len(self.connection_name)
    num_connections=property(get_num_connections)
    def get_neighbour_names(self):
        """Returns a set of neighbouring block names- those connected to this one."""
        return set([[blkname for blkname in cn if blkname<>self.name][0] for cn in self.connection_name])
    neighbour_name=property(get_neighbour_names)

class t2connection(object):
    """Connection between two blocks"""
    def __init__(self,blocks=[t2block(),t2block()],direction=0,distance=[0.0,0.0],area=1.0,dircos=0.0,sigma=None):
        self.block=blocks
        self.nseq,self.nad1,self.nad2=None,None,None
        self.direction=direction # permeability direction
        self.distance=distance
        self.area=area
        self.dircos=dircos # direction cosine
        self.sigma=sigma # radiant emittance factor (TOUGH2)
    def __repr__(self):
        return self.block[0].name+':'+self.block[1].name

class t2grid(object):
    """TOUGH2 grid"""
    def __init__(self): self.empty()

    def get_num_rocktypes(self):
        return len(self.rocktypelist)
    num_rocktypes=property(get_num_rocktypes)
        
    def get_num_blocks(self):
        return len(self.blocklist)
    num_blocks=property(get_num_blocks)
        
    def get_num_connections(self):
        return len(self.connectionlist)
    num_connections=property(get_num_connections)

    def get_num_atmosphere_blocks(self):
        return len(self.atmosphere_blocks)
    num_atmosphere_blocks=property(get_num_atmosphere_blocks)

    def get_num_underground_blocks(self):
        return self.num_blocks-self.num_atmosphere_blocks
    num_underground_blocks=property(get_num_underground_blocks)
    
    def get_atmosphere_blocks(self):
        return [blk for blk in self.blocklist if blk.atmosphere]
    atmosphere_blocks=property(get_atmosphere_blocks)

    def get_block_centres_defined(self):
        if self.num_atmosphere_blocks==1: istart=1
        else: istart=0
        return any([blk.centre<>None for blk in self.blocklist[istart:]])
    block_centres_defined=property(get_block_centres_defined)

    def calculate_block_centres(self,geo):
        """Calculates block centres from geometry object."""
        if geo.atmosphere_type==0:
            istart=1
            self.blocklist[0].centre=None  # centre not well defined for single atmosphere block
        else: istart=0
        for blk in self.blocklist[istart:]:
            layername=geo.layer_name(blk.name)
            lay=geo.layer[layername]
            colname=geo.column_name(blk.name)
            col=geo.column[colname]
            blk.centre=geo.block_centre(lay,col)

    def rocktype_frequency(self,rockname):
        """Returns how many times the rocktype with given name is used in the grid."""
        return [blk.rocktype.name for blk in self.blocklist].count(rockname)
    def get_rocktype_frequencies(self):
        """Returns a list of tuples of occurring frequencies of rock types in the grid and the names of rocktypes with that frequency, 
        ordered by increasing frequency."""
        freq=[(rt.name,self.rocktype_frequency(rt.name)) for rt in self.rocktypelist]
        occurring_freqs=list(set([item[1] for item in freq]))
        occurring_freqs.sort()
        frocks=dict([(f,[]) for f in occurring_freqs])
        for item in freq: frocks[item[1]].append(item[0])
        return [(f,frocks[f]) for f in occurring_freqs]
    rocktype_frequencies=property(get_rocktype_frequencies)

    def sort_rocktypes(self):
        """Sorts rocktype list in alphabetical order by name."""
        rocknames=[rt.name for rt in self.rocktypelist]
        rocknames.sort()
        self.rocktypelist=[self.rocktype[name] for name in rocknames]

    def __repr__(self):
        return str(self.num_rocktypes)+' rock types; '+str(self.num_blocks)+' blocks; '+str(self.num_connections)+' connections'

    def __add__(self,other):
        """Adds two grids together."""
        result=t2grid()
        for grid in [self,other]:
            for rt in grid.rocktypelist: result.add_rocktype(rt)
            for blk in grid.blocklist: result.add_block(blk)
            for con in grid.connectionlist: result.add_connection(con)
        return result

    def empty(self):
        """Empties a TOUGH2 grid"""
        self.rocktypelist=[]
        self.blocklist=[]
        self.connectionlist=[]
        self.rocktype={}
        self.block={}
        self.connection={}
        
    def add_rocktype(self,newrocktype=rocktype()):
        """Adds a rock type to the grid.  Any existing rocktype of the same name is replaced."""
        if newrocktype.name in self.rocktype:
            i=self.rocktypelist.index(self.rocktype[newrocktype.name])
            self.rocktypelist[i]=newrocktype
        else: self.rocktypelist.append(newrocktype)
        self.rocktype[newrocktype.name]=newrocktype

    def delete_rocktype(self,rocktypename):
        """Deletes a rock type from the grid"""
        if rocktypename in self.rocktype:
            rt=self.rocktype[rocktypename]
            del self.rocktype[rocktypename]
            self.rocktypelist.remove(rt)

    def clean_rocktypes(self):
        """Deletes any unused rock types from the grid"""
        unused_rocktypes=[]
        for rt in self.rocktypelist:
            if self.rocktype_frequency(rt.name)==0: unused_rocktypes.append(rt.name)
        for name in unused_rocktypes: self.delete_rocktype(name)

    def add_block(self,newblock=t2block()):
        """Adds a block to the grid"""
        if newblock.name in self.block:
            i=self.blocklist.index(self.block[newblock.name])
            self.blocklist[i]=newblock
        else: self.blocklist.append(newblock)
        self.block[newblock.name]=newblock
    
    def delete_block(self,blockname):
        """Deletes a block from the grid"""
        if blockname in self.block:
            blk=self.block[blockname]
            for conname in blk.connection_name: self.delete_connection(conname)
            del self.block[blockname]
            if blk in self.blocklist: self.blocklist.remove(blk)

    def add_connection(self,newconnection=t2connection()):
        """Adds a connection to the grid"""
        conname=tuple([blk.name for blk in newconnection.block])
        if conname in self.connection: 
            i=self.connectionlist.index(self.connection[conname])
            self.connectionlist[i]=newconnection
        else: self.connectionlist.append(newconnection)
        self.connection[conname]=newconnection
        for block in newconnection.block: block.connection_name.add(conname)

    def delete_connection(self,connectionname):
        """Deletes a connection from the grid"""
        if connectionname in self.connection:
            con=self.connection[connectionname]
            del self.connection[connectionname]
            self.connectionlist.remove(con)

    def block_index(self,blockname):
        """Returns index of block with specified name in the block list of the grid"""
        if blockname in self.block:
            return self.blocklist.index(self.block[blockname])
        else: return None

    def connection_index(self,connectionnames):
        """Returns index of connection with specified pair of names in the connection list of the grid"""
        if connectionnames in self.connection:
            return self.connectionlist.index(self.connection[connectionnames])
        else: return None

    def fromgeo(self,geo):
        """Converts a MULgraph grid to a TOUGH2 grid"""
        self.empty()
        self.add_rocktype(rocktype()) # add default rock type
        self.add_blocks(geo)
        self.add_connections(geo)
        return self

    def add_blocks(self,geo=mulgrid()):
        """Adds blocks to grid from MULgraph geometry file"""
        self.add_atmosphereblocks(geo)
        self.add_underground_blocks(geo)

    def add_atmosphereblocks(self,geo=mulgrid()):
        """Adds atmosphere blocks from geometry"""
        atmosrocktype=self.rocktypelist[0]
        if geo.atmosphere_type==0: # one atmosphere block
            atmblockname=geo.block_name(geo.layerlist[0].name,geo.atmosphere_column_name)
            centre=None
            self.add_block(t2block(atmblockname,geo.atmosphere_volume,atmosrocktype,centre=centre,atmosphere=True))
        elif geo.atmosphere_type==1: # one atmosphere block per column
            for col in geo.columnlist:
                atmblockname=geo.block_name(geo.layerlist[0].name,col.name)
                centre=geo.block_centre(geo.layerlist[0],col)
                self.add_block(t2block(atmblockname,geo.atmosphere_volume,atmosrocktype,centre=centre,atmosphere=True))

    def add_underground_blocks(self,geo=mulgrid()):
        """Add underground blocks from geometry"""
        for lay in geo.layerlist[1:]:
            for col in [col for col in geo.columnlist if col.surface>lay.bottom]:
                name=geo.block_name(lay.name,col.name)
                centre=geo.block_centre(lay,col)
                self.add_block(t2block(name,geo.block_volume(lay,col),self.rocktypelist[0],centre=centre))

    def add_connections(self,geo=mulgrid()):
        """Add connections from geometry"""
        for thislayer in geo.layerlist[1:]:
            layercols=[col for col in geo.columnlist if col.surface>thislayer.bottom]
            self.add_vertical_layer_connections(geo,thislayer,layercols)
            self.add_horizontal_layer_connections(geo,thislayer,layercols)

    def add_vertical_layer_connections(self,geo=mulgrid(),thislayer=layer(),layercols=[]):
        """Add vertical connections in layer"""
        for col in layercols:
            thisblk=self.block[geo.block_name(thislayer.name,col.name)]
            if (geo.layerlist.index(thislayer)==1) or (col.surface<=thislayer.top): # connection to atmosphere
                abovelayer=geo.layerlist[0]
                abovedist=geo.atmosphere_connection
                belowdist=col.surface-thisblk.centre[2]
                if geo.atmosphere_type==0:
                    aboveblk=self.blocklist[0]
                elif geo.atmosphere_type==1:
                    aboveblk=self.block[geo.block_name(abovelayer.name,col.name)]
                else: # no atmosphere blocks
                    continue
            else:
                ilayer=geo.layerlist.index(thislayer)
                abovelayer=geo.layerlist[ilayer-1]
                aboveblk=self.block[geo.block_name(abovelayer.name,col.name)]
                abovedist=aboveblk.centre[2]-abovelayer.bottom
                belowdist=thislayer.top-thislayer.centre
            con=t2connection([thisblk,aboveblk],3,[belowdist,abovedist],col.area,-1.0)
            self.add_connection(con)

    def add_horizontal_layer_connections(self,geo=mulgrid(),thislayer=layer(),layercols=[]):
        """Add horizontal connections in layer"""
        from math import cos,sin
        layercolset=set(layercols)
        anglerad=geo.permeability_angle*np.pi/180.
        c,s=cos(anglerad),sin(anglerad)
        rotation=np.array([[c,s],[-s,c]])
        for con in [con for con in geo.connectionlist if set(con.column).issubset(layercolset)]:
            conblocks=[self.block[geo.block_name(thislayer.name,concol.name)] for concol in con.column]
            [dist,area]=geo.connection_params(con,thislayer)
            d=conblocks[1].centre-conblocks[0].centre
            d2=np.dot(rotation,d[0:2])
            direction=np.argmax(abs(d2))+1
            dircos=-d[2]/np.linalg.norm(d)
            self.add_connection(t2connection(conblocks,direction,dist,area,dircos))

    def copy_connection_directions(self,geo,grid):
        """Copies connection permeability directions from another grid.  It is assumed the two grids have
        the same column structure.  The geo argument is the geometry file corresponding to grid."""
        nlayercons=len(geo.connectionlist)
        noldcons=len(grid.connectionlist)
        # create dictionary of permeability directions within a layer (from bottom layer, assumed complete):
        dirn={}
        for i,con in enumerate(geo.connectionlist):
            dirn[(con.column[0].name,con.column[1].name)]=grid.connectionlist[noldcons-nlayercons+i].direction
        # transfer permeability directions to horizontal connections:
        for con in self.connectionlist:
            if con.direction<3:
                colnames=tuple([geo.column_name(blk.name) for blk in con.block])
                con.direction=dirn[colnames]

    def get_unconnected_blocks(self):
        """Returns a set of blocks in the grid that are not connected to any other blocks."""
        return set([blk.name for blk in self.blocklist if len(blk.connection_name)==0])
    unconnected_blocks=property(get_unconnected_blocks)
    
    def get_isolated_rocktype_blocks(self):
        """Returns a list of blocks with isolated rocktypes- that is, blocks with a rocktype different from that of
        all other blocks they are connected to."""
        bc_volume=1.e20  # blocks with volume greater than this are considered boundary condition blocks and not counted
        return set([blk.name for blk in self.blocklist if (blk.volume<bc_volume) and not (blk.rocktype.name in [self.block[nbr].rocktype.name for nbr in blk.neighbour_name])])
    isolated_rocktype_blocks=property(get_isolated_rocktype_blocks)

    def check(self,fix=False,silent=False):
        """Checks a grid for errors, and optionally fixes them.  Errors checked for are:
        - blocks not connected to any other blocks
        - blocks with isolated rocktypes
        Returns True if no errors were found, and False otherwise.  If silent is True, there is no printout.
        Unconnected blocks are fixed by deleting them.  Isolated rocktype blocks are fixed by assigning them the
        most popular rocktype of their neighbours."""
        ok=True
        ub=self.unconnected_blocks
        if len(ub)>0:
            ok=False
            if not silent: print 'Unconnected blocks:',list(ub)
            if fix:
                for blk in ub: self.delete_block(blk)
                if not silent: print 'Unconnected blocks fixed.'
        ib=self.isolated_rocktype_blocks
        if len(ib)>0:
            ok=False
            if not silent: print 'Isolated rocktype blocks:',list(ib)
            if fix:
                for blk in ib:
                    nbr_rocktype=[self.block[nbr].rocktype.name for nbr in self.block[blk].neighbour_name]
                    pop_rocktype=max(set(nbr_rocktype), key=nbr_rocktype.count)
                    self.block[blk].rocktype=self.rocktype[pop_rocktype]
                if not silent: print 'Isolated rocktype blocks fixed.'
        if ok and not silent: print 'No problems found.'
        return ok

    def get_rocktype_indices(self):
        """Returns an integer array containing the rocktype index for each block in the grid."""
        rocknames=[rt.name for rt in self.rocktypelist]
        return np.array([rocknames.index(blk.rocktype.name) for blk in self.blocklist])
    rocktype_indices=property(get_rocktype_indices)

    def get_vtk_data(self,geo):
        """Returns dictionary of VTK data arrays from rock types.  The geometry object geo must be passed in."""
        from vtk import vtkIntArray,vtkFloatArray,vtkCharArray
        arrays={'Block':{'Rock type index':vtkIntArray(),'Porosity':vtkFloatArray(),
                         'Permeability':vtkFloatArray(),'Name':vtkCharArray()},'Node':{}}
        vector_properties=['Permeability']
        string_properties=['Name']
        string_length=5
        nele=geo.num_underground_blocks
        array_length={'Block':nele,'Node':0}
        for array_type,array_dict in arrays.items():
            for name,array in array_dict.items():
                array.SetName(name)
                if name in vector_properties:
                    array.SetNumberOfComponents(3)
                    array.SetNumberOfTuples(array_length[array_type])
                elif name in string_properties:
                    array.SetNumberOfComponents(string_length)
                    array.SetNumberOfTuples(array_length[array_type])
                else: 
                    array.SetNumberOfComponents(1)
                    array.SetNumberOfValues(array_length[array_type])
        natm=geo.num_atmosphere_blocks
        rindex=self.rocktype_indices[natm:]
        for i,ri in enumerate(rindex):
            arrays['Block']['Rock type index'].SetValue(i,ri)
            rt=self.rocktypelist[ri]
            arrays['Block']['Porosity'].SetValue(i,rt.porosity)
            k=rt.permeability
            arrays['Block']['Permeability'].SetTuple3(i,k[0],k[1],k[2])
        for i,blk in enumerate(self.blocklist[natm:]):
            arrays['Block']['Name'].SetTupleValue(i,blk.name)
        return arrays

    def write_vtk(self,geo,filename,wells=False):
        """Writes *.vtu file for a vtkUnstructuredGrid object corresponding to the grid in 3D, with the specified filename,
        for visualisation with VTK."""
        from vtk import vtkXMLUnstructuredGridWriter
        if wells: geo.write_well_vtk()
        arrays=geo.vtk_data
        grid_arrays=self.get_vtk_data(geo)
        for array_type,array_dict in arrays.items():
            array_dict.update(grid_arrays[array_type])
        vtu=geo.get_vtk_grid(arrays)
        writer=vtkXMLUnstructuredGridWriter()
        writer.SetFileName(filename)
        writer.SetInput(vtu)
        writer.Write()

    def flux_matrix(self,geo):
        """Returns a sparse matrix which can be used to multiply a vector of connection table values for underground
        blocks, to give approximate average fluxes of those values at the block centres."""
        natm=geo.num_atmosphere_blocks
        nele=geo.num_underground_blocks
        conindex=dict([((c.block[0].name,c.block[1].name),i) for i,c in enumerate(self.connectionlist)])
        from scipy import sparse
        A=sparse.lil_matrix((3*nele,self.num_connections))
        if not self.block_centres_defined: self.calculate_block_centres(geo)
        for iblk,blk in enumerate(self.blocklist[natm:]):
            nbr_name=blk.neighbour_name
            ncons=blk.num_connections
            for conname in blk.connection_name:
                otherindex,sgn=[(0,-1),(1,1)][conname[0]==blk.name]
                blk2name=conname[otherindex]
                icon=conindex[conname]
                centre2=self.block[blk2name].centre
                if centre2<>None:
                    n=centre2-blk.centre
                    n/=np.linalg.norm(n)
                else: n=np.array([0,0,1]) # assumed connection to atmosphere
                for i,ni in enumerate(n):
                    A[3*iblk+i,icon]=-sgn*ni/(ncons*self.connection[conname].area)
        return A

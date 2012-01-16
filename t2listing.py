"""For reading TOUGH2 listing files."""

"""
Copyright 2012 University of Auckland.

This file is part of PyTOUGH.

PyTOUGH is free software: you can redistribute it and/or modify it under the terms of the GNU Lesser General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

PyTOUGH is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License along with PyTOUGH.  If not, see <http://www.gnu.org/licenses/>."""

import string
try:
    import numpy as np
    from numpy import float64
except ImportError: # try importing Numeric on old installs
    import Numeric as np
    from Numeric import Float64 as float64
from mulgrids import fix_blockname, valid_blockname, fortran_float

class listingtable(object):
    """Class for table in listing file, with values addressable by index (0-based) or row name, and column name:
    e.g. table[i] returns the ith row (as a dictionary), table[rowname] returns the row with the specified name,
    and table[colname] returns the column with the specified name."""
    def __init__(self,cols,rows,row_format=None,row_line=None):
        """The row_format parameter is a dictionary with three keys, 'key','index' and 'values'.  These contain the positions,
        in each row of the table, of the start of the keys, index and data fields.  The row_line parameter is a list containing,
        for each row of the table, the number of lines before it in the listing file, from the start of the table.  This is
        needed for TOUGH2_MP listing files, in which the rows are not in index order and can also be duplicated."""
        self.column_name=cols
        self.row_name=rows
        self.row_format=row_format
        self.row_line=row_line
        self._col=dict([(c,i) for i,c in enumerate(cols)])
        self._row=dict([(r,i) for i,r in enumerate(rows)])
        self._data=np.zeros((len(rows),len(cols)),float64)
    def __repr__(self): return repr(self.column_name)+'\n'+repr(self._data)
    def __getitem__(self,key):
        if isinstance(key,int): return dict(zip(self.column_name,self._data[key,:]))
        else:
            if key in self.column_name: return self._data[:,self._col[key]]
            elif key in self.row_name: return dict(zip(self.column_name,self._data[self._row[key],:]))
            else: return None 
    def __setitem__(self,key,value):
        if isinstance(key,int): self._data[key,:]=value
        else: self._data[self._row[key],:]=value
    def get_num_columns(self):
        return len(self.column_name)
    num_columns=property(get_num_columns)
    def get_num_rows(self):
        return len(self.row_name)
    num_rows=property(get_num_rows)
    def key_from_line(self,line):
        key=[fix_blockname(line[pos:pos+5]) for pos in self.row_format['key']]
        if len(key)==1: return key[0]
        else: return tuple(key)

class t2listing(file):
    """Class for TOUGH2 listing file.  The element, connection and generation tables can be accessed
       via the element, connection and generation fields.  (For example, the pressure in block 'aa100' is
       given by element['aa100']['Pressure'].)  It is possible to navigate through time in the listing by 
       using the next() and prev() functions to step through, or using the first() and last() functions to go to 
       the start or end, or to set the index, step (model time step number) or time properties directly."""
    def __init__(self,filename=None):
        super(t2listing,self).__init__(filename)
        self.detect_simulator()
        if self.simulator==None: print 'Could not detect simulator type.'
        else:
            self.setup_short()
            self.setup_pos()
            if self.num_fulltimes>0:
                self._index=0
                self.setup_tables()
                self.set_table_attributes()
                self.first()
            else: print 'No full results found in listing file.'

    def __repr__(self): return self.title

    def get_index(self): return self._index
    def set_index(self,i):
        self.seek(self._fullpos[i])
        self._index=i
        if self._index<0: self._index+=self.num_fulltimes
        self.read_tables()
    index=property(get_index,set_index)

    def get_time(self): return self._time
    def set_time(self,t):
        if t<self.fulltimes[0]: self.index=0
        elif t>self.fulltimes[-1]: self.index=-1
        else:
            i=[j for j,tj in enumerate(self.fulltimes) if tj>=t]
            if len(i)>0: self.index=i[0]
    time=property(get_time,set_time)

    def get_num_times(self): return len(self.times)
    num_times=property(get_num_times)
    def get_num_fulltimes(self): return len(self.fulltimes)
    num_fulltimes=property(get_num_fulltimes)

    def get_step(self): return self._step
    def set_step(self,step):
        if step<self.fullsteps[0]: self.index=0
        elif step>self.fullsteps[-1]: self.index=-1
        else:
            i=[j for j,sj in enumerate(self.fullsteps) if sj>=step]
            if len(i)>0: self.index=i[0]
    step=property(get_step,set_step)

    def get_table_names(self):
        names=self._table.keys()
        names.sort()
        return names
    table_names=property(get_table_names)

    def rewind(self):
        """Rewinds to start of listing (without reading any results)"""
        self.seek(0)
        self._index=-1
        
    def first(self): self.index=0
    def last(self): self.index=-1
    def next(self):
        """Find and read next set of results; returns false if at end of listing"""
        more=self.index<self.num_fulltimes-1
        if more: self.index+=1
        return more
    def prev(self):
        """Find and read previous set of results; returns false if at start of listing"""
        more=self.index>0
        if more: self.index-=1
        return more

    def skiplines(self,number=1):
        """Skips specified number of lines in listing file"""
        for i in xrange(number):  self.readline()

    def skipto(self,keyword='',start=1):
        """Skips to line starting  with keyword.  keyword can be either a string or a list of strings, in which case
        it skips to a line starting with any of the specified strings.
        Returns the keyword found, or false if it can't find any of them.  The start parameter specifies which
        character in the line is to be considered the first to search."""
        line=''
        if isinstance(keyword,list): keywords=keyword
        else: keywords=[keyword]
        while not any([line[start:].startswith(kw) for kw in keywords]):
            line=self.readline()
            if line=='': return False
        return [kw for kw in keywords if line[start:].startswith(kw)][0]

    def skip_to_nonblank(self):
        """Skips to start of next non-blank line."""
        pos=self.tell()
        while not self.readline().strip(): pos=self.tell()
        self.seek(pos)

    def skip_to_blank(self):
        """Skips to start of next blank line."""
        pos=self.tell()
        while self.readline().strip(): pos=self.tell()
        self.seek(pos)
        
    def skip_over_next_blank(self):
        """Skips past next blank line."""
        while self.readline().strip(): pass

    def detect_simulator(self):
        """Detects whether the listing has been produced by AUTOUGH2, TOUGH2/TOUGH2_MP or TOUGH+, and sets some internal methods
        according to the simulator type."""
        self.seek(0)
        simulator={'EEEEE':'AUTOUGH2','ESHORT':'AUTOUGH2','BBBBB':'AUTOUGH2','@@@@@':'TOUGH2','=====':'TOUGH+'}
        line=' '
        while not ('output data after' in line or 'output after' in line or line==''): line=self.readline().lower()
        if line=='': self.simulator=None
        else:
            self.readline()
            line=self.readline()
            linechars=line[1:6]
            if linechars in simulator.keys(): self.simulator=simulator[linechars]
            else: self.simulator=None
            if self.simulator:
                # Set internal methods according to simulator type:
                simname=self.simulator.replace('+','plus')
                internal_fns=['setup_pos','table_type','setup_table','setup_tables','read_header','read_table','next_table',
                              'read_tables','skip_to_table','read_table_line']
                for fname in internal_fns:
                    fname_sim=fname+'_'+simname
                    if simname=='TOUGHplus' and not hasattr(self,fname_sim): fname_sim=fname_sim.replace('plus','2')
                    setattr(self,fname,getattr(self,fname_sim))

    def table_type_AUTOUGH2(self,keyword):
        """Returns AUTOUGH2 table name based on the 5-character keyword read at the top of the table."""
        keytable={'EEEEE':'element','CCCCC':'connection','GGGGG':'generation'}
        if keyword in keytable: return keytable[keyword]
        else: return None

    def table_type_TOUGH2(self,headers):
        """Returns TOUGH2 table name based on a tuple of the first three column headings."""
        if headers[0:2]==('ELEM.','INDEX'):
            if headers[2]=='P': return 'element'
            elif headers[2]=='X1': return 'primary'
        else:
            keytable={('ELEM1','ELEM2','INDEX'):'connection',('ELEMENT','SOURCE','INDEX'):'generation'}
            if headers in keytable: return keytable[headers]
        return None

    def table_type_TOUGHplus(self,headers):
        """Returns TOUGH+ table name based on a tuple of the first three column headings."""
        if headers[0:2]==('ELEM','INDEX'):
            if headers[2]=='X1': return 'primary'
            else: return 'element'
        else:
            keytable={('ELEM1','ELEM2','INDEX'):'connection',('ELEMENT','SOURCE','INDEX'):'generation'}
            if headers in keytable: return keytable[headers]
        return None
        
    def setup_short(self):
        """Sets up short_types and short_indices, for handling short output."""
        self.short_types=[]
        self.short_indices={}
        self.seek(0)
        if self.simulator=='AUTOUGH2':
            done=False
            while not done:
                shortkw=self.skipto(['ESHORT','CSHORT','GSHORT'])
                if (shortkw in self.short_types) or not shortkw: done=True
                else:
                    self.short_types.append(shortkw)
                    self.short_indices[shortkw]={}
                    self.skipto(shortkw)
                    self.skiplines(2)
                    indexpos=self.readline().index('INDEX')
                    self.skiplines()
                    endtable=False
                    lineindex=0
                    while not endtable:
                        line=self.readline()
                        if line[1:].startswith(shortkw): endtable=True
                        else:
                            index=int(line[indexpos:indexpos+5])-1
                            self.short_indices[shortkw][index]=lineindex
                        lineindex+=1
        # (no SHORT output for TOUGH2 or TOUGH+)

    def setup_pos_AUTOUGH2(self):
        """Sets up _pos list for AUTOUGH2 listings, containing file position at the start of each set of results.
        Also sets up the times and steps arrays."""
        self.seek(0)
        # set up pos,times, steps and short arrays:
        self._fullpos,self._pos,self._short=[],[],[]
        fullt,fulls,t,s=[],[],[],[]
        keywords=['EEEEE']
        if len(self.short_types)>0: keywords.append(self.short_types[0])
        endfile=False
        while not endfile:
            kwfound=self.skipto(keywords)
            if kwfound:
                self._pos.append(self.tell())
                self.read_header_AUTOUGH2()
                if kwfound=='EEEEE': # full results
                    self._fullpos.append(self._pos[-1])
                    fullt.append(self.time)
                    fulls.append(self.step)
                    self._short.append(False)
                else: self._short.append(True)
                t.append(self.time)
                s.append(self.step)
                self.readline()
                self.skipto(kwfound) # to end of table
            else: endfile=True
        self.times=np.array(t)
        self.steps=np.array(s)
        self.fulltimes=np.array(fullt)
        self.fullsteps=np.array(fulls)

    def setup_pos_TOUGH2(self):
        """Sets up _pos list for TOUGH2 listings, containing file position at the start of each set of results.
        Also sets up the times and steps arrays."""
        self.seek(0)
        # set up pos,times, steps and short arrays:
        self._fullpos,self._pos=[],[]
        t,s=[],[]
        endfile=False
        while not endfile:
            lf_found=self.skipto('\f',0)
            if lf_found:
                pos=self.tell()
                self.skiplines(2)
                line=self.readline()
                if 'OUTPUT DATA AFTER' in line:
                    self._pos.append(pos)
                    self._fullpos.append(pos)
                    self.seek(pos)
                    self.read_header_TOUGH2()
                    t.append(self.time)
                    s.append(self.step)
                    self.skiplines(2)
                    self.skipto('@@@@@')
            else: endfile=True
        self.times=np.array(t)
        self.steps=np.array(s)
        self.fulltimes=np.array(t)
        self.fullsteps=np.array(s)
        self._short=[False for p in self._pos]

    def setup_pos_TOUGHplus(self):
        """Sets up _pos list for TOUGH+ listings, containing file position at the start of each set of results.
        Also sets up the times and steps arrays."""
        self.seek(0)
        # set up pos,times, steps and short arrays:
        self._fullpos,self._pos=[],[]
        t,s=[],[]
        endfile=False
        while not endfile:
            line=' '
            while not (line.lstrip().startswith('Output data after') or line==''): line=self.readline()
            if line<>'':
                self.skipto('TOTAL TIME',2)
                pos=self.tell()
                self._pos.append(pos)
                self._fullpos.append(pos)
                self.read_header_TOUGHplus()
                t.append(self.time)
                s.append(self.step)
                self.skipto('@@@@@')
            else: endfile=True
        self.times=np.array(t)
        self.steps=np.array(s)
        self.fulltimes=np.array(t)
        self.fullsteps=np.array(s)
        self._short=[False for p in self._pos]

    def set_table_attributes(self):
        """Makes tables in self._table accessible as attributes."""        
        for key,table in self._table.iteritems(): setattr(self,key,table)
        
    def setup_tables_AUTOUGH2(self):
        """Sets up configuration of element, connection and generation tables."""
        self._table={}
        tablename='element'
        self.seek(self._fullpos[0])
        while tablename:
            self.read_header()
            self.setup_table(tablename)
            tablename=self.next_table()

    def setup_tables_TOUGH2(self):
        self._table={}
        tablename='element'
        self.seek(self._fullpos[0])
        self.read_header() # only one header at each time
        while tablename:
            self.setup_table(tablename)
            tablename=self.next_table()

    def setup_tables_TOUGHplus(self):
        self.read_title_TOUGHplus()
        self._table={}
        tablename='element'
        self.seek(self._fullpos[0])
        self.read_header() # only one header at each time
        nelt_tables=0 # can have multiple element tables
        while tablename:
            self.setup_table(tablename)
            tablename=self.next_table()
            if tablename=='element':
                nelt_tables+=1
                tablename+=str(nelt_tables)

    def next_table_AUTOUGH2(self):
        """Goes to start of next table at current time and returns its type- or None if there are no more."""
        keyword=self.readline()[1:6]
        return self.table_type(keyword)

    def next_table_TOUGH2(self):
        if self.skipto('\f',0):
            pos=self.tell()
            if (self.num_fulltimes>1) and (self.index<self.num_fulltimes-1):
                if pos>=self._fullpos[self.index+1]: return None
            line=self.readline().strip()
            if (line==self.title):
                self.skiplines(3)
                headpos=self.tell()
                headers=tuple(self.readline().strip().split()[0:3])
                self.seek(headpos)
                return self.table_type(headers)
            else: return None
        else: return None

    def next_table_TOUGHplus(self):
        if self.skipto('_____',0):
            self.readline()
            pos=self.tell()
            if (self.num_fulltimes>1) and (self.index<self.num_fulltimes-1):
                if pos>=self._fullpos[self.index+1]: return None
            headpos=self.tell()
            headers=tuple(self.readline().strip().split()[0:3])
            self.seek(headpos)
            return self.table_type(headers)
        else: return None

    def skip_to_table_AUTOUGH2(self,tablename,last_tablename,nelt_tables):
        """Skips forwards to headers of table with specified name at the current time."""
        if self._short[self._index]: keyword=tablename[0].upper()+'SHORT'
        else: keyword=tablename[0].upper()*5
        self.skipto(keyword)
        if tablename<>'element': self.skipto(keyword)
        self.skip_to_blank()
        self.skip_to_nonblank()

    def skip_to_table_TOUGH2(self,tablename,last_tablename,nelt_tables):
        if last_tablename==None:
            for i in xrange(2): self.skipto('@@@@@')
            self.skip_to_nonblank()
            tname='element'
        else: tname=last_tablename
        while tname<>tablename:
            self.skipto('@@@@@')
            tname=self.next_table_TOUGH2()

    def skip_to_table_TOUGHplus(self,tablename,last_tablename,nelt_tables):
        if last_tablename==None:
            self.skipto('=====',0)
            self.skip_to_nonblank()
            tname='element'
            nelt_tables=0
        else: tname=last_tablename
        while tname<>tablename:
            if tname=='primary': keyword='_____'
            else: keyword='@@@@@'
            self.skipto(keyword,0)
            tname=self.next_table_TOUGHplus()
            if tname=='element':
                nelt_tables+=1
                tname+=str(nelt_tables)

    def keysearch_startpos(self,headline,key_headers):
        """Returns start point for searching for keys, based on key header positions."""
        keylength=5
        half_keylength=int(keylength/2.)
        headmid=[]
        for header in key_headers:
            header_startpos=headline.find(header)
            header_endpos=header_startpos+len(header)-1
            headmid.append(int((header_startpos+header_endpos)/2.))
        startpos=[max(mid-half_keylength-1,0) for mid in headmid]
        return startpos

    def key_positions(self,line,nkeys,startpos):
        """Returns detected positions of keys in a table line."""
        def valid_spaced_blockname(name): return (name[0]==name[6]==' ') and valid_blockname(name[1:6])
        keypos=[]
        for k in xrange(nkeys):
            pos=startpos[k]
            while not valid_spaced_blockname(line[pos:pos+7]): pos+=1
            while valid_spaced_blockname(line[pos:pos+7]): pos+=1
            keypos.append(pos)
        return keypos

    def setup_table_AUTOUGH2(self,tablename):
        """Sets up table from AUTOUGH2 listing file."""
        keyword=tablename[0].upper()*5
        self.skiplines(3)
        # Read column names (joining lowercase words to previous names):
        headline=self.readline()
        strs=headline.strip().split()
        nkeys=strs.index('INDEX')
        rows,cols=[],[]
        for s in strs[nkeys+1:]:
            if s[0]==s[0].upper(): cols.append(s)
            else: cols[-1]+=' '+s
        self.readline()
        line=self.readline()
        # Double-check number of columns:
        start=headline.index('INDEX')+5
        nvalues=len([s for s in line[start:].strip().split()])
        if (len(cols)==nvalues):
            startpos=self.keysearch_startpos(headline,strs[0:nkeys])
            keypos=self.key_positions(line,nkeys,startpos)
            # determine row names:
            while line[1:6]<>keyword:
                keyval=[fix_blockname(line[kp:kp+5]) for kp in keypos]
                if len(keyval)>1: keyval=tuple(keyval)
                else: keyval=keyval[0]
                rows.append(keyval)
                line=self.readline()
            row_format={'values':[start]}
            self._table[tablename]=listingtable(cols,rows,row_format)
            self.readline()
        else:
            print 'Error parsing '+tablename+' table columns: table not created.'

    def setup_table_TOUGH2(self,tablename):
        """Sets up table from TOUGH2 (or TOUGH+) listing file."""
        # Read column names (joining flow items to previous names):
        if self.simulator=='TOUGH2': flow_headers=['RATE']
        else: flow_headers=['Flow','Veloc']
        headline=self.readline()
        strs=headline.strip().split()
        nkeys=strs.index('INDEX')
        self.skip_over_next_blank()
        rows,cols=[],[]
        for s in strs[nkeys+1:]:
            if s in flow_headers: cols[-1]+=' '+s
            else: cols.append(s)
        line=self.readline()
        startpos=self.keysearch_startpos(headline,strs[0:nkeys])
        keypos=self.key_positions(line,nkeys,startpos)
        # work out position of index:
        index_pos=[keypos[-1]+5]
        pos=line.find('.')
        c=line[pos-2]
        if c in [' ','-']: index_pos.append(pos-2)
        elif c.isdigit(): index_pos.append(pos-1)
        # determine row names:
        longest_line=line
        rowdict={}
        count,index=0,-1
        while line.strip():
            keyval=[fix_blockname(line[kp:kp+5]) for kp in keypos]
            if len(keyval)>1: keyval=tuple(keyval)
            else: keyval=keyval[0]
            indexstr=line[index_pos[0]:index_pos[1]]
            try: index=int(indexstr)-1
            except ValueError: index+=1    # to handle overflow (****) in index field: assume indices continue
            rowdict[index]=(count,keyval)  # use a dictionary to deal with duplicate row indices (TOUGH2_MP)
            line=self.readline(); count+=1
            if line.startswith('\f'): # extra headers in the middle of TOUGH2 listings
                while self.readline().strip(): count+=1
                line=self.readline(); count+=2
            if len(line.strip())>len(longest_line): longest_line=line
        # sort rows (needed for TOUGH2_MP):
        indices=rowdict.keys(); indices.sort()
        row_line=[rowdict[index][0] for index in indices]
        rows=[rowdict[index][1] for index in indices]
        # determine row parsing format:
        line=longest_line
        start=keypos[-1]+5
        numpos=[]
        p,done=start,False
        while not done:
            pos=line.find('.',p)
            if pos>2:
                c=line[pos-2]
                if c in [' ','-']: numpos.append(pos-2)
                elif c.isdigit(): numpos.append(pos-1)
                p=pos+1
            else: done=True
        numpos.append(len(line))
        row_format={'key':keypos,'index':keypos[-1]+5,'values':numpos}
        self._table[tablename]=listingtable(cols,rows,row_format,row_line)

    def read_header_AUTOUGH2(self):
        """Reads header info (title and time data) for one set of AUTOUGH2 listing results."""
        self.title=self.readline().strip()
        line=self.readline()
        istart,iend=string.find(line,'AFTER')+5,string.find(line,'TIME STEPS')
        self._step=int(line[istart:iend])
        istart=iend+10
        iend=string.find(line,'SECONDS')
        self._time=fortran_float(line[istart:iend])
        self.readline()

    def read_header_TOUGH2(self):
        """Reads header info (title and time data) for one set of TOUGH2 listing results."""
        self.title=self.readline().strip()
        self.skiplines(6)
        vals=self.readline().split()
        self._time=fortran_float(vals[0])
        self._step=int(vals[1])
        self.skipto('@@@@@')
        self.skip_to_nonblank()

    def read_header_TOUGHplus(self):
        """Reads header info (time data) for one set of TOUGH+ listing results."""
        line=self.readline()
        strs=line.split()
        self._time,self._step=float(strs[0]),int(strs[1])
        self.skipto('=====')
        self.skip_to_nonblank()

    def read_title_TOUGHplus(self):
        """Reads simulation title for TOUGH+ listings, at top of file."""
        self.seek(0)
        line=' '
        while not (line.lstrip().startswith('PROBLEM TITLE:') or line==''): line=self.readline()
        if line=='': self.title=''
        else:
            colonpos=line.find(':')
            if colonpos>=0: self.title=line[colonpos+1:].strip()
            else: self.title=''

    def read_tables_AUTOUGH2(self):
        tablename='element'
        while tablename:
            self.read_header()
            self.read_table(tablename)
            tablename=self.next_table()

    def read_tables_TOUGH2(self):
        tablename='element'
        self.read_header() # only one header at each time
        while tablename:
            self.read_table(tablename)
            tablename=self.next_table()

    def read_tables_TOUGHplus(self):
        tablename='element'
        self.read_header() # only one header at each time
        nelt_tables=0
        while tablename:
            self.read_table(tablename)
            tablename=self.next_table()
            if tablename=='element':
                nelt_tables+=1
                tablename+=str(nelt_tables)

    def read_table_AUTOUGH2(self,tablename):
        fmt=self._table[tablename].row_format
        keyword=tablename[0].upper()*5
        self.skip_to_blank()
        self.readline()
        self.skip_to_blank()
        self.skip_to_nonblank()
        line=self.readline()
        row=0
        while line[1:6]<>keyword:
            self._table[tablename][row]=self.read_table_line_AUTOUGH2(line,fmt=fmt)
            row+=1
            line=self.readline()
        self.readline()

    def read_table_line_AUTOUGH2(self,line,num_columns=None,fmt=None):
        start=fmt['values'][0]
        vals=[fortran_float(s) for s in line[start:].strip().split()]        
        return vals

    def read_table_line_TOUGH2(self,line,num_columns,fmt):
        """Reads values from a line in a TOUGH2 listing, given the number of columns, and format."""
        vals=[fortran_float(line[fmt['values'][i]:fmt['values'][i+1]]) for i in xrange(len(fmt['values'])-1)]
        num_missing=num_columns-len(vals)
        for i in xrange(num_missing): vals.append(0.0)
        return vals
        
    def read_table_TOUGH2(self,tablename):
        ncols=self._table[tablename].num_columns
        fmt=self._table[tablename].row_format
        self.skip_to_blank()
        self.skip_to_nonblank()
        line=self.readline()
        while line.strip():
            key=self._table[tablename].key_from_line(line)
            self._table[tablename][key]=self.read_table_line_TOUGH2(line,ncols,fmt)
            line=self.readline()
            if line.startswith('\f'): # extra headers in the middle of TOUGH2 listings
                self.skip_over_next_blank()
                line=self.readline()

    def history(self,selection):
        """Returns time histories for specified selection of table type, names (or indices) and column names.
           Table type is specified as 'e','c','g' or 'p' (upper or lower case) for element table,
           connection table, generation table or primary table respectively.  For TOUGH+ results, additional
           element tables may be specified as 'e1' or 'e2'."""

        # This can obviously be done much more simply using next(), and accessing self._table,
        # but that is too slow for large listing files.  This method reads only the required data lines
        # in each table.

        def tablename_from_specification(tabletype): # expand table specification to table name:
            from string import digits
            namemap={'e':'element','c':'connection','g':'generation','p':'primary'}
            type0=tabletype[0].lower()
            if type0 in namemap:
                name=namemap[type0]
                if tabletype[-1] in digits: name+=tabletype[-1] # additional TOUGH+ element tables
                return name
            else: return None

        def ordered_selection(selection,tables,short_types,short_indices):
            """Given the initial history selection, returns a list of tuples of table name and table selection.  The tables
            are in the same order as they appear in the listing file.  The table selection is a list of tuples of 
            (row index, column name, selection index, short row index) for each table, ordered by row index.  This ordering
            means all data can be read sequentially to make it more efficient.""" 
            converted_selection=[]
            for (tspec,key,h) in selection:  # convert keys to indices as necessary, and expand table names
                tablename=tablename_from_specification(tspec)
                if isinstance(key,int): index=key
                else: index=tables[tablename]._row[key]
                if tables[tablename].row_line: index=tables[tablename].row_line[index] # find line index if needed
                ishort=None
                short_keyword=tspec[0].upper()+'SHORT'
                if short_keyword in short_types:
                    if index in short_indices[short_keyword]: ishort=short_indices[short_keyword][index]
                converted_selection.append((tablename,index,ishort,h))
            tables=list(set([sel[0] for sel in converted_selection]))
            # need to retain table order as in the file:
            tables=[tname for tname in ['element','element1','connection','primary','element2','generation'] if tname in tables]
            tagselection=[(tname,i,ishort,h,sel_index) for sel_index,(tname,i,ishort,h) in enumerate(converted_selection)]
            tableselection=[]
            shortindex={}
            for table in tables:
                tselect=[(i,ishort,h,sel_index) for (tname,i,ishort,h,sel_index) in tagselection if tname==table]
                tselect.sort()
                tableselection.append((table,tselect))
            return tableselection

        old_index=self.index
        if isinstance(selection,tuple): selection=[selection] # if input just one tuple rather than a list of them
        tableselection=ordered_selection(selection,self._table,self.short_types,self.short_indices)
        hist=[[] for s in selection]
        self.rewind()

        for ipos,pos in enumerate(self._pos):
            self.seek(pos)
            self._index=ipos
            short=self._short[ipos]
            last_tname=None
            nelt_tables=-1
            for (tname,tselect) in tableselection:
                if short: tablename=tname[0].upper()+'SHORT'
                else: tablename=tname
                if not (short and not (tablename in self.short_types)):
                    self.skip_to_table(tablename,last_tname,nelt_tables)
                    if tablename.startswith('element'): nelt_tables+=1
                    self.skip_to_blank()
                    self.skip_to_nonblank()
                    ncols=self._table[tablename].num_columns
                    fmt=self._table[tablename].row_format
                    index=0
                    line=self.readline()
                    for (itemindex,ishort,colname,sel_index) in tselect:
                        lineindex=[itemindex,ishort][short]
                        if lineindex<>None:
                            for k in xrange(lineindex-index): line=self.readline()
                            index=lineindex
                            vals=self.read_table_line(line,ncols,fmt)
                            valindex=self._table[tablename]._col[colname]
                            hist[sel_index].append(vals[valindex])
                last_tname=tname

        self._index=old_index
        result=[([self.times,self.fulltimes][len(h)==self.num_fulltimes],np.array(h)) for sel_index,h in enumerate(hist)]
        if len(result)==1: result=result[0]
        return result

    def get_reductions(self):
        """Returns a list of time step indices at which the time step is reduced, and the blocks at which the maximum
        residual occurred prior to the reduction."""
        self.rewind()
        line,lastline='',''
        keyword="+++++++++ REDUCE TIME STEP"
        keyend=len(keyword)+1
        rl=[]
        finished=False
        while not finished:
            while line[1:keyend]<>keyword:
                lastline=line
                line=self.readline()
                if not line:
                    finished=True
                    break
            if not finished:
                lowerlastline=lastline.lower()
                eltindex=lowerlastline.find('element')
                if eltindex>0:
                    if lowerlastline.find('eos cannot find parameters')>=0: space=9
                    else: space=8
                    blockname=fix_blockname(lastline[eltindex+space:eltindex+space+5])
                    brackindex,comindex=line.find('('),line.find(',')
                    timestep=int(line[brackindex+1:comindex])
                    rl.append((timestep,blockname))
                lastline=line
                line=self.readline()
                if not line: finished=True
        return rl
    reductions=property(get_reductions)

    def get_difference(self,indexa=None,indexb=None):
        """Returns dictionary of maximum differences, and locations of difference, of all element table properties between two sets of results.
        If both indexa and indexb are provided, the result is the difference between these two result indices.  If only one index is given, the
        result is the difference between the given index and the one before that.  If neither are given, the result is the difference between
        the last and penultimate sets of results."""
        from copy import deepcopy
        tablename='element'
        if indexa == None: self.last()
        else: self.set_index(indexa)
        results2=deepcopy(self._table[tablename])
        if indexb == None: self.prev()
        else: self.set_index(indexb)
        results1=self._table[tablename]
        cvg={}
        for name in results1.column_name:
            iblk=np.argmax(abs(results2[name]-results1[name]))
            blkname=results1.row_name[iblk]
            diff=results2[name][iblk]-results1[name][iblk]
            cvg[name]=(diff,blkname)
        return cvg
    convergence=property(get_difference)

    def get_vtk_data(self,geo,grid=None,flows=False,flux_matrix=None,geo_matches=True):
        """Returns dictionary of VTK data arrays from listing file at current time.  If flows is True, average flux vectors
        are also calculated from connection data at the block centres."""
        from vtk import vtkFloatArray
        natm=geo.num_atmosphere_blocks
        nele=geo.num_underground_blocks
        arrays={'Block':{},'Node':{}}
        elt_tablenames=[key for key in self._table.keys() if key.startswith('element')]
        for tablename in elt_tablenames:
            for name in self._table[tablename].column_name: arrays['Block'][name]=vtkFloatArray()
        flownames=[]
        def is_flowname(name):
            name=name.lower()
            return name.startswith('flo') or name.endswith('flo') or name.endswith('flow') or name.endswith('veloc')
        if flows:
            if flux_matrix==None: flux_matrix=grid.flux_matrix(geo)
            flownames=[name for name in self.connection.column_name if is_flowname(name)]
            for name in flownames: arrays['Block'][name]=vtkFloatArray()
        array_length={'Block':nele,'Node':0}
        array_data={'Block':{},'Node':{}}
        for array_type,array_dict in arrays.items():
            for name,array in array_dict.items():
                if name in flownames:
                    array.SetName(name+'/area')
                    array.SetNumberOfComponents(3)
                    array.SetNumberOfTuples(array_length[array_type])
                    array_data[array_type][name]=flux_matrix*self.connection[name]
                else:
                    array.SetName(name)
                    array.SetNumberOfComponents(1)
                    array.SetNumberOfValues(array_length[array_type])
                    for tablename in elt_tablenames:
                        if geo_matches: array_data[array_type][name]=self._table[tablename][name][natm:] # faster
                        else:  # more flexible
                            array_data[array_type][name]=np.array([self._table[tablename][blk][name] for blk in geo.block_name_list[natm:]])
        for array_type,data_dict in array_data.items():
            for name,data in data_dict.items():
                if name in flownames:
                    for iblk in xrange(nele):
                        arrays[array_type][name].SetTuple3(iblk,data[3*iblk],data[3*iblk+1],data[3*iblk+2])
                else:    
                    for iblk in xrange(nele):
                        arrays[array_type][name].SetValue(iblk,data[iblk])
        return arrays

    def write_vtk(self,geo,filename,grid=None,indices=None,flows=False,wells=False,start_time=0.0,time_unit='s'):
        """Writes VTK files for a vtkUnstructuredGrid object corresponding to the grid in 3D with the listing data,
        with the specified filename, for visualisation with VTK.  A t2grid can optionally be specified, to include rock type
        data as well.  A list of the required time indices can optionally be specified.  If a grid is specified, flows is True,
        and connection data are present in the listing file, approximate average flux vectors are also calculated at the 
        block centres from the connection data."""
        from vtk import vtkXMLUnstructuredGridWriter
        from os.path import splitext
        base,ext=splitext(filename)
        if wells: geo.write_well_vtk()
        geo_matches=geo.block_name_list==self.element.row_name
        doflows=flows and (self.connection<>None) and (grid<>None) and geo_matches
        arrays=geo.vtk_data
        if grid<>None:
            grid_arrays=grid.get_vtk_data(geo)
            for array_type,array_dict in arrays.items():
                array_dict.update(grid_arrays[array_type])
        if doflows: flux_matrix=grid.flux_matrix(geo)
        else: flux_matrix=None
        import xml.dom.minidom
        pvd=xml.dom.minidom.Document()
        vtkfile=pvd.createElement('VTKFile')
        vtkfile.setAttribute('type','Collection')
        pvd.appendChild(vtkfile)
        collection=pvd.createElement('Collection')
        initial_index=self.index
        if indices==None: indices=range(self.num_fulltimes)
        timescales={'s':1.0,'h':3600.,'d':3600.*24,'y':3600.*24*365.25}
        if time_unit in timescales: timescale=timescales[time_unit]
        else: timescale=1.0
        writer=vtkXMLUnstructuredGridWriter()
        for i in indices:
            self.index=i
            t=start_time+self.time/timescale
            filename_time=base+'_'+str(i)+'.vtu'
            results_arrays=self.get_vtk_data(geo,grid,flows=doflows,flux_matrix=flux_matrix,geo_matches=geo_matches)
            for array_type,array_dict in arrays.items():
                array_dict.update(results_arrays[array_type])
            vtu=geo.get_vtk_grid(arrays)
            writer.SetFileName(filename_time)
            writer.SetInput(vtu)
            writer.Write()
            dataset=pvd.createElement('DataSet')
            dataset.setAttribute('timestep',str(t))
            dataset.setAttribute('file',filename_time)
            collection.appendChild(dataset)
        vtkfile.appendChild(collection)
        pvdfile=open(base+'.pvd','w')
        pvdfile.write(pvd.toprettyxml())
        pvdfile.close()
        self.index=initial_index

    def add_side_recharge(self,geo,dat):
        """Adds side recharge generators to a TOUGH2 data object for a production run,
        calculated according to the final results in the listing.  These generators represent side
        inflows due to pressure changes in the blocks on the model's horizontal boundaries.
        Recharge generators are given the names of their blocks- any existing generators with the same
        names will be overwritten."""
        from IAPWS97 import cowat,sat,visc
        from geometry import line_projection
        from t2data import t2generator
        initial_index=self.index
        keyword={'AUTOUGH2':{'P':'Pressure','T':'Temperature'},'TOUGH2':{'P':'P','T':'T'},
                 'TOUGH+':{'P':'Pressure','T':'Temperature'}}
        self.last()
        bdy_nodes=geo.boundary_nodes
        for blk in dat.grid.blocklist[geo.num_atmosphere_blocks:]:
            colname=geo.column_name(blk.name)
            if colname in geo.column:
                col=geo.column[colname]
                if col.num_neighbours<col.num_nodes:
                    k=0.5*np.sum(blk.rocktype.permeability[0:2])
                    p0=self.element[blk.name][keyword[self.simulator]['P']]
                    t0=self.element[blk.name][keyword[self.simulator]['T']]
                    rho,u=cowat(t0,p0)
                    h=u+p0/rho
                    Ps=sat(t0)
                    xnu=visc(rho,t0)/rho
                    coef=0.
                    for iface in xrange(col.num_nodes):
                        facenode=[col.node[i] for i in [iface,(iface+1)%col.num_nodes]]
                        if all([node in bdy_nodes for node in facenode]):
                            side_length=np.linalg.norm(facenode[1].pos-facenode[0].pos)
                            height=blk.volume/col.area
                            area=side_length*height
                            facepos=line_projection(col.centre,[node.pos for node in facenode])
                            dist=np.linalg.norm(col.centre-facepos)
                            coef+=0.5*area*k/(xnu*dist) # recharge coefficient
                    gen_name=blk.name
                    dat.add_generator(t2generator(gen_name,blk.name,type='RECH',gx=coef,ex=h,hg=p0))
        self.index=initial_index

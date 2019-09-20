"""
Jigsaw module

"""
# Copyright 2018 European Union
# This file is part of pyPoseidon.
# Licensed under the EUPL, Version 1.2 or – as soon they will be approved by the European Commission - subsequent versions of the EUPL (the "Licence").
# Unless required by applicable law or agreed to in writing, software distributed under the Licence is distributed on an "AS IS" basis, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
# See the Licence for the specific language governing permissions and limitations under the Licence. 

import pandas as pd
import numpy as np
from matplotlib import tri
from shapely import geometry, ops
import geopandas as gp
import xarray as xr
import os
import shapely
import subprocess
import sys
import pyproj
from shapely.ops import transform
from functools import partial
import cartopy.feature as cf

import pyPoseidon.dem as pdem
from .limgrad import *
import logging        
        
logger = logging.getLogger('pyPoseidon')


def jig(path='.',tag='jigsaw'):    
    
    fjig = path + '/' + tag+'.jig'
    
    with open(fjig,'w') as f:
        f.write('GEOM_FILE ={}\n'.format(tag+'-geo.msh'))
        f.write('MESH_FILE ={}\n'.format(tag+'.msh'))
        f.write('HFUN_FILE ={}\n'.format(tag+'-hfun.msh'))
        f.write('HFUN_SCAL = ABSOLUTE\n')
        f.write('HFUN_HMAX = Inf\n')
        f.write('HFUN_HMIN = 0.0\n')
        f.write('MESH_DIMS = 2\n')
        f.write('MESH_TOP1 = TRUE\n')
        f.write('MESH_EPS1 = 1.0\n')
        f.write('MESH_RAD2 = 1\n')
        f.write('GEOM_FEAT = TRUE\n')
        f.write('VERBOSITY = 2')


def geo(df, path='.', tag='jigsaw'):
    
    fgeo = path + tag+'-geo.msh'
    # write header
    with open(fgeo,'w') as f:
        f.write('#{}; created by pyPoseidon\n'.format(tag +'-geo.msh'))
        f.write('MSHID=2;EUCLIDEAN-MESH\n')
        f.write('NDIMS=2\n')
        f.write('POINT={}\n'.format(df.shape[0]))
    
    #write lines
    with open(fgeo, 'a') as f:
        for line in df.index.levels[0]:
            df.loc[line].to_csv(f, index=False, header=0, columns=['lon','lat','z'],sep=';')


    edges = pd.DataFrame([]) # initiate

    # create edges
    for line in df.index.levels[0]:
        i0 = edges.shape[0]
        ie = df.loc[line].shape[0] + edges.shape[0]
        dline = df.loc[line].copy()
        dline.index = range(i0,ie)
        dline.loc[:,'ie'] = dline.index.values + 1
        dline.loc[dline.index[-1],'ie']=i0
        dout = dline.reset_index().loc[:,['index','ie','tag']]

        dout['tag1'] = dline.loc[dline.ie.values,'tag'].values.astype(int)
        dout['que'] = np.where(((dout['tag'] != dout['tag1']) & (dout['tag'] > 0)) , dout['tag1'], dout['tag'])    
        dout = dout.reset_index().loc[:,['index','ie','que']]
        edges = edges.append(dout)        
        
    # write header
    with open(fgeo,'a') as f:
        f.write('EDGE2={}\n'.format(edges.shape[0]))
    
    with open(fgeo, 'a') as f:
        edges.to_csv(f, index=False, header=0, sep=';')
        

def hfun(dem, path='.', tag='jigsaw', resolution_min=.05, resolution_max=.5, dhdx=.15, imax=100, **kwargs):
    
    X, Y = np.meshgrid(dem.Dataset.longitude.values,dem.Dataset.latitude.values)
    V = dem.Dataset.values
    
    #scale
    hmin = resolution_min                       # min. H(X) [deg.]
    hmax = resolution_max                       # max. H(X)

    V[V>0] = 0 #normalize to only negative values

    hfun =  np.sqrt(-V)/.5 # scale with sqrt(H)
    hfun[hfun < hmin] = hmin
    hfun[hfun > hmax] = hmax
    
    hfun = hfun.flatten() # make it 1-d
    
    hfun = np.array([[hf] for hf in list(hfun)]) #convert it to the appropriate format for LIMHFN2 below
    
    #triangulate
    points = np.column_stack([X.flatten(),Y.flatten()])
    # Use Matplotlib for triangulation
    triang = tri.Triangulation(points[:,0], points[:,1])
#    tri3 = triang.triangles
    edges = triang.edges
    #edge lengths
    elen = [shapely.geometry.LineString(points[edge]).length for edge in edges]
    
    [fun,flag] = limgrad2(edges,elen,hfun,dhdx,imax)

    ##OUTPUT
    
    fhfun = path + tag+'-hfun.msh'
    # write header
    with open(fhfun,'w') as f:
        f.write('#{}; created by pyPoseidon\n'.format(tag+'-hfun.msh'))
        f.write('MSHID=3;EUCLIDEAN-GRID\n')
        f.write('NDIMS=2\n')
        f.write('COORD=1;{}\n'.format(dem.Dataset.longitude.size))
        
    with open(fhfun, 'a') as f:
        dem.Dataset.longitude.to_dataframe().to_csv(f, index=False, header=0)
        
    with open(fhfun, 'a') as f:
        f.write('COORD=2;{}\n'.format(dem.Dataset.latitude.size))
        
    with open(fhfun, 'a') as f:
        dem.Dataset.latitude.to_dataframe().to_csv(f, index=False, header=0)
    
    with open(fhfun, 'a') as f:
        f.write('VALUE={};1\n'.format(dem.Dataset.longitude.size * dem.Dataset.latitude.size))
    
    #converted TRANSPOSED, IS THERE A WAY TO FIX IT?
    cfun = fun.flatten().reshape(X.shape).T
    with open(fhfun, 'a') as f:
        for i in range(fun.size):
            f.write('{}\n'.format(cfun.flatten()[i]))
            

def read_msh(fmsh):
    
    grid = pd.read_csv(fmsh, header=0, names=['data'], index_col=None, low_memory=False)
    npoints = int(grid.loc[2].str.split('=')[0][1])

    nodes = pd.DataFrame(grid.loc[3: 3 + npoints - 1,'data'].str.split(';').values.tolist(),columns=['lon','lat','z'])

    ie = grid[grid.data.str.contains('EDGE')].index.values[0]
    nedges = int(grid.loc[ie].str.split('=')[0][1])
    edges = pd.DataFrame(grid.loc[ie + 1 :ie  + nedges ,'data'].str.split(';').values.tolist(),columns=['e1','e2','e3'])

    i3 = grid[grid.data.str.contains('TRIA')].index.values[0]
    ntria = int(grid.loc[i3].str.split('=')[0][1])
    tria = pd.DataFrame(grid.loc[i3 + 1 : i3 + ntria + 1 ,'data'].str.split(';').values.tolist(),columns=['a','b','c','d'])

    return [nodes,edges,tria]
    
    
            

def jigsaw(**kwargs):
     
    cr = kwargs.get('coast_resolution', 'l')
    
    logger.info('Creating grid with JIGSAW\n')
    
    # world polygons - user input
    coast = cf.NaturalEarthFeature(
        category='physical',
        name='land',
        scale='{}m'.format({'l':110, 'i':50, 'h':10}[cr]))
    
           
    natural_world = gp.GeoDataFrame(geometry = [x for x in coast.geometries()])    
    
    world = kwargs.get('coastlines',natural_world)
    
    world = world.explode()
        
    minlon = kwargs.get('minlon', None)
    maxlon = kwargs.get('maxlon', None)
    minlat = kwargs.get('minlat', None)
    maxlat = kwargs.get('maxlat', None)
        
    block = world.cx[minlon:maxlon,minlat:maxlat] #mask based on lat/lon window
    
    #create a polygon of the lat/lon window
    grp=geometry.Polygon([(minlon,minlat),(minlon,maxlat),(maxlon,maxlat),(maxlon,minlat)])

    #create a LineString of the grid
    grl=geometry.LineString([(minlon,minlat),(minlon,maxlat),(maxlon,maxlat),(maxlon,minlat),(minlon,minlat)])

    
    g = block.unary_union.symmetric_difference(grp) # get the dif from the world

    try: # make geoDataFrame 
        t = gp.GeoDataFrame({'geometry':g})
    except:
        t = gp.GeoDataFrame({'geometry':[g]})    
    t['length']=t['geometry'][:].length #get length
    t = t.sort_values(by='length', ascending=0) #sort
    t = t.reset_index(drop=True)
    
    t['in'] = gp.GeoDataFrame(geometry=[grp] * t.shape[0]).contains(t) # find the largest of boundaries
    idx = np.where(t['in']==True)[0][0] # first(largest) boundary within lat/lon
    b = t.iloc[idx].geometry #get the largest 
    
    # SETUP JIGSAW
    dic={}
    for l in range(len(b.boundary)):
        lon=[]
        lat=[]
        for x,y in b.boundary[l].coords[:]:
            lon.append(x)
            lat.append(y)
        dic.update({'line{}'.format(l):{'lon':lon,'lat':lat}})

    dict_of_df = {k: pd.DataFrame(v) for k,v in dic.items()}
    df = pd.concat(dict_of_df, axis=0)
    df['z']=0
    df = df.drop_duplicates() # drop the repeat value on closed boundaries
    
    
    #open (water) boundaries
    water = b.boundary[0] - (b.boundary[0] - grl) 
    try:
        cwater = ops.linemerge(water)
    except:
        cwater= water

    mindx = 0
    #get all lines in a pandas DataFrame
    if cwater.type == 'LineString':
            lon=[]
            lat=[]
            for x,y in cwater.coords[:]:
                lon.append(x)
                lat.append(y)
            dic= {'line{}'.format(mindx):{'lon':lon,'lat':lat, 'z':0 ,'tag':mindx + 1}}
            mindx += 1
        
    elif cwater.type == 'MultiLineString' :
        dic={}
        for l in range(len(cwater)):
            lon=[]
            lat=[]
            for x,y in cwater[l].coords[:]:
                lon.append(x)
                lat.append(y)
            dic.update({'line{}'.format(mindx):{'lon':lon,'lat':lat, 'z':0 ,'tag':mindx + 1}})
            mindx += 1
    
    dict_of_df = {k: pd.DataFrame(v) for k,v in dic.items()}
    df_water = pd.concat(dict_of_df, axis=0)

       
    # land boundaries!!
    land = b.boundary[0] - grl 

    try:
        cland = ops.linemerge(land)
    except:
        cland = land
        
    mindx = 0 
    
    #get all lines in a pandas DataFrame
    if cland.type == 'LineString':
            lon=[]
            lat=[]
            for x,y in cland.coords[:]:
                lon.append(x)
                lat.append(y)
            dic= {'line{}'.format(mindx):{'lon':lon,'lat':lat, 'z':0 ,'tag':mindx - 1}}
            mindx -= 1
        
    elif cland.type == 'MultiLineString' :
        dic={}
        for l in range(len(cland)):
            lon=[]
            lat=[]
            for x,y in cland[l].coords[:]:
                lon.append(x)
                lat.append(y)
            dic.update({'line{}'.format(mindx):{'lon':lon,'lat':lat, 'z':0 ,'tag':mindx - 1}})
            mindx -= 1
            
    dict_of_df = {k: pd.DataFrame(v) for k,v in dic.items()}

    df_land = pd.concat(dict_of_df, axis=0)
    
    ddf = pd.concat([df_water,df_land])
    
    #Sort outer boundary
    
    out_b = []
    for line in ddf.index.levels[0]:
        out_b.append(shapely.geometry.LineString(ddf.loc[line,['lon','lat']].values))

    merged = shapely.ops.linemerge(out_b)
    merged = pd.DataFrame(merged.coords[:], columns=['lon','lat'])
    merged = merged.drop_duplicates()
    match = ddf.drop_duplicates(['lon','lat']).droplevel(0)
    match = match.reset_index(drop=True)

    df1 = merged.sort_values(['lon', 'lat'])
    df2 = match.sort_values(['lon', 'lat'])
    df2.index = df1.index
    final = df2.sort_index()
    final = pd.concat([final],keys=['line0'])
    
    
    bmindx = mindx
    
    #merge with islands    
    ndf = df.drop('line0')
    for line in ndf.index.levels[0][1:]:
        ndf.loc[line,'tag'] = mindx - 1
        mindx -= 1
    ndf['tag'] = ndf.tag.astype(int)
    df = pd.concat([final,ndf])
          
    tag = kwargs.get('tag', 'jigsaw')
    rpath = kwargs.get('rpath', '.')
    
    logger.info('Creating JIGSAW files\n')
    
    if not os.path.exists(rpath):
            os.makedirs(rpath)
    
    path = rpath+'/jigsaw/'
    if not os.path.exists(path):
        os.makedirs(path)
    
    
    jig(path=path,tag=tag)
    geo(df,path=path,tag=tag)
    
    dem_file = kwargs.get('dem_file', None)
    
    dem_dic={'minlon':minlon, # lat/lon window
         'maxlon':maxlon,
         'minlat':minlat,
         'maxlat':maxlat}
    if dem_file:
        dem_dic.update({'dem_file':dem_file})
         
    dem = pdem.dem(**dem_dic)
      
    hfun(dem, path=path, **kwargs)
    
    calc_dir = rpath+'/jigsaw/'
    
    #---------------------------------     
    logger.info('executing jigsaw\n')
    #--------------------------------- 
    
    #execute jigsaw
    ex=subprocess.Popen(args=[os.environ['CONDA_PREFIX']+'/envs/pyPoseidon/bin/jigsaw {}'.format(tag+'.jig')], cwd=calc_dir, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=1)
        
    with open(calc_dir+'err.log', 'w') as f: 
      for line in iter(ex.stderr.readline,b''): 
        f.write(line.decode(sys.stdout.encoding))   
#        logger.info(line.decode(sys.stdout.encoding))
    ex.stderr.close()            

    with open(calc_dir+'run.log', 'w') as f: 
      for line in iter(ex.stdout.readline,b''): 
        f.write(line.decode(sys.stdout.encoding))   
#        logger.info(line.decode(sys.stdout.encoding))
    ex.stdout.close()         
    
    #--------------------------------- 
    logger.info('Jigsaw FINISHED\n')
    #---------------------------------
   
    logger.info('..reading mesh\n')
    
    [nodes,edges,tria] = read_msh(rpath+'/jigsaw/'+ tag + '.msh')
    
    nodes = nodes.apply(pd.to_numeric)
    tria = tria.apply(pd.to_numeric)
    edges = edges.apply(pd.to_numeric)
    
# Interpolate on grid points 

    dem_dic.update({'grid_x':nodes.lon.values, 'grid_y':nodes.lat.values})
        
    dem = pdem.dem(**dem_dic)
   
    # Boundaries
    
    # LAND Boundaries (negative tag)    
    ib = 1
    isl = []
    for ik in range(edges.e3.min(),0):
        bb = np.unique(edges.loc[edges.e3 == ik,['e1','e2']].values.flatten())
        bf = pd.concat([nodes.loc[bb]],keys=['land_boundary_{}'.format(ib)])
        bf['idx'] = bb
        if ik >= bmindx: 
            bf['flag'] = 0
        else:
            bf['flag'] = 1

        isl.append(bf)
        ib += 1
        
    landb = pd.concat(isl)
    
    land_i = sorted(landb.index.levels[0], key=lambda x: int(x.split('_')[2]))
    
    # WATER Boundaries (positive tag)
    
    wb = 1
    wbs = []
    for ik in range(1,edges.e3.max()+1):
        bb = np.unique(edges.loc[edges.e3 == ik,['e1','e2']].values.flatten())
        bf = pd.concat([nodes.loc[bb]],keys=['open_boundary_{}'.format(wb)])
        bf['idx'] = bb

        wbs.append(bf)
        wb += 1
        
    openb = pd.concat(wbs)
    
    open_i = sorted(openb.index.levels[0], key=lambda x: int(x.split('_')[2]))
    
    #MAKE Dataset
    
    els = xr.DataArray(
          tria.loc[:,['a','b','c']].values,
          dims=['nSCHISM_hgrid_face', 'nMaxSCHISM_hgrid_face_nodes'], name='SCHISM_hgrid_face_nodes'
          )

    nod = nodes.loc[:,['lon','lat']].to_xarray().rename({'index':'nSCHISM_hgrid_node','lon':'SCHISM_hgrid_node_x','lat':'SCHISM_hgrid_node_y'})
    nod = nod.drop('nSCHISM_hgrid_node')

    dep = xr.Dataset({'depth': (['nSCHISM_hgrid_node'], -dem.Dataset.ival.values)})

    #open boundaries
    op=[]
    nop=[]
    o_label=[]
    for line in open_i:
        op.append(openb.loc[line,'idx'].values)
        nop.append(openb.loc[line,'idx'].size)
        o_label.append(line)

    xob = pd.DataFrame(op).T
    xob.columns = o_label

    oattr = pd.DataFrame({'label':o_label,'nps':nop})
    oattr['type'] = np.nan
    oattr.set_index('label', inplace=True, drop=True)

    #land boundaries

    lp=[]
    nlp=[]
    l_label=[]
    itype = []
    for line in land_i:
        lp.append(landb.loc[line,'idx'].values)
        nlp.append(landb.loc[line,'idx'].size)
        itype.append(landb.loc[line,'flag'].values[0])
        l_label.append(line)
    
    xlb = pd.DataFrame(lp).T
    xlb.columns = l_label

    lattr = pd.DataFrame({'label':l_label,'nps':nlp})
    lattr['type'] = itype
    lattr.set_index('label', inplace=True, drop=True)


    gr = xr.merge([nod,dep,els,xob.to_xarray(), xlb.to_xarray(), lattr.to_xarray(), oattr.to_xarray()]) # total
    
    
    logger.info('..done creating mesh\n')
    
    
    return gr
    
    
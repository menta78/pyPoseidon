import numpy as np
import matplotlib.pyplot as plt
import netCDF4
from mpl_toolkits.basemap import Basemap, shiftgrid
import scipy.interpolate
import sys
import grid

PATH='../BATHYMETRY/'

def pltm(minlat,maxlat,minlon,maxlon,lons,lats,topo,title=None):

# Create map
 m = Basemap(projection='cyl', llcrnrlat=minlat,urcrnrlat=maxlat,llcrnrlon=minlon, urcrnrlon=maxlon,resolution='l')
 fig = plt.figure(figsize=(10,8))
 cs = m.contourf(lons,lats,topo,cmap=plt.cm.jet)
 m.drawcoastlines()
 m.drawmapboundary()
 plt.title(title)
 cbar = plt.colorbar(orientation='horizontal', extend='both')
 cbar.ax.set_xlabel('meters')
 
# Save figure (without 'white' borders)
#plt.savefig('topo.png', bbox_inches='tight')
 plt.show(block=False)

def readsrtm(minlat,maxlat,minlon,maxlon,grid_x=None,grid_y=None,interpolate=False):
 file=PATH+'GLOBAL/topo30.grd'
# open NetCDF data in 
 nc = netCDF4.Dataset(file)
 ncv = nc.variables
#print ncv.keys()

 lon = ncv['lon'][:]
 lat = ncv['lat'][:]


# Shift longitude if neccessary

 if minlon < 0:

    lon=lon-180.

    i1=np.abs(lon-minlon).argmin()
    if lon[i1] > minlon: i1=i1-1
    i2=np.abs(lon-maxlon).argmin()
    if lon[i2] < maxlon: i2=i2+1

    j1=np.abs(lat-minlat).argmin()
    if lat[j1] > minlat: j1=j1-1
    j2=np.abs(lat-maxlat).argmin()
    if lat[j2] < maxlat: j2=j2+1

    lons, lats = np.meshgrid(lon[i1:i2],lat[j1:j2])

    zlon=lon.shape[0]

    topo = ncv['z'][j1:j2,zlon/2+i1:]
    topo = np.hstack([topo,ncv['z'][j1:j2,:i2-zlon/2]])

 else:

    i1=np.abs(lon-minlon).argmin()
    if lon[i1] > minlon: i1=i1-1
    i2=np.abs(lon-maxlon).argmin()
    if lon[i2] < maxlon: i2=i2+1

    j1=np.abs(lat-minlat).argmin()
    if lat[j1] > minlat: j1=j1-1
    j2=np.abs(lat-maxlat).argmin()
    if lat[j2] < maxlat: j2=j2+1

    lons, lats = np.meshgrid(lon[i1:i2],lat[j1:j2])
    topo = ncv['z'][j1:j2,i1:i2]

 pltm(minlat,maxlat,minlon,maxlon,lons,lats,topo,title='SRTM30 - READ')

 if interpolate :
# interpolate on the given grid
  #flip on lat to make it increasing for RectBivariateSpline
  ilon=lons[0,:]
  ilat=lats[:,0]
  sol=scipy.interpolate.RectBivariateSpline(ilon,ilat,topo.T)

  itopo=[]
  for x,y in zip(grid_x.ravel(),grid_y.ravel()):
      itopo.append(sol(x,y).ravel()[0])

  itopo=np.array(itopo)
  itopo=itopo.reshape(grid_x.shape)
  pltm(minlat,maxlat,minlon,maxlon,grid_x,grid_y,itopo,title='SRTM30 interpolated')
  return itopo
 else:
  return lons,lats,topo


def readgebco(minlat,maxlat,minlon,maxlon,grid_x=None,grid_y=None,interpolate=False):
 file=PATH+'GLOBAL/GEBCO_2014_2D.nc'
# open NetCDF data in 
 nc = netCDF4.Dataset(file)
 ncv = nc.variables
#print ncv.keys()

 lon = ncv['lon'][:]
 lat = ncv['lat'][:]

 if maxlon > 180:

    lon=lon+180.

    i1=np.abs(lon-minlon).argmin()
    if lon[i1] > minlon: i1=i1-1
    i2=np.abs(lon-maxlon).argmin()
    if lon[i2] < maxlon: i2=i2+1

    j1=np.abs(lat-minlat).argmin()
    if lat[j1] > minlat: j1=j1-1
    j2=np.abs(lat-maxlat).argmin()
    if lat[j2] < maxlat: j2=j2+1

    lons, lats = np.meshgrid(lon[i1:i2],lat[j1:j2])

    zlon=lon.shape[0]

    topo = ncv['elevation'][j1:j2,zlon/2+i1:]
    topo = np.hstack([topo,ncv['elevation'][j1:j2,:i2-zlon/2]])

 else:

    i1=np.abs(lon-minlon).argmin()
    if lon[i1] > minlon: i1=i1-1
    i2=np.abs(lon-maxlon).argmin()
    if lon[i2] < maxlon: i2=i2+1

    j1=np.abs(lat-minlat).argmin()
    if lat[j1] > minlat: j1=j1-1
    j2=np.abs(lat-maxlat).argmin()
    if lat[j2] < maxlat: j2=j2+1

    lons, lats = np.meshgrid(lon[i1:i2],lat[j1:j2])
    topo = ncv['elevation'][j1:j2,i1:i2]

 pltm(minlat,maxlat,minlon,maxlon,lons,lats,topo,title='GEBCO 2014 - READ')

 if interpolate :
# interpolate on the given grid
  #flip on lat to make it increasing for RectBivariateSpline
  ilon=lons[0,:]
  ilat=lats[:,0]
  sol=scipy.interpolate.RectBivariateSpline(ilon,ilat,topo.T)

  itopo=[]
  for x,y in zip(grid_x.ravel(),grid_y.ravel()):
      itopo.append(sol(x,y).ravel()[0])

  itopo=np.array(itopo)
  itopo=itopo.reshape(grid_x.shape)
  pltm(minlat,maxlat,minlon,maxlon,grid_x,grid_y,itopo,title='GEBCO 2014 - interpolated')
  return itopo
 else:
  return lons,lats,topo


def read_mod_gebco(minlat,maxlat,minlon,maxlon,grid_x=None,grid_y=None,interpolate=False):
 file=PATH+'GLOBAL/gebco30.nc'
# open NetCDF data in 
 nc = netCDF4.Dataset(file)
 ncv = nc.variables
#print ncv.keys()

 lon = ncv['x'][:]
 lat = ncv['y'][:]

 if maxlon > 180:

    lon=lon+180.

    i1=np.abs(lon-minlon).argmin()
    if lon[i1] > minlon: i1=i1-1
    i2=np.abs(lon-maxlon).argmin()
    if lon[i2] < maxlon: i2=i2+1

    j1=np.abs(lat-minlat).argmin()
    if lat[j1] > minlat: j1=j1-1
    j2=np.abs(lat-maxlat).argmin()
    if lat[j2] < maxlat: j2=j2+1

    lons, lats = np.meshgrid(lon[i1:i2],lat[j1:j2])

    zlon=lon.shape[0]

    topo = ncv['z'][j1:j2,zlon/2+i1:]
    topo = np.hstack([topo,ncv['z'][j1:j2,:i2-zlon/2]])

 else:

    i1=np.abs(lon-minlon).argmin()
    if lon[i1] > minlon: i1=i1-1
    i2=np.abs(lon-maxlon).argmin()
    if lon[i2] < maxlon: i2=i2+1

    j1=np.abs(lat-minlat).argmin()
    if lat[j1] > minlat: j1=j1-1
    j2=np.abs(lat-maxlat).argmin()
    if lat[j2] < maxlat: j2=j2+1

    lons, lats = np.meshgrid(lon[i1:i2],lat[j1:j2])
    topo = ncv['z'][j1:j2,i1:i2]

 pltm(minlat,maxlat,minlon,maxlon,lons,lats,topo,title='MODIFIED GEBCO - READ')

 if interpolate :
# interpolate on the given grid
  #flip on lat to make it increasing for RectBivariateSpline
  ilon=lons[0,:]
  ilat=lats[:,0]
  sol=scipy.interpolate.RectBivariateSpline(ilon,ilat,topo.T)

  itopo=[]
  for x,y in zip(grid_x.ravel(),grid_y.ravel()):
      itopo.append(sol(x,y).ravel()[0])

  itopo=np.array(itopo)
  itopo=itopo.reshape(grid_x.shape)
  pltm(minlat,maxlat,minlon,maxlon,grid_x,grid_y,itopo,title='MODIFIED GEBCO - interpolated')
  return itopo
 else:
  return lons,lats,topo


#############################################################################################################
### MAIN


# Definine the domain of interest
if __name__ == "__main__":
 try:
    minlat=sys.argv[1]
    maxlat=sys.argv[2]
    minlon=sys.argv[3]
    maxlon=sys.argv[4]
    stride=sys.argv[5]
 except:
    minlat = 28.
    maxlat = 48.
    minlon = -5.5
    maxlon = 47.5

 l1,l2,ba = readsrtm(float(minlat),float(maxlat),float(minlon),float(maxlon))
 c1,c2,bg = readgebco(float(minlat),float(maxlat),float(minlon),float(maxlon))
 m1,m2,bm = read_mod_gebco(float(minlat),float(maxlat),float(minlon),float(maxlon))

 topo=ba-bg
 pltm(minlat,maxlat,minlon,maxlon,m1,m2,topo,title='SRTM-GEBCO (DIFF)')
 plt.show(block=False)

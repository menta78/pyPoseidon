"""
Simulation management module

"""
# Copyright 2018 European Union
# This file is part of pyPoseidon, a software written by George Breyiannis (JRC E.1)
# Licensed under the EUPL, Version 1.2 or – as soon they will be approved by the European Commission - subsequent versions of the EUPL (the "Licence").
# Unless required by applicable law or agreed to in writing, software distributed under the Licence is distributed on an "AS IS" basis, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
# See the Licence for the specific language governing permissions and limitations under the Licence. 

import numpy as np
import datetime
import sys
import os, errno
from shutil import copy2
import logging
import glob
import pyPoseidon.model as pmodel
import pyPoseidon.grid as pgrid
from pyPoseidon.utils.get_value import get_value
import pandas as pd
from pyPoseidon.utils import data
import subprocess


#logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(levelname)-8s %(asctime)s:%(name)s:%(message)s')

file_handler = logging.FileHandler('cast.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

sformatter = logging.Formatter('%(levelname)-8s %(message)s')
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(sformatter)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)


def cast(solver=None,**kwargs):
    if solver == 'd3d' :
        return dcast(**kwargs)
    elif solver == 'schism' :
        return scast(**kwargs)
            

class dcast():
    
    def __init__(self,**kwargs):
               
        for attr, value in kwargs.items():
                setattr(self, attr, value)
                                   
    def run(self,**kwargs):
        
        pwd = os.getcwd()
                      
        files=[self.tag+'_hydro.xml',self.tag+'.enc',self.tag+'.obs', self.tag+'.bnd', self.tag+'.bca','run_flow2d3d.sh']
        files_sym=[self.tag+'.grd',self.tag+'.dep']
        
                
        prev=self.folders[0]
        fpath = self.path+'/{}/'.format(prev)
        
        cf = [glob.glob(self.path+prev+'/'+e) for e in files]
        cfiles = [item.split('/')[-1] for sublist in cf for item in sublist]
                    
        for date,folder,meteo,time_frame in zip(self.dates[1:],self.folders[1:],self.meteo_files[1:],self.time_frame[1:]):
            
            ppath = self.path+'/{}/'.format(prev)
            if not os.path.exists(ppath):
                sys.stdout.write('Initial folder not present {}\n'.format(ppath)) 
                sys.exit(1)
            
            prev = folder    
            # create the folder/run path

            rpath=self.path+'/{}/'.format(folder)   

            if not os.path.exists(rpath):
                os.makedirs(rpath)

            copy2(ppath+self.tag+'_model.json',rpath) #copy the info file

            # load model
            with open(rpath+self.tag+'_model.json', 'rb') as f:
                          info = pd.read_json(f,lines=True).T
                          info[info.isnull().values] = None
                          info = info.to_dict()[0]
                          
            
            args = set(kwargs.keys()).intersection(info.keys()) # modify dic with kwargs
            for attr in list(args):
                info[attr] = kwargs[attr]
            
            #update the properties   
            info['date'] = date
            info['start_date'] = date
            info['time_frame'] = time_frame
            info['meteo_files'] = meteo
            info['rpath'] = rpath
            if self.restart_step:
                info['restart_step'] = self.restart_step
            
#            for attr, value in self.items():
#                setattr(info, attr, value)
            m=pmodel(**info)
                                                         
            # copy/link necessary files

            for filename in cfiles:
                 copy2(ppath+filename,rpath+filename)
        #     if os.path.exists(rpath+filename)==False: 
        #        os.symlink(fpath+filename,rpath+filename)
        
        
            #symlink the big files
            for filename in files_sym:
                ipath = glob.glob(self.path+self.folders[0]+'/'+filename)[0]
                try:
                    os.symlink(os.path.realpath(ipath),rpath+filename)
                except OSError as e:
                  if e.errno == errno.EEXIST:
                      logger.warning('symlink for file {} present\n'.format(filename))
                      logger.info('overwriting\n')
                      os.remove(rpath+filename)
                      os.symlink(ipath,rpath+filename)
            
            copy2(ppath+m.tag+'.mdf',rpath) #copy the mdf file
                
            # copy restart file

            inresfile='tri-rst.'+m.tag+'.'+datetime.datetime.strftime(date,'%Y%m%d.%H%M%M')

            outresfile='restart.'+datetime.datetime.strftime(date,'%Y%m%d.%H%M%M')

          #  copy2(ppath+inresfile,rpath+'tri-rst.'+outresfile)
            try:
              os.symlink(ppath+inresfile,rpath+'tri-rst.'+outresfile)
            except OSError as e:
              if e.errno == errno.EEXIST:
                  logger.warning('Restart symlink present\n')
                  logger.warning('overwriting\n')
                  os.remove(rpath+'tri-rst.'+outresfile)
                  os.symlink(ppath+inresfile,rpath+'tri-rst.'+outresfile)
              else:
                  raise e            

            #get new meteo 

            logger.info('process meteo\n')

            flag = get_value(self,kwargs,'update',[])
            
#            check=[os.path.exists(rpath+f) for f in ['u.amu','v.amv','p.amp']]

#            if (np.any(check)==False) or ('meteo' in flag):
               
            m.force()
            m.to_force(m.meteo.Dataset,vars=['msl','u10','v10'],rpath=rpath)  #write u,v,p files 
        
#            else:
#                logger.info('meteo files present\n')
            
            # modify mdf file
            m.config(config_file = ppath+m.tag+'.mdf', config={'Restid':outresfile}, output=True)
                                              
            # run case
            logger.info('executing\n')
         
            os.chdir(rpath)
            #subprocess.call(rpath+'run_flow2d3d.sh',shell=True)
            m.save()
            
            m.run()
            
            #cleanup
            os.remove(rpath+'tri-rst.'+outresfile)
            
            # save compiled nc file
            
            #out = data(**{'solver':m.solver,'rpath':rpath,'savenc':True})
            
            logger.info('done for date :'+datetime.datetime.strftime(date,'%Y%m%d.%H'))


            os.chdir(pwd)
            
            
class scast():
    
    def __init__(self,**kwargs):
               
        for attr, value in kwargs.items():
                setattr(self, attr, value)

                   
    def run(self,**kwargs):
        
        
        pwd = os.getcwd()
                      
        files = [ 'bctides.in', 'launchSchism.sh','sflux/sflux_inputs.txt']
        files_sym = ['hgrid.gr3', 'hgrid.ll', 'manning.gr3', 'vgrid.in', 'drag.gr3', 'rough.gr3', 'windrot_geo2proj.gr3']

                
        prev=self.folders[0]
        fpath = self.path+'/{}/'.format(prev)
            

        for date,folder,meteo,time_frame in zip(self.dates[1:],self.folders[1:],self.meteo_files[1:],self.time_frame[1:]):
            
            ppath = self.path+'/{}/'.format(prev)
            if not os.path.exists(ppath):
                sys.stdout.write('Initial folder not present {}\n'.format(ppath)) 
                sys.exit(1)
            
            prev = folder    
            # create the folder/run path

            rpath=self.path+'/{}/'.format(folder)   

            if not os.path.exists(rpath):
                os.makedirs(rpath)

            copy2(ppath+self.tag+'_model.json',rpath) #copy the info file

            # load model
            with open(rpath+self.tag+'_model.json', 'rb') as f:
                          info = pd.read_json(f,lines=True).T
                          info[info.isnull().values] = None
                          info = info.to_dict()[0]
                          
            
            args = set(kwargs.keys()).intersection(info.keys()) # modify dic with kwargs
            for attr in list(args):
                info[attr] = kwargs[attr]
            
            
            # create restart file
            
            info['config_file'] = ppath + 'param.in'
            #check for combine hotstart
            hotout=int((date - self.date).total_seconds()/info['params']['vals']['dt'])
            
            resfiles=glob.glob(ppath+'/outputs/*_it*.nc')
            if not resfiles:
                ex=subprocess.Popen(args=['/Users/brey/SCHISM/v5.6.1/src/Utility/Combining_Scripts/combine_hotstart7 -i {}'.format(hotout)], cwd=ppath+'/outputs/', shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=1)

                for line in iter(ex.stdout.readline,b''): 
                    logger.info(line)
                    
                                
            #update the properties   
#            info['date'] = date
            info['start_date'] = date
            info['time_frame'] = time_frame
            info['meteo_files'] = meteo
            info['rpath'] = rpath
            info['grid_file'] = ppath + '/hgrid.gr3'
            
#            for attr, value in self.items():
#                setattr(info, attr, value)

            m=pmodel(**info)           
            
            # Grid         
            m.grid=pgrid.grid(type='tri2d',**info)
                 
            # set lat/lon from file
            if hasattr(self, 'grid_file'):
                info.update({'minlon' : m.grid.Dataset.SCHISM_hgrid_node_x.values.min()})
                info.update({'maxlon' : m.grid.Dataset.SCHISM_hgrid_node_x.values.max()})
                info.update({'minlat' : m.grid.Dataset.SCHISM_hgrid_node_y.values.min()})
                info.update({'maxlat' : m.grid.Dataset.SCHISM_hgrid_node_y.values.max()})
                                                         
            # copy/link necessary files
            for filename in files:
                ipath = glob.glob(ppath+filename)
                if ipath:
                    try:
                        copy2(ppath+filename,rpath+filename)
                    except:
                        dir_name ,file_name = os.path.split(filename)
                        if not os.path.exists(rpath + dir_name):
                            os.makedirs(rpath + dir_name)
                        copy2(ppath+filename,rpath+filename)


            #symlink the big files
            for filename in files_sym:
                ipath = glob.glob(self.path+self.folders[0]+'/'+filename)
                if ipath:
                    try:
                        os.symlink(ipath[0],rpath+filename)
                    except OSError as e:
                        if e.errno == os.errno.EEXIST:
                            sys.stdout.write('Restart link present\n')
                            sys.stdout.write('overwriting\n')
                            os.remove(rpath+filename)
                            os.symlink(ipath[0],rpath+filename)


                
            # link restart file
            inresfile='/outputs/hotstart_it={}.nc'.format(hotout)
            outresfile='/hotstart.nc'


            logger.info('set restart\n')

            try:
                os.symlink(ppath+inresfile,rpath+outresfile)
            except OSError as e:
                if e.errno == os.errno.EEXIST:
                    sys.stdout.write('Restart link present\n')
                    sys.stdout.write('overwriting\n')
                    os.remove(rpath+outresfile)
                    os.symlink(ppath+inresfile,rpath+outresfile)
                else:
                    raise e            

            #get new meteo 

            logger.info('process meteo\n')

            flag = get_value(self,kwargs,'update',[])
            
#            check=[os.path.exists(rpath+'sflux/'+ f) for f in ['sflux_inputs.txt', 'sflux_air_1.001.nc']]

#            if (np.any(check)==False) or ('meteo' in flag):
               
            m.force(**info)
            m.to_force(m.meteo.Dataset,vars=['msl','u10','v10'],rpath=rpath)  #write u,v,p files 
        
#            else:
#                logger.warning('meteo files present\n')
            
            # modify param file
            rnday_new = (date - self.date).total_seconds()/(3600*24.) + pd.to_timedelta(time_frame).total_seconds()/(3600*24.)
            info['parameters'].update({'ihot': 2, 'rnday':rnday_new, 'nramp_elev':1, 'start_hour':self.date.hour , 'start_day':self.date.day, 'start_month':self.date.month, 'start_year':self.date.year })
            
            m.config(output=True, **info)
                                              
            os.chdir(rpath)
            #subprocess.call(rpath+'run_flow2d3d.sh',shell=True)
            m.save()
            
            m.run()
            
            #cleanup
#            os.remove(rpath+'hotstart.nc')
            
            # save compiled nc file
            
            #out = data(**{'solver':m.solver,'rpath':rpath,'savenc':True})
            
            logger.info('done for date :'+datetime.datetime.strftime(date,'%Y%m%d.%H'))

            os.chdir(pwd)
            

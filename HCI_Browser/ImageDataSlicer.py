'''
Created on Jan 20, 2014

@author: tpmaxwel
'''
from PyQt4 import QtGui, QtCore
import cdms2, sys

class CacheLevel:
    NoCache = 0
    CurrentTimestep = 1
    AllTimesteps = 2
    
class DataSlicer( QtCore.QObject ):
    
    dsCacheLevel = CacheLevel.AllTimesteps
    
    def __init__(self, dsetPath, varName, **args ):  
        self.dset = cdms2.open( dsetPath, 'r' )
        self.var = self.dset[ varName ]
        self.timestep_cache = {}
        self.currentAxis = -1
        self.currentSlice = -1
        
    def getVariable(self):
        return self.var
    
    def getDataCube( self, iTime ):
        dataCube = self.timestep_cache.get( iTime, None )
        if dataCube == None:
            dataCube = self.var( time=slice(iTime,iTime+1), order ='zyx' )
            dataCube = dataCube.data.squeeze() 
            if ( self.dsCacheLevel == CacheLevel.AllTimesteps ):
                self.timestep_cache[ iTime ] = dataCube 
        return dataCube 
    
    def getSlice( self, iAxis, iTime, slider_pos, coord_value ):
        axis = None
        if  iAxis == 0:   
            axis = self.var.getLongitude()
        elif  iAxis == 1:  
            axis = self.var.getLatitude()
        elif  iAxis == 2:   
            axis = self.var.getLevel()
        assert (axis <> None), "Error, nonexistent azis index: %d " % iAxis
        values = axis.getValue()
        nvals = len( values )
#        fval = values[0] + slider_pos * ( values[-1] - values[0] ) 
        iVal = int ( slider_pos * nvals )
        if ( iAxis == self.currentAxis ) and ( iVal == self.currentSlice ): return None
        if ( iVal > nvals - 1 ): iVal = nvals - 1
        dataCube = None if ( self.dsCacheLevel == CacheLevel.NoCache ) else self.getDataCube( iTime )
        hasDataCube = ( id(dataCube) <> id(None) )
        if not hasDataCube:
            iVal0 = nvals - 2 if (iVal == nvals - 1) else iVal
            iVal1 = iVal0 + 1
        try:
            if  iAxis == 0:   
                if hasDataCube:     dataslice = dataCube[ :, :, iVal ]
                else:               dataslice = self.var( time=slice(iTime,iTime+1), longitude = slice(iVal0,iVal1), order ='zy' )                  
            elif  iAxis == 1: 
                if hasDataCube:     dataslice = dataCube[ :, iVal, : ]
                else:               dataslice = self.var( time=slice(iTime,iTime+1), latitude = slice(iVal0,iVal1), order ='zx'  )                 
            elif  iAxis == 2: 
                if hasDataCube:     dataslice = dataCube[ iVal, :, : ]
                else:               dataslice = self.var( time=slice(iTime,iTime+1), level = slice(iVal0,iVal1), order ='yx'  ) 
        except cdms2.error.CDMSError, err:
            print>>sys.stderr, "Error getting slice[%d] (%.2f): %s " % ( iAxis, coord_value, str(err) )
            return None
        
        self.currentAxis = iAxis 
        self.currentSlice = iVal 
        imageOutput =  dataslice.squeeze() 
             
        return imageOutput
    
if __name__ == "__main__":
    
    dset_path = "/Developer/Data/AConaty/comp-ECMWF/ac-comp1-geos5.xml"
    varname = "uwnd"
    
    ds = DataSlicer( dset_path, varname )
    
    s = ds.getSlice( 0, 0, 0.5, 180.0 )
    
    print "Done!"
    pass
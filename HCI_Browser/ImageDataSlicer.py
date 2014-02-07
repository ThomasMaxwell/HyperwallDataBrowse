'''
Created on Jan 20, 2014

@author: tpmaxwel
'''
from PyQt4 import QtGui, QtCore
import cdms2, sys, copy
import numpy as np

class CacheLevel:
    NoCache = 0
    CurrentTimestep = 1
    AllTimesteps = 2
    
class DataSlicer( QtCore.QObject ):
    
    dsCacheLevel = CacheLevel.AllTimesteps
    
    def __init__(self, dsetPath, varName, **args ): 
        QtCore.QObject.__init__(self) 
        self.dset = cdms2.open( dsetPath, 'r' )
        self.var = self.dset[ varName ]
        self.timestep_cache = {}
        self.currentGridAxis = -1
        self.currentSlice = -1
        self.currentTime = 0
        self.currentPosition = [ 0, 0, 0, 0 ]
        
    def getVariable(self):
        return self.var
    
    def getDatasetTitle(self):
        return " %s: %s " % ( self.dset.getglobal('id'), self.dset.getglobal('Title') )
    
    def getDataCube( self, iTime ):
        dataCube = self.timestep_cache.get( iTime, None )
        if dataCube == None:
            time_axis = self.var.getTime()
            dataCube = self.var( time=time_axis[iTime], order ='zyx' )
            dataCube = dataCube.data.squeeze() 
            if ( self.dsCacheLevel == CacheLevel.AllTimesteps ):
                self.timestep_cache[ iTime ] = dataCube 
        return dataCube 
    
    def getAxis(self, iAxis ):
        axis = None
        if  iAxis == 0:   
            axis = self.var.getLongitude()
        elif  iAxis == 1:  
            axis = self.var.getLatitude()
        elif  iAxis == 2:   
            axis = self.var.getLevel()   
        elif  iAxis == 3:   
            axis = self.var.getTime() 
        else:
            print>>sys.stderr, "Error, illegal axis index: %d " % iAxis
        return axis  

    def getPoint( self, **args ):
        taxis = self.var.getTime()
        saxes = [ None, None, None ]
        pointIndices = copy.deepcopy( self.currentPosition )
        for ( iAxis, axisName ) in enumerate( [ 'lon', 'lat', 'lev'] ):
            cVal = args.get( axisName, None )
            if cVal:
                axis = self.getAxis( iAxis )
                saxes[ iAxis ] = axis
                avals = axis.getValue()
                nvals = len( avals )
                if avals[0] > avals[-1]:
                    iVal = np.searchsorted( avals[::-1], cVal )
                    iVal = nvals - iVal - 1
                else:
                    iVal = np.searchsorted( avals, cVal ) 
                pointIndices[ iAxis ] = iVal if (iVal < nvals) else ( nvals - 1 )
        dataCube = None if ( self.dsCacheLevel == CacheLevel.NoCache ) else self.getDataCube( pointIndices[ 3 ] )
        hasDataCube = ( id(dataCube) <> id(None) )
        try:
            if hasDataCube:     datapoint = dataCube[ pointIndices[2], pointIndices[1], pointIndices[0] ]
            else:               datapoint = self.var( time=taxis[pointIndices[0]], level=saxes[0][pointIndices[1]], latitude=saxes[1][pointIndices[2]], longitude=saxes[2][pointIndices[3]]  )                  
        except cdms2.error.CDMSError, err:
            print>>sys.stderr, "Error getting point[%s] (%s): %s " % ( str(args), str(pointIndices), str(err) )
            return None
        
        return datapoint.squeeze()              
    
    def getSlice( self, iAxis, slider_pos, coord_value ):
        taxis = self.var.getTime()
        axis = self.getAxis( iAxis )
        if iAxis == 3:
            values = taxis.getValue()
            nvals = len( values )
            iTime = int ( slider_pos * nvals )
            if iTime >= nvals: iTime = nvals - 1
            iVal = self.currentSlice
            if ( iTime == self.currentTime ): return None
            self.currentPosition[ iAxis ] = iTime
        else:
            values = axis.getValue()
            nvals = len( values )
            iVal = int ( slider_pos * nvals )
            if iVal >= nvals: iVal = nvals - 1
            self.currentPosition[ iAxis ] = iVal
            iTime = self.currentTime
            if ( iAxis == self.currentGridAxis ) and ( iVal == self.currentSlice ): return None
            if ( iVal > nvals - 1 ): iVal = nvals - 1
        dataCube = None if ( self.dsCacheLevel == CacheLevel.NoCache ) else self.getDataCube( iTime )
        hasDataCube = ( id(dataCube) <> id(None) )
        try:
            if    (iAxis == 0) or ( (iAxis == 3) and (self.currentGridAxis == 0) ):   
                if hasDataCube:     dataslice = dataCube[ :, :, iVal ]
                else:               dataslice = self.var( time=taxis[iTime], longitude=axis[iVal], order ='zy' )                  
            elif  (iAxis == 1) or ( (iAxis == 3) and (self.currentGridAxis == 1) ):   
                if hasDataCube:     dataslice = dataCube[ :, iVal, : ]
                else:               dataslice = self.var( time=taxis[iTime], latitude=axis[iVal], order ='zx'  )                 
            elif  (iAxis == 2) or ( (iAxis == 3) and (self.currentGridAxis == 2) ):   
                if hasDataCube:     dataslice = dataCube[ iVal, :, : ]
                else:               dataslice = self.var( time=taxis[iTime], level=axis[iVal], order ='yx'  ) 
        except cdms2.error.CDMSError, err:
            print>>sys.stderr, "Error getting slice[%d] (%s): %s " % ( iAxis, str(coord_value), str(err) )
            return None
        
        if ( iAxis <> 3 ): 
            self.currentGridAxis = iAxis 
        self.currentSlice = iVal 
        self.currentTime = iTime
        imageOutput =  dataslice.squeeze() 
             
        return imageOutput
    
if __name__ == "__main__":
    
    dset_path = "/Developer/Data/AConaty/comp-ECMWF/ac-comp1-geos5.xml"
    varname = "uwnd"
    
    ds = DataSlicer( dset_path, varname )
    
    
    s = ds.getSlice( 2, 0.5, 50.0 )
    ptOutput = ds.getPoint( lat=-2.2, lon=100.0 )
    print str( s.shape ), str( ptOutput )
    
    print "Done!"
    pass
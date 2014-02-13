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
        self.roi = None
        self.currentPosition = [ 0, 0, 0, 0 ]
        self.index_interval = [ None, None, None ]
        
    def getVariable(self):
        return self.var
    
    def getDatasetTitle(self):
        ds_title = []
        title = self.dset.getglobal('Title')
        dsid = self.dset.getglobal('id')
        if title:   ds_title.append( title ) 
        if dsid:    ds_title.append( "id = %s" % dsid ) 
        return "\n".join( ds_title )
    
    def computeIndexIntervals(self):
        for iAxis in range(3):
            axis = self.getAxis( iAxis )
            if (self.roi == None) or (iAxis==2):    
                self.index_interval[iAxis] = [ 0, len(axis) ]
            else: 
                coord_bounds = [ self.roi[iAxis], self.roi[2+iAxis] ]
                if axis.isLongitude() and ( ( coord_bounds[0] < 0.0 ) or ( coord_bounds[1] < 0.0 ) ):        
                    coord_bounds[0] = coord_bounds[0] + 360.0
                    coord_bounds[1] = coord_bounds[1] + 360.0
                self.index_interval[iAxis] = axis.mapIntervalExt( coord_bounds )                  
    
    def getDataCube( self, iTime ):
        dataCube = self.timestep_cache.get( iTime, None )
        if dataCube == None:
            time_axis = self.var.getTime()
            if self.roi == None:    
                dataCube = self.var( time=time_axis[iTime], order ='zyx' )
            else:
                dataCube = self.var( time=time_axis[iTime], latitude=slice(*self.index_interval[1]), longitude=slice(*self.index_interval[0]), order ='zyx' )
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
        pointCoords = [ 0, 0, 0 ]
        rpt = args.get( 'rpt', None )
        if rpt:
            if self.currentGridAxis==0:
                args[ 'rlat' ] = rpt[0]
                args[ 'rlev' ] = rpt[1]
                activeCoords = [ 1, 2 ]
            elif self.currentGridAxis==1:
                args[ 'rlon' ] = rpt[0]
                args[ 'rlev' ] = rpt[1]
                activeCoords = [ 0, 2 ]
            elif self.currentGridAxis==2:
                args[ 'rlon' ] = rpt[0]
                args[ 'rlat' ] = rpt[1]
                activeCoords = [ 0, 1 ]
        for ( iAxis, axisName ) in enumerate( [ 'lon', 'lat', 'lev'] ):
            axis = self.getAxis( iAxis )
            avals = axis.getValue()
            saxes[ iAxis ] = axis
            nvals = len( avals )
            index_interval = self.index_interval[ iAxis ]
                
            rVal = args.get( "r%s" % axisName, None )
            if rVal:   
                if hasattr( axis, 'positive' ) and ( axis.positive == 'down' ) and ( avals[1] > avals[0] ):
                    iVal = int( round( index_interval[1] + rVal * ( index_interval[0] - index_interval[1] ) ) )
                else:
                    iVal = int( round( index_interval[0] + rVal * ( index_interval[1] - index_interval[0] ) ) )
                iVal = iVal if (iVal < nvals) else ( nvals - 1 )
                pointCoords[ iAxis ] = avals[ iVal ] 
            else: 
                iVal = pointIndices[ iAxis ]
                
            pointIndices[ iAxis ] = iVal - index_interval[0]
            
        dataCube = None if ( self.dsCacheLevel == CacheLevel.NoCache ) else self.getDataCube( pointIndices[ 3 ] )
        hasDataCube = ( id(dataCube) <> id(None) )
        try:
            if hasDataCube:     datapoint = dataCube[ pointIndices[2], pointIndices[1], pointIndices[0] ]
            else:               datapoint = self.var( time=taxis[pointIndices[0]], level=saxes[0][pointIndices[1]], latitude=saxes[1][pointIndices[2]], longitude=saxes[2][pointIndices[3]]  )                  
        except cdms2.error.CDMSError, err:
            print>>sys.stderr, "Error getting point[%s] (%s): %s " % ( str(args), str(pointIndices), str(err) )
            return None
        
        return [ pointCoords[activeCoords[0]], pointCoords[activeCoords[1]] ], [ pointIndices[activeCoords[0]], pointIndices[activeCoords[1]] ], datapoint.squeeze()              

#     def getPoint( self, **args ):
#         taxis = self.var.getTime()
#         saxes = [ None, None, None ]
#         pointIndices = copy.deepcopy( self.currentPosition )
#         pointCoords = [ 0, 0, 0 ]
#         rpt = args.get( 'rpt', None )
#         if rpt:
#             if self.currentGridAxis==0:
#                 args[ 'rlat' ] = rpt[0]
#                 args[ 'rlev' ] = rpt[1]
#                 activeCoords = [ 1, 2 ]
#             elif self.currentGridAxis==1:
#                 args[ 'rlon' ] = rpt[0]
#                 args[ 'rlev' ] = rpt[1]
#                 activeCoords = [ 0, 2 ]
#             elif self.currentGridAxis==2:
#                 args[ 'rlon' ] = rpt[0]
#                 args[ 'rlat' ] = rpt[1]
#                 activeCoords = [ 0, 1 ]
#         for ( iAxis, axisName ) in enumerate( [ 'lon', 'lat', 'lev'] ):
#             axis = self.getAxis( iAxis )
#             avals = axis.getValue()
#             saxes[ iAxis ] = axis
#             nvals = len( avals )
#             cVal = args.get( axisName, None )
#             if cVal == None:
#                 rVal = args.get( "r%s" % axisName, None )
#                 if rVal:
#                     if (self.roi == None) or (iAxis==2):
#                         vbnds = [ avals[0], avals[-1] ]
#                     else:
#                         vbnds = [ self.roi[iAxis], self.roi[2+iAxis] ]
#                 
#                     if hasattr( axis, 'positive' ) and ( axis.positive == 'down' ) and ( vbnds[1] > vbnds[0] ):
#                         cVal = vbnds[1] + rVal * ( vbnds[0] - vbnds[1] )
#                     else:
#                         cVal = vbnds[0] + rVal * ( vbnds[1] - vbnds[0] )
#             if cVal <> None:
#                 if avals[0] > avals[-1]:
#                     iVal = np.searchsorted( avals[::-1], cVal )
#                     iVal = nvals - iVal - 1
#                 else:
#                     iVal = np.searchsorted( avals, cVal )
#                 iVal = iVal if (iVal < nvals) else ( nvals - 1 )
#                 pointCoords[ iAxis ] = avals[ iVal ] 
#                 pointIndices[ iAxis ] = iVal
#             
#         dataCube = None if ( self.dsCacheLevel == CacheLevel.NoCache ) else self.getDataCube( pointIndices[ 3 ] )
#         hasDataCube = ( id(dataCube) <> id(None) )
#         try:
#             if hasDataCube:     datapoint = dataCube[ pointIndices[2], pointIndices[1], pointIndices[0] ]
#             else:               datapoint = self.var( time=taxis[pointIndices[0]], level=saxes[0][pointIndices[1]], latitude=saxes[1][pointIndices[2]], longitude=saxes[2][pointIndices[3]]  )                  
#         except cdms2.error.CDMSError, err:
#             print>>sys.stderr, "Error getting point[%s] (%s): %s " % ( str(args), str(pointIndices), str(err) )
#             return None
#         
#         return [ pointCoords[activeCoords[0]], pointCoords[activeCoords[1]] ], [ pointIndices[activeCoords[0]], pointIndices[activeCoords[1]] ], datapoint.squeeze()              
    
    def getSlice( self, iAxis, slider_pos, coord_value ):
        taxis = self.var.getTime()
        axis = self.getAxis( iAxis )
        if self.index_interval[0] == None:
            self.computeIndexIntervals()
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
                if hasDataCube:             dataslice = dataCube[ :, :, iVal ]
                elif ( self.roi == None):   dataslice = self.var( time=taxis[iTime], longitude=axis[iVal], order ='zy' )  
                else:                       dataslice = self.var( time=taxis[iTime], longitude=axis[iVal], latitude=slice(*self.index_interval[1]), order ='zy' )   
            elif  (iAxis == 1) or ( (iAxis == 3) and (self.currentGridAxis == 1) ):   
                if hasDataCube:             dataslice = dataCube[ :, iVal, : ]
                elif ( self.roi == None):   dataslice = self.var( time=taxis[iTime], latitude=axis[iVal], order ='zx'  )                 
                else:                       dataslice = self.var( time=taxis[iTime], latitude=axis[iVal], longitude=slice(*self.index_interval[0]), order ='zx'  )                 
            elif  (iAxis == 2) or ( (iAxis == 3) and (self.currentGridAxis == 2) ):   
                if hasDataCube:             dataslice = dataCube[ iVal, :, : ]
                elif ( self.roi == None):   dataslice = self.var( time=taxis[iTime], level=axis[iVal], order ='yx'  ) 
                else:                       dataslice = self.var( time=taxis[iTime], level=axis[iVal], latitude=slice(*self.index_interval[1]), longitude=slice(*self.index_interval[0]), order ='yx'  ) 
        except cdms2.error.CDMSError, err:
            print>>sys.stderr, "Error getting slice[%d] (%s): %s " % ( iAxis, str(coord_value), str(err) )
            return None
        
        if ( iAxis <> 3 ): 
            self.currentGridAxis = iAxis 
        self.currentSlice = iVal 
        self.currentTime = iTime
        imageOutput =  dataslice.squeeze() 
             
        return imageOutput

    def setRoi( self, roi ):
        self.roi = roi
        self.computeIndexIntervals()
        self.timestep_cache = {}
        taxis = self.var.getTime()
        iAxis = self.currentGridAxis
        iVal = self.currentSlice if (iAxis == 2) else 0
        iTime = self.currentTime
        axis = self.getAxis( iAxis ) 
        dataCube = None if ( self.dsCacheLevel == CacheLevel.NoCache ) else self.getDataCube( iTime )
        hasDataCube = ( id(dataCube) <> id(None) )
        try:
            if    (iAxis == 0) or ( (iAxis == 3) and (self.currentGridAxis == 0) ):   
                if hasDataCube:     dataslice = dataCube[ :, :, iVal ]
                else:               dataslice = self.var( time=taxis[iTime], longitude=axis[iVal], latitude=slice(*self.index_interval[1]), order ='zy' )                  
            elif  (iAxis == 1) or ( (iAxis == 3) and (self.currentGridAxis == 1) ):   
                if hasDataCube:     dataslice = dataCube[ :, iVal, : ]
                else:               dataslice = self.var( time=taxis[iTime], latitude=axis[iVal], longitude=slice(*self.index_interval[0]), order ='zx'  )                 
            elif  (iAxis == 2) or ( (iAxis == 3) and (self.currentGridAxis == 2) ):   
                if hasDataCube:     dataslice = dataCube[ iVal, :, : ]
                else:               dataslice = self.var( time=taxis[iTime], level=axis[iVal], latitude=slice(*self.index_interval[1]), longitude=slice(*self.index_interval[0]), order ='yx'  ) 
        except cdms2.error.CDMSError, err:
            print>>sys.stderr, "Error getting slice[%d]: %s " % ( iAxis, str(err) )
            return None
        
        self.currentSlice = iVal
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
'''
Created on Jan 20, 2014

@author: tpmaxwel
'''
from PyQt4 import QtGui, QtCore
import cdms2, sys, copy, traceback
import numpy as np

class CacheLevel:
    NoCache = 0
    CurrentTimestep = 1
    AllTimesteps = 2

def isDesignated( axis ):
    return ( axis.isLatitude() or axis.isLongitude() or axis.isLevel() or axis.isTime() )

def matchesAxisType( axis, axis_attr, axis_aliases ):
    matches = False
    aname = axis.id.lower()
    axis_attribute = axis.attributes.get('axis',None)
    if axis_attribute and ( axis_attribute.lower() in axis_attr ):
        matches = True
    else:
        for axis_alias in axis_aliases:
            if ( aname.find( axis_alias ) >= 0): 
                matches = True
                break
    return matches
    
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
        self.designateAxes()
        self.data_bounds = None
        
        
    def getVariable(self):
        return self.var

    def designateAxes(self):
        lev_aliases = [ 'bottom', 'top', 'zdim', 'level', 'height', 'isobaric' ]
        lev_axis_attr = [ 'z' ]
        lat_aliases = [ 'north', 'south' ]
        alt_lat_names = [ 'ydim' ]
        lat_axis_attr = [ 'y' ]
        lon_aliases = [ 'east', 'west' ]
        alt_lon_names = [ 'xdim' ]
        lon_axis_attr = [ 'x' ]
        latLonGrid = True
        for axis in self.var.getAxisList():
            if not isDesignated( axis ):
                if matchesAxisType( axis, lev_axis_attr, lev_aliases ):
                    axis.designateLevel()
                    print " --> Designating axis %s as a Level axis " % axis.id            
                elif matchesAxisType( axis, lat_axis_attr, lat_aliases ):
                    axis.designateLatitude()
                    print " --> Designating axis %s as a fake Latitude axis " % axis.id 
                    latLonGrid = False 
                elif axis.id.lower() in alt_lat_names:
                    axis.designateLatitude()
                    print " --> Designating axis %s as a true Latitude axis " % axis.id                                        
                elif matchesAxisType( axis, lon_axis_attr, lon_aliases ):
                    axis.designateLongitude()
                    print " --> Designating axis %s as a fake Longitude axis " % axis.id 
                    latLonGrid = False 
                elif axis.id.lower() in alt_lon_names:
                    axis.designateLongitude()
                    print " --> Designating axis %s as a true Longitude axis " % axis.id                                        
            elif ( axis.isLatitude() or axis.isLongitude() ):
                if ( axis.id.lower()[0] == 'x' ) or ( axis.id.lower()[0] == 'y' ):
                    latLonGrid = False 
        return latLonGrid    
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

    def getTimeseries( self, iTime ):
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
        compute_timeseries = args.get( 'timeseries', False )
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
                if hasattr( axis, 'positive' ) and ( axis.positive == 'down' ):
                    iVal = int( round( index_interval[1] + rVal * ( index_interval[0] - index_interval[1] ) ) )
                else:
                    iVal = int( round( index_interval[0] + rVal * ( index_interval[1] - index_interval[0] ) ) )
                iVal = iVal if  (iVal < index_interval[1] ) else ( index_interval[1] - 1 )
                pointCoords[ iAxis ] = avals[ iVal ] 
            else: 
                iVal = pointIndices[ iAxis ]
                
            pointIndices[ iAxis ] = iVal - index_interval[0]
            
        dataCube = None if ( ( self.dsCacheLevel == CacheLevel.NoCache ) or compute_timeseries ) else self.getDataCube( pointIndices[ 3 ] )
        hasDataCube = ( id(dataCube) <> id(None) )
        tseries = None
        try:
            try:
#                print str( saxes ), str( pointIndices )
                if compute_timeseries:
#                     lat_val = saxes[1][pointIndices[1]]
#                     lon_val = saxes[0][pointIndices[0]]
#                     lev_axis = saxes[2]
#                     tseries = self.var( level=saxes[2][pointIndices[2]], latitude=saxes[1][pointIndices[1]], longitude=saxes[0][pointIndices[0]] ).squeeze()  
#                     nts = len( tseries )
#                     tindex = pointIndices[3] if ( pointIndices[3] < nts ) else nts - 1
#                     datapoint = tseries[ tindex ]    
 
                    lon_val = saxes[0][ pointIndices[0] + self.index_interval[0][0] ]
                    lat_val = saxes[1][ pointIndices[1] + self.index_interval[1][0] ]
                    lev_axis = saxes[2]
#                    invert_lev = ( hasattr( lev_axis, 'positive' ) and ( lev_axis.positive == 'down' ) )
#                    lev_index =  self.index_interval[2][1] - C if invert_lev else pointIndices[2] 
                    lev_val = lev_axis[ pointIndices[2]  ]
                    tseries = self.var( level=lev_val, latitude=lat_val, longitude=lon_val  ).squeeze() 
                    datapoint = tseries[ pointIndices[3] ]
                    print "Compute timeseries: pt = [ %.2f, %.2f, %.2f ], ptIndices = %s, lev_index = %d " % ( lon_val, lat_val, lev_val, str(pointIndices), pointIndices[2] )
                else:                   
                    if hasDataCube:     datapoint = dataCube[ pointIndices[2], pointIndices[1], pointIndices[0] ].squeeze()
                    else:               datapoint = self.var( time=taxis[pointIndices[3]], level=saxes[2][pointIndices[2]], latitude=saxes[1][pointIndices[1]], longitude=saxes[0][pointIndices[0]]  ).squeeze()      
            except cdms2.error.CDMSError, err:
                print>>sys.stderr, "Error getting point[%s] (%s): %s " % ( str(args), str(pointIndices), str(err) )
                return None
        except:
            traceback.print_exc(10)
            return None
        
        return [ pointCoords[activeCoords[0]], pointCoords[activeCoords[1]] ], [ pointIndices[activeCoords[0]], pointIndices[activeCoords[1]] ], datapoint, tseries           

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

    def getCurrentPositionIndex( self, iAxis ):
        return self.currentPosition[ iAxis ]
    
    def getSlice( self, iAxis=None, slider_pos=None, coord_value='NULL' ):
        taxis = self.var.getTime()
        if iAxis == None: iAxis = self.currentGridAxis
        axis = self.getAxis( iAxis )
        if self.index_interval[0] == None:
            self.computeIndexIntervals()
        if iAxis == 3:
            values = taxis.getValue()
            nvals = len( values )
            iTime = self.currentTime if (slider_pos == None) else int ( slider_pos * nvals )
            if iTime >= nvals: iTime = nvals - 1
            iVal = self.currentSlice
            if ( (iTime == self.currentTime) and (slider_pos <> None)  ): return None
            self.currentPosition[ iAxis ] = iTime
        else:
            values = axis.getValue()
            nvals = len( values )
            iVal = self.currentSlice if (slider_pos == None) else int ( slider_pos * nvals )
            if iVal >= nvals: iVal = nvals - 1
            self.currentPosition[ iAxis ] = iVal
            iTime = self.currentTime
            if ( iAxis == self.currentGridAxis ) and ( iVal == self.currentSlice ) and (slider_pos <> None): return None
            if ( iVal > nvals - 1 ): iVal = nvals - 1
        dataCube = None if ( self.dsCacheLevel == CacheLevel.NoCache ) else self.getDataCube( iTime )
        hasDataCube = ( id(dataCube) <> id(None) )
        aval = axis[iVal]
        try:
            try:
                if    (iAxis == 0) or ( (iAxis == 3) and (self.currentGridAxis == 0) ):   
                    if hasDataCube:             dataslice = dataCube[ :, :, iVal-self.index_interval[0][0] ]
                    elif ( self.roi == None):   dataslice = self.var( time=taxis[iTime], longitude=aval, order ='zy' )  
                    else:                       dataslice = self.var( time=taxis[iTime], longitude=aval, latitude=slice(*self.index_interval[1]), order ='zy' )   
                elif  (iAxis == 1) or ( (iAxis == 3) and (self.currentGridAxis == 1) ):   
                    if hasDataCube:             dataslice = dataCube[ :, iVal-self.index_interval[1][0], : ]
                    elif ( self.roi == None):   dataslice = self.var( time=taxis[iTime], latitude=aval, order ='zx'  )                 
                    else:                       dataslice = self.var( time=taxis[iTime], latitude=aval, longitude=slice(*self.index_interval[0]), order ='zx'  )                 
                elif  (iAxis == 2) or ( (iAxis == 3) and (self.currentGridAxis == 2) ):   
                    if hasDataCube:             dataslice = dataCube[ iVal, :, : ]
                    elif ( self.roi == None):   dataslice = self.var( time=taxis[iTime], level=aval, order ='yx'  ) 
                    else:                       dataslice = self.var( time=taxis[iTime], level=aval, latitude=slice(*self.index_interval[1]), longitude=slice(*self.index_interval[0]), order ='yx'  ) 
            except cdms2.error.CDMSError, err:
                print>>sys.stderr, "Error getting slice[%d] (%s): %s " % ( iAxis, str(coord_value), str(err) )
                return None
        except:
            traceback.print_exc()
            return None
            
        if ( iAxis <> 3 ): 
            self.currentGridAxis = iAxis 
        self.currentSlice = iVal 
        self.currentTime = iTime
        missing_value = self.var.missing_value if hasattr( self.var, 'missing_value' ) else None
        if missing_value <> None: dataslice = np.ma.masked_equal( dataslice, missing_value, False )
        self.data_bounds = [ np.ma.amin( dataslice ), np.ma.amax( dataslice ) ]
        imageOutput =  dataslice.squeeze()             
        return imageOutput
    
    def getDataBounds(self):
        return self.data_bounds

    def setRoi( self, roi ):
        self.roi = roi
        self.computeIndexIntervals()
        self.timestep_cache = {}
        return self.getSlice()
        
        
#        
#        taxis = self.var.getTime()
#        iAxis = self.currentGridAxis
#        iVal = self.currentSlice # if (iAxis == 2) else 0
#        iTime = self.currentTime
#        axis = self.getAxis( iAxis ) 
#        dataCube = None if ( self.dsCacheLevel == CacheLevel.NoCache ) else self.getDataCube( iTime )
#        hasDataCube = ( id(dataCube) <> id(None) )
#        try:
#            try:
#                if    (iAxis == 0) or ( (iAxis == 3) and (self.currentGridAxis == 0) ):   
#                    if hasDataCube:     dataslice = dataCube[ :, :, iVal-self.index_interval[0][0] ]
#                    else:               dataslice = self.var( time=taxis[iTime], longitude=axis[iVal], latitude=slice(*self.index_interval[1]), order ='zy' )                  
#                elif  (iAxis == 1) or ( (iAxis == 3) and (self.currentGridAxis == 1) ):   
#                    if hasDataCube:     dataslice = dataCube[ :, iVal-self.index_interval[1][0], : ]
#                    else:               dataslice = self.var( time=taxis[iTime], latitude=axis[iVal], longitude=slice(*self.index_interval[0]), order ='zx'  )                 
#                elif  (iAxis == 2) or ( (iAxis == 3) and (self.currentGridAxis == 2) ):   
#                    if hasDataCube:     dataslice = dataCube[ iVal, :, : ]
#                    else:               dataslice = self.var( time=taxis[iTime], level=axis[iVal], latitude=slice(*self.index_interval[1]), longitude=slice(*self.index_interval[0]), order ='yx'  ) 
#            except cdms2.error.CDMSError, err:
#                print>>sys.stderr, "Error getting slice[%d]: %s " % ( iAxis, str(err) )
#                return None
#        except Exception, err:
#            traceback.print_exc()
#            pass
#        
#        self.currentSlice = iVal
#        imageOutput =  dataslice.squeeze()              
#        return imageOutput
    
if __name__ == "__main__":
    
    dset_path = "/Developer/Data/AConaty/comp-ECMWF/ac-comp1-geos5.xml"
    varname = "uwnd"
    
    ds = DataSlicer( dset_path, varname )
    
    
    s = ds.getSlice( 2, 0.5, 50.0 )
    ptOutput = ds.getPoint( lat=-2.2, lon=100.0 )
    print str( s.shape ), str( ptOutput )
    
    print "Done!"
    pass
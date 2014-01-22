'''
Created on Jan 15, 2014

@author: tpmaxwel
'''

#from PyQt4 import QtCore, QtGui
import vtk, sys, traceback, copy, collections
from Utilities import getItem, getFullPath, isLevelAxis, getVarNDim, newList, getMaxScalarValue, getDatatypeString, getNewVtkDataArray, encodeToString, getStringDataArray 
import numpy as np
#import numpy.ma as ma
# from vtk.util.misc import vtkGetDataRoot
# packagePath = os.path.dirname( __file__ ) 
import cdms2, cdtime, cdutil, MV2 
DataSetVersion = 0
DefaultDecimation = [ 0, 7 ]
cdms2.axis.level_aliases.append('isobaric')
DefaultReferenceTimeUnits = "days since 1900-1-1"

class OutputRecManager:   
            
    def __init__( self ): 
        self.outputRecs = {}
            
    def deleteOutput( self, dsid, outputName ):
        orecMap =  self.outputRecs.get( dsid, None )
        if orecMap: del orecMap[outputName] 

    def addOutputRec( self, dsid, orec ): 
        orecMap =  self.outputRecs.setdefault( dsid, {} )
        orecMap[ orec.name ] = orec

    def getOutputRec( self, dsid, outputName ):
        orecMap =  self.outputRecs.get( dsid, None )
        return orecMap[ outputName ] if orecMap else None

    def getOutputRecNames( self, dsid  ): 
        orecMap =  self.outputRecs.get( dsid, None )
        return orecMap.keys() if orecMap else []

    def getOutputRecs( self, dsid ):
        orecMap =  self.outputRecs.get( dsid, None )
        return orecMap.values() if orecMap else []
          
         
class OutputRec:
    
    def __init__(self, name, **args ): 
        self.name = name
        self.varComboList = args.get( "varComboList", [] )
        self.levelsCombo = args.get( "levelsCombo", None )
        self.level = args.get( "level", None )
        self.varTable = args.get( "varTable", None )
        self.varList = args.get( "varList", None )
        self.varSelections = args.get( "varSelections", [] )
        self.type = args.get( "type", None )
        self.ndim = args.get( "ndim", 3 )
        self.updateSelections() 

    def getVarList(self):
        vlist = []
        for vrec in self.varList:
            vlist.append( str( getItem( vrec ) ) )
        return vlist
    
    def getSelectedVariableList(self):
        return [ str( varCombo.currentText() ) for varCombo in self.varComboList ]

    def getSelectedLevel(self):
        return str( self.levelsCombo.currentText() ) if self.levelsCombo else None
    
    def updateSelections(self):
        self.varSelections = []
        for varCombo in self.varComboList:
            varSelection = str( varCombo.currentText() ) 
            self.varSelections.append( [ varSelection, "" ] )


class CDMSDataType:
    Volume = 1
    Slice = 2
    Vector = 3
    Hoffmuller = 4 
    ChartData = 5
    VariableSpace = 6
    Points = 7
    
    @classmethod
    def getName( cls, dtype ):
        if dtype == cls.Volume: return "volume"
        if dtype == cls.Points: return "points"
        if dtype == cls.Vector: return "vector"

def getTitle( dsid, name, attributes, showUnits=False ):
    long_name = attributes.get( 'long_name', attributes.get( 'standard_name', name ) )
    if not showUnits: return "%s:%s" % ( dsid, long_name )
    units = attributes.get( 'units', 'unitless' )
    return  "%s:%s (%s)" % ( dsid, long_name, units )

class DataCache():
    
    def __init__(self):
        self.data = {}
        self.cells = set()

class CachedImageData():
    
    def __init__(self, image_data, cell_coords ):
        self.data = image_data
        self.cells = set()
        self.cells.add( cell_coords )

def getRoiSize( roi ):
    if roi == None: return 0
    return abs((roi[2]-roi[0])*(roi[3]-roi[1]))
   
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

class AxisType:
    NONE = 0
    Time = 1
    Longitude = 2
    Latitude = 3
    Level = 4
    lev_aliases = [ 'bottom', 'top', 'zdim' ]
    lev_axis_attr = [ 'z' ]
    lat_aliases = [ 'north', 'south', 'ydim' ]
    lat_axis_attr = [ 'y' ]
    lon_aliases = [ 'east', 'west', 'xdim' ]
    lon_axis_attr = [ 'x' ]

def getAxisType( axis ):
    if axis.isLevel() or matchesAxisType( axis, AxisType.lev_axis_attr, AxisType.lev_aliases ):
        return AxisType.Level      
    elif axis.isLatitude() or matchesAxisType( axis, AxisType.lat_axis_attr, AxisType.lat_aliases ):
        return AxisType.Latitude                   
    elif axis.isLongitude() or matchesAxisType( axis, AxisType.lon_axis_attr, AxisType.lon_aliases ):
        return AxisType.Longitude     
    elif axis.isTime():
        return AxisType.Time
    else: return  AxisType.NONE    

def designateAxisType( self, axis ):
    if not isDesignated( axis ):
        if matchesAxisType( axis, AxisType.lev_axis_attr, AxisType.lev_aliases ):
            axis.designateLevel() 
            return AxisType.Level         
        elif matchesAxisType( axis, AxisType.lat_axis_attr, AxisType.lat_aliases ):
            axis.designateLatitude() 
            return AxisType.Latitude                    
        elif matchesAxisType( axis, AxisType.lon_axis_attr, AxisType.lon_aliases ):
            axis.designateLongitude()
            return AxisType.Longitude    
    return getAxisType( axis )

def freeImageData( image_data ):
    pointData = image_data.GetPointData()
    for aIndex in range( pointData.GetNumberOfArrays() ):
#       array = pointData.GetArray( aIndex )
        pointData.RemoveArray( aIndex )
#        if array:
#            name = pointData.GetArrayName(aIndex)            
#            print "---- freeImageData-> Removing array %s: %s" % ( name, array.__class__.__name__ )  
    fieldData = image_data.GetFieldData()
    for aIndex in range( fieldData.GetNumberOfArrays() ): 
        aname = fieldData.GetArrayName(aIndex)
        array = fieldData.GetArray( aname )
        if array:
            array.Initialize()
            fieldData.RemoveArray( aname )
    image_data.ReleaseData()

class CDMSDatasetRecord(): 
   
    def __init__( self, ds_id, dataset=None, dataFile = None ):
        self.id = ds_id
        self.lev = None
        self.dataset = dataset
        self.cdmsFile = dataFile
#        self.cachedFileVariables = {} 

    def getTimeValues( self, dsid ):
        return self.dataset['time'].getValue() 
    
    def getVariable(self, varName ):
        return self.dataset[ varName ] 
    
#    def clearDataCache( self ):
#         self.cachedFileVariables = {} 
    
    def getLevAxis(self ):
        for axis in self.dataset.axes.values():
            if isLevelAxis( axis ): return axis
        return None

    def getLevBounds( self, levaxis ):
        levbounds = None
        if levaxis:
            values = levaxis.getValue()
            ascending_values = ( values[-1] > values[0] )
            if levaxis:
                if   levaxis.attributes.get( 'positive', '' ) == 'down' and ascending_values:   levbounds = slice( None, None, -1 )
                elif levaxis.attributes.get( 'positive', '' ) == 'up' and not ascending_values: levbounds = slice( None, None, -1 )
        return levbounds
    
    def getVarDataTimeSlice( self, varName, timeValue, gridBounds, decimation, referenceVar=None, referenceLev=None ):
        """
        This method extracts a CDMS variable object (varName) and then cuts out a data slice with the correct axis ordering (returning a NumPy masked array).
        """        
#        cachedFileVariableRec = self.cachedFileVariables.get( varName )
#        if cachedFileVariableRec:
#            cachedTimeVal = cachedFileVariableRec[ 0 ]
#            if cachedTimeVal.value == timeValue.value:
#                return cachedFileVariableRec[ 1 ]
        
        rv = CDMSDataset.NullVariable
        varData = self.dataset[ varName ] 
#        print "Reading Variable %s, attributes: %s" % ( varName, str(varData.attributes) )

        refFile = self.cdmsFile
        refVar = varName
        refGrid = None
        if referenceVar:
            referenceData = referenceVar.split('*')
#            refDsid = referenceData[0]
            refFileRelPath = referenceData[1]
            refVar  = referenceData[2]
            try:
                refFile = getFullPath( refFileRelPath )
                f=cdms2.open( refFile )
                refGrid=f[refVar].getGrid()
            except cdms2.error.CDMSError, err:
                print>>sys.stderr, " --- Error[1] opening dataset file %s: %s " % ( refFile, str( err ) )
        if not refGrid: refGrid = varData.getGrid()
        if not refGrid: 
            print>>sys.stderr, "DV3D Error", "CDAT is unable to create a grid for this dataset."  
            return None
        refLat=refGrid.getLatitude()
        refLon=refGrid.getLongitude()
        nRefLat, nRefLon = len(refLat) - 1, len(refLon) - 1
        LatMin, LatMax =  float(refLat[0]), float(refLat[-1]) 
        LonMin, LonMax =  float(refLon[0]), float(refLon[-1]) 
        if LatMin > LatMax:
            tmpLatMin = LatMin
            LatMin = LatMax
            LatMax = tmpLatMin
        
        args1 = {} 
        gridMaker = None
        decimationFactor = 1
#        try:
        args1['time'] = timeValue
        if gridBounds[0] < LonMin and gridBounds[0]+360.0<LonMax: gridBounds[0] = gridBounds[0] + 360.0
        if gridBounds[2] < LonMin and gridBounds[2]+360.0<LonMax: gridBounds[2] = gridBounds[2] + 360.0
        if gridBounds[0] > LonMax and gridBounds[0]-360.0>LonMin: gridBounds[0] = gridBounds[0] - 360.0
        if gridBounds[2] > LonMax and gridBounds[2]-360.0>LonMin: gridBounds[2] = gridBounds[2] - 360.0
        if decimationFactor == 1:
            args1['lon'] = ( gridBounds[0], gridBounds[2] )
            args1['lat'] = ( gridBounds[1], gridBounds[3] )
        else:
            varGrid = varData.getGrid() 
            if varGrid: 
                varLonInt = varGrid.getLongitude().mapIntervalExt( [ gridBounds[0], gridBounds[2] ] )
                latAxis = varGrid.getLatitude()
                latVals = latAxis.getValue()
                latBounds =  [ gridBounds[3], gridBounds[1] ] if latVals[0] > latVals[1] else  [ gridBounds[1], gridBounds[3] ]            
                varLatInt = latAxis.mapIntervalExt( latBounds )
                args1['lon'] = slice( varLonInt[0], varLonInt[1], decimationFactor )
                args1['lat'] = slice( varLatInt[0], varLatInt[1], decimationFactor )
                print " ---- Decimate(%d) grid %s: varLonInt=%s, varLatInt=%s, lonSlice=%s, latSlice=%s" % ( decimationFactor, str(gridBounds), str(varLonInt), str(varLatInt), str(args1['lon']), str(args1['lat']) )
#        args1['squeeze'] = 1
#        start_t = time.time() 
            
#        if (gridMaker == None) or ( gridMaker.grid == varData.getGrid() ):
                   
        if ( (referenceVar==None) or ( ( referenceVar[0] == self.cdmsFile ) and ( referenceVar[1] == varName ) ) ) and ( decimationFactor == 1):
            levbounds = self.getLevBounds( referenceLev )
            if levbounds: args1['lev'] = levbounds
            args1['order'] = 'xyz'
            rv = varData( **args1 )
        else:
            refDelLat = ( LatMax - LatMin ) / nRefLat
            refDelLon = ( LonMax - LonMin ) / nRefLon
#            nodataMask = cdutil.WeightsMaker( source=self.cdmsFile, var=varName,  actions=[ MV2.not_equal ], values=[ nodata_value ] ) if nodata_value else None
            gridMaker = cdutil.WeightedGridMaker( flat=LatMin, flon=LonMin, nlat=int(nRefLat/decimationFactor), nlon=int(nRefLon/decimationFactor), dellat=(refDelLat*decimationFactor), dellon=(refDelLon*decimationFactor) ) # weightsMaker=nodataMask  )                    
            
            vc = cdutil.VariableConditioner( source=self.cdmsFile, var=varName,  cdmsKeywords=args1, weightedGridMaker=gridMaker ) 
            regridded_var_slice = vc.get( returnTuple=0 )
            if referenceLev: regridded_var_slice = regridded_var_slice.pressureRegrid( referenceLev )
            args2 = { 'order':'xyz', 'squeeze':1 }
            levbounds = self.getLevBounds( referenceLev )
            if levbounds: args2['lev'] = levbounds
            rv = regridded_var_slice( **args2 ) 
            try: rv = MV2.masked_equal( rv, rv.fill_value ) 
            except: pass
#            max_values = [ regridded_var_slice.max(), rv.max()  ]
#            print " Regrid variable %s: max values = %s " % ( varName, str(max_values) )
            
#            end_t = time.time() 
#            self.cachedFileVariables[ varName ] = ( timeValue, rv )
#            print  "Reading variable %s, shape = %s, base shape = %s, time = %s (%s), args = %s, slice duration = %.4f sec." % ( varName, str(rv.shape), str(varData.shape), str(timeValue), str(timeValue.tocomp()), str(args1), end_t-start_t  ) 
#        except Exception, err:
#            print>>sys.stderr, ' Exception getting var slice: %s ' % str( err )
        return rv

    def getFileVarDataCube( self, varName, decimation, **args ):
        """
        This method extracts a CDMS variable object (varName) and then cuts out a data slice with the correct axis ordering (returning a NumPy masked array).
        """ 
        lonBounds = args.get( 'lon', None )
        latBounds = args.get( 'lat', None )
        levBounds = args.get( 'lev', None )
        timeBounds = args.get( 'time', None )
        [ timeValue, timeIndex, useTimeIndex ] = timeBounds if timeBounds else [ None, None, None ]
        referenceVar = args.get( 'refVar', None )
        referenceLev = args.get( 'refLev', None )

#        nSliceDims = 0
#        for bounds in (lonBounds, latBounds, levBounds, timeBounds):
#            if ( bounds <> None ) and ( len(bounds) == 1 ):  
#               nSliceDims = nSliceDims + 1
#        if nSliceDims <> 1:
#            print "Error, Wrong number of data dimensions:  %d slice dims " %  nSliceDims
#            return None
#        cachedFileVariableRec = self.cachedFileVariables.get( varName )
#        if cachedFileVariableRec:
#            cachedTimeVal = cachedFileVariableRec[ 0 ]
#            if cachedTimeVal.value == timeValue.value:
#                return cachedFileVariableRec[ 1 ]
        
        rv = CDMSDataset.NullVariable
        varData = self.dataset[ varName ] 
        currentLevel = varData.getLevel()
#        print "Reading Variable %s, attributes: %s" % ( varName, str(varData.attributes) )

#        refFile = self.cdmsFile
        refVar = varName
        refGrid = None
        if referenceVar:
            referenceData = referenceVar.split('*')
#            refDsid = referenceData[0]
            relFilePath = referenceData[1]
            refVar  = referenceData[2]
            try:
                cdmsFile = getFullPath( relFilePath )
                f=cdms2.open( cdmsFile )
                refGrid=f[refVar].getGrid()
            except cdms2.error.CDMSError, err:
                print>>sys.stderr, " --- Error[2] opening dataset file %s: %s " % ( cdmsFile, str( err ) )
        if not refGrid: refGrid = varData.getGrid()
        if not refGrid: 
            print>>sys.stderr, "DV3D Error", "CDAT is unable to create a grid for this dataset."
            return None
        refLat=refGrid.getLatitude()
        refLon=refGrid.getLongitude()
        nRefLat, nRefLon = len(refLat) - 1, len(refLon) - 1
        LatMin, LatMax =  float(refLat[0]), float(refLat[-1]) 
        LonMin, LonMax =  float(refLon[0]), float(refLon[-1]) 
        if LatMin > LatMax:
            tmpLatMin = LatMin
            LatMin = LatMax
            LatMax = tmpLatMin
        
        args1 = {} 
        gridMaker = None
        decimationFactor = 1
        order = 'xyt' if ( timeBounds == None) else 'xyz'
        try:
            nts = self.dataset['time'].shape[0]
            if ( timeIndex <> None ) and  useTimeIndex: 
                args1['time'] = slice( timeIndex, timeIndex+1, 1 )
            elif timeValue and (nts>1): 
                args1['time'] = timeValue
        except: pass
        
        if lonBounds <> None:
            if (lonBounds[1] - lonBounds[0]) < 355.0:
                if lonBounds[0] < LonMin: lonBounds[0] = LonMin
                if lonBounds[1] > LonMax: lonBounds[1] = LonMax
#            if lonBounds[0] < LonMin and lonBounds[0]+360.0 < LonMax: lonBounds[0] = lonBounds[0] + 360.0
#            if lonBounds[0] > LonMax and lonBounds[0]-360.0 > LonMin: lonBounds[0] = lonBounds[0] - 360.0
#            if len( lonBounds ) > 1:
#                if lonBounds[1] < LonMin and lonBounds[1]+360.0<LonMax: lonBounds[1] = lonBounds[1] + 360.0
#                if lonBounds[1] > LonMax and lonBounds[1]-360.0>LonMin: lonBounds[1] = lonBounds[1] - 360.0                       
            if (decimationFactor == 1) or len( lonBounds ) == 1:
                args1['lon'] = lonBounds[0] if ( len( lonBounds ) == 1 ) else lonBounds
            else:
                varGrid = varData.getGrid() 
                varLonInt = varGrid.getLongitude().mapIntervalExt( [ lonBounds[0], lonBounds[1] ] )
                args1['lon'] = slice( varLonInt[0], varLonInt[1], decimationFactor )
               
        if latBounds <> None:
            if decimationFactor == 1:
                args1['lat'] = latBounds[0] if ( len( latBounds ) == 1 ) else latBounds
            else:
                latAxis = varGrid.getLatitude()
                latVals = latAxis.getValue()
                latBounds =  [ latBounds[1], latBounds[0] ] if latVals[0] > latVals[1] else  [ latBounds[0], latBounds[1] ]            
                varLatInt = latAxis.mapIntervalExt( latBounds )
                args1['lat'] = slice( varLatInt[0], varLatInt[1], decimationFactor )
                
#        start_t = time.time() 
        
        if ( (referenceVar==None) or ( ( referenceVar[0] == self.cdmsFile ) and ( referenceVar[1] == varName ) ) ) and ( decimationFactor == 1):
            if levBounds <> None:
                args1['lev'] =  levBounds[0] if ( len( levBounds ) == 1 ) else levBounds                        
            else:
                levBounds = self.getLevBounds( referenceLev )
                if levBounds: args1['lev'] = levBounds
            args1['order'] = order
            rv = varData( **args1 )
        else:
            refDelLat = ( LatMax - LatMin ) / nRefLat
            refDelLon = ( LonMax - LonMin ) / nRefLon
#            nodataMask = cdutil.WeightsMaker( source=self.cdmsFile, var=varName,  actions=[ MV2.not_equal ], values=[ nodata_value ] ) if nodata_value else None
            gridMaker = cdutil.WeightedGridMaker( flat=LatMin, flon=LonMin, nlat=int(nRefLat/decimationFactor), nlon=int(nRefLon/decimationFactor), dellat=(refDelLat*decimationFactor), dellon=(refDelLon*decimationFactor) ) # weightsMaker=nodataMask  )                    
                
#            from packages.vtDV3D.CDMS_DatasetReaders import getRelativeTimeValues 
#            time_values, dt, time_units = getRelativeTimeValues ( cdms2.open( self.cdmsFile ) ) 
            
            vc = cdutil.VariableConditioner( source=self.cdmsFile, var=varName,  cdmsKeywords=args1, weightedGridMaker=gridMaker ) 
            print " regridded_var_slice(%s:%s): %s " % ( self.dataset.id, varName, str( args1 ) )
            regridded_var_slice = vc.get( returnTuple=0 )
#            if (referenceLev <> None) and ( referenceLev.shape[0] <> currentLevel.shape[0] ): 
#                regridded_var_slice = regridded_var_slice.pressureRegrid( referenceLev ) 
            
            args2 = { 'order' : order, 'squeeze' : 1 }
            if levBounds <> None:
                args2['lev'] = levBounds[0] if ( len( levBounds ) == 1 ) else levBounds                            
            else:
                levBounds = self.getLevBounds( currentLevel )
                if levBounds: args2['lev'] = levBounds
            rv = regridded_var_slice( **args2 ) 
            try: rv = MV2.masked_equal( rv, rv.fill_value )
            except: pass
#            max_values = [ regridded_var_slice.max(), rv.max()  ]
#            print " Regrid variable %s: max values = %s " % ( varName, str(max_values) )
            
#           end_t = time.time() 
#            self.cachedFileVariables[ varName ] = ( timeValue, rv )
            print  "Reading variable %s, shape = %s, base shape = %s, args = %s" % ( varName, str(rv.shape), str(varData.shape), str(args1) ) 
#        except Exception, err:
#            print>>sys.stderr, ' Exception getting var slice: %s ' % str( err )
        return rv

class CDMSDataset: 
    
    NullVariable = cdms2.createVariable( np.array([]), id='NULL' )

    def __init__( self ):
        self.datasetRecs = collections.OrderedDict()
        self.variableRecs = collections.OrderedDict()
        self.transientVariables = collections.OrderedDict()
#        self.cachedTransVariables = {}
        self.outputVariables = collections.OrderedDict()
        self.referenceVariable = None
        self.timeRange = None
        self.referenceTimeUnits = None
        self.gridBounds = None
        self.decimation = DefaultDecimation
        self.zscale = 1.0
        self.cells = []
        self.latLonGrid = True
        
    def setCells( self, cells ):
        self.cells[:] = cells[:]
      
    def setVariableRecord( self, dsid, varName ):
        self.variableRecs[dsid] = varName

    def getVariableRecord( self, dsid ):
        return self.variableRecs[dsid] 

    def getVarRecValues( self ):
        return self.variableRecs.values() 

    def getVarRecKeys( self ):
        return self.variableRecs.keys() 

    def setRoi( self, roi ): 
        if roi <> None: 
            self.gridBounds = list(roi)

    def setBounds( self, timeRange, time_units, roi, zscale, decimation ): 
        self.timeRange = timeRange
        self.referenceTimeUnits = time_units
        self.setRoi( roi )
        self.zscale = zscale
        self.decimation = decimation
        
    def getTimeValues( self, asComp = True ):
        if self.timeRange == None: return None
        start_rel_time = cdtime.reltime( float( self.timeRange[2] ), self.referenceTimeUnits )
        time_values = []
        for iTime in range( self.timeRange[0], self.timeRange[1]+1 ):
            rval = start_rel_time.value + iTime * self.timeRange[3]
            tval = cdtime.reltime( float( rval ), self.referenceTimeUnits )
            if asComp:   time_values.append( tval.tocomp() )
            else:        time_values.append( tval )
        return time_values
    
    def getGrid( self, gridData ):
        dsetRec = self.datasetRecs.get( gridData[0], None )
        if dsetRec:
            grids = dsetRec.dataset.grids
            return grids.get( gridData[1], None  )
        return None

    def setReferenceVariable( self, selected_grid_id ):
        try:
            if (selected_grid_id == None) or (selected_grid_id == 'None'): return
            grid_id = getItem( selected_grid_id )
            refVarData = grid_id.split('*')
            if len( refVarData ) > 1:
                dsid = refVarData[0]
                varName = refVarData[1].split('(')[0].strip()
                dsetRec = self.datasetRecs.get( dsid, None )
                if dsetRec:
                    variable = dsetRec.dataset.variables.get( varName, None )
                    if variable: 
                        self.referenceVariable = "*".join( [ dsid, dsetRec.cdmsFile, varName ] )
                        self.referenceLev = variable.getLevel()
        except Exception, err:
            print>>sys.stderr, " Error in setReferenceVariable: ", str(err)
            
    def getReferenceDsetId(self):
        if self.referenceVariable == None: return self.datasetRecs.keys()[0]
        return self.referenceVariable.split("*")[0]
                                                             
    def getStartTime(self):
        return cdtime.reltime( float( self.timeRange[2] ), self.referenceTimeUnits )

    def close( self ):
        for dsetRec in self.datasetRecs.values(): dsetRec.dataset.close()
         
    def addTransientVariable( self, varName, variable, ndim = None ):
        if varName in self.transientVariables:
            var = self.transientVariables[ varName ]
            if id(var) <> id(variable): print>>sys.stderr, "Warning, transient variable %s already exists in dataset, overwriting!" % ( varName )
            else: return
        self.transientVariables[ varName ] = variable

    def getTransientVariable( self, varName ):
        return self.transientVariables.get( varName, None )

    def getTransientVariableNames( self ):
        return self.transientVariables.keys()

    def addOutputVariable( self, varName, variable, ndim = None ):
        self.outputVariables[ varName ] = variable

    def getOutputVariable( self, varName ):
        return self.outputVariables.get( varName, None )

    def getOutputVariableNames( self ):
        return self.outputVariables.keys()

    def __getitem__(self, dsid ):
        return self.datasetRecs.get( dsid, None )

    def __delitem__(self, dsid ):
        dsetRec = self.datasetRecs[ dsid ]
        dsetRec.dataset.close()
        del self.datasetRecs[ dsid ]
    
#    def getVarData( self, dsid, varName ):
#        dsetRec = self.datasetRecs[ dsid ]
#        if varName in dsetRec.dataset.variables:
#            return dsetRec.getVarData( self, varName )
#        elif varName in self.transientVariables:
#            return self.transientVariables[ varName ]
#        else: 
#            print>>sys.stderr, "Error: can't find variable %s in dataset" % varName
#            return self.NullVariable

    def clearDataCache( self ):
        for dsetRec in self.datasetRecs.values(): dsetRec.clearDataCache()
        
#    def clearVariableCache( self, varName ):
#        cachedData = self.cachedTransVariables.get( varName, None )
#        if cachedData:
#            ( timeValue, tvar ) = cachedData
#            del self.cachedTransVariables[ varName]
#            del tvar

    def clearTransientVariable( self, varName ):
        try:
            tvar = self.transientVariables[ varName ]
            del self.transientVariables[ varName]
            del tvar
        except Exception, err:
            print>>sys.stderr, "Error releasing tvar: ", str(err)

    def getVarDataTimeSlice( self, dsid, varName, timeValue ):
        """
        This method extracts a CDMS variable object (varName) and then cuts out a data slice with the correct axis ordering (returning a NumPy masked array).
        """
        rv = CDMSDataset.NullVariable
        if dsid:
            dsetRec = self.datasetRecs[ dsid ]
            if varName in dsetRec.dataset.variables:
                rv = dsetRec.getVarDataTimeSlice( varName, timeValue, self.gridBounds, self.decimation, self.referenceVariable, self.referenceLev )   
        if (rv.id == "NULL") and (varName in self.transientVariables):
            rv = self.transientVariables[ varName ]
        if rv.id <> "NULL": 
            return rv 
#            current_grid = rv.getGrid()
#            if ( gridMaker == None ) or SameGrid( current_grid, gridMaker.grid ): return rv
#            else:       
#                vc = cdutil.VariableConditioner( source=rv, weightedGridMaker=gridMaker )
#                return vc.get( returnTuple=0 )
        print>>sys.stderr, "Error: can't find time slice variable %s in dataset" % varName
        return rv

    def getVarDataCube( self, dsid, varName, timeValues, levelValues = None, **kwargs ):
        """
        This method extracts a CDMS variable object (varName) and then cuts out a data slice with the correct axis ordering (returning a NumPy masked array).
        """
        rv = CDMSDataset.NullVariable
        if dsid:
            dsetRec = self.datasetRecs.get( dsid, None )
            if dsetRec:
                if varName in dsetRec.dataset.variables:
                    args = { 'time':timeValues, 'lev':levelValues, 'refVar':self.referenceVariable, 'refLev':self.referenceLev }
                    for item in kwargs.iteritems(): args[ item[0] ] = item[1]
                    if self.gridBounds:
                        args['lon'] = [self.gridBounds[0],self.gridBounds[2]] 
                        args['lat'] = [self.gridBounds[1],self.gridBounds[3]] 
                    rv = dsetRec.getFileVarDataCube( varName, self.decimation, **args )  
            elif varName in self.getTransientVariableNames():
                tvar = self.getTransientVariable( varName ) 
                args = { 'time':timeValues, 'lev':levelValues }
                for item in kwargs.iteritems(): args[ item[0] ] = item[1]
                if self.gridBounds:
                    args['lon'] = [self.gridBounds[0],self.gridBounds[2]] 
                    args['lat'] = [self.gridBounds[1],self.gridBounds[3]] 
                rv = self.getTransVarDataCube( varName, tvar, self.decimation, **args )  
        if (rv.id == "NULL") and (varName in self.outputVariables):
            rv = self.outputVariables[ varName ]
        if rv.id == "NULL": 
            print>>sys.stderr, "Error: can't find time slice data cube for variable %s in dataset" % varName
        return rv


    def getTransVarDataCube( self, varName, transVar, decimation, **args ):
        """
        This method returns a data slice with the correct axis ordering (returning a NumPy masked array).
        """ 
        invert_z = False
        invert_y = False
        levaxis = transVar.getLevel() 
#        timeaxis = transVar.getTime() 
        level = args.get( 'lev', None )
        lonBounds = args.get( 'lon', None )
        latBounds = args.get( 'lat', None )
#        cell_coords = args.get( 'cell', None )

        if levaxis:
            values = levaxis.getValue()
            ascending_values = ( values[-1] > values[0] )
            invert_z = ( (levaxis.attributes.get( 'positive', '' ) == 'down') and ascending_values ) or ( (levaxis.attributes.get( 'positive', '' ) == 'up') and not ascending_values )
               
        timeBounds = args.get( 'time', None )
        [ timeValue, timeIndex, useTimeIndex ] = timeBounds if timeBounds else [ None, None, None ]

#        cachedTransVariableRec = self.cachedTransVariables.get( varName )
#        if cachedTransVariableRec:
#            cachedTimeVal = cachedTransVariableRec[ 0 ]
#            if cachedTimeVal.value == timeValue.value:
#                print>>sys.stderr, "Returning cached trans var %s" % varName
#                return cachedTransVariableRec[ 1 ]
        
        rv = CDMSDataset.NullVariable 
#        currentLevel = transVar.getLevel()
#        print "Reading Variable %s, attributes: %s" % ( varName, str(transVar.attributes) )

        decimationFactor = 1        
        args1 = {} 
        order = 'xyt' if ( timeBounds == None) else 'xyz' if levaxis else 'xy'
        try:
            nts = self.timeRange[1]
            if ( timeIndex <> None ) and  useTimeIndex: 
                args1['time'] = slice( timeIndex, timeIndex+1 )
            elif timeValue and (nts>1): 
                args1['time'] = timeValue
        except: pass

        if (decimationFactor > 1) or lonBounds or latBounds:
            lonAxis = transVar.getLongitude() 
            lonVals = lonBounds if lonBounds else lonAxis.getValue()
            varLonInt = lonAxis.mapIntervalExt( [ lonVals[0], lonVals[-1] ], 'ccn' )
            if varLonInt:
                if (decimationFactor > 1):  args1['lon'] = slice( varLonInt[0], varLonInt[1], decimationFactor )
                else:                       args1['lon'] = slice( varLonInt[0], varLonInt[1] )
           
            latAxis = transVar.getLatitude() 
            latVals = latAxis.getValue()
            latRange = [ latVals[0], latVals[-1] ]
            if latBounds:
                if ( latVals[-1] > latVals[0] ):     
                    latRange = [ latBounds[0], latBounds[-1] ] if (latBounds[-1] > latBounds[0]) else [ latBounds[-1], latBounds[0] ]
                else:                                
                    latRange = [ latBounds[0], latBounds[-1] ] if (latBounds[-1] < latBounds[0]) else [ latBounds[-1], latBounds[0] ]
                    invert_y = True
            varLatInt = latAxis.mapIntervalExt( latRange, 'ccn' )
            if varLatInt:
                if invert_y:    args1['lat'] = slice( varLatInt[1], varLatInt[0], -decimationFactor )
                else:           args1['lat'] = slice( varLatInt[0], varLatInt[1], decimationFactor )   
                     
        args1['order'] = order
        if levaxis:
            if level: args1['lev'] = float( level )
            elif invert_z:  args1['lev'] = slice( None, None, -1 )
        
        try:
            rv = transVar( **args1 )
        except Exception, err: 
            print>>sys.stderr, "Error Reading Variable: ", str(err) 
            return CDMSDataset.NullVariable
      
        try: 
            rv = MV2.masked_equal( rv, rv.fill_value )
        except: 
            pass         
#       self.cachedTransVariables[ varName ] = ( timeValue, rvm )
        print  "Reading variable %s, shape = %s, base shape = %s, args = %s" % ( varName, str(rv.shape), str(transVar.shape), str(args1) ) 
        return rv
    
    def ensure3D( self, cdms_variable ):
        lev = cdms_variable.getLevel()
        if lev == None:
            axis_list = cdms_variable.getAxisList()
            axis = cdms2.createAxis( [0.0] )
            axis.designateLevel()
            axis_list.append( axis )
            new_shape = list( cdms_variable.data.shape )
            new_shape.append(1)
            cdms_variable.data.reshape( new_shape )
            cdms_variable.setAxisList( axis_list )

    def getVarDataTimeSlices( self, varList, timeValue ):
        """
        This method extracts a CDMS variable object (varName) and then cuts out a data slice with the correct axis ordering (returning a NumPy masked array).
        """
        timeSlices, condTimeSlices = [], []
        vc0 = None
        for ( dsid, varName ) in varList:
            varTimeSlice = self.getVarDataTimeSlice( dsid, varName, timeValue )
            if not vc0: vc0 = cdutil.VariableConditioner( varTimeSlice )    
            else:       timeSlices.append( varTimeSlice )                
        for varTimeSlice in timeSlices:
            vc1 = cdutil.VariableConditioner( varTimeSlice ) 
            VM = cdutil.VariablesMatcher( vc0, vc1 )
            condTimeSlice0, condTimeSlice1 = VM.get( returnTuple=0 )
            if not condTimeSlices: condTimeSlices.append( condTimeSlice0 )
            condTimeSlices.append( condTimeSlice1 )
        return condTimeSlices
    
    def addDatasetRecord( self, dsetId, relFilePath ):
        cdmsDSet = self.datasetRecs.get( dsetId, None )
        if (cdmsDSet <> None) and (cdmsDSet.cdmsFile == relFilePath):
            return cdmsDSet
        try:
            relFilePath = relFilePath.strip()
            if relFilePath:
                cdmsFile = getFullPath( relFilePath )
                dataset = cdms2.open( cdmsFile ) 
                cdmsDSet = CDMSDatasetRecord( dsetId, dataset, cdmsFile )  
                self.datasetRecs[ dsetId ] = cdmsDSet
        except Exception, err:
            print>>sys.stderr, " --- Error[3] opening dataset file %s: %s " % ( cdmsFile, str( err ) )
        return cdmsDSet             

    def getVariableList( self, ndims ):
        vars_list = []     
        for dsetRec in self.datasetRecs.values(): 
            for var in dsetRec.dataset.variables:               
                vardata = dsetRec.dataset[var]
                var_ndim = getVarNDim( vardata )
                if var_ndim == ndims: vars_list.append( '%s*%s' % ( dsetRec.id, var ) )
        return vars_list
    
    def getDsetId(self): 
        rv = '-'.join( self.datasetRecs.keys() )
        return rv   
    
                
class ImageDataReader:

    dataCache = {}
    imageDataCache = {}
    
    def __init__(self, rank, **args ):  
        self.referenceTimeUnits = DefaultReferenceTimeUnits
        self.rank = rank
        self.datasetId = None
        self.fileSpecs = None
        self.varSpecs = None
        self.gridSpecs = None
        self.currentTime = 0
        self.currentLevel = None
        self.timeIndex = 0
        self.timeValue = None
        self.useTimeIndex = False
        self.timeAxis = None
        self.outputType = CDMSDataType.Volume
        self.result = {}
            
    def getTimeAxis(self):
        return self.timeAxis
       
    def getCachedImageData( self, data_id, cell_coords ):
        image_data = self.imageDataCache.get( data_id, None )
        if image_data: 
            image_data.cells.add( cell_coords )
            return image_data.data
        return None

    def setCachedImageData( self, data_id, cell_coords, image_data ):
        self.imageDataCache[data_id] = CachedImageData( image_data, cell_coords )

    @classmethod
    def clearCache( cls, cell_coords ):
        for dataCacheItems in cls.dataCache.items():
            dataCacheKey = dataCacheItems[0]
            dataCacheObj = dataCacheItems[1]
            if cell_coords in dataCacheObj.cells:
                dataCacheObj.cells.remove( cell_coords )
                if len( dataCacheObj.cells ) == 0:
                    varDataMap = dataCacheObj.data.get('varData', None )
                    if varDataMap:
                        newDataArray = varDataMap.get( 'newDataArray', None  )
                        try:
                            varDataMap['newDataArray' ] = None
                            del newDataArray
                        except Exception, err:
                            print>>sys.stderr, "Error releasing variable data: ", str(err)
                    dataCacheObj.data['varData'] = None
                    del cls.dataCache[ dataCacheKey ]
                    print "Removing Cached data: ", str( dataCacheKey )
        for imageDataItem in cls.imageDataCache.items():
            imageDataCacheKey = imageDataItem[0]
            imageDataCacheObj = imageDataItem[1]
            if cell_coords in imageDataCacheObj.cells:
                imageDataCacheObj.cells.remove( cell_coords )
                if len( imageDataCacheObj.cells ) == 0:
                    freeImageData( imageDataCacheObj.data )
                    imageDataCacheObj.data = None
                    print "Removing Cached image data: ", str( imageDataCacheKey )
        
    def getCachedData( self, varDataId, cell_coords ):
        dataCacheObj = self.dataCache.setdefault( varDataId, DataCache() )
        data = dataCacheObj.data.get( 'varData', None )
        if data: dataCacheObj.cells.add( cell_coords )
        return data

    def setCachedData(self, varDataId, cell_coords, varDataMap ):
        dataCacheObj = self.dataCache.setdefault( varDataId, DataCache() )
        dataCacheObj.data[ 'varData' ] = varDataMap
        dataCacheObj.cells.add( cell_coords )
                
    def getParameterDisplay( self, parmName, parmValue ):
        if parmName == 'timestep':
#            timestep = self.getTimeIndex( int( parmValue[0] ) )
            timestep = int( parmValue[0] )
            try:    return str( self.timeLabels[ timestep ] ), 10
            except: pass
        return None, 1

    def addCDMSVariable( self, cdms_var, index ):
        dsetId = "Computed"
        varname = cdms_var.name
        var = cdms_var.var
        if cdms_var.file : dsetId = cdms_var.file
        self.cdmsDataset.addTransientVariable( varname, var )
        self.cdmsDataset.setVariableRecord( "VariableName%d" % index, '*'.join( [ dsetId, varname ] ) )
        return var, dsetId
    
    def designateAxes(self,var):
        lev_aliases = [ 'bottom', 'top', 'zdim', 'level' ]
        lev_axis_attr = [ 'z' ]
        lat_aliases = [ 'north', 'south', 'ydim' ]
        lat_axis_attr = [ 'y' ]
        lon_aliases = [ 'east', 'west', 'xdim' ]
        lon_axis_attr = [ 'x' ]
        latLonGrid = True
        for axis in var.getAxisList():
            if not isDesignated( axis ):
                if matchesAxisType( axis, lev_axis_attr, lev_aliases ):
                    axis.designateLevel()
                    print " --> Designating axis %s as a Level axis " % axis.id            
                elif matchesAxisType( axis, lat_axis_attr, lat_aliases ):
                    axis.designateLatitude()
                    print " --> Designating axis %s as a Latitude axis " % axis.id 
                    latLonGrid = False                     
                elif matchesAxisType( axis, lon_axis_attr, lon_aliases ):
                    axis.designateLongitude()
                    print " --> Designating axis %s as a Longitude axis " % axis.id 
                    latLonGrid = False 
            elif ( axis.isLatitude() or axis.isLongitude() ):
                if ( axis.id.lower()[0] == 'x' ) or ( axis.id.lower()[0] == 'y' ):
                    latLonGrid = False 
        return latLonGrid

    def setupTimeAxis( self, var, **args ):
        self.nTimesteps = 1
        self.timeRange = [ 0, self.nTimesteps, 0.0, 0.0 ]
        self.timeAxis = var.getTime()
        if self.timeAxis:
            self.nTimesteps = len( self.timeAxis ) if self.timeAxis else 1
            try:
                comp_time_values = self.timeAxis.asComponentTime()
                t0 = comp_time_values[0].torel(self.referenceTimeUnits).value
                if (t0 < 0):
                    self.referenceTimeUnits = self.timeAxis.units
                    t0 = comp_time_values[0].torel(self.referenceTimeUnits).value
                dt = 0.0
                if self.nTimesteps > 1:
                    t1 = comp_time_values[-1].torel(self.referenceTimeUnits).value
                    dt = (t1-t0)/(self.nTimesteps-1)
                    self.timeRange = [ 0, self.nTimesteps, t0, dt ]
            except:
                values = self.timeAxis.getValue()
                t0 = values[0] if len(values) > 0 else 0
                t1 = values[-1] if len(values) > 1 else t0
                dt = ( values[1] - values[0] )/( len(values) - 1 ) if len(values) > 1 else 0
                self.timeRange = [ 0, self.nTimesteps, t0, dt ]
#        self.setParameter( "timeRange" , self.timeRange )
        self.cdmsDataset.timeRange = self.timeRange
        self.cdmsDataset.referenceTimeUnits = self.referenceTimeUnits
        self.timeLabels = self.cdmsDataset.getTimeValues()
        timeData = args.get( 'timeData', [ self.cdmsDataset.timeRange[2], 0, False ] )
        if timeData:
            self.timeValue = cdtime.reltime( float(timeData[0]), self.referenceTimeUnits )
            self.timeIndex = timeData[1]
            self.useTimeIndex = timeData[2]
        else:
            self.timeValue = cdtime.reltime( t0, self.referenceTimeUnits )
            self.timeIndex = 0
            self.useTimeIndex = False
#            print "Set Time [mid = %d]: %s, NTS: %d, Range: %s, Index: %d (use: %s)" % ( self.moduleID, str(self.timeValue), self.nTimesteps, str(self.timeRange), self.timeIndex, str(self.useTimeIndex) )
#            print "Time Step Labels: %s" % str( self.timeLabels )
           
    def execute(self, dset, **args ):
            self.cdmsDataset = dset
#                dsetid = self.getAnnotation( "datasetId" )
#                if dsetid: self.datasetId = dsetid 
            dsetId = self.cdmsDataset.getDsetId()
#                self.newDataset = ( self.datasetId <> dsetId )
            self.newLayerConfiguration = True # self.newDataset
            self.datasetId = dsetId
            self.timeRange = self.cdmsDataset.timeRange
            timeData = args.get( 'timeData', None )
            if timeData:
                self.timeValue = cdtime.reltime( float(timeData[0]), self.referenceTimeUnits )
                self.timeIndex = timeData[1]
                self.useTimeIndex = timeData[2]
                self.timeLabels = self.cdmsDataset.getTimeValues()
                self.nTimesteps = self.timeRange[1]
#                print "Set Time: %s, NTS: %d, Range: %s, Index: %d (use: %s)" % ( str(self.timeValue), self.nTimesteps, str(self.timeRange), self.timeIndex, str(self.useTimeIndex) )
#                print "Time Step Labels: %s" % str( self.timeLabels ) 
            self.generateOutput( **args )
#                if self.newDataset: self.addAnnotation( "datasetId", self.datasetId )
#        memoryLogger.log("finished CDMS_DataReader:execute")
 

    def generateOutput( self, **args ): 
        oRecMgr = None 
        varRecs = self.cdmsDataset.getVarRecValues()
        if len( varRecs ):
            oRecMgr = OutputRecManager() 
#            varCombo = QComboBox()
#            for var in varRecs: varCombo.addItem( str(var) ) 
#            otype = 'pointCloud' if ( self.outputType == CDMSDataType.Points ) else 'volume'
            otype = 'volume'
            orec = OutputRec( otype, ndim=3, varList=varRecs )   
            oRecMgr.addOutputRec( self.datasetId, orec ) 
        orecs = oRecMgr.getOutputRecs( self.datasetId ) if oRecMgr else None
        if not orecs: raise Exception( self, 'No Variable selected for dataset %s.' % self.datasetId )             
        for orec in orecs:
            cachedImageDataName = self.getImageData( orec, **args ) 
            if cachedImageDataName: 
                cachedImageData = self.getCachedImageData( cachedImageDataName, self.rank )            
                self.result[ orec.name ] = cachedImageData 
                print " --> ImageDataReader:  Read data ", cachedImageDataName  
        self.currentTime = self.getTimestep() 
                  
    def getParameterId(self):
        return self.datasetId
            

    def generateVariableOutput( self, cdms_var ): 
        print str(cdms_var.var)
        self.set3DOutput( name=cdms_var.name,  output=cdms_var.var )
        
     
    def getTimestep( self ):
        dt = self.timeRange[3]
        return 0 if dt <= 0.0 else int( round( ( self.timeValue.value - self.timeRange[2] ) / dt ) )

    def setCurrentLevel(self, level ): 
        self.currentLevel = level


#     def getFileMetadata( self, orec, **args ):
#         varList = orec.varList
#         if len( varList ) == 0: return False
#         varDataIds = []
#         intersectedRoi = args.get('roi', None )
#         url = args.get('url', None )
#         if intersectedRoi: self.cdmsDataset.setRoi( intersectedRoi )
#         dsid = None
#         vars = []
#         for varRec in varList:
#             range_min, range_max, scale, shift  = 0.0, 0.0, 1.0, 0.0   
#             imageDataName = getItem( varRec )
#             varNameComponents = imageDataName.split('*')
#             if len( varNameComponents ) == 1:
#                 dsid = self.cdmsDataset.getReferenceDsetId() 
#                 varName = varNameComponents[0]
#             else:
#                 dsid = varNameComponents[0]
#                 varName = varNameComponents[1]
#             ds = self.cdmsDataset[ dsid ]
#             if ds:
#                 var = ds.getVariable( varName )
#                 self.setupTimeAxis( var, **args )
#             portName = orec.name
#             selectedLevel = orec.getSelectedLevel() if ( self.currentLevel == None ) else self.currentLevel
#             ndim = 3 if ( orec.ndim == 4 ) else orec.ndim
#             default_dtype = np.float32
#             scalar_dtype = args.get( "dtype", default_dtype )
#             self._max_scalar_value = getMaxScalarValue( scalar_dtype )
#             self._range = [ 0.0, self._max_scalar_value ]  
#             datatype = getDatatypeString( scalar_dtype )
#             if (self.outputType == CDMSDataType.Hoffmuller):
#                 if ( selectedLevel == None ):
#                     varDataIdIndex = 0
#                 else:
#                     varDataIdIndex = selectedLevel  
#                                       
#             iTimestep = self.timeIndex if ( varName <> '__zeros__' ) else 0
#             varDataIdIndex = iTimestep  
#             roiStr = ":".join( [ ( "%.1f" % self.cdmsDataset.gridBounds[i] ) for i in range(4) ] ) if self.cdmsDataset.gridBounds else ""
#             varDataId = '%s;%s;%d;%s;%s' % ( dsid, varName, self.outputType, str(varDataIdIndex), roiStr )
#             vmd = {}         
#             vmd[ 'dsid' ] = dsid 
#             vmd[ 'file' ] = url if url else dsid              
#             vmd[ 'varName' ] = varName                 
#             vmd[ 'outputType' ] = self.outputType                 
#             vmd[ 'varDataIdIndex' ] = varDataIdIndex
#             vmd['datatype'] = datatype
#             vmd['timeIndex']= iTimestep
#             vmd['timeValue']= self.timeValue.value
#             vmd['latLonGrid']= self.cdmsDataset.latLonGrid
#             vmd['timeUnits' ] = self.referenceTimeUnits 
#             vmd[ 'bounds' ] = self.cdmsDataset.gridBounds          
#             enc_mdata = encodeToString( vmd ) 
#             if enc_mdata and fieldData: 
#                 fieldData.AddArray( getStringDataArray( 'metadata:%s' % varName,   [ enc_mdata ]  ) ) 
#                 vars.append( varName )                   
#         fieldData.AddArray( getStringDataArray( 'varlist',  vars  ) )                       


    def getAxisValues( self, axis, roi ):
        values = axis.getValue()
        bounds = None
        if roi:
            if   axis.isLongitude():  bounds = [ roi[0], roi[2] ]
            elif axis.isLatitude():   bounds = [ roi[1], roi[3] ] if ( roi[3] > roi[1] ) else [ roi[3], roi[1] ] 
        if bounds:
            if len( values ) < 2: values = bounds
            else:
                if axis.isLongitude() and (values[0] > values[-1]):
                    values[-1] = values[-1] + 360.0 
                value_bounds = [ min(values[0],values[-1]), max(values[0],values[-1]) ]
                mid_value = ( value_bounds[0] + value_bounds[1] ) / 2.0
                mid_bounds = ( bounds[0] + bounds[1] ) / 2.0
                offset = (360.0 if mid_bounds > mid_value else -360.0)
                trans_val = mid_value + offset
                if (trans_val > bounds[0]) and (trans_val < bounds[1]):
                    value_bounds[0] = value_bounds[0] + offset
                    value_bounds[1] = value_bounds[1] + offset           
                bounds[0] = max( [ bounds[0], value_bounds[0] ] )
                bounds[1] = min( [ bounds[1], value_bounds[1] ] )
        return bounds, values

    def getCoordType( self, axis, outputType ):
        iCoord = -2
        if axis.isLongitude(): 
            self.lon = axis
            iCoord  = 0
        if axis.isLatitude(): 
            self.lat = axis
            iCoord  = 1
        if isLevelAxis( axis ): 
            self.lev = axis
            iCoord  = 2 if ( outputType <> CDMSDataType.Hoffmuller ) else -1
        if axis.isTime():
            self.time = axis
            iCoord  = 2 if ( outputType == CDMSDataType.Hoffmuller ) else -1
        return iCoord

    def getIntersectedRoi( self, var, current_roi ):   
        try:
            newRoi = newList( 4, 0.0 )
            varname = var.outvar.name if hasattr( var,'outvar') else var.name
            tvar = self.cdmsDataset.getTransientVariable( varname )
            if id( tvar ) == id( None ): return current_roi
            current_roi_size = getRoiSize( current_roi )
            for iCoord in range(2):
                axis = None
                if iCoord == 0: axis = tvar.getLongitude()
                if iCoord == 1: axis = tvar.getLatitude()
                axisvals = axis.getValue()          
                if ( len( axisvals.shape) > 1 ):
#                    displayMessage( "Curvilinear grids not currently supported by DV3D.  Please regrid. ")
                    return current_roi
                newRoi[ iCoord ] = axisvals[0] # max( current_roi[iCoord], roiBounds[0] ) if current_roi else roiBounds[0]
                newRoi[ 2+iCoord ] = axisvals[-1] # min( current_roi[2+iCoord], roiBounds[1] ) if current_roi else roiBounds[1]
            if ( current_roi_size == 0 ): return newRoi
            new_roi_size = getRoiSize( newRoi )
            return newRoi if ( ( current_roi_size > new_roi_size ) and ( new_roi_size > 0.0 ) ) else current_roi
        except:
            print>>sys.stderr, "Error getting ROI for input variable"
            traceback.print_exc()
            return current_roi
       
    def getGridSpecs( self, var, roi, zscale, outputType, dset ):   
#        dims = var.getAxisIds()
        gridOrigin = newList( 3, 0.0 )
        outputOrigin = newList( 3, 0.0 )
        gridBounds = newList( 6, 0.0 )
        gridSpacing = newList( 3, 1.0 )
        gridExtent = newList( 6, 0 )
        outputExtent = newList( 6, 0 )
        gridShape = newList( 3, 0 )  
        gridSize = 1
#        domain = var.getDomain()
        self.lev = var.getLevel()
        axis_list = var.getAxisList()
#        isCurvilinear = False
        for axis in axis_list:
            size = len( axis )
            iCoord = self.getCoordType( axis, outputType )
            roiBounds, values = self.getAxisValues( axis, roi )
            if iCoord >= 0:
                iCoord2 = 2*iCoord
                gridShape[ iCoord ] = size
                gridSize = gridSize * size
                outputExtent[ iCoord2+1 ] = gridExtent[ iCoord2+1 ] = size-1 
                vmax =  max( values[0], values[-1] )                   
                vmin =  min( values[0], values[-1] )                   
                if iCoord < 2:
                    lonOffset = 0.0 #360.0 if ( ( iCoord == 0 ) and ( roiBounds[0] < -180.0 ) ) else 0.0
                    outputOrigin[ iCoord ] = gridOrigin[ iCoord ] = vmin + lonOffset
                    spacing = (vmax - vmin)/(size-1)
                    if roiBounds:
                        if ( roiBounds[1] < 0.0 ) and  ( roiBounds[0] >= 0.0 ): roiBounds[1] = roiBounds[1] + 360.0
                        gridExtent[ iCoord2 ] = int( round( ( roiBounds[0] - vmin )  / spacing ) )                
                        gridExtent[ iCoord2+1 ] = int( round( ( roiBounds[1] - vmin )  / spacing ) )
                        if gridExtent[ iCoord2 ] > gridExtent[ iCoord2+1 ]:
                            geTmp = gridExtent[ iCoord2+1 ]
                            gridExtent[ iCoord2+1 ] = gridExtent[ iCoord2 ] 
                            gridExtent[ iCoord2 ] = geTmp
                        outputExtent[ iCoord2+1 ] = gridExtent[ iCoord2+1 ] - gridExtent[ iCoord2 ]
                        outputOrigin[ iCoord ] = lonOffset + roiBounds[0]
                    roisize = gridExtent[ iCoord2+1 ] - gridExtent[ iCoord2 ] + 1                  
                    gridSpacing[ iCoord ] = spacing
                    gridBounds[ iCoord2 ] = roiBounds[0] if roiBounds else vmin 
                    gridBounds[ iCoord2+1 ] = (roiBounds[0] + roisize*spacing) if roiBounds else vmax
                else:                                             
                    gridSpacing[ iCoord ] = 1.0
#                    gridSpacing[ iCoord ] = zscale
                    gridBounds[ iCoord2 ] = vmin  # 0.0
                    gridBounds[ iCoord2+1 ] = vmax # float( size-1 )
        if gridBounds[ 2 ] > gridBounds[ 3 ]:
            tmp = gridBounds[ 2 ]
            gridBounds[ 2 ] = gridBounds[ 3 ]
            gridBounds[ 3 ] = tmp
        gridSpecs = {}
        md = { 'datasetId' : self.datasetId,  'bounds':gridBounds, 'lat':self.lat, 'lon':self.lon, 'lev':self.lev, 'time': self.timeAxis }
        gridSpecs['gridOrigin'] = gridOrigin
        gridSpecs['outputOrigin'] = outputOrigin
        gridSpecs['gridBounds'] = gridBounds
        gridSpecs['gridSpacing'] = gridSpacing
        gridSpecs['gridExtent'] = gridExtent
        gridSpecs['outputExtent'] = outputExtent
        gridSpecs['gridShape'] = gridShape
        gridSpecs['gridSize'] = gridSize
        gridSpecs['md'] = md
        if dset:  gridSpecs['attributes'] = dset.dataset.attributes
        return gridSpecs   
                 
    def computeMetadata( self ):
        metadata = {}
        if self.cdmsDataset:
            metadata[ 'vars2d' ] = self.cdmsDataset.getVariableList( 2 )
            metadata[ 'vars3d' ] = self.cdmsDataset.getVariableList( 3 )
        if self.fileSpecs: metadata[ 'fileSpecs' ] = self.fileSpecs
        if self.varSpecs:  metadata[ 'varSpecs' ]  = self.varSpecs
        if self.gridSpecs: metadata[ 'gridSpecs' ] = self.gridSpecs
        return metadata
            
    def getImageData( self, orec, **args ):
        """
        This method converts cdat data into vtkImageData objects. The ds object is a CDMSDataset instance which wraps a CDAT CDMS Dataset object. 
        The ds.getVarDataCube method execution extracts a CDMS variable object (varName) and then cuts out a data slice with the correct axis ordering (returning a NumPy masked array).   
        The array is then rescaled, converted to a 1D unsigned short array, and then wrapped as a vtkUnsignedShortArray using the vtkdata.SetVoidArray method call.  
        The vtk data array is then attached as point data to a vtkImageData object, which is returned.
        The CDAT metadata is serialized, wrapped as a vtkStringArray, and then attached as field data to the vtkImageData object.  
        """
        
        varList = orec.varList
        npts = -1
        if len( varList ) == 0: return False
        varDataIds = []
        intersectedRoi = args.get('roi', None )
        if intersectedRoi: self.cdmsDataset.setRoi( intersectedRoi )
        exampleVarDataSpecs = None
        dsid = None
        if (self.outputType == CDMSDataType.Vector ) and len(varList) < 3:
            if len(varList) == 2: 
                imageDataName = getItem( varList[0] )
                dsid = imageDataName.split('*')[0]
                varList.append( '*'.join( [ dsid, '__zeros__' ] ) )
            else: 
                print>>sys.stderr, "Not enough components for vector plot: %d" % len(varList)
#        print " Get Image Data: varList = %s " % str( varList )
        for varRec in varList:
            range_min, range_max, scale, shift  = 0.0, 0.0, 1.0, 0.0   
            imageDataName = getItem( varRec )
            varNameComponents = imageDataName.split('*')
            if len( varNameComponents ) == 1:
                dsid = self.cdmsDataset.getReferenceDsetId() 
                varName = varNameComponents[0]
            else:
                dsid = varNameComponents[0]
                varName = varNameComponents[1]
            ds = self.cdmsDataset[ dsid ]
            if ds:
                var = ds.getVariable( varName )
                self.setupTimeAxis( var, **args )
#            portName = orec.name
            selectedLevel = orec.getSelectedLevel() if ( self.currentLevel == None ) else self.currentLevel
            ndim = 3 if ( orec.ndim == 4 ) else orec.ndim
            default_dtype = np.float32
            scalar_dtype = args.get( "dtype", default_dtype )
            self._max_scalar_value = getMaxScalarValue( scalar_dtype )
            self._range = [ 0.0, self._max_scalar_value ]  
            datatype = getDatatypeString( scalar_dtype )   
            if (self.outputType == CDMSDataType.Hoffmuller):
                if ( selectedLevel == None ):
                    varDataIdIndex = 0
                else:
                    varDataIdIndex = selectedLevel  
                                      
            iTimestep = self.timeIndex if ( varName <> '__zeros__' ) else 0
            varDataIdIndex = iTimestep  
            roiStr = ":".join( [ ( "%.1f" % self.cdmsDataset.gridBounds[i] ) for i in range(4) ] ) if self.cdmsDataset.gridBounds else ""
            varDataId = '%s;%s;%d;%s;%s' % ( dsid, varName, self.outputType, str(varDataIdIndex), roiStr )
            varDataIds.append( varDataId )
            varDataSpecs = self.getCachedData( varDataId, self.rank ) 
#            flatArray = None
            if varDataSpecs == None:
                if varName == '__zeros__':
                    assert( npts > 0 )
                    newDataArray = np.zeros( npts, dtype=scalar_dtype ) 
                    varDataSpecs = copy.deepcopy( exampleVarDataSpecs )
                    varDataSpecs['newDataArray'] = newDataArray.ravel('F')  
                    self.setCachedData( varName, self.rank, varDataSpecs ) 
                else: 
                    tval = None if (self.outputType == CDMSDataType.Hoffmuller) else [ self.timeValue, iTimestep, self.useTimeIndex ] 
                    varDataMasked = self.cdmsDataset.getVarDataCube( dsid, varName, tval, selectedLevel, cell=self.rank )
                    if varDataMasked.id <> 'NULL':
                        varDataSpecs = self.getGridSpecs( varDataMasked, self.cdmsDataset.gridBounds, self.cdmsDataset.zscale, self.outputType, ds )
                        if (exampleVarDataSpecs == None) and (varDataSpecs <> None): exampleVarDataSpecs = varDataSpecs
                        range_min = varDataMasked.min()
                        if type( range_min ).__name__ == "MaskedConstant": range_min = 0.0
                        range_max = varDataMasked.max()
                        if type( range_max ).__name__ == 'MaskedConstant': range_max = 0.0
                        var_md = copy.copy( varDataMasked.attributes )
                                                          
                        if ( scalar_dtype == np.float32 ) or ( scalar_dtype == np.float64 ):
                            varData = varDataMasked.filled( 1.0e-15 * range_min ).astype(scalar_dtype).ravel('F')
                        else:
                            shift = -range_min
                            scale = ( self._max_scalar_value ) / ( range_max - range_min ) if  ( range_max > range_min ) else 1.0        
                            varData = ( ( varDataMasked + shift ) * scale ).astype(scalar_dtype).filled( 0 ).ravel('F')                          
                        del varDataMasked                          
                        
                        array_size = varData.size
                        if npts == -1:  npts = array_size
                        else: assert( npts == array_size )
                            
                        var_md[ 'range' ] = ( range_min, range_max )
                        var_md[ 'scale' ] = ( shift, scale )   
                        varDataSpecs['newDataArray'] = varData 
#                        print " ** Allocated data array for %s, size = %.2f MB " % ( varDataId, (varData.nbytes /(1024.0*1024.0) ) )                    
                        md =  varDataSpecs['md']                 
                        md['datatype'] = datatype
                        md['timeValue']= self.timeValue.value
                        md['latLonGrid']= self.cdmsDataset.latLonGrid
                        md['timeUnits' ] = self.referenceTimeUnits
                        md[ 'attributes' ] = var_md
                        md[ 'plotType' ] = 'zyt' if (self.outputType == CDMSDataType.Hoffmuller) else 'xyz'
                                        
                self.setCachedData( varDataId, self.rank, varDataSpecs )  
        
        if not varDataSpecs: return None            

        cachedImageDataName = '-'.join( varDataIds )
        image_data = self.getCachedImageData( cachedImageDataName, self.rank ) 
        if not image_data:
#            print 'Building Image for cache: %s ' % cachedImageDataName
            image_data = vtk.vtkImageData() 
            outputOrigin = varDataSpecs[ 'outputOrigin' ]
            outputExtent = varDataSpecs[ 'outputExtent' ]
            gridSpacing = varDataSpecs[ 'gridSpacing' ]
            if   scalar_dtype == np.ushort: image_data.SetScalarTypeToUnsignedShort()
            elif scalar_dtype == np.ubyte:  image_data.SetScalarTypeToUnsignedChar()
            elif scalar_dtype == np.float32:  image_data.SetScalarTypeToFloat()
            elif scalar_dtype == np.float64:  image_data.SetScalarTypeToDouble()
            image_data.SetOrigin( outputOrigin[0], outputOrigin[1], outputOrigin[2] )
#            image_data.SetOrigin( 0.0, 0.0, 0.0 )
            if ndim == 3: extent = [ outputExtent[0], outputExtent[1], outputExtent[2], outputExtent[3], outputExtent[4], outputExtent[5] ]   
            elif ndim == 2: extent = [ outputExtent[0], outputExtent[1], outputExtent[2], outputExtent[3], 0, 0 ]   
            image_data.SetExtent( extent )
            image_data.SetWholeExtent( extent )
            image_data.SetSpacing(  gridSpacing[0], gridSpacing[1], gridSpacing[2] )
#            print " ********************* Create Image Data, extent = %s, spacing = %s ********************* " % ( str(extent), str(gridSpacing) )
#            offset = ( -gridSpacing[0]*gridExtent[0], -gridSpacing[1]*gridExtent[2], -gridSpacing[2]*gridExtent[4] )
            self.setCachedImageData( cachedImageDataName, self.rank, image_data )
            
        fieldData = image_data.GetFieldData()        
#        nVars = len( varList )
#        npts = image_data.GetNumberOfPoints()
        pointData = image_data.GetPointData()
        for aname in range( pointData.GetNumberOfArrays() ): 
            pointData.RemoveArray( pointData.GetArrayName(aname) )
        extent = image_data.GetExtent()    
        scalars, nTup = None, 0
        vars_list = [] 
        for varDataId in varDataIds:
            try: 
                varDataSpecs = self.getCachedData( varDataId, self.rank )   
                newDataArray = varDataSpecs.get( 'newDataArray', None )
                md = varDataSpecs[ 'md' ] 
                varName = varDataId.split(';')[1]
                var_md = md[ 'attributes' ]            
                if newDataArray <> None:
                    vars_list.append( varName ) 
                    md[ 'valueRange'] = var_md[ 'range' ] 
                    vtkdata = getNewVtkDataArray( scalar_dtype )
                    nTup = newDataArray.size
                    vtkdata.SetNumberOfTuples( nTup )
                    vtkdata.SetNumberOfComponents( 1 )
                    vtkdata.SetVoidArray( newDataArray, newDataArray.size, 1 )
                    vtkdata.SetName( varName )
                    vtkdata.Modified()
                    pointData.AddArray( vtkdata )
#                    print "Add array to PointData: %s " % ( varName  )  
                    if (scalars == None) and (varName <> '__zeros__'):
                        scalars = varName
                        pointData.SetActiveScalars( varName  ) 
                        md[ 'scalars'] = varName 
            except Exception, err:
                print>>sys.stderr, "Error creating variable metadata: %s " % str(err)
                traceback.print_exc()
#         for iArray in range(2):
#             scalars = pointData.GetArray(iArray) 
# #            print "Add array %d to PointData: %s (%s)" % ( iArray, pointData.GetArrayName(iArray), scalars.GetName()  )       
        try:                           
            if (self.outputType == CDMSDataType.Vector ): 
                vtkdata = getNewVtkDataArray( scalar_dtype )
                vtkdata.SetNumberOfComponents( 3 )
                vtkdata.SetNumberOfTuples( nTup )
                iComp = 0
                for varName in vars:
                    fromArray =  pointData.GetArray( varName )
#                    fromNTup = fromArray.GetNumberOfTuples()
#                    tup0 = fromArray.GetValue(0)
#                    toNTup = vtkdata.GetNumberOfTuples()
                    vtkdata.CopyComponent( iComp, fromArray, 0 )
                    if iComp == 0: 
                        md[ 'scalars'] = varName 
                    iComp = iComp + 1                    
                vtkdata.SetName( 'vectors' )
                md[ 'vectors'] = ','.join( vars ) 
                vtkdata.Modified()
                pointData.SetVectors(vtkdata)
                pointData.SetActiveVectors( 'vectors'  )         
            if len( vars )== 0: raise Exception(  'No dataset variables selected for output %s.' % orec.name) 
            for varDataId in varDataIds:
                varDataFields = varDataId.split(';')
                dsid = varDataFields[0] 
                varName = varDataFields[1] 
                if varName <> '__zeros__':
                    varDataSpecs = self.getCachedData( varDataId, self.rank )
                    vmd = varDataSpecs[ 'md' ] 
                    var_md = md[ 'attributes' ]               
#                    vmd[ 'vars' ] = vars               
                    vmd[ 'title' ] = getTitle( dsid, varName, var_md )                   
                    enc_mdata = encodeToString( vmd ) 
                    if enc_mdata and fieldData: fieldData.AddArray( getStringDataArray( 'metadata:%s' % varName,   [ enc_mdata ]  ) ) 
            if enc_mdata and fieldData: fieldData.AddArray( ( 'varlist',  vars  ) )                         
            image_data.Modified()
        except Exception, err:
            print>>sys.stderr, "Error encoding variable metadata: %s " % str(err)
            traceback.print_exc()
        return cachedImageDataName

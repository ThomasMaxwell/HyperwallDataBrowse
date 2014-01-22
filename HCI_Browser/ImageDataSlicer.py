'''
Created on Jan 20, 2014

@author: tpmaxwel
'''
from PyQt4 import QtGui, QtCore
import cdms2, sys

class DataSlicer( QtCore.QObject ):
    
    def __init__(self, dsetPath, varName, **args ):  
        self.dset = cdms2.open( dsetPath, 'r' )
        self.var = self.dset[ varName ]
    
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
        iVal0 = int ( slider_pos * nvals )
        if ( iVal0 >= nvals - 1 ): iVal0 = nvals - 2
        iVal1 = iVal0 + 1
        try:
            if  iAxis == 0:
                dataslice = self.var( time=slice(iTime,iTime+1), longitude = slice(iVal0,iVal1), order ='yz' )          
#                dataslice = self.var( time=slice(iTime,iTime+1), longitude = coord_value, order ='yz' )          
            elif  iAxis == 1:
                dataslice = self.var( time=slice(iTime,iTime+1), latitude = slice(iVal0,iVal1), order ='xz'  )          
#                dataslice = self.var( time=slice(iTime,iTime+1), latitude = coord_value, order ='xz'  )          
            elif  iAxis == 2:
                dataslice = self.var( time=slice(iTime,iTime+1), level = slice(iVal0,iVal1), order ='xy'  ) 
#                dataslice = self.var( time=slice(iTime,iTime+1), level = coord_value, order ='xy'  ) 
        except cdms2.error.CDMSError, err:
            print>>sys.stderr, "Error getting slice[%d] (%.2f): %s " % ( iAxis, coord_value, str(err) )
            return None
         
        imageOutput =  dataslice.data.squeeze()  
             
        return imageOutput
    
if __name__ == "__main__":
    
    dset_path = "/Developer/Data/AConaty/comp-ECMWF/ac-comp1-geos5.xml"
    varname = "uwnd"
    
    ds = DataSlicer( dset_path, varname )
    
    s = ds.getSlice( 0, 0, 0.5, 180.0 )
    
    print "Done!"
    pass
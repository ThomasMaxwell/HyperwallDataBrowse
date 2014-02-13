'''
Created on Jan 21, 2014

@author: tpmaxwell
'''

#import matplotlib.pyplot as plt
from matplotlib.widgets import Cursor
from PyQt4 import QtCore, QtGui
import sys, os, cdms2, random, time, cdtime, ctypes, traceback
import numpy as np
from matplotlib.backends.backend_qt4agg import FigureCanvasAgg, FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure, SubplotParams
from HCI_Browser.ImageDataSlicer import DataSlicer

_decref = ctypes.pythonapi.Py_DecRef
_decref.argtypes = [ctypes.py_object]
_decref.restype = None

progversion = "0.1"
progname = "Hyperwall Cell Plot"

qtversion = str( QtCore.qVersion() )
isQt4 = ( qtversion[0] == '4' )

class MyCursor( Cursor ):
    
    def __init__( self, axes, **args ):
        Cursor.__init__( self, axes, **args )
        
    def onmove(self, event):
        self.visible = True
        self.vertOn = True
        self.horizOn = True
        Cursor.onmove( self, event )
#        print "Cursor move : %s %s " % ( str(event.xdata), str(event.ydata) )
    

def prettyPrintFloat( fval ):
    str_format = "%.2f"
    if ( abs(fval) > 9999.9 ) or ( abs(fval) < 0.1 ): str_format = "%.2e"
    return str_format % fval

cmaps = [('Sequential',     ['binary', 'Blues', 'BuGn', 'BuPu', 'gist_yarg',
                             'GnBu', 'Greens', 'Greys', 'Oranges', 'OrRd',
                             'PuBu', 'PuBuGn', 'PuRd', 'Purples', 'RdPu',
                             'Reds', 'YlGn', 'YlGnBu', 'YlOrBr', 'YlOrRd']),
         ('Sequential (2)', ['afmhot', 'autumn', 'bone', 'cool', 'copper',
                             'gist_gray', 'gist_heat', 'gray', 'hot', 'pink',
                             'spring', 'summer', 'winter']),
         ('Diverging',      ['BrBG', 'bwr', 'coolwarm', 'PiYG', 'PRGn', 'PuOr',
                             'RdBu', 'RdGy', 'RdYlBu', 'RdYlGn', 'seismic']),
         ('Qualitative',    ['Accent', 'Dark2', 'hsv', 'Paired', 'Pastel1',
                             'Pastel2', 'Set1', 'Set2', 'Set3', 'spectral']),
         ('Miscellaneous',  ['gist_earth', 'gist_ncar', 'gist_rainbow',
                             'gist_stern', 'jet', 'brg', 'CMRmap', 'cubehelix',
                             'gnuplot', 'gnuplot2', 'ocean', 'rainbow',
                             'terrain', 'flag', 'prism'])]

class MoveEvent:
    
    def __init__(self, inaxes, xdata, ydata ):
        self.inaxes = inaxes
        self.xdata = xdata
        self.ydata = ydata

class WindowDisplayMode:
    Normal = 0
    Maximized = 1
    FullScreen = 2

def getAxisLabel( coord_axis ): 
    try:    return "%s (%s)" % ( coord_axis.long_name, coord_axis.units )
    except: return coord_axis.id

class FrameEater( QtCore.QObject):
    
    def __init__(self, parent, *args, **kwargs):
        QtCore.QObject.__init__(self)
        self.nPaintEvents = 0

    def eventFilter(self, obj, event ):
        if self.nPaintEvents > 0:
            self.nPaintEvents = self.nPaintEvents - 1
        print "Process Event: %s, nPaintEvents = %d" % ( event.__class__.__name__,  self.nPaintEvents )
        sys.stdout.flush()
        return False
        
    def logRepaint(self):
        self.nPaintEvents = self.nPaintEvents + 1

class mplSlicePlot(FigureCanvas):

    def __init__(self, parent, *args, **kwargs):
        self.fig = Figure( subplotpars=SubplotParams(left=0.05, right=0.95, bottom=0.05, top=0.95 ) )
        self.axes = self.fig.add_subplot(111)    
        self.axes.hold(False)                   # We want the axes cleared every time plot() is called    
        self.compute_initial_figure()
        FigureCanvas.__init__(self, self.fig)
        self.setParent(parent)
        FigureCanvas.setSizePolicy(self, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        timestep = kwargs.get( 'timestep', None )
        if timestep:
            self.timer = QtCore.QTimer(self)
            QtCore.QObject.connect(self.timer, QtCore.SIGNAL("timeout()"), self.update_figure)
            self.timer.start(1000)
        self.vrange = [ None, None ]
        self.parms = {}
        self.parms.update( kwargs )
        self.plot = None
        self.cbar = None
        self.zscale = 3
        self.current_plot_index = -1
        self.current_grid_index = -1
        self.annotation_box = None
        self.grid_annotation = None
        self.time_annotation = None
        self.dset_annotation = None
        self.slice_loc = [ 0, 0, 0, 0 ]
        self.cursor_pos = [ 0.0, 0.0 ]
        self.axes_intervals = [ [0,0], [0,0] ]
        self.cursor_plot = None
        self.roi = None
        self.fig.canvas.mpl_connect( 'button_press_event', self.processMouseClick )
        self.slicedImageData = None
#        self.frameEater = FrameEater( self ) 
#        self.installEventFilter( self.frameEater )

    def processProbe( self, point ):
        pointCoords, pointIndices, ptVal = self.dataSlicer.getPoint( rpt=point )
        self.plotPoint( pointCoords, pointIndices, ptVal ) 
        print " processProbe: %s %s %s "  % ( str(pointCoords), str(pointIndices), str(ptVal) )   

    def processSubset( self, roi ):
        dataSlice = self.dataSlicer.setRoi( roi )          
        if id(dataSlice) <> id(None):
            self.slicedImageData =  dataSlice     
            self.plotSubset( self.slicedImageData, roi )   
        print " processSubset: %s "  % ( str(roi) )   

    def positionSlice( self, iAxis, slider_pos, coord_value ):
        dataSlice = self.dataSlicer.getSlice( iAxis, slider_pos, coord_value )          
        if id(dataSlice) <> id(None):
            self.slicedImageData =  dataSlice     
            self.plotSlice( iAxis, self.slicedImageData, coord_value )   

    def processMouseClick( self, event ):
        ibutton = event.button
        pointIndices = [ 0, 0 ]
        pointCoords = [ 0, 0 ]
        rCoord = [ 0, 0 ]
        if ibutton == 1:
            for iAxis in range(2):
                dcoord = event.xdata if (iAxis==0) else event.ydata
                bounds = self.axes.get_xbound() if (iAxis==0) else self.axes.get_ybound()
                rCoord[iAxis] = ( dcoord - bounds[0] ) / (  bounds[1] - bounds[0] ) 
                axis = self.xcoord if ( iAxis == 0 ) else self.ycoord
                axis_vals = axis.getValue() 
                ainterval = self.axes_intervals[iAxis]
                pointIndices[iAxis] = ainterval[0] + rCoord[iAxis] * ( ainterval[1] - ainterval[0] )
                pointCoords[ iAxis ] = axis_vals[ pointIndices[iAxis] ]

            pointCoords1, pointIndices1, ptVal = self.dataSlicer.getPoint( rpt=rCoord )
            self.plotPoint( pointCoords, pointIndices, ptVal )
            print " pointCoords1 = %s, pointIndices1 = %s,  pointIndices1 = %s, pointCoords = %s, rCoord=%s " % ( pointCoords1, pointIndices, pointIndices1, pointCoords, rCoord )
            
              
    def param(self, pname, defval = None ):
        return self.parms.get( pname, defval )

    def set_param(self, pname, val ):
        self.parms[ pname ] = val
        

#        self.cmap = None
#        self.norm = None
#        self.aspect = None
#        self.interpolation = None
#        self.alpha = None
#        
#        self.origin = None
#        self.extent = None
#        self.shape = None
#        self.filternorm = None
#        self.filterrad = 4.0
#        self.imlim = None
#        self.resample = None
#        self.url = None

    def initCanvas( self, parent ): 
        pass
#        fig = Figure(figsize=(width, height), dpi=dpi) # , width=5, height=4, dpi=100, **kwargs):

    def compute_initial_figure(self):
        pass   

#     def setTicks1( self, iaxis, nticks, coord_bounds=None ):            
#         tvals = [0]*nticks
#         tlocs = [0]*nticks     
#         axis = self.xcoord if ( iaxis == 0 ) else self.ycoord
#         axis_vals = axis.getValue() 
#         nvals = len( axis_vals )
#         bounds = self.axes.get_xbound() if ( iaxis == 0 ) else self.axes.get_ybound()
#         brange = bounds[1] - bounds[0]
#         tstep = brange / float( nticks ) 
#         ihalfstep = brange / ( 2 * float( nvals ) )
#         invertAxis = ( iaxis == 1 )
#         if axis.isLevel() and hasattr( axis, 'positive' ) :           
#             invertValues = (bounds[0] < bounds[1]) if axis.positive == 'down' else (bounds[1] < bounds[0])
#             if invertValues: invertAxis = not invertAxis
#                    
#         if invertAxis:
#             for iTick in range( 0, nticks ):
#                 tlocs[iTick] = bounds[1] - ( tstep * iTick )   
#         else:
#             for iTick in range( 0, nticks ):
#                 tlocs[iTick] = bounds[0] + tstep * iTick  
#             
#         if coord_bounds == None: 
#             index_offset = 0
#             index_step = nvals / float( nticks - 1 )
#             self.axes_intervals[iaxis] = [ 0, nvals ]
#         else: 
#             if axis.isLongitude() and ( ( coord_bounds[0] < 0.0 ) or ( coord_bounds[1] < 0.0 ) ):
#                 coord_bounds[0] = coord_bounds[0] + 360.0
#                 coord_bounds[1] = coord_bounds[1] + 360.0
#             index_interval = axis.mapIntervalExt( coord_bounds )
#             index_offset = index_interval[0]
#             index_step = ( index_interval[1] - index_interval[0] ) / float( nticks - 1 )
#             self.axes_intervals[iaxis] = [ index_interval[0], index_interval[1] ]
#             
#         iValIndex = int( index_offset )
#         for iVal in range( 0, nticks ):            
#             cval = axis_vals[ iValIndex ]
#             tvals[iVal] = ( "%.1f" % cval )
#             iValIndex = int( round( iValIndex + index_step ) )
#             if iValIndex >= nvals: iValIndex = nvals - 1
#                        
#         if ( iaxis == 0 ):
#             self.axes.set_autoscalex_on( False )
#             self.axes.set_xticklabels( tvals )
#             self.axes.set_xticks( tlocs )
#         else:
#             self.axes.set_autoscaley_on( False )
#             self.axes.set_yticklabels( tvals )
#             self.axes.set_yticks( tlocs )

    def setTicks( self, iaxis, nticks, coord_bounds=None ):            
        tvals = [0]*nticks
        tlocs = [0]*nticks     
        axis = self.xcoord if ( iaxis == 0 ) else self.ycoord
        axis_vals = axis.getValue() 
        nvals = len( axis_vals )
        bounds = self.axes.get_xbound() if ( iaxis == 0 ) else self.axes.get_ybound()
        brange = bounds[1] - bounds[0]
        tstep = brange / float( nticks-1 )     
        invertAxis = ( hasattr( axis, 'positive' ) and (bounds[0] < bounds[1]) and ( axis.positive == 'down') )
                               
        if coord_bounds == None: 
            index_offset = 0
            index_step = nvals / float( nticks - 1 )
            self.axes_intervals[iaxis] = [ 0, nvals ]
            interval_width = float( nvals - 1 )
        else: 
            if axis.isLongitude() and ( ( coord_bounds[0] < 0.0 ) or ( coord_bounds[1] < 0.0 ) ):
                coord_bounds[0] = coord_bounds[0] + 360.0
                coord_bounds[1] = coord_bounds[1] + 360.0
            index_interval = axis.mapIntervalExt( coord_bounds )
            index_offset = index_interval[0]
            index_step = int( round( ( index_interval[1] - index_interval[0] ) / float( nticks - 1 ) ) )
            self.axes_intervals[iaxis] = [ index_interval[0], index_interval[1] ]
            interval_width = float( index_interval[1] - index_interval[0] - 1 )
        
        indices = []    
        iValIndex = int( index_offset )
        for iVal in range( 0, nticks ):            
            cval = axis_vals[ iValIndex ]
            tvals[iVal] = ( "%.1f" % cval )
            rval = ( iValIndex - index_offset ) / interval_width
            tlocs[iVal] = (bounds[1] - rval * brange)  if invertAxis else ( bounds[0] + rval * brange )  
            indices.append( iValIndex ) 
            iValIndex = int( round( iValIndex + index_step ) )
            if iValIndex >= nvals: iValIndex = nvals - 1
         
#        print "Set ticks[%d]: %s %s %s " % ( iaxis, str(indices), str(tlocs), str(tvals) )      
        if ( iaxis == 0 ):
            self.axes.set_autoscalex_on( False )
            self.axes.set_xticklabels( tvals )
            self.axes.set_xticks( tlocs )
        else:
            self.axes.set_autoscaley_on( False )
            self.axes.set_yticklabels( tvals )
            self.axes.set_yticks( tlocs )
                
    def setTitle(self):
        try:
            title_font = { 'family' : 'serif', 'color'  : 'black', 'weight' : 'bold', 'size'   : 32, }
            title = self.var.long_name if hasattr( self.var, 'long_name') else self.var.id
            self.axes.set_title(title, fontdict=title_font )
        except: pass
        
    def setAxisLabels(self):
        axis_font = { 'family' : 'serif', 'color'  : 'black', 'weight' : 'normal', 'size'   : 21, }
        self.axes.set_xlabel( getAxisLabel( self.xcoord ), fontdict=axis_font )
        self.axes.set_ylabel( getAxisLabel( self.ycoord ), fontdict=axis_font )
        
    def createColorbar( self, **args ):
        if self.cbar == None:
            shrink_factor = args.get( 'shrink', 0.5 )
            self.cbar = self.figure.colorbar( self.plot, shrink=shrink_factor ) 
            try: self.cbar.set_label( self.var.units )
            except: pass
            
    def setZScale( self, zscale ):
        if self.zscale <> zscale:
            self.zscale = zscale
            self.update_figure( True )
     
    def showAnnotation( self, textstr ): 
        if self.annotation_box == None:     
            props = dict( boxstyle='round', facecolor='wheat', alpha=0.5 )
            self.annotation_box = self.axes.text( 0.82, 0.99, textstr, transform=self.fig.transFigure, fontsize=14, verticalalignment='top', bbox=props)
        else:
            self.annotation_box.set_text( textstr )
            
#     def getDisplayPoint1( self, data_point, dataPointIndices ):
#         dpnt = [0,0]
#         for iaxis in range(2):   
#             axis = self.xcoord if ( iaxis == 0 ) else self.ycoord
#             axis_vals = axis.getValue() 
#             cVal = data_point[ iaxis ]
#             index_bnds = self.axes_intervals[iaxis]
#             sub_axis_vals = axis_vals[index_bnds[0]:index_bnds[1]]
#             nvals = index_bnds[1] - index_bnds[0]
#             if sub_axis_vals[0] > sub_axis_vals[-1]:
#                 iVal = np.searchsorted( sub_axis_vals[::-1], cVal )
#                 iVal = nvals - iVal - 1
#             else:
#                 iVal = np.searchsorted( sub_axis_vals, cVal )            
#             fVal = iVal / float( nvals )
#             bounds = self.axes.get_xbound() if ( iaxis == 0 ) else self.axes.get_ybound()
#             brange = bounds[1] - bounds[0]            
#             dpnt[ iaxis ] = ( bounds[0] + fVal * brange ) if ( iaxis == 0 ) else ( bounds[1] - fVal * brange )
#         return dpnt 

    def getDisplayPoint( self, dataPointIndices ):
        dpnt = [0,0]
        for iaxis in range(2): 
            axis = self.xcoord if ( iaxis == 0 ) else self.ycoord  
            index_bnds = self.axes_intervals[iaxis]
            axis_vals = axis.getValue() 
            localIndex = dataPointIndices[ iaxis ] # - index_bnds[0]
            fVal = localIndex / float( index_bnds[1] - index_bnds[0] -1 )
            bounds = self.axes.get_xbound() if ( iaxis == 0 ) else self.axes.get_ybound()
            brange = bounds[1] - bounds[0] 
            invertAxis = ( iaxis == 1 ) 
            if hasattr( axis, 'positive' ) and ( axis.positive == 'down' ) and ( axis_vals[1] > axis_vals[0] ): invertAxis = not invertAxis     
            if  invertAxis:  dpnt[ iaxis ] = ( bounds[1] - fVal * brange )
            else:            dpnt[ iaxis ] = ( bounds[0] + fVal * brange )  
        return dpnt 
            
    def updateCursor( self, dataPointIndices ):          
        if self.cursor_plot == None: 
#                self.axes.hold(True)
            self.cursor_plot = MyCursor( self.axes,  color='red', linewidth=1 ) # useblit=True,
#                self.axes.hold(False)
#            cdata = self.axes.transData.transform_point( self.cursor_pos )
        x, y = self.getDisplayPoint( dataPointIndices )
        mv_event = MoveEvent( self.axes, [ x ], [ y ] )
        self.cursor_plot.onmove( mv_event )
#        print "Update cursor: %.1f, %.1f (%s)" % ( x, y, str(data_point)  ); sys.stdout.flush()
                
    def update_figure( self, refresh = True, label=None, **kwargs ):    
        if ( id(self.data) <> id(None) ):
            if refresh:
                if self.cursor_plot <> None:
                    self.cursor_plot.disconnect_events()
                    self.cursor_plot = None
                self.plot = self.axes.imshow( self.data, cmap=self.param('cmap'), norm=self.param('norm'), aspect=self.param('aspect'), interpolation=self.param('interpolation'), alpha=self.param('self.alpha'), vmin=self.vrange[0],
                            vmax=self.vrange[1], origin='lower', extent=self.param('extent'), shape=self.param('shape'), filternorm=self.param('filternorm'), filterrad=self.param('filterrad',4.0),
                            imlim=self.param('imlim'), resample=self.param('resample'), url=self.param('url'), **kwargs)
                if self.roi == None:
                    self.setTicks( 0, 5 )
                    self.setTicks( 1, 5 )            
                else:
                    if self.current_grid_index == 0:
                        self.setTicks( 0, 5, [ self.roi[1], self.roi[3] ] )
                        self.setTicks( 1, 5 )  
                    elif self.current_grid_index == 1:
                        self.setTicks( 0, 5, [ self.roi[0], self.roi[2] ] )
                        self.setTicks( 1, 5 )  
                    elif self.current_grid_index == 2:
                        self.setTicks( 0, 5, [ self.roi[0], self.roi[2] ] )
                        self.setTicks( 1, 5, [ self.roi[1], self.roi[3] ]  )
                self.setTitle()
                if self.ycoord.isLevel():  self.axes.set_aspect( self.zscale, 'box') 
                self.createColorbar()
                self.setAxisLabels()
                self.annotation_box = None
            else:
                self.plot.set_array(self.data)
#            self.updateCursor()
            if label: 
                self.showAnnotation( label )
            FigureCanvasAgg.draw(self)
            self.repaint()
            if isQt4: QtGui.qApp.processEvents()   # Workaround Qt bug in v. 4.x

    def setVariable(self, filepath, varname ):
        self.dataSlicer = DataSlicer( filepath, varname )
        self.var = self.dataSlicer.getVariable() 
        self.dset_annotation = self.dataSlicer.getDatasetTitle() 
        
    def setColormap( self, cmap ):
        self.plot.set_cmap( cmap )
        
    def plotPoint(self, point, pointIndices, ptVal ):
        point_annotation = "Probe Point( %.1f, %.1f ) = %s" % ( point[0], point[1], prettyPrintFloat(ptVal) )
        label = '\n'.join([ self.dset_annotation, self.grid_annotation, self.time_annotation, point_annotation ]) 
        self.showAnnotation( label )
        self.updateCursor( pointIndices )
        self.axes.figure.canvas.draw_idle()
#        FigureCanvasAgg.draw(self)
#        self.repaint()
#        if isQt4: QtGui.qApp.processEvents()   # Workaround Qt bug in v. 4.x
        
    def plotSlice( self, plot_index, slice_data, coord_value ):
        self.slice_loc[plot_index] = coord_value
        if plot_index == 0: 
            self.xcoord = self.var.getLatitude()
            self.ycoord = self.var.getLevel()
            self.grid_annotation = "Longitude = %.1f" % ( coord_value )
        if plot_index == 1: 
            self.xcoord = self.var.getLongitude()
            self.ycoord = self.var.getLevel()
            self.grid_annotation = "Latitude = %.1f" % ( coord_value )
        if plot_index == 2: 
            self.ycoord = self.var.getLatitude()
            self.xcoord = self.var.getLongitude()
            self.grid_annotation = "Level = %.1f" % ( coord_value )
        if plot_index == 3: 
            time_axis = self.var.getTime()
            r = cdtime.reltime( coord_value, time_axis.units )
            ts = str( r.tocomp() )
            self.time_annotation = "Time = %s" % ts
            self.slice_loc[plot_index] = ts
        if self.time_annotation == None:
            time_axis = self.var.getTime()
            r = cdtime.reltime( 0.0, time_axis.units )
            ts = str( r.tocomp() )
            self.time_annotation = "Time = %s" % ts 
            self.slice_loc[ plot_index ] = ts      
        self.data = slice_data
        refresh_axes = ( self.current_plot_index <> plot_index ) and ( plot_index <> 3 )
        self.current_plot_index = plot_index 
        if plot_index <> 3: self.current_grid_index = plot_index 
        self.update_figure( refresh_axes, '\n'.join([ self.dset_annotation, self.grid_annotation, self.time_annotation ]) )

    def plotSubset( self, slice_data, roi ):
        self.data = slice_data
        self.roi = roi
        self.update_figure( True, '\n'.join([ self.dset_annotation, self.grid_annotation, self.time_annotation ]) )

class qtApplicationWindow(QtGui.QMainWindow):
    
    def __init__( self, **args ):
        QtGui.QMainWindow.__init__( self, **args )
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle("application main window")
        self.main_widget = QtGui.QWidget(self)
        self.generateContent( **args )
        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)
        self.statusBar().showMessage("Status here.", 2000)

    def fileQuit(self):
        self.close()

    def closeEvent(self, ce):
        self.fileQuit()
        self.emit( QtCore.SIGNAL("Close") )
        
    def generateContent( self, **args ): 
        l = QtGui.QVBoxLayout(self.main_widget)
        self.plot = mplSlicePlot( self.main_widget )
        l.addWidget( self.plot )
        
    def generateSlice( self, plot_index, slice_data, coord_value ):
        self.plot.plotSlice( plot_index, slice_data, coord_value )

    def setVariable( self, var, title ):
        self.plot.setVariable( var, title )

if __name__ == '__main__':
    data_dir = "~/Data/AConaty/comp-ECMWF"
    data_file = "ac-comp1-geos5.xml"
    varName = 'uwnd'
    displayMode = WindowDisplayMode.Maximized
    ds = cdms2.open( os.path.expanduser( os.path.join( data_dir, data_file) ), 'r' )
    var = ds[ varName ]
    
    qApp = QtGui.QApplication(sys.argv)
    
    aw = qtApplicationWindow()
    aw.setWindowTitle("%s" % progname)
    aw.setVariable( var, "Test" )
    aw.generateSlice( 0, var[0,0,:,:], 0.0 )
    
    if   displayMode == WindowDisplayMode.Normal:       aw.show()
    elif displayMode == WindowDisplayMode.FullScreen:   aw.showFullScreen()
    elif displayMode == WindowDisplayMode.Maximized:    aw.showMaximized()
    sys.exit(qApp.exec_())
    
    
 
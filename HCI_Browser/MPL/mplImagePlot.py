'''
Created on Jan 21, 2014

@author: tpmaxwell
'''

import matplotlib.pyplot as plt
from PyQt4 import QtCore, QtGui
import sys, os, cdms2, random, time
from matplotlib.backends.backend_qt4agg import FigureCanvasAgg, FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure, SubplotParams

progversion = "0.1"
progname = "Hyperwall Cell Plot"

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

class WindowDisplayMode:
    Normal = 0
    Maximized = 1
    FullScreen = 2

def getAxisLabel( coord_axis ): 
    try:    return "%s (%s)" % ( coord_axis.long_name, coord_axis.units )
    except: return coord_axis.id

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
        self.annotation_box = None
        
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
    
    def setTicks( self, iaxis, nticks ):
        axis_vals = self.xcoord.getValue() if ( iaxis == 0 ) else self.ycoord.getValue()
        nvals = len( axis_vals )
        vstep = ( nvals - 1.0 ) / ( nticks - 1.0 )
        tvals = []
        tlocs = []
        coord_index = 0.0
        while True:
            index0 = int( coord_index )
            offset = coord_index - index0
            if offset == 0: 
                cval = axis_vals[ index0 ]
            else:
                cval = offset * axis_vals[ index0 ] + ( 1.0 - offset ) * axis_vals[ index0 + 1 ]
            tvals.append( "%.1f" % cval )
            tlocs.append( coord_index )
            coord_index = coord_index + vstep
            if coord_index > ( nvals - 1 - vstep/2 ):
                cval = axis_vals[ nvals - 1 ]
                tvals.append( "%.1f" % cval )
                tlocs.append( nvals - 1 )
                break
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
            self.annotation_box = self.axes.text( 0.05, 0.95, textstr, transform=self.fig.transFigure, fontsize=14, verticalalignment='top', bbox=props)
        else:
            self.annotation_box.set_text( textstr )
                
    def update_figure( self, refresh = True, label=None, **kwargs ):    
        if ( id(self.data) <> id(None) ):
            if refresh:
                self.plot = self.axes.imshow( self.data, cmap=self.param('cmap'), norm=self.param('norm'), aspect=self.param('aspect'), interpolation=self.param('interpolation'), alpha=self.param('self.alpha'), vmin=self.vrange[0],
                            vmax=self.vrange[1], origin=self.param('origin'), extent=self.param('extent'), shape=self.param('shape'), filternorm=self.param('filternorm'), filterrad=self.param('filterrad',4.0),
                            imlim=self.param('imlim'), resample=self.param('resample'), url=self.param('url'), **kwargs)
                self.setTicks( 0, 5 )
                self.setTicks( 1, 5 )
                self.setTitle()
                if self.ycoord.isLevel():  self.axes.set_aspect( self.zscale, 'box') 
                self.createColorbar()
                self.setAxisLabels()
                self.annotation_box = None
            else:
                self.plot.set_array(self.data)
            if label: self.showAnnotation( label )
            FigureCanvasAgg.draw(self)
            self.repaint()

    def setVariable( self, var ):
        self.var = var
        
    def setColormap( self, cmap ):
        self.plot.set_cmap( cmap )
        

    def plotSlice( self, plot_index, slice_data, coord_value ):
        if plot_index == 0: 
            self.xcoord = self.var.getLatitude()
            self.ycoord = self.var.getLevel()
            slice_coord_name = "Longitude"
        if plot_index == 1: 
            self.xcoord = self.var.getLongitude()
            self.ycoord = self.var.getLevel()
            slice_coord_name = "Latitude"
        if plot_index == 2: 
            self.ycoord = self.var.getLatitude()
            self.xcoord = self.var.getLongitude()
            slice_coord_name = "Level"
        if plot_index == 3: 
            slice_coord_name = "Time"
        self.data = slice_data
        refresh_axes = self.current_plot_index <> plot_index
        self.current_plot_index = plot_index 
        annotation = "%s = %.1f" % ( slice_coord_name, coord_value )
        self.update_figure( refresh_axes, annotation )

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
        
    def generateSlice( self, plot_index, slider_value ):
        self.plot.generateSlice( plot_index, slider_value )

    def setVariable( self, var ):
        self.plot.setVariable( var )

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
    aw.setVariable( var )
    aw.generateSlice( 0, 0.5 )
    
    if   displayMode == WindowDisplayMode.Normal:       aw.show()
    elif displayMode == WindowDisplayMode.FullScreen:   aw.showFullScreen()
    elif displayMode == WindowDisplayMode.Maximized:    aw.showMaximized()
    sys.exit(qApp.exec_())
    
    
 
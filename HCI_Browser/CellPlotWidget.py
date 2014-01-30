'''
Created on Jan 13, 2014

@author: tpmaxwel
'''
from PyQt4 import QtGui
import sys, os, cdms2
from ClusterCommunicator import control_message_signal
from ColormapManager import ColorMapManager
from ImageDataSlicer import DataSlicer
from HCI_Browser.MPL import getCellWidget

class PlotLib:
    VTK = 0
    VCS = 1
    MPL = 2
    
class WindowDisplayMode:
    Normal = 0
    Maximized = 1
    FullScreen = 2

PlotLibrary = PlotLib.MPL

class CellPlotWidget( QtGui.QWidget ):
    
    def __init__(self, parent, hcomm, **args ):  
        super( CellPlotWidget, self ).__init__( parent ) 
        self.comm = hcomm
        self.cellWidget = None
        self.filepath = None
        self.varname = None
        self.roi = None 
        if self.comm: 
            self.comm.connect( hcomm, control_message_signal, self.processConfigCmd )
            self.comm.start()
            
    def processConfigCmd( self, msg ):
#        print " CellPlotWidget: Process Config Cmd: ", str( msg )
        if msg['type'] == 'Quit': 
            self.terminate()
            self.parent().close()
        elif msg['type'] == 'Config': 
            self.buildCanvas()
            self.processConfigData( msg['data'] )   
        elif msg['type'] == 'Slider': 
            cmd = msg.get( 'cmd', None )
            slice_index = int( msg.get( 'index', -1 ) )
            if cmd == 'Moved':
                values = msg.get( 'values', None )
                if values: self.positionSlice( slice_index, values[0], values[1] )
#                print " Slider Moved: %s " % str( values )
#                sys.stdout.flush()
#                sval = float( values[0] ) if values else None
                    
                                
    def processConfigData( self, config_data ): 
        print " processConfigData "  
        global_config = config_data.get('global', None )
        if global_config:
            self.roi = global_config.get('roi',None)
            self.dir = global_config.get('dir',None)
        iproc = self.comm.rank
        dset = None
        cell_data = config_data.get( "c%d" % iproc, None )
        if cell_data:
            var = cell_data.get( 'dv', None )
            if var:
                var_data = config_data.get( var, None )
                if var_data:                
                    self.varname = var_data.get( 'name', None )
                    dset = var_data.get( 'ds', None )
            else: print>>sys.stderr, "Error, no variable declared for cell %d " % iproc
            if dset:
                dset_data = config_data.get( dset, None )
                if dset_data:                
                    filename = dset_data.get( 'file', None )
                    self.dset_id = dset_data.get( 'id', dset )
                    self.filepath = filename if ( self.dir == None ) else os.path.join( self.dir, filename )
                    self.dataSlicer = DataSlicer( self.filepath, self.varname )
                    self.cellWidget.setVariable( self.dataSlicer.getVariable(), self.dataSlicer.getDatasetTitle() )
                    self.positionSlice( 0, 0.5, 180.0 )
                else: print>>sys.stderr, "Error, no dataset declared for cell %d " % iproc

    def positionSlice( self, iAxis, slider_pos, coord_value ):
        dataSlice = self.dataSlicer.getSlice( iAxis, slider_pos, coord_value )          
        if id(dataSlice) <> id(None):
            self.slicedImageData =  dataSlice     
            self.cellWidget.plotSlice( iAxis, self.slicedImageData, coord_value )   
     
    def buildCanvas(self):
        print " buildCanvas "  
        if self.cellWidget <> None: return
        top_level_layout = QtGui.QVBoxLayout() 
        self.setLayout(top_level_layout)
        self.cellWidget = getCellWidget(self) 
#         if   PlotLibrary == PlotLib.MPL: self.cellWidget = HCI_Browser.MPL.getCellWidget(self) 
#         elif PlotLibrary == PlotLib.VTK: self.cellWidget = HCI_Browser.VTK.getCellWidget(self) 
#         elif PlotLibrary == PlotLib.VCS: self.cellWidget = HCI_Browser.VCS.getCellWidget(self) 
        top_level_layout.addWidget( self.cellWidget )
        
    def terminate(self):
        self.comm.stop()
       
class CellPlotWidgetWindow( QtGui.QMainWindow ):

    def __init__(self, hcomm= None, parent = None):
        QtGui.QMainWindow.__init__(self, parent)
        self.wizard = CellPlotWidget( self, hcomm )
        self.setCentralWidget(self.wizard)
        self.setWindowTitle("Hyperwall Cell")
        self.resize(500,400)
        
    def terminate(self):
        self.wizard.terminate()
        self.close()
                
if __name__ == "__main__":
    app = QtGui.QApplication( ['Hyperwall Cell'] )
    displayMode = WindowDisplayMode.Normal
    window = CellPlotWidgetWindow()
    if len(sys.argv)>2 and sys.argv[1] == '-c':
        window.wizard.loadFromCommand(sys.argv[2:])
    if   displayMode == WindowDisplayMode.Normal:       window.show()
    elif displayMode == WindowDisplayMode.FullScreen:   window.showFullScreen()
    elif displayMode == WindowDisplayMode.Maximized:    window.showMaximized()
    app.exec_()  
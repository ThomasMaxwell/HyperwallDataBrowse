'''
Created on Jan 13, 2014

@author: tpmaxwel
'''
from PyQt4 import QtGui, QtCore
import sys, os, cdms2
from Utilities import control_message_signal
from ColormapManager import ColorMapManager
from HCI_Browser.mpl import getCellWidget


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
        elif msg['type'] == 'Probe': 
            self.cellWidget.processProbe( msg.get( 'point', None ), msg.get( 'button', None ) )
        elif msg['type'] == 'Subset': 
            self.cellWidget.processSubset( msg.get( 'roi', None ) )
        elif msg['type'] == 'Color': 
            self.cellWidget.processColorConfig( msg.get( 'vscale', None ), msg.get( 'cmap', None ) )
        elif msg['type'] == 'Slider': 
            cmd = msg.get( 'cmd', None )
            slice_index = int( msg.get( 'index', -1 ) )
            if cmd == 'Moved':
                values = msg.get( 'values', None )
                if values: self.cellWidget.positionSlice( slice_index, values[0], values[1] )
#                print " Slider Moved: %s " % str( values )
#                sys.stdout.flush()
#                sval = float( values[0] ) if values else None
                                                   
    def processConfigData( self, config_data ): 
        global_config = config_data.get('global', None )
        if global_config:
            self.roi = global_config.get('roi',None)
            self.dir = global_config.get('dir',None)
        iproc = self.comm.rank if self.comm else 1
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
                    self.cellWidget.setVariable( self.filepath, self.varname )
                    self.cellWidget.positionSlice( 0, 0.5, 180.0 )
                else: print>>sys.stderr, "Error, no dataset declared for cell %d " % iproc

     
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
        if self.comm: self.comm.stop()
       
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
    
#    data_dir = '/Developer/Data/AConaty/comp-ECMWF'
    data_dir = '~/data/AConaty/comp-ECMWF'
    data_file = 'ac-comp1-geos5.xml'
    data_var = 'uwnd'
    dsid = 'geos5'
    roi = [ 160, -6, 200, 40 ]
    vscale = [ -20.0, 20.0 ]
    cmap = 'gist_ncar'
    
    app = QtGui.QApplication( ['Hyperwall Data Browser'] )

    window = CellPlotWidgetWindow( None )
    app.connect( app, QtCore.SIGNAL("aboutToQuit()"), window.terminate ) 
    window.show()
    
    cfg_data = {'type': 'Config', 'data': {'c1': {'dv': 'dv1'}, 'global': {'dir': data_dir}, 'dv1': {'name': data_var, 'ds': 'ds1'}, 'ds1': {'id': dsid, 'file': data_file}}}
    window.wizard.processConfigCmd( cfg_data )

    cfg_data = {'index': 2, 'cmd': 'Moved', 'values': (0.017, 1.7000000000000002), 'type': 'Slider'}
    window.wizard.processConfigCmd( cfg_data )

    cfg_data = {'roi': roi, 'type': 'Subset'}
    window.wizard.processConfigCmd( cfg_data )

    cfg_data = {'vscale': vscale, 'cmap' : cmap, 'type': 'Color'}
    window.wizard.processConfigCmd( cfg_data )
       
    cfg_data = {'type': 'Probe', 'point': [0.8, 0.5 ] }
    window.wizard.processConfigCmd( cfg_data )
    
#     
#     cfg_data = {'roi': roi, 'type': 'Subset'}
#     window.wizard.processConfigCmd( cfg_data )
    
    app.exec_()  
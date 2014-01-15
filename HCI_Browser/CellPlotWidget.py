'''
Created on Jan 13, 2014

@author: tpmaxwel
'''
from PyQt4 import QtCore, QtGui
import sys, vtk, os, cdms2
from ClusterCommunicator import control_message_signal
from vtkQtIntegration import QVTKClientWidget, VTK_BACKGROUND_COLOR

class WindowDisplayMode:
    Normal = 0
    Maximized = 1
    FullScreen = 2

class CellPlotWidget( QtGui.QWidget ):
    
    def __init__(self, parent, hcomm, **args ):  
        super( CellPlotWidget, self ).__init__( parent ) 
        self.comm = hcomm
        self.filepath = None
        self.varname = None
        self.roi = None
        self.file = None
        self.var = None
        self.buildCanvas()
        if self.comm: 
            self.comm.connect( hcomm, control_message_signal, self.processConfigCmd )
            self.comm.start()
        
    def processConfigCmd( self, msg ):
        print " CellPlotWidget: Process Config Cmd: ", str( msg )
        if msg['type'] == 'Quit': 
            self.terminate()
            self.parent().close()
        elif msg['type'] == 'Config': 
            self.processConfigData( msg['data'] )   
                
    def processConfigData( self, config_data ):   
        global_config = config_data.get('global', None )
        if global_config:
            self.roi = global_config.get('roi',None)
            self.dir = global_config.get('dir',None)
        iproc = self.comm.rank
        group_data = config_data[ "c%d" % iproc ]
        if group_data:
            filename = group_data.get( 'file', None )
            if filename:
                self.filepath = filename if ( self.dir == None ) else os.path.join( self.dir, filename )
                self.varname = group_data.get(  'var', None )
                self.initData()
            
    def initData(self):
        self.file = cdms2.open( self.filepath, 'r' ) 
        if self.varname:
            self.var = self.file[ self.varname ] 
            print "Initialized variable %s from file %s"  % ( self.varname, self.filepath )  
        
    def buildCanvas(self):
        top_level_layout = QtGui.QVBoxLayout() 
        self.setLayout(top_level_layout)
        self.cellWidget =  QVTKClientWidget(self)
        self.renWin = self.cellWidget.GetRenderWindow() 
        self.iren = self.renWin.GetInteractor()
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground( VTK_BACKGROUND_COLOR[0], VTK_BACKGROUND_COLOR[1], VTK_BACKGROUND_COLOR[2] )
        self.renWin.AddRenderer( self.renderer )
        top_level_layout.addWidget( self.cellWidget )

        self.UserControlledLookupTable = False
        self.ColorMap = vtk.vtkImageMapToColors()
        self.Reslice = vtk.vtkImageReslice()
        self.Reslice.TransformInputSamplingOff()     

        self.LookupTable = self.CreateDefaultLookupTable()        
        self.ColorMap.SetLookupTable(self.LookupTable)
        self.ColorMap.SetOutputFormatToRGBA()
        self.ColorMap.PassAlphaToOutputOn()
        
        texturePlaneMapper  = vtk.vtkPolyDataMapper()
        texturePlaneMapper.SetInput( self.PlaneSource.GetOutput() )

        self.TexturePlaneProperty  = vtk.vtkProperty()
        self.TexturePlaneProperty.SetAmbient(1)
        self.TexturePlaneProperty.SetInterpolationToFlat()
        
        self.Texture = vtk.vtkTexture()
        self.Texture.SetQualityTo32Bit()
        self.Texture.MapColorScalarsThroughLookupTableOff()
        self.Texture.SetInterpolate(self.TextureInterpolate)
        self.Texture.RepeatOff()
        self.Texture.SetLookupTable(self.LookupTable)
        
        self.TexturePlaneActor   = vtk.vtkActor()
        self.TexturePlaneActor.SetMapper(texturePlaneMapper)
        self.TexturePlaneActor.SetTexture(self.Texture)
        self.TexturePlaneActor.PickableOn()

        scalar_range = self.imageData.GetScalarRange()        
        if (  not self.UserControlledLookupTable ):       
            self.LookupTable.SetTableRange( scalar_range[0], scalar_range[1] )
            self.LookupTable.Build()            
        self.Reslice.SetInput(self.ImageData)
        self.Reslice.Modified()                
        self.ColorMap.SetInput(self.Reslice.GetOutput())       
        self.Texture.SetInput(self.ColorMap.GetOutput())
#        self.Texture.SetInterpolate(self.TextureInterpolate)

        self.renderer.AddViewProp(self.TexturePlaneActor)    
        self.TexturePlaneActor.SetProperty(self.TexturePlaneProperty)        
        self.TexturePlaneActor.PickableOn()

    def terminate(self):
        self.file.close()
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
'''
Created on Jan 13, 2014

@author: tpmaxwel
'''
from PyQt4 import QtGui
import sys, vtk, os, cdms2
import vtk.util.vtkImageImportFromArray as vtkUtil
from ClusterCommunicator import control_message_signal
from NcImageDataReader import CDMSDataset, ImageDataReader
from ColormapManager import ColorMapManager
from vtkQtIntegration import QVTKClientWidget, VTK_BACKGROUND_COLOR
from ImageDataSlicer import DataSlicer

VTK_NEAREST_RESLICE = 0
VTK_LINEAR_RESLICE  = 1
VTK_CUBIC_RESLICE   = 2

class WindowDisplayMode:
    Normal = 0
    Maximized = 1
    FullScreen = 2

class CellPlotWidget( QtGui.QWidget ):
    
    def __init__(self, parent, hcomm, **args ):  
        super( CellPlotWidget, self ).__init__( parent ) 
        self.TextureInterpolate = 1
        self.ResliceInterpolate = VTK_LINEAR_RESLICE
        self.UserControlledLookupTable= 0
        self.comm = hcomm
        self.cellWidget = None
        self.filepath = None
        self.varname = None
        self.roi = None
        self.iTimeIndex = 0
#        self.ResliceAxes   = vtk.vtkMatrix4x4()   
        if self.comm: 
            self.comm.connect( hcomm, control_message_signal, self.processConfigCmd )
            self.comm.start()

    def CreateDefaultLookupTable(self):    
        lut  = vtk.vtkLookupTable()
        lut.SetNumberOfColors( 256 )
        lut.SetHueRange( 0, 1 )
        lut.SetSaturationRange( 0, 1 )
        lut.SetValueRange( 0 , 1 )
        lut.SetAlphaRange( 1, 1 )
        lut.Build()
        return lut
            
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
                if values:
                    print " Slider Moved: %s " % str( values )
#                sval = float( values[0] ) if values else None
                    self.positionSlice( slice_index, values[0], values[1] )
                                
    def processConfigData( self, config_data ):   
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
                    self.positionSlice( 0, 0.5, 180.0 )
                else: print>>sys.stderr, "Error, no dataset declared for cell %d " % iproc
#            self.initData()
            
#     def initData(self):
#         self.dset = CDMSDataset() 
#         if self.dset_id:
#             varSpec = "%s*%s" % ( self.dset_id, self.varname )
#             self.dset.setVariableRecord( "VariableName0", varSpec )
#             self.dset.addDatasetRecord( self.dset_id, self.filepath )
#             self.dset.setReferenceVariable( varSpec )
#             self.reader = ImageDataReader( self.comm.rank )
#             self.reader.execute( self.dset )
#             print "Read Image Data: %s " % str( self.reader.result.keys() )
#             self.imageData = self.reader.result.get( 'volume', None )
#             if self.imageData: self.Reslice.SetInput( self.imageData )

    def positionSlice( self, iAxis, slider_pos, coord_value ):
        print "Plotting Slice[%d]: %.2f %.2f" % ( iAxis, slider_pos, coord_value )
        self.slicedImageData =  self.dataSlicer.getSlice( iAxis, self.iTimeIndex, slider_pos, coord_value ) 
        if  self.slicedImageData <> None:      
            self.vtkImageImporter.SetArray( self.slicedImageData )
            self.vtkImageImporter.Update()        
            self.renWin.Render()     
     
    def buildCanvas(self):
        if self.cellWidget <> None: return
        top_level_layout = QtGui.QVBoxLayout() 
        self.setLayout(top_level_layout)
        self.cellWidget =  QVTKClientWidget(self)
        self.renWin = self.cellWidget.GetRenderWindow() 
        self.iren = self.renWin.GetInteractor()
        interactorStyle = vtk.vtkInteractorStyleTerrain()
        self.iren.SetInteractorStyle( interactorStyle )
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground( VTK_BACKGROUND_COLOR[0], VTK_BACKGROUND_COLOR[1], VTK_BACKGROUND_COLOR[2] )
        self.renWin.AddRenderer( self.renderer )
        top_level_layout.addWidget( self.cellWidget )
 
        self.UserControlledLookupTable = False
        self.ColorMap = vtk.vtkImageMapToColors()
#         self.Reslice = vtk.vtkImageReslice()
#         self.Reslice.TransformInputSamplingOff() 
#         self.Reslice.SetOutputDimensionality(2)  
#         self.Reslice.SetResliceAxesOrigin( 0, 0, 0 )
#         self.Reslice.SetResliceAxesDirectionCosines( 1, 0, 0, 0, 1, 0, 0, 0, 1 )  
        
        self.LookupTable = vtk.vtkLookupTable()
        self.colorMapManager = ColorMapManager( self.LookupTable ) 
        self.colorMapManager.load_lut('jet')
       
        self.ColorMap.SetLookupTable(self.LookupTable)
        self.ColorMap.SetOutputFormatToRGBA()
        self.ColorMap.PassAlphaToOutputOn()

        self.vtkImageImporter = vtkUtil.vtkImageImportFromArray()
        self.ColorMap.SetInput( self.vtkImageImporter.GetOutput() )  

        psize = [ 400.0, 400.0  ] 
        pbounds = [ 0.0, psize[0], 0.0, psize[1] ]  
        self.PlaneSource  = vtk.vtkPlaneSource()
        self.PlaneSource.SetXResolution(1)
        self.PlaneSource.SetYResolution(1)
        self.PlaneSource.SetOrigin(pbounds[0],pbounds[2], 0.0 )
        self.PlaneSource.SetPoint1(pbounds[1],pbounds[2], 0.0 )
        self.PlaneSource.SetPoint2(pbounds[0],pbounds[3], 0.0 )
         
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
 
#         scalar_range = self.imageData.GetScalarRange()        
#         if (  not self.UserControlledLookupTable ):       
#             self.LookupTable.SetTableRange( scalar_range[0], scalar_range[1] )
#             self.LookupTable.Build()   
                 
#        self.Reslice.Modified()                
        self.Texture.SetInput(self.ColorMap.GetOutput())
        self.Texture.SetInterpolate(self.TextureInterpolate)
 
        self.renderer.AddViewProp(self.TexturePlaneActor)    
        self.TexturePlaneActor.SetProperty(self.TexturePlaneProperty)        
        self.TexturePlaneActor.PickableOn()

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
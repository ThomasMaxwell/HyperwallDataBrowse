'''
Created on Jan 13, 2014

@author: tpmaxwel
'''

from PyQt4 import QtCore, QtGui
from ROISelection import ROISelectionWidget
from PointSelection import PointSelectionWidget
import sys

class LabeledSliderWidget( QtGui.QWidget ):
    
    def __init__(self, index, label, **args ):  
        super( LabeledSliderWidget, self ).__init__()
        top_level_layout = QtGui.QVBoxLayout() 
        self.setLayout(top_level_layout)
        slider_layout = QtGui.QHBoxLayout()
        top_level_layout.addLayout(slider_layout)
        self.cparm = args.get( 'cparm', None )
        self.maxValue =  1000 
        self.minValue =  0 
        self.tickInterval = 100
        self.scaledMaxValue = args.get( 'max_value', 1.0 )
        self.scaledMinValue = args.get( 'min_value', 0.0 )
        self.scaledInitValue = args.get( 'init_value', ( self.scaledMaxValue - self.scaledMinValue )/2.0 )
        self.useScaledValue = True
        self.slider_index = index
        self.title = label
        slider_layout.setMargin(2)
        label_font = QtGui.QFont( "Arial", 16, QtGui.QFont.Bold)
        slider_label = QtGui.QLabel( label  )
        slider_label.setFixedWidth( 80 )
        slider_label.setFont( label_font )
        slider_layout.addWidget( slider_label  ) 
        
        self.slider = QtGui.QSlider( QtCore.Qt.Horizontal )
        self.slider.setRange( int(self.minValue), int(self.maxValue) ) 
        self.slider.setTickPosition( QtGui.QSlider.TicksBelow )
        self.slider.setTickInterval ( self.tickInterval )
        fvalue = ( self.scaledInitValue - self.scaledMinValue ) / float( self.scaledMaxValue - self.scaledMinValue )
        self.initValue = int( round( self.minValue + fvalue * ( self.maxValue - self.minValue ) ) )
        self.slider.setValue( int( self.initValue ) )
        self.current_slider_pos = self.initValue
        self.connect( self.slider, QtCore.SIGNAL('valueChanged(int)'), self.sliderMoved )
        self.connect( self.slider, QtCore.SIGNAL('sliderPressed()'), self.configStart )
        self.connect( self.slider, QtCore.SIGNAL('sliderReleased()'), self.configEnd )
        slider_label.setBuddy( self.slider )
        
        tick_label_font = QtGui.QFont( "Arial", 10, QtGui.QFont.Bold)
        slider_container = QtGui.QVBoxLayout() 
        slider_container.addWidget( self.slider  )
        tick_label_layout = QtGui.QHBoxLayout() 
        slider_container.addLayout(tick_label_layout)        
        min_value_label = QtGui.QLabel( "%.2f" % self.scaledMinValue  )
        min_value_label.setFont(tick_label_font)
        tick_label_layout.addWidget( min_value_label  ) 
        tick_label_layout.addStretch()
        max_value_label = QtGui.QLabel( "%.2f" % self.scaledMaxValue  )
        max_value_label.setFont(tick_label_font)
        tick_label_layout.addWidget( max_value_label  ) 
        
        slider_layout.addSpacing ( 20 )
        slider_layout.addLayout( slider_container  )
        slider_layout.addSpacing( 20 )
         
        self.value_pane = QtGui.QLabel( "%6.2f" % self.getCoordinateValue()  )   
        self.value_pane.setFrameStyle( QtGui.QFrame.StyledPanel | QtGui.QFrame.Raised   )     
        self.value_pane.setLineWidth( 2 )
        self.value_pane.setFixedWidth( 60 )
        self.value_pane.setFixedHeight( 25 )
        self.value_pane.setStyleSheet("QLabel { background-color : white; color : black; }");
        slider_layout.addWidget( self.value_pane  ) 
        
        
    def getTitle(self):
        return self.title
        
    def setSliderValue( self, normailzed_slider_value ): 
        index_value = int( round( self.minValue + normailzed_slider_value * ( self.maxValue - self.minValue ) ) )
        scaled_slider_value = self.scaledMinValue + normailzed_slider_value * ( self.scaledMaxValue - self.scaledMinValue )
        self.value_pane.setText( str( scaled_slider_value ) )
        self.slider.setValue( index_value )   

    def getCoordinateValue( self, scaled_slider_value = None ):
        if scaled_slider_value == None: scaled_slider_value = self.getScaledValue()
        return self.scaledMinValue + scaled_slider_value * ( self.scaledMaxValue - self.scaledMinValue )
    
    def getScaledValue( self, slider_value = None ):
        slider_value = self.slider.value() if not slider_value else slider_value
        fvalue = ( slider_value - self.minValue ) / float( self.maxValue - self.minValue ) 
        return fvalue

    def sliderMoved( self, raw_slider_value ):
        coordinate_value = None
        if self.current_slider_pos <> raw_slider_value:
            scaled_slider_value = self.getScaledValue( raw_slider_value )
            coordinate_value = self.getCoordinateValue( scaled_slider_value )
            self.value_pane.setText( str( coordinate_value ) )
            self.emit( QtCore.SIGNAL('ConfigCmd'), 'Moved', self.slider_index, ( scaled_slider_value, coordinate_value ) )
            self.current_slider_pos = raw_slider_value
        return coordinate_value
    
    def isTracking(self):
        return self.slider.isSliderDown()
    
    def configStart( self ):
        self.emit( QtCore.SIGNAL('ConfigCmd'), 'Start', self.slider_index ) 

    def configEnd( self ):
        self.emit( QtCore.SIGNAL('ConfigCmd'), 'End', self.slider_index ) 

class SliceWidget(QtGui.QWidget):

    def __init__( self, parent, hcomm ):
        super( SliceWidget, self ).__init__( parent ) 
        self.widgets = {}
        self.comm = hcomm
        self.point = None
        self.createTabLayout()
        self.leveling_tab_index, tab_layout = self.addTab( 'Slice Controls' )
        self.sLonIndex = self.addSlider( "Longitude", tab_layout , min_value=0, max_value=360, init_value=180 )
        self.sLatIndex = self.addSlider( "Latitude", tab_layout , min_value=-90, max_value=90, init_value=0 )
        self.sLevIndex = self.addSlider( "Level", tab_layout , min_value=0, max_value=100, init_value=0 )
        self.sTimeIndex = self.addSlider( "Time", tab_layout , min_value=0, max_value=100, init_value=0 )
        self.probe_tab_index, probe_tab_layout = self.addTab( 'Probe' )
        self.addProbeWidget( probe_tab_layout )
        self.probe_tab_index, probe_tab_layout = self.addTab( 'ROI' )
        self.addROIWidget( probe_tab_layout )
#        print "Starting SliceWidget, rank = %d, nproc = %d" % ( self.comm.rank, self.comm.size )

    def addProbeWidget( self, layout ):
        self.pointSelector = PointSelectionWidget([5,3])
        layout.addWidget( self.pointSelector )
        self.pointSelector.setSelectionCallback( self.setPoint )

    def addROIWidget( self, layout ):
        self.roiSelector = ROISelectionWidget(self)
        layout.addWidget( self.roiSelector )
        self.connect( self.roiSelector, QtCore.SIGNAL('roiSelected()'), self.setPoint )

    def setPoint(self, rel_point):
        self.point = rel_point
        print "Relative Selection Point: ", str( self.point )    
        if self.comm:
            self.comm.post( { 'type': 'Probe', 'point' : self.point } )
            
    def addSlider(self, label, layout, **args ):
        slider_index = len( self.widgets ) 
        slider = LabeledSliderWidget( slider_index, label, **args )
        self.connect( slider, QtCore.SIGNAL('ConfigCmd'), self.processSliderConfigCmd )
        layout.addWidget( slider  ) 
        self.widgets[slider_index] = slider
        return slider_index
    
    def processSliderConfigCmd( self, cmd, slider_index, values=None  ):
#        print "Slider[%d] Config Cmd ( %s ): %s " % ( slider_index, cmd, str(values) )
        if self.comm:
            self.comm.post( { 'type': 'Slider', 'index' : slider_index, 'cmd' : cmd, 'values' : values } )
        
    def processConfig( self, config_data ):
        if self.comm:
            self.comm.post( { 'type': 'Config',  'data' : config_data } )
    
    def updateTabPanel( self, index ):
        pass

    def addTab( self, tabname ):
        self.tabWidget.setEnabled(True)
        tabContents = QtGui.QWidget( self.tabWidget )
        layout = QtGui.QVBoxLayout()
        tabContents.setLayout(layout)
        tab_index = self.tabWidget.addTab( tabContents, tabname )
        return tab_index, layout
    
    def getCurrentTabIndex(self):
        return self.tabWidget.currentIndex() 

    def createTabLayout(self):
        if self.layout() == None:
            self.setLayout(QtGui.QVBoxLayout())
#             title_label = QtGui.QLabel( self.getName()  )
#             self.layout().addWidget( title_label  )
            self.tabWidget = QtGui.QTabWidget(self)
            self.layout().addWidget( self.tabWidget )
            self.connect( self.tabWidget,  QtCore.SIGNAL('currentChanged(int)'), self.updateTabPanel )
            self.addButtonLayout()
            self.setMinimumWidth(450)

    def addButtonLayout(self):
        self.buttonLayout = QtGui.QHBoxLayout()
        self.buttonLayout.setContentsMargins(-1, 3, -1, 3)
        
        self.btnOK = QtGui.QPushButton('OK')
        self.btnCancel = QtGui.QPushButton('Cancel')

        self.buttonLayout.addWidget(self.btnOK)
        self.buttonLayout.addWidget(self.btnCancel)
        
        self.layout().addLayout(self.buttonLayout)
        
        self.btnCancel.setShortcut('Esc')
        self.connect(self.btnOK, QtCore.SIGNAL('clicked(bool)'),      self.ok )
        self.connect(self.btnCancel, QtCore.SIGNAL('clicked(bool)'),  self.cancel )
        
    def ok(self):
        self.parent().close()

    def cancel(self):
        self.parent().close()

    def terminate(self):
        if self.comm: self.comm.stop()        
        self.close()
        
class SliceWidgetWindow(QtGui.QMainWindow):

    def __init__(self, comm = None, parent = None):
        QtGui.QMainWindow.__init__(self, parent)
        self.wizard = SliceWidget( self, comm )
        self.setCentralWidget(self.wizard)
        self.setWindowTitle("Hyperwall Data Browser")
        self.resize(1200,800)

    def terminate(self):
        self.wizard.terminate()
        self.close()
                
if __name__ == "__main__":
    app = QtGui.QApplication( ['Hyperwall Data Browser'] )
    window = SliceWidgetWindow()
    if len(sys.argv)>2 and sys.argv[1] == '-c':
        window.wizard.loadFromCommand(sys.argv[2:])
    window.show()
    app.exec_()  

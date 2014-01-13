'''
Created on Jan 13, 2014

@author: tpmaxwel
'''
from PyQt4 import QtCore, QtGui
import sys, vtk

class WindowDisplayMode:
    Normal = 0
    Maximized = 1
    FullScreen = 2

class CellPlotWidget( QtGui.QWidget ):
    
    def __init__(self, parent, index, **args ):  
        super( CellPlotWidget, self ).__init__( parent ) 
        self.buildCanvas()
        
    def buildCanvas(self):
        pass
       
class CellPlotWidgetWindow( QtGui.QMainWindow ):

    def __init__(self, parent = None):
        QtGui.QMainWindow.__init__(self, parent)
        self.wizard = CellPlotWidget( self, 0 )
        self.setCentralWidget(self.wizard)
        self.setWindowTitle("Hyperwall Cell")
        self.resize(500,400)
                
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
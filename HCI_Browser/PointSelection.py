'''
Created on Feb 10, 2014

@author: tpmaxwel
'''
from __future__ import division
import sys, copy 
from PyQt4.QtCore import *
from PyQt4.QtGui import *
#from HCI_Browser.MPL import getCellWidget

class CellButton( QPushButton ):
    
    selected_signal = SIGNAL("selected_signal")
    
    def __init__( self, label ):
        QPushButton.__init__(self, label )
        self.connect( self, SIGNAL('clicked(bool)'), self.selected )
        self.setCheckable(True)
        self.setChecked(False)
        
    def selected(self):
        self.setFocus( Qt.MouseFocusReason )
        self.emit( self.selected_signal, self.text() )
        
    def focusOutEvent ( self, event ):
        QPushButton.focusOutEvent( self, event )
        self.setChecked(False)

class MousePad( QFrame ):
    
    def __init__(self, dims, parent=None, **args ):
        QWidget.__init__( self, parent )
        self.setMinimumSize( dims[0], dims[1] )
        self.setStyleSheet("background-color:black;")
        self.setCursor( Qt.CrossCursor )
        self.dragCount = -1
        self.dragSkipIndex = 2
        
    def processEvent( self, event ):
        p = event.pos()
        s = self.size()
        rpos = [ p.x()/float( s.width() ),  1.0 - p.y()/float( s.height() ) ]; 
        self.emit( CellButton.selected_signal, rpos )

    def mousePressEvent( self, event ):
        QFrame.mousePressEvent( self, event )
        self.processEvent(event)
        self.dragCount = 0
        
    def mouseMoveEvent ( self, event  ):
        QFrame.mouseMoveEvent( self, event )
        if (self.dragCount >= 0):
            if (self.dragCount % self.dragSkipIndex) == 0:
                self.processEvent(event)
            self.dragCount = self.dragCount + 1
#        print "mousePressEvent: ", str( rpos )
#        gpos = event.globalPos()
        
    def mouseReleaseEvent ( self, event ):
        QFrame.mouseReleaseEvent( self, event )
        self.dragCount = -1
         
class PointSelectionWidget(QWidget):
    
    def __init__(self, spreadsheet_dims, parent=None, **args ):
        super(QWidget, self).__init__(parent)
        layout = QVBoxLayout()
        groupBox = QGroupBox("Cell Selection")
        self.cells = {}
        self.selected_cell = None
        layout.addWidget(groupBox)        
        cell_grid_layout = QGridLayout()
        cell_grid_layout.setSpacing( 0 )
        for ix in range( spreadsheet_dims[0] ):
            for iy in range( spreadsheet_dims[1] ):
                cellLabel = "%s%d" % ( str( (unichr( ord('A') + iy ) ) ), ix+1)
                pushButton = CellButton ( cellLabel )
                self.connect( pushButton, CellButton.selected_signal, self.cellSelected )
                cell_grid_layout.addWidget ( pushButton, ix, iy )
                self.cells[cellLabel] = pushButton
        groupBox.setLayout( cell_grid_layout )
        layout.addStretch()
#        self.cellWidget = getCellWidget(self) 
#        layout.addWidget( self.cellWidget )
        self.mousePad = MousePad( [ 600, 400 ] )
        layout.addWidget( self.mousePad )
        self.setLayout(layout)
        
    def cellSelected( self, cell_label ):
        self.selected_cell = str( cell_label )
        self.updateSelection()
        
    def updateSelection(self ):
        self.emit( CellButton.selected_signal, self.selected_cell )
        
    def setSelectionCallback( self, callback ):
        self.connect( self.mousePad, CellButton.selected_signal, callback )


class ExampleForm(QDialog):
 
    def __init__(self, parent=None):
        super(ExampleForm, self).__init__(parent)
        layout = QVBoxLayout()                
        roiSelector = PointSelectionWidget( [ 3, 5 ], self.parent() )
        layout.addWidget(roiSelector)
        self.setLayout(layout)
        self.setWindowTitle("Point Selector")

if __name__ == '__main__':                                                
    app = QApplication(sys.argv)
    form = ExampleForm()

    rect = QApplication.desktop().availableGeometry()
    form.resize( 300, 150 )
    form.show()
    app.exec_()
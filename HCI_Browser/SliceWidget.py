'''
Created on Jan 13, 2014

@author: tpmaxwel
'''

from PyQt4 import QtCore, QtGui
import sys

class SliceWidget(QtGui.QWidget):

    def __init__( self ):
        super( SliceWidget, self ).__init__() 
        self.createTabLayout()
        self.addTab('Data Slice Controls')
        
    def loadFromCommand( self, config_file_path ):
        pass
    
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
        pass

    def cancel(self):
        pass
        
class SliceWidgetWindow(QtGui.QMainWindow):

    def __init__(self, parent = None):
        QtGui.QMainWindow.__init__(self, parent)
        self.wizard = SliceWidget()
        self.setCentralWidget(self.wizard)
        self.setWindowTitle("Hyperwall Data Browser")
        self.resize(1000,600)
                
if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = SliceWidgetWindow()
    if len(sys.argv)>2 and sys.argv[1] == '-c':
        window.wizard.loadFromCommand(sys.argv[2:])
    window.show()
    app.exec_()
        
        
if __name__ == '__main__': 
    
    app = QtGui.QApplication(['ImageSlicerTest'])
     
    w = SliceWidgetWindow()    
    
    app.exec_()   

'''
Created on Jan 14, 2014

@author: tpmaxwel
'''
from PyQt4 import QtCore, QtGui
import ClusterCommunicator
from SliceWidget import SliceWidgetWindow
from CellPlotWidget import CellPlotWidgetWindow
import sys

if __name__ == "__main__":
    app = QtGui.QApplication( ['Hyperwall Data Browser'] )
    hcomm = ClusterCommunicator.getHComm()
    
    if hcomm.rank == 0:
        window = SliceWidgetWindow( hcomm )
        if len(sys.argv)>2 and sys.argv[1] == '-c':
            window.wizard.loadFromCommand(sys.argv[2:])
        app.connect( app, QtCore.SIGNAL("aboutToQuit()"), window.terminate ) 
        window.show()
    else:
        window = CellPlotWidgetWindow( hcomm )
        app.connect( app, QtCore.SIGNAL("aboutToQuit()"), window.terminate ) 
        window.show()
    
    app.exec_()  
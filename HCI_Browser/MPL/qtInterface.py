import sys, os, random
from PyQt4 import QtGui, QtCore

from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure, SubplotParams

progname = "Hyperwall Cell Plot"
progversion = "0.1"


class qtMplCanvas(FigureCanvas):
    
    """Ultimately, this is a QWidget (as well as a FigureCanvasAgg, etc.)."""
    def __init__( self, parent=None, **kwargs ): 
#        fig = Figure(figsize=(width, height), dpi=dpi) # , width=5, height=4, dpi=100, **kwargs):
        fig = Figure( subplotpars=SubplotParams(left=0.05, right=0.95, bottom=0.05, top=0.95 ) )
        self.axes = fig.add_subplot(111)    
        self.axes.hold(False)                   # We want the axes cleared every time plot() is called    
        self.compute_initial_figure()
        FigureCanvas.__init__(self, fig)
        self.setParent(parent)
        FigureCanvas.setSizePolicy(self, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        timestep = kwargs.get( 'timestep', None )
        if timestep:
            self.timer = QtCore.QTimer(self)
            QtCore.QObject.connect(self.timer, QtCore.SIGNAL("timeout()"), self.update_figure)
            self.timer.start(1000)

    def compute_initial_figure(self):
        pass

    def update_figure(self):   
        pass


class qtSampleMplCanvas(qtMplCanvas):

    def __init__(self, *args, **kwargs):
        qtMplCanvas.__init__(self, *args, **kwargs)

    def compute_initial_figure(self):   # Override in subclass
        pass

    def update_figure(self):    # Override in subclass
        l = [ random.randint(0, 10) for i in range(4) ]
        self.axes.plot([0, 1, 2, 3], l, 'r')
        self.draw()


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
        
    def generateContent(self): 
        pass

class qtSampleApplicationWindow(qtApplicationWindow):

    def generateContent(self): # Override in subclass 
        l = QtGui.QVBoxLayout(self.main_widget)
        sc = qtSampleMplCanvas(self.main_widget, width=5, height=4, dpi=100, timestep=1000)
        l.addWidget(sc)

if __name__ == '__main__':
    
    qApp = QtGui.QApplication(sys.argv)
    
    aw = qtSampleApplicationWindow()
    aw.setWindowTitle("%s" % progname)
    aw.show()
    sys.exit(qApp.exec_())
#qApp.exec_()

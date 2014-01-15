'''
Created on Jan 14, 2014

@author: tpmaxwel
'''
from PyQt4 import QtCore, QtGui
import ClusterCommunicator
from SliceWidget import SliceWidgetWindow
from CellPlotWidget import CellPlotWidgetWindow
import sys, os
from Utilities import *

class ConfigFileParser( QtCore.QObject ):
    
    def __init__ (self, configFilePath ):
        self.config_file = open( os.path.expanduser(configFilePath), 'r' )
        self.cats = {}
        self.current_cat = None
        self.parse()
        
    def parse(self):
        while True:
            line = self.config_file.readline()
            if not line: break
            else: line = line.strip()
            if line:
                if line[0] == '[': 
                    self.addCategory( line.strip('[] \t').lower() )
                else:
                    toks = line.split('=')
                    if len( toks ) == 2:
                        self.addField( toks[0].strip().lower(), toks[1].strip() )
                    
    def addCategory( self, cat_name ):
        if cat_name in self.cats:
            self.current_cat = self.cats[ cat_name ]
        else:
            self.current_cat = {}
            self.cats[ cat_name ] = self.current_cat
            
    def addField( self, name, value ):
        if self.current_cat == None: self.addCategory( 'global' )
        vlist = value.split(',')
        self.current_cat[ name ] = value if isList( vlist ) else [ val.strip() for val in vlist ]  
        
    def data(self): 
        return self.cats     

if __name__ == "__main__":
    app = QtGui.QApplication( ['Hyperwall Data Browser'] )
    hcomm = ClusterCommunicator.getHComm()
    
    if hcomm.rank == 0:
        window = SliceWidgetWindow( hcomm )
        if len(sys.argv)>2 and sys.argv[1] == '-c':
            config = ConfigFileParser( sys.argv[2] )
            window.wizard.processConfig( config.data() )
        app.connect( app, QtCore.SIGNAL("aboutToQuit()"), window.terminate ) 
        window.show()
    else:
        window = CellPlotWidgetWindow( hcomm )
        app.connect( app, QtCore.SIGNAL("aboutToQuit()"), window.terminate ) 
        window.show()
    
    app.exec_()  
'''
Created on Jan 13, 2014

@author: tpmaxwel
'''

from PyQt4 import QtCore, QtGui
from mpi4py import MPI
import time

control_message_signal = QtCore.SIGNAL("ControlMsg")

class HControllerComm( QtCore.QObject ):

    def __init__(self, comm, **args ): 
        super( HControllerComm, self ).__init__()      
        self.comm = comm
        self.rank = self.comm.Get_rank()
        self.size = self.comm.Get_size()
        assert self.rank == 0, "Controller rank ( %d ) must be 0" % self.rank
        
    def post(self, msg_object ):
        self.comm.bcast( msg_object, root = 0 )
                
    def start(self):
        pass

    def stop(self):
        self.post( { 'type' : 'Quit' } )        

class QMessage( QtCore.QThread ):
    
    def __init__(self, mdata ): 
        super( QMessage, self ).__init__()   
        self.type = mdata.get( 'type', None )
        self.items = mdata
        
    def __getitem__(self, key):
        return self.items.get( key, None )
        
    
class HCellComm( QtCore.QThread ):

    def __init__(self, comm, **args ): 
        super( HCellComm, self ).__init__()      
        self.comm = comm
        self.rank = self.comm.Get_rank()
        self.size = self.comm.Get_size()
        self.sleepTime = 0.01
        self.active = True
        assert self.rank <> 0, "Cell rank must not be 0" 
        
    def stop(self):
        self.active = False
        
    def run(self):
        while self.active:
            msg = None
            msg = self.comm.bcast( msg, root = 0 )
#            print "HCellComm-> message received: ", str( msg )
            self.emit( control_message_signal, msg )
            if msg[ 'type' ] == 'Quit': 
                self.stop()               
            else: 
                time.sleep( self.sleepTime )
            
def getHComm():
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()    
    hcomm = HControllerComm(comm) if ( rank == 0 ) else HCellComm( comm )    
    return hcomm

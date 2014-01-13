'''
Created on Jan 13, 2014

@author: tpmaxwel
'''

from PyQt4 import QtCore, QtGui
from mpi4py import MPI
comm = MPI.COMM_WORLD

class DistributedModule( QtCore.QObject ):

    def __init__(self, **args ):      
        self.rank = comm.Get_rank()
        
    def message( self, msg = None ):
        if self.rank == 0:
            comm.send( msg, dest=1, tag=11 )
        else:
            data = comm.recv( source=0, tag=11 )


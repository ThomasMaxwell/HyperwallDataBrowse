HyperwallDataBrowse
===================

Enables easy distributed browsing of xyzt climate datasets on hyperwall using adjustable slices in any of the 4 dimensions.

Example execution:

mpiexec -np 2 -hostfile ~/mpi.hosts python DistributedApplication.py -c ../config/HyperwallDataBrowse.office1.txt
         
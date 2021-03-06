from PyQt4 import QtCore, QtGui
import sys, vtk, datetime, platform
import types, sip

VTK_BACKGROUND_COLOR = [ 0, 0, 0 ]

AsciiToKeySymTable = ( None, None, None, None, None, None, None,
                       None, None,
                       "Tab", None, None, None, None, None, None,
                       None, None, None, None, None, None,
                       None, None, None, None, None, None,
                       None, None, None, None,
                       "space", "exclam", "quotedbl", "numbersign",
                       "dollar", "percent", "ampersand", "quoteright",
                       "parenleft", "parenright", "asterisk", "plus",
                       "comma", "minus", "period", "slash",
                       "0", "1", "2", "3", "4", "5", "6", "7",
                       "8", "9", "colon", "semicolon", "less", "equal",
                       "greater", "question",
                       "at", "A", "B", "C", "D", "E", "F", "G",
                       "H", "I", "J", "K", "L", "M", "N", "O",
                       "P", "Q", "R", "S", "T", "U", "V", "W",
                       "X", "Y", "Z", "bracketleft",
                       "backslash", "bracketright", "asciicircum",
                       "underscore",
                       "quoteleft", "a", "b", "c", "d", "e", "f", "g",
                       "h", "i", "j", "k", "l", "m", "n", "o",
                       "p", "q", "r", "s", "t", "u", "v", "w",
                       "x", "y", "z", "braceleft", "bar", "braceright",
                       "asciitilde", "Delete",
                       None, None, None, None, None, None, None, None, 
                       None, None, None, None, None, None, None, None,
                       None, None, None, None, None, None, None, None,
                       None, None, None, None, None, None, None, None,
                       None, None, None, None, None, None, None, None,
                       None, None, None, None, None, None, None, None,
                       None, None, None, None, None, None, None, None,
                       None, None, None, None, None, None, None, None, 
                       None, None, None, None, None, None, None, None, 
                       None, None, None, None, None, None, None, None,
                       None, None, None, None, None, None, None, None,
                       None, None, None, None, None, None, None, None,
                       None, None, None, None, None, None, None, None,
                       None, None, None, None, None, None, None, None,
                       None, None, None, None, None, None, None, None,
                       None, None, None, None, None, None, None, None)

def XDestroyWindow(displayId, windowId):
    """ XDestroyWindow(displayId: void_p_str, windowId: void_p_str) -> None
    Destroy the X window specified by two strings displayId and
    windowId containing void pointer string of (Display*) and (Window)    
    type.
    This is specific for VTKCell to remove the top shell window. Since
    VTK does not expose X11-related functions to Python, we have to
    use ctypes to hi-jack X11 library and call XDestroyWindow to kill
    the top-shell widget after reparent the OpenGL canvas to another
    Qt widget
    
    """
    import ctypes
#     ctypes = core.bundles.pyimport.py_import('ctypes',
#                                              {'linux-ubuntu':
#                                               'python-ctypes'})
    c_void_p = ctypes.c_void_p
    displayPtr = c_void_p(int(displayId[1:displayId.find('_void_p')], 16))
    windowPtr = c_void_p(int(windowId[1:windowId.find('_void_p')], 16))
    CDLL = ctypes.CDLL
    libx = CDLL('libX11.so.6')
    libx.XDestroyWindow(displayPtr, windowPtr)
    
class qt_super(object):

    def __init__(self, class_, obj):
        self._class = class_
        self._obj = obj

    def __getattr__(self, attr):
        s = super(self._class, self._obj)
        try:
            return getattr(s, attr)
        except AttributeError, e:
            mro = type(self._obj).mro()
            try:
                ix = mro.index(self._class)
            except ValueError:
                raise TypeError("qt_super: obj must be an instance of class")
            
            for class_ in mro[ix+1:]:
                try:
                    unbound_meth = getattr(class_, attr)
                    return types.MethodType(unbound_meth, self._obj, class_)
                except AttributeError:
                    pass
            raise e

class QCellWidget(QtGui.QWidget):
    """
    QCellWidget is the base cell class. All types of spreadsheet cells
    should inherit from this.
    
    """

    def __init__(self, parent=None, flags=QtCore.Qt.WindowFlags()):
        """ QCellWidget(parent: QWidget) -> QCellWidget
        Instantiate the cell and helper properties
        
        """
        QtGui.QWidget.__init__(self, parent, flags)
        self._historyImages = []
        self._player = QtGui.QLabel(self.parent())
        self._player.setAutoFillBackground(True)
        self._player.setFocusPolicy(QtCore.Qt.NoFocus)
        self._player.setScaledContents(True)
        self._playerTimer = QtCore.QTimer()        
        self._playerTimer.setSingleShot(True)
        self._currentFrame = 0
        self._playing = False
        self._capturingEnabled = False
#         self.connect(self._playerTimer, QtCore.SIGNAL('timeout()'), self.playNextFrame)
#         if getattr(get_vistrails_configuration(),'fixedSpreadsheetCells',False):
#             self.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
#             self.setFixedSize(200, 180)
            
    SENDING_EVENTS = False
    def event(self, e):
        """ event(e: QEvent) -> depends on event type
        Process window and interaction events. 
        
        """
        
        #send events to all selected cells, to support linked interaction
        if e.type() in [QtCore.QEvent.MouseMove, 
                        QtCore.QEvent.MouseButtonPress,
                        QtCore.QEvent.MouseButtonRelease]:
            if not QCellWidget.SENDING_EVENTS:
                QCellWidget.SENDING_EVENTS = True
                try:
                    for cell in self.getSelectedCellWidgets():
                        if cell is not self: 
                            cell.event(e)
                finally:
                    QCellWidget.SENDING_EVENTS = False
        
        return qt_super(QCellWidget, self).event(e)
    

    def getSelectedCellWidgets(self):
        sheet = self.findSheetTabWidget()
        if sheet:
            return [sheet.getCell(row, col) \
                    for (row, col) in sheet.getSelectedLocations()]
        return []

    def findSheetTabWidget(self):
        """ findSheetTabWidget() -> QTabWidget
        Find and return the sheet tab widget
        
        """
        p = self.parent()
        while p:
            if hasattr(p, 'isSheetTabWidget'):
                if p.isSheetTabWidget()==True:
                    return p
            p = p.parent()
        return None

    def setAnimationEnabled(self, enabled):
        """ setAnimationEnabled(enabled: bool) -> None
        
        """
        self._capturingEnabled = enabled
        if not enabled:
            self.clearHistory()
        
    def saveToPNG(self, filename):
        """ saveToPNG(filename: str) -> None        
        Abtract function for saving the current widget contents to an
        image file
        
        """



    def deleteLater(self):
        """ deleteLater() -> None        
        Make sure to clear history and delete the widget
        
        """
        self.clearHistory()
        QtGui.QWidget.deleteLater(self)

    def updateContents(self, inputPorts):
        """ updateContents(inputPorts: tuple)
        Make sure to capture to history
        
        """
        # Capture window into history for playback
        if self._capturingEnabled:
            self.saveToHistory()

    def resizeEvent(self, e):
        """ resizeEvent(e: QEvent) -> None
        Re-adjust the player widget
        
        """
        QtGui.QWidget.resizeEvent(self, e)

        if self._player.isVisible():
            self._player.setGeometry(self.geometry())

    def setPlayerFrame(self, frame):
        """ setPlayerFrame(frame: int) -> None
        Set the player to display a particular frame number
        
        """
        if (len(self._historyImages)==0):
            return
        if frame>=len(self._historyImages):
            frame = frame % len(self._historyImages)
        if frame>=len(self._historyImages):
            return
        self._player.setPixmap(QtGui.QPixmap(self._historyImages[frame]))

    def startPlayer(self):
        """ startPlayer() -> None
        Adjust the size of the player to the cell and show it
        
        """
        if not self._capturingEnabled:
            return
        self._player.setParent(self.parent())
        self._player.setGeometry(self.geometry())
        self._player.raise_()
        self._currentFrame = -1
        self.playNextFrame()
        self._player.show()
        self.hide()
        self._playing = True
        
    def stopPlayer(self):
        """ startPlayer() -> None
        Adjust the size of the player to the cell and show it
        
        """
        if not self._capturingEnabled:
            return
        self._playerTimer.stop()
        self._player.hide()
        self.show()
        self._playing = False

    def showNextFrame(self):
        """ showNextFrame() -> None
        Display the next frame in the history
        
        """
        self._currentFrame += 1
        if self._currentFrame>=len(self._historyImages):
            self._currentFrame = 0
        self.setPlayerFrame(self._currentFrame)
        
    def playNextFrame(self):
        """ playNextFrame() -> None        
        Display the next frame in the history and start the timer for
        the frame after
        
        """
        self.showNextFrame()
        self._playerTimer.start(100)

    def grabWindowPixmap(self):
        """ grabWindowPixmap() -> QPixmap
        Widget special grabbing function
        
        """
        return QtGui.QPixmap.grabWidget(self)

    def dumpToFile(self, filename):
        """ dumpToFile(filename: str, dump_as_pdf: bool) -> None
        Dumps itself as an image to a file, calling grabWindowPixmap """
        pixmap = self.grabWindowPixmap()
        pixmap.save(filename,"PNG")
            
    def saveToPDF(self, filename):
        printer = QtGui.QPrinter()

        printer.setOutputFormat(QtGui.QPrinter.PdfFormat)
        printer.setOutputFileName(filename)
        pixmap = self.grabWindowPixmap()
        size = pixmap.size()
        printer.setPaperSize(QtCore.QSizeF(size.width(), size.height()),
                             QtGui.QPrinter.Point)
        painter = QtGui.QPainter()
        painter.begin(printer)
        rect = painter.viewport()
        size.scale(rect.size(), QtCore.Qt.KeepAspectRatio)
        painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
        painter.setWindow(pixmap.rect())
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

class QVTKWidget(QCellWidget):
    """
    QVTKWidget is the actual rendering widget that can display
    vtkRenderer inside a Qt QWidget
    
    """
    def __init__(self, parent=None, f=QtCore.Qt.WindowFlags()):
        """ QVTKWidget(parent: QWidget, f: WindowFlags) -> QVTKWidget
        Initialize QVTKWidget with a toolbar with its own device
        context
        
        """
        QCellWidget.__init__(self, parent, f | QtCore.Qt.MSWindowsOwnDC)

        self.interacting = None
        self.mRenWin = None
        self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent)
        self.setAttribute(QtCore.Qt.WA_PaintOnScreen)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,
                                             QtGui.QSizePolicy.Expanding))
        self.iHandlers = []
        self.setAnimationEnabled(True)
        self.renderer_maps = {}
        
    def removeObserversFromInteractorStyle(self):
        """ removeObserversFromInteractorStyle() -> None        
        Remove all python binding from interactor style observers for
        safely freeing the cell
        
        """
        iren = self.mRenWin.GetInteractor()
        if iren:
            style = iren.GetInteractorStyle()
            style.RemoveObservers("InteractionEvent")
            style.RemoveObservers("EndPickEvent")
            style.RemoveObservers("CharEvent")
            style.RemoveObservers("MouseWheelForwardEvent")
            style.RemoveObservers("MouseWheelBackwardEvent")
        
    def addObserversToInteractorStyle(self):
        """ addObserversToInteractorStyle() -> None        
        Assign observer to the current interactor style
        
        """
        iren = self.mRenWin.GetInteractor()
        if iren:
            style = iren.GetInteractorStyle()
            style.AddObserver("InteractionEvent", self.interactionEvent)
            style.AddObserver("EndPickEvent", self.interactionEvent)
            style.AddObserver("CharEvent", self.charEvent)
            style.AddObserver("MouseWheelForwardEvent", self.interactionEvent)
            style.AddObserver("MouseWheelBackwardEvent", self.interactionEvent)

    def deleteLater(self):
        """ deleteLater() -> None        
        Make sure to free render window resource when
        deallocating. Overriding PyQt deleteLater to free up
        resources
        
        """
        self.renderer_maps = {}
        for ren in self.getRendererList():
            self.mRenWin.RemoveRenderer(ren)
            
        self.removeObserversFromInteractorStyle()
        
        self.updateContents(([], None, [], None, None))
        
        self.SetRenderWindow(None)

        QCellWidget.deleteLater(self)

    def updateContents(self, inputPorts):
        """ updateContents(inputPorts: tuple)
        Updates the cell contents with new vtkRenderer
        
        """
        renWin = self.GetRenderWindow()
        for iHandler in self.iHandlers:
            if iHandler.observer:
                iHandler.observer.vtkInstance.SetInteractor(None)
            iHandler.clear()

        # Remove old renderers first
        oldRenderers = self.getRendererList()
        for renderer in oldRenderers:
            renWin.RemoveRenderer(renderer)
            renderer.SetRenderWindow(None)
        del oldRenderers

        (renderers, renderView, self.iHandlers, iStyle, picker) = inputPorts
        if renderView:
            renderView.vtkInstance.SetupRenderWindow(renWin)
            renderers = [renderView.vtkInstance.GetRenderer()]
        self.renderer_maps = {}
        for renderer in renderers:
            if renderView==None:
                vtkInstance = renderer.vtkInstance
                renWin.AddRenderer(vtkInstance)
                self.renderer_maps[vtkInstance] = renderer.moduleInfo['moduleId']
            else:
                vtkInstance = renderer
            if hasattr(vtkInstance, 'IsActiveCameraCreated'):
                if not vtkInstance.IsActiveCameraCreated():
                    vtkInstance.ResetCamera()
                else:
                    vtkInstance.ResetCameraClippingRange()
            
        iren = renWin.GetInteractor()
        if picker:
            iren.SetPicker(picker.vtkInstance)
            
        # Update interactor style
        self.removeObserversFromInteractorStyle()
        if renderView==None:
            if iStyle==None:
                iStyleInstance = vtk.vtkInteractorStyleTrackballCamera()
            else:
                iStyleInstance = iStyle.vtkInstance
            iren.SetInteractorStyle(iStyleInstance)
        self.addObserversToInteractorStyle()
        
        for iHandler in self.iHandlers:
            if iHandler.observer:
                iHandler.observer.vtkInstance.SetInteractor(iren)
        renWin.Render()

        # Capture window into history for playback
        # Call this at the end to capture the image after rendering
        QCellWidget.updateContents(self, inputPorts)

    def GetRenderWindow(self):
        """ GetRenderWindow() -> vtkRenderWindow
        Return the associated vtkRenderWindow
        
        """
        if not self.mRenWin:
            win = vtk.vtkRenderWindow()
            win.DoubleBufferOn()
            self.SetRenderWindow(win)
            del win

        return self.mRenWin

    def SetRenderWindow(self,w):
        """ SetRenderWindow(w: vtkRenderWindow)        
        Set a new render window to QVTKWidget and initialize the
        interactor as well
        
        """
        if w == self.mRenWin:
            return
        
        systemType = platform.system()
        if self.mRenWin:
            if systemType!='Linux':
                self.mRenWin.SetInteractor(None)
            if self.mRenWin.GetMapped():
                self.mRenWin.Finalize()
            
        self.mRenWin = w
        
        if self.mRenWin:
            self.mRenWin.Register(None)
            if self.mRenWin.GetMapped():
                self.mRenWin.Finalize()
            if systemType=='Linux':
                try:
                    vp = '_%s_void_p' % (hex(int(QtGui.QX11Info.display()))[2:])
                except TypeError:
                    #This was change for PyQt4.2
                    if isinstance(QtGui.QX11Info.display(),QtGui.Display):
                        display = sip.unwrapinstance(QtGui.QX11Info.display())
                        vp = '_%s_void_p' % (hex(display)[2:])
                self.mRenWin.SetDisplayId(vp)
                self.resizeWindow(1,1)
            self.mRenWin.SetWindowInfo(str(int(self.winId())))
            if self.isVisible():
                self.mRenWin.Start()

            if not self.mRenWin.GetInteractor():
                iren = vtk.vtkRenderWindowInteractor()
                if systemType=='Darwin':
                    iren.InstallMessageProcOff()
                iren.SetRenderWindow(self.mRenWin)
                iren.Initialize()
                if systemType=='Linux':
                    XDestroyWindow(self.mRenWin.GetGenericDisplayId(), self.mRenWin.GetGenericWindowId())
                self.mRenWin.SetWindowInfo(str(int(self.winId())))
                self.resizeWindow(self.width(), self.height())
                self.mRenWin.SetPosition(self.x(), self.y())

    def GetInteractor(self):
        """ GetInteractor() -> vtkInteractor
        Return the vtkInteractor control this QVTKWidget
        """
        return self.GetRenderWindow().GetInteractor()

    def event(self, e):
        """ event(e: QEvent) -> depends on event type
        Process window and interaction events
        
        """
        if e.type()==QtCore.QEvent.ParentAboutToChange:
            if self.mRenWin:
                if self.mRenWin.GetMapped():
                    self.mRenWin.Finalize()
        else:
            if e.type()==QtCore.QEvent.ParentChange:
                if self.mRenWin:
                    self.mRenWin.SetWindowInfo(str(int(self.winId())))
                    if self.isVisible():
                        self.mRenWin.Start()
        
        if QtCore.QObject.event(self,e):
            return 1

        if e.type() == QtCore.QEvent.KeyPress:
            self.keyPressEvent(e)
            if e.isAccepted():
                return e.isAccepted()

        return qt_super(QVTKWidget, self).event(e)
        
        # return QtGui.QWidget.event(self,e)
        # Was this right? Wasn't this supposed to be QCellWidget.event()?

    def resizeWindow(self, width, height):
        """ resizeWindow(width: int, height: int) -> None
        Work around vtk bugs for resizing window
        
        """
        ########################################################
        # VTK - BUGGGGGGGGG - GRRRRRRRRR
        # This is a 'bug' in vtkWin32OpenGLRenderWindow(.cxx)
        # If a render window is mapped to screen, the actual
        # window size is the client area of the window in Win32.
        # However, this real window size is only updated through
        # vtkWin32OpenGLRenderWindow::GetSize(). So this has to
        # be called here to get the cell size correctly. This
        # invalidates the condition in the next SetSize().
        # We can use self.mRenWin.SetSize(0,0) here but it will
        # cause flickering and decrease performance!
        # SetPosition(curX,curY) also works here but slower.
        self.mRenWin.GetSize()
        
        self.mRenWin.SetSize(width, height)
        if self.mRenWin.GetInteractor():
            self.mRenWin.GetInteractor().SetSize(width, height)

    def resizeEvent(self, e):
        """ resizeEvent(e: QEvent) -> None
        Re-adjust the vtkRenderWindow size then QVTKWidget resized
        
        """
        qt_super(QVTKWidget, self).resizeEvent(e)
        if not self.mRenWin:
            return

        self.resizeWindow(self.width(), self.height())
        self.mRenWin.Render()

    def moveEvent(self,e):
        """ moveEvent(e: QEvent) -> None
        Echo the move event into vtkRenderWindow
        
        """
        qt_super(QVTKWidget, self).moveEvent(e)
        if not self.mRenWin:
            return

        self.mRenWin.SetPosition(self.x(),self.y())

    def paintEvent(self, e):
        """ paintEvent(e: QPaintEvent) -> None
        Paint the QVTKWidget with vtkRenderWindow
        
        """
        iren = None
        if self.mRenWin:
            iren = self.mRenWin.GetInteractor()

        if (not iren) or (not iren.GetEnabled()):
            return

        if hasattr(self.mRenWin, 'UpdateGLRegion'):
            self.mRenWin.UpdateGLRegion()
        self.mRenWin.Render()

    def SelectActiveRenderer(self,iren):
        """ SelectActiveRenderer(iren: vtkRenderWindowIteractor) -> None
        Only make the vtkRenderer below the mouse cursor active
        
        """
        epos = iren.GetEventPosition()
        rens = iren.GetRenderWindow().GetRenderers()
        rens.InitTraversal()
        for i in xrange(rens.GetNumberOfItems()):
            ren = rens.GetNextItem()
            ren.SetInteractive(ren.IsInViewport(epos[0], epos[1]))

    def mousePressEvent(self,e):
        """ mousePressEvent(e: QMouseEvent) -> None
        Echo mouse event to vtkRenderWindowwInteractor
        
        """
        iren = None
        if self.mRenWin:
            iren = self.mRenWin.GetInteractor()

        if (not iren) or (not iren.GetEnabled()):
            return

        ctrl = (e.modifiers()&QtCore.Qt.ControlModifier)
        isDoubleClick = e.type()==QtCore.QEvent.MouseButtonDblClick
        iren.SetEventInformationFlipY(e.x(),e.y(),
                                      ctrl,
                                      (e.modifiers()&QtCore.Qt.ShiftModifier),
                                      chr(0),
                                      isDoubleClick,
                                      None)
        invoke = {QtCore.Qt.LeftButton:"LeftButtonPressEvent",
                  QtCore.Qt.MidButton:"MiddleButtonPressEvent",
                  QtCore.Qt.RightButton:"RightButtonPressEvent"}

        self.SelectActiveRenderer(iren)

        if ctrl:
            e.ignore()
            return

        self.interacting = self.getActiveRenderer(iren)
        
        if e.button() in invoke:
            iren.InvokeEvent(invoke[e.button()])

    def mouseMoveEvent(self,e):
        """ mouseMoveEvent(e: QMouseEvent) -> None
        Echo mouse event to vtkRenderWindowwInteractor
        
        """
        iren = None
        if self.mRenWin:
            iren = self.mRenWin.GetInteractor()

        if (not iren) or (not iren.GetEnabled()):
            return

        iren.SetEventInformationFlipY(e.x(),e.y(),
                                      (e.modifiers()&QtCore.Qt.ControlModifier),
                                      (e.modifiers()&QtCore.Qt.ShiftModifier),
                                      chr(0), 0, None)

        iren.InvokeEvent("MouseMoveEvent")
                  
    def enterEvent(self,e):
        """ enterEvent(e: QEvent) -> None
        Echo mouse event to vtkRenderWindowwInteractor
        
        """
        iren = None
        if self.mRenWin:
            iren = self.mRenWin.GetInteractor()

        if (not iren) or (not iren.GetEnabled()):
            return

        iren.InvokeEvent("EnterEvent")

    def leaveEvent(self,e):
        """ leaveEvent(e: QEvent) -> None
        Echo mouse event to vtkRenderWindowwInteractor
        
        """
        iren = None
        if self.mRenWin:
            iren = self.mRenWin.GetInteractor()

        if (not iren) or (not iren.GetEnabled()):
            return

        iren.InvokeEvent("LeaveEvent")

    def mouseReleaseEvent(self,e):
        """ mouseReleaseEvent(e: QEvent) -> None
        Echo mouse event to vtkRenderWindowwInteractor
        
        """
        iren = None
        if self.mRenWin:
            iren = self.mRenWin.GetInteractor()

        if (not iren) or (not iren.GetEnabled()):
            return

        iren.SetEventInformationFlipY(e.x(),e.y(),
                                      (e.modifiers()&QtCore.Qt.ControlModifier),
                                      (e.modifiers()&QtCore.Qt.ShiftModifier),
                                      chr(0),0,None)

        invoke = {QtCore.Qt.LeftButton:"LeftButtonReleaseEvent",
                  QtCore.Qt.MidButton:"MiddleButtonReleaseEvent",
                  QtCore.Qt.RightButton:"RightButtonReleaseEvent"}

        self.interacting = None
        
        if e.button() in invoke:
            iren.InvokeEvent(invoke[e.button()])

    def keyPressEvent(self,e):
        """ keyPressEvent(e: QKeyEvent) -> None
        Disallow 'quit' key in vtkRenderWindowwInteractor and sync the others
        
        """
        iren = None
        if self.mRenWin:
            iren = self.mRenWin.GetInteractor()

        if (not iren) or (not iren.GetEnabled()):
            return

        ascii_key = None
        if e.text().length()>0:
            ascii_key = e.text().toLatin1()[0]
        else:
            ascii_key = chr(0)

        keysym = self.ascii_to_key_sym(ord(ascii_key))

        if not keysym:
            keysym = self.qt_key_to_key_sym(e.key())

        # Ignore 'q' or 'e' or Ctrl-anykey
        ctrl = (e.modifiers()&QtCore.Qt.ControlModifier)
        shift = (e.modifiers()&QtCore.Qt.ShiftModifier)
        if (keysym in ['q', 'e'] or ctrl):
            e.ignore()
            return
        
        iren.SetKeyEventInformation(ctrl,shift,ascii_key, e.count(), keysym)

        iren.InvokeEvent("KeyPressEvent")

        if ascii_key:
            iren.InvokeEvent("CharEvent")

        
    def keyReleaseEvent(self,e):
        """ keyReleaseEvent(e: QKeyEvent) -> None
        Disallow 'quit' key in vtkRenderWindowwInteractor and sync the others
        
        """
        iren = None
        if self.mRenWin:
            iren = self.mRenWin.GetInteractor()

        if (not iren) or (not iren.GetEnabled()):
            return

        ascii_key = None
        if e.text().length()>0:
            ascii_key = e.text().toLatin1()[0]
        else:
            ascii_key = chr(0)

        keysym = self.ascii_to_key_sym(ord(ascii_key))

        if not keysym:
            keysym = self.qt_key_to_key_sym(e.key())

        # Ignore 'q' or 'e' or Ctrl-anykey
        ctrl = (e.modifiers()&QtCore.Qt.ControlModifier)
        shift = (e.modifiers()&QtCore.Qt.ShiftModifier)
        if (keysym in ['q','e'] or ctrl):
            e.ignore()
            return
        
        iren.SetKeyEventInformation(ctrl, shift, ascii_key, e.count(), keysym)

        iren.InvokeEvent("KeyReleaseEvent")

    def wheelEvent(self,e):
        """ wheelEvent(e: QWheelEvent) -> None
        Zoom in/out while scrolling the mouse
        
        """
        iren = None
        if self.mRenWin:
            iren = self.mRenWin.GetInteractor()

        if (not iren) or (not iren.GetEnabled()):
            return

        iren.SetEventInformationFlipY(e.x(),e.y(),
                                      (e.modifiers()&QtCore.Qt.ControlModifier),
                                      (e.modifiers()&QtCore.Qt.ShiftModifier),
                                      chr(0),0,None)
        
        self.SelectActiveRenderer(iren)
        
        if e.delta()>0:
            iren.InvokeEvent("MouseWheelForwardEvent")
        else:
            iren.InvokeEvent("MouseWheelBackwardEvent")

    def focusInEvent(self,e):
        """ focusInEvent(e: QFocusEvent) -> None
        Ignore focus event
        
        """
        pass

    def focusOutEvent(self,e):
        """ focusOutEvent(e: QFocusEvent) -> None
        Ignore focus event
        
        """
        pass

    def contextMenuEvent(self,e):
        """ contextMenuEvent(e: QContextMenuEvent) -> None        
        Make sure to get the right mouse position for the context menu
        event, i.e. also the right click
        
        """
        iren = None
        if self.mRenWin:
            iren = self.mRenWin.GetInteractor()

        if (not iren) or (not iren.GetEnabled()):
            return

        ctrl = int(e.modifiers()&QtCore.Qt.ControlModifier)
        shift = int(e.modifiers()&QtCore.Qt.ShiftModifier)
        iren.SetEventInformationFlipY(e.x(),e.y(),ctrl,shift,chr(0),0,None)
        iren.InvokeEvent("ContextMenuEvent")

    def ascii_to_key_sym(self,i):
        """ ascii_to_key_sym(i: int) -> str
        Convert ASCII code into key name
        
        """
        return AsciiToKeySymTable[i]

    def qt_key_to_key_sym(self,i):
        """ qt_key_to_key_sym(i: QtCore.Qt.Keycode) -> str
        Convert Qt key code into key name
        
        """
        handler = {QtCore.Qt.Key_Backspace:"BackSpace",
                   QtCore.Qt.Key_Tab:"Tab",
                   QtCore.Qt.Key_Backtab:"Tab",
                   QtCore.Qt.Key_Return:"Return",
                   QtCore.Qt.Key_Enter:"Return",
                   QtCore.Qt.Key_Shift:"Shift_L",
                   QtCore.Qt.Key_Control:"Control_L",
                   QtCore.Qt.Key_Alt:"Alt_L",
                   QtCore.Qt.Key_Pause:"Pause",
                   QtCore.Qt.Key_CapsLock:"Caps_Lock",
                   QtCore.Qt.Key_Escape:"Escape",
                   QtCore.Qt.Key_Space:"space",
                   QtCore.Qt.Key_End:"End",
                   QtCore.Qt.Key_Home:"Home",
                   QtCore.Qt.Key_Left:"Left",
                   QtCore.Qt.Key_Up:"Up",
                   QtCore.Qt.Key_Right:"Right",
                   QtCore.Qt.Key_Down:"Down",
                   QtCore.Qt.Key_SysReq:"Snapshot",
                   QtCore.Qt.Key_Insert:"Insert",
                   QtCore.Qt.Key_Delete:"Delete",
                   QtCore.Qt.Key_Help:"Help",
                   QtCore.Qt.Key_0:"0",
                   QtCore.Qt.Key_1:"1",
                   QtCore.Qt.Key_2:"2",
                   QtCore.Qt.Key_3:"3",
                   QtCore.Qt.Key_4:"4",
                   QtCore.Qt.Key_5:"5",
                   QtCore.Qt.Key_6:"6",
                   QtCore.Qt.Key_7:"7",
                   QtCore.Qt.Key_8:"8",
                   QtCore.Qt.Key_9:"9",
                   QtCore.Qt.Key_A:"a",
                   QtCore.Qt.Key_B:"b",
                   QtCore.Qt.Key_C:"c",
                   QtCore.Qt.Key_D:"d",
                   QtCore.Qt.Key_E:"e",
                   QtCore.Qt.Key_F:"f",
                   QtCore.Qt.Key_G:"g",
                   QtCore.Qt.Key_H:"h",
                   QtCore.Qt.Key_I:"i",
                   QtCore.Qt.Key_J:"h",
                   QtCore.Qt.Key_K:"k",
                   QtCore.Qt.Key_L:"l",
                   QtCore.Qt.Key_M:"m",
                   QtCore.Qt.Key_N:"n",
                   QtCore.Qt.Key_O:"o",
                   QtCore.Qt.Key_P:"p",
                   QtCore.Qt.Key_Q:"q",
                   QtCore.Qt.Key_R:"r",
                   QtCore.Qt.Key_S:"s",
                   QtCore.Qt.Key_T:"t",
                   QtCore.Qt.Key_U:"u",
                   QtCore.Qt.Key_V:"v",
                   QtCore.Qt.Key_W:"w",
                   QtCore.Qt.Key_X:"x",
                   QtCore.Qt.Key_Y:"y",
                   QtCore.Qt.Key_Z:"z",
                   QtCore.Qt.Key_Asterisk:"asterisk",
                   QtCore.Qt.Key_Plus:"plus",
                   QtCore.Qt.Key_Minus:"minus",
                   QtCore.Qt.Key_Period:"period",
                   QtCore.Qt.Key_Slash:"slash",
                   QtCore.Qt.Key_F1:"F1",
                   QtCore.Qt.Key_F2:"F2",
                   QtCore.Qt.Key_F3:"F3",
                   QtCore.Qt.Key_F4:"F4",
                   QtCore.Qt.Key_F5:"F5",
                   QtCore.Qt.Key_F6:"F6",
                   QtCore.Qt.Key_F7:"F7",
                   QtCore.Qt.Key_F8:"F8",
                   QtCore.Qt.Key_F9:"F9",
                   QtCore.Qt.Key_F10:"F10",
                   QtCore.Qt.Key_F11:"F11",
                   QtCore.Qt.Key_F12:"F12",
                   QtCore.Qt.Key_F13:"F13",
                   QtCore.Qt.Key_F14:"F14",
                   QtCore.Qt.Key_F15:"F15",
                   QtCore.Qt.Key_F16:"F16",
                   QtCore.Qt.Key_F17:"F17",
                   QtCore.Qt.Key_F18:"F18",
                   QtCore.Qt.Key_F19:"F19",
                   QtCore.Qt.Key_F20:"F20",
                   QtCore.Qt.Key_F21:"F21",
                   QtCore.Qt.Key_F22:"F22",
                   QtCore.Qt.Key_F23:"F23",
                   QtCore.Qt.Key_F24:"F24",
                   QtCore.Qt.Key_NumLock:"Num_Lock",
                   QtCore.Qt.Key_ScrollLock:"Scroll_Lock"}
        if i in handler:            
            return handler[i]
        else:
            return "None"

    def getRendererList(self):
        """ getRendererList() -> list
        Return a list of vtkRenderer running in this QVTKWidget
        """
        result = []
        renWin = self.GetRenderWindow()
        renderers = renWin.GetRenderers()
        renderers.InitTraversal()
        for i in xrange(renderers.GetNumberOfItems()):
            result.append(renderers.GetNextItem())
        return result

    def getActiveRenderer(self, iren):
        """ getActiveRenderer(iren: vtkRenderWindowwInteractor) -> vtkRenderer
        Return the active vtkRenderer under mouse
        
        """
        epos = list(iren.GetEventPosition())
        if epos[1]<0:
            epos[1] = -epos[1]
        rens = iren.GetRenderWindow().GetRenderers()
        rens.InitTraversal()
        for i in xrange(rens.GetNumberOfItems()):
            ren = rens.GetNextItem()
            if ren.IsInViewport(epos[0], epos[1]):
                return ren
        return None

    def findSheetTabWidget(self):
        """ findSheetTabWidget() -> QTabWidget
        Find and return the sheet tab widget
        
        """
        p = self.parent()
        while p:
            if hasattr(p, 'isSheetTabWidget'):
                if p.isSheetTabWidget()==True:
                    return p
            p = p.parent()
        return None

    def getRenderersInCellList(self, sheet, cells):
        """ isRendererIn(sheet: spreadsheet.StandardWidgetSheet,
                         cells: [(int,int)]) -> bool
        Get the list of renderers in side a list of (row, column)
        cells.
        
        """
        rens = []
        for (row, col) in cells:
            cell = sheet.getCell(row, col)
            if hasattr(cell, 'getRendererList'):
                rens += cell.getRendererList()
        return rens

    def getSelectedCellWidgets(self):
        sheet = self.findSheetTabWidget()
        if sheet:
            iren = self.mRenWin.GetInteractor()
            ren = self.interacting
            if not ren: ren = self.getActiveRenderer(iren)
            if ren:
                cells = sheet.getSelectedLocations()
                if (ren in self.getRenderersInCellList(sheet, cells)):
                    return [sheet.getCell(row, col)
                            for (row, col) in cells
                            if hasattr(sheet.getCell(row, col), 
                                       'getRendererList')]
        return []

    def interactionEvent(self, istyle, name):
        """ interactionEvent(istyle: vtkInteractorStyle, name: str) -> None
        Make sure interactions sync across selected renderers
        
        """
        if name=='MouseWheelForwardEvent':
            istyle.OnMouseWheelForward()
        if name=='MouseWheelBackwardEvent':
            istyle.OnMouseWheelBackward()
        ren = self.interacting
        if not ren:
            ren = self.getActiveRenderer(istyle.GetInteractor())
        if ren:
            cam = ren.GetActiveCamera()
            cpos = cam.GetPosition()
            cfol = cam.GetFocalPoint()
            cup = cam.GetViewUp()
            for cell in self.getSelectedCellWidgets():
                if cell!=self and hasattr(cell, 'getRendererList'): 
                    rens = cell.getRendererList()
                    for r in rens:
                        if r!=ren:
                            dcam = r.GetActiveCamera()
                            dcam.SetPosition(cpos)
                            dcam.SetFocalPoint(cfol)
                            dcam.SetViewUp(cup)
                            r.ResetCameraClippingRange()
                    cell.update()

    def charEvent(self, istyle, name):
        """ charEvent(istyle: vtkInteractorStyle, name: str) -> None
        Make sure key presses also sync across selected renderers

        """
        iren = istyle.GetInteractor()
        ren = self.interacting
        if not ren: ren = self.getActiveRenderer(iren)
        if ren:
            keyCode = iren.GetKeyCode()
            if keyCode in ['w','W','s','S','r','R','p','P']:
                for cell in self.getSelectedCellWidgets():
                    if hasattr(cell, 'GetInteractor'):
                        selectedIren = cell.GetInteractor()
                        selectedIren.SetKeyCode(keyCode)
                        selectedIren.GetInteractorStyle().OnChar()
                        selectedIren.Render()
            istyle.OnChar()

    def saveToPNG(self, filename):
        """ saveToPNG(filename: str) -> filename or vtkUnsignedCharArray
        
        Save the current widget contents to an image file. If
        str==None, then it returns the vtkUnsignedCharArray containing
        the PNG image. Otherwise, the filename is returned.
        
        """
        w2i = vtk.vtkWindowToImageFilter()
        w2i.ReadFrontBufferOff()
        w2i.SetInput(self.mRenWin)
        # Render twice to get a clean image on the back buffer
        self.mRenWin.Render()
        self.mRenWin.Render()
        w2i.Update()
        writer = vtk.vtkPNGWriter()
        writer.SetInputConnection(w2i.GetOutputPort())
        if filename!=None:
            writer.SetFileName(filename)
        else:
            writer.WriteToMemoryOn()
        writer.Write()
        if filename:
            return filename
        else:
            return writer.GetResult()

    def captureWindow(self):
        """ captureWindow() -> None        
        Capture the window contents to file
        
        """
        fn = QtGui.QFileDialog.getSaveFileName(None,
                                               "Save file as...",
                                               "screenshot.png",
                                               "Images (*.png)")
        if fn.isNull():
            return
        self.saveToPNG(str(fn))
        
    def grabWindowPixmap(self):
        """ grabWindowImage() -> QPixmap
        Widget special grabbing function
        
        """
        uchar = self.saveToPNG(None)

        ba = QtCore.QByteArray()
        buf = QtCore.QBuffer(ba)
        buf.open(QtCore.QIODevice.WriteOnly)
        for i in xrange(uchar.GetNumberOfTuples()):
            c = uchar.GetValue(i)
            buf.putChar(chr(c))
        buf.close()
        
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(ba, 'PNG')
        return pixmap

    def dumpToFile(self, filename):
        """dumpToFile() -> None
        Dumps itself as an image to a file, calling saveToPNG
        """
        self.saveToPNG(filename)

class QVTKClientWidget(QVTKWidget):
    """
    QVTKWidget with interaction observers
    
    """
    def __init__(self, parent=None, f=QtCore.Qt.WindowFlags()):
        QVTKWidget.__init__(self, parent, f )
        self.dv3dRenderCount = 0         # Do not rename -> used to id a dv3d widget.
        self.dv3dRenderPeriod = 10
#        self.toolBarType = QVTKWidgetToolBar2
        self.current_button = QtCore.Qt.NoButton
        self.current_pos = QtCore.QPoint( 50, 50 )

    def event(self, e): 
#         if ENABLE_JOYSTICK and ( e.type() == ControlEventType ):   
#             self.processControllerEvent( e, [ self.width(), self.height() ] ) 
        if e.type() == QtCore.QEvent.MouseButtonPress:     
            self.current_button = e.button()  
            self.current_pos = e.globalPos()   
        elif e.type() == QtCore.QEvent.MouseButtonRelease: 
            self.current_button = QtCore.Qt.NoButton
        return qt_super(QVTKClientWidget, self).event(e) 
    
    def processControllerEvent(self, event, size ):
        renWin = self.GetRenderWindow()
        iren = renWin.GetInteractor()
        renderers = renWin.GetRenderers()
        renderer = renderers.GetFirstRenderer()
        if event.controlEventType == 'J':
            doRender = ( self.dv3dRenderCount == self.dv3dRenderPeriod )
            self.dv3dRenderCount = 0 if doRender else self.dv3dRenderCount + 1
            dx = event.jx
            dy = event.jy
            while renderer <> None:
              center = [ size[0]/2, size[1]/2]           
              vp = renderer.GetViewport()         
              delta_elevation = -700.0/((vp[3] - vp[1])*size[1])
              delta_azimuth = -700.0/((vp[2] - vp[0])*size[0])             
              rxf = dx * delta_azimuth
              ryf = dy * delta_elevation 
#              print "Processing Rotate Event: ( %.2f, %.2f )" % ( rxf, ryf )         
              camera = renderer.GetActiveCamera()
              camera.Azimuth(rxf)
              camera.Elevation(ryf)
                                               
              if doRender:
                  camera.OrthogonalizeViewUp()     
                  renderer.ResetCameraClippingRange()
                  iren.Render()
              renderer = renderers.GetNextItem()
              
        elif event.controlEventType == 'j':
            doRender = ( self.dv3dRenderCount == self.dv3dRenderPeriod )
            self.dv3dRenderCount = 0 if doRender else self.dv3dRenderCount + 1
            dx = event.jx
            dy = event.jy
            if dy <> 0.0: 
                while renderer <> None:                                               
                  if doRender:
                      camera = renderer.GetActiveCamera()
                      if dy > 0.0: camera.Dolly( 0.9 )
                      if dy < 0.0: camera.Dolly( 1.1 )    
                      renderer.ResetCameraClippingRange()
                      iren.Render()
                  renderer = renderers.GetNextItem()
                               
        elif event.controlEventType == 'P':
            i0 = event.buttonId[0]
            i1 = event.buttonId[1]
            while renderer <> None:          
              if i0 == 1:  
                  camera = renderer.GetActiveCamera()  
                  if i1 == 4: camera.Dolly( 1.1 )         
                  if i1 == 6: camera.Dolly( 0.9 ) 
                  renderer.ResetCameraClippingRange()     
                  iren.Render()
                  renderer = renderers.GetNextItem()

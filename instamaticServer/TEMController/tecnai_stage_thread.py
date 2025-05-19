import threading
import comtypes
from typing import Union

class TecnaiStageThread(threading.Thread):
    """
    Stage communication with the Tecnai microscope over a separate thread.
    """
    
    def __init__(self, tem=None, pos:(float, float, float, float, float)=None, axis:int=None, speed:Union[int, float]=0):
        super().__init__()

        #TEM-Scriptinginterface
        self._tem = tem
        
        #StagePosition
        if (pos != None) and (len(pos) == 5):
            _x = float(pos[0])
            _y = float(pos[1])
            _z = float(pos[2])
            _a = float(pos[3])
            _b = float(pos[4])
            self._pos = (_x, _y, _z, _a, _b)
        else:
            self._pos = None
        
        #changing Stagecoordinates    
        if axis == None: axis = 0
        self._axis = axis
        
        #Stagespeed
        if (speed>0.0) and (speed<=1.0):
            self._speed = speed
        else:
            self._speed = 1.0
        
    def run(self) -> None:
        #run only on the alpha-axis
        if self._pos is None:
            return
        with ContextManagedComtypes() as cmc:
            tem_constant = comtypes.client.Constants(self._tem)
            stagePos = self._tem.Stage.Position
            if self._axis & tem_constant.StageAxes['axisX']:
                stagePos.X = self._pos[0]
            if self._axis & tem_constant.StageAxes['axisY']:
                stagePos.Y = self._pos[1]
            if self._axis & tem_constant.StageAxes['axisZ']:
                stagePos.Z = self._pos[2]
            if self._axis & tem_constant.StageAxes['axisA']:
                stagePos.A = self._pos[3]
            if self._axis & tem_constant.StageAxes['axisB']:
                stagePos.B = self._pos[4]
            if self._speed == 1.0:
                self._tem.Stage.GoTo(stagePos, self._axis)
            else:
                self._tem.Stage.GoToWithSpeed(stagePos, self._axis, self._speed)

class ContextManagedComtypes():
    '''The Context Manager Protocoll is used to initialize the COM connection again'''
    def __enter__(self):
        comtypes.CoInitialize()
        return self

    def __exit__(self, *args):
        comtypes.CoUninitialize()
        return True

    def __str__(self):
        return 'ContextManagedComtypes object'
      

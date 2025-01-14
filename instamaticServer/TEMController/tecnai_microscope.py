import atexit
import logging
import time
import comtypes.client
from math import pi

from utils.exceptions import FEIValueError, TEMCommunicationError
from utils.config import config
from TEMController.tecnai_stage_thread import TecnaiStageThread

_FUNCTION_MODES = {1: 'lowmag', 2: 'mag1', 3: 'samag', 4: 'mag2', 5: 'LAD', 6: 'diff'}

#diff=D, LAD=LAD, lowmag=LM, mag1=Mi, samag=SA, mag2=Mh in Functionmodes



#dict([('D', [0.0265, 0.035, 0.044, 0.062, 0.071, 0.089, 0.135, 0.175, 0.265, 0.43, 0.6, 0.86, 1.65, 2.65, 3.5, 4.1]),
#                   ('LAD', [4.5, 7.1, 9, 12.5, 18, 27, 36, 53, 71, 81, 130, 180, 245, 360, 530, 720, 790, 810, 960, 1100, 1300]),
#                   ('LM', [19, 25, 35, 50, 65, 82, 105, 145, 200, 300, 390, 500, 730, 980, 1350, 1850]),
#                   ('Mi', [2250, 3500, 4400]),
#                   ('SA', [6200, 8700, 13500, 17000, 26000, 34000, 38000, 63000, 86000, 125000, 175000, 250000, 350000, 400000]),
#                   ('Mh', [440000, 520000, 610000, 700000, 780000, 910000])])


class Singleton(type):
    """Singleton Metaclass from Stack Overflow, stackoverflow.com/q/6760685"""
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class TecnaiMicroscope(metaclass=Singleton):
    """Python bindings to the Tecnai-G2 microscope using the COM scripting interface."""

    def __init__(self, name: str=None) -> None:

        try:
            comtypes.CoInitialize()
        except:
            raise

        print('FEI Scripting initializing...')
        ## TEM interfaces the GUN, stage etc
        self._tem = comtypes.client.CreateObject('TEMScripting.Instrument', comtypes.CLSCTX_ALL)

        ## TEM enum constants
        self._tem_constant = comtypes.client.Constants(self._tem)

        self._t = 0
        while True:
            ht = self._tem.GUN.HTValue
            if ht > 0:
                break
            time.sleep(1)
            self._t += 1
            if self._t > 3:
                print('Waiting for microscope, t = %ss' % (self._t))
            if self._t > 30:
                raise TEMCommunicationError('Cannot establish microscope connection (timeout).')

        self._logger = logging.getLogger(__name__)
        self._logger.info('Microscope connection established')
        #close the network connection
        atexit.register(TecnaiMicroscope.release_connection)

        self.name = name

        self._conf = config(self.name)
        self._mic_ranges = None
        if self._conf.micr_interface == 'tecnai':
            self._mic_ranges = self._conf.micr_ranges

        self._rotation_speed = 1.0
        self._tecnaiStage = TecnaiStageThread() #Thread für a-Movement
        self._goniotool_available = False


    ###Stage-Functions
    def getHolderType(self) -> int:
        """Return TEM-Holder type as enum constant."""
        return self._tem.Stage.Holder

    def getStagePosition(self) -> (float, float, float, float, float):
        """Return Stageposition x, y, z in microns and alpha(a), beta(b) in degs."""
        x = self._tem.Stage.Position.X * 1e6
        y = self._tem.Stage.Position.Y * 1e6
        z = self._tem.Stage.Position.Z * 1e6
        A = self._tem.Stage.Position.A / pi * 180
        B = self._tem.Stage.Position.B / pi * 180
        return x, y, z, A, B

    def getStageSpeed(self) -> float:
        """Return Stagespeed, can not be read on Tecnai = constant(0.5)."""
        print('StageSpeed can not be read on Tecnai')        
        return 0.5

    def is_goniotool_available(self) -> bool:
        """Return goniotool status, always False."""
        return self._goniotool_available

    def isAThreadAlive(self) -> bool:
        """Return goniotool status, always False."""
        return self._tecnaiStage.is_alive()

    def isStageMoving(self) -> bool:
        """is Stage moving?, False if the Stage is ready, else it is True."""
        if self._tem.Stage.Status != self._tem_constant.StageStatus['stReady']:
            return True
            
        pos1 = self.getStagePosition()
        time.sleep(0.3)
        pos2 = self.getStagePosition()
            
        for i in range(len(pos1)):
            diff = abs(pos1[i] - pos2[i])
            #z-Value, gap of 0.4micrometer is okay
            if (i == 2) and diff >= 0.4:
                return True
            #a, b-Value, gap of 0.1degree is okay
            elif (3 <= i <= 4) and diff >= 0.1:
                return True
                    
        return False
           
    def setStagePosition(self, x: float=None, y: float=None, z: float=None, a: float=None,
                         b: float=None, wait: bool=True, speed: float=1.0) -> None:
        """Set the Stageposition x, y, z in microns and alpha(a), beta(b) in degs."""
        pos = self._tem.Stage.Position
        axis = 0
        enable_stage = False
        enable_B = False
        if (speed > 1.0) or (speed <= 0.0):
            speed = 1.0

        if self._tem.Stage.Holder in (self._tem_constant.StageHolderType['hoSingleTilt'],
                                      self._tem_constant.StageHolderType['hoDoubleTilt']):
            enable_stage = True

        if self._tem.Stage.Holder == self._tem_constant.StageHolderType['hoDoubleTilt']:
            enable_B = True

        if x is not None and enable_stage:
            pos.X = x * 1e-6
            axis = axis | self._tem_constant.StageAxes['axisX']
        if y is not None and enable_stage:
            pos.Y = y * 1e-6
            axis = axis | self._tem_constant.StageAxes['axisY']
        if z is not None and enable_stage:
            pos.Z = z * 1e-6
            axis = axis | self._tem_constant.StageAxes['axisZ']
        if a is not None and enable_stage:
            pos.A = a / 180 * pi
            axis = axis | self._tem_constant.StageAxes['axisA']
        if b is not None and enable_B:
            pos.B = b / 180 * pi
            axis = axis | self._tem_constant.StageAxes['axisB']
        
        if wait:
            if axis != 0:
                if speed == 1.0:
                    if (axis == self._tem_constant.StageAxes['axisA']) and (self._rotation_speed != 1.0):
                        self._tem.Stage.GoToWithSpeed(pos, axis, self._rotation_speed)
                    else:
                        self._tem.Stage.GoTo(pos, axis)
                else:
                    self._tem.Stage.GoToWithSpeed(pos, axis, speed)
            self.waitForStage()
        elif (wait == False) and (self._tecnaiStage.is_alive() is False):
            if axis == self._tem_constant.StageAxes['axisA']:
                #start Rotation in separate Thread and go on
                stagePos = (pos.X, pos.Y, pos.Z, pos.A, pos.B)
                self._tecnaiStage = TecnaiStageThread(self._tem, stagePos, axis, speed)
                self._tecnaiStage.daemon=True
                self._tecnaiStage.start()
        

        #self._tem.Stage.GoToWithSpeed(pos, axis, 0.01) => 1grad in 4-5sec.


    def setStageA(self, value: float=None, wait: bool=True) -> None:
        """Set the Stageposition alpha (A) in degrees."""
        pos = self._tem.Stage.Position
        axis = 0
        enable_stage = False

        if self._tem.Stage.Holder in (self._tem_constant.StageHolderType['hoSingleTilt'],
                                      self._tem_constant.StageHolderType['hoDoubleTilt']):
            enable_stage = True

        if value is not None:
            pos.A = value / 180 * pi
            axis = self._tem_constant.StageAxes['axisA']

        if enable_stage:
            if wait == True:
                self._tem.Stage.GoToWithSpeed(pos, axis, self._rotation_speed)
                self.waitForStage()
            elif (wait == False) and (self._tecnaiStage.is_alive() is False):
                #start Rotation in separate Thread and go on
                stagePos = (pos.X, pos.Y, pos.Z, pos.A, pos.B)
                self._tecnaiStage = TecnaiStageThread(self._tem, stagePos, axis, self._rotation_speed)
                self._tecnaiStage.daemon=True
                self._tecnaiStage.start()
                
    def setStageB(self, value: float=None, wait: bool=True) -> None:
        """Set the Stageposition beta (B) in degrees."""
        """wait has no meaning, Jeol-API"""        
        pos = self._tem.Stage.Position
        axis = 0
        enable_B = False

        if self._tem.Stage.Holder == self._tem_constant.StageHolderType['hoDoubleTilt']:
            enable_B = True

        if value is not None:
            pos.B = value / 180 * pi
            axis = self._tem_constant.StageAxes['axisB']

        if enable_B:
            self._tem.Stage.GoTo(pos, axis)
        
        self.waitForStage()

    def waitForStage(self, delay: float=0.1) -> None:
        """helper function to wait, until the stage movement is finished."""
        while self._tem.Stage.Status is not self._tem_constant.StageStatus['stReady']:
            if delay > 0:
                time.sleep(delay)

    def setStageSpeed(self, value: float) -> None:
        """Set Stage speed, not available on Tecnai."""
        print('StageSpeed can not be set on Tecnai')

    def stopStage(self) -> None:
        """Stop Stage, not available on Tecnai."""
        print('stopStage: not available on Tecnai.')

    def setRotationSpeed(self, value: float) -> None:
        """Set rotationspeed of the alpha rotation."""
        if 0.0 < value <= 1.0:
            self._rotation_speed = value

    def getRotationSpeed(self) -> float:
        """get the rotation speed of the alpha rotation"""
        return self._rotation_speed


    ###Gun
    def getGunShift(self) -> (float, float):
        """get the Gun-Shift values."""
        return self._tem.GUN.Shift.X, self._tem.GUN.Shift.Y

    def setGunShift(self, x: float, y: float) -> None:
        """set the Gun-Shift values, should be a number between -1 and 1."""
        if abs(x) > 1 or abs(y) > 1:
            raise FEIValueError('GunShift x/y must be a floating number between -1 an 1. Input: x=%s, y=%s' % (x, y))

        gs = self._tem.GUN.Shift
    
        if x is not None:
            gs.X = x
        if y is not None:
            gs.Y = y

        self._tem.GUN.Shift = gs

    def getGunTilt(self) -> (float, float):
        """get the Gun-Tilt values."""
        return self._tem.GUN.Tilt.X, self._tem.GUN.Tilt.Y

    def setGunTilt(self, x: float, y: float) -> None:
        """set the Gun-Tilt values, should be a number between -1 and 1."""
        if abs(x) > 1 or abs(y) > 1:
            raise FEIValueError('GunTilt x/y must be a floating number between -1 an 1. Input: x=%s, y=%s' % (x, y))

        gt = self._tem.Gun.Tilt
        
        if x is not None:
            gt.X = x
        if y is not None:
            gt.Y = y

        self._tem.Gun.Tilt = gt

    def getHTValue(self) -> int:
        """get the HT-value."""
        return self._tem.GUN.HTValue

    def setHTValue(self, htvalue: int) -> None:
        """set the HT-value."""
        self._tem.GUN.HTValue = htvalue

    def isBeamBlanked(self) -> bool:
        """is the Beam blanked? -> True/False."""
        return self._tem.Illumination.BeamBlanked

    def setBeamBlank(self, value: bool) -> None:
        """Blank the Beam: True/False."""
        if isinstance(value, bool):
            self._tem.Illumination.BeamBlanked = value

    def setBeamUnblank(self) -> None:
        """unblank the Beam."""
        self._tem.Illumination.BeamBlanked = False

    def setNeutral(self, *args) -> None:
        """Neutralize all deflectors."""
        self._tem.Projection.Normalize(self._tem_constant.ProjectionNormalization['pnmAll'])
        self._tem.Illumination.Normalize(self._tem_constant.IlluminationNormalization['nmAll'])
        time.sleep(4)

    def getBeamAlignShift(self) -> (float, float):
        """get the Gun-Shift values."""
        return self.getGunShift()

    def setBeamAlignShift(self, x: float, y: float) -> None:
        """set Gun-Shift values."""
        self.setGunShift(x, y)

        
    ###Illumination
    def getSpotSize(self) -> int:
        """get the Spotsize."""
        return self._tem.Illumination.SpotsizeIndex

    def setSpotSize(self, value: int) -> None:
        """set the Spotsize"""
        if isinstance(value, int):
            self._tem.Illumination.SpotsizeIndex = value

    def getBrightness(self) -> int:
        """get the Intensity value -> scaled to 0-65536"""
        return int(self._tem.Illumination.Intensity * 65536)

    def setBrightness(self, value: int) -> None:
        """set the Intensity value (0-65536)."""
        if 0 <= value <= 65536:
            it = float(value / 65536.0)
            self._tem.Illumination.Intensity = it

    def getBrightnessValue(self) -> float:
        """get the Intensity value."""
        return self._tem.Illumination.Intensity

    def setBrightnessValue(self, value: float) -> None:
        """set the Intensity value"""
        self._tem.Illumination.Intensity = value

    def getBeamShift(self) -> (float, float):
        """get the BeamShift values."""
        return self._tem.Illumination.Shift.X, self._tem.Illumination.Shift.Y

    def setBeamShift(self, x: float, y: float) -> None:
        """set the BeamShift values."""
        bs = self._tem.Illumination.Shift
      
        if x is not None:
            bs.X = x
        if y is not None:
            bs.Y = y
            
        self._tem.Illumination.Shift = bs

    def getBeamTilt(self) -> (float, float):
        """get Rotation center."""
        return self._tem.Illumination.RotationCenter.X, self._tem.Illumination.RotationCenter.Y

    def setBeamTilt(self, x: float, y: float) -> None:
        """set Rotation center."""
        if abs(x) > 0.4 or abs(y) > 0.4:
            raise FEIValueError('BeamTilt x/y must be a floating number between -0.4 an 0.4. Input: x/y=%s/%s' % (x, y))

        bt = self._tem.Illumination.RotationCenter
        
        if x is not None:
            bt.X = x
        if y is not None:
            bt.Y = y

        self._tem.Illumination.RotationCenter = bt

    def getCondensorLensStigmator(self) -> (float, float):
        """get Condensor lens stigmator."""
        return self._tem.Illumination.CondenserStigmator.X, self._tem.Illumination.CondenserStigmator.Y

    def setCondensorLensStigmator(self, x: float, y: float) -> None:
        """set Condensor lens stigmator."""
        self._tem.Illumination.CondenserStigmator.X = x
        self._tem.Illumination.CondenserStigmator.Y = y


    ###Projection
    def getCurrentDensity(self) -> float:
        """Get the current density, not available on Tecnai."""
        print('getCurrentDensity: not available on the Tecnai.')
        return 0

    def getScreenCurrent(self) -> float:
        """get the Screen current in nA."""
        return self._tem.Camera.ScreenCurrent * 1e9

    def isfocusscreenin(self) -> bool:
        """is small Screen down?"""
        return self._tem.Camera.IsSmallScreenDown

    def getScreenPosition(self) -> str:
        """is Screen 'up' or 'down'."""
        while self._tem.Camera.MainScreen == self._tem_constant.ScreenPosition['spUnknown']:
            time.sleep(1)

        if self._tem.Camera.MainScreen == self._tem_constant.ScreenPosition['spUp']:
            return 'up'
        elif self._tem.Camera.MainScreen == self._tem_constant.ScreenPosition['spDown']:
            return 'down'
        else:
            return ''
        
    def setScreenPosition(self, value: str) -> None:
        """set Screen 'up' or 'down'."""
        if value not in ('up', 'down'):
            raise FEIValueError("No such screen position: %s ." % (value))
        if value == 'up':
            self._tem.Camera.MainScreen = self._tem_constant.ScreenPosition['spUp']
        else:
            self._tem.Camera.MainScreen = self._tem_constant.ScreenPosition['spDown']

        while self._tem.Camera.MainScreen == self._tem_constant.ScreenPosition['spUnknown']:
            time.sleep(1)

    def getDiffFocus(self, confirm_mode: bool=True) -> int:
        """get the diffraction focus scaled between -1e4 (0) und 1e4 (65536)."""
        if not self.getFunctionMode() == 'diff':
            raise FEIValueError("Must be in 'diff' mode to get DiffFocus")

        foc = self._tem.Projection.Defocus
        val = int(32768.0 * 1.0e4 * (foc + 1.0e-4))
        return val

    def setDiffFocus(self, value: int, confirm_mode: bool=True) -> None:
        """set the diffraction focus value between -1e4 (0) und 1e4 (65536)."""
        if not self.getFunctionMode() == 'diff':
            raise FEIValueError("Must be in 'diff' mode to set DiffFocus")

        if 0 <= value <= 65536:
            foc = float((1.0e-4 / 32768.0 * value) - 1e-4)
            self._tem.Projection.Defocus = foc

    def getDiffFocusValue(self, confirm_mode: bool=True) -> float:
        """get the diffraction focus value."""
        if not self.getFunctionMode() == 'diff':
            raise FEIValueError("Must be in 'diff' mode to get DiffFocus")

        return self._tem.Projection.Defocus

    def setDiffFocusValue(self, value: float, confirm_mode: bool=True) -> None:
        """set the diffraction focus value."""
        if not self.getFunctionMode() == 'diff':
            raise FEIValueError("Must be in 'diff' mode to set DiffFocus")

        self._tem.Projection.Defocus = value

    def getFocus(self) -> float:
        """get the Defocus value."""
        if not self.getFunctionMode() in ['lowmag', 'mag1', 'samag', 'mag2']:
            raise FEIValueError("Must be in 'mag' mode to get Focus")

        return self._tem.Projection.Defocus

    def setFocus(self, value: float) -> None:
        """set the Defocus value."""
        if not self.getFunctionMode() in ['lowmag', 'mag1', 'samag', 'mag2']:
            raise FEIValueError("Must be in 'mag' mode to set Focus")
                                          
        self._tem.Projection.Defocus = value

    def getFunctionMode(self) -> str:
        """get the Function Mode. diff=D, lowmag=LM, mag1=Mi, samag=SA, mag2=Mh ."""
        mode = self._tem.Projection.SubMode
        return _FUNCTION_MODES[mode]

    def setFunctionMode(self, value: str) -> None:
        """set the Function Mode. diff = diffraction mode, lowmag=mag1=samag=mag2 = imaging mode ."""
        if isinstance(value, str):
            try:
                if value in list(_FUNCTION_MODES.values()):
                    if value in ['lowmag', 'mag1', 'samag', 'mag2']:
                        self._tem.Projection.Mode = self._tem_constant.ProjectionMode['pmImaging']
                    elif value == 'diff':
                        self._tem.Projection.Mode = self._tem_constant.ProjectionMode['pmDiffraction']
            except ValueError:
                raise FEIValueError('Unrecognized function mode: %s' % (value))

    def getMagnification(self) -> float:
        """get Magnification/camera length."""
        ind = self.getMagnificationIndex() - 1

        if self.getFunctionMode() == 'diff':
            return self._mic_ranges['D'][ind]
        elif self.getFunctionMode() == 'LAD':
            return self._mic_ranges['LAD'][ind]
        else:
            magni = self._mic_ranges['LM']
            for k in ['Mi', 'SA', 'Mh']:
                magni.extend(self._mic_ranges[k])
            return magni[ind]
        
    def setMagnification(self, value: float) -> None:
        """set Magnification/camera length."""
        ind = None

        try:
            if self.getFunctionMode() == 'diff':
                ind = self._mic_ranges['D'].index(value)
            elif self.getFunctionMode() == 'LAD':
                ind = self._mic_ranges['LAD'].index(value)
            else:
                magni = self._mic_ranges['LM']
                for k in ['Mi', 'SA', 'Mh']:
                    magni.extend(self._mic_ranges[k])
                ind = magni.index(value)
        except ValueError:
            raise FEIValueError('wrong Magnification: %s' % (value))

        if ind:
            self.setMagnificationIndex(ind + 1)
        else:
            pass
    
    def getMagnificationRanges(self) -> dict:
        """get the MagnificationRanges from the config file"""
        mag_ranges = {}

        mag_ranges['diff'] = self._mic_ranges['D']
        mag_ranges['LAD'] = self._mic_ranges['LAD']
        mag_ranges['lowmag'] = self._mic_ranges['LM']
        mag_ranges['mag1'] = self._mic_ranges['Mi']
        mag_ranges['samag'] = self._mic_ranges['SA']
        mag_ranges['mag2'] = self._mic_ranges['Mh']
        
        return mag_ranges

    def getMagnificationIndex(self) -> int:
        """get Magnification / camera length index."""
        if self._tem.Projection.Mode == self._tem_constant.ProjectionMode['pmImaging']:
            return self._tem.Projection.MagnificationIndex
        elif self._tem.Projection.Mode == self._tem_constant.ProjectionMode['pmDiffraction']:
            return self._tem.Projection.CameraLengthIndex
        else:
            return 0

    def setMagnificationIndex(self, index: int) -> None:
        """set Magnification / camera length index."""        
        if self._tem.Projection.Mode == self._tem_constant.ProjectionMode['pmImaging']:
            self._tem.Projection.MagnificationIndex = index
        elif self._tem.Projection.Mode == self._tem_constant.ProjectionMode['pmDiffraction']:
            self._tem.Projection.CameraLengthIndex = index
        else:
            raise FEIValueError("setMagnificationIndex: wrong MagnificationIndex / Mode.")

    def getMagnificationAbsoluteIndex(self) -> None:
        """not implemented"""
        raise NotImplementedError

    def increaseMagnificationIndex(self) -> None:
        """increase Magnification by one step."""
        try:
            self._tem.Projection.MagnificationIndex += 1
        except ValueError:
            raise FEIValueError('Unrecognized Magnification Index.')

    def getDarkFieldTilt(self) -> (float, float):
        """get the dark field tile value."""
        return self._tem.Illumination.Tilt.X, self._tem.Illumination.Tilt.Y

    def setDarkFieldTilt(self, x: float, y: float) -> None:
        """set the dark field tilt value."""
        dt = self._tem.Illumination.Tilt
        
        if x is not None:
            dt.X = x
        if y is not None:
            dt.Y = y

        self._tem.Illumination.Tilt = dt

    def getImageShift1(self) -> (float, float):
        """get the image shift value"""
        return self._tem.Projection.ImageShift.X, self._tem.Projection.ImageShift.Y

    def setImageShift1(self, x: float, y: float) -> None:
        """set the image shift value."""
        is1 = self._tem.Projection.ImageShift

        if x is not None:
            is1.X = x
        if y is not None:
            is1.Y = y

        self._tem.Projection.ImageShift = is1

    def getImageShift2(self) -> (float, float):
        """not implemented."""
        return 0, 0

    def setImageShift2(self, x: float, y: float) -> None:
        """not implemented."""
        return None

    def getImageBeamShift(self) -> (float, float):
        """get the beam shift value."""
        return self._tem.Projection.ImageBeamShift.X, self._tem.Projection.ImageBeamShift.Y

    def setImageBeamShift(self, x: float, y: float) -> None:
        """set the beam shift values."""
        is1 = self._tem.Projection.ImageBeamShift
        
        if x is not None:
            is1.X = x
        if y is not None:
            is1.Y = y

        self._tem.Projection.ImageBeamShift = is1

    def getDiffShift(self) -> (float, float):
        """get the diffraction shift value in degree."""
        return (float(180 / pi * self._tem.Projection.DiffractionShift.X),
                float(180 / pi * self._tem.Projection.DiffractionShift.Y))

    def setDiffShift(self, x: float, y: float) -> None:
        """set the diffraction shift values in degree."""
        ds1 = self._tem.Projection.DiffractionShift

        if x is not None:
            ds1.X = float(x / 180 * pi)
        if y is not None:
            ds1.Y = float(y / 180 * pi)

        self._tem.Projection.DiffractionShift = ds1

    def getObjectiveLensStigmator(self) -> (float, float):
        """get the objective lens stigmator value."""
        return self._tem.Projection.ObjectiveStigmator.X, self._tem.Projection.ObjectiveStigmator.Y

    def setObjectiveLensStigmator(self, x: float, y: float) -> None:
        """set the objective lens stigmator value."""
        self._tem.Projection.ObjectiveStigmator.X = x
        self._tem.Projection.ObjectiveStigmator.Y = y
        
    def getIntermediateLensStigmator(self) -> (float, float):
        """get the intermediate lens stigmator value."""
        return self._tem.Projection.DiffractionStigmator.X, self._tem.Projection.DiffractionStigmator.Y

    def setIntermediateLensStigmator(self, x: float, y: float) -> None:
        """set the intermediate lens stigmator value."""
        self._tem.Projection.DiffractionStigmator.X = x
        self._tem.Projection.DiffractionStigmator.Y = y

    @staticmethod
    def release_connection() -> None:
        """release the COM-connection."""
        comtypes.CoUninitialize()
        print('Connection to microscope released')

    def getApertureSize(self, aperture: str) -> None:
        """not available on Tecnai."""
        print('getApertureSize, not available on Tecnai.')

 
if __name__ == '__main__':
    tem = TecnaiMicroscope()

    from IPython import embed
    embed()

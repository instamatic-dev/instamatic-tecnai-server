from utils.config import config

_conf = config()
_tem_interfaces = ('simulate', 'tecnai')

__all__ = ['Microscope', 'get_tem']


def get_tem(interface: str):
    """Grab the tem class with the given 'interface'."""

    if interface == 'simulate':
        from .simu_microscope import SimuMicroscope as cls
    elif interface == 'tecnai':
        from .tecnai_microscope import TecnaiMicroscope as cls
    else:
        raise ValueError("No such microscope interface: %s" % (interface))

    return cls


def Microscope(name: str = None):
    """Generic class to load microscope interface class.

    name: str
        Specify which microscope to use, must be one of `tecnai`, `simulate`
    use_server: bool
        Connect to microscope server running on the host/port defined in the config file

    returns: TEM interface class
    """
    if name in _tem_interfaces:
        interface = name
    else:
        interface = _conf.micr_interface
        name = _conf.default_settings['microscope']

    cls = get_tem(interface=interface)
    tem = cls(name=name)

    return tem

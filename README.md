# Server for the Tecnai-Scripting interface

The "Tecnai-Server" is an additional TEM interface used to control a FEI Tecnai-TEM via the instamatic software. We have tested the server software on a FEI Tecnai G2 microscope. The program provides access for the instamatic software to the com-scripting interface of the TEM.

## Installation and Requirement

The server software was developed in a Python 3.4 software environment (Windows XP). Following you have to install the Python 3.4 software package on your microscope-PC. The additional needed software-side packages and their last versions confirmed to work on Windows XP are:

- `comtypes` – version 1.2.1 ([link](https://pypi.org/project/comtypes/1.2.1/#comtypes-1.2.1-py2.py3-none-any.whl));
- `PyYAML` – version 5.1.2 ([link](https://pypi.org/project/PyYAML/5.1.2/#PyYAML-5.1.2-cp34-cp34m-win32.whl), might require updating pip)
- `typing` – version 3.10.0.0 ([link](https://pypi.org/project/typing/3.10.0.0/#typing-3.10.0.0-py3-none-any.whl))

The packages can be installed using pip, either automatically (if connected to the internet) or manually, by downloading, copying, and pointing to the wheel files linked above. Furthermore, the FEI com-scripting interface should be available on your TEM-PC.

## Usage

Microscope PC: This script
Camera PC (or other): [instamatic software](https://github.com/instamatic-dev/instamatic)

The instamatic instance on the camera PC communicates with "Tecnai-Server"-software [over the network](https://instamatic.readthedocs.io/en/latest/network/).

The "Tecnai-Server"-software is provided as a standard python-program. You can download and install the software in your chosen directory on the microscope-PC. After you have opened a MS-DOS command prompt you are navigating to the installation directory. The server will be started by the usual python invocation py `tem_server.py`. A corresponding `start.bat` -file is provided in the installation directory.

The software will be configured by the .yaml-files in the `utils`-subdirectory. For instance the correct network address of your microscope-PC is set in the `settings.yaml` file. The magnification table of your TEM or the scripting interface `tecnai` are saved in the `microscope.yaml` file.

In our experimental setup the [instamatic software](https://github.com/instamatic-dev/instamatic) is installed on a separate PC (camera PC). In this case the configuration files of Instamatic must be adapted like in the server software. Especially the `interface="tecnai"`, the microscope, the network address and the flag `use_tem_server"` should be verified. Afterwards the instamatic software should be starting without errors on your PC. You can try it out in an IPython shell if the TEMController-object has access to TEM.

## Credits

Thanks to Steffen Schmidt ([CUP, LMU München](https://www.cup.uni-muenchen.de/)) for providing this script.

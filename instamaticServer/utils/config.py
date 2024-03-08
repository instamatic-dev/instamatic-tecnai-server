from pathlib import Path
import yaml


_settings_file = 'settings.yaml'


class config:

    def __init__(self, name:str=None):
        self.default_settings = self.settings()

        if name != None:
            self.default_settings['microscope'] = name

        self.micr_interface, self.micr_wavelength, self.micr_ranges = self.microscope()

    def settings(self) -> dict:
        """load the settings.yaml file."""
        default = None

        direc = Path(__file__).resolve().parent
        file = direc.joinpath(_settings_file)
        with open(str(file), 'r') as stream:
            default = yaml.safe_load(stream)

        return default

    def microscope(self):
        """load the microscope.yaml file."""
        default = None
        
        direc = Path(__file__).resolve().parent
        microscope_file = '\\' + str(self.default_settings['microscope']) + '.yaml'
        file = str(direc) + microscope_file
        with open(file, 'r') as stream:
            default = yaml.safe_load(stream)

        interface = default['interface']
        wavelength = default['wavelength']
        micr_ranges = default['ranges']

        return interface, wavelength, micr_ranges


if __name__ == '__main__':
    data = config()
    print(data.default_settings['microscope'])
    print(data.micr_ranges['Mh'])
    


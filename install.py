# Installer for HoekWindLEDMatrix extension

from weecfg.extension import ExtensionInstaller


def loader():
    return HoekWindLEDMatrixInstaller()


class HoekWindLEDMatrixInstaller(ExtensionInstaller):
    def __init__(self):
        super(HoekWindLEDMatrixInstaller, self).__init__(
            version="0.1",
            name='hoekwindledmatrix',
            description='Display wind speed on an LED Matrix.',
            report_services='user.hoekwind.HoekWindLEDMatrix',
            config={'HoekWindLEDMatrix': {}},
            files=[('bin/user', ['bin/user/hoekwindledmatrix.py'])]
        )

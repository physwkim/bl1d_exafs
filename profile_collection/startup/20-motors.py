from ophyd import Device, EpicsSignal
from ophyd import (EpicsMotor, PseudoSingle, PseudoPositioner, PVPositioner,
                   Component as Cpt)
from utils import loadPV

# PV parameter loadings
pv_names = loadPV()

class Slits(Device):
    up  = Cpt(EpicsMotor, pv_names['Motor']['slit_up'])
    down  = Cpt(EpicsMotor, pv_names['Motor']['slit_down'])
    left  = Cpt(EpicsMotor, pv_names['Motor']['slit_left'])
    right  = Cpt(EpicsMotor, pv_names['Motor']['slit_right'])

slit = Slits('', name='slit')

from ophyd import (EpicsMotor, PseudoSingle, PseudoPositioner,
                   Component as Cpt, EpicsSignal, EpicsSignal)
from ophyd.pseudopos import (pseudo_position_argument, real_position_argument)
import numpy as np
from scipy import interpolate

from utils import loadPV
from utils import loadOffset, saveOffset

# PV parameter loadings
pv_names = loadPV()


_hc = 12398.5
_si_111 = 5.4309/np.sqrt(3)

class DCMEnergy(PseudoPositioner):
    # Energy in eV unit, 2800 eV to 100 keV
    energy = Cpt(PseudoSingle, limits=(2800, 100000))
    theta  = Cpt(EpicsMotor, pv_names['DCM']['mono_theta'])
    offset  = Cpt(EpicsSignal, pv_names['DCM']['mono_offset'])
    calibSet     = Cpt(EpicsSignal, pv_names['DCM']['mono_set'])
    foff     = Cpt(EpicsSignal, pv_names['DCM']['mono_foff']) # Fixed Offset Mode
    encResolution = Cpt(EpicsSignal, pv_names['DCM']['mono_enc_resolution'])
    statusUpdate = Cpt(EpicsSignal, pv_names['DCM']['mono_status_update']) # Encoder Position Status Update


    def forward(self, pseudo_pos):
        _th = np.rad2deg(np.arcsin(_hc/(2.*_si_111*pseudo_pos.energy)))
        return self.RealPosition(theta=_th)

    def inverse(self, real_pos):
        en = _hc/(2.*_si_111*np.sin(np.deg2rad(real_pos.theta)))
        en = float(en)
        return self.PseudoPosition(energy=en)

dcm = DCMEnergy('', name='dcm', egu='eV')

class DCM_Etc(Device):
    """Other motors from mono theta"""
    zt  = Cpt(EpicsMotor, pv_names['DCM']['mono_zt'])
    mono_vmax  = Cpt(EpicsSignal, pv_names['DCM']['mono_theta_speed_max'])
    mono_vbas  = Cpt(EpicsSignal, pv_names['DCM']['mono_theta_speed_base'])
    z1  = Cpt(EpicsMotor, pv_names['DCM']['mono_z1'])
    theta2  = Cpt(EpicsMotor, pv_names['DCM']['mono_theta2'])
    z2  = Cpt(EpicsMotor, pv_names['DCM']['mono_z2'])
    gamma2  = Cpt(EpicsMotor, pv_names['DCM']['mono_gamma2'])
    spmg   = Cpt(EpicsSignal, pv_names['DCM']['mono_theta']+'.SPMG')

dcm_etc = DCM_Etc('', name="dcm_etc")

from ophyd import EpicsSignal, EpicsScaler, Device, Component as Cpt
from ophyd import EpicsSignalRO
from ophyd.scaler import ScalerCH

from utils import loadPV

# PV parameter loadings
pv_names = loadPV()

# beam=EpicsSignal(pv_names['Beam_Current'],name='beam')

class Accelerator(Device):
    beam_current = Cpt(EpicsSignal, pv_names['Beam']['Current'])
    life_time    = Cpt(EpicsSignal, pv_names['Beam']['LifeTime'])
    topup_count  = Cpt(EpicsSignal, pv_names['Beam']['TopUpCount'])

accelerator = Accelerator('', name='accelerator')

# Scaler
scaler = ScalerCH(pv_names['Scaler']['scaler'], name='scaler')

# only select named channels
scaler.select_channels(None)

# Stage signal to set counting mode to "single shot"
scaler.stage_sigs["count_mode"] = 0
scaler.stage_sigs["count"] = 0

preset_time = scaler.preset_time

# Step-Scan Counter
I0 = EpicsSignalRO(pv_names['Scaler']['I0_counter_cal'], name='I0_calc')
It = EpicsSignalRO(pv_names['Scaler']['It_counter_cal'], name='It_calc')
If = EpicsSignalRO(pv_names['Scaler']['If_counter_cal'], name='If_calc')
Ir = EpicsSignalRO(pv_names['Scaler']['Ir_counter_cal'], name='Ir_calc')

ENC_fly_counter  = EpicsSignalRO(pv_names['Scaler']['HC10E_ENC'], name='ENC_fly_counter')
I0_fly_counter   = EpicsSignalRO(pv_names['Scaler']['HC10E_I0'],  name='I0_fly_counter')
It_fly_counter   = EpicsSignalRO(pv_names['Scaler']['HC10E_It'],  name='It_fly_counter')
If_fly_counter   = EpicsSignalRO(pv_names['Scaler']['HC10E_If'],  name='If_fly_counter')
Ir_fly_counter   = EpicsSignalRO(pv_names['Scaler']['HC10E_Ir'],  name='Ir_fly_counter')

# HC10E Counter Fly mode
class HC10E(Device):
    preset        = Cpt(EpicsSignal, pv_names['Scaler']['HC10E_Preset'])
    reset         = Cpt(EpicsSignal, pv_names['Scaler']['HC10E_Reset'])
    mode          = Cpt(EpicsSignal, pv_names['Scaler']['HC10E_Mode'])
    trigger_step  = Cpt(EpicsSignal, pv_names['Scaler']['HC10E_TrigStep'])

    ENC  = Cpt(EpicsSignalRO, pv_names['Scaler']['HC10E_ENC'])
    I0   = Cpt(EpicsSignalRO, pv_names['Scaler']['HC10E_I0'])
    It   = Cpt(EpicsSignalRO, pv_names['Scaler']['HC10E_It'])
    If   = Cpt(EpicsSignalRO, pv_names['Scaler']['HC10E_If'])
    Ir   = Cpt(EpicsSignalRO, pv_names['Scaler']['HC10E_Ir'])

    Enc_waveform  = Cpt(EpicsSignalRO, pv_names['Scaler']['HC10E_ENC_WF'])
    I0_waveform   = Cpt(EpicsSignalRO, pv_names['Scaler']['HC10E_I0_WF'])
    It_waveform   = Cpt(EpicsSignalRO, pv_names['Scaler']['HC10E_It_WF'])
    If_waveform   = Cpt(EpicsSignalRO, pv_names['Scaler']['HC10E_If_WF'])
    Ir_waveform   = Cpt(EpicsSignalRO, pv_names['Scaler']['HC10E_Ir_WF'])

scaler_fly = HC10E('', name='scaler_fly')

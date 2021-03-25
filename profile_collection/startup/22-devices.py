import time as ttime
import numpy as np
import threading
import logging

import ophyd
from ophyd import (Component as Cpt, Device, EpicsSignal, EpicsSignalRO)
from ophyd.flyers import MonitorFlyerMixin
from ophyd.utils import OrderedDefaultDict
from ophyd.status import DeviceStatus
import bluesky.plans as bp

from utils import loadPV

logger = logging.getLogger('__name__')

# PV parameter loadings
pv_names = loadPV()

_hc = 12398.5
_si_111 = 5.4309/np.sqrt(3)

# Energy Flyer
class DCMFlyer(Device):
    """DCM flyer with HC10E counter board

    :PV fly_motor : monochromator theta1
    :PV fly_motor_speed : monochromator speed [deg/sec]
    :PV fly_motor_stop : Stop monochromator theta
    :PV fly_motor_done_move : Done moving when value is '1', '0' : moving
    :PV scaler_mode : change mode. '0' : normal mode, '1' : fly(trigger) mode
    :PV encoder_steps : Flyer will accumulate counts during specified encoder steps
    :PV scaler_preset : set to '0' will result in measured values to reset
    :PV scaler_reset : reset array waveform

    :PV enc_waveform : encoder waveform
    :PV I0_waveform : I0 waveform
    :PV It_waveform : It waveform
    :PV If_waveform : If waveform
    :PV Ir_waveform : Ir waveform

    """
    fly_motor           = Cpt(EpicsSignal,   pv_names['DCM']["mono_theta"])
    fly_motor_speed     = Cpt(EpicsSignal,   pv_names['DCM']["mono_theta_speed"])
    fly_motor_stop      = Cpt(EpicsSignal,   pv_names['DCM']["mono_theta_stop"])
    fly_motor_done_move = Cpt(EpicsSignalRO, pv_names['DCM']["mono_theta_dmov"])
    fly_motor_eres      = Cpt(EpicsSignalRO, pv_names['DCM']["mono_enc_resolution"])

    scaler_mode         = Cpt(EpicsSignal,   pv_names['Scaler']["HC10E_Mode"])
    encoder_steps       = Cpt(EpicsSignal,   pv_names['Scaler']["HC10E_TrigStep"])
    scaler_preset       = Cpt(EpicsSignal,   pv_names['Scaler']["HC10E_Preset"])
    scaler_reset        = Cpt(EpicsSignal,   pv_names['Scaler']["HC10E_Reset"])

    enc_waveform        = Cpt(EpicsSignalRO, pv_names['Scaler']["HC10E_ENC_WF"])
    I0_waveform         = Cpt(EpicsSignalRO, pv_names['Scaler']["HC10E_I0_WF"])
    It_waveform         = Cpt(EpicsSignalRO, pv_names['Scaler']["HC10E_It_WF"])
    If_waveform         = Cpt(EpicsSignalRO, pv_names['Scaler']["HC10E_If_WF"])
    Ir_waveform         = Cpt(EpicsSignalRO, pv_names['Scaler']["HC10E_Ir_WF"])

    def __init__(self, *args, target_energy=None, speed=None, encoder_steps=None, stream_names=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.complete_status = None
        self._acquiring = False
        self._paused = False

        self.stream_names = stream_names
        self._collected_data = None
        self._start_energy = 8333

        # Flyer motor target position
        if target_energy is None:
            self._target_energy = 9300
        else:
            self._target_energy = target_energy

        # Flyer motor speed
        self._speed = speed

        # Encoder step size for accumulating counts
        self._encoder_step_counts = encoder_steps

        # Number of scan points to read
        self._num_of_counts = int(100)

    def energyToTheta(self, energy):
        _th = np.rad2deg(np.arcsin(_hc/(2.*_si_111*energy)))
        return _th

    def pause(self):
        # Stop motor motion
        self.fly_motor_stop.put(1, wait=True)

    def resume(self):
        # Resume without erasing
        _th = self.energyToTheta(self._target_energy)
        self.fly_motor.put(_th, wait=True)

    def setStartEnergy(self, energy):
        self._start_energy = energy

    def setTargetEnergy(self, energy):
        self._target_energy = energy

    def setSpeed(self, speed):
        """Set Scan Speed"""
        self._speed = speed

    def setEncSteps(self, steps):
        self._encoder_step_counts = steps

    def setNumOfCounts(self, counts):
        self._num_of_counts = int(counts)

    def checkMotor(self):
        """check motor motion on a separated thread"""

        # Wait for completion
        while True:
            if self.fly_motor_done_move.get() == 0:
                # logger.error("fly_motor : {}".format(self.fly_motor_done_move.get()))
                ttime.sleep(0.1)
            else:
                # logger.error("fly_motor : {}".format(self.fly_motor_done_move.get()))
                break

        # logger.error("Done fly")
        # After the wait, we declare success
        self._acquiring = False
        self.complete_status._finished(success=True)

    def kickoff(self):
        '''Start collection

        Returns
        -------
        DeviceStatus
            This will be set to done when acquisition has begun
        '''
        # Put scaler in fly mode
        # self.scaler_mode.put(1, wait=True)

        # Set monochromator speed
        self.fly_motor_speed.put(self._speed, wait=True)

        # Set encoder step size for accumulating counts
        self.encoder_steps.put(self._encoder_step_counts, wait=True)

        # Reset scaler array waveform
        self.scaler_reset.put(1, wait=True)

        # Reset scaler counter
        self.scaler_preset.put(0, wait=True)

        # Wait For HC10E scaler reset
        ttime.sleep(.2)

        # Indicators
        self._start_time = ttime.time()
        self._acquiring = True
        self._paused = False

        # Put scaler in fly mode
        self.scaler_mode.put(1, wait=True)

        # Start motor motion to target_position asynchronously
        _th = self.energyToTheta(self._target_energy)
        self.fly_motor.put(_th, wait=False)
        ttime.sleep(0.2)

        thread = threading.Thread(target=self.checkMotor, daemon=True)
        thread.start()

        # make status object, Indicate flying has started
        self.kickoff_status = DeviceStatus(self)
        self.kickoff_status._finished(success=True)

        self.complete_status = DeviceStatus(self)

        return self.kickoff_status


    def complete(self):
        '''Wait for flying to be complete'''
        if self.complete_status is None:
            raise RuntimeError('No collection in progress')

        return self.complete_status

    def describe_collect(self):
        d = dict(
        source = "HC10E",
        dtype = "number",
        shape = (1,)
        )

        return {
            'primary': {
                "ENC"    : d,
                "I0"     : d,
                "It"     : d,
                "If"     : d,
                "Ir"     : d
            }}

    def collect(self):
        # Put scaler in normal mode
        self.scaler_mode.put(0, wait=False)

        # '''Retrieve all collected data'''
        if self._acquiring:
            raise RuntimeError('Acquisition still in progress. Call complete()'
                               ' first.')

        self.complete_status = None

        # Retrive waveforms from epics PVs
        ENC = self.enc_waveform.get()
        if isinstance(ENC, type(None)):
            ENC = self.enc_waveform.get()

        I0  = self.I0_waveform.get()
        if isinstance(I0, type(None)):
            I0  = self.I0_waveform.get()

        It  = self.It_waveform.get()
        if isinstance(It, type(None)):
            It  = self.It_waveform.get()

        If  = self.If_waveform.get()
        if isinstance(If, type(None)):
            If  = self.If_waveform.get()

        Ir  = self.Ir_waveform.get()
        if isinstance(Ir, type(None)):
            Ir  = self.Ir_waveform.get()

        if self._num_of_counts > len(ENC):
            self._num_of_counts = len(ENC)

        # logger.error("ENC : {}".format(ENC))
        # logger.error("num_of_counts : {}".format(self._num_of_counts))
        # for idx in range(len(ENC)):
        for idx in range(int(self._num_of_counts)):
            t = ttime.time()
            enc = ENC[idx]
            _i0  = I0[idx]
            _it  = It[idx]
            _if  = If[idx]
            _ir  = Ir[idx]

            d = dict(
                time=t,
                data=dict(ENC=enc, I0=_i0, It=_it, If=_if, Ir=_ir),
                timestamps=dict(ENC=t, I0=t, It=t, If=t, Ir=t)
            )
            yield d


""" Example)
RE(bpp.monitor_during_wrapper(bp.fly([energyFlyer]), [dcm, I0_sim, It_sim, If_sim, Ir_sim]))
"""

energyFlyer = DCMFlyer('', name='energyFlyer')

class ICAmplifier(Device):
    """Keithely 428 Current Amplifier Ophyd device"""
    def __init__(self,
                 *args,
                 gain_set_pv,
                 gain_get_pv,
                 autoFilter_set_pv,
                 autoFilter_get_pv,
                 riseTime_set_pv,
                 riseTime_get_pv,
                 zcheck_set_pv,
                 zcheck_get_pv,
                 filter_set_pv,
                 filter_get_pv,
                 x10_set_pv,
                 x10_get_pv,
                 autoSupEnable_set_pv,
                 autoSupEnable_get_pv,
                 suppression_enable_set_pv,
                 suppression_enable_get_pv,
                 suppressionValue_set_pv,
                 suppressionExponent_set_pv,
                 suppression_set_pv,
                 suppression_get_pv,
                 overload_get_pv,
                 **kwargs):

        super().__init__(*args, **kwargs)

        self.gain = EpicsSignal(write_pv=self.prefix + gain_set_pv,
                                read_pv=self.prefix + gain_get_pv,
                                auto_monitor=True,
                                name=self.name)

        self.autoFilter = EpicsSignal(write_pv=self.prefix + autoFilter_set_pv,
                                      read_pv=self.prefix + autoFilter_get_pv,
                                      auto_monitor=True,
                                      name=self.name)

        self.filter = EpicsSignal(write_pv=self.prefix + filter_set_pv,
                                  read_pv=self.prefix + filter_get_pv,
                                  auto_monitor=True,
                                  name=self.name)

        self.riseTime = EpicsSignal(write_pv=self.prefix + riseTime_set_pv,
                                      read_pv=self.prefix + riseTime_get_pv,
                                      auto_monitor=True,
                                      name=self.name)

        self.zeroCheck = EpicsSignal(write_pv=self.prefix + zcheck_set_pv,
                                      read_pv=self.prefix + zcheck_get_pv,
                                      auto_monitor=True,
                                      name=self.name)

        self.x10 = EpicsSignal(write_pv=self.prefix + x10_set_pv,
                                      read_pv=self.prefix + x10_get_pv,
                                      auto_monitor=True,
                                      name=self.name)

        self.suppressionValue = EpicsSignal(write_pv=self.prefix + suppressionValue_set_pv,
                                            read_pv=self.prefix + suppressionValue_set_pv,
                                            auto_monitor=True,
                                            name=self.name)

        self.suppressionExponent = EpicsSignal(write_pv=self.prefix + suppressionExponent_set_pv,
                                               read_pv=self.prefix + suppressionExponent_set_pv,
                                               auto_monitor=True,
                                               name=self.name)

        self.autoSupEnable = EpicsSignal(write_pv=self.prefix + autoSupEnable_set_pv,
                                         read_pv=self.prefix + autoSupEnable_get_pv,
                                         auto_monitor=True,
                                         name=self.name)

        self.suppression = EpicsSignal(write_pv=self.prefix + suppression_set_pv,
                                       read_pv=self.prefix + suppression_get_pv,
                                       auto_monitor=True,
                                       name=self.name)

        self.overload = EpicsSignalRO(read_pv=self.prefix + overload_get_pv,
                                      auto_monitor=True,
                                      name=self.name)

    def set_gain(self, value: int):
        val = int(value)
        self.gain.put(val)

    def get_gain(self):
        return self.gain.get()

    def set_suppress(self, value: int):
        """Set current suppression depending on gain"""
        if value == 0:
            # Suppression : -0.05E-3
            self.suppressionValue.set(-0.05)
            self.suppressionExponent.set(6)
        elif value == 1:
            # Suppression : -5E-6
            self.suppressionValue.set(-5)
            self.suppressionExponent.set(3)
        elif value == 2:
            # Suppression : -0.5E-6
            self.suppressionValue.set(-0.5)
            self.suppressionExponent.set(3)
        elif value == 3:
            # Suppression : -0.05E-6
            self.suppressionValue.set(-0.05)
            self.suppressionExponent.set(3)
        elif value == 4:
            # Suppression : -5E-9
            self.suppressionValue.set(-5)
            self.suppressionExponent.set(0)
        elif value == 5:
            # Suppression : -0.5E-9
            self.suppressionValue.set(-0.5)
            self.suppressionExponent.set(0)
        elif value == 6:
            # Suppression : -0.05E-9
            self.suppressionValue.set(-0.05)
            self.suppressionExponent.set(0)
        elif value == 7:
            # Suppression : -0.005E-9
            self.suppressionValue.set(-0.005)
            self.suppressionExponent.set(0)
        else:
            pass

    def do_correct(self):
        self.zeroCheck.put(2)

    def set_zcheck(self, value: int):
        val = int(value)
        self.zeroCheck.put(val)

    def get_zcheck(self):
        return self.zeroCheck.enum_strs[self.zeroCheck.get()]


I0_amp = ICAmplifier('',
                     gain_set_pv = pv_names['Amplifier']['I0_gain_set'],
                     gain_get_pv = pv_names['Amplifier']['I0_gain_get'],
                     autoFilter_set_pv = pv_names['Amplifier']['I0_auto_filter_set'],
                     autoFilter_get_pv = pv_names['Amplifier']['I0_auto_filter_get'],
                     riseTime_set_pv = pv_names['Amplifier']['I0_rise_time_set'],
                     riseTime_get_pv = pv_names['Amplifier']['I0_rise_time_get'],
                     zcheck_set_pv = pv_names['Amplifier']['I0_zero_check_set'],
                     zcheck_get_pv = pv_names['Amplifier']['I0_zero_check_get'],
                     filter_set_pv = pv_names['Amplifier']['I0_filter_set'],
                     filter_get_pv = pv_names['Amplifier']['I0_filter_get'],
                     x10_set_pv = pv_names['Amplifier']['I0_x10_set'],
                     x10_get_pv = pv_names['Amplifier']['I0_x10_get'],
                     autoSupEnable_set_pv = pv_names['Amplifier']['I0_auto_suppression_set'],
                     autoSupEnable_get_pv = pv_names['Amplifier']['I0_auto_suppression_get'],
                     suppression_enable_set_pv = pv_names['Amplifier']['I0_suppression_set'],
                     suppression_enable_get_pv = pv_names['Amplifier']['I0_suppression_get'],
                     suppressionValue_set_pv = pv_names['Amplifier']['I0_suppression_value_set'],
                     suppressionExponent_set_pv = pv_names['Amplifier']['I0_suppression_exponent_set'],
                     suppression_set_pv = pv_names['Amplifier']['I0_suppression_set'],
                     suppression_get_pv = pv_names['Amplifier']['I0_suppression_get'],
                     overload_get_pv = pv_names['Amplifier']['I0_overload_get'], name='I0_amp')

It_amp = ICAmplifier('',
                     gain_set_pv = pv_names['Amplifier']['It_gain_set'],
                     gain_get_pv = pv_names['Amplifier']['It_gain_get'],
                     autoFilter_set_pv = pv_names['Amplifier']['It_auto_filter_set'],
                     autoFilter_get_pv = pv_names['Amplifier']['It_auto_filter_get'],
                     riseTime_set_pv = pv_names['Amplifier']['It_rise_time_set'],
                     riseTime_get_pv = pv_names['Amplifier']['It_rise_time_get'],
                     zcheck_set_pv = pv_names['Amplifier']['It_zero_check_set'],
                     zcheck_get_pv = pv_names['Amplifier']['It_zero_check_get'],
                     filter_set_pv = pv_names['Amplifier']['It_filter_set'],
                     filter_get_pv = pv_names['Amplifier']['It_filter_get'],
                     x10_set_pv = pv_names['Amplifier']['It_x10_set'],
                     x10_get_pv = pv_names['Amplifier']['It_x10_get'],
                     autoSupEnable_set_pv = pv_names['Amplifier']['It_auto_suppression_set'],
                     autoSupEnable_get_pv = pv_names['Amplifier']['It_auto_suppression_get'],
                     suppression_enable_set_pv = pv_names['Amplifier']['It_suppression_set'],
                     suppression_enable_get_pv = pv_names['Amplifier']['It_suppression_get'],
                     suppressionValue_set_pv = pv_names['Amplifier']['It_suppression_value_set'],
                     suppressionExponent_set_pv = pv_names['Amplifier']['It_suppression_exponent_set'],
                     suppression_set_pv = pv_names['Amplifier']['It_suppression_set'],
                     suppression_get_pv = pv_names['Amplifier']['It_suppression_get'],
                     overload_get_pv = pv_names['Amplifier']['It_overload_get'], name='It_amp')

If_amp = ICAmplifier('',
                     gain_set_pv = pv_names['Amplifier']['If_gain_set'],
                     gain_get_pv = pv_names['Amplifier']['If_gain_get'],
                     autoFilter_set_pv = pv_names['Amplifier']['If_auto_filter_set'],
                     autoFilter_get_pv = pv_names['Amplifier']['If_auto_filter_get'],
                     riseTime_set_pv = pv_names['Amplifier']['If_rise_time_set'],
                     riseTime_get_pv = pv_names['Amplifier']['If_rise_time_get'],
                     zcheck_set_pv = pv_names['Amplifier']['If_zero_check_set'],
                     zcheck_get_pv = pv_names['Amplifier']['If_zero_check_get'],
                     filter_set_pv = pv_names['Amplifier']['If_filter_set'],
                     filter_get_pv = pv_names['Amplifier']['If_filter_get'],
                     x10_set_pv = pv_names['Amplifier']['If_x10_set'],
                     x10_get_pv = pv_names['Amplifier']['If_x10_get'],
                     autoSupEnable_set_pv = pv_names['Amplifier']['If_auto_suppression_set'],
                     autoSupEnable_get_pv = pv_names['Amplifier']['If_auto_suppression_get'],
                     suppression_enable_set_pv = pv_names['Amplifier']['If_suppression_set'],
                     suppression_enable_get_pv = pv_names['Amplifier']['If_suppression_get'],
                     suppressionValue_set_pv = pv_names['Amplifier']['If_suppression_value_set'],
                     suppressionExponent_set_pv = pv_names['Amplifier']['If_suppression_exponent_set'],
                     suppression_set_pv = pv_names['Amplifier']['If_suppression_set'],
                     suppression_get_pv = pv_names['Amplifier']['If_suppression_get'],
                     overload_get_pv = pv_names['Amplifier']['If_overload_get'], name='If_amp')

Ir_amp = ICAmplifier('',
                     gain_set_pv = pv_names['Amplifier']['Ir_gain_set'],
                     gain_get_pv = pv_names['Amplifier']['Ir_gain_get'],
                     autoFilter_set_pv = pv_names['Amplifier']['Ir_auto_filter_set'],
                     autoFilter_get_pv = pv_names['Amplifier']['Ir_auto_filter_get'],
                     riseTime_set_pv = pv_names['Amplifier']['Ir_rise_time_set'],
                     riseTime_get_pv = pv_names['Amplifier']['Ir_rise_time_get'],
                     zcheck_set_pv = pv_names['Amplifier']['Ir_zero_check_set'],
                     zcheck_get_pv = pv_names['Amplifier']['Ir_zero_check_get'],
                     filter_set_pv = pv_names['Amplifier']['Ir_filter_set'],
                     filter_get_pv = pv_names['Amplifier']['Ir_filter_get'],
                     x10_set_pv = pv_names['Amplifier']['Ir_x10_set'],
                     x10_get_pv = pv_names['Amplifier']['Ir_x10_get'],
                     autoSupEnable_set_pv = pv_names['Amplifier']['Ir_auto_suppression_set'],
                     autoSupEnable_get_pv = pv_names['Amplifier']['Ir_auto_suppression_get'],
                     suppression_enable_set_pv = pv_names['Amplifier']['Ir_suppression_set'],
                     suppression_enable_get_pv = pv_names['Amplifier']['Ir_suppression_get'],
                     suppressionValue_set_pv = pv_names['Amplifier']['Ir_suppression_value_set'],
                     suppressionExponent_set_pv = pv_names['Amplifier']['Ir_suppression_exponent_set'],
                     suppression_set_pv = pv_names['Amplifier']['Ir_suppression_set'],
                     suppression_get_pv = pv_names['Amplifier']['Ir_suppression_get'],
                     overload_get_pv = pv_names['Amplifier']['Ir_overload_get'], name='Ir_amp')


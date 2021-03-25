import bluesky.plans as bp
import bluesky.plan_stubs as bps
import bluesky.plan_patterns as bpt
import bluesky.preprocessors as bpp
from itertools import chain

import time as ttime
import numpy as np

import bluesky.utils as utils
from bluesky.utils import (separate_devices,
                           all_safe_rewind,
                           Msg,
                           merge_cycler,
                           ensure_generator,
                           short_uid as _short_uid)

from silx.gui.utils.concurrent import submitToQtMainThread as _submit

try:
    # cytools is a drop-in replacement for toolz, implemented in Cython
    from cytools import partition
except ImportError:
    from toolz import partition

logger = logging.getLogger('plan')

def stop_and_mv(motor, pos):
    """ Stop motor and then move to pos"""

    if False:
        # Stop motor
        yield from bps.stop(motor)

    # Sleep until motor stop
    while(True):
        if motor.moving:
            yield from bps.sleep(0.1)
        else:
            yield from bps.sleep(0.5)

            if not motor.moving:
                break

    # Move to the target position
    yield from bps.mv(motor, pos)

def delay_per_step(detectors, motor, step, delay_time):
    """
    Customized 1d step for delay
    """

    def move():
        grp = _short_uid('set')
        yield Msg('checkpoint')
        yield Msg('set', motor, step, group=grp)
        yield Msg('wait', None, group=grp)

    def delay():
        yield Msg('sleep', None, delay_time)

    yield from move()
    # added for wait motor to settle
    yield from delay()

    return (yield from bps.trigger_and_read(list(detectors) + [motor]))

def sleep_and_count(detectors, waitTime=2):
    """sleep for waitTime and then count

    :param detectors : ophyd counters and signals
    :param waitTime : sleep time
    """
    # wait for finish
    yield from bps.sleep(waitTime)

    # move to energy
    yield from bp.count(detectors)

def mv_and_wait(motor, energy, delay=2):
    """ Move motor to energy[eV], and wait for temperature saturation

    :param motor : DCM mono angle
    :param energy : Target Energy
    :param delay : wait time[sec]

    """
    # wait for finish
    yield from bps.wait()

    # move to energy
    yield from bps.mv(motor, energy)

    # wait for temperature stabilization
    yield from bps.sleep(delay)

def cleanup_energy_scan(motor, E0):
    # move Energy to E0
    return(yield from bps.mv(dcm.energy, E0))

def energy_list_scan(detectors,
                     motor,
                     E0,
                     energy_list,
                     time_list,
                     delay_time,
                     per_step=delay_per_step,
                     md={}):


    """
    Scan over energy lists.

    Parameters
    ----------
    detectors : list, list of 'readable' objects
    motor : object, any 'settable' object (motor, temp controller, etc.)
    E0 : edge energy in eV
    energy_list : list of energy list
    time_list : count time list
    per_step : callable, optional
               hook for customizing action of inner loop (messages per step)
               Expected signature:
               ``f(detectors, motor, step, delay_time) -> plan (a generator)``
    md : dict, optional, metadata
    """
    energy_list = list(energy_list)

    np_energy_list = np.array(energy_list).flatten()
    num_points = len(np_energy_list)

    _md = {'detectors': [det.name for det in detectors],
           'motors': [motor.name],
           'num_points': num_points,
           'num_intervals': num_points - 1,
           'plan_name': 'energy_list_scan',
           'delay_after_set_energy' : delay_time,
           'hints': {},
           }
    _md.update(md or {})

    if per_step is None:
        per_step = bps.one_1d_step

    @bpp.stage_decorator(list(detectors) + [motor])
    @bpp.run_decorator(md=_md)
    def inner_list_scan(energy_list, time_list):
        index = 0
        for item in time_list:
            # set counter time
            yield from bps.abs_set(scaler.preset_time, item)

            # move and count
            for step in energy_list[index]:
                yield from per_step(detectors, motor, step, delay_time)
            index += 1

    startEnergy = energy_list[0][0]

    # move Energy to Start_Energy - 200 eV
    yield from bps.mv(dcm.energy, startEnergy-200)

    # sleep 2 seconds at -200 eV from Start_Energy
    yield from bps.sleep(2)

    # move Energy to Start_Energy
    yield from bps.mv(dcm.energy, startEnergy)

    # sleep 1 seconds at Start_Energy
    yield from bps.sleep(1)

    # mark as a checkpoint, motor comeback to this position
    # when scan is interrupted
    yield from bps.checkpoint()
    yield from inner_list_scan(energy_list, time_list)

    # move back to E0 after scan
    yield from bps.mv(dcm.energy, E0)

    return 0

def exafs_scan(detectors,
               motor,
               E0,
               energy_list,
               time_list,
               delay_time,
               per_step=delay_per_step,
               md={},
               waitTime=0):
    """

    EXAFS scan with waitTime sleep for autoCounter

    """

    yield from bps.sleep(waitTime)
    yield from bpp.finalize_wrapper(energy_list_scan(detectors,
                                                     motor,
                                                     E0,
                                                     energy_list,
                                                     time_list,
                                                     delay_time,
                                                     per_step=delay_per_step,
                                                     md=md),
                                    cleanup_energy_scan(motor, E0))


def multi_exafs_scan(detectors, motor, E0, energy_list, time_list,
                     delay_time, waitTime, device_dict, parent):
    """ Repeat multiple or batch exafs_scan"""

    batch_scan = parent.control.use_batch_checkbox.isChecked()

    if batch_scan:
        # Batch scan
        sample_names, sample_info = parent.sampleTable.getData()

        for idx, sample_name in enumerate(sample_names):

            # Do not run this scan if sample_name is empty
            if not len(sample_name):
                continue

            sample_pos, num_scan = sample_info[idx]
            num_scan = int(num_scan)

            if num_scan > 1:
                # Multi-scan
                _submit(parent.control.run_type.setCurrentIndex, 1)
            else:
                # Single-scan
                _submit(parent.control.run_type.setCurrentIndex, 0)

            # Set number of scan
            _submit(parent.control.number_of_scan_edit.setValue, num_scan)

            # Set filename
            _submit(parent.control.filename_edit.setText, sample_name)

            parent.toLog("Current sample_name in Batch mode is " + sample_name)

            # Disable controls
            parent.control_enable(False)

            # Move to sample position
            sample_changer = device_dict['sampleChanger']
            yield from stop_and_mv(sample_changer, sample_pos)
            parent.toLog("Sample position is moving to " + str(sample_pos))

            for _ in range(num_scan):
                parent.subscribe_callback()
                parent.toLog("A new scan is started", color='blue')

                # Do exafs scan
                yield from exafs_scan(detectors,
                                      motor,
                                      E0,
                                      energy_list,
                                      time_list,
                                      delay_time,
                                      waitTime)

                parent.unsubscribe_callback()

                # Decrease remaining scan-number
                remaining_scan = num_scan - (idx + 1)
                if remaining_scan > 0:
                    _submit(parent.control.number_of_scan_edit.setValue, remaining_scan)
                    _submit(parent.control.number_of_scan_edit.setDisabled, True)

    else:
        # Multi scan
        num_scan = int(parent.control.number_of_scan_edit.value())

        for idx in range(num_scan):

            parent.subscribe_callback()
            parent.toLog("A new scan is started : {}".format(idx+1), color='blue')

            # Do exafs scan
            yield from exafs_scan(detectors,
                                    motor,
                                    E0,
                                    energy_list,
                                    time_list,
                                    delay_time,
                                    waitTime)

            parent.unsubscribe_callback()

            # Decrease remaining scan-number
            remaining_scan = num_scan - (idx + 1)
            if remaining_scan > 0:
                _submit(parent.control.number_of_scan_edit.setValue, remaining_scan)
                _submit(parent.control.number_of_scan_edit.setDisabled, True)


def multi_exafs_scan_with_cleanup(detectors, motor, E0, energy_list, time_list,
                     delay_time, waitTime, device_dict, parent):
    """ Repeat multiple or batch exafs_scan with clean-up"""
    yield from bpp.finalize_wrapper(multi_exafs_scan(detectors,
                                                     motor,
                                                     E0,
                                                     energy_list,
                                                     time_list,
                                                     delay_time,
                                                     waitTime,
                                                     device_dict,
                                                     parent),
                                    finalize(parent, device_dict, E0))


def finalize(parent, device_dict, E0):
    """ Cleanup exafs_scan """

    device_keys = device_dict.keys()

    try:
        fly_mode = parent.control.run_type.currentIndex() == 2
        if fly_mode:
            orig_mono_speed = parent._orig_mono_speed
            flyer = device_dict['energyFlyer']

            yield from bps.abs_set(flyer.fly_motor_speed, orig_mono_speed)
            # yield from bps.abs_set(flyer.fly_motor_stop, 1)

        if 'dcm' in device_keys:
            _submit(parent.control.abortButton.setDisabled, True)
            # _submit(parent.control.pauseButton.setDisabled, True)
            # _submit(parent.control.resumeButton.setDisabled, True)
            _submit(parent.control.ecal_abortButton.setDisabled, True)
            _submit(parent.control.run_start.setDisabled, True)
            _submit(parent.control.run_calibrate_button.setDisabled, True)

            dcm = device_dict['dcm']
            parent.toLog("Energy is moving to " + str(E0) + " keV", color='blue')
            yield from stop_and_mv(dcm.energy, E0)


    finally:
        parent.blinkStatus = False
        parent.control_enable(True)

        try:
            parent.unsubscribe_callback()
        except Exception as e:
            print("Exception in unsubscribe callback : {}".format(e))

        parent.toLog("Scan is finished", color='blue')


def fly_scan(E0, mono_speed, device_dict, parent):
    # Initial settings
    flyer = device_dict['energyFlyer']

    parent.subscribe_callback()
    parent.toLog("A new fly scan is started!", color='blue')

    # Set to fly scan speed
    yield from bps.abs_set(flyer.fly_motor_speed, mono_speed)

    # Do fly scan
    yield from bpp.monitor_during_wrapper(bp.fly([flyer]),
                                          [device_dict['ENC_fly_counter'],
                                           device_dict['I0_fly_counter'],
                                           device_dict['It_fly_counter'],
                                           device_dict['If_fly_counter'],
                                           device_dict['Ir_fly_counter']])

    # Set to normal speed
    yield from bps.abs_set(flyer.fly_motor_speed, parent._orig_mono_speed)

    # Move to E0
    yield from stop_and_mv(dcm, E0)

    parent.unsubscribe_callback()

    # Decrease remaining scan-number
    num_scan = int(parent.control.number_of_scan_edit.value())
    if num_scan > 1:
        _submit(parent.control.number_of_scan_edit.setValue, num_scan-1)

        cooling_time = parent.control.flyControl.flyCoolTime.value()
        parent.toLog("Cooling dcm. The next scan starts after {} seconds.".format(cooling_time))
        yield from bps.sleep(cooling_time)


def fly_scan_with_cleanup(E0, mono_speed, device_dict, parent):
    """ Repeat multiple or batch exafs_scan with clean-up"""
    yield from bpp.finalize_wrapper(fly_scan(E0, mono_speed, device_dict, parent),
                                    finalize(parent, device_dict, E0))

def move_and_count(motor, target):
    yield from bps.open_run(None)
    yield from bps.mv(motor, target)
    yield from bps.close_run()

def delay_scan_with_cleanup(detectors,
                     motor,
                     E0,
                     start,
                     stop,
                     step_size,
                     delay_time,
                     per_step=delay_per_step,
                     md={}):
    yield from bpp.finalize_wrapper(delay_scan(detectors,
                                               motor,
                                               E0,
                                               start,
                                               stop,
                                               step_size,
                                               delay_time,
                                               per_step=delay_per_step,
                                               md=md),
                                    cleanup_energy_scan(motor, E0))


def delay_scan(detectors, motor, E0, start, stop,
               step_size, delay_time, per_step=delay_per_step, md={}):
    """
    Scan over one multi-motor trajectory with delay time.

    Parameters
    ----------
    detectors : list
        list of 'readable' objects

    motor : object, any 'settable' object (motor, temp controller, etc.)

    E0 : edge energy in eV

    start : start energy in eV

    stop : stop energy in eV

    step_size : energy step in eV

    per_step : callable, optional
               hook for customizing action of inner loop (messages per step)
               Expected signature:
               ``f(detectors, motor, step, delay_time) -> plan (a generator)``
    md : dict, optional, metadata

    See Also
    --------
    :func:`bluesky.plans.relative_inner_product_scan`
    :func:`bluesky.plans.grid_scan`
    :func:`bluesky.plans.scan_nd`
    """

    _md = {'detectors': [det.name for det in detectors],
           'motors': [motor.name],
           'plan_name': 'delay_scan',
           'delay_after_set_energy' : delay_time,
           'hints': {},
           }
    _md.update(md or {})

    if per_step is None:
        per_step = bps.one_1d_step

    num = int((stop - start)/step_size) + 1
    start = E0 + start
    stop  = E0 + stop
    scan_list = np.linspace(start, stop, num, endpoint=True)

    @bpp.stage_decorator(list(detectors) + [motor])
    @bpp.run_decorator(md=_md)
    def inner_scan_nd():
        for step in list(scan_list):
            yield from per_step(detectors, motor, step, delay_time)

    # # move Energy to E0
    # yield from bps.mv(dcm.energy, E0)

    # move Energy to Start_Energy - 200 eV
    yield from bps.mv(dcm.energy, start-200)

    # sleep 2 seconds
    yield from bps.sleep(2)

    # move Energy to Start_Energy
    yield from bps.mv(dcm.energy, start)

    # sleep 1 seconds
    yield from bps.sleep(1)

    # mark as a checkpoint, motor comeback to this position
    # when scan is interrupted
    yield from bps.checkpoint()

    yield from inner_scan_nd()

    # move back to E0 after scan
    return (yield from bps.mv(dcm.energy, E0))


# tweak custom
def tweak_custom(detector, target_field, motor, step,
                 time, obj, *, md=None):
    """
    Move motor and read a detector with an interactive prompt.

    Parameters
    ----------
    detector : Device
    target_field : string
        data field whose output is the focus of the adaptive tuning
    motor : Device
    step : float
        initial suggestion for step size
    md : dict, optional
        metadata
    time : count time
    obj : custom class for control tweak, obj.wait and obj.step is necessary
    """
    prompt_str = '{0}, {1:.3}, {2:.3}, ({3}) '

    _md = {'detectors': [detector.name],
           'motors': [motor.name],
           'plan_args': {'detector': repr(detector),
                         'target_field': target_field,
                         'motor': repr(motor),
                         'step': step},
           'plan_name': 'tweak',
           'hints': {},
           }
    try:
        dimensions = [(motor.hints['fields'], 'primary')]
    except (AttributeError, KeyError):
        pass
    else:
        _md['hints'].update({'dimensions': dimensions})
    _md.update(md or {})
    d = detector
    try:
        from IPython.display import clear_output
    except ImportError:
        # Define a no-op for clear_output.
        def clear_output(wait=False):
            pass

    @bpp.stage_decorator([detector, motor])
    @bpp.run_decorator(md=_md)
    def tweak_core():
        nonlocal step

        while True:
            yield Msg('create', None, name='primary')
            ret_mot = yield Msg('read', motor)
            if ret_mot is None:
                return
            key = list(ret_mot.keys())[0]
            pos = ret_mot[key]['value']
            yield Msg('trigger', d, group='A')
            yield Msg('wait', None, 'A')
            reading = yield Msg('read', d)
            val = reading[target_field]['value']
            yield Msg('save')


            prompt = prompt_str.format(motor.name, float(pos),
                                       float(val), step)
            # print(prompt)

            # wait until user click
            while obj.wait:
                yield Msg('sleep', None, 0.1)

                # change tweak step
                new_step = obj.step

            if new_step:
                try:
                    step = float(new_step)
                except ValueError:
                    print("step is not valid input")
                    break

            yield Msg('set', motor, pos + step, group='A')
            print('Motor moving...')
            sys.stdout.flush()
            yield Msg('wait', None, 'A')
            clear_output(wait=True)
            # stackoverflow.com/a/12586667/380231
            #print('\x1b[1A\x1b[2K\x1b[1A')
            obj.wait=True

    yield from bps.abs_set(scaler.preset_time, time)

    return (yield from tweak_core())



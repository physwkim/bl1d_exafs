import sys
import os
import psutil

import bluesky.plans as bp
import bluesky.plan_stubs as bps
import bluesky.plan_patterns as bpt
import bluesky.preprocessors as bpp

from main import Main
from silx.gui import qt

# Resize matplotlib font and change font family
import matplotlib.pyplot as plt
plt.rcParams['font.size'] = 14

def quit(*args):
    try:
        main.updatePlotThread.stop()
        main.control.saveSettings()
    except:
        pass

    # sys.exit()
    for proc in psutil.process_iter():
        try:
            proc_name = proc.name()
            proc_id = proc.pid

            is_window = sys.platform.startswith('win')
            if is_window:
                ipython_name = 'ipython.exe'
            else:
                ipython_name = 'ipython'

            if proc_name == ipython_name:
                parent_pid = proc_id
                parent = psutil.Process(parent_pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
        except:
            ...

        try:
            main.dataViewerProc.kill()
        except:
            ...


main = Main(RE=RE,
            plan_funcs=[exafs_scan,
                        multi_exafs_scan_with_cleanup,
                        fly_scan_with_cleanup,
                        scan,
                        tweak_custom,
                        delay_scan_with_cleanup,
                        bpp.monitor_during_wrapper,
                        bp.fly,
                        mv_and_wait,
                        bps.wait,
                        bps.mv,
                        stop_and_mv,
                        sleep_and_count],
            db=db,
            dets=[scaler,
                  preset_time,
                  I0,
                  It,
                  If,
                  Ir],
            motors=[dcm,
                    dcm.energy,
                    dcm.theta,
                    dcm_etc,
                    dcm_etc.theta2,
                    slit],
            devices=[I0_amp,
                     It_amp,
                     If_amp,
                     Ir_amp,
                     ENC_fly_counter,
                     I0_fly_counter,
                     It_fly_counter,
                     If_fly_counter,
                     Ir_fly_counter,
                     energyFlyer,
                     accelerator])

mon = qt.QDesktopWidget().screenGeometry(1)

main.move(mon.left(), mon.top())
main.setWindowIcon(qt.QIcon('icon/control.png'))
main.closed.connect(quit)

main.show()

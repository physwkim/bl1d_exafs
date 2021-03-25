import threading
import time as ttime

from silx.gui import qt
from silx.gui.utils.concurrent import submitToQtMainThread as _submit

class TimerThread(threading.Thread):
    """
    Update timer specified in seconds
    """

    def __init__(self, func, time=1):
        threading.Thread.__init__(self)
        self._stop = False
        self.func = func
        self.time = time

    def run(self):
        while(1):
            if self._stop:
                break
            ttime.sleep(self.time)
            self.func()

    def stop(self):
        self._stop = True

class ThreadManager(object):
    """
    Original code from Xi-cam.core/xicam/core/threads/__init__.py

    A global thread manager that holds on to threads with 'keepalive'
    """

    def __init__(self):
        super().__init__()
        self.timer = TimerThread(self.update, time=1)
        self.timer.start()
        self._threads = []

    @property
    def threads(self):
        return [thread for thread in self._threads]

    def update(self):
        # purge
        for thread in reversed(self.threads):
            if thread._purge:
                self._threads.remove(thread)
                continue
            elif thread.done or thread.cancelled or thread.exception:
                thread._purge = True

    def append(self, thread):
        self._threads.append(thread)

    def stop(self):
        self.timer.stop()

manager = ThreadManager()


class QThreadFuture(qt.QThread):
    """
    modified from Xi-cam.core/xicam/core/threads/__init__.py

    Convenient thread executor
    """

    sigCallback = qt.Signal()
    sigFinished = qt.Signal()
    sigExcept   = qt.Signal(Exception)

    def __init__(self,
                 method,
                 *args,
                 callback_slot=None,
                 finished_slot=None,
                 except_slot=None,
                 threadkey: str = None,
                 priority=qt.QThread.InheritPriority,
                 keepalive=True,
                 timeout=0,
                 **kwargs):
        super(QThreadFuture, self).__init__()

        # Auto-kill other threads with same threadkey
        if threadkey:
            for thread in manager.threads:
                if thread.threadkey == threadkey:
                    thread.cancel()

        self.threadkey = threadkey
        self.callback_slot = callback_slot
        self.except_slot = except_slot

        if finished_slot:
            self.sigFinished.connect(finished_slot)

        if except_slot:
            self.sigExcept.connect(except_slot)

        qt.QApplication.instance().aboutToQuit.connect(self.quit)

        self.method = method
        self.args = args
        self.kwargs = kwargs
        self.timeout = timeout # ms

        self.cancelled = False
        self.exception = None
        self._purge = False
        self.thread = None
        self.priority = priority

        if keepalive:
            manager.append(self)

    @property
    def done(self):
        return self.isFinished()

    @property
    def running(self):
        return self.isRunning()

    def start(self):
        """
        Start the thread
        """

        if self.running:
            raise ValueError("Thread could not be started; it is already running.")
        super(QThreadFuture, self).start(self.priority)
        if self.timeout:
            self._timeout_timer = qt.QTimer.singleShot(self.timeout, self.cancel)

    def run(self, *args, **kwargs):
        """
        Do not call this from the main thread; you're probably looking for start()
        """
        self.cancelled = False
        self.exception = None

        try:
            for self._result in self._run(*args, **kwargs):
                if not isinstance(self._result, tuple):
                    self._result = (self._result,)
                if self.callback_slot:
                    _submit(self.callback_slot, *self._result)

        except Exception as ex:
            self.exception = ex
            self.sigExcept.emit(ex)

        else:
            self.sigFinished.emit()
        finally:
            self.quit()
            qt.QApplication.instance().aboutToQuit.disconnect(self.quit)

    def _run(self, *args, **kwargs):
        yield from self.method(*self.args, **self.kwargs)

    def result(self):
        if not self.running:
            self.start()
        while not self.done and not self.exception:
            time.sleep(0.01)
        if self.exception:
            return self.exception
        return self._result

    def cancel(self):
        self.cancelled = True
        if self.except_slot:
            _submit(self.except_slot, InterruptedError("Thread cancelled."))
        self.quit()
        self.wait()


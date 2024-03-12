# TODO 修改 is_running() 方法, 它用属性覆盖了 psutil 中的 is_running()

import re
import time
import psutil
import logging
import warnings
import threading
import subprocess

import llm4mc.utils as mc_utils


class SubprocessMonitor:
    def __init__(
            self,
            commands,
            name,
            ready_match=r".*",
            log_path="logs",
            callback_match=r"^(?!x)x$",
            callback=None,
            finished_callback=None
    ):
        self.name = name
        self.callback = callback
        self.commands = commands
        self.ready_match = ready_match
        self.callback_match = callback_match
        self.finished_callback = finished_callback

        self.logger = logging.getLogger(name)
        start_time = time.strftime("%Y%m%d_%H%M%S")

        handler = logging.FileHandler(mc_utils.f_join(log_path, f"{start_time}.log"))

        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        handler.setFormatter(formatter)

        self.logger.addHandler(handler)

        self.logger.setLevel(logging.INFO)

        self.thread = None
        self.process = None
        self.ready_line = None
        self.ready_event = None

    def _start(self):
        self.logger.info(f"Starting subprocess with commands: {self.commands}")

        self.process = psutil.Popen(
            self.commands,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        print(f"Subprocess {self.name} started with PID {self.process.pid}.")

        for line in iter(self.process.stdout.readline, ""):
            self.logger.info(line.strip())

            if re.search(self.ready_match, line):
                self.ready_line = line
                self.logger.info("Subprocess is ready.")
                self.ready_event.set()

            if re.search(self.callback_match, line):
                self.callback()

        if not self.ready_event.is_set():
            self.ready_event.set()
            warnings.warn(f"Subprocess {self.name} failed to start.")

        if self.finished_callback:
            self.finished_callback()

    def run(self):
        self.ready_event = threading.Event()
        self.ready_line = None

        self.thread = threading.Thread(target=self._start)
        self.thread.start()

        self.ready_event.wait()

    def stop(self):
        self.logger.info("Stopping subprocess.")
        if self.process and self.process.is_running():
            self.process.terminate()
            self.process.wait()

    @property
    def is_running(self):
        if self.process is None:
            return False
        return self.process.is_running()

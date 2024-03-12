import time
import json
import os.path
import requests
import gymnasium as gym

import llm4mc.utils as mc_utils
from .process_monitor import SubprocessMonitor


class LLM4MCEnv(gym.Env):
    def __init__(
            self,
            mc_port=None,
            server_port=3000,
            log_path="./logs",
            request_timeout=600,
            server_host="http://127.0.0.1"
    ):
        if not mc_port:
            raise ValueError("Mc_port must be specified.")

        self.mc_port = mc_port
        self.log_path = log_path
        self.server_port = server_port
        self.request_timeout = request_timeout
        self.server = f"{server_host}:{server_port}"

        self.mineflayer = self.get_mineflayer_process(server_port)

        self.has_reset = False
        self.connected = False
        self.reset_options = None
        self.server_paused = False

    def get_mineflayer_process(self, server_port):
        log_path = mc_utils.f_mkdir(self.log_path, "mineflayer")

        # TODO file_utils.py 中有文件可以代替
        file_path = os.path.abspath(os.path.dirname(__file__))

        return SubprocessMonitor(
            commands=[
                "node",
                mc_utils.f_join(file_path, "mineflayer/index.js"),
                str(server_port),
            ],
            name="mineflayer",
            ready_match=r"Server started on port (\d+)",
            log_path=log_path,
        )

    def check_process(self):
        retry = 0
        while not self.mineflayer.is_running:
            print("Mineflayer process has exited, restarting")
            self.mineflayer.run()

            if not self.mineflayer.is_running:
                if retry > 3:
                    raise RuntimeError("Mineflayer process failed to start")
                else:
                    continue
            print(self.mineflayer.ready_line)

            res = requests.post(
                f"{self.server}/start",
                json=self.reset_options,
                timeout=self.request_timeout,
            )
            if res.status_code != 200:
                self.mineflayer.stop()
                raise RuntimeError(f"Minecraft server reply with code {res.status_code}")

            return res.json()

    def step(self, code, programs=""):
        if not self.has_reset:
            raise RuntimeError("Environment has not been reset yet")

        self.check_process()
        self.unpause()

        data = {"code": code, "programs": programs}
        res = requests.post(
            f"{self.server}/step",
            json=data,
            timeout=self.request_timeout
        )
        if res.status_code != 200:
            raise RuntimeError("Failed to step Minecraft server")

        returned_data = res.json()
        self.pause()

        return json.loads(returned_data)

    def render(self):
        raise NotImplementedError("render is not implemented")

    def reset(self, *, seed=None, options=None):
        if options is None:
            options = {}

        if options.get("inventory", {}) and options.get("mode", "hard") != "hard":
            raise RuntimeError("inventory can only be set when options is hard")

        self.reset_options = {
            "port": self.mc_port,
            "reset": options.get("mode", "hard"),
            "inventory": options.get("inventory", {}),
            "equipment": options.get("equipment", []),
            "spread": options.get("spread", False),
            "waitTicks": options.get("wait_ticks", 5),
            "position": options.get("position", None),
        }

        self.unpause()
        self.mineflayer.stop()
        time.sleep(1)

        returned_data = self.check_process()

        self.has_reset = True
        self.connected = True
        self.reset_options["reset"] = "soft"

        self.pause()
        return json.loads(returned_data)

    def close(self):
        self.unpause()

        if self.connected:
            res = requests.post(f"{self.server}/stop")
            if res.status_code == 200:
                self.connected = False

        self.mineflayer.stop()

        return not self.connected

    def pause(self):
        if self.mineflayer.is_running and not self.server_paused:
            res = requests.post(f"{self.server}/pause")
            if res.status_code == 200:
                self.server_paused = True
            else:
                print(res.json())
        return self.server_paused

    def unpause(self):
        if self.mineflayer.is_running and self.server_paused:
            res = requests.post(f"{self.server}/pause")
            if res.status_code == 200:
                self.server_paused = False
            else:
                print(res.json())
        return self.server_paused

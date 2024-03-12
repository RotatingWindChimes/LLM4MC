""" Location guide agent """

from __future__ import annotations

import json
import regex
import random
import inflect
import requests
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from llm4mc.prompts import load_prompt


class GuideAgent:
    def __init__(
            self,
            llama_server,
            baseline_model_name="gpt-4",
            temperature=0,
            request_timeout=120,
            request_llama_timeout=2400
    ):
        self.server = llama_server
        self.guide_llm = ChatOpenAI(
            model_name=baseline_model_name,
            temperature=temperature,
            request_timeout=request_timeout,
        )
        self.llama_timeout = request_llama_timeout

    @classmethod
    def render_system_message(cls):
        system_message = SystemMessage(content=load_prompt("guide_locate"))
        assert isinstance(system_message, SystemMessage)

        return system_message

    def render_human_message(self, events, goals):
        goals = GuideAgent.norm_name(GuideAgent.singular_underscore(goals))

        observation_info = self.render_observation(events=events)

        final_goal = f"Goals: {goals}"
        supple_info = (observation_info["environment"].strip() + '\n' +
                       observation_info["position"])

        content = supple_info + "\n" + final_goal

        msg = ('=' * 10 + ' Guide Agent Message ' + '=' * 10).center(100, '=')
        print(f"\033[34m\n{msg}\n{content}\033[0m")

        return content

    @classmethod
    def singular_underscore(cls, key):
        p = inflect.engine()

        key = key.strip(' .\n').lower().replace(" ", "_")

        singular_key = p.singular_noun(key)

        return singular_key if singular_key else key

    @classmethod
    def norm_name(cls, item_name):
        if item_name.endswith('plank'):
            item_name += 's'

        return item_name

    @classmethod
    def render_observation(cls, *, events):
        assert events[-1][0] == "observe", "Last event must be observe"

        event = events[-1][1]

        voxels = event["voxels"]
        biome = event["status"]["biome"]
        entities = event["status"]["entities"]
        position = event["status"]["position"]

        nearby_item = voxels + list(entities.keys())

        observation = {
            "biome": f"Biome: {biome}\n",
            "environment": f"Environment: {nearby_item}\n",
            "position": f"Position: {(position['x'], position['y'], position['z'])}"
        }

        return observation

    def get_gpt4_response(self, events, goals):
        content = self.render_human_message(events=events, goals=goals)
        messages = [
            self.render_system_message(),
            HumanMessage(content=content)
        ]
        response = self.guide_llm(messages).content

        msg = ('=' * 10 + ' Baseline GPT4-Guide Agent Answer ' + '=' * 10).center(100, '=')
        print(f"\033[34m\n{msg}\n{response}\033[0m")

        return response

    def get_llama_sft_response(self, events, goals):
        input_txt = self.render_human_message(events=events, goals=goals)
        request_data = {"input_txt": input_txt, "mode": "3"}
        res = requests.post(
            f"{self.server}/minecraftapi",
            json=request_data,
            timeout=self.llama_timeout
        )
        if res.status_code != 200:
            raise RuntimeError("Failed to step AutoDL curriculum server.")
        returned_data = res.json()

        llama_response = returned_data["response_sft"]

        msg = ('=' * 10 + ' Finetune LlaMA-Guide Agent Answer ' + '=' * 10).center(100, '=')
        print(f"\033[34m\n{msg}\n{llama_response}\033[0m")

        return llama_response

    @classmethod
    def process_ai_answer(cls, response, direction_random=0.3):
        match = regex.search(r'\{(?:[^{}]|(?R))*\}', response)
        response = match.group()

        response_dict = json.loads(response)

        response_found = response_dict["Found"]
        response_not = response_dict["Not found"]

        if response_found == "None":
            flag = False

            direction = response_not

            components = direction.strip('()').split(',')
            y_direction = float(components[1])

            random_number = random.random()
            if y_direction and random_number >= direction_random:
                direction = "(1, 0, 1)" if random_number >= 0.5 else "(-1, 0, 1)"

            item_name = None
        else:
            flag = True
            direction = None
            item_name = response_found

        return flag, direction, item_name

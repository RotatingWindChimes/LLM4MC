""" task verify agent """

from __future__ import annotations

import re
import json
import regex
import inflect
import requests
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from llm4mc.prompts import load_prompt


class CriticAgent:
    def __init__(
            self,
            llama_server,
            baseline_model_name="gpt-4",
            temperature=0,
            request_timeout=120,
            request_llama_timeout=2400
    ):
        self.server = llama_server
        self.critic_llm = ChatOpenAI(
            model_name=baseline_model_name,
            temperature=temperature,
            request_timeout=request_timeout,
        )
        self.llama_timeout = request_llama_timeout

    @classmethod
    def render_system_message(cls):
        system_message = SystemMessage(content=load_prompt("verify_task"))
        assert isinstance(system_message, SystemMessage)

        return system_message

    def render_human_message(self, events, final_task):
        observation_info, inventory = self.render_inventory(events=events)

        final_task = final_task.strip(' .\n').lower()

        final_task_name = CriticAgent.norm_name(CriticAgent.singular_underscore('_'.join(final_task.split(' ')[2:])))
        new_task = "Get " + final_task.split(' ')[1] + ' ' + final_task_name + '.'

        inventory_info = observation_info["inventory"].strip()

        content = f"Final Task: {new_task}" + "\n" + inventory_info

        msg = ('=' * 10 + ' Critic Agent Message ' + '=' * 10).center(100, '=')
        print(f"\033[32m\n{msg}\n{content}\033[0m")

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
    def process_dict_info(cls, inventory):
        new_inventory = {CriticAgent.norm_name(CriticAgent.singular_underscore(k)): v for k, v in inventory.items()}

        return new_inventory

    @classmethod
    def render_inventory(cls, *, events):
        assert events[-1][0] == "observe", "Last event must be observe"

        event = events[-1][1]

        inventory = event["inventory"]
        inventory_used = event["status"]["inventoryUsed"]

        inventory = CriticAgent.process_dict_info(inventory=inventory)

        observation = {
            "inventory": f"Inventory ({inventory_used}/36): {inventory}\n"
        }

        return observation, inventory

    def get_gpt4_response(self, events, final_task):
        content = self.render_human_message(events=events, final_task=final_task)
        messages = [
            self.render_system_message(),
            HumanMessage(content=content)
        ]
        response = self.critic_llm(messages).content

        msg = ('=' * 10 + ' Baseline GPT4-Critic Agent Answer ' + '=' * 10).center(100, '=')
        print(f"\033[32m{msg}\n{response}\033[0m")

        return response

    def get_llama_sft_response(self, events, final_task):
        input_txt = self.render_human_message(events=events, final_task=final_task)
        request_data = {"input_txt": input_txt, "mode": "5"}
        res = requests.post(
            f"{self.server}/minecraftapi",
            json=request_data,
            timeout=self.llama_timeout
        )
        if res.status_code != 200:
            raise RuntimeError("Failed to step AutoDL critic server.")
        returned_data = res.json()

        llama_response = returned_data["response_sft"]

        msg = ('=' * 10 + ' Finetune LlaMA-Critic Agent Answer ' + '=' * 10).center(100, '=')
        print(f"\033[32m{msg}\n{llama_response}\033[0m")

        return llama_response

    @classmethod
    def process_ai_answer(cls, response):
        match = regex.search(r'\{(?:[^{}]|(?R))*\}', response)
        response = match.group()

        response_dict = json.loads(response)

        finished_label = True if response_dict["Finished"] == "true" else False

        return finished_label

    @classmethod
    def summarize_error(cls, events):
        craft_pattern = r"I cannot make \w+ because I need: (.*)"
        mine_pattern = r"I need at least a (.*) to mine \w+!"

        for event_type, event in events:
            if event_type == "onChat":
                error_msg = event["onChat"]

                if re.match(craft_pattern, error_msg):
                    error_info = re.match(craft_pattern, error_msg).groups()[0]

                    task_pattern = r'(\d+) more (\w+)'

                    matches = re.findall(task_pattern, error_info)

                    add_task_list = [f"Get {match[0]} {match[1]}." for match in matches]

                    msg = ('*' * 10 + ' Error Info ' + '*' * 10).center(100, '*')
                    print(f"{msg}\n{', '.join(add_task_list)}")

                    return add_task_list

                elif re.match(mine_pattern, error_msg):
                    error_info = re.match(mine_pattern, error_msg).groups()[0]
                    add_task_list = [f"Get 1 {error_info}."]

                    msg = ('*' * 10 + ' Error Info ' + '*' * 10).center(100, '*')
                    print(f"{msg}\n{add_task_list[0]}")

                    return add_task_list

        return ""

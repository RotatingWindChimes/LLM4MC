from __future__ import annotations

import json
import regex
import inflect
import requests
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from llm4mc.prompts import load_prompt


class ActorAgent:
    def __init__(
            self,
            llama_server,
            baseline_model_name="gpt-4",
            temperature=0,
            request_timeout=120,
            request_llama_timeout=2400
    ):
        self.server = llama_server
        self.actor_llm = ChatOpenAI(
            model_name=baseline_model_name,
            temperature=temperature,
            request_timeout=request_timeout,
        )
        self.llama_timeout = request_llama_timeout

    @classmethod
    def render_system_message(cls):
        system_message = SystemMessage(content=load_prompt("plan_action"))
        assert isinstance(system_message, SystemMessage)

        return system_message

    def render_human_message(self, events, final_task):
        inventory_used, inventory = self.render_inventory(events=events)

        final_info = final_task.strip(' .\n').split(' ')
        final_task_name = ActorAgent.norm_name(ActorAgent.singular_underscore('_'.join(final_info[2:])))
        final_task_nums = final_info[1]

        final_task = f"Final Task: Get {final_task_nums} {final_task_name}."

        if final_task_name in inventory:
            del inventory[final_task_name]

            inventory_used -= 1

        inventory_info = f"Inventory ({inventory_used}/36): {inventory}"
        content = final_task + "\n" + inventory_info

        msg = ('=' * 10 + ' Actor Agent Message (Additional) ' + '=' * 10).center(100, '=')
        print(f"\033[31m\n{msg}\n{content}\033[0m")

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
        new_inventory = {ActorAgent.norm_name(ActorAgent.singular_underscore(k)): v
                         for k, v in inventory.items()}

        return new_inventory

    @classmethod
    def render_inventory(cls, *, events):
        assert events[-1][0] == "observe", "Last event must be observe"

        event = events[-1][1]

        inventory = event["inventory"]
        inventory_used = event["status"]["inventoryUsed"]

        inventory = ActorAgent.process_dict_info(inventory=inventory)

        return inventory_used, inventory

    def get_gpt4_response(self, events, final_task):
        content = self.render_human_message(events=events, final_task=final_task)
        messages = [
            self.render_system_message(),
            HumanMessage(content=content)
        ]
        response = self.actor_llm(messages).content

        msg = ('=' * 10 + ' Baseline GPT4-Actor Agent Answer ' + '=' * 10).center(100, '=')
        print(f"\033[31m{msg}\n{response}\033[0m")

        return response

    def get_llama_sft_response(self, events, final_task):
        input_txt = self.render_human_message(events=events, final_task=final_task)
        request_data = {"input_txt": input_txt, "mode": "4"}
        res = requests.post(
            f"{self.server}/minecraftapi",
            json=request_data,
            timeout=self.llama_timeout
        )
        if res.status_code != 200:
            raise RuntimeError("Failed to step AutoDL actor server.")
        returned_data = res.json()

        llama_response = returned_data["response_sft"]

        msg = ('=' * 10 + ' Finetune LlaMA-Actor Agent Answer ' + '=' * 10).center(100, '=')
        print(f"\033[31m{msg}\n{llama_response}\033[0m")

        return llama_response

    @classmethod
    def process_ai_answer(cls, response):
        match = regex.search(r'\{(?:[^{}]|(?R))*\}', response)
        response = match.group()

        response_dict = json.loads(response)

        task_name = response_dict["My task"]
        task_category = response_dict["Task category"]

        if task_category == "Mining":
            mining_block = ActorAgent.norm_name(ActorAgent.singular_underscore(response_dict["Mining block"]))
            crafting_tool = "None"
            furn = "None"
        else:
            mining_block = "None"
            crafting_tool = ActorAgent.norm_name(ActorAgent.singular_underscore(response_dict["Crafting tool"]))

            furn = response_dict["Furnace info"]
            if furn != "None":
                furn["raw materials"] = ActorAgent.norm_name(ActorAgent.singular_underscore(furn["raw materials"]))
                furn["need coal"] = True if furn["need coal"] == "true" else False

        return task_name, task_category, mining_block, crafting_tool, furn

""" plan materials for final task """

from __future__ import annotations

import json
import regex
import inflect
import requests
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from .judger import JudgeAgent
from llm4mc.prompts import load_prompt


class CurriculumAgent:
    def __init__(
            self,
            llama_server,
            model_type="baseline",
            baseline_model_name="gpt-4",
            temperature=0,
            request_timeout=120,
            judge_model_name="gpt-4",
            judge_model_temperature=0,
            request_llama_timeout=2400
    ):
        self.server = llama_server
        self.baseline_model = True if model_type.lower() == "baseline" else False
        self.curriculum_llm = ChatOpenAI(
            model_name=baseline_model_name,
            temperature=temperature,
            request_timeout=request_timeout,
        )

        self.judger = JudgeAgent(
            llama_server=self.server,
            baseline_model_name=judge_model_name,
            temperature=judge_model_temperature,
            request_timeout=request_timeout
        )
        self.llama_timeout = request_llama_timeout

        self.task_history = []

    @classmethod
    def render_system_message(cls):
        system_message = SystemMessage(content=load_prompt("plan_materials"))
        assert isinstance(system_message, SystemMessage)

        return system_message

    def render_human_message(self, events, final_task):
        observation_info, inventory = self.render_inventory(events=events)

        if self.task_history:
            last_element = self.task_history[-1]

            first_key = next(iter(last_element))

            index_value = last_element["index"]

            if index_value < len(last_element[first_key]):
                new_task = last_element[first_key][index_value]

                item_name = new_task.split(' ')[2].strip(' .\n').lower()

                item_num = int(new_task.split(' ')[1]) + inventory.get(item_name, 0)
                new_task = f"Get {item_num} {item_name}."

                last_element["index"] += 1
            else:
                new_task = first_key
                self.task_history.pop()
        else:
            final_info = final_task.split(' ')
            final_task_name = CurriculumAgent.norm_name(CurriculumAgent.singular_underscore('_'.join(final_info[2:])))
            new_task = "Get " + final_task.split(' ')[1] + ' ' + final_task_name + '.'

        final_task = f"Final Task: {new_task}"
        inventory_info = observation_info["inventory"].strip()

        content = final_task + "\n" + inventory_info

        msg = ('=' * 10 + ' Curriculum Agent Message ' + '=' * 10).center(100, '=')
        print(f"\033[33m\n{msg}\n{content}\033[0m")

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
        new_inventory = {CurriculumAgent.norm_name(CurriculumAgent.singular_underscore(k)): v
                         for k, v in inventory.items() if v}

        return new_inventory

    @classmethod
    def render_inventory(cls, *, events):
        assert events[-1][0] == "observe", "Last event must be observe"

        event = events[-1][1]

        inventory = event["inventory"]
        inventory_used = event["status"]["inventoryUsed"]

        inventory = CurriculumAgent.process_dict_info(inventory=inventory)

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
        response = self.curriculum_llm(messages).content

        msg = ('=' * 10 + ' Baseline GPT4-Curriculum Agent Answer ' + '=' * 10).center(100, '=')
        print(f"\033[33m{msg}\n{response}\033[0m")

        return response

    def get_llama_sft_response(self, events, final_task):
        input_txt = self.render_human_message(events=events, final_task=final_task)
        request_data = {"input_txt": input_txt, "mode": "1"}
        res = requests.post(
            f"{self.server}/minecraftapi",
            json=request_data,
            timeout=self.llama_timeout
        )
        if res.status_code != 200:
            raise RuntimeError("Failed to step AutoDL curriculum server.")
        returned_data = res.json()

        llama_response = returned_data["response_sft"]

        msg = ('=' * 10 + ' Finetune LlaMA-Curriculum Agent Answer ' + '=' * 10).center(100, '=')
        print(f"\033[33m{msg}\n{llama_response}\033[0m")

        return llama_response

    def process_ai_answer(self, response):
        match = regex.search(r'\{(?:[^{}]|(?R))*\}', response)
        response = match.group()

        response_dict = json.loads(response)

        final_task_name, final_task_nums = list(response_dict["Original final task"].items())[0]
        final_task_name = CurriculumAgent.norm_name(CurriculumAgent.singular_underscore(final_task_name))
        final_task = f"Get {final_task_nums} {final_task_name}."

        updated_task = response_dict["Updated final task"]

        if updated_task:
            updated_task_name, updated_task_nums = list(updated_task.items())[0]
            updated_task_name = CurriculumAgent.norm_name(CurriculumAgent.singular_underscore(updated_task_name))

            updated_task = f"Get {updated_task_nums} {updated_task_name}." if updated_task_nums else ""
        else:
            updated_task = ""

        needed_dict = self.process_dict_info(response_dict["Items Needed"])

        missing_dict = self.process_dict_info(response_dict["Items Missing"])

        if missing_dict:
            if self.baseline_model:
                judge_response = self.judger.get_gpt4_response(missing_list=list(missing_dict.keys()))
            else:
                judge_response = self.judger.get_llama_sft_response(missing_list=list(missing_dict.keys()))

            task_label = self.judger.process_ai_answer(judge_response)
        else:
            task_label = True

        having_dict = {k: needed_dict[k] - missing_dict[k] for k in missing_dict}

        require_list = [f"Get {v} {k}." for k, v in missing_dict.items()]

        if not task_label:
            prerequisite_task = {
                final_task: require_list,
                "index": 0
            }
            self.task_history.append(prerequisite_task)

        return final_task, updated_task, task_label, missing_dict, having_dict

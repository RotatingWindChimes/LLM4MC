""" Judge mission start agent """

from __future__ import annotations

import json
import regex
import inflect
import requests
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from llm4mc.prompts import load_prompt


class JudgeAgent:
    def __init__(
            self,
            llama_server,
            baseline_model_name="gpt-4",
            temperature=0,
            request_timeout=120,
            request_llama_timeout=2400
    ):
        self.server = llama_server
        self.judge_llm = ChatOpenAI(
            model_name=baseline_model_name,
            temperature=temperature,
            request_timeout=request_timeout,
        )
        self.llama_timeout = request_llama_timeout

    @classmethod
    def render_system_message(cls):
        system_message = SystemMessage(content=load_prompt("judge_start"))
        assert isinstance(system_message, SystemMessage)

        return system_message

    @classmethod
    def render_human_message(cls, missing_list):
        missing_list = [
            JudgeAgent.norm_name(JudgeAgent.singular_underscore(missing_item)) for missing_item in missing_list
        ]

        content = f"Item List: {missing_list}"

        msg = ('=' * 10 + ' Judge Agent Message ' + '=' * 10).center(100, '=')
        print(f"\033[36m\n{msg}\n{content}\033[0m")

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

    def get_gpt4_response(self, missing_list):
        content = self.render_human_message(missing_list=missing_list)
        messages = [
            self.render_system_message(),
            HumanMessage(content=content)
        ]
        response = self.judge_llm(messages).content

        msg = ('=' * 10 + ' Baseline GPT4-Judge Agent Answer ' + '=' * 10).center(100, '=')
        print(f"\033[36m\n{msg}\n{response}\033[0m")

        return response

    def get_llama_sft_response(self, missing_list):
        input_txt = self.render_human_message(missing_list=missing_list)
        request_data = {"input_txt": input_txt, "mode": "2"}
        res = requests.post(
            f"{self.server}/minecraftapi",
            json=request_data,
            timeout=self.llama_timeout
        )
        if res.status_code != 200:
            raise RuntimeError("Failed to step AutoDL curriculum server.")
        returned_data = res.json()

        llama_response = returned_data["response_sft"]

        msg = ('=' * 10 + ' Finetune LlaMA-Judge Agent Answer ' + '=' * 10).center(100, '=')
        print(f"\033[36m\n{msg}\n{llama_response}\033[0m")

        return llama_response

    @classmethod
    def process_ai_answer(cls, response):
        match = regex.search(r'\{(?:[^{}]|(?R))*\}', response)
        response = match.group()

        response_dict = json.loads(response)
        flag = True

        for item_name, item_category in response_dict.items():
            if item_category == "synthetic items":
                flag = False
                break

        return flag

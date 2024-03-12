# TODO 如果无法摆放工作台或者熔炉怎么移动
import os
import time
import random

from env import LLM4MCEnv
from basic_skills import load_basic_skills
from agents import ActorAgent, GuideAgent, CriticAgent, CurriculumAgent


class AgentMC:
    def __init__(
            self,
            mc_port,
            api_key,
            api_base,
            llama_server,
            max_attempts=3,
            server_port=3000,
            env_wait_ticks=20,
            env_request_timeout=600,
            judge_model_name="gpt-4",             # judge agent
            judge_model_temperature=0,
            judge_model_type="baseline",
            actor_agent_name="gpt-4",             # actor agent
            actor_agent_temperature=0.2,
            actor_model_type="baseline",
            guide_agent_name="gpt-4",             # guide agent
            guide_agent_temperature=0.3,
            guide_model_type="baseline",
            critic_agent_name="gpt-4",            # critic agent
            critic_agent_temperature=0,
            critic_model_type="baseline",
            curriculum_agent_name="gpt-4",        # curriculum agent
            curriculum_agent_temperature=0.3,
            curriculum_model_type="baseline",
            openai_api_request_timeout=240
    ):
        self.env = LLM4MCEnv(
            mc_port=mc_port,
            server_port=server_port,
            request_timeout=env_request_timeout
        )

        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["OPENAI_API_BASE"] = api_base

        self.server = llama_server

        self.curriculum_agent = CurriculumAgent(
            llama_server=llama_server,
            model_type=judge_model_type,
            baseline_model_name=curriculum_agent_name,
            temperature=curriculum_agent_temperature,
            request_timeout=openai_api_request_timeout,
            judge_model_name=judge_model_name,
            judge_model_temperature=judge_model_temperature
        )

        self.actor_agent = ActorAgent(
            llama_server=llama_server,
            baseline_model_name=actor_agent_name,
            temperature=actor_agent_temperature,
            request_timeout=openai_api_request_timeout
        )

        self.guide_agent = GuideAgent(
            llama_server=llama_server,
            baseline_model_name=guide_agent_name,
            temperature=guide_agent_temperature,
            request_timeout=openai_api_request_timeout
        )

        self.critic_agent = CriticAgent(
            llama_server=llama_server,
            baseline_model_name=critic_agent_name,
            temperature=critic_agent_temperature,
            request_timeout=openai_api_request_timeout
        )

        self.env_wait_ticks = env_wait_ticks
        self.max_attempts = max_attempts
        self.basic_skills = load_basic_skills()

        self.curriculum_baseline = True if curriculum_model_type.lower() == "baseline" else False
        self.actor_baseline = True if actor_model_type.lower() == "baseline" else False
        self.critic_baseline = True if critic_model_type.lower() == "baseline" else False
        self.guide_baseline = True if guide_model_type.lower() == "baseline" else False

    def reset(self, options, reset_env=True):
        if reset_env:
            self.env.reset(options=options)

        self.env.step(
            "bot.chat(`/time set ${getNextTime()}`);\n bot.chat('/difficulty peaceful');"
        )

    def mine_block(self, task_name, block_name, add, total):
        final_task = f"Get {total} {task_name}."
        add_task = ""
        events = self.env.step("")

        if self.guide_baseline:
            guide_response = self.guide_agent.get_gpt4_response(events=events, goals=block_name)
        else:
            guide_response = self.guide_agent.get_llama_sft_response(events=events, goals=block_name)

        flag, direction, name = self.guide_agent.process_ai_answer(guide_response)
        guides = 0

        while guides < 10:  # 挖矿探索次数为10

            # 方块存在, 可以找到
            if flag:
                # 挖掘代码
                mine_code = f"await mineBlock(bot, '{name}', {add})"
                code = self.basic_skills + '\n' + mine_code

                new_events = self.env.step(code=code)
                time.sleep(1)

                if self.critic_baseline:
                    critic_response = self.critic_agent.get_gpt4_response(events=new_events, final_task=final_task)
                else:
                    critic_response = self.critic_agent.get_llama_sft_response(events=new_events, final_task=final_task)

                add_task = self.critic_agent.summarize_error(events=new_events)

                finished = self.critic_agent.process_ai_answer(critic_response)

                if finished or add_task:
                    break

            # 探索代码
            explore_code = f"await exploreUntil(bot, new Vec3{direction}, 5)"
            code = self.basic_skills + '\n' + explore_code

            events = self.env.step(code=code)

            if self.guide_baseline:
                guide_response = self.guide_agent.get_gpt4_response(events=events, goals=block_name)
            else:
                guide_response = self.guide_agent.get_llama_sft_response(events=events, goals=block_name)

            flag, direction, name = self.guide_agent.process_ai_answer(guide_response)

            guides += 1

        return add_task

    def craft_without_table(self, task_name, add, total):
        final_task = f"Get {total} {task_name}."

        craft_code = f"await craftItem(bot, '{task_name}', {add})"

        code = self.basic_skills + '\n' + craft_code

        new_events = self.env.step(code=code)
        time.sleep(1)

        if self.critic_baseline:
            _ = self.critic_agent.get_gpt4_response(events=new_events, final_task=final_task)
        else:
            _ = self.critic_agent.get_llama_sft_response(events=new_events, final_task=final_task)

        add_task = self.critic_agent.summarize_error(events=new_events)

        return add_task

    def craft_with_table(self, task_name, add, total):
        final_task = f"Get {total} {task_name}."
        place_attempts = 0
        add_task = ""

        while place_attempts < 5:

            place_code = "await placeItem(bot, 'crafting_table', bot.entity.position.offset(0, 0, 1))"
            craft_code = f"await craftItem(bot, '{task_name}', {add})"
            code = self.basic_skills + '\n' + place_code + '\n' + craft_code

            new_events = self.env.step(code=code)
            time.sleep(1)

            if self.critic_baseline:
                critic_response = self.critic_agent.get_gpt4_response(events=new_events, final_task=final_task)
            else:
                critic_response = self.critic_agent.get_llama_sft_response(events=new_events, final_task=final_task)

            add_task = self.critic_agent.summarize_error(events=new_events)

            finished = self.critic_agent.process_ai_answer(critic_response)

            if finished or add_task:
                break

            place_attempts += 1

            direction = AgentMC.random_direction()
            move_code = f"await exploreUntil(bot, new Vec3{direction}, 10)"
            code = self.basic_skills + '\n' + move_code

            self.env.step(code=code)

        return add_task

    def smelt_with_furnace(self, task_name, furn_info, add, total):
        final_task = f"Get {total} {task_name}."
        place_attempts = 0
        add_task = ""

        raw_materials = furn_info["raw materials"]
        need_coal = furn_info["need coal"]

        if need_coal:   # 需要燃料, 挖四个煤炭
            self.mine_block(task_name="coal", block_name="coal_ore", add=4, total=4)

        fuels = "coal"

        while place_attempts < 10:
            place_code = "await placeItem(bot, 'furnace', bot.entity.position.offset(0, 0, 1))"
            smelt_code = f"await smeltItem(bot, '{raw_materials}', '{fuels}', {add})"
            code = self.basic_skills + '\n' + place_code + '\n' + smelt_code

            new_events = self.env.step(code=code)
            time.sleep(1)

            if self.critic_baseline:
                critic_response = self.critic_agent.get_gpt4_response(events=new_events, final_task=final_task)
            else:
                critic_response = self.critic_agent.get_llama_sft_response(events=new_events, final_task=final_task)
            add_task = self.critic_agent.summarize_error(events=new_events)

            finished = self.critic_agent.process_ai_answer(critic_response)

            if finished:
                break

            place_attempts += 1

            direction = AgentMC.random_direction()
            execute_code = f"await exploreUntil(bot, new Vec3{direction}, 10)"
            code = self.basic_skills + '\n' + execute_code

            self.env.step(code=code)

        return add_task

    def collect_action(self, requirements, materials):
        add_task = ""

        for item_name, item_nums in requirements.items():
            num_in_inventory = materials[item_name]

            temp_task = f"Get {item_nums + num_in_inventory} {item_name}."
            add_task = ""

            events = self.env.step("")

            if self.guide_baseline:
                guide_response = self.guide_agent.get_gpt4_response(events=events, goals=item_name)
            else:
                guide_response = self.guide_agent.get_llama_sft_response(events=events, goals=item_name)

            flag, direction, name = self.guide_agent.process_ai_answer(guide_response)
            guides = 0

            # 定位、探索
            while guides < 5:
                if flag:
                    mine_code = f"await mineBlock(bot, '{name}', {item_nums})"
                    code = self.basic_skills + '\n' + mine_code

                    new_events = self.env.step(code=code)
                    time.sleep(1)

                    if self.critic_baseline:
                        critic_response = self.critic_agent.get_gpt4_response(events=new_events, final_task=temp_task)
                    else:
                        critic_response = self.critic_agent.get_llama_sft_response(events=new_events,
                                                                                   final_task=temp_task)
                    add_task = self.critic_agent.summarize_error(events=new_events)

                    finished = self.critic_agent.process_ai_answer(critic_response)

                    if finished or add_task:
                        break

                guide_code = f"await exploreUntil(bot, new Vec3{direction}, 10)"

                code = self.basic_skills + '\n' + guide_code

                events = self.env.step(code=code)   # 执行

                if self.guide_baseline:
                    guide_response = self.guide_agent.get_gpt4_response(events=events, goals=item_name)    # 获得响应用于检查
                else:
                    guide_response = self.guide_agent.get_llama_sft_response(events=events, goals=item_name)

                flag, direction, name = self.guide_agent.process_ai_answer(guide_response)

                guides += 1

            if add_task:
                break

        return add_task

    def inference(self, task=None, reset_mode="soft"):
        if not task:
            raise ValueError("In inference step, a final task is essential.")

        task_info = task.strip(' .\n').lower().split(' ')

        final_name = self.curriculum_agent.norm_name(self.curriculum_agent.singular_underscore('_'.join(task_info[2:])))
        final_nums = task_info[1]

        new_task = f"Get {final_nums} {final_name}."
        new_task_attempts = 0

        options = {
            "mode": reset_mode,
            "wait_ticks": self.env_wait_ticks,
        }
        self.reset(options=options, reset_env=True)

        while True:
            events = self.env.step("")

            if self.curriculum_baseline:
                response = self.curriculum_agent.get_gpt4_response(events=events, final_task=new_task)
            else:
                response = self.curriculum_agent.get_llama_sft_response(events=events, final_task=new_task)

            (final_task,
             updated_task,
             task_label,
             missing_dict,
             having_dict) = self.curriculum_agent.process_ai_answer(response)

            if task_label and updated_task:

                total_name, total_nums = AgentMC.split_task(final_task)
                add_name, add_nums = AgentMC.split_task(updated_task)

                if not missing_dict:
                    if self.actor_baseline:
                        response = self.actor_agent.get_gpt4_response(events=events, final_task=updated_task)
                    else:
                        response = self.actor_agent.get_llama_sft_response(events=events, final_task=updated_task)

                    (task_name,
                     task_category,
                     mining_block,
                     crafting_tool,
                     furn) = self.actor_agent.process_ai_answer(response)

                    if task_category == "Mining":
                        add_task = self.mine_block(task_name=task_name, block_name=mining_block, add=add_nums,
                                                   total=total_nums)
                    elif crafting_tool == "no_tool":
                        add_task = self.craft_without_table(task_name=task_name, add=add_nums, total=total_nums)
                    elif crafting_tool == "crafting_table":
                        add_task = self.craft_with_table(task_name=task_name, add=add_nums, total=total_nums)
                    else:
                        add_task = self.smelt_with_furnace(task_name=task_name, furn_info=furn, add=add_nums,
                                                           total=total_nums)
                else:
                    add_task = self.collect_action(requirements=missing_dict, materials=having_dict)

                if add_task:
                    add_task_dict = {final_task: add_task, "index": 0}

                    self.curriculum_agent.task_history.append(add_task_dict)

            if not self.curriculum_agent.task_history and new_task_attempts < self.max_attempts:
                current_event = self.env.step("")

                if self.critic_baseline:
                    response = self.critic_agent.get_gpt4_response(events=current_event, final_task=new_task)
                else:
                    response = self.critic_agent.get_llama_sft_response(events=current_event, final_task=new_task)

                finished = self.critic_agent.process_ai_answer(response)

                if finished:
                    break

                new_task_attempts += 1

        self.close()

    @classmethod
    def split_task(cls, task):
        info_list = task.strip(' .\n').split(' ')

        name = info_list[2]
        nums = int(info_list[1])

        return name, nums

    @classmethod
    def random_direction(cls):
        triplet = (1, 0, 0)

        return triplet

    def close(self):
        self.env.close()

    @classmethod
    def render_task(cls):
        item_list = [
            'crafting_table', 'stick', 'torch', 'furnace', 'chest', 'bed', 'ladder', 'boat', 'wooden_pickaxe',
            'wooden_axe', 'wooden_shovel', 'wooden_sword', 'wooden_hoe', 'stone_pickaxe', 'stone_axe', 'stone_shovel',
            'stone_sword', 'stone_hoe', 'iron_pickaxe', 'iron_axe', 'iron_shovel', 'iron_sword', 'iron_hoe',
            'diamond_pickaxe', 'diamond_axe', 'diamond_shovel', 'diamond_sword', 'diamond_hoe', 'gold_pickaxe',
            'gold_axe', 'gold_shovel', 'gold_sword', 'gold_hoe', 'bow', 'arrow', 'bucket', 'shears', 'book',
            'item_frame', 'golden_sword', 'golden_axe', 'crossbow', "coal", "cobblestone", "raw_iron", "raw_gold",
            "raw_copper", "diamond", "iron_ingot", "gold_ingot", "copper_ingot", "iron_helmet", "diamond_helmet",
            "golden_helmet", "leather_chestplate", "chainmail_chestplate", "iron_chestplate", "diamond_chestplate",
            "golden_chestplate", "chainmail_leggings", "iron_leggings", "diamond_leggings", "golden_leggings",
            "iron_boots", "diamond_boots", "golden_boots", "oak_planks", "spruce_planks", "birch_planks",
            "jungle_planks", "acacia_planks", "cherry_planks", "bookshelf", "iron_door",  "jukebox", "oak_door",
            "spruce_door", "birch_door", "jungle_door", "acacia_door", "cherry_door", "copper_door",
            "spruce_fence_gate", "birch_fence_gate", "jungle_fence_gate", "dark_oak_fence_gate", "acacia_fence_gate",
            "oak_fence_gate", "spruce_fence", "birch_fence", "jungle_fence", "acacia_fence", "oak_fence"
        ]

        item_num = random.randint(0, 10)
        item_name = item_list[random.randint(0, len(item_list))]

        final_task = f"Get {item_num} {item_name}."

        return final_task


if __name__ == "__main__":
    key = r"your key"     # 我使用的是closeai，换成自己的GPT4-api
    base = r"your base"
    server = r"https://u284241-a083-3edacbc8.westc.gpuhub.com:8443/"

    mc_player = AgentMC(
        llama_server=server,
        mc_port=50838,
        api_key=key,
        api_base=base,
        max_attempts=3,
        server_port=3000,
        env_wait_ticks=40,
        env_request_timeout=1000,
        judge_model_name="gpt-4",
        judge_model_temperature=0,
        actor_agent_name="gpt-4",
        actor_agent_temperature=0.2,
        guide_agent_name="gpt-4",
        guide_agent_temperature=0.1,
        critic_agent_name="gpt-4",
        critic_agent_temperature=0,
        curriculum_agent_name="gpt-4",
        curriculum_agent_temperature=0.2,
        openai_api_request_timeout=240,
        curriculum_model_type="baseline",
        judge_model_type="baseline",
        actor_model_type="baseline",
        guide_model_type="baseline",
        critic_model_type="baseline"
    )

    # 预热任务
    mc_player.inference("Get 1 crafting table.")
    mc_player.inference("Get 1 furnace.")

    # 随机 3 个任务
    for i in range(3):
        task_i = AgentMC.render_task()

        msg = ('*' * 10 + task_i + '*' * 10).center(100, '*')
        print(msg)

        mc_player.inference(task_i)

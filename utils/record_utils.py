import re
import time

from .file_utils import f_mkdir, f_listdir, f_join
from .json_utils import json_dump, json_load


class EventRecorder:
    def __init__(self, ckpt_dir="checkpoint", resume=False, init_position=None):
        """ 情景记录类

        :param ckpt_dir: 保存路径
        :param resume: 是否加载已经保存的场景 (是否从之前的保存点恢复)
        :param init_position: 初始位置
        """
        self.ckpt_dir = ckpt_dir
        self.init_position = init_position

        self.item_vs_time = {}      # 两个用于记录事件的字典。
        self.item_vs_iter = {}
        self.item_history = set()   # 跟踪物品和生物群落的历史
        self.biome_history = set()

        self.iteration = 0          # 当前的事件或循环的迭代次数
        self.elapsed_time = 0       # 已经过去的时间
        self.position_history = [[0, 0]]   # 相对位置历史

        _ = f_mkdir(self.ckpt_dir, "events")   # 创建路径

        if resume:
            self.resume()   # 加载已经保存的场景

    def update_elapsed_time(self, event):   # 更新已经过去的时间
        self.elapsed_time += event["status"]["elapsedTime"]

    def record(self, events, task):
        # 正则替换, 替换字符串 task 中的 \/:"*?<>| ] 为 _, 同时加上时间戳, task 后缀变成 _20230705_140705
        task = re.sub(r'[\\/:"*?<>| ]', "_", task)
        task = task.replace(" ", "_") + time.strftime("_%Y%m%d_%H%M%S", time.localtime())

        self.iteration += 1   # 次数加一

        if not self.init_position:   # 如果位置没有初始化, 利用 events 中第一个事件初始化
            self.init_position = [events[0][1]["status"]["position"]["x"], events[0][1]["status"]["position"]["z"]]

        for event_type, event in events:   # 遍历 events 中每个事件, 更新
            self.update_items(event)
            if event_type == "observe":    # 事件类型为 observe, 更新已经过去的时间
                self.update_elapsed_time(event)
        print(
            f"\033[96m****Recorder message: {self.elapsed_time} ticks have elapsed****\033[0m\n"  # 设置为青色、还原为默认色
            f"\033[96m****Recorder message: {self.iteration} iteration passed****\033[0m"
        )
        json_dump(events, f_join(self.ckpt_dir, "events", task))

    def resume(self, cutoff=None):
        self.item_vs_time = {}       # 物品随时间、游戏次数的变化
        self.item_vs_iter = {}
        self.elapsed_time = 0
        self.item_history = set()    # 物品历史
        self.position_history = [[0, 0]]

        def get_timestamp(string):
            timestamp = "_".join(string.split("_")[-2:])   # 提取时间,  events 文件下的是 record 中的 task_20230705_140705

            # timestamp 是字符串形式的时间 "20230705_140705", strptime 变成 struct_time 对象, 2023年7月5日14点7分5秒
            # mktime 获得 Epoch 秒数
            return time.mktime(time.strptime(timestamp, "%Y%m%d_%H%M%S"))

        # 在self.ckpt_dir 路径下名为 "events"的目录, 列出该目录下的所有文件和子目录
        # 对这些文件和子目录进行排序, 返回这些文件和子目录的名字 (而不是完整路径)
        records = f_listdir(self.ckpt_dir, "events")
        sorted_records = sorted(records, key=get_timestamp)   # 按转换后的时间排序

        for record in sorted_records:
            self.iteration += 1
            if cutoff and self.iteration > cutoff:
                break

            # 加载事件
            events = json_load(f_join(self.ckpt_dir, "events", record))
            if not self.init_position:   # 按最老的事件初始化位置
                self.init_position = (
                    events[0][1]["status"]["position"]["x"],
                    events[0][1]["status"]["position"]["z"],
                )
            for event_type, event in events:
                self.update_items(event)      # 恢复事件, 更新背包和相对位置
                self.update_position(event)
                if event_type == "observe":
                    self.update_elapsed_time(event)

    def update_items(self, event):
        # 背包、背包中物品
        inventory = event["inventory"]
        items = set(inventory.keys())

        # 状态 {群落: , 时间: }
        biome = event["status"]["biome"]
        elapsed_time = event["status"]["elapsedTime"]

        new_items = items - self.item_history   # 新增加的物品
        self.item_history.update(items)         # 更新物品, 添加多个元素
        self.biome_history.add(biome)           # 更新群落, 添加单个元素
        if new_items:                           # 添加新物品
            if self.elapsed_time + elapsed_time not in self.item_vs_time:
                self.item_vs_time[self.elapsed_time + elapsed_time] = []
            self.item_vs_time[self.elapsed_time + elapsed_time].extend(new_items)

            if self.iteration not in self.item_vs_iter:
                self.item_vs_iter[self.iteration] = []
            self.item_vs_iter[self.iteration].extend(new_items)

    def update_position(self, event):           # 更新位置, 计算相对位置
        # position 表示当前位置与初始时刻位置的差异, 得到相对位置
        position = [
            event["status"]["position"]["x"] - self.init_position[0],
            event["status"]["position"]["z"] - self.init_position[1]
        ]

        # 相对位置和上一个时刻相对位置不同, 存入位置历史
        if self.position_history[-1] != position:
            self.position_history.append(position)

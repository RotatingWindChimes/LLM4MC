# TODO 修改命名法

import re
import json
from .file_utils import f_join


def json_load(*filepaths, **kwargs):
    """ 加载 json 文件, load from file

    :param filepaths: 多个参数
    :param kwargs: other
    :return: 加载后的 json 文件
    """
    fpath = f_join(filepaths)
    with open(fpath, "r") as fp:
        return json.load(fp, **kwargs)


def json_loads(string, **kwargs):
    """ 加载 json 字符串, load from string

    :param string: json 字符串
    :param kwargs: other
    :return: 加载后的 json 字符串
    """
    return json.loads(string, **kwargs)


def json_dump(data, *filepaths, **kwargs):
    """ 保存为 json 文件

    :param data: 要保存的数据
    :param filepaths: 保存的路径
    :param kwargs: other
    :return: None
    """
    fpath = f_join(filepaths)
    with open(fpath, "w") as fp:
        json.dump(data, fp, **kwargs)


def json_dumps(data, **kwargs):
    """ 保存为 json 字符串

    :param data: 要保存的数据
    :param kwargs: other
    :return: json格式字符串
    """
    return json.dumps(data, **kwargs)


load_json = json_load
loads_json = json_loads
dump_json = json_dump
dumps_json = json_dumps


def extract_char_position(errmsg):
    """ 从给定的错误消息中提取和返回报错的位置

    :param errmsg: 错误信息
    :return: 字符位置
    """
    pattern = re.compile(r"\(char (\d+)\)")   # 正则表达式匹配类似于 (char 123) 的字符串, '123' 将作为子数组提取 (两端有括号)

    '''
    match = pattern.search(error_message)
    if match:
        ...
    '''
    if match := pattern.search(errmsg):   # 海象操作符, 可以在一行中同时进行赋值和值检测, 如果有, match 是匹配对象
        return int(match[1])   # 返回匹配对象的第一个捕获组的内容, 这里 match.group(1) 相当于抓第一个子数组
    else:
        raise ValueError("Character position not found in the error message.")


def add_quotes_to_property_names(json_string):
    """ 处理 JSON 格式错误, json 中所有的属性名称 (键) 都必须由双引号包围, 函数自动为这些不符合 JSON 规范的属性名称添加双引号

    :param json_string: json 字符串
    :return: 处理后的 json 字符串
    """
    def replace_func(match):
        """ 内部回调函数

        :param match: 匹配对象
        :return: 格式化的字符串, 属性名称被添加了双引号
        """
        return f'"{match.group(1)}":'

    property_name_pattern = re.compile(r"(\w+):")   # 匹配一个或多个单词字符, 后接冒号; 捕获组匹配属性名称
    corrected_json_string = property_name_pattern.sub(replace_func, json_string)   # 替换操作, sub 形参为替换函数和原始字符串

    try:   # 解析修正后的 json string
        json.loads(corrected_json_string)
        return corrected_json_string
    except json.JSONDecodeError as e:
        raise e


def balance_braces(json_string):
    """ 处理一些由于大括号不匹配而不能正确解析的 JSON 字符串

    :param json_string: json 字符串
    :return: 平衡后的 json 字符串
    """
    open_braces_count = json_string.count("{")
    close_braces_count = json_string.count("}")

    while open_braces_count > close_braces_count:
        json_string += "}"
        close_braces_count += 1

    while close_braces_count > open_braces_count:
        json_string = json_string.rstrip("}")
        close_braces_count -= 1

    try:   # 解析修正后的 json string
        json.loads(json_string)
        return json_string
    except json.JSONDecodeError as e:
        raise e


def fix_invalid_escape(json_string, error_message):
    """ 修复 JSON 字符串中的无效转义字符

    :param json_string: json 字符串
    :param error_message: 报错信息
    :return: 修复后的 json 字符串
    """
    while error_message.startswith("Invalid \\escape"):
        bad_escape_location = extract_char_position(error_message)
        json_string = json_string[:bad_escape_location] + json_string[bad_escape_location + 1:]   # 假设那个位置处的字符是 \

        try:   # 解析修正后的 json string
            json.loads(json_string)
            return json_string
        except json.JSONDecodeError as e:
            error_message = str(e)

    return json_string


def correct_json(json_string):
    """ 修复一些常见的 JSON 格式错误, 通过各种策略和子函数来处理和修复这些错误

    :param json_string: json 字符串
    :return: 修复后的字符串
    """
    try:
        json.loads(json_string)   # 解析 json string
        return json_string
    except json.JSONDecodeError as e:
        error_message = str(e)

        if error_message.startswith("Invalid \\escape"):   # 处理转义字符错误
            json_string = fix_invalid_escape(json_string, error_message)

        if error_message.startswith("Expecting property name enclosed in double quotes"):   # 处理属性名称双引号错误
            json_string = add_quotes_to_property_names(json_string)
            try:
                json.loads(json_string)   # 可以解析, 直接返回
                return json_string
            except json.JSONDecodeError:
                pass

        if balanced_str := balance_braces(json_string):   # 进一步确保大括号平衡
            return balanced_str

    return json_string


def fix_and_parse_json(json_string):
    """ 处理和修复 JSON 字符串和文件的常见错误

    :param json_string: json 字符串
    :return: 修复后的 json 字符串
    """
    try:
        json_string = json_string.replace("\t", "")
        return json.loads(json_string)
    except json.JSONDecodeError:
        json_string = correct_json(json_string)
        try:
            return json.loads(json_string)
        except json.JSONDecodeError:
            pass
    try:
        # 找到 json 字符串中第一个 { 和 最后一个 } 位置
        brace_index = json_string.index("{")
        json_string = json_string[brace_index:]

        last_brace_index = json_string.rindex("}")
        json_string = json_string[: last_brace_index + 1]

        return json.loads(json_string)
    except json.JSONDecodeError as e:
        raise e

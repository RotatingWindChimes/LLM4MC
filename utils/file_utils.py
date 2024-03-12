# TODO 修改命名法
# TODO 可变数量参数函数不规范

import os
import sys
import glob
import errno
import shutil
import pickle
import codecs
import hashlib
import tarfile
import fnmatch
import tempfile
from collections import abc
from datetime import datetime
from socket import gethostname
# import pwd
# import logging
# import collections

f_ext = os.path.splitext   # 将文件路径分割为 "根部分" 和 "扩展名" 两个部分, 并返回一个包含两者的元组
f_size = os.path.getsize   # 返回给定路径的文件的大小, 单位是字节
is_file = os.path.isfile   # 检查给定路径是否指向一个存在的文件
is_dir = os.path.isdir     # 检查给定路径是否指向一个存在的目录
get_dir = os.path.dirname  # 返回给定文件或目录路径的目录部分 (返回父目录)


def host_name():   # 运行 Python 脚本的机器的主机名
    return gethostname()


def host_id():   # 保留 "根部分"
    return host_name().split(".")[0]


def utf_open(filename, mode):   # 打开文件并返回一个文件对象, 同时提供了指定的文本编码和解码功能。
    return codecs.open(filename, mode=mode, encoding="utf-8")


def is_sequence(obj):   # 检查对象是否为序列 (列表、元组), 但不是字符串
    return isinstance(obj, abc.Sequence) and not isinstance(obj, str)


def pack_varargs(args):
    """ 适用于那些既可以接受多个参数, 也可以接受一个列表或元组作为参数的函数 f, 此时函数形参为 *arg
    def f(*args):
        arg_list = pack_varargs(args)
        print(arg_list)
    f(1, 2, 3)
    f((1, 2, 3))
    f([1, 2, 3])

    :param args: 函数参数
    :return: 转换后的序列
    """

    assert isinstance(args, tuple), "please input the tuple `args` as in *args"
    if len(args) == 1 and is_sequence(args[0]):   # 直接传递一个列表或元组给 f
        return args[0]
    else:
        return args   # 传递多个参数给 f


# TODO f_join()函数拼接多个路径, 但要求输入不能有嵌套列表
def f_join(*filepaths):
    """ 连接多个文件路径, 扩展其中的特殊符号

    :param filepaths: 不定数量的参数
    :return: 处理后的文件路径
    """
    filepaths = pack_varargs(filepaths)   # 处理输入的文件路径, 确保它们被收集为一个序列
    fpath = f_expand(os.path.join(*filepaths))  # 连接所有的文件路径
    if isinstance(fpath, str):
        fpath = fpath.strip()             # 去掉路径字符串的前导和尾随空格
    return fpath


def f_expand(fpath):
    """ 扩展文件路径中的特殊符号

    :param fpath: 文件路径
    :return: 处理后的文件路径
    """
    return os.path.expandvars(os.path.expanduser(fpath))   # 依次处理环境变量和'~'


def f_exists(*filepaths):
    """ 连接多个文件路径, 判断路径是否存在

    :param filepaths: 不定数量的参数
    :return: True or False
    """
    return os.path.exists(f_join(*filepaths))


def f_not_empty(*filepaths):
    """ 判断文件路径是否对应于一个存在的且不为空的文件或目录

    :param filepaths: 不定数量的参数
    :return: True or False
    """
    fpath = f_join(*filepaths)      # 拼路径
    if not os.path.exists(fpath):   # 路径不存在
        return False

    if is_dir(fpath):               # 路径是目录
        return len(os.listdir(fpath)) > 0
    else:                           # 路径是文件
        return f_size(fpath) > 0


def f_listdir(
        *filepaths,
        filter_ext=None,
        mask=None,
        sort=True,
        full_path=False,
        non_exist_ok=True,
        recursive=False,
):
    """ 一个功能增强的目录列表函数, 为用户提供多种选项来列出目录中的文件

    :param filepaths: 不定数量的文件路径部分, 将被连接成完整的目录路径
    :param filter_ext: 可选参数, 用于只列出具有特定扩展名的文件
    :param mask: 可选函数, 用于过滤文件列表
    :param sort: 是否对结果文件列表进行排序
    :param full_path: 是否返回每个文件的完整路径
    :param non_exist_ok: 目录不存在时, 报错还是返回空列表
    :param recursive: 是否递归地列出子目录中的文件
    :return:
    """
    assert not (filter_ext and mask), "filter_ext and filter are mutually exclusive"  # 两个参数互斥

    dir_path = f_join(*filepaths)
    if not os.path.exists(dir_path) and non_exist_ok:  # 路径不存在, 进行异常处理
        return []

    if recursive:  # 深入到最终的文件
        files = [
            os.path.join(os.path.relpath(root, dir_path), file)  # 连接相对路径和 file
            for root, _, files in os.walk(dir_path)   # 递归地遍历 dir_path 目录, 返回三元组 (当前目录路径, 子目录列表, 文件列表)
            for file in files
        ]
    else:  # 只会列出当前目录下的内容, 可能仅停留在文件夹
        files = os.listdir(dir_path)

    if mask is not None:  # 函数过滤
        files = [f for f in files if mask(f)]
    elif filter_ext is not None:  # 扩展名过滤
        files = [f for f in files if f.endswith(filter_ext)]

    if sort:  # 列表排序, 就地
        files.sort()

    if full_path:  # files 内只是相对路径, 拼接成完整路径
        return [os.path.join(dir_path, f) for f in files]
    else:
        return files


def f_mkdir(*filepaths):
    """ 创建路径

    :param filepaths: 多个参数
    :return: 创建好的路径
    """
    fpath = f_join(*filepaths)
    os.makedirs(fpath, exist_ok=True)

    return fpath


def f_mkdir_in_path(*filepaths):
    """ 创建路径的父路径, 确保文件路径中的父目录存在

    :param filepaths: 多个参数
    :return: None
    """
    os.makedirs(get_dir(f_join(*filepaths)), exist_ok=True)


def last_part_in_path(fpath):
    """ 规范和扩展文件路径, 获取文件路径中的最后一部分

    :param fpath: 多个参数
    :return: 路径的基名
    """
    return os.path.basename(os.path.normpath(f_expand(fpath)))   # 基名、规范路径、扩展路径


def is_abs_path(*filepaths):
    """ 判断是否是绝对路劲, 绝对路径从根目录开始

    :param filepaths: 多个参数
    :return: True or False
    """
    return os.path.isabs(f_join(*filepaths))


def is_relative_path(*filepaths):
    """ 判断是否是相对路劲

    :param filepaths: 多个参数
    :return: True or False
    """
    return not is_abs_path(f_join(*filepaths))


def f_time(*filepaths):
    """ 获取文件的创建时间

    :param filepaths: 多个参数
    :return: UNIX 时间戳的字符串形式
    """
    return str(os.path.getctime(f_join(*filepaths)))


# TODO 有两个功能一样的函数
def f_append_before_ext(fpath, suffix):
    """ 在文件路径后附加后缀, 目录不变

    :param fpath: 文件路径
    :param suffix: 后缀
    :return: 附加后的文件路径
    """
    name, ext = f_ext(fpath)
    return name + suffix + ext


def insert_before_ext(name, insert):
    """ 在文件路径后附加后缀, 目录不变

    :param name: 文件路径
    :param insert: 后缀
    :return: 附加后的文件路径
    """
    name, ext = f_ext(name)
    return name + insert + ext


# TODO f_add_ext(fpath, ext) 没有处理 fpath 自带扩展名的可能新
def f_add_ext(fpath, ext):
    """ 给文件路径添加扩展名

    :param fpath: 文件路径
    :param ext: 扩展名
    :return: 添加后的文件路径
    """
    if not ext.startswith("."):
        ext = "." + ext
    if fpath.endswith(ext):
        return fpath
    else:
        return fpath + ext


def f_has_ext(fpath, ext):
    """ 判断路径是否以 ext 为扩展名

    :param fpath: 文件路径
    :param ext: 扩展名
    :return: True or False
    """
    _, actual_ext = f_ext(fpath)

    return actual_ext == "." + ext.lstrip(".")


def f_glob(*filepaths):
    """ 搜索匹配特定模式的文件和目录

    :param filepaths: 多个参数
    :return: 匹配的文件和目录的列表
    """
    return glob.glob(f_join(*filepaths), recursive=True)  # 递归的搜索, 会检查到所有子目录


# TODO os.remove(f)时可能会报别的错
def f_remove(*filepaths, verbose=False, dry_run=False):
    """ 根据提供的文件或目录路径来删除它们

    :param filepaths: 多个参数
    :param verbose: 删除成功是否打印消息
    :param dry_run: 是否为预览模式, 即不会真正删除
    :return: None
    """
    assert isinstance(verbose, bool)

    fpath = f_join(filepaths)

    if dry_run:  # 预览模式, 不会删除
        print("Dry run, delete:", fpath)
        return

    # 匹配文件, 然后删除
    for f in glob.glob(fpath):
        try:
            shutil.rmtree(f)   # 删除目录及其所有内容
        except OSError as e:   # 处理与操作系统相关的错误, 有 FileNotFoundError 等子类
            if e.errno == errno.ENOTDIR:  # 判断报错是否因为尝试的路径不是目录 (例如, 它是一个文件)
                try:
                    os.remove(f)   # os.remove()删除文件
                except OSError:
                    pass
    if verbose:
        print(f'Deleted "{fpath}"')


def f_copy(srcpath, dstpath, ignore=None, include=None, exists_ok=True, verbose=False):
    """ 增强版的复制函数, 复制文件或目录 (包括子目录)
    
    :param srcpath: 源文件/目录的路径
    :param dstpath: 目标文件/目录的路径
    :param ignore: 函数, 确定哪些文件或目录应该忽略而不复制
    :param include: 函数, 确定哪些文件或目录应该被包含进复制过程
    :param exists_ok: 目标已经存在时是否会发生错误
    :param verbose: 复制成功打印消息
    :return: None
    """
    srcpath, dstpath = f_expand(srcpath), f_expand(dstpath)   # 扩展源路径、目标路径

    for f in glob.glob(srcpath):
        try:   # 直接处理/复制目录
            f_copytree(f, dstpath, ignore=ignore, include=include, exist_ok=exists_ok)
        except OSError as e:
            if e.errno == errno.ENOTDIR:   # 源路径不是一个目录, 而是一个文件
                shutil.copy(f, dstpath)
            else:
                raise
    if verbose:
        print(f'Copied "{srcpath}" to "{dstpath}"')


def _f_copytree(
        src,
        dst,
        symlinks=False,
        ignore=None,
        exist_ok=True,
        copy_function=shutil.copy2,
        ignore_dangling_symlinks=False,
):
    """ 对标准库中 shutil.copytree 的修改, 添加了对目标路径已存在的情况的处理, 负责递归地复制一个目录及其子目录

    :param src: 源目录的路径
    :param dst: 目标目录的路径
    :param symlinks: 符号链接的复制方式: True 则作为符号链接, 否则会复制链接指向的实际文件或目录
    :param ignore: 函数, 返回一个要忽略的文件/目录名列表
    :param exist_ok: 目标路径已存在的情况下是否引发错误
    :param copy_function: 复制文件的函数, 默认为 copy2
    :param ignore_dangling_symlinks: True 则忽略悬空的符号链接
    :return: 复制后的路径
    """
    names = os.listdir(src)

    if ignore is not None:   # 返回要忽略的名字的集合
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    # 创建路径
    os.makedirs(dst, exist_ok=exist_ok)

    # 复制目录内的信息
    errors = []
    for name in names:
        if name in ignored_names:
            continue

        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if os.path.islink(srcname):   # 是符号链接？
                link_to = os.readlink(srcname)
                if symlinks:  # 复制原始的符号链接并继承其元数据
                    os.symlink(link_to, dstname)   # 在目标路径复制了原始的符号链接
                    shutil.copystat(srcname, dstname, follow_symlinks=not symlinks)   # 复制元数据
                else:
                    if not os.path.exists(link_to) and ignore_dangling_symlinks:
                        continue

                    if os.path.isdir(srcname):
                        _f_copytree(
                            srcname, dstname, symlinks, ignore, exist_ok, copy_function
                        )
                    else:
                        copy_function(srcname, dstname)
            elif os.path.isdir(srcname):   # 是目录？
                _f_copytree(srcname, dstname, symlinks, ignore, exist_ok, copy_function)
            else:   # 是文件？
                copy_function(srcname, dstname)
        except shutil.Error as err:
            errors.extend(err.args[0])
        except OSError as why:
            errors.append((srcname, dstname, str(why)))   # 添加报错信息

    # 复制目录元数据
    try:
        shutil.copystat(src, dst)
    except OSError as why:
        if getattr(why, "winerror", None) is None:   # 检查异常对象 why 是否具有 winerror 属性, 不是特定于 windows 的错误则添加
            errors.append((src, dst, str(why)))

    if errors:
        raise shutil.Error(errors)
    return dst


def _include_patterns(*patterns):
    """ 忽略函数, 用于确定在遍历目录结构时哪些文件或目录应该忽略

    :param patterns: 任意数量的模式
    :return: ignore函数, 得到一个用 patterns 不匹配而忽略的函数
    """
    def _ignore_patterns(path, names):
        """ 忽略模式

        :param path: 当前路径
        :param names: 该目录中的文件和子目录名称列表
        :return: 忽略的集合, 只有文件
        """
        keep = set(
            name for pattern in patterns for name in fnmatch.filter(names, pattern)
        )   # 包含了所有与提供的模式匹配的文件和目录名称
        ignore = set(
            name
            for name in names
            if name not in keep and not is_dir(os.path.join(path, name))
        )   # 不在 keep 中的, 不包括目录
        return ignore

    return _ignore_patterns


def f_copytree(src, dst, symlinks=False, ignore=None, include=None, exist_ok=True):
    """ 文件复制函数, 复制一个目录及其子目录

    :param src: 源目录
    :param dst: 目标目录
    :param symlinks: 符号链接复制方式
    :param ignore: 应忽略的文件列表
    :param include: 应包含的文件列表
    :param exist_ok: 目录存在时是否报错
    :return: 目标目录
    """
    src, dst = f_expand(src), f_expand(dst)
    assert (ignore is None) or (include is None), "ignore= and include= are mutually exclusive"

    if ignore:
        ignore = shutil.ignore_patterns(*ignore)
    elif include:
        ignore = _include_patterns(*include)

    _f_copytree(src, dst, ignore=ignore, symlinks=symlinks, exist_ok=exist_ok)


# TODO f_split_path(fpath, normpath)完全拆分路径, 可以稍微修改加快速度, 不用每次插在列表头
def f_split_path(fpath, normpath=True):
    """ 将一个文件或目录路径拆分为其各个组成部分, 完全拆分

    :param fpath: 文件或目录路径
    :param normpath: 是否规范路径
    :return: 拆分后的列表
    """
    if normpath:
        fpath = os.path.normpath(fpath)

    allparts = []
    while True:
        parts = os.path.split(fpath)   # os.path.split() 拆成两部分, 目录名和文件名

        if parts[0] == fpath:    # 检查拆分后的目录部分是否与原始路径相同, 表示拆完
            allparts.insert(0, parts[0])
            break
        elif parts[1] == fpath:  # 检查拆分后的文件名部分是否与原始路径相同, 表示拆完
            allparts.insert(0, parts[1])
            break
        else:
            fpath = parts[0]
            allparts.insert(0, parts[1])
    return allparts


def get_script_dir():
    """ 获取当前正在执行的脚本的父目录

    :return: 当前执行的 Python 脚本的绝对父目录
    """
    return get_dir(os.path.realpath(sys.argv[0]))   # 父目录, 绝对路径, 脚本的名字或者路径


def get_script_file_name():
    """ 获取当前正在执行的脚本的文件名

    :return: 当前执行的 Python 脚本的文件名
    """
    return os.path.basename(sys.argv[0])


def get_script_self_path():
    """ 获取当前正在执行的脚本的父目录

    :return: 当前执行的 Python 脚本的绝对路径
    """
    return os.path.realpath(sys.argv[0])


def get_parent_dir(location, abspath=False):
    """ 返回指定路径 location 的父目录

    :param location: 路径
    :param abspath: 绝对或者相对
    :return: 父目录
    """
    _path = os.path.abspath if abspath else os.path.relpath
    return _path(f_join(location, os.pardir))   # os.pardir为常量, 表示 ..


def md5_checksum(*filepaths):
    """ 计算指定文件的 MD5 校验和

    :param filepaths: 多个参数
    :return: 文件的 MD5 校验和的十六进制表示形式
    """
    hash_md5 = hashlib.md5()   # md5 hash对象
    with open(f_join(*filepaths), "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):  # 循环读取文件内容, 分块读取, 每块的大小是 65536 字节
            hash_md5.update(chunk)   # b""表示读到文件末尾
    return hash_md5.hexdigest()


def create_tar(fsrc, output_tarball, include=None, ignore=None, compress_mode="gz"):
    """ 从给定的源文件创建 tar 文件

    :param fsrc: 源路径
    :param output_tarball: 目标路径
    :param include: 包含哪些
    :param ignore: 忽略哪些
    :param compress_mode: 压缩模式
    :return:
    """
    fsrc, output_tarball = f_expand(fsrc), f_expand(output_tarball)   # 路径扩展, 绝对路径

    assert compress_mode in ["gz", "bz2", "xz", ""]

    src_base = os.path.basename(fsrc)
    tempdir = None

    if include or ignore:   # 是否提供了包含或忽略的文件模式. 如果是, 需要先复制文件/目录到一个临时目录, 然后再从那里创建 tar 文件
        tempdir = tempfile.mkdtemp()   # 创建临时目录
        tempdst = f_join(tempdir, src_base)   # 临时目录中的新路径
        f_copy(fsrc, tempdst, include=include, ignore=ignore)
        fsrc = tempdst      # fsrc 指向临时目录

    with tarfile.open(output_tarball, "w:" + compress_mode) as tar:
        tar.add(fsrc, arcname=src_base)

    if tempdir:
        f_remove(tempdir)


def extract_tar(source_tarball, output_dir=".", members=None):
    """ 解压文件

    :param source_tarball: 源目录
    :param output_dir: 解压到目录
    :param members: 提取的成员
    :return: None
    """
    source_tarball, output_dir = f_expand(source_tarball), f_expand(output_dir)
    with tarfile.open(source_tarball, "r:*") as tar:
        tar.extractall(output_dir, members=members)


def move_with_backup(*filepaths, suffix=".bak"):
    """ 移动文件或目录, 并在其原始位置创建一个备份

    :param filepaths: 多个参数
    :param suffix: 后缀
    :return: None
    """
    filepaths = str(f_join(*filepaths))
    if os.path.exists(filepaths):
        move_with_backup(filepaths + suffix)
        shutil.move(filepaths, filepaths + suffix)


def timestamp_file_name(name):
    """ 在文件名和其扩展名之间插入一个时间戳, 从而生成一个新的文件名

    :param name: 文件名
    :return:
    """
    stime = datetime.now().strftime("_%H-%M-%S_%m-%d-%y")
    return insert_before_ext(name, stime)


def load_pickle(*filepaths):
    """ 反序列化

    :param filepaths: 多个参数
    :return: 读取后的文件
    """
    with open(f_join(*filepaths), "rb") as fp:
        return pickle.load(fp)


def dump_pickle(data, *filepaths):
    """ 序列化

    :param data: 要保存的数据
    :param filepaths: 多个参数
    :return: 读取后的文件
    """
    with open(f_join(*filepaths), "wb") as fp:
        pickle.dump(data, fp)


def load_text(*filepaths, by_lines=False):
    """ 读取文本

    :param filepaths: 多个参数
    :param by_lines: 是否逐行读取
    :return: 字符串 (列表)
    """
    with open(f_join(*filepaths), "r", encoding="utf-8") as fp:
        if by_lines:
            return fp.readlines()
        else:
            return fp.read()


def load_text_lines(*filepaths):
    # 读文本
    return load_text(*filepaths, by_lines=True)


def dump_text(s, *filepaths):
    # 写一段文本
    with open(f_join(*filepaths), "w") as fp:
        fp.write(s)


def dump_text_lines(lines: list[str], *filepaths, add_newline=True):
    # 逐行写文本
    with open(f_join(*filepaths), "w") as fp:
        for line in lines:
            print(line, file=fp, end="\n" if add_newline else "")


pickle_load = load_pickle
pickle_dump = dump_pickle
text_load = load_text
read_text = load_text
read_text_lines = load_text_lines
write_text = dump_text
write_text_lines = dump_text_lines
text_dump = dump_text

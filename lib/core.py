VERSION = "1.5.0"
BUILD = 27

import atexit
import fcntl
import os
import sys
import time
import traceback

from .color import *

DEBUG = False
DEBUG_DS = False
DEBUG_SANDBOX = False
DEBUG_EXC = True

class MsgLevel():
    DEBUG = 1
    INFO = 2
    WARNING = 3
    ERROR = 4
    FATAL = 5
class Message():
    def __init__(self, msg: Exception | Text | str, level: int = MsgLevel.INFO):
        self.detail = Text()
        if isinstance(msg, Exception):
            self.msg = MAGENTA(msg.__class__.__qualname__) + (" " if level < MsgLevel.FATAL else "\n") + str(msg)
            if hasattr(msg, "__notes__"):
                for x in msg.__notes__:
                    self.msg += "\n" + x
            if DEBUG_EXC and level >= MsgLevel.WARNING:
                sta = []
                while True:
                    if msg.__context__ is None and msg.__cause__ is None:
                        sta.append((msg, 0))
                        break
                    elif msg.__context__ is not None:
                        sta.append((msg, 1))
                        msg = msg.__context__
                    else:
                        sta.append((msg, 2))
                        msg = msg.__cause__
                for e, typ in reversed(sta):
                    if typ == 1:
                        self.detail += "\n处理上述异常时，产生了另一个异常：\n"
                    elif typ == 2:
                        self.detail += "\n上述异常直接引发了另一个异常：\n"
                    for tb in traceback.extract_tb(e.__traceback__):
                        self.detail += "  File <" + Magenta(f"{tb.filename}:{tb.lineno}:{tb.colno}") + "> In `" + Blue(tb.name) + "`:\n"
                        try:
                            with open(tb.filename) as file:
                                line = ""
                                for i in range(tb.lineno):
                                    line = file.readline()
                                cnt = 0
                                for c in line:
                                    if c == " ":
                                        cnt += 1
                                    elif c == "\t":
                                        cnt += 4
                                    else:
                                        break
                                if tb.lineno == tb.end_lineno:
                                    self.detail += "    " + line[cnt:tb.colno] + Red(ITALIC(line[tb.colno:tb.end_colno])) + line[tb.end_colno:]
                                else:
                                    self.detail += "    " + line[cnt:]
                                    for j in range(tb.end_lineno - tb.lineno):
                                        self.detail += "    " + file.readline()[cnt:]
                        except OSError:
                            self.detail += "[无法显示代码]\n"
        else:
            self.msg = msg
        self.level = level
    def add_note(self, s: str):
        self.msg += "\n" + s
    def get_prompt(self):
        match self.level:
            case MsgLevel.DEBUG:
                return Blue("Debug ")
            case MsgLevel.INFO:
                return Blue("Info ")
            case MsgLevel.WARNING:
                return YELLOW("Warning ")
            case MsgLevel.ERROR:
                return RED("Error ")
            case MsgLevel.FATAL:
                return RED("FATAL ")
            case _:
                return NOCOLOR("Message ")
    def toansi(self):
        return self.__repr__().toansi()
    def __repr__(self):
        return self.detail + self.get_prompt() + self.msg

def fatal(msg: Exception | str): ...
def error(msg: Exception | str, remind = False): ...
def warning(msg: str, remind = False): ...
def startup_recall(): ...

REMIND_MAX = 100
def errlog_v1():
    _rmd: list[Text] = []
    def _fexc(err: Exception, *, _prompt = "") -> Text:
        ret = ""
        if DEBUG_EXC:
            for tb in traceback.extract_tb(err.__traceback__):
                ret += "  File <" + Magenta(f"{tb.filename}:{tb.lineno}:{tb.colno}") + "> In `" + Blue(tb.name) + "`:\n"
                try:
                    with open(tb.filename) as file:
                        for i in range(tb.lineno):
                            line = file.readline()
                        if tb.lineno == tb.end_lineno:
                            ret += "    " + line[:tb.colno].lstrip() + Red(ITALIC(line[tb.colno:tb.end_colno])) + line[tb.end_colno:]
                        else:
                            ret += "    " + line.lstrip()
                            for j in range(tb.end_lineno - tb.lineno):
                                ret += "    " + file.readline().lstrip()
                except OSError:
                    ret += "[无法显示代码]\n"
        ret += MAGENTA(err.__class__.__qualname__) + " " + _prompt + str(err)
        if hasattr(err, "__notes__"):
            for x in err.__notes__:
                ret += "\n" + x
        return ret
    def _remember(s: Text):
        if len(_rmd) < REMIND_MAX:
            _rmd.append(s)
        elif len(_rmd) == REMIND_MAX:
            _rmd.append(YELLOW("Warning") + " 异常记录达到上限，因此有异常被忽略。")
    def _get_prompt(dep = 0):
        return Gray(f"{os.path.relpath(sys._getframe(dep+1).f_code.co_filename)}:{sys._getframe(dep+1).f_lineno} ") if DEBUG_EXC else ""
    def fatal(msg: Exception | str):
        _rmd.clear()
        print()
        print((RED("FATAL") + " " + (_fexc(msg, _prompt="\n") if isinstance(msg, Exception) else msg)).toansi())
        print()
    def error(msg: Exception | str, remind = False):
        s = (_fexc(msg, _prompt = _get_prompt(1)) if isinstance(msg, Exception) else RED("Error") + " " + _get_prompt(1) + msg)
        if remind or DEBUG:
            _remember(s)
        print(s.toansi())
    def warning(msg: str, remind = False):
        s = YELLOW("Warning") + " " + _get_prompt(1) + msg
        if remind or DEBUG:
            _remember(s)
        print(s.toansi())
    def _remind():
        if _rmd:
            print()
            print(CYAN("RECALL").toansi())
            for x in _rmd:
                print(x.toansi())
    def startup_recall():
        atexit.register(_remind)
    return {
        "fatal": fatal,
        "error": error,
        "warning": warning,
        "startup_recall": startup_recall,
    }
def errlog_v2():
    _rmd: list[Message] = []
    def _remember(s: Text):
        if len(_rmd) < REMIND_MAX:
            _rmd.append(s)
        elif len(_rmd) == REMIND_MAX:
            _rmd.append(Message("异常记录达到上限，因此有异常被忽略。", MsgLevel.WARNING))
    def fatal(msg: Exception | str):
        _rmd.clear()
        print()
        print(Message(msg, MsgLevel.FATAL).toansi())
        print()
    def _echo(msg: Message, remind = False):
        if remind or DEBUG_EXC:
            _remember(msg)
        print(msg.toansi())
    def error(msg: Exception | str, remind = False):
        _echo(Message(msg, MsgLevel.ERROR), remind)
    def warning(msg: str, remind = False):
        _echo(Message(msg, MsgLevel.WARNING), remind)
    def _remind():
        if _rmd:
            print()
            print(CYAN("RECALL").toansi())
            for x in _rmd:
                print(x.toansi())
    def startup_recall():
        atexit.register(_remind)
    return {
        "fatal": fatal,
        "error": error,
        "warning": warning,
        "startup_recall": startup_recall,
    }
globals().update(errlog_v2())

def acquire_cpu() -> int: ...
def release_cpu(x: int, /): ...

CPU_LOGICAL = False
CPU_PIPE = "/tmp/selfeval-cpu-manage-pipe"
def _get_cpus() -> list[int]:
    if CPU_LOGICAL:
        return [x for x in range(os.cpu_count())]
    mp = {}
    for x in range(os.cpu_count()):
        with open(f"/sys/devices/system/cpu/cpu{x}/topology/core_id") as file:
            mp[int(file.read())] = x
    return list(mp.values())
def affinity_v1():
    # CPU 亲和性调度
    # 不要在运行过程中修改 CPU 核心数！！！
    def _add_lock_ex(fd: int):
        retry = 3
        while retry >= 0:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                retry -= 1
                time.sleep(0.005)
            else:
                return True
        return False
    def acquire_cpu():
        try:
            with open(CPU_PIPE, "xb") as file:
                for x in _get_cpus():
                    file.write(x.to_bytes(4))
        except FileExistsError:
            pass
        with open(CPU_PIPE, "r+b") as file:
            if not _add_lock_ex(file.fileno()):
                return -1
            try:
                pos = file.seek(-4, os.SEEK_END)
            except OSError:
                return -1
            else:
                ret = int.from_bytes(file.read(4))
                file.truncate(pos)
                return ret
            finally:
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)
    def release_cpu(x: int, /):
        if x == -1:
            return
        with open(CPU_PIPE, "ab") as file:
            if not _add_lock_ex(file.fileno()):
                error(f"无法获取 CPU 管道的独占锁，释放的 CPU {x} 没有正确写入管道。", True)
                return
            file.write(x.to_bytes(4))
            fcntl.flock(file.fileno(), fcntl.LOCK_UN)
    return {
        "acquire_cpu": acquire_cpu,
        "release_cpu": release_cpu,
    }
def affinity_v2():
    cpus = _get_cpus()
    def acquire_cpu():
        return cpus.pop() if cpus else -1
    def release_cpu(x: int, /):
        if x != -1:
            cpus.append(x)
    return {
        "acquire_cpu": acquire_cpu,
        "release_cpu": release_cpu,
    }
globals().update(affinity_v2())

# 计时
_ticket = []
def tick():
    _ticket.append(time.monotonic())
def tock(prompt: str = None):
    t = time.monotonic()-_ticket[-1]
    if prompt is None:
        print(t, "s")
    else:
        print(prompt, t, "s")
    _ticket.pop()
    return t

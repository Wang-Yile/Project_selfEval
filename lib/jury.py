import copy
import decimal
import os
import shutil
import subprocess
import time
from itertools import chain

from . import userconf
from .core import DEBUG, error, warning
from .constants import SIGPIPE
from .ds import Program, ModelNULL, Limit, TestConf, JudgeConf, Verdict, Test
from .fmt import LiveStream
from .sandbox import run, run_interactive
from .utils import sec, get_unique_path, is_wsl, is_xok, copy_to, cache_add, cache_get

def _compile_cpp(cwd: str, source: str, output: str, graders: list[str], args: list[str]):
    return Program(output) if run(Program("g++", *args, source, *graders, "-o", output), Limit(time=sec(10)), cwd, stderr=None, trust=True).verdict == "ok" else None
def _compile_cpp_makefile(cwd: str, usage: str):
    return Program(os.path.join(cwd, usage)) if run(Program("make", usage), Limit(time=sec(10)), cwd, stdout=None, stderr=None, trust=True).verdict == "ok" else None
def compile_program(cwd: str, source: str, source_backup: str, lang: str, headers: list[str], graders: list[str], /, use_testlib = False, usage = "program"):
    wd = get_unique_path(cwd)
    os.mkdir(wd)
    testlib_ok = False
    for file in headers:
        if os.path.basename(file) == "testlib.h":
            testlib_ok = True
        copy_to(file, wd)
    if not testlib_ok and use_testlib:
        if (p := userconf.UserJudge.testlib) is ModelNULL:
            error("没有找到 testlib，请将 userconf.UserJudge.testlib 设置为 testlib.h 的绝对路径，或者将 testlib.h 放入数据文件夹中。")
            return
        copy_to(p, wd)
    for file in graders:
        copy_to(file, wd)
    if (x := lang.find(":")) != -1:
        typ = lang[:x]
        flags = lang[x+1:].split(",")
    else:
        typ = lang
        flags = []
    if typ.startswith("c++"):
        if typ == "c++":
            std = "c++14"
        elif typ == "c++20":
            std = "c++2a"
        elif typ == "c++23":
            std = "c++2b"
        elif typ == "c++26":
            std = "c++2c"
        else:
            std = typ
        args = [f"-std={std}", "-Wall", "-Wextra", "-Wshadow", "-Wconversion"]
        makefile = False
        for flag in flags:
            flag = flag.strip()
            if not flag:
                continue
            if flag.startswith("O"):
                args.append("-" + flag)
            elif flag.startswith("D"):
                if flag == "D":
                    error("语言标记中没有指定宏名称。")
                else:
                    args.append("-" + flag)
            elif flag == "static":
                args.append("-static")
            elif flag == "sanitize" or flag == "fsanitize":
                args.append("-fsanitize=address,undefined")
            elif flag == "Makefile":
                makefile = True
            else:
                error(f"未知的 C++ 语言标记 {repr(flag)}")
        if makefile:
            if not os.path.isfile(p := os.path.join(os.path.dirname(source), "Makefile")):
                error("指定使用 Makefile 编译，但源文件同一目录下未找到 Makefile。")
                return
            headers.append(p)
            shutil.copyfile(p, os.path.join(wd, "Makefile"))
        if is_xok(source):
            now = time.time_ns()
            s_mt = os.stat(source).st_mtime_ns
            a_mt = [os.stat(p).st_mtime_ns for p in chain(headers, graders)]
            if s_mt > now or any(t > now for t in a_mt):
                if is_wsl():
                    warning("文件的修改发生在未来，将被无条件重新制作。此警告可能在 WSL 中反复出现。")
                else:
                    warning("文件的修改发生在未来，将被无条件重新制作。")
            elif all(s_mt < t for t in a_mt):
                return Program(source)
            if (source := source_backup) is None:
                return
        try:
            if (tmp := cache_get([source, *graders, *headers], args, "")) is not None:
                shutil.copy(tmp, p := get_unique_path(wd))
                os.remove(tmp)
                return Program(p)
        except Exception as err:
            err.add_note("尝试读取缓存时发生异常。")
            error(err)
        if makefile:
            shutil.copyfile(source, os.path.join(wd, usage + ".cpp"))
            ret = _compile_cpp_makefile(wd, usage)
        else:
            shutil.copyfile(source, p := os.path.join(wd, "a.cpp"))
            ret = _compile_cpp(wd, p, get_unique_path(wd), graders, args)
        if isinstance(ret, Program):
            try:
                cache_add(ret.prog, [source, *graders, *headers], args, "")
            except Exception as err:
                err.add_note("尝试创建缓存时发生异常。")
                error(err)
        return ret
    # elif typ == "customized": # TODO 自定义编译
    #     pass
    else:
        error(f"未知的编程语言 {lang}")

def read_checklog(resp: Verdict, path: str, /, name = "校验器"):
    try:
        with open(path) as file:
            msg = file.readline()[:-1]
    except OSError as err:
        error(err, True)
    from .sandbox import BOX_MASK, BOX_EXIT
    score = None
    normal = True
    if resp.verdict == "re" and (resp.stat & BOX_EXIT):
        verdict = "wa"
        if (resp.stat & BOX_MASK) == 7: # testlib 部分分
            verdict = "pt"
            msg = msg.removeprefix("points ")
            if msg.find(" ") == -1:
                score = msg
            else:
                score, msg = msg.split(" ", 1)
            try:
                score = decimal.Decimal(score)
            except decimal.DecimalException as err:
                error(err)
                score = decimal.Decimal(0)
        elif msg.startswith("wrong answer "):
            verdict = "wa"
            msg = msg.removeprefix("wrong answer ")
        elif msg.startswith("wrong output format "):
            verdict = "wa"
            msg = msg.removeprefix("wrong output format ")
            normal = False
        elif msg.startswith("unexpected eof "):
            verdict = "wa"
            msg = msg.removeprefix("unexpected eof ")
            normal = False
        else:
            verdict = "wa"
            msg = msg
            normal = False
    elif resp.verdict == "ok":
        verdict = "ac"
        msg = msg.removeprefix("ok ")
    else:
        verdict = "fail"
        msg = name + "运行失败 " + repr(resp)
    return verdict, msg, score, normal
def jury(cwd: str, prog: Program, testconf: TestConf, judgeconf: JudgeConf, infile: str, ansfile: str):
    if testconf.limit.fsize <= (fsz := os.stat(ansfile).st_size):
        testconf = copy.deepcopy(testconf)
        testconf.limit.fsize = fsz
    name = judgeconf.name
    retry = judgeconf.retry
    while True:
        wd = get_unique_path(cwd)
        os.mkdir(wd)
        for file in judgeconf.additional:
            copy_to(file, wd)
        permissions = []
        if name:
            stdin = stdout = subprocess.DEVNULL
            shutil.copyfile(infile, os.path.join(wd, name + ".in"))
            permissions.append((os.path.join(wd, name + ".in"), 0))
            permissions.append((os.path.join(wd, name + ".out"), 1))
        else:
            stdin = get_unique_path(wd)
            shutil.copyfile(infile, stdin)
            stdout = get_unique_path(wd)
            permissions.append((stdin, 0))
            permissions.append((stdout, 1))
        if (interactor := judgeconf.interactor):
            checklog = get_unique_path(wd)
            permissions.append((checklog, 1))
            ret, ret_interactor = run_interactive(prog, interactor, testconf.limit, wd, None, stdin, stdout, None if userconf.UserJudge.stderr else subprocess.DEVNULL, checklog, None, permissions, trust_interactor=judgeconf.checker_conf.safe)
        else:
            ret = run(prog, testconf.limit, wd, None, stdin, stdout, None if userconf.UserJudge.stderr else subprocess.DEVNULL, permissions)
        if name:
            stdin = os.path.join(wd, name + ".in")
            stdout = os.path.join(wd, name + ".out")
            if ret.verdict == "ok" and not os.path.isfile(stdout):
                ret.verdict = "wa"
                ret.msg = "未找到选手输出文件"
        from .sandbox import BOX_TLE
        if ret.verdict == "tl" and not (ret.stat & BOX_TLE) and retry > 0:
            if not DEBUG:
                shutil.rmtree(wd)
            retry -= 1
            continue
        break
    from .sandbox import BOX_SIG, BOX_MLE, BOX_OLE, BOX_FBD
    if interactor and (ret_interactor.stat & (BOX_SIG | BOX_TLE | BOX_MLE | BOX_OLE | BOX_FBD)):
        if ret_interactor.stat == BOX_SIG | SIGPIPE:
            ret.verdict = "il"
            ret.msg = "选手程序在读取全部交互库输出前退出 (SIGPIPE)"
        elif ret_interactor.stat & (BOX_SIG | BOX_OLE | BOX_FBD):
            ret.verdict = "fail"
            ret.msg = "交互库运行失败 " + repr(ret_interactor)
        elif ret.verdict == "ok":
            ret.verdict = "il"
            ret.msg = "选手程序正常退出时，交互库运行失败，状态为 " + repr(ret_interactor)
        else:
            ret.msg = "选手程序异常退出时，交互库运行失败，状态为 " + repr(ret_interactor)
    elif interactor and ret_interactor.verdict != "ok":
        ret.verdict, ret.msg, ret.score, _ = read_checklog(ret_interactor, checklog, "交互库")
        if not _:
            ret.verdict = "il"
    elif ret.verdict == "ok":
        checker: Program = copy.deepcopy(judgeconf.checker)
        lim = judgeconf.checker_conf.limit
        if checker is None:
            if interactor:
                ret.verdict, ret.msg, ret.score, _ = read_checklog(ret_interactor, checklog, "交互库")
            else:
                resp = run(Program("diff", "-Z", "-q", "--strip-trailing-cr", stdout, ansfile), lim, cwd, trust=True)
                from .sandbox import BOX_MASK
                if resp.verdict == "re" and (resp.stat & BOX_MASK) == 1:
                    ret.verdict = "wa"
                elif resp.verdict == "ok":
                    ret.verdict = "ac"
                else:
                    ret.verdict = "fail"
                    ret.msg = "diff 运行失败 " + repr(resp)
        else:
            checklog = get_unique_path(wd)
            checker.args += [infile, stdout, ansfile]
            resp = run(checker, lim, cwd, stderr=checklog, permissions=[(infile, 0), (stdout, 0), (ansfile, 0), (checklog, 1)], trust=judgeconf.checker_conf.safe)
            ret.verdict, ret.msg, ret.score, _ = read_checklog(resp, checklog)
    if not DEBUG:
        shutil.rmtree(wd)
    return ret
def jury_test(cwd: str, prog: Program, testconf: TestConf, conf: JudgeConf, test: Test, live: LiveStream = None, arg_testconf: TestConf = None):
    if test.conf:
        testconf.update(test.conf)
    if arg_testconf:
        testconf.update(arg_testconf)
    jump = False
    for tc in test.tests:
        if jump:
            test.result.append(Verdict(verdict="ig"))
            if live:
                live.println()
            continue
        ret = jury(cwd, prog, testconf, conf, tc[0], tc[1])
        test.result.append(ret)
        if ret.verdict != "ac" and (ret.verdict != "pt" or ret.score <= 0):
            if not testconf.keep:
                jump = True
        if live:
            live.println()

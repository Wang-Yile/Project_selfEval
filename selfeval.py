import os
import pwd

from lib.kernel import *

if __name__ == "__main__":
    if os.getuid() == 0:
        kernel_warning("不推荐使用 root 启动 selfeval。")
        try:
            try:
                user = os.getlogin()
            except OSError as err:
                kernel_warning("获取登录用户名失败，将降权至 nobody。")
                user = "nobody"
            try:
                info = pwd.getpwnam(user)
                gid = info.pw_gid
                uid = info.pw_uid
            except KeyError as err:
                raise selfEvalFatalError from err
            os.setgroups([])
            os.setregid(gid, gid)
            os.setreuid(uid, uid)
            if "HOME" in os.environ:
                del os.environ["HOME"]
            if os.getuid() == 0:
                raise selfEvalFatalError("降权失败。请以普通用户身份运行本程序，从而绕过此错误。")
        except selfEvalFatalError as err:
            kernel_fatal(err)
            exit(2)
        except Exception as err:
            kernel_fatal(err)
            exit(1)

import argparse
import atexit
import copy
import resource
import shutil
import sys
import tempfile
from contextlib import redirect_stdout

# import argcomplete
# import rich.traceback
# rich.traceback.install(show_locals=True)

from lib.collect import process_file, collect_tests, collect_problem, collected_problem
from lib.color import *
from lib.constants import RLIM_INFINITY
from lib.core import VERSION, BUILD, DEBUG, enable_cache, disable_cache, cache_disabled, startup_recall, error, fatal, tick, tock
from lib.ds import Model, TestConf, JudgeConf, read_judge_conf, Verdict, Test
from lib.fmt import LiveStream
from lib.jury import compile_program, jury_test
from lib.sandbox import SandboxFatalError
from lib.userconf import UserApperance, UserWarn, UserJudge, UserInteractor
from lib.utils import fmemory, is_xok, path_cmp2, cache_clear

# cache_path = os.path.abspath(".eval")
cache_path = tempfile.mkdtemp(prefix="selfeval-main-cache-")

class Arguments(Model):
    remind: bool = True
    file_list: list[str] = []
    dir_list: list[str] = []
    lang: str = UserApperance.lang
    testconf: TestConf = TestConf()
    judgeconf: JudgeConf = JudgeConf()
def create_parser():
    parser = argparse.ArgumentParser(
        # prog=f"{sys.executable} {sys.argv[0]}",
        prog="selfeval",
        description="使用给定文件夹（默认为 data）中的数据评测给定文件（默认为 1.cpp）。",
        epilog="报告问题请到：<https://github.com/Wang-Yile/Project_selfEval>",
    )
    group = parser.add_mutually_exclusive_group()
    def addx(group: argparse.ArgumentParser | argparse._ArgumentGroup, default: bool, help1: str, help2: str, *names: str):
        if default:
            help1 += "（默认）"
        else:
            help2 += "（默认）"
        gp = group.add_mutually_exclusive_group()
        gp.add_argument(*(f"--{x}" for x in names), default=default, action="store_true", help=help1)
        gp.add_argument(*(f"--x{x}" for x in names), default=not default, action="store_true", help=help2)
    # group.add_argument("-h", "--help", action="store_true")
    group.add_argument("-v", "--version", action="store_true", help="打印版本信息并退出")
    parser.add_argument("-e", "--exercise", action="store_true", help="进入练习模式")
    parser.add_argument("--clean", action="store_true", help="清除缓存")
    addx(parser, not cache_disabled(), "启用缓存", "禁用缓存", "cache")
    addx(parser, True, "启用异常回顾", "禁用异常回顾", "recall")
    parser.add_argument("--lang", type=str, metavar="TAG", help="指定选手程序的语言标记")
    group = parser.add_argument_group("评测选项")
    group.add_argument("--trust", action="store_true", help="信任选手程序和数据文件夹中的程序，启用微型沙箱。")
    addx(group, UserJudge.isolate, "启用核心隔离", "关闭核心隔离", "iso")
    addx(group, UserJudge.stderr, "回显选手程序的标准错误流", "不回显选手程序的标准错误流", "stderr")
    group.add_argument("--testlib", nargs=argparse.OPTIONAL, default=UserJudge.testlib, metavar="PATH", help="使用工作目录下的 testlib.h 或指定 testlib 路径")
    group.add_argument("--name", default=None, type=str, help="启用文件读写并指定文件名")
    group = parser.add_argument_group("资源限制")
    group.add_argument("-t", "--time", type=str, metavar="T")
    group.add_argument("-m", "--memory", type=str, metavar="N")
    group.add_argument("--fsize", type=str, metavar="N")
    group = parser.add_argument_group("警告选项")
    for x in list(UserWarn._allkeys()):
        gp = group.add_mutually_exclusive_group()
        ok = getattr(UserWarn, x)
        gp.add_argument(f"-W,{x}", default=ok, action="store_true")
        gp.add_argument(f"-w,{x}", default=not ok, action="store_true", help=argparse.SUPPRESS)
    group = parser.add_argument_group("交互选项")
    for x in list(UserInteractor._allkeys()):
        gp = group.add_mutually_exclusive_group()
        ok = getattr(UserInteractor, x)
        gp.add_argument(f"-Wi,{x}", default=ok, action="store_true")
        gp.add_argument(f"-wi,{x}", default=not ok, action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--", dest="dash_files", action="store_true", help="该选项之后的参数全部加入文件列表")
    parser.add_argument("files", nargs=argparse.ZERO_OR_MORE, metavar="PATH", help="文件列表")
    return parser

def main(source: str, data: list[str], argv: Arguments):
    tests: list[Test] = []
    testconf = TestConf()
    with collect_problem(): # 一般题目只有一个数据文件夹，但是为了实现当前目录下不递归地收集数据，实现成允许收集多个文件夹的方式
        for d, flag in data:
            if not os.path.isdir(d := os.path.realpath(d)):
                continue
            if flag:
                ts, cnf = collect_tests(d)
                tests += ts
                if cnf is not None:
                    testconf.update(cnf)
            else:
                for file in os.listdir(d):
                    if os.path.isfile(p := os.path.realpath(os.path.join(d, file))):
                        process_file(p, testcase=False)
    tests.sort(key=path_cmp2(lambda x: x.tests[0][0]))
    if not tests:
        print("无数据。")
        return
    problem = collected_problem()
    t = 0
    for d, flag in data:
        if os.path.isfile(p := os.path.realpath(os.path.join(d, "manifest.json"))):
            t = max(t, os.stat(p).st_mtime_ns)
            if (cnf := read_judge_conf(p)) is not None:
                problem.update(cnf)
    problem.update(argv.judgeconf)
    if problem.checker and t >= os.stat(problem.checker).st_mtime_ns and is_xok(problem.checker):
        problem.checker = problem.checker_backup
        if problem.checker is None:
            error("清单文件修改后没有编译校验器，且没有找到对应源文件。")
            return
    if problem.interactor and t >= os.stat(problem.interactor).st_mtime_ns and is_xok(problem.interactor):
        problem.interactor = problem.interactor_backup
        if problem.interactor is None:
            error("清单文件修改后没有编译交互库，且没有找到对应源文件。")
            return
    if problem.name is not None and problem.interactor is not None:
        error("使用文件读写时不能使用交互库。")
        return
    prog = compile_program(cache_path, source, None, argv.lang, problem.headers, problem.graders, False, "program")
    if prog is None:
        error("编译失败。")
        return
    if isinstance(prog, Verdict):
        error(f"编译失败，编译器退出状态为 {repr(prog)}")
        return
    checker = problem.checker
    if checker is not None:
        problem.checker = compile_program(cache_path, checker, problem.checker_backup, problem.checker_conf.lang, problem.headers, [], True, "checker")
        if problem.get("checker") is None:
            error(f"校验器 {checker} 编译失败。")
            return
    if (interactor := problem.interactor) is not None:
        problem.interactor = compile_program(cache_path, interactor, problem.interactor_backup, problem.interactor_conf.lang, problem.headers, [], True, "interactor")
        if problem.get("interactor") is None:
            error(f"交互库 {interactor} 编译失败。")
            return
    if argv.remind and UserApperance.remind:
        startup_recall()
    live = LiveStream(tests)
    for test in tests:
        jury_test(cache_path, prog, copy.deepcopy(testconf), problem, test, live, argv.testconf)
    if UserApperance.conclusion:
        print()
        live.print_conclusion()

def print_header():
    print(BOLD("selfeval").toansi(), VERSION)
def help_help():
    print_header()
    print("用法：")
    print(f"  {sys.executable} {sys.argv[0]} [选项] [评测参数] [文件列表...]")
    print("文件列表中的目录/指向目录的符号链接将作为数据文件夹，并代替默认数据文件夹 data/")
    print("选项：")
    print("  -                  该选项之后的参数全部加入文件列表。")
    print("  -h --help          打印此帮助信息并退出。")
    print("  -v --version       打印版本信息并退出。")
    print("  -e --exercise      进入练习模式。")
    print("     --clean         清除缓存的编译结果。")
    print("     --no-cache      不缓存编译结果。")
    print("     --ignore-recall 禁用异常回顾。")
    print("     --quiet         等效于 --ignore-recall")
    print("  -W -w              打开/关闭警告选项。")
    print("                     例如通过 -w limit 关闭对配置文件中不合理项目的警告。")
    print("  -I -i              打开/关闭交互选项。")
    print("                     例如通过 -I echo 打开交互过程回显。")
    print("评测参数：")
    print("     --lang=<tag>    指定选手程序的语言标记，详见文档" + ITALIC("编程语言-语言标记").toansi() + "。")
    print("     --isolate       启用核心隔离。（默认启用）")
    print("     --expose        关闭核心隔离。")
    print("     --stderr        回显选手程序的标准错误流。")
    print("     --no-stderr     不回显选手程序的标准错误流。（默认不回显）")
    print("评测配置：")
    print("     --testlib       使用工作目录下的 testlib.h")
    print("     --testlib=<p>   指定 testlib 路径。")
    print("     --time=<t>      指定时间限制，如 1000000，1s，1.5s，详见文档" + ITALIC("配置文件-时间字面量").toansi() + "。")
    print("     --memory=<n>    指定空间限制，如 536870912，512M，1GiB，详见文档" + ITALIC("配置文件-空间字面量").toansi() + "。")
    print("     --name=<name>   启用文件读写并指定文件名。")
    print("     --<key>=<value> 覆盖 TestConf 或 JudgeConf 的任意项目。")
    print("报告问题请到：")
    print("  <https://github.com/Wang-Yile/Project_selfEval>")
def help_version():
    print(BOLD("selfeval").toansi(), VERSION, f"({BUILD})")
    print("Copyright (C) 2025 Yile Wang")
    print("本程序是自由软件，不含任何担保。")
    print("详情见 GNU 通用公共许可证，第三版以上：")
    print("  <https://www.gnu.org/licenses/gpl-3.0.html>")

def parse_argv(argv: list[str]):
    i = -1
    raw = False
    ret = Arguments()
    while True:
        i += 1
        if i == len(argv):
            break
        def get_arg(prompt: str):
            nonlocal i
            i += 1
            if i == len(argv):
                error(f"没有为选项 {prompt} 提供参数。")
                return
            return argv[i]
        arg = argv[i]
        if raw or not arg.startswith("-"):
            if not os.path.exists(arg):
                error(f"路径 {repr(arg)} 不存在。")
            arg = os.path.realpath(arg)
            if os.path.isdir(arg):
                ret.dir_list.append(arg)
            else:
                ret.file_list.append(arg)
            continue
        unknown = False
        if arg == "-":
            raw = True
        elif arg in ("-h", "--help"):
            help_help()
            exit()
        elif arg in ("-v", "--version"):
            help_version()
            exit()
        elif arg in ("-e", "--exercise"):
            UserInteractor.echo = True
            UserApperance.remind = False
            UserApperance.conclusion = False
            UserApperance.exmsg = False
            UserJudge.stderr = True
        elif arg == "--clean":
            cache_clear()
        elif arg == "--no-cache":
            disable_cache()
        elif arg in ("--ignore-recall", "--quiet"):
            ret.remind = False
        elif arg.startswith("-W") or arg.startswith("-w"):
            if len(arg) == 2:
                if (key := get_arg(arg)) is None:
                    break
            else:
                key = arg[2:]
            if UserWarn.isvalid(key):
                setattr(UserWarn, key, arg[1] == "W")
            else:
                unknown = True
        elif arg.startswith("-I") or arg.startswith("-i"):
            if len(arg) == 2:
                if (key := get_arg(arg)) is None:
                    break
            else:
                key = arg[2:]
            if UserInteractor.isvalid(key):
                setattr(UserInteractor, key, arg[1] == "I")
            else:
                unknown = True
        elif arg == "--isolate":
            UserJudge.isolate = True
        elif arg == "--expose":
            UserJudge.isolate = False
        elif arg == "--stderr":
            UserJudge.stderr = True
        elif arg == "--no-stderr":
            UserJudge.stderr = False
        elif arg == "--testlib":
            if os.path.isfile(p := os.path.realpath(os.path.abspath("testlib.h"))):
                UserJudge.testlib = p
            else:
                error(f"当前目录下不存在 testlib.h", True)
        elif arg.startswith("--") and arg.find("=") != -1:
            key, val = arg[2:].split("=", 1)
            if key == "lang":
                ret.lang = val
            elif key == "testlib":
                try:
                    if os.path.isfile(p := os.path.realpath(os.path.abspath(val))):
                        UserJudge.testlib = p
                    else:
                        error(f"指定的 testlib 路径 {repr(val)} 无效。", True)
                except OSError:
                    error(f"指定的 testlib 路径 {repr(val)} 无效。", True)
            elif ret.testconf.isvalid(key):
                if val.isdigit():
                    val = int(val)
                ori = ret.testconf.get(key)
                ret.testconf._throw_on_invalid = True
                try:
                    setattr(ret.testconf, key, val)
                except ValueError as err:
                    setattr(ret.testconf, key, ori)
                    err.add_note(f"测试点配置无法解析的项目 {key} = {repr(val)}")
                    error(err, True)
                finally:
                    ret.testconf._throw_on_invalid = False
            elif ret.judgeconf.isvalid(key):
                ori = ret.judgeconf.get(key)
                ret.judgeconf._throw_on_invalid = True
                try:
                    setattr(ret.judgeconf, key, val)
                except ValueError as err:
                    setattr(ret.judgeconf, key, ori)
                    err.add_note(f"评测配置无法解析的项目 {key} = {repr(val)}")
                    error(err, True)
                finally:
                    ret.judgeconf._throw_on_invalid = False
            else:
                unknown = True
        else:
            unknown = True
        if unknown:
            error(f"未知选项 {repr(arg)}", True)
    return ret
def parse_argv2(argv: list[str]):
    parser = create_parser()
    # argcomplete.autocomplete(parser)
    space = parser.parse_intermixed_args(argv)
    if space.version:
        help_version()
        exit()
    ret = Arguments()
    if space.exercise:
        UserInteractor.echo = True
        UserApperance.remind = False
        UserApperance.conclusion = False
        UserApperance.exmsg = False
        UserApperance.trust = True
        UserJudge.stderr = True
        ret.testconf.limit.memory = RLIM_INFINITY
    for key, val in space._get_kwargs():
        if key.startswith("W,") or key.startswith("w,"):
            ok = key[0] == "W"
            if val:
                setattr(UserWarn, key[2:], ok)
            else:
                setattr(UserWarn, key[2:], not ok)
        elif key.startswith("Wi,") or key.startswith("wi,"):
            ok = key[0] == "W"
            if val:
                setattr(UserInteractor, key[3:], ok)
            else:
                setattr(UserInteractor, key[3:], not ok)
        elif key == "files":
            for o in val:
                p = os.path.abspath(os.path.realpath(o))
                if os.path.exists(p):
                    if os.path.isdir(p):
                        ret.dir_list.append(p)
                    else:
                        ret.file_list.append(p)
                else:
                    error(f"路径 {repr(o)} 不存在。")
        elif val:
            if key == "clean":
                cache_clear()
            elif key == "cache":
                enable_cache()
            elif key == "xcache":
                disable_cache()
            elif key == "recall":
                ret.remind = True
            elif key == "xrecall":
                ret.remind = False
            elif key == "iso":
                UserJudge.isolate = True
            elif key == "xiso":
                UserJudge.isolate = False
            elif key == "stderr":
                UserJudge.stderr = True
            elif key == "xstderr":
                UserJudge.stderr = False
            elif key == "lang":
                ret.lang = val
            elif key == "trust":
                UserApperance.trust = val
            elif key == "testlib":
                try:
                    if os.path.isfile(o := os.path.realpath(os.path.abspath(val))):
                        UserJudge.testlib = o
                    else:
                        error(f"testlib 路径 {repr(val)} 无效。", True)
                except OSError:
                    error(f"testlib 路径 {repr(val)} 无效。", True)
            elif key == "time":
                ret.testconf.limit.time = val
            elif key == "memory":
                ret.testconf.limit.memory = val
            elif key == "fsize":
                ret.testconf.limit.fsize = val
        elif key == "testlib":
            if os.path.isfile(o := os.path.realpath(os.path.abspath("testlib.h"))):
                UserJudge.testlib = o
            else:
                error(f"当前目录下不存在 testlib.h", True)
    return ret
def starter():
    ret = parse_argv2(sys.argv[1:])
    print_header()
    if os.path.isdir(cache_path):
        shutil.rmtree(cache_path)
    os.mkdir(cache_path)
    if not DEBUG:
        atexit.register(lambda: shutil.rmtree(cache_path))
    prog = os.path.abspath(ret.file_list[0] if ret.file_list else "1.cpp")
    # data = [os.path.join(os.path.dirname(prog), path) for path in (["data"] if len(lst) < 2 else lst[1:])]
    data = [
        (os.path.abspath("data"), True),
        (os.getcwd(), False),
        *((d, True) for d in ret.dir_list),
    ]
    if len(ret.file_list) > 1:
        for x in ret.file_list[1:]:
            error(f"冗余参数 {x}")
    try:
        main(prog, data, ret)
    except KeyboardInterrupt:
        print()
        print("评测被打断。")

if __name__ == "__main__":
    autoset_color()
    tick()
    try:
        starter()
    except SandboxFatalError as err:
        fatal(err)
        exit(2)
    if UserApperance.exmsg:
        t = tock("用时")
        mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        print("内存用量", fmemory(mem))
        if (p := os.environ.get("SELFEVAL_DEBUG_AUTO", None)) is not None:
            with (
                open(p, "w") as file,
                redirect_stdout(file),
            ):
                print(t)
                print(mem)

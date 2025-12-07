import os
import shutil
import subprocess
import sys
import time

__st = time.monotonic()

# compiler 指定你的 C++ 编译器，你可能需要修改它为你使用的编译器
compiler = "g++"
# 默认的 C++ 编译选项
args = [
    "-std=c++2a",
    "-Wall",
    "-Wextra",
    "-Wshadow",
    "-Wconversion",
    "-O3",
]
# 是否设置权限能力，设置能力需要管理员权限
# 你可以通过命令行参数 --no-cap 取消设置
setcap = True
for arg in sys.argv[1:]:
    if arg == "--no-cap":
        setcap = False
    else:
        print(f"无法识别参数 {repr(arg)}")

# 判断是否处于 WSL 环境
if "WSL" in os.uname().release:
    args.append("-DWSL")

# 此函数跟随 lib.color 更新
def detect_color():
    if not sys.stdout.isatty():
        return False
    if "NO_COLOR" in os.environ:
        return False
    term = os.environ.get("TERM")
    if not term or term == "dumb":
        return False
    colorterm = os.environ.get("COLORTERM")
    if colorterm == "truecolor" or colorterm == "24bit":
        return True
    vte = os.environ.get("VTE_VERSION")
    if vte.isdigit() and int(vte) >= 3600: # VTE 0.36.0 开始实验性支持真彩色
        return True
    return False
colorful = detect_color()
def error(err: Exception):
    if hasattr(err, "__notes__"):
        for line in reversed(err.__notes__):
            print(line)
    if colorful:
        print("\033[35;1m", end="")
    print(f"{err.__class__.__qualname__}:", end=" ")
    if colorful:
        print("\033[0m", end="")
    print(err)
def ensure_removed(path: str):
    if not os.path.exists(path):
        return
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except Exception as err:
        err.add_note(f"调用 ensure_removed({repr(path)}) 时发生此错误。")
        error(err)
        exit(1)
def run(cmd: list[str]):
    if colorful:
        print(f"\033[33;1m{cmd[0]}\033[0m", *cmd[1:])
    else:
        print(" ".join(cmd))
    try:
        proc = subprocess.run(cmd)
        proc.check_returncode()
    except Exception as err:
        err.add_note(f"调用 run({" ".join(cmd)}) 时发生此错误。")
        error(err)
        exit(1)

cwd = os.getcwd()
source = os.path.join(cwd, "src")
binary = os.path.join(cwd, "bin")
lib = os.path.join(cwd, "lib")
build = os.path.join(cwd, "build")

ensure_removed(binary)
ensure_removed(build)
run(["mkdir", "-p", binary])
run(["mkdir", "-p", build])

run([compiler, os.path.join(source, "sandbox.cpp"), "-o", os.path.join(binary, "sandbox"), *args, "-lseccomp", "-lcap"])
if setcap:
    run(["sudo", "setcap", "cap_sys_nice+ep", os.path.join(binary, "sandbox")])

run([compiler, os.path.join(source, "sandbox-tiny.cpp"), "-o", os.path.join(binary, "sandbox-tiny"), *args])

run([compiler, os.path.join(source, "gen.cpp"), "-o", os.path.join(build, "gen"), *args])
os.chdir(build)
run(["./gen"])
os.chdir(cwd)
run(["cp", os.path.join(build, "constants.py"), os.path.join(lib, "constants.py")])

run(["rm", "-rf", build])

__ed = time.monotonic()
print(f"构建过程使用 {__ed-__st:.3f} 秒。")

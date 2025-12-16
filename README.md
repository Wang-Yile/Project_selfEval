# selfeval

> version 1.5.0  
> 内部版本 rev27  
> Copyright (C) 2025 [Yile Wang](mailto:bluewindde@163.com)  
> 使用 [GNU 通用公共许可证，第三版以上](https://www.gnu.org/licenses/gpl-3.0.html) 发布，不含任何担保。  

信息学竞赛程序本地测试工具。

建议搭配 VSCode 使用。

项目仍在开发中，请在受信任环境中使用，API 随时可能变化。

## 部署指南

最低配置：

- Linux 5.0 以上（对应 Ubuntu 20 以上）
- Python 3.12 以上
- GNU GCC 8 以上
- libseccomp 2.5.0 以上，需要开发包
- libcap 2.32 以上，需要开发包

建议全部更新到可以更新的最新版本。

如果你使用 Windows，请 [安装 WSL2](https://learn.microsoft.com/zh-cn/windows/wsl/install)。

如果你确认操作系统为 Debian/Ubuntu (基于 Linux 5.0 +)，并安装了 Python 和 GCC，可以运行 `install.sh` 以直接使用推荐配置安装。运行脚本前可以通过指定环境变量 `PY`，选择 Python 解释器路径。

### 搭建 Python 环境

以下命令如果无特殊说明，均在安装目录下执行。

检查 Python 版本：

```sh
python3 --version
```

如果你使用旧版操作系统，例如 NOILinux（Ubuntu 20.04），请考虑 [deadsnakes](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa) 或 [pyenv](https://github.com/pyenv/pyenv)。

使用如下命令创建 venv：

```sh
python3 -m venv .venv
```

在控制台激活 venv：

```sh
source .venv/bin/activate
```

然后安装依赖：

```sh
pip3 install -r requirements.txt
```

如果你所在的地区直接访问 PyPI 不稳定，可以尝试使用镜像，例如：

```sh
pip3 install -r requirements.txt -i https://mirror.tuna.tsinghua.edu.cn/pypi/web/simple
```

本程序使用 natsort 排序文件，如果你希望获得更好的排序结果，请安装 PyICU，参见 [natsort 上的相关介绍](https://github.com/SethMMorton/natsort?tab=readme-ov-file#pyicu)。

这样就准备好了 Python 环境。

### 编译沙箱

沙箱基于 seccomp-bpf 和 capabilities。

检查 GCC 版本：

```sh
g++ --version
```

安装 libseccomp 和 libcap，以 Ubuntu 为例：

```sh
# 运行时依赖
sudo apt install libseccomp2
sudo apt install libcap2
# 构建依赖
sudo apt install libseccomp-dev
sudo apt install libcap-dev
```

沙箱使用脚本 build.py 构建，脚本包含如下可修改的变量：

- compiler：指定编译器，默认为 g++。你可能需要修改它为你使用的编译器。如果你使用非 GCC 的编译器，请自行研究。
- args：指定默认 C++ 编译选项。如果在 WSL 中编译，脚本将自动添加 `-DWSL` 宏，沙箱将针对 WSL 进行修改。
- setcap：控制是否设置能力，设置能力需要管理员权限，默认为是。如果不希望设置能力，请从命令行传入参数 `--no-cap`。
- clean：控制构建完成后是否删除 build 目录，默认为否。如果不希望删除 build 目录，请从命令行传入参数 `--keep-build`。

脚本将生成如下中间结果：

- build/gen：用于生成 lib.constants 模块的程序。
- build/constants.py：由 build/gen 生成的临时文件。

脚本将制作如下项目：

- 主沙箱：根据 src/sandbox.cpp 编译出 bin/sandbox。
- 简化版沙箱：根据 src/sandbox-tiny.cpp 编译出 bin/sandbox-tiny。
- 常量模块：根据 src/constants.cpp 编译出 build/constants，然后运行它以获取 lib/constants.py。
- 宏定义模块：根据 src/macros.cpp，通过 `g++ -E -dM` 选项编译出 build/macros，获取已定义的全部系统调用，存储到 lib/macros.py。

执行如下命令即可编译沙箱，你可能需要输入密码以设置可执行文件能力（不要以 sudo 运行！）：

```sh
python3 build.py
```

如果没有发生错误或被选项抑制，构建完成后，脚本会自动删除 build 目录。

**注意：本程序的沙箱被设计为在非特权环境下工作。建议以普通用户权限运行，避免使用 root。**

### 启动方法

你可以从任何地方运行安装目录下的 run.sh 启动 selfeval，可以附加命令行参数。

你需要确保 run.sh 有执行权限：`chmod +x run.sh`

不推荐直接使用 python 解释器运行 selfeval.py，因为这样可能无法正常加载虚拟环境。

### （可选）在终端中创建别名

为了让使用 selfeval 更加方便，建议在终端中创建别名，以 bash 为例，步骤如下：

1. 修改 `~/.bashrc` 或 `~/.bash_aliases` 可以在 bash 启动时注入命令。

    注意：修改配置文件前建议进行备份。

2. 在 `~/.bash_aliases` 文件末尾加入下面的代码：

    ```sh
    alias selfeval="/path/to/selfeval/run.sh"
    ```

    例如，selfeval 安装在文件夹 `/home/user/Project_selfEval/` 下时：

    ```sh
    alias selfeval="/home/user/Project_selfEval/run.sh"
    ```

3. 重启终端或者使用命令 `source ~/.bashrc` 重新加载终端配置即可应用更改。

4. 如果别名没有生效，请检查 `~/.bashrc` 是否包含以下内容来加载别名文件，或者直接将配置别名的代码加在 `~/.bashrc` 文件末尾：

    ```sh
    if [ -f ~/.bash_aliases ]; then
        . ~/.bash_aliases
    fi
    ```

通过 `install.sh` 脚本自动安装时，默认将别名放在 `~/.selfeval.sh` 中。

## 测试环境

本项目在如下环境进行过测试：

| 设备名称 | 内部版本 | OS | Linux | Python | GCC |
| :-: | :-: | :-: | :-: | :-: | :-: |
| NOILinux 物理机 | rev27 | Ubuntu 20.04.6 | 5.15.0-139-generic | 3.13.9 | 9.4.0 |
| NOILinux + gcc 13 物理机 | rev27 | Ubuntu 20.04.6 | 5.15.0-139-generic | 3.13.9 | 13.1.0 |
| Ubuntu 24 虚拟机 | rev25 | VMWare Workstation 17.6.4 <br> Ubuntu 24.04.3 | 6.14.0-36-generic | 3.12.3 | 13.3.0 |
| WSL2 | rev26 | Windows 11 25H2 (26200.7171) <br> Ubuntu 24.04 | 5.15.167.4-microsoft-standard-WSL2 | 3.12.3 | 13.3.0 |

## 文档

咕咕咕……

docs 文件夹下可以看到已经完成的部分。

## 第三方依赖

- **testlib.h**: MIT 许可证 © Mike Mirzayanov  
  位于 `third_party/testlib/`  
  仓库：<https://github.com/MikeMirzayanov/testlib>

## 问题反馈

如遇问题，请提交 Issue。

如果问题涉及隐私、安全或者其它不适合公开的场景，请 [通过邮箱联系](mailto:bluewindde@163.com)。

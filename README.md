# selfeval

> version 1.5.0  
> 构建版本 rev25  
> Copyright (C) 2025 [Yile Wang](mailto:bluewindde@163.com)  
> 使用 [GNU 通用公共许可证，第三版以上](https://www.gnu.org/licenses/gpl-3.0.html) 发布，不含任何担保。  

信息学竞赛程序本地测试工具。

建议搭配 VSCode 使用。

项目仍在开发中，请在受信任环境中使用，API 随时可能变化。

## 部署指南

最低配置：

- Linux 5.0 以上（对应 Ubuntu 20 以上）
- Python 3.12 以上
- GCC 8 以上
- libseccomp-dev 2.5.0 以上

建议全部更新到可以更新的最新版本。

### 搭建 Python 环境

以下命令如果无特殊说明，均在安装目录下执行。

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

这样就准备好了 Python 环境。

### 编译沙箱

沙箱基于 seccomp-bpf。

在 lib 目录下执行命令 make 即可使用 gcc 编译沙箱，其它编译器请自行研究。

你可能需要修改 Makefile 中 `COMPILER = ...` 一行，使得它与你使用的编译器匹配。

### 启动方法

你可以从任何地方运行安装目录下的 run.sh 启动 selfeval，可以附加命令行参数。

你需要确保 run.sh 有执行权限：`chmod +x run.sh`

不推荐直接使用 python 解释器运行 selfeval.py，因为这样可能无法正常加载虚拟环境。

### （可选）在 bash 中配置别名

为了让使用 selfeval 更加方便，建议在 bash 中创建别名，步骤如下：

1. 在 bash 中，可以修改 `~/.bashrc` 或 `~/.bash_aliases` 以在 bash 启动时注入命令。

    注意：修改配置文件前建议进行备份。

2. 在 `~/.bash_aliases` 文件末尾加入下面的代码：

    ```sh
    alias selfeval="/path/to/selfeval/run.sh"
    ```

    例如，selfeval 安装在文件夹 `/home/user/selfeval/` 下时：

    ```sh
    alias selfeval="/home/user/selfeval/run.sh"
    ```

3. 重启终端或者使用命令 `source ~/.bashrc` 重新加载终端配置即可应用更改。

4. 如果别名没有生效，请检查 `~/.bashrc` 是否包含以下内容来加载别名文件，或者直接将配置别名的代码加在 `~/.bashrc` 文件末尾：

    ```sh
    if [ -f ~/.bash_aliases ]; then
        . ~/.bash_aliases
    fi
    ```

## 测试环境

本项目在如下环境进行过测试：

| 设备名称 | OS | Linux | Python | GCC | libseccomp |
| :-: | :-: | :-: | :-: | :-: | :-: |
| NOILinux 物理机 | Ubuntu 20.04.6 | 5.15.0-139-generic | 3.13.7 | 9.4.0 | 2.5.1 |
| NOILinux + gcc 13 物理机 | Ubuntu 20.04.6 | 5.15.0-139-generic | 3.13.7 | 13.1.0 | 2.5.1 |
| Ubuntu 24 虚拟机 | VMWare Workstation 17.6.4 <br> Ubuntu 24.04.3 | 6.14.0-36-generic | 3.12.3 | 13.3.0 | 2.5.5 |
| WSL2 | Windows 11 25H2 <br> Ubuntu 24.04.6 | unknown | 3.12.3 | 13.3.0 | / |

注：构建版本 rev18 及以上未在 WSL2 上测试，待后续补测。由于 rev22 前没有引入 libseccomp，不标记版本。

## 文档

咕咕咕……

docs 文件夹下可以看到已经完成的部分。

## 问题反馈

如遇问题，请提交 Issue。

如果问题涉及隐私、安全或者其它不适合公开的场景，请 [通过邮箱联系](mailto:bluewindde@163.com)。

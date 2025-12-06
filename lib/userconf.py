from .ds import Model

class _UserApperanceConf(Model):
    remind: bool = True
    conclusion: bool = True
    exmsg: bool = True
    lang: str = "c++14:O2"
UserApperance = _UserApperanceConf()

class _UserWarnConf(Model):
    limit: bool = True
    checker_limit: bool = True
UserWarn = _UserWarnConf()

class _UserJudgeConf(Model):
    # testlib: str = "/home/noilinux/selfeval/testlib.h"
    testlib: str
    isolate: bool = True
UserJudge = _UserJudgeConf()

class _UserInteractorConf(Model):
    fast_sandbox: bool = False
    echo: bool = False
UserInteractor = _UserInteractorConf()

import os

from .ds import Model

class _UserApperanceConf(Model):
    remind: bool = True
    conclusion: bool = True
    exmsg: bool = True
    trust: bool = False
    lang: str = "c++14:O2"
UserApperance = _UserApperanceConf()

class _UserWarnConf(Model):
    limit: bool = True
    checker_limit: bool = True
UserWarn = _UserWarnConf()

class _UserJudgeConf(Model):
    testlib: str = os.path.join(os.path.dirname(__file__), "..", "third_party", "testlib", "testlib.h")
    isolate: bool = True
    stderr: bool = False
UserJudge = _UserJudgeConf()

class _UserInteractorConf(Model):
    fast_sandbox: bool = False
    echo: bool = False
UserInteractor = _UserInteractorConf()

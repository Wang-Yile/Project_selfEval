from .ds import Model

class _UserWarnConf(Model):
    warn_limit: bool = True
    warn_checker_limit: bool = True
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

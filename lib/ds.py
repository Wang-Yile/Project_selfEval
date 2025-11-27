import copy
import decimal
import json
import os
from types import GenericAlias, UnionType
from typing import Any, Callable, TypeVar

import json5

from .core import DEBUG_DS, error, warning
from .utils import sec, msec, MiB, tobool, totime, tomem, ftime, fmemory, stdopen

class Program():
    __slots__ = ("prog", "args", "env")
    def __init__(self, prog: str = None, *args: str):
        self.prog = prog
        self.args = list(args)
        self.env: os._Environ = None

class _ModelNULLType():
    __slots__ = ()
    def __init_subclass__(cls):
        raise TypeError("_ModelNULLType 不能被继承，你应该直接使用 ModelNULL 常量。")
    def __copy__(self):
        return self
    def __deepcopy__(self, memo):
        return self
    def __bool__(self):
        return False
    def __eq__(self, value):
        return isinstance(value, _ModelNULLType)
    def __ne__(self, value):
        return not isinstance(value, _ModelNULLType)
    def __repr__(self):
        return "<ModelNULL>"
    def __hash__(self):
        return 0x66ccff
ModelNULL = _ModelNULLType()
class ModelTransform():
    """
    转换基类，实现为导入或导出不影响类的行为。
    """
    __slots__ = ()
    _method: list[tuple[type, Callable[[Any], Any]]] = []
    @classmethod
    def trans(cls, obj: Any):
        for typ, func in cls._method:
            if isinstance(obj, typ):
                if (x := func(obj)) != ModelNULL:
                    return x
        return ModelNULL
    @classmethod
    def decorate_none_to_null(cls, func: Callable[[Any], Any | None]):
        def foo(x):
            return ModelNULL if (x := func(x)) is None else x
        return foo
    def __init_subclass__(cls):
        cls.__slots__ = ()
class ModelDirectTransform(ModelTransform):
    _method: dict[type, Callable[[Any], Any]] = {}
class ModelTransformToBool(ModelTransform):
    _method = [(str, ModelTransform.decorate_none_to_null(tobool))]
class ModelTransformToTime(ModelTransform):
    _method = [(str, ModelTransform.decorate_none_to_null(totime))]
class ModelTransformToMemory(ModelTransform):
    _method = [(str, ModelTransform.decorate_none_to_null(tomem))]
class ModelTransformFmtTime(ModelTransform):
    _method = [(int, ftime)]
class ModelTransformFmtMemory(ModelTransform):
    _method = [(int, fmemory)]

class Model():
    _method: dict[str, ModelTransform] = {}
    _export: dict[str, ModelDirectTransform] = {}
    _ignore: set = set()
    @classmethod
    def get_types_of(cls, key: str) -> _ModelNULLType | tuple[Any, ...]:
        if key in cls._ignore or key not in cls.__annotations__:
            return ModelNULL
        if (typ := cls.__annotations__.get(key)) is None:
            return ()
        elif isinstance(typ, GenericAlias):
            return (typ.__origin__, )
        elif isinstance(typ, UnionType):
            return typ.__args__
        return (typ, )
    def __init__(self, *, record_extra = False, record_invalid = False, throw_on_extra = False, throw_on_invalid = False, **kwargs):
        self._default: dict[str, Any] = {}
        self._real: dict[str, Any] = {}
        self._record_extra: list[tuple[str, Any]] = [] if record_extra else None
        self._record_invalid: list[tuple[str, Any]] = [] if record_invalid else None
        self._throw_on_extra = throw_on_extra
        self._throw_on_invalid = throw_on_invalid
        for key in self.__class__.__annotations__:
            if (val := getattr(self, key, ModelNULL)) is not ModelNULL:
                self._default[key] = copy.deepcopy(val)
            super().__setattr__(key, val)
        for key, val in kwargs.items():
            if key.startswith("_"):
                raise TypeError(f"{self.__class__.__qualname__} 不支持下划线开头的键 {key} = {repr(val)}")
            setattr(self, key, val)
    def _is_ignored(self, key: str):
        return key.startswith("_") or key in self.__class__._ignore
    def _update(self, key: str, value, /):
        if value is ModelNULL: # 逻辑删除
            if key in self._real:
                del self._real[key]
            return super().__setattr__(key, self._default.get(key, ModelNULL))
        self._real[key] = value
        if (typs := self.__class__.get_types_of(key)) is ModelNULL: # 冗余项
            self.record_extra(key, value)
            return
        for typ in typs:
            if isinstance(value, typ): # 通过类型检查
                return super().__setattr__(key, value)
        if (tr := self.__class__._method.get(key, ModelNULL)) is not ModelNULL: # 尝试类型转换
            if (val := tr.trans(value)) is not ModelNULL: # 转换成功
                return super().__setattr__(key, val)
        self.record_invalid(key, value)
        return super().__setattr__(key, self._default.get(key, ModelNULL))
    def record_extra(self, key: str, value, /):
        if self._record_extra is not None:
            self._record_extra.append((key, value))
        elif DEBUG_DS:
            warning(f"未记录的冗余项目 {repr(key)} = {repr(value)}")
        if self._throw_on_extra:
            raise ValueError(f"冗余项目 {repr(key)} = {repr(value)}")
    def record_invalid(self, key: str, value, /):
        if self._record_invalid is not None:
            self._record_invalid.append((key, value))
        elif DEBUG_DS:
            error(f"未记录的无效项目 {repr(key)} = {repr(value)}")
        if self._throw_on_invalid:
            raise ValueError(f"冗余项目 {repr(key)} = {repr(value)}")
    def __setattr__(self, key: str, value):
        if self._is_ignored(key):
            return super().__setattr__(key, value)
        return self._update(key, value)
    def __delattr__(self, key: str):
        if self._is_ignored(key):
            return super().__delattr__(key)
        self._update(key, ModelNULL)
    def get(self, key: str, /):
        """
        获取模型内部 key 对应的值，如果没有存储 key 则返回 ModelNULL。

        这个值是按原样提供的，没有经过类型转换，且不会返回定义模型时给出的默认值。

        如果需要使用转换后的值并考虑默认值，请直接访问对应属性，或者使用 getattr(model, key)。
        """
        return self._real.get(key, ModelNULL)
    def keys(self):
        """
        获取模型存储的键。
        """
        return self._real.keys()
    def items(self):
        """
        获取模型存储的项目。
        """
        return self._real.items()
    def values(self):
        """
        获取模型存储的值。
        """
        return self._real.values()
    def isvalid(self, key: str):
        """
        判断 key 是否是合法的键。

        这个接口用于外部实现，目的是兼容扩展类定义的特殊类名，内部仍然使用 key in self.__class__.__annotations__
        """
        return key in self.__class__.__annotations__
    def __len__(self):
        return len(self._real)
    def __contains__(self, key: str):
        return key in self._real
    def __iter__(self):
        return iter(self._real)
    def update(self, dic: "Model | dict[str, Any]", /):
        """
        从 dic 更新模型。
        """
        if isinstance(dic, dict):
            return self.update(TestConf.from_dict(dic))
        for key in dic:
            setattr(self, key, dic.get(key))
    def get_extra_recursive(self, root: str = None):
        """
        递归获取已记录的冗余项目。
        """
        root = "" if root is None else root + "."
        ret = []
        for key, val in self._record_extra:
            ret.append((root + key, val))
        for key in self.__class__.__annotations__:
            if (val := self.get(key)) is not ModelNULL and isinstance(val, Model):
                ret += val.get_extra_recursive(root + key)
        return ret
    def get_invalid_recursive(self, root: str = None):
        """
        递归获取已记录的无效项目。
        """
        root = "" if root is None else root + "."
        ret = []
        for key, val in self._record_invalid:
            ret.append((root + key, val))
        for key in self.__class__.__annotations__:
            if (val := self.get(key)) is not ModelNULL and isinstance(val, Model):
                ret += val.get_invalid_recursive(root + key)
        return ret
    @classmethod
    def from_dict(cls, dic: dict[str, Any], /, record_extra = False, record_invalid = False, strict = True, prohibit: set[str] = None):
        ret = cls()
        if record_extra:
            ret._record_extra = []
        if record_invalid:
            ret._record_invalid = []
        for key, val in dic.items():
            if (prohibit is not None and key in prohibit) or (strict and key.startswith("_")): # 避免攻击
                ret.record_invalid(key, val)
                continue
            setattr(ret, key, val)
        return ret
    @classmethod
    def from_model(cls, dic: "Model", /, record_extra = False, record_invalid = False):
        ret = cls()
        if record_extra:
            ret._record_extra = []
        if record_invalid:
            ret._record_invalid = []
        for key, val in dic.items():
            setattr(ret, key, val)
        return ret

def ModelTransformToModelWrapper(cls: type[Model], /, record_extra = False, record_invalid = False):
    class A(ModelTransform):
        _method = [(dict, lambda dic: cls.from_dict(dic, record_extra, record_invalid))]
    return A

def ModelAliasWrapper(alias: dict[str, str]):
    T = TypeVar("T", bound=Model)
    def _wrapper(cls: type[T]) -> type[T]:
        def trans(key: str):
            return alias[key] if key in alias else key
        class A(cls):
            __annotations__ = cls.__annotations__
            def __setattr__(self, key, value):
                if self._is_ignored(key):
                    return super().__setattr__(key, value)
                return super().__setattr__(trans(key), value)
            def isvalid(self, key):
                if self._is_ignored(key):
                    return super().isvalid(key)
                return super().isvalid(trans(key))
        return A
    return _wrapper
def ModelDotWrapper():
    T = TypeVar("T", bound=Model)
    def _wrapper(cls: type[T]) -> type[T]:
        def split(key: str):
            if (x := key.find(".")) == -1:
                return key, None
            return key[:x], key[x+1:]
        class A(cls):
            __annotations__ = cls.__annotations__
            def __setattr__(self, key, value):
                if self._is_ignored(key):
                    return super().__setattr__(key, value)
                root, child = split(key)
                if child is None:
                    return super().__setattr__(key, value)
                if (v := self.get(root)) is ModelNULL:
                    if (tr := self.__class__._method.get(root, ModelNULL)) is ModelNULL:
                        self.record_invalid(key, value)
                        return
                    self._real[root] = v = tr.trans({})
                if isinstance(v, Model):
                    return setattr(v, child, value)
                self.record_invalid(key, value)
            def isvalid(self, key):
                if self._is_ignored(key):
                    return super().isvalid(key)
                return super().isvalid(split(key)[0])
        return A
    return _wrapper

# TODO
class LangTag(Model):
    pass

class Limit(Model):
    _method = {
        "time": ModelTransformToTime,
        "time_redundancy": ModelTransformToTime,
        "memory": ModelTransformToMemory,
        "memory_redundancy": ModelTransformToMemory,
        "stack": ModelTransformToMemory,
        "fsize": ModelTransformToMemory,
    }
    _export = {
        "time": ModelTransformFmtTime,
        "time_redundancy": ModelTransformFmtTime,
        "memory": ModelTransformFmtMemory,
        "memory_redundancy": ModelTransformFmtMemory,
        "stack": ModelTransformFmtMemory,
        "fsize": ModelTransformFmtMemory,
    }
    time: int = sec(1)
    time_redundancy: int = msec(200)
    memory: int = MiB(512)
    memory_redundancy: int = MiB(4)
    stack: int = -1
    fsize: int = MiB(64)
    def tl(self, t: int):
        return t > self.time
    def ml(self, n: int):
        return n > self.memory
    def cmdline(self):
        return (self.time+self.time_redundancy, self.memory+self.memory_redundancy, self.memory+self.memory_redundancy if self.stack is None else self.stack, self.fsize)
@ModelAliasWrapper({
    "time": "limit.time",
    "time_redundancy": "limit.time_redundancy",
    "memory": "limit.memory",
    "memory_redundancy": "limit.memory_redundancy",
    "stack": "limit.stack",
    "fsize": "limit.fsize",
})
@ModelDotWrapper()
class TestConf(Model):
    _method = {
        "limit": ModelTransformToModelWrapper(Limit, True, True),
    }
    limit: Limit = Limit(record_extra=True, record_invalid=True)
    keep: bool = False
class JudgeConf(Model):
    class _CheckerConf(Model):
        _method = {
            "limit": ModelTransformToModelWrapper(Limit, True, True),
        }
        limit: Limit = Limit(record_extra=True, record_invalid=True)
        safe: bool = False
        lang: str = "c++14:O2"
    class _InteractorConf(Model):
        safe: bool = False
        lang: str = "c++14:O2"
    _method = {
        "checker_conf": ModelTransformToModelWrapper(_CheckerConf, True, True),
        "interactor_conf": ModelTransformToModelWrapper(_InteractorConf, True, True),
    }
    name: str = None
    checker: Program | str | None = None
    checker_backup: str = None
    checker_conf: _CheckerConf = _CheckerConf(record_extra=True, record_invalid=True)
    interactor: Program | str | None = None
    interactor_backup: str = None
    interactor_conf: _InteractorConf = _InteractorConf(record_extra=True, record_invalid=True)
    graders: list[str] = []
    headers: list[str] = []
    additional: list[str] = []
    retry: int = 0
def _read_conf(path: str, /):
    with stdopen(path) as file:
        try:
            data = json5.load(file)
        except json.JSONDecodeError as err:
            error(err, True)
            return
    if isinstance(data, dict):
        return data
    error(f"测试点配置文件 {repr(path)} 无效：数据类型不是字典。", True)
def _check_limit(path: str, lim: Limit, /, _prompt: str = "测试点配置文件"):
    # 注意：此函数假定默认值是合理的
    if lim.time <= msec(10):
        warning(f"{_prompt} {repr(path)} 给出的时间限制 {lim.time} ({ftime(lim.time)}) 不合理", True)
    if lim.memory <= MiB(10):
        warning(f"{_prompt} {repr(path)} 给出的空间限制 {lim.memory} ({fmemory(lim.memory)}) 不合理", True)
    if lim.stack != -1 and lim.stack <= MiB(10):
        warning(f"{_prompt} {repr(path)} 给出的栈空间限制 {lim.stack} ({fmemory(lim.stack)}) 不合理", True)
    if lim.fsize <= MiB(1):
        warning(f"{_prompt} {repr(path)} 给出的文件 IO 量限制 {lim.stack} ({fmemory(lim.stack)}) 不合理", True)
def read_test_conf(path: str, /):
    if (data := _read_conf(path)) is None:
        return
    ret = TestConf.from_dict(data, True, True)
    for key, val in ret._record_extra:
        warning(f"测试点配置文件 {repr(path)} 中有冗余的项目 {key} = {repr(val)}", True)
    for key, val in ret._record_invalid:
        error(f"测试点配置文件 {repr(path)} 中有无法解析的项目 {key} = {repr(val)}", True)
    from . import userconf
    if userconf.UserWarn.warn_limit:
        _check_limit(path, ret.limit)
    return ret
def read_judge_conf(path: str, /):
    if (data := _read_conf(path)) is None:
        return
    ret = JudgeConf.from_dict(data, True, True)
    for key, val in ret.get_extra_recursive():
        warning(f"评测配置文件 {repr(path)} 中有冗余的项目 {key} = {repr(val)}", True)
    for key, val in ret.get_invalid_recursive():
        error(f"评测配置文件 {repr(path)} 中有无法解析的项目 {key} = {repr(val)}", True)
    from . import userconf
    if userconf.UserWarn.warn_checker_limit:
        _check_limit(path, ret.checker_conf.limit)
    return ret
class Verdict():
    __slots__ = ("verdict", "tm", "mem", "stat", "msg", "score")
    def __init__(self, verdict: str = "", tm: int = 0, mem: int = 0, stat: int = 0, msg: str = "", score: decimal.Decimal = None):
        self.verdict = verdict
        self.tm = tm
        self.mem = mem
        self.stat = stat
        self.msg = msg
        self.score = score
    def __repr__(self):
        return f"Verdict({self.verdict}, {ftime(self.tm)}, {fmemory(self.mem)}, stat={self.stat}, msg={repr(self.msg)})"
class Test():
    __slots__ = ("tests", "conf", "result")
    def __init__(self, tests: list[tuple[str, str]] = None, conf: TestConf = None):
        self.tests = [] if tests is None else tests
        self.conf = TestConf() if conf is None else conf
        self.result: list[Verdict] = []

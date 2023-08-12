"""Module for creation of `NewType` in Python, currently, only works for `str` and `int`."""

from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary, WeakValueDictionary, ref

HAS_PANDAS = False
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    pass

if TYPE_CHECKING:
    from typing import Any, Callable, Dict, List, NoReturn, Optional, Tuple, Type, TypeVar, Union
    from weakref import ReferenceType

    Self = TypeVar("Self")
    Arg = TypeVar("Arg")
    VarArgs, VarArgsMayIncludeSelf, KwArgs = Tuple[Arg,
                                                   ...], Tuple[Union[Self, Arg], ...], Dict[Arg, Any]
    AnyCallable = Callable[[VarArgs, KwArgs], Any]
    SetAttrFunc = Callable[[Self, str], None]
    AnyObjectMethod = Callable[[Self, VarArgs, KwArgs], Optional[Any]]
    AnyObjectMethodMightRaise = Callable[[
        Self, VarArgs, KwArgs], Union[Any, NoReturn, None]]
    DeletedObjectMethod = Callable[[Self, VarArgs, KwArgs], NoReturn]
    NewTypeClassMethod = Callable[[Type, Arg, VarArgs], Self]

    class NewTypeType:
        __newtype__: NewTypeClassMethod

    class NewTypeConduitType:
        __supertype__: ReferenceType[Type[Any]]
        __thisclass__: ReferenceType[Type[Any]]


def copy_slots_dict(new: "object", old: "object") -> "Tuple[object, object]":
    for var in vars(old):
        object.__setattr__(new, var, object.__getattribute__(old, var))
    return new, old


def is_meth_dunder(meth_name: "str") -> "bool":
    return meth_name.startswith("__") and meth_name.endswith("__")


def wrap_meths(cls: "NewTypeType", supertype: "Type[Any]"):
    mro: "Tuple[Type, ...]" = cls.__mro__[:-1]

    def outer(meth: "AnyObjectMethod") -> "AnyObjectMethod":
        def inner(
            *args: "VarArgsMayIncludeSelf",
                **kwargs: "KwArgs") -> "AnyObjectMethodMightRaise":
            v = meth(*args, **kwargs)
            if isinstance(v, bool):
                return v
            if v is None and isinstance(args[0], supertype):
                cls.__newtype__(args[0])  # AnyObjectMethodMightRaise
            if isinstance(v, mro):
                return cls(v)
            return v
        if not hasattr(cls, "__setattr__"):
            cls.__setattr__ = inner
        return inner
    return outer


def delete_impl(msg: "str" = "") -> "DeletedObjectMethod":
    def delete_impl_inner(*_: "VarArgs", **__: "KwArgs") -> "NoReturn":
        raise NotImplementedError(
            f"This implementation is not implemented or deleted{', ' + msg if msg else ''}")
    return delete_impl_inner


def get_meths_to_wrap(meth_name: "str") -> "bool":
    __EXCLUDED_DUNDERS__ = ("__getattribute__", "__new__", "__repr__", "__init__", "__str__")  # noqa: N806
    return meth_name not in __EXCLUDED_DUNDERS__


class NewType:

    _cached_conduittypes: "Dict[ReferenceType[Type[Any]], NewTypeConduitType]" = WeakKeyDictionary(
    )
    _cached_newtypes: "Dict[Tuple[str, Tuple[Type[Any], ...], Dict[str, Any]], NewTypeType]" = {
    }

    @staticmethod
    def filter_onetype_from_bases(
            bases: "Tuple[Type[Any], ...]",
            to_filter: "Type[Any]") -> "Tuple[Type[Any], ...]":
        return tuple(filter(lambda b: b is not to_filter, bases))

    def __new__(cls, supertype: "Type[Any]") -> "NewTypeType":
        if supertype in cls._cached_conduittypes:
            return cls._cached_conduittypes[supertype]
        conduittype: "NewTypeConduitType" = type(
            cls.__name__,
            (supertype, *cls.__bases__[:-1]),
            dict(cls.__dict__))
        conduittype.__supertype__ = ref(supertype)
        conduittype.__new__ = cls.__newtype_new__
        conduittype.__thisclass__ = ref(conduittype)
        cls._cached_conduittypes[supertype] = conduittype
        return cls._cached_conduittypes[supertype]

    def __newtype_new__(cls: "Union[NewTypeType, NewTypeConduitType, NewType]", val: "Any", *args: "VarArgs", **kwargs: "KwArgs") -> "NewTypeType":   # noqa: N805
        newtype_attrs = dict(cls.__dict__)
        supertype = cls.__supertype__()
        supertype_attrs = dict(supertype.__dict__)
        supertype_attrs = {k: wrap_meths(cls, supertype)(v)
                           for k, v in supertype_attrs.items()
                           if callable(v)
                           and get_meths_to_wrap(k)}
        newtype_attrs.update(supertype_attrs)
        supertype_attrs = {
            k: v for k,
            v in supertype_attrs.items() if not callable(v)}
        newtype_attrs.update(supertype_attrs)
        newtype_attrs.update({"__dict__": {}, "__supertype__": ref(
            supertype), "_cached_newtypes": cls._cached_newtypes})
        newtype_bases = (
            *cls.filter_onetype_from_bases(
                cls.__bases__,
                cls.__thisclass__()),
            supertype)  # supertype must be last
        if cls.__name__ in cls._cached_newtypes:
            cls = cls._cached_newtypes[cls.__name__]
        else:
            cls = type(cls.__name__, newtype_bases, newtype_attrs)
            cls._cached_newtypes[cls.__name__] = cls
        if supertype.__new__ is object.__new__:
            inst = supertype.__new__(cls)
            old_inst = cls.__newtype__(val, *args, **kwargs)
            inst, _ = copy_slots_dict(new=inst, old=old_inst)
        else:
            inst: "supertype" = supertype.__new__(
                cls, cls.__newtype__(val, *args, **kwargs))
        if hasattr(cls, "__init__") and cls.__init__ != supertype.__init__:
            inst.__init__(val, *args, **kwargs)
        elif supertype in (list, set, dict, tuple):
            supertype.__init__(inst, val)
        return inst

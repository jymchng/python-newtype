import logging
from typing import TYPE_CHECKING, cast
from weakref import WeakKeyDictionary, WeakValueDictionary, ref

logger = logging.getLogger("newtype")


if TYPE_CHECKING:
    from typing import (
        Any,
        Callable,
        ClassVar,
        Dict,
        NoReturn,
        Optional,
        Tuple,
        Type,
        TypeAlias,
        Union,
        cast,
        Protocol,
    )
    from weakref import ReferenceType
    from typing_extensions import Self, ParamSpecArgs, ParamSpecKwargs

    AnyCallable: TypeAlias = Callable[..., Any]
    SuperType = Any

    class ConduitType(Protocol):
        __supertype__: ClassVar[ReferenceType[SuperType]]
        __conduittype__: ClassVar[ReferenceType["ConduitType"]]

    class NewType(Protocol):
        __newtype__: AnyCallable
        __supertype__: ClassVar[ReferenceType[SuperType]]
        __conduittype__: ClassVar[ReferenceType[ConduitType]]
        _cached_conduittypes: ClassVar[Dict[ReferenceType[Type[Any]], Type[ConduitType]]]
        _cached_newtypes: ClassVar[Dict[Tuple[str, Tuple[Type[Any], ...], Dict[str, Any]], "Type[NewType]"]]
        

BUILTIN_TYPES = (
    int,
    float,
    complex,
    str,
    bool,
    bytes,
    bytearray,
    memoryview,
    list,
    tuple,
    set,
    frozenset,
    dict,
    type(None),
    type,
    object,
)

WARNING_MSG = (
    "Creating newtypes of supertypes that are not in Python's built-in types "
    "can lead to hard-to-debug behaviors for the newtypes. It's recommended to stick to "
    "creating newtypes based on simple built-in types such as int, float, str, etc."
    )

class NewTypeWarning(UserWarning):
    pass

def warn_about_newtypes():
    import warnings
    warnings.warn(WARNING_MSG, NewTypeWarning)  # noqa: B028


def copy_slots_dict(new: "object", old: "object") -> "Tuple[object, object]":
    for var in vars(old):
        object.__setattr__(new, var, object.__getattribute__(old, var))
    return new, old


def is_meth_dunder(meth_name: "str") -> "bool":
    return meth_name.startswith("__") and meth_name.endswith("__")


def wrap_meths(cls: "Type[NewType]", supertype: "Type[SuperType]"):
    def outer(meth: "AnyCallable") -> "AnyCallable":
        def inner(
                *args: "ParamSpecArgs",
                    **kwargs: "ParamSpecKwargs") -> "Union[AnyCallable, Any]":
                v = meth(*args, **kwargs)
                if isinstance(v, bool):
                    return v
                if (v is None and isinstance(args[0], supertype)) or (meth.__name__ == "__setattr__"):
                    cls.__newtype__(args[0])  # AnyObjectMethodMightRaise
                if type(v) == supertype:
                    return cls(v)
                return v
        if not hasattr(cls, "__setattr__"):
            inner = cast("Callable[[object, str, Any], None]", inner)
            cls.__setattr__ = inner
        return inner
    return outer


def delete_impl(msg: "str" = "") -> "AnyCallable":
    def delete_impl_inner(*_: "ParamSpecArgs", **__: "ParamSpecKwargs") -> "NoReturn":
        raise NotImplementedError(
            f"This implementation is not implemented or deleted{', ' + msg if msg else ''}")
    return delete_impl_inner


def get_meths_to_wrap(meth_name: "str") -> "bool":
    __EXCLUDED_DUNDERS__ = ("__getattribute__", "__new__", "__repr__", "__init__", "__str__")  # noqa: N806
    return meth_name not in __EXCLUDED_DUNDERS__


class ConduitType:  # noqa: F811

    _cached_conduittypes: "WeakKeyDictionary[ReferenceType[SuperType], ConduitType]" = WeakKeyDictionary()
    _cached_newtypes: "WeakValueDictionary[Tuple[str, Tuple[Type[Any], ...], Dict[str, Any]], NewType]" = WeakValueDictionary()

    @staticmethod
    def filter_onetype_from_bases(
            bases: "Tuple[Type[Any], ...]",
            to_filter: "Type[Any]") -> "Tuple[Type[Any], ...]":
        return tuple(filter(lambda b: b is not to_filter, bases))

    def __new__(cls: "Type[ConduitType]", supertype: "Type[SuperType]") -> "Type[ConduitType]":
        if supertype not in BUILTIN_TYPES:
            warn_about_newtypes()
        if supertype in cls._cached_conduittypes:
            return cls._cached_conduittypes[supertype]
        conduittype = cast("ConduitType", type(
            cls.__name__,
            (supertype, *cls.__bases__[:-1]),
            dict(cls.__dict__)))
        conduittype.__supertype__ = ref(supertype)
        conduittype.__new__ = cls.__newtype_new__
        conduittype.__conduittype__ = ref(conduittype)
        cls._cached_conduittypes[supertype] = conduittype
        return cls._cached_conduittypes[supertype]

    def __newtype_new__(cls: "Type[NewType]", val: "Any", *args: "ParamSpecArgs", **kwargs: "ParamSpecKwargs") -> "NewType": # noqa: N805
        supertype = cast("Type[SuperType]", cls.__supertype__())
        if cls.__name__ in cls._cached_newtypes:
            cls = cls._cached_newtypes[cls.__name__]
        else:
            newtype_attrs = dict(cls.__dict__)
            supertype_attrs = cast("Dict[str, Any]", dict(supertype.__dict__))
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
            newtype_bases = cast("Tuple[Union[Type[Any], SuperType], ...]", (
                *cls.filter_onetype_from_bases(
                    cls.__bases__,
                    cls.__conduittype__()),
                supertype))  # supertype must be last
            cls = cast("Type[NewType]", type(cls.__name__, newtype_bases, newtype_attrs))
            cls._cached_newtypes[cls.__name__] = cls
        if supertype.__new__ is object.__new__:
            inst = supertype.__new__(cls)
            old_inst = cls.__newtype__(val, *args, **kwargs)
            inst, _ = cast("Tuple[NewType, SuperType]", copy_slots_dict(new=inst, old=old_inst))
        else:
            inst = cast("NewType", supertype.__new__(
                cls, cls.__newtype__(val, *args, **kwargs)))
        if hasattr(cls, "__init__") and cls.__init__ != supertype.__init__:
            inst.__init__(val, *args, **kwargs)
        elif supertype in (list, set, dict, tuple):
            supertype.__init__(inst, val)
        return inst

NewType = ConduitType

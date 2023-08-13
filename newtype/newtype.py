from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary, WeakValueDictionary, ref

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
    )
    from typing import NewType as NewType_fn
    from weakref import ReferenceType

    MetaType: TypeAlias = type
    SuperType = NewType_fn("SuperType", MetaType)
    NewType = NewType_fn("NewType", SuperType)
    Self: TypeAlias = Any
    Arg: TypeAlias = Any
    VarArgs: TypeAlias = Tuple[Any, ...]
    KwArgs: TypeAlias = Dict[str, Any]
    VarArgsMayIncludeSelf: TypeAlias = Tuple[Union[Self, Arg], ...]
    AnyCallable: TypeAlias = Callable[[VarArgs, KwArgs], Any]
    SetAttrFunc: TypeAlias = Callable[[Self, str], None]
    AnyObjectMethod: TypeAlias = Callable[[Self, VarArgs, KwArgs], Optional[Any]]
    AnyObjectMethodMightRaise: TypeAlias = Callable[[
    Self, VarArgs, KwArgs], Union[Any, NoReturn, None]]
    DeletedObjectMethod: TypeAlias = Callable[[Self, VarArgs, KwArgs], NoReturn]
    NewTypeClassMethod: TypeAlias = Union[Callable[[Type[Self], SuperType, VarArgs, KwArgs], NoReturn], Callable[[Type[Self], SuperType, VarArgs, KwArgs], SuperType]]

    class ConduitType:
        __supertype__: ReferenceType[Type[Any]]
        __conduittype__: ReferenceType[Type[Any]]

    class NewType:
        __newtype__: NewTypeClassMethod
        __supertype__: ClassVar[ReferenceType[Type[Any]]]
        __conduittype__: ClassVar[ReferenceType[Type[Any]]]
        _cached_conduittypes: ClassVar[Dict[ReferenceType[Type[Any]], ConduitType]]
        _cached_newtypes: ClassVar[Dict[Tuple[str, Tuple[Type[Any], ...], Dict[str, Any]], NewType]]


def copy_slots_dict(new: "object", old: "object") -> "Tuple[object, object]":
    for var in vars(old):
        object.__setattr__(new, var, object.__getattribute__(old, var))
    return new, old


def is_meth_dunder(meth_name: "str") -> "bool":
    return meth_name.startswith("__") and meth_name.endswith("__")


def wrap_meths(cls: "NewType", supertype: "SuperType"):
    mro: "Tuple[Type[Any], ...]" = cls.__mro__[:-1]

    def outer(meth: "AnyObjectMethod") -> "AnyObjectMethod":
        def inner(
            *args: "VarArgsMayIncludeSelf",
                **kwargs: "KwArgs") -> "Union[AnyObjectMethodMightRaise, Any]":
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


class ConduitType:  # noqa: F811

    _cached_conduittypes: "WeakKeyDictionary[ReferenceType[Type[Any]], ConduitType]" = WeakKeyDictionary()
    _cached_newtypes: "WeakValueDictionary[Tuple[str, Tuple[Type[Any], ...], Dict[str, Any]], NewType]" = WeakValueDictionary()

    @staticmethod
    def filter_onetype_from_bases(
            bases: "Tuple[Type[Any], ...]",
            to_filter: "Type[Any]") -> "Tuple[Type[Any], ...]":
        return tuple(filter(lambda b: b is not to_filter, bases))

    def __new__(cls: "Type[ConduitType]", supertype: "SuperType") -> "NewType":
        if supertype in cls._cached_conduittypes:
            return cls._cached_conduittypes[supertype]
        conduittype = type(
            cls.__name__,
            (supertype, *cls.__bases__[:-1]),
            dict(cls.__dict__))
        conduittype.__supertype__ = ref(supertype)
        conduittype.__new__ = cls.__newtype_new__
        conduittype.__conduittype__ = ref(conduittype)
        cls._cached_conduittypes[supertype] = conduittype
        return cls._cached_conduittypes[supertype]

    def __newtype_new__(cls: "NewType", val: "Any", *args: "VarArgs", **kwargs: "KwArgs") -> "Any": # noqa: N805
        supertype = cls.__supertype__()
        if cls.__name__ in cls._cached_newtypes:
            cls = cls._cached_newtypes[cls.__name__]
        else:
            newtype_attrs = dict(cls.__dict__)
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
                    cls.__conduittype__()),
                supertype)  # supertype must be last
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

NewType = ConduitType

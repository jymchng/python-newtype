import random
import re
from enum import Enum, auto
from itertools import combinations_with_replacement
from typing import Iterable
from weakref import WeakKeyDictionary, WeakValueDictionary

import numpy as np
import pandas as pd
import pytest
from pydantic import BaseModel, Field, ValidationError

from newtype import NewType

random.seed(42)


class NRIC(NewType(str)):

    def __init__(self, val: "str"):
        self._prefix = val[0]
        self._suffix = val[-1]
        self._digits = val[1:-1]

    def __str__(self):
        return f"NRIC(Prefix:{self._prefix}, Suffix:{self._suffix}, Digits:{self._digits})"

    @classmethod
    def __newtype__(cls, nric: "str") -> "NRIC":
        alpha_ST = ("J", "Z", "I", "H", "G", "F", "E", "D", "C", "B", "A")
        alpha_GF = ("X", "W", "U", "T", "R", "Q", "P", "N", "M", "L", "K")
        alpha_M = ("K", "L", "J", "N", "P", "Q", "R", "T", "U", "W", "X")
        assert len(
            str(nric)) == 9, f"NRIC length must be 9, it is `{len(nric)}`"
        assert nric[0] in ["S", "T", "G", "F",
                           "M"], f"NRIC Prefix must be in ['S', 'T', 'G', 'F'], it is `{nric[0]}`"
        weights = [2, 7, 6, 5, 4, 3, 2]
        digits = nric[1:-1]
        weighted_sum = sum(int(digits[i]) * weights[i] for i in range(7))
        offset = 0
        if nric[0] in ["T", "G"]:
            offset = 4
        if nric[0] == "M":
            offset = 3
        expected_checksum = (offset + weighted_sum) % 11
        if nric[0] in ["S", "T"]:
            assert alpha_ST[expected_checksum] == nric[8], "Checksum is not right"
        elif nric[0] == "M":
            expected_checksum = 10 - expected_checksum
            assert alpha_M[expected_checksum] == nric[8]
        else:
            assert alpha_GF[expected_checksum] == nric[8]
        return nric


def test_nric():
    nric_one = NRIC("S1234567D")
    NRIC("M5398242L")
    NRIC("F5611427X")
    nric_one.hello = "bye"
    assert nric_one.hello == "bye"
    assert nric_one._prefix == "S"
    assert nric_one._digits == "1234567"
    assert nric_one._suffix == "D"
    assert nric_one.__supertype__() == str
    assert type(nric_one).__name__ == NRIC.__name__

    with pytest.raises(Exception):  # noqa: B017
        nric_one = nric_one.replace("S", "Q")

    with pytest.raises(Exception):  # noqa: B017
        nric_one = nric_one + "1234567"


class PositiveInt(NewType(int)):

    @classmethod
    def __newtype__(cls, positive_int: int):
        assert positive_int > 0, f"`PositiveInt` object must be positive, but the passed in value is {positive_int}"
        return positive_int

    @classmethod
    def __get_validators__(cls):
        yield cls.__newtype__


def test_positive_int():

    positive_int_one = PositiveInt(5)

    assert positive_int_one.__supertype__(
    ) == int, "positive_int_one.__supertype__() == int FAILED"
    assert type(
        positive_int_one).__name__ == PositiveInt.__name__, f"type(positive_int_one)={type(positive_int_one)}"

    with pytest.raises(AssertionError):
        positive_int_one - 10


class UserAccount(BaseModel):
    amount: PositiveInt


try:
    user_account = UserAccount(amount=-75)
except ValidationError as err:
    print(err)


class MnemonicsLength:
    _cache = WeakValueDictionary()

    def __new__(cls, word_length: "int"):
        if word_length in cls._cache:
            return cls._cache[word_length]
        cls._cache[word_length] = type(
            cls.__name__, (), {
                "word_length": word_length})
        return cls._cache[word_length]


class BaseMnemonics(NewType(str)):
    word_length: int

    @classmethod
    def __get_validators__(cls):
        yield cls.__newtype__

    @classmethod
    def __newtype__(cls, val: "str") -> "Mnemonics":
        if len(val.split(" ")) != cls.word_length:
            raise Exception(f"Mnemonics is supposed to have `word_length`={cls.word_length} but it has `word_length`={len(val.split(' '))}")  # noqa: TRY002
        return val


class Mnemonics:
    _cache = WeakValueDictionary()
    __new__ = NotImplementedError

    def __class_getitem__(cls, index) -> "Mnemonics":
        assert isinstance(
            index, int), f"`index` must be of type `int`, it is of type `{type(index)}`"
        if index in cls._cache:
            return cls._cache[index]
        cls._cache[index] = type(
            cls.__name__, (BaseMnemonics, MnemonicsLength(index)), {})
        return cls._cache[index]


class Account(BaseModel):
    mnemonics: Mnemonics[2]


def test_mnemonics_pydantic():
    Account(mnemonics="hello bye")
    with pytest.raises(Exception):
        Account(mnemonics="hello bye hey")


def test_mnemonics():
    mnemonics_one = Mnemonics[2]("hello bye")

    with pytest.raises(Exception):
        mnemonics_one + " hey"

    mnemonics_one = mnemonics_one.replace("hello", "hey")
    assert mnemonics_one == "hey bye"

    with pytest.raises(Exception):
        mnemonics_one.replace("bye", "hey you")

    with pytest.raises(Exception):
        mnemonics_one.replace("bye", "hey you how")
    assert type(
        mnemonics_one).__name__ == Mnemonics.__name__, f"type(mnemonics_one)={type(mnemonics_one)}"


class MyType:
    A = "A"

    def __init__(self, a, b):
        self._a = a
        self._b = b

    @classmethod
    def get_a(cls):
        return cls.A

    def add(self):
        print("type(self._a + self._b)", type(self._a + self._b))
        return self._a + self._b

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        self._a += 10


class MyNewType(NewType(MyType)):

    @classmethod
    def __newtype__(cls, val, threshold=9):
        assert val.add() < threshold, f"{val.add()}"
        return val


def test_my_type():
    my_type = MyType(5, 3)
    my_new_type = MyNewType(my_type)
    assert my_new_type.A == "A", f"my_new_type.A != 'A'; {my_new_type.A == 'A'}"
    assert type(
        my_new_type).__name__ == MyNewType.__name__, f"type(my_new_type)={type(my_new_type)}"
    assert my_new_type.add(
    ) == 8, f"my_new_type.add() != 8 but equals to {my_new_type.add()}"
    # try:
    #     with my_new_type as ok:
    #         assert ok._a == my_new_type._a, f"{ok._a == my_new_type._a}; {ok._a} == {my_new_type._a}"
    #         assert ok == my_new_type, f"ok={ok}, my_new_type={my_new_type}"
    # except Exception as err:
    #     print(err, type(err))
    assert MyNewType.__newtype__(my_new_type)

# import numpy as np


# class VecDim:
#     _cache = WeakValueDictionary()

#     def __new__(cls, dimension: "int"):
#         if dimension in cls._cache:
#             return cls._cache[dimension]
#         cls._cache[dimension] = type(cls.__name__, (), {"dimension": dimension})
#         return cls._cache[dimension]


# class BaseVector(NewType(np.ndarray)):
#     dimension: int

#     def __init__(self, val):
#         print("val ", val)
#         np.ndarray.__init__(val)

#     @classmethod
#     def __get_validators__(cls):
#         yield cls.__newtype__

#     @classmethod
#     def __newtype__(cls, val: np.ndarray):
#         print(val.shape, (cls.dimension,))
#         if val.shape[0] != cls.dimension:
#             raise Exception(f"BaseVector is supposed to have `dimension`={cls.dimension} but it has `dimension`={val.shape[0]}")
#         return val

# class D_DimensionalVector:
#     _cache = WeakValueDictionary()
#     __new__ = delete_impl(msg="consider using D_DimensionalVector[dimension], e.g. `D_DimensionalVector[3]`")

#     def __class_getitem__(cls, dimension):
#         assert isinstance(dimension, int), f"`index` must be of type `int`, it is of type `{type(dimension)}`"
#         if dimension in cls._cache:
#             return cls._cache[dimension]
#         cls._cache[dimension] = type(cls.__name__, (BaseVector, VecDim(dimension=dimension)), {})
#         return cls._cache[dimension]

#     def __str__(self):
#         return f"Vec({self})"

# d3_vec = D_DimensionalVector[3](np.array([1,2,3]))
# print(d3_vec)

class BaseWithMaximumSizedList(NewType(list)):

    def __init__(self, val: "object"):
        super().__init__(val)
        self._id = random.randint(0, 1000)

    def inner_product(self: "Iterable", other: "Iterable"):
        assert len(self) == len(other)
        sum = 0
        for i, j in zip(self, other):
            sum += (i * j)
        return sum

    @classmethod
    def __newtype__(cls, val: "list") -> "BaseWithMaximumSizedList":
        assert len(
            val) <= cls.size, f"`WithMaximumSizedList` must have a length of {cls.size} but it has length of {len(val)}"
        return val


class Size:
    _cache = {}

    def __new__(cls, size: "int") -> "Size":
        if size in cls._cache:
            print("size in cls._cache: ", size in cls._cache)
            return cls._cache[size]
        cls._cache[size] = type(cls.__name__, (), {"size": size})
        return cls._cache[size]


class WithMaximumSizeList:

    def __class_getitem__(cls, size: "int") -> "WithMaximumSizeList":
        print("size: ", size, "type(size): ", type(size))
        return type(
            cls.__name__ + "_" + str(size),
            (BaseWithMaximumSizedList,
             Size(size)),
            dict(
                BaseWithMaximumSizedList.__dict__))


def test_fixed_size_list():
    sized_list_one = WithMaximumSizeList[3]([1, 2, 3])
    sized_list_one[0] = 5
    assert sized_list_one[0] == 5
    assert sized_list_one[1] == 2
    assert sized_list_one[2] == 3

    with pytest.raises(Exception):
        sized_list_one.append(4)
    inner_pdt = WithMaximumSizeList[3]([1, 2, 3]).inner_product([1, 2, 3])
    # 1*1 (=1) + 2*2 (=4) + 3*3 (=9) = 14 (1+4=5; 5+9=14)
    assert inner_pdt == 14
    assert sized_list_one._id == 654

    sized_list_one = WithMaximumSizeList[3]([1])
    sized_list_one.extend([2, 3])
    assert sized_list_one[0] == 1
    assert sized_list_one[1] == 2
    assert sized_list_one[2] == 3
    with pytest.raises(Exception):
        sized_list_one.append(4)


class NewDataFrame(NewType(pd.DataFrame)):

    @classmethod
    def __newtype__(cls, val: "pd.DataFrame") -> "NewDataFrame":
        assert val.shape == (3, 3)
        return val


def test_new_dataframe():
    df = pd.DataFrame([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    new_df = NewDataFrame(df)
    assert df.equals(new_df) and new_df.equals(df)
    with pytest.raises(Exception):
        df = pd.DataFrame([[1, 2, 3], [4, 6]])
        new_df = NewDataFrame(df)


class ObjectID(NewType(int)):

    @classmethod
    def __newtype__(cls, val: "int") -> "ObjectID":
        assert val >= 100000
        assert val <= 999999
        return val


def test_objectid():
    id = ObjectID(123456)
    assert id == 123456
    id += 1
    assert id == 123457
    id += 10
    assert id == 123467
    id = ObjectID(999999)
    with pytest.raises(AssertionError):
        id += 1


class IntLessThanTen(NewType(int)):
    TEN = 10

    @classmethod
    def __newtype__(cls, val: "int") -> "ObjectID":
        assert val <= cls.TEN
        return val


class IntLessThanThree(NewType(int)):
    THREE = 3

    @classmethod
    def __newtype__(cls, val: "int") -> "ObjectID":
        assert val <= cls.THREE
        return val


def test_withmaxsizelist_and_objectid():
    li = WithMaximumSizeList[IntLessThanTen(5)]([1, 2, 3, 4, 5])
    assert li[0] == 1
    assert li[1] == 2
    assert li[2] == 3
    assert li[3] == 4
    assert li[4] == 5

    with pytest.raises(AssertionError):
        li.append(6)

    with pytest.raises(AssertionError):
        li.extend([6, 7])

    li = WithMaximumSizeList[IntLessThanThree(3)]([1, 2, 3])
    assert li[0] == 1
    assert li[1] == 2
    assert li[2] == 3

    with pytest.raises(AssertionError):
        li.append(4)

    with pytest.raises(AssertionError):
        li.extend([4, 5])


# def test_lessthanthreeintenum():
#     class LessThanThreeIntEnum(IntLessThanThree, Enum):
#         ONE = auto()
#         TWO = auto()
#         THREE = auto()

#     assert LessThanThreeIntEnum.ONE == 1
#     assert LessThanThreeIntEnum.TWO == 2
#     assert LessThanThreeIntEnum.THREE == 3

#     with pytest.raises(AssertionError):
#         class LessThanThreeIntEnum(IntLessThanThree, Enum):
#             ONE = auto()
#             TWO = auto()
#             THREE = auto()
#             FOUR = auto()

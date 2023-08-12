<div align="center"><h1>newtype</h1></div>

<div align="center">

![](assets/python-newtype-logo.png)

</div>

Simplifies the creation of custom types using the `newtype` pattern. This pattern allows you to extend and customize existing types, creating tailored data structures with specialized behaviors.

[![License](https://img.shields.io/pypi/l/python-newtype.svg)](https://github.com/jymchng/python-newtype/blob/main/LICENSE) [![Python Version](https://img.shields.io/badge/%3E=python-3.8-blue.svg)](https://img.shields.io/badge/%3E=python-3.8-blue.svg)


## Features

- Streamlined type creation using the `newtype` pattern.
- Customization of behaviors and attributes for new types.
- Integration with Python's type system and conventions.
- Efficient base type manipulation without altering core properties.

## Installation

You can install the `newtype` package using pip:

```bash
python -m pip install -U git+https://git@github.com/jymchng/python-newtype
```

Or using poetry:
```bash
poetry add git+https://git@github.com/jymchng/python-newtype
```

# Usage

Import the NewType class from the package.
```python
from newtype import NewType
```

Create a new type by inheriting from NewType and specifying the desired base type.

Customize the new type by extending and modifying its behavior as needed.

Utilize the new type in your code to encapsulate specific data structures and logic.

## Examples

### Mnemonics

`Mnemonics` type introduces the concept of mnemonic phrases with specific word lengths. It includes two primary classes:

`MnemonicsLength`: A class that represents the length of a mnemonic phrase. It uses a cache to efficiently store and retrieve instances for different lengths.

`BaseMnemonics`: A base class that defines the core behavior of mnemonic phrases. It checks if a given mnemonic phrase has the correct number of words according to its word length.

`Mnemonics`: A utility class that allows creating mnemonic phrase types of various lengths. It uses the `BaseMnemonics` class and the `MnemonicsLength` class to dynamically generate generic classes representing specific mnemonic lengths.

#### Codes

```python
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
```

#### Usage

1. Use with `pydantic`
   
The example demonstrates the integration of Mnemonics with the Pydantic package. The code defines an Account Pydantic model with a field named mnemonics of type Mnemonics[2], indicating that the mnemonic phrase should have a length of two words. The model is then used to validate mnemonic phrases.

```python
from pydantic import BaseModel
import pytest

class Account(BaseModel):
    mnemonics: Mnemonics[2]

def test_mnemonics_pydantic():
    Account(mnemonics="hello bye") # ok

    with pytest.raises(Exception): # fails
        Account(mnemonics="hello bye hey")
```

2. Normal usage

```python
import pytest

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
```

### Blockchain Addresses

A fuller example of using `NewType` for creation of new type of in-built `str` that preserves the invariance of the type.

``` python
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import web3

from newtype import NewType

if TYPE_CHECKING:
    from typing import Type


class BlockchainAddress(NewType(str), ABC):

    @classmethod
    @abstractmethod
    def __newtype__(cls, val: "str") -> "Type[BlockchainAddress]":
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def _validate_address(val: " str") -> "bool":
        raise NotImplementedError

    @classmethod
    def __get_validators__(cls):
        yield cls.__newtype__


class EthereumAddress(BlockchainAddress):

    @classmethod
    def __newtype__(cls, val: "str") -> "type[EthereumAddress]":
        assert cls._validate_address(
            val), f"val = {val} does not match the regex of `Address`"
        return web3.Web3.to_checksum_address(val)

    def __init__(self, _val: "str"):
        self._is_checksum = True

    @property
    def is_checksum(self):
        return self._is_checksum

    @staticmethod
    def _validate_address(address):
        # Ethereum addresses are 40 hexadecimal characters prefixed with '0x'
        if not re.match(r"^0x[0-9a-fA-F]{40}$", address):
            return False
        return True


class ZkSyncAddress(EthereumAddress):
    ...

```

# Contributing
Contributions are welcome! If you have suggestions, bug reports, or feature requests, please open an issue on the GitHub repository.

# License
This project is licensed under the MIT License.
from __future__ import annotations

import copy
import enum
import types
import typing

import attr

from .scope import Scope
from ..ast import ParameterKind

if typing.TYPE_CHECKING:
    from typing_extensions import Self, TypeGuard

TypeT = typing.TypeVar('TypeT', bound='Atom')
KindT = typing.TypeVar('KindT', bound='AtomKind')


class AtomKind(enum.Enum):
    UNKNOWN = enum.auto()
    TYPE = enum.auto()
    UNION = enum.auto()
    OBJECT = enum.auto()
    BOOL = enum.auto()
    NONE = enum.auto()
    ELLIPSIS = enum.auto()
    STRING = enum.auto()
    BYTES = enum.auto()
    INTEGER = enum.auto()
    FLOAT = enum.auto()
    COMPLEX = enum.auto()
    DICT = enum.auto()
    SET = enum.auto()
    TUPLE = enum.auto()
    LIST = enum.auto()
    SLICE = enum.auto()
    MODULE = enum.auto()
    CLASS = enum.auto()
    FUNCTION = enum.auto()
    METHOD = enum.auto()


class AtomFlags(enum.IntFlag):
    NONE = 0
    TYPE = enum.auto()
    IMPLICIT = enum.auto()


@attr.s(slots=True)
class AtomBase(typing.Generic[KindT]):
    """Represents a type or an instance of that type."""

    kind: KindT = attr.ib(init=False, repr=False)
    flags: AtomFlags = attr.ib(kw_only=True, default=AtomFlags.NONE, repr=False)

    def __str__(self) -> str:
        if self.kind in (AtomKind.TYPE, AtomKind.UNION):
            return self.stringify()

        string = self.stringify()
        return f'type{{{string}}}' if self.flags & AtomFlags.TYPE else string

    def stringify(self) -> str:
        raise NotImplementedError

    def copy(self) -> Self:
        return copy.copy(self)

    def is_type(self) -> bool:
        if self.kind in (AtomKind.TYPE, AtomKind.UNION):
            return True

        return self.flags & AtomFlags.TYPE != 0

    def instantiate(self) -> Self:
        if not self.is_type():
            return self

        copy = self.copy()
        copy.flags &= ~AtomFlags.TYPE
        return copy

    def uninstantiate(self) -> Self:
        if self.is_type():
            return self

        copy = self.copy()
        copy.flags |= AtomFlags.TYPE
        return copy

    def synthesize(self) -> typing.Union[Self, TypeAtom]:
        if self.kind is AtomKind.TYPE or not self.is_type():
            return self

        assert isinstance(self, Atom)
        return TypeAtom(self.instantiate())

    def unwrap_as(self, type: typing.Type[TypeT]) -> TypeT:
        assert isinstance(self, type)
        return self


@attr.s(slots=True)
class UnknownAtom(AtomBase[typing.Literal[AtomKind.UNKNOWN]]):
    kind: typing.Literal[AtomKind.UNKNOWN] = attr.ib(init=False, default=AtomKind.UNKNOWN)

    def stringify(self) -> str:
        return 'unknown'


class ErrorCategory(enum.IntEnum):
    SYNTAX_ERROR = enum.auto()
    TYPE_ERROR = enum.auto()


@attr.s(slots=True)
class ErrorAtom(UnknownAtom):
    category: ErrorCategory = attr.ib()
    message: str = attr.ib()


@attr.s(slots=True)
class TypeAtom(AtomBase[typing.Literal[AtomKind.TYPE]]):
    """Represents a reflected version of a Ftype."""

    kind: typing.Literal[AtomKind.TYPE] = attr.ib(init=False, default=AtomKind.TYPE)
    value: typing.Optional[Atom] = attr.ib(default=None)

    def stringify(self) -> str:
        return f'type{{{self.value}}}' if self.value is not None else 'type'


@attr.s(slots=True)
class UnionAtom(AtomBase[typing.Literal[AtomKind.UNION]]):
    kind: typing.Literal[AtomKind.UNION] = attr.ib(init=False, default=AtomKind.UNION)
    values: typing.Optional[typing.List[Atom]] = attr.ib(default=None)

    def stringify(self) -> str:
        if self.values is None:
            return 'union'

        return ' | '.join(str(value) for value in self.values)


@attr.s(slots=True)
class ObjectAtom(AtomBase[typing.Literal[AtomKind.OBJECT]]):
    kind: typing.Literal[AtomKind.OBJECT] = attr.ib(init=False, default=AtomKind.OBJECT)
    value: typing.Optional[Atom] = attr.ib(default=None)

    def stringify(self) -> str:
        return f'{self.value}' if self.value is not None else 'object'


@attr.s(slots=True)
class BoolAtom(AtomBase[typing.Literal[AtomKind.BOOL]]):
    kind: typing.Literal[AtomKind.BOOL] = attr.ib(init=False, default=AtomKind.BOOL)
    value: typing.Optional[bool] = attr.ib(default=None)

    def stringify(self) -> str:
        return f'bool({self.value})' if self.value is not None else 'bool'


@attr.s(slots=True)
class NoneAtom(AtomBase[typing.Literal[AtomKind.NONE]]):
    kind: typing.Literal[AtomKind.NONE] = attr.ib(init=False, default=AtomKind.NONE)
    value: None = attr.ib(default=None)

    def stringify(self) -> str:
        return 'None'


@attr.s(slots=True)
class EllipsisAtom(AtomBase[typing.Literal[AtomKind.ELLIPSIS]]):
    kind: typing.Literal[AtomKind.ELLIPSIS] = attr.ib(init=False, default=AtomKind.ELLIPSIS)
    value: types.EllipsisType = attr.ib(default=types.EllipsisType)

    def stringify(self) -> str:
        return 'Ellipsis'


@attr.s(slots=True)
class StringAtom(AtomBase[typing.Literal[AtomKind.STRING]]):
    kind: typing.Literal[AtomKind.STRING] = attr.ib(init=False, default=AtomKind.STRING)
    value: typing.Optional[str] = attr.ib(default=None)

    def stringify(self) -> str:
        return f'str({self.value!r})' if self.value is not None else 'str'


@attr.s(slots=True)
class IntegerAtom(AtomBase[typing.Literal[AtomKind.INTEGER]]):
    kind: typing.Literal[AtomKind.INTEGER] = attr.ib(init=False, default=AtomKind.INTEGER)
    value: typing.Optional[int] = attr.ib(default=None)

    def stringify(self) -> str:
        return f'int({self.value})' if self.value is not None else 'int'


@attr.s(slots=True)
class FloatAtom(AtomBase[typing.Literal[AtomKind.FLOAT]]):
    kind: typing.Literal[AtomKind.FLOAT] = attr.ib(init=False, default=AtomKind.FLOAT)
    value: typing.Optional[float] = attr.ib(default=None)

    def stringify(self) -> str:
        return f'float({self.value})' if self.value is not None else 'float'


@attr.s(slots=True)
class ComplexAtom(AtomBase[typing.Literal[AtomKind.COMPLEX]]):
    kind: typing.Literal[AtomKind.COMPLEX] = attr.ib(init=False, default=AtomKind.COMPLEX)
    value: typing.Optional[complex] = attr.ib(default=None)

    def stringify(self) -> str:
        if self.value is not None:
            return f'complex({self.value.real}, {self.value.imag})'

        return 'complex'


@attr.s(slots=True)
class DictFields:
    key: Atom = attr.ib()
    value: Atom = attr.ib()


@attr.s(slots=True)
class DictAtom(AtomBase[typing.Literal[AtomKind.DICT]]):
    kind: typing.Literal[AtomKind.DICT] = attr.ib(init=False, default=AtomKind.DICT)
    fields: typing.Optional[DictFields] = attr.ib(default=None)

    def stringify(self) -> str:
        if self.fields is not None:
            return f'{{{self.fields.key}: {self.fields.value}}}'

        return 'dict'

    def get_fields(self) -> DictFields:
        if self.fields is None:
            raise RuntimeError('dict atom is missing fields')

        return self.fields


@attr.s(slots=True)
class SetAtom(AtomBase[typing.Literal[AtomKind.SET]]):
    kind: typing.Literal[AtomKind.SET] = attr.ib(init=False, default=AtomKind.SET)
    value: typing.Optional[Atom] = attr.ib(default=None)

    def stringify(self) -> str:
        return f'{{{self.value}}}' if self.value is None else 'set'


@attr.s(slots=True)
class TupleAtom(AtomBase[typing.Literal[AtomKind.TUPLE]]):
    kind: typing.Literal[AtomKind.TUPLE] = attr.ib(init=False, default=AtomKind.TUPLE)
    values: typing.Optional[typing.List[Atom]] = attr.ib(default=None)

    def stringify(self) -> str:
        if self.values is not None:
            values = ', '.join(str(value) for value in self.values)
            return f'({values},)' if len(self.values) == 1 else f'({values})'

        return 'tuple'


@attr.s(slots=True)
class ListAtom(AtomBase[typing.Literal[AtomKind.LIST]]):
    kind: typing.Literal[AtomKind.LIST] = attr.ib(init=False, default=AtomKind.LIST)
    value: typing.Optional[Atom] = attr.ib(default=None)
    size: typing.Optional[int] = attr.ib(default=None)

    def stringify(self) -> str:
        if self.value is not None:
            return f'[{self.value}, {self.size}]' if self.size is not None else f'[{self.value}]'

        return 'list'


@attr.s(slots=True)
class SliceAtom(AtomBase[typing.Literal[AtomKind.SLICE]]):
    kind: typing.Literal[AtomKind.SLICE] = attr.ib(init=False, default=AtomKind.SLICE)
    start: typing.Optional[Atom] = attr.ib(default=None)
    stop: typing.Optional[Atom] = attr.ib(default=None)
    step: typing.Optional[Atom] = attr.ib(default=None)

    def stringify(self) -> str:
        return f'slice({self.start}, {self.stop}, {self.step})'


@attr.s(kw_only=True, slots=True)
class FunctionParameter:
    name: str = attr.ib()
    annotation: typing.Optional[Atom] = attr.ib()
    kind: ParameterKind = attr.ib()
    default: typing.Optional[Atom] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionFields:
    name: str = attr.ib()
    parameters: typing.List[FunctionParameter] = attr.ib()
    returns: typing.Optional[Atom] = attr.ib()
    scope: typing.Optional[Scope] = attr.ib(default=None)


@attr.s(slots=True)
class FunctionAtom(AtomBase[typing.Literal[AtomKind.FUNCTION]]):
    kind: typing.Literal[AtomKind.FUNCTION] = attr.ib(init=False, default=AtomKind.FUNCTION)
    fields: typing.Optional[FunctionFields] = attr.ib(default=None)

    def stringify(self) -> str:
        if self.fields is not None:
            return f'<function {self.fields.name}>'

        return 'function'

    def get_fields(self) -> FunctionFields:
        if self.fields is None:
            raise RuntimeError('function atom is missing fields')

        return self.fields


@attr.s(slots=True)
class BuiltinFunctionAtom(FunctionAtom):
    function: typing.Callable[..., Atom] = attr.ib(kw_only=True)


@attr.s(kw_only=True, slots=True)
class MethodFields:
    instance: Atom = attr.ib()
    function: FunctionAtom = attr.ib()


@attr.s(slots=True)
class MethodAtom(AtomBase[typing.Literal[AtomKind.METHOD]]):
    kind: typing.Literal[AtomKind.METHOD] = attr.ib(init=False, default=AtomKind.METHOD)
    fields: typing.Optional[MethodFields] = attr.ib(default=None)

    def stringify(self) -> str:
        if self.fields is None:
            return 'method'

        function = self.fields.function
        if function.fields is None:
            return f'<bound method of {self.fields.instance}>'

        return f'<bound method {function.fields.name} of {self.fields.instance}>'

    def get_fields(self) -> MethodFields:
        if self.fields is None:
            raise RuntimeError('method atom is missing fields')

        return self.fields


def is_unknown(atom: Atom) -> TypeGuard[UnknownAtom]:
    if atom.kind is AtomKind.UNION:
        return atom.values is None or any(is_unknown(atom) for atom in atom.values)

    return atom.kind is AtomKind.UNKNOWN


def union(atoms: typing.Iterable[Atom]) -> Atom:
    flattened: typing.List[Atom] = []

    for atom in atoms:
        if atom.kind is AtomKind.UNION:
            if atom.values is None:
                continue

            for value in atom.values:
                if value not in flattened:
                    flattened.append(value)
        else:
            if atom not in flattened:
                flattened.append(atom)

    if len(flattened) == 1:
        return flattened[0]

    return UnionAtom(flattened)


Atom = typing.Union[
    TypeAtom,
    UnionAtom,
    UnknownAtom,
    ObjectAtom,
    BoolAtom,
    NoneAtom,
    EllipsisAtom,
    StringAtom,
    IntegerAtom,
    FloatAtom,
    ComplexAtom,
    DictAtom,
    SetAtom,
    TupleAtom,
    ListAtom,
    SliceAtom,
    FunctionAtom,
    MethodAtom,
]

LiteralAtom = typing.Union[
    BoolAtom,
    StringAtom,
    IntegerAtom,
    FloatAtom,
    ComplexAtom,
]

TYPE = TypeAtom()
UNION = UnionAtom()
UNKNOWN = UnknownAtom()
OBJECT = ObjectAtom()
BOOL = BoolAtom()
NONE = NoneAtom()
ELLIPSIS = EllipsisAtom()
STRING = StringAtom()
INTEGER = IntegerAtom()
FLOAT = FloatAtom()
COMPLEX = ComplexAtom()
DICT = DictAtom()
SET = SetAtom()
TUPLE = TupleAtom()
LIST = ListAtom()
SLICE = SliceAtom()
FUNCTION = FunctionAtom()
METHOD = MethodAtom()


def get_type(atom: TypeT) -> TypeT:
    return atom.uninstantiate()

from __future__ import annotations

import typing
import types
import enum

import attr

from .. import ast


class TypeKind(enum.Enum):
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

    FUNCTION = enum.auto()
    CLASS = enum.auto()

    UNION = enum.auto()


@attr.s(kw_only=True, slots=True)
class Type:
    kind: TypeKind = attr.ib()

    def compatible_with(self, other: Type) -> bool:
        return self.kind is other.kind

    def call(
        self,
        arguments: typing.Union[typing.List[Type], typing.Tuple[Type, ...]] = (),
        keyword_arguments: typing.Optional[typing.Mapping[typing.Optional[str], Type]] = None,
    ) -> Type:
        assert False, '<Not Callable>'

    def truthness(self) -> typing.Optional[bool]:
        return None

    def getattribute(self, name: str) -> Type:
        assert False, '<Missing Attribute>'

    def getitem(self, slice: Type) -> Type:
        assert False, '<Not Subscriptable>'

    def pos(self) -> Type:
        assert False, '<Unsupported Operand>'

    def neg(self) -> Type:
        assert False, '<Unsupported Operand>'

    def invert(self) -> Type:
        assert False, '<Unsupported Operand>'

    def add(self, other: Type) -> Type:
        assert False, '<Unsupported Operand>'

    def sub(self, other: Type) -> Type:
        assert False, '<Unsupported Operand>'

    def mult(self, other: Type) -> Type:
        assert False, '<Unsupported Operand>'

    def matmult(self, other: Type) -> Type:
        assert False, '<Unsupported Operand>'

    def div(self, other: Type) -> Type:
        assert False, '<Unsupported Operand>'

    def floordiv(self, other: Type) -> Type:
        assert False, '<Unsupported Operand>'

    def mod(self, other: Type) -> Type:
        assert False, '<Unsupported Operand>'

    def pow(self, other: Type) -> Type:
        assert False, '<Unsupported Operand>'

    def lshift(self, other: Type) -> Type:
        assert False, '<Unsupported Operand>'

    def rshift(self, other: Type) -> Type:
        assert False, '<Unsupported Operand>'

    def bitor(self, other: Type) -> Type:
        assert False, '<Unsupported Operand>'

    def bitxor(self, other: Type) -> Type:
        assert False, '<Unsupported Operand>'

    def bitand(self, other: Type) -> Type:
        assert False, '<Unsupported Operand>'


@attr.s(kw_only=True, slots=True)
class BoolType(Type):
    kind: typing.Literal[TypeKind.BOOL] = attr.ib(init=False, default=TypeKind.BOOL)
    constraint: typing.Optional[bool] = attr.ib()

    def __str__(self) -> str:
        if self.constraint is None:
            return 'bool'

        return str(self.constraint)

    def truthness(self) -> typing.Optional[bool]:
        if self.constraint is None:
            return None

        return self.constraint


@attr.s(kw_only=True, slots=True)
class NoneType(Type):
    kind: typing.Literal[TypeKind.NONE] = attr.ib(init=False, default=TypeKind.NONE)
    constraint: None = attr.ib(init=False, default=None)

    def __str__(self) -> str:
        return 'None'

    def truthness(self) -> bool:
        return False


@attr.s(kw_only=True, slots=True)
class EllipsisType(Type):
    kind: typing.Literal[TypeKind.ELLIPSIS] = attr.ib(init=False, default=TypeKind.ELLIPSIS)
    constraint: types.EllipsisType = attr.ib(init=False, default=Ellipsis)

    def __str__(self) -> str:
        return 'ellipsis'

    def truthness(self) -> bool:
        return True


@attr.s(kw_only=True, slots=True)
class StringType(Type):
    kind: typing.Literal[TypeKind.STRING] = attr.ib(init=False, default=TypeKind.STRING)
    constraint: typing.Optional[str] = attr.ib()

    def __str__(self):
        if self.constraint is None:
            return 'str'

        return repr(self.constraint)

    def truthness(self) -> typing.Optional[bool]:
        if self.constraint is None:
            return None

        return bool(self.constraint)


@attr.s(kw_only=True, slots=True)
class IntegerType(Type):
    kind: typing.Literal[TypeKind.INTEGER] = attr.ib(init=False, default=TypeKind.INTEGER)
    constraint: typing.Optional[int] = attr.ib()

    def __str__(self) -> str:
        if self.constraint is None:
            return 'int'

        return str(self.constraint)

    def truthness(self) -> typing.Optional[bool]:
        if self.constraint is None:
            return None

        return bool(self.constraint)

    def pos(self) -> Type:
        if self.constraint is None:
            return self

        constraint = +self.constraint
        return IntegerType(constraint=constraint)

    def neg(self) -> Type:
        if self.constraint is None:
            return self

        constraint = -self.constraint
        return IntegerType(constraint=constraint)

    def invert(self) -> Type:
        if self.constraint is None:
            return self

        constraint = ~self.constraint
        return IntegerType(constraint=constraint)

    def add(self, other: Type) -> Type:
        if not isinstance(other, (IntegerType, FloatType)):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return other

        constraint = self.constraint + other.constraint
        if isinstance(constraint, float):
            return FloatType(constraint=constraint)

        return IntegerType(constraint=constraint)

    def sub(self, other: Type) -> Type:
        if not isinstance(other, (IntegerType, FloatType)):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return other

        constraint = self.constraint - other.constraint
        if isinstance(constraint, float):
            return FloatType(constraint=constraint)

        return IntegerType(constraint=constraint)

    def mult(self, other: Type) -> Type:
        if not isinstance(other, (IntegerType, FloatType)):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return other

        constraint = self.constraint * other.constraint
        if isinstance(constraint, float):
            return FloatType(constraint=constraint)

        return IntegerType(constraint=constraint)

    def div(self, other: Type) -> Type:
        if not isinstance(other, (IntegerType, FloatType)):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return FloatType(constraint=None)

        constraint = self.constraint / other.constraint
        return FloatType(constraint=constraint)

    def floordiv(self, other: Type) -> Type:
        if not isinstance(other, (IntegerType, FloatType)):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return other

        constraint = self.constraint // other.constraint
        if isinstance(constraint, float):
            return FloatType(constraint=constraint)

        return IntegerType(constraint=constraint)

    def mod(self, other: Type) -> Type:
        if not isinstance(other, (IntegerType, FloatType)):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return other

        constraint = self.constraint % other.constraint
        if isinstance(constraint, float):
            return FloatType(constraint=constraint)

        return IntegerType(constraint=constraint)

    def pow(self, other: Type) -> Type:
        if not isinstance(other, (IntegerType, FloatType)):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return other

        constraint = self.constraint ** other.constraint
        if isinstance(constraint, float):
            return FloatType(constraint=constraint)

        return IntegerType(constraint=constraint)

    def lshift(self, other: Type) -> Type:
        if not isinstance(other, IntegerType):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return other

        constraint = self.constraint << other.constraint
        return IntegerType(constraint=constraint)

    def rshift(self, other: Type) -> Type:
        if not isinstance(other, IntegerType):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return other

        constraint = self.constraint >> other.constraint
        return IntegerType(constraint=constraint)

    def bitor(self, other: Type) -> Type:
        if not isinstance(other, IntegerType):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return other

        constraint = self.constraint | other.constraint
        return IntegerType(constraint=constraint)

    def bitxor(self, other: Type) -> Type:
        if not isinstance(other, IntegerType):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return other

        constraint = self.constraint ^ other.constraint
        return IntegerType(constraint=constraint)

    def bitand(self, other: Type) -> Type:
        if not isinstance(other, IntegerType):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return other

        constraint = self.constraint & other.constraint
        return IntegerType(constraint=constraint)


@attr.s(kw_only=True, slots=True)
class FloatType(Type):
    kind: typing.Literal[TypeKind.FLOAT] = attr.ib(init=False, default=TypeKind.FLOAT)
    constraint: typing.Optional[float] = attr.ib()

    def __str__(self) -> str:
        if self.constraint is None:
            return 'float'

        return str(self.constraint)

    def truthness(self) -> typing.Optional[bool]:
        if self.constraint is None:
            return None

        return bool(self.constraint)

    def add(self, other: Type) -> Type:
        if not isinstance(other, (IntegerType, FloatType)):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return self

        constraint = self.constraint + other.constraint
        return FloatType(constraint=constraint)

    def sub(self, other: Type) -> Type:
        if not isinstance(other, (IntegerType, FloatType)):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return self

        constraint = self.constraint - other.constraint
        return FloatType(constraint=constraint)

    def mult(self, other: Type) -> Type:
        if not isinstance(other, (IntegerType, FloatType)):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return self

        constraint = self.constraint * other.constraint
        return FloatType(constraint=constraint)

    def div(self, other: Type) -> Type:
        if not isinstance(other, (IntegerType, FloatType)):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return self

        constraint = self.constraint / other.constraint
        return FloatType(constraint=constraint)

    def floordiv(self, other: Type) -> Type:
        if not isinstance(other, (IntegerType, FloatType)):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return self

        constraint = self.constraint // other.constraint
        return FloatType(constraint=constraint)

    def mod(self, other: Type) -> Type:
        if not isinstance(other, (IntegerType, FloatType)):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return self

        constraint = self.constraint % other.constraint
        return FloatType(constraint=constraint)

    def pow(self, other: Type) -> Type:
        if not isinstance(other, (IntegerType, FloatType)):
            assert False, '<Unsupported Operand>'

        if self.constraint is None or other.constraint is None:
            return self

        constraint = self.constraint ** other.constraint
        return FloatType(constraint=constraint)


@attr.s(kw_only=True, slots=True)
class ComplexType(Type):
    kind: typing.Literal[TypeKind.COMPLEX] = attr.ib(init=False, default=TypeKind.COMPLEX)
    constraint: typing.Optional[complex] = attr.ib(repr=False, eq=False)

    def __str__(self) -> str:
        if self.constraint is None:
            return 'complex'

        return str(self.constraint)

    def truthness(self) -> typing.Optional[bool]:
        if self.constraint is None:
            return None

        return bool(self.constraint)


@attr.s(kw_only=True, slots=True)
class DictType(Type):
    kind: typing.Literal[TypeKind.DICT] = attr.ib(init=False, default=TypeKind.DICT)

    key: Type = attr.ib()
    value: Type = attr.ib()

    def __str__(self) -> str:
        return f'{{{self.key}: {self.value}}}'


@attr.s(kw_only=True, slots=True)
class SetType(Type):
    kind: typing.Literal[TypeKind.SET] = attr.ib(init=False, default=TypeKind.SET)
    value: Type = attr.ib()

    def __str__(self) -> str:
        return f'{{{self.value}}}'


@attr.s(kw_only=True, slots=True)
class TupleType(Type):
    kind: typing.Literal[TypeKind.TUPLE] = attr.ib(init=False, default=TypeKind.TUPLE)
    values: typing.List[Type] = attr.ib()

    def __str__(self) -> str:
        values = ', '.join(str(value) for value in self.values)
        return f'({values})'

    def truthness(self) -> bool:
        return bool(self.values)


@attr.s(kw_only=True, slots=True)
class ListType(Type):
    kind: typing.Literal[TypeKind.LIST] = attr.ib(init=False, default=TypeKind.LIST)
    value: Type = attr.ib()
    size: typing.Optional[int] = attr.ib()

    def __str__(self) -> str:
        if self.size is None:
            return f'[{self.value}]'

        return f'[{self.value}, {self.size}]'

    def truthness(self) -> typing.Optional[bool]:
        if self.size is None:
            return None

        return bool(self.size)


@attr.s(kw_only=True, slots=True)
class SliceType(Type):
    kind: typing.Literal[TypeKind.SLICE] = attr.ib(init=False, default=TypeKind.SLICE)
    start: typing.Optional[Type] = attr.ib()
    stop: typing.Optional[Type] = attr.ib()
    step: typing.Optional[Type] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionParameter:
    name: str = attr.ib()
    type: Type = attr.ib()
    kind: ast.ParameterKind = attr.ib()
    default: typing.Optional[Type] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionType(Type):
    kind: typing.Literal[TypeKind.FUNCTION] = attr.ib(init=False, default=TypeKind.FUNCTION)
    parameters: typing.List[FunctionParameter] = attr.ib()
    returns: Type = attr.ib()

    def get_parameters(self, kind: ast.ParameterKind) -> typing.List[FunctionParameter]:
        return list(parameter for parameter in self.parameters if parameter.kind is kind)

    def call(
        self,
        arguments: typing.Union[typing.List[Type], typing.Tuple[Type, ...]] = (),
        keyword_arguments: typing.Optional[typing.Mapping[typing.Optional[str], Type]] = None,
    ) -> Type:
        if arguments:
            parameters: typing.List[FunctionParameter] = []

            parameters.extend(self.get_parameters(ast.ParameterKind.POSONLY))
            parameters.extend(self.get_parameters(ast.ParameterKind.ARG))

            default = parameters[-1].default
            required = len(parameters) if default is None else len(parameters) - 1

            if len(arguments) <= required:
                assert False, '<Not Enough Arguments>'

            for parameter, argument in zip(parameters, arguments):
                if not parameter.type.compatible_with(argument):
                    assert False, '<Incompatible Type>'

                parameters.pop(0)

            arguments = arguments[:len(parameters)]
            parameters = self.get_parameters(ast.ParameterKind.VARARG)

            if len(parameters) == 0 and arguments:
                assert False, '<Too Many Arguments>'

            parameter = parameters[0]
            for argument in arguments:
                if not parameter.type.compatible_with(argument):
                    assert False, '<Incompatible Type>'

        if keyword_arguments is not None:
            keys = list(keyword_arguments.keys())
            parameters = self.get_parameters(ast.ParameterKind.KWONLY)

            for parameter in parameters:
                argument = keyword_arguments.get(parameter.name)
                if argument is None and parameter.default is None:
                    assert False, '<Missing Argument>'

                if argument is not None:
                    if not parameter.type.compatible_with(argument):
                        assert False, '<Incompatible Type>'

                    keys.remove(parameter.name)

            parameters = self.get_parameters(ast.ParameterKind.VARKWARG)
            if len(parameters) == 0 and keys:
                assert False, '<Too Many Keyword Arguments>'

            parameter = parameters[0]
            for key in keys:
                argument = keyword_arguments[key]
                if not parameter.type.compatible_with(argument):
                    assert False, '<Incompatible Type>'

        return self.returns


@attr.s(kw_only=True, slots=True)
class ClassType(Type):
    kind: typing.Literal[TypeKind.CLASS] = attr.ib(init=False, default=TypeKind.CLASS)
    bases: typing.List[Type] = attr.ib()


@attr.s(slots=True)
class UnionType(Type):
    kind: typing.Literal[TypeKind.UNION] = attr.ib(init=False, default=TypeKind.UNION)
    types: typing.List[Type] = attr.ib()

    def __str__(self) -> str:
        return ' | '.join(str(type) for type in self.types)


def union(types: typing.Iterable[Type]) -> UnionType:
    flattened: typing.List[Type] = []

    for type in types:
        if isinstance(type, UnionType):
            flattened.extend(type for type in type.types if type not in flattened)
        else:
            if type not in flattened:
                flattened.append(type)

    return UnionType(types=flattened)


ConstantType = typing.Union[
    BoolType,
    NoneType,
    EllipsisType,
    StringType,
    IntegerType,
    FloatType,
    ComplexType,
]

LiteralType = typing.Union[
    BoolType,
    StringType,
    IntegerType,
    FloatType,
    ComplexType,
]

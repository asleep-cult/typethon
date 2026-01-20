from __future__ import annotations

import enum
import attr
import typing


@attr.s(kw_only=True, slots=True)
class ImplementationFunction:
    function: FunctionType = attr.ib()
    parameter_map: typing.Optional[
        typing.Dict[TypeParameter, ConcreteType]
    ] = attr.ib()
    # I am storing parameter_map on both ImplementationFunction
    # and ImplementationClass so you can have things like
    # use Type(int), where the implementation is only defined 
    # for Type(int) and not, for example, Type(str). Or
    # Type('t), where 't is constrained to a certain type class.
    # There will need to be some work to get the parameter and return
    # types right because the functions in the use block will
    # have their own type parameters
    # Right now, I've actually only implemented this "unification"
    # class_parameter_map and it seems to work.


@attr.s(kw_only=True, slots=True)
class ImplementationClass:
    type_class: TypeClass = attr.ib()
    parameter_map: typing.Optional[typing.Dict[TypeParameter, ConcreteType]] = attr.ib()
    class_parameter_map: typing.Optional[typing.Dict[TypeParameter, ConcreteType]] = attr.ib()


@attr.s(kw_only=True, slots=True)
class TypeImplementation:
    type: typing.Union[NonParameterizedConcreteType, PolymorphicType] = attr.ib()
    functions: typing.Dict[str, ImplementationFunction] = attr.ib(factory=dict)
    type_classes: typing.List[ImplementationClass] = attr.ib(factory=list)


@attr.s(kw_only=True, slots=True)
class TypeCache:
    types: typing.List[NonParameterizedConcreteType] = attr.ib(factory=list)
    implementations: typing.Dict[
        typing.Union[NonParameterizedConcreteType, PolymorphicType], TypeImplementation
    ] = attr.ib(factory=dict)

    def create_type_alias(self, name: str) -> TypeAlias:
        type_alias = TypeAlias(id=len(self.types), name=name)
        self.types.append(type_alias)
        return type_alias

    def create_struct_type(self, name: str) -> StructType:
        struct_type = StructType(id=len(self.types), name=name)
        self.types.append(struct_type)
        return struct_type

    def create_tuple_type(self, name: str) -> TupleType:
        tuple_type = TupleType(id=len(self.types), name=name)
        self.types.append(tuple_type)
        return tuple_type

    def create_sum_type(self, name: str) -> SumType:
        sum_type = SumType(id=len(self.types), name=name)
        self.types.append(sum_type)
        return sum_type

    def create_function_type(self, name: str) -> FunctionType:
        function_type = FunctionType(id=len(self.types), name=name)
        self.types.append(function_type)
        return function_type

    def create_type_class(self, name: str) -> TypeClass:
        type_class = TypeClass(id=len(self.types), name=name)
        self.types.append(type_class)
        return type_class

    def create_type_parameter(self, name: str) -> TypeParameter:
        type_parameter = TypeParameter(id=len(self.types), name=name)
        self.types.append(type_parameter)
        return type_parameter


class SingletonType(enum.Enum):
    ANY = enum.auto()
    UNDECLARED = enum.auto()
    UNIT = enum.auto()
    UNKNOWN = enum.auto()
    SELF = enum.auto()

    BOOL = enum.auto()
    INT = enum.auto()
    FLOAT = enum.auto()
    COMPLEX = enum.auto()
    STR = enum.auto()
    # LIST, DICT, SET?
    # I think dict and set need to be in the std library
    # with no special syntax

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True, hash=True)
class TypeAlias:
    id: int = attr.ib(hash=True)
    name: str = attr.ib(hash=False)
    type: ConcreteType = attr.ib(default=SingletonType.UNKNOWN, hash=False)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True)
class StructField:
    name: str = attr.ib()
    type: ConcreteType = attr.ib()

    def to_string(self) -> str:
        return f'{self.name}: {self.type.to_string()}'


@attr.s(kw_only=True, slots=True, hash=True)
class StructType:
    id: int = attr.ib(hash=True)
    name: str = attr.ib(hash=False)
    fields: typing.Dict[str, StructField] = attr.ib(factory=dict, hash=False)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True, hash=True)
class TupleType:
    id: int = attr.ib(hash=True)
    name: str = attr.ib(hash=False)
    fields: typing.List[ConcreteType] = attr.ib(factory=list, hash=False)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True)
class SumType:
    id: int = attr.ib(hash=True)
    name: str = attr.ib()
    fields: typing.Dict[str, SumField] = attr.ib(factory=dict)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True)
class SumField:
    name: str = attr.ib()
    data: typing.Optional[DataType] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionParameter:
    name: str = attr.ib()
    type: ConcreteType = attr.ib()

    def to_string(self) -> str:
        return f'{self.name}: {self.type.to_string()}'


@attr.s(kw_only=True, slots=True, hash=True)
class FunctionType:
    id: int = attr.ib(hash=True)
    name: str = attr.ib(hash=False)
    parameters: typing.Dict[str, FunctionParameter] = attr.ib(factory=dict, hash=False)
    returns: ConcreteType = attr.ib(default=SingletonType.UNIT, hash=False)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True, hash=True)
class TypeClass:
    id: int = attr.ib(hash=True)
    name: str = attr.ib(hash=False)
    functions: typing.Dict[str, FunctionType] = attr.ib(factory=dict, hash=False)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True, hash=True)
class TypeParameter:
    id: int = attr.ib(hash=True)
    name: str = attr.ib(hash=False)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True)
class PolymorphicType:
    type: NonParameterizedConcreteType = attr.ib(hash=False)
    parameters: typing.List[TypeParameter] = attr.ib(factory=list, hash=False)

    def to_string(self) -> str:
        parameters = ', '.join(parameter.to_string() for parameter in self.parameters)
        return f'polmorohic({self.type.to_string()}, {parameters})'

    def with_parameters(self, parameters: typing.List[ConcreteType]) -> ParameterizedType:
        if len(self.parameters) != len(parameters):
            raise ValueError(f'{self} requires {len(self.parameters)}, got {len(parameters)}')

        parameter_map = dict(zip(self.parameters, parameters))
        return ParameterizedType(type=self.type, parameter_map=parameter_map)


@attr.s(kw_only=True, slots=True)
class ParameterizedType:
    type: NonParameterizedConcreteType = attr.ib()
    parameter_map: typing.Dict[TypeParameter, ConcreteType] = attr.ib()

    def to_string(self) -> str:
        parameters = ', '.join(
            f'{param1.to_string()} -> {param2.to_string()}'
            for param1, param2 in self.parameter_map.items()
        )
        return f'parameterized({self.type.to_string()}, {parameters})'


NonParameterizedConcreteType = typing.Union[
    SingletonType,
    TypeAlias,
    StructType,
    TupleType,
    FunctionType,
    TypeClass,
    SumType,
    TypeParameter,
]

ConcreteType = typing.Union[
    NonParameterizedConcreteType,
    ParameterizedType,
]

Type = typing.Union[
    ConcreteType,
    PolymorphicType,
]

DataType = typing.Union[
    StructType,
    TupleType,
]

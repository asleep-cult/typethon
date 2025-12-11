from __future__ import annotations

import attr
import typing
import enum

# TODO: __eq__ needs to resolve resursion issues
# that arise from cyclic references

T = typing.TypeVar('T')


@attr.s(kw_only=True, slots=True)
class AnalyzedType:
    name: str = attr.ib()

    def __str__(self) -> str:
        string = self.get_string()
        return f'type({string})'

    def get_string(self, *, top_level: bool = True) -> str:
        return str(self.name)

    def access_attribute(self, name: str) -> AnalyzedType:
        assert False, f'<{self} has no attribute {name}>'

    def to_instance(self, value: typing.Any = None) -> InstanceOfType:
        return InstanceOfType(name=self.name, type=self, known_value=value)


@attr.s(kw_only=True, slots=True)
class InstanceOfType(AnalyzedType):
    type: AnalyzedType = attr.ib()
    known_value: typing.Any = attr.ib()

    def __str__(self) -> str:
        return self.get_string()


UNKNOWN = AnalyzedType(name='unknown')

@attr.s(kw_only=True, slots=True)
class TypeParameter(AnalyzedType):
    owner: AnalyzedType = attr.ib(default=UNKNOWN, eq=False)  # False because of recursion
    constraint: typing.Optional[AnalyzedType] = attr.ib(default=None)

    def get_string(self, *, top_level: bool = True) -> str:
        if top_level:
            owner = self.owner.get_string(top_level=False)
            name = f'{self.name}@{owner}'
        else:
            name = self.name

        if self.constraint is not None:
            return f'|{name}: {self.constraint}|'

        return f'|{name}|'


@attr.s(kw_only=True, slots=True)
class PolymorphicType(AnalyzedType):
    initial_type: typing.Optional[PolymorphicType] = attr.ib(default=None)
    parameters: typing.List[AnalyzedType] = attr.ib(factory=list)

    def get_string(self, *, top_level: bool = True) -> str:
        parameters = ', '.join(
            parameter.get_string(top_level=False) for parameter in self.parameters
        )
        return f'{self.name}({parameters})'

    def get_initial_type(self) -> PolymorphicType:
        return self.initial_type if self.initial_type is not None else self

    def is_polymorphic(self) -> bool:
        return any(self.uninitialized_parameters())

    def uninitialized_parameters(self) -> typing.Generator[TypeParameter]:
        for parameter in self.parameters:
            match parameter:
                case TypeParameter():
                    yield parameter
                case PolymorphicType():
                    # This should always be nothing theoretically
                    # So this function is useless
                    yield from parameter.uninitialized_parameters()

    def with_parameters(self, parameters: typing.List[AnalyzedType]) -> PolymorphicType:
        initial_type = self.get_initial_type()
        return PolymorphicType(initial_type=initial_type, name=self.name, parameters=parameters)


@attr.s(kw_only=True, slots=True)
class TypeTrait(PolymorphicType):
    tr_functions: typing.List[FunctionType] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionParameter:
    name: str = attr.ib()
    type: AnalyzedType = attr.ib()
    # TODO: default
    # kw_only, etc.


@attr.s(kw_only=True, slots=True)
class FunctionType(PolymorphicType):
    propagated: bool = attr.ib(default=True)
    # PolymorphicType fields must be filled regardless of propagation
    fn_self: typing.Optional[AnalyzedType] = attr.ib(default=None)
    fn_parameters: typing.List[FunctionParameter] = attr.ib(factory=list)
    fn_returns: AnalyzedType = attr.ib(default=UNKNOWN)

    def get_string(self, *, top_level: bool = True) -> str:
        strings: typing.List[str] = []

        for parameter in self.fn_parameters:
            string = parameter.type.get_string(top_level=False)
            strings.append(f'{parameter.name}: {string}')

        parameters = ', '.join(strings)
        returns = self.fn_returns.get_string(top_level=False)
        return f'({parameters}) -> {returns}'

    def complete_propagation(self) -> None:
        self.propagated = True


@attr.s(kw_only=True, slots=True)
class ClassAttribute:
    name: str = attr.ib()
    type: AnalyzedType = attr.ib()
    # TODO: default?, kw_only?


@attr.s(kw_only=True, slots=True)
class ClassType(PolymorphicType):
    propagated: bool = attr.ib(default=True)
    cls_attributes: typing.List[ClassAttribute] = attr.ib(factory=list)
    cls_functions: typing.List[FunctionType] = attr.ib(factory=list)

    def complete_propagation(self) -> None:
        self.propagated = True


class TypeBuilderKind(enum.Enum):
    BASIC = enum.auto()
    POLYMORPHIC = enum.auto()
    FUNCTION = enum.auto()
    CLASS = enum.auto()
    TRAIT = enum.auto()


@attr.s(kw_only=True, slots=True)
class _UnknownTypeParameter(AnalyzedType):
    ...


class TypeBuilder(typing.Generic[T]):
    def __init__(self, name: str, kind: TypeBuilderKind) -> None:
        self.name = name
        self.kind = kind

        if self.kind is not TypeBuilderKind.BASIC:
            self.parameters: typing.List[typing.Tuple[str, typing.Optional[AnalyzedType]]] = []

        match self.kind:
            case TypeBuilderKind.FUNCTION:
                self.fn_parameters: typing.List[FunctionParameter] = []

            case TypeBuilderKind.CLASS:
                self.cls_attributes: typing.List[ClassAttribute] = []
                self.cls_functions: typing.List[FunctionType] = []

            case TypeBuilderKind.TRAIT:
                self.tr_functions: typing.List[FunctionType] = []

    @classmethod
    def new_type(
        cls: typing.Type[TypeBuilder[AnalyzedType]], name: str
    ) -> TypeBuilder[AnalyzedType]:
        return cls(name, TypeBuilderKind.BASIC)

    @classmethod
    def new_polymorphic_type(
        cls: typing.Type[TypeBuilder[PolymorphicType]], name: str
    ) -> TypeBuilder[PolymorphicType]:
        return cls(name, TypeBuilderKind.POLYMORPHIC)

    @classmethod
    def new_function(
        cls: typing.Type[TypeBuilder[FunctionType]], name: str
    ) -> TypeBuilder[FunctionType]:
        return cls(name, TypeBuilderKind.FUNCTION)

    @classmethod
    def new_class(
        cls: typing.Type[TypeBuilder[ClassType]], name: str
    ) -> TypeBuilder[ClassType]:
        return TypeBuilder(name, TypeBuilderKind.CLASS)

    @classmethod
    def new_trait(
        cls: typing.Type[TypeBuilder[TypeTrait]], name: str
    ) -> TypeBuilder[TypeTrait]:
        return cls(name, TypeBuilderKind.TRAIT)

    def build_type_parameters(self, owner: AnalyzedType) -> typing.Generator[TypeParameter]:
        for name, constraint in self.parameters:
            yield TypeParameter(name=name, owner=owner, constraint=constraint)

    def update_function_types(
        self,
        type_parameters: typing.Dict[str, AnalyzedType],
        function: FunctionType,
        allow_unknown: bool
    ) -> None:
        for parameter in function.fn_parameters:
            if not isinstance(parameter.type, _UnknownTypeParameter):
                continue

            if parameter.type.name in type_parameters:
                parameter.type = type_parameters[parameter.type.name]

            elif not allow_unknown:
                raise ValueError(
                    f'Encountered unknown paramater {parameter.name}: '
                    f'{parameter.type.name} in {function.name}'
                )

        if isinstance(function.fn_returns, _UnknownTypeParameter):
            if function.fn_returns.name in type_parameters:
                function.fn_returns = type_parameters[function.fn_returns.name]

            elif not allow_unknown:
                raise ValueError(
                    f'Encountered unknown return value {function.fn_returns.name} '
                    f'in {function.name}'
                )

    def update_unknown_parameters(
        self,
        type: PolymorphicType,
        allow_unknown: bool
    ) -> None:
        type_parameters = {parameter.name: parameter for parameter in type.parameters}

        match type:
            case FunctionType():
                self.update_function_types(type_parameters, type, allow_unknown)

            case ClassType():
                for attribute in self.cls_attributes:
                    if not isinstance(attribute.type, _UnknownTypeParameter):
                        continue

                    if attribute.type.name in type_parameters:
                        attribute.type = type_parameters[attribute.type.name]

                    elif not allow_unknown:
                        raise ValueError(
                            f'Encountered unknown attribute {attribute.name}: '
                            f'{attribute.type.name} in {type.name}'
                        )

                for function in self.cls_functions:
                    self.update_function_types(type_parameters, function, allow_unknown)

            case TypeTrait():
                for function in self.tr_functions:
                    self.update_function_types(type_parameters, function, allow_unknown)

    def build_type(self, *, nested: bool = False) -> T:
        # This function creates the type and the type parameters,
        # then replaces the temporary instances of _UnknownTypeParameter.
        # If nested is set to True, this function will not raise an exception
        # for any unresolved type parameters. This allows nested types to use
        # type parameters from their parent types.
        match self.kind:
            case TypeBuilderKind.BASIC:
                return typing.cast(T, AnalyzedType(name=self.name))

            case TypeBuilderKind.POLYMORPHIC:
                type = PolymorphicType(name=self.name)

            case TypeBuilderKind.FUNCTION:
                type = FunctionType(
                    name=self.name,
                    fn_parameters=self.fn_parameters,
                    fn_returns=self.fn_returns,
                )

            case TypeBuilderKind.CLASS:
                type = ClassType(
                    name=self.name,
                    cls_attributes=self.cls_attributes,
                    cls_functions=self.cls_functions,
                )

            case TypeBuilderKind.TRAIT:
                type = TypeTrait(name=self.name, tr_functions=self.tr_functions)

        type.parameters.extend(self.build_type_parameters(type))
        self.update_unknown_parameters(type, allow_unknown=nested)

        return typing.cast(T, type)

    def add_type_parameter(
        self, name: str, constraint: typing.Optional[AnalyzedType] = None
    ) -> typing.Self:
        self.parameters.append((name, constraint))
        return self

    def add_parameter(
        self, name: str, type: typing.Union[AnalyzedType, str]
    ) -> typing.Self:
        if self.kind is not TypeBuilderKind.FUNCTION:
            raise TypeError('add_parameter() is for functions')

        if isinstance(type, str):
            type = _UnknownTypeParameter(name=type)

        self.fn_parameters.append(FunctionParameter(name=name, type=type))
        return self

    def add_return_type(self, type: typing.Union[str, AnalyzedType]) -> typing.Self:
        if isinstance(type, str):
            type = _UnknownTypeParameter(name=type)

        self.fn_returns = type
        return self

    def add_function(self, function: FunctionType) -> typing.Self:
        if self.kind is TypeBuilderKind.CLASS:
            self.cls_functions.append(function)
        elif self.kind is TypeBuilderKind.TRAIT:
            self.tr_functions.append(function)
        else:
            raise TypeError('add_function() is for functions and traits')

        return self

    def add_attribute(
        self, name: str, type: typing.Union[AnalyzedType, str]
    ) -> typing.Self:
        if self.kind is not TypeBuilderKind.CLASS:
            raise TypeError('add_attribute() is for classes')

        if isinstance(type, str):
            type = _UnknownTypeParameter(name=name)

        self.cls_attributes.append(ClassAttribute(name=name, type=type))
        return self


class BuiltinTypes:
    SELF = TypeBuilder.new_type('Self').build_type()

    NONE_TYPE = TypeBuilder.new_type('NoneType').build_type()
    NONE = NONE_TYPE.to_instance()

    BOOL = TypeBuilder.new_type('bool').build_type()
    TRUE = BOOL.to_instance(True)
    FALSE = BOOL.to_instance(False)

    INT = TypeBuilder.new_type('bool').build_type()
    FLOAT = TypeBuilder.new_type('float').build_type()
    COMPLEX = TypeBuilder.new_type('complex').build_type()
    STR = TypeBuilder.new_type('str').build_type()
    LIST = (
        TypeBuilder.new_polymorphic_type('list')
        .add_type_parameter('T')
        .build_type()
    )

    DICT: PolymorphicType
    SET: PolymorphicType


class BuiltinTraits:
    HASH = (
        TypeBuilder.new_trait('Hash')
        .add_function(
            TypeBuilder.new_function('hash')
            .add_parameter('self', BuiltinTypes.SELF)
            .add_return_type(BuiltinTypes.STR)
            .build_type(nested=True)
        )
        .build_type()
    )

    ADD = (
        TypeBuilder.new_trait('Add')
        .add_type_parameter('T')
        .add_type_parameter('U')
        .add_function(
            TypeBuilder.new_function('add')
            .add_parameter('self', BuiltinTypes.SELF)
            .add_parameter('rhs', 'T')
            .add_return_type('U')
            .build_type(nested=True)
        )
        .build_type()
    )


BuiltinTypes.DICT = (
    TypeBuilder.new_polymorphic_type('dict')
    .add_type_parameter('K', BuiltinTraits.HASH)
    .add_type_parameter('V')
    .build_type()
)
BuiltinTypes.SET = (
    TypeBuilder.new_polymorphic_type('set')
    .add_type_parameter('T', BuiltinTraits.HASH)
    .build_type()
)

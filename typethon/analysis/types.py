from __future__ import annotations

import attr
import typing
import enum

# TODO: __eq__ needs to resolve resursion issues
# that arise from cyclic references, improve handling
# type parameters, it is error prone at the moment

T = typing.TypeVar('T')


@attr.s(kw_only=True, slots=True, hash=True)
class AnalyzedType:
    name: str = attr.ib()
    trait_tables: typing.List[TraitTable] = attr.ib(factory=list, repr=False)

    def __str__(self) -> str:
        string = self.get_string()
        return f'type({string})'

    def is_compatible_with(self, type: AnalyzedType) -> bool:
        if self is BuiltinTypes.ANY or type is BuiltinTypes.ANY:
            return True

        return self is type

    def add_trait_table(self, trait_table: TraitTable) -> None:
        # The implementation functions for traits are stored on each type
        # in the form of a TraitTable which holds a mapping of functions
        # along with the trait it is implementing. To find a TraitTable
        # for a specific trait, we iterate over each one and return the first
        # table the whos trait is compatible with the trait we are looking
        # for. Since traits can be polymorphic, this means checking whether
        # each parameter for both traits are compatible.
        self.trait_tables.append(trait_table)

    def get_trait_table(self, trait: TypeTrait) -> typing.Optional[TraitTable]:
        for table in self.trait_tables:
            if table.trait.is_compatible_with(trait):
                return table

    def get_string(self, *, top_level: bool = True) -> str:
        return str(self.name)

    def access_attribute(self, name: str) -> AnalyzedType:
        assert False, f'<{self} has no attribute {name}>'

    def to_instance(self, value: typing.Any = None) -> InstanceOfType:
        return InstanceOfType(name=self.name, type=self, known_value=value)

    def bind_with_parameters(self, type: PolymorphicType) -> AnalyzedType:
        return self


@attr.s(kw_only=True, slots=True)
class TraitTable:
    trait: TypeTrait = attr.ib()
    owner: typing.Optional[PolymorphicType] = attr.ib(default=None, repr=str)
    functions: typing.Dict[str, FunctionType] = attr.ib()

    def with_owner(self, type: PolymorphicType) -> TraitTable:
        return TraitTable(trait=self.trait, owner=type, functions=self.functions)


@attr.s(kw_only=True, slots=True)
class UnionType(AnalyzedType):
    # XXX: This will probably be a compiler only type
    types: typing.List[AnalyzedType] = attr.ib(factory=list)


@attr.s(kw_only=True, slots=True)
class InstanceOfType(AnalyzedType):
    type: AnalyzedType = attr.ib()
    known_value: typing.Any = attr.ib()

    def __str__(self) -> str:
        return self.get_string()


UNKNOWN = AnalyzedType(name='unknown')


@attr.s(kw_only=True, slots=True, hash=True)
class TypeParameter(AnalyzedType):
    owner: AnalyzedType = attr.ib(default=UNKNOWN, eq=False, repr=False)  # False because of recursion
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

    def bind_with_parameters(self, type: PolymorphicType) -> AnalyzedType:
        for parameter in type.parameters:
            if not isinstance(parameter, GivenTypeParameter):
                assert False, f'<{parameter} has not been given>'

            resolved = parameter.resolve_for(self)
            if resolved is not None:
                return resolved

        # No overlap between this parameter and the given parameters on type
        return self


@attr.s(kw_only=True, slots=True)
class GivenTypeParameter(AnalyzedType):
    # This class is resursively instantiated so that the original
    # type parameter is always on top.
    parameter: TypeParameter = attr.ib()
    type: typing.Union[
        GivenTypeParameter,
        TypeParameter,
        AnalyzedType,
    ] = attr.ib()

    def is_compatible_with(self, type: AnalyzedType) -> bool:
        if not isinstance(type, GivenTypeParameter):
            return False

        if self.parameter is not type.parameter:
            assert False, f'<{self.parameter} and {type.parameter} are not the same parameter>'

        # XXX: This may or may not be what we want to do
        return self.type.is_compatible_with(type.type)

    def get_actual_type(self) -> AnalyzedType:
        if not isinstance(self.type, GivenTypeParameter):
            return self.type

        return self.type.get_actual_type()

    def resolve_for(self, parameter: TypeParameter) -> typing.Optional[AnalyzedType]:
        if self.parameter is parameter:
            if isinstance(self.type, GivenTypeParameter):
                return self.type.get_actual_type()
            else:
                return self.type

        if isinstance(self.type, GivenTypeParameter):
            return self.type.resolve_for(parameter)

    def with_type(self, type: AnalyzedType) -> GivenTypeParameter:
        if isinstance(self.type, GivenTypeParameter):
            return GivenTypeParameter(
                name=self.name,
                parameter=self.parameter,
                type=self.type.with_type(type),
            )

        elif not isinstance(self.type, TypeParameter):
            assert False, f'<{self.parameter.name} is already {self.type}>'

        innter_parameter = GivenTypeParameter(
            name=f'{self.name}@{type.name}',
            parameter=self.type,
            type=type,
        )
        return GivenTypeParameter(
            name=self.name,
            parameter=self.parameter,
            type=innter_parameter,
        )


@attr.s(kw_only=True, slots=True)
class PolymorphicType(AnalyzedType):
    initial_type: typing.Optional[typing.Self] = attr.ib(default=None, repr=False)
    parameters: typing.List[
        typing.Union[TypeParameter, GivenTypeParameter]
    ] = attr.ib(factory=list)

    def add_trait_table(self, trait_table: TraitTable) -> None:
        initial_type = self.get_initial_type()
        initial_type.trait_tables.append(trait_table)

    def get_trait_table(self, trait: TypeTrait) -> typing.Optional[TraitTable]:
        initial_type = self.get_initial_type()
        for table in initial_type.trait_tables:
            if table.trait.is_compatible_with(trait):
                return table.with_owner(self)

    def is_compatible_with(self, type: AnalyzedType) -> bool:
        if not isinstance(type, PolymorphicType):
            return False

        if self.get_initial_type() is not type.get_initial_type():
            return False

        parameters = zip(self.parameters, type.parameters)
        for parameter1, parameter2 in parameters:
            if not parameter1.is_compatible_with(parameter2):
                return False

        return True

    def get_string(self, *, top_level: bool = True) -> str:
        parameters = ', '.join(
            parameter.get_string(top_level=False) for parameter in self.parameters
        )
        return f'{self.name}({parameters})'

    def get_initial_type(self) -> typing.Self:
        return self.initial_type if self.initial_type is not None else self

    def is_polymorphic(self) -> bool:
        return any(self.uninitialized_parameters())

    def all_parameters_given(self) -> bool:
        return all(isinstance(parameter, GivenTypeParameter) for parameter in self.parameters)

    def uninitialized_parameters(self) -> typing.Generator[TypeParameter]:
        # TODO: FIX THIS
        for parameter in self.parameters:
            match parameter:
                case TypeParameter():
                    yield parameter
                case GivenTypeParameter():
                    if isinstance(parameter.type, TypeParameter):
                        yield parameter.type        

    def with_parameters(self, parameters: typing.List[AnalyzedType]) -> typing.Self:
        initial_type = self.get_initial_type()
        if len(parameters) != len(initial_type.parameters):
            raise ValueError(f'with_parameters(): must pass the same number of parameters')

        given_parameters: typing.List[GivenTypeParameter] = []

        for parameter, given_parameter in zip(self.parameters, parameters):
            if isinstance(parameter, GivenTypeParameter):
                new_parameter = parameter.with_type(given_parameter)
            else:
                new_parameter = GivenTypeParameter(
                    name=f'{parameter.name}@{given_parameter.name}',
                    parameter=parameter,
                    type=given_parameter,
                )

            given_parameters.append(new_parameter)

        cls = type(self)
        return cls(
            initial_type=initial_type,
            name=self.name,
            parameters=given_parameters,
        )


@attr.s(kw_only=True, slots=True)
class SelfType(AnalyzedType):
    name: str = attr.ib(default='Self', init=False)
    owner: AnalyzedType = attr.ib(default=UNKNOWN, repr=str)


@attr.s(kw_only=True, slots=True)
class TypeTrait(PolymorphicType):
    tr_functions: typing.List[FunctionType] = attr.ib(factory=list)


@attr.s(kw_only=True, slots=True)
class FunctionParameter:
    name: str = attr.ib()
    type: AnalyzedType = attr.ib()
    # TODO: default
    # kw_only, etc.


@attr.s(kw_only=True, slots=True)
class FunctionType(PolymorphicType):
    # XXX: Make sure we never store the result of bind_with_parameters
    # do everything lazily
    propagated: bool = attr.ib(default=True)
    # PolymorphicType fields must be filled regardless of propagation
    fn_self: typing.Optional[SelfType] = attr.ib(default=None)
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

    def get_parameter_type(
        self,
        name: str,
        owner: PolymorphicType,
    ) -> AnalyzedType:
        if owner.all_parameters_given():
            assert False, '<The owner is missing a parameter...>'

        for parameter in self.fn_parameters:
            if parameter.name != name:
                continue

            return parameter.type.bind_with_parameters(owner)

        assert False, f'<No parameter {name!r}>'

    def get_return_type(self, owner: PolymorphicType) -> AnalyzedType:
        return self.fn_returns.bind_with_parameters(owner)


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


# TODO: Clean everything below this up

class TypeBuilderKind(enum.Enum):
    BASIC = enum.auto()
    POLYMORPHIC = enum.auto()
    FUNCTION = enum.auto()
    CLASS = enum.auto()
    TRAIT = enum.auto()
    TRAIT_TABLE = enum.auto()


@attr.s(kw_only=True, slots=True)
class _UnknownTypeParameter(AnalyzedType):
    # This class is used to represent Self and type parameters before they are created.
    # The resolver function is called after the actual type is created.
    # This allows for something like f(x: |T|) -> [T], which becomes:
    # TypeBuilder.new_function()
    #   .add_type_parameter('T')
    #   .add_parameter('x', 'T')
    #   .add_return_type('T', lambda type: LIST.with_parameters([type]))
    resolver: typing.Optional[typing.Callable[[AnalyzedType], AnalyzedType]] = attr.ib(default=None)

    def resolve(self, types: typing.Dict[str, AnalyzedType]) -> AnalyzedType:
        type = types[self.name]
        if self.resolver is not None:
            return self.resolver(type)

        return type


class TypeBuilder(typing.Generic[T]):
    def __init__(self, name: str, kind: TypeBuilderKind) -> None:
        self.name = name
        self.kind = kind

        if self.kind is not TypeBuilderKind.BASIC:
            self.parameters: typing.List[typing.Tuple[str, typing.Optional[AnalyzedType]]] = []

        match self.kind:
            case TypeBuilderKind.FUNCTION:
                self.fn_parameters: typing.List[FunctionParameter] = []
                self.fn_self = None
                self.fn_returns = None

            case TypeBuilderKind.CLASS:
                self.cls_attributes: typing.List[ClassAttribute] = []
                self.cls_functions: typing.List[FunctionType] = []

            case TypeBuilderKind.TRAIT:
                self.tr_functions: typing.List[FunctionType] = []
            
            case TypeBuilderKind.TRAIT_TABLE:
                self.tb_functions: typing.List[FunctionType] = []
                self.tb_trait: TypeTrait

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

    @classmethod
    def new_trait_table(
        cls: typing.Type[TypeBuilder[TraitTable]],
        trait: TypeTrait,
    ) -> TypeBuilder[TraitTable]:
        builder = cls(trait.name, TypeBuilderKind.TRAIT_TABLE)
        builder.tb_trait = trait
        return builder

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

            if parameter.type.name == 'Self':
                if function.fn_self is None:
                    function.fn_self = SelfType()

                parameter.type = parameter.type.resolve({'Self': function.fn_self})

            elif parameter.type.name in type_parameters:
                parameter.type = parameter.type.resolve(type_parameters)

            elif not allow_unknown:
                raise ValueError(
                    f'Encountered unknown paramater {parameter.name}: '
                    f'{parameter.type.name} in {function.name}'
                )

        if isinstance(function.fn_returns, _UnknownTypeParameter):
            if function.fn_returns.name == 'Self':
                if function.fn_self is None:
                    raise ValueError(f'{function.name} must accept Self')

                function.fn_returns = function.fn_returns.resolve({'Self': function.fn_self})

            elif function.fn_returns.name in type_parameters:
                function.fn_returns = function.fn_returns.resolve(type_parameters)

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
                        attribute.type = attribute.type.resolve(type_parameters)

                    elif not allow_unknown:
                        raise ValueError(
                            f'Encountered unknown attribute {attribute.name}: '
                            f'{attribute.type.name} in {type.name}'
                        )

                for function in self.cls_functions:
                    if function.fn_self is not None:
                        function.fn_self.owner = type

                    self.update_function_types(type_parameters, function, allow_unknown)

            case TypeTrait():
                for function in self.tr_functions:
                    if function.fn_self is not None:
                        function.fn_self.owner = type

                    self.update_function_types(type_parameters, function, allow_unknown)

    def build_type(self, *, nested: bool = False) -> T:
        # This function creates the type and the type parameters,
        # then replaces the temporary instances of _UnknownTypeParameter.
        # If nested is set to True, this function will not raise an exception
        # for any unresolved type parameters. This allows nested types to use
        # type parameters from their parent types.
        if self.kind is TypeBuilderKind.TRAIT_TABLE:
            raise ValueError('build_type() is not for trait tables')

        match self.kind:
            case TypeBuilderKind.BASIC:
                return typing.cast(T, AnalyzedType(name=self.name))

            case TypeBuilderKind.POLYMORPHIC:
                type = PolymorphicType(name=self.name)

            case TypeBuilderKind.FUNCTION:
                if self.fn_returns is None:
                    raise ValueError('function requires return type')

                type = FunctionType(
                    name=self.name,
                    fn_parameters=self.fn_parameters,
                    fn_returns=self.fn_returns,
                )

                if self.fn_self is not None:
                    self.fn_self.owner = type

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

    def build_table(self, type: AnalyzedType) -> TraitTable:
        if self.kind is not TypeBuilderKind.TRAIT_TABLE:
            raise ValueError('build_table() is for trait tables')

        parameters = self.build_type_parameters(type)
        type_parameters = {parameter.name: parameter for parameter in parameters}

        for function in self.tb_functions:
            if function.fn_self is not None:
                function.fn_self.owner = type

            self.update_function_types(type_parameters, function, False)

        functions = {function.name: function for function in self.tb_functions}

        table = TraitTable(trait=self.tb_trait, functions=functions)
        type.trait_tables.append(table)
        return table

    def add_type_parameter(
        self, name: str, constraint: typing.Optional[AnalyzedType] = None
    ) -> typing.Self:
        self.parameters.append((name, constraint))
        return self

    def add_parameter(
        self,
        name: str,
        type: typing.Union[AnalyzedType, str],
        resolver: typing.Optional[typing.Callable[[AnalyzedType], AnalyzedType]] = None,
    ) -> typing.Self:
        if self.kind is not TypeBuilderKind.FUNCTION:
            raise TypeError('add_parameter() is for functions')

        if isinstance(type, str):
            type = _UnknownTypeParameter(name=type, resolver=resolver)
        elif resolver is not None:
            raise ValueError('type must be a string to use a resolver')

        self.fn_parameters.append(FunctionParameter(name=name, type=type))
        return self

    def add_return_type(
        self,
        type: typing.Union[str, AnalyzedType],
        resolver: typing.Optional[typing.Callable[[AnalyzedType], AnalyzedType]] = None,
    ) -> typing.Self:
        if self.kind is not TypeBuilderKind.FUNCTION:
            raise TypeError('add_return_type() is for functions')

        if isinstance(type, str):
            type = _UnknownTypeParameter(name=type, resolver=resolver)
        elif resolver is not None:
            raise ValueError('type must be a string to use a resolver')

        self.fn_returns = type
        return self

    def add_function(self, function: FunctionType) -> typing.Self:
        if self.kind is TypeBuilderKind.CLASS:
            self.cls_functions.append(function)
        elif self.kind is TypeBuilderKind.TRAIT:
            self.tr_functions.append(function)
        elif self.kind is TypeBuilderKind.TRAIT_TABLE:
            self.tb_functions.append(function)
        else:
            raise TypeError('add_function() is for functions and traits')

        return self

    def add_attribute(
        self,
        name: str,
        type: typing.Union[AnalyzedType, str],
        resolver: typing.Optional[typing.Callable[[AnalyzedType], AnalyzedType]] = None,
    ) -> typing.Self:
        if self.kind is not TypeBuilderKind.CLASS:
            raise TypeError('add_attribute() is for classes')

        if isinstance(type, str):
            type = _UnknownTypeParameter(name=name, resolver=resolver)
        elif resolver is not None:
            raise ValueError('type must be a string to use a resolver')

        self.cls_attributes.append(ClassAttribute(name=name, type=type))
        return self


class BuiltinTypes:
    # This is meant as a placeholder when the analyzer
    # doesn't care about a type
    ANY = TypeBuilder.new_type('Any').build_type()

    NONE_TYPE = TypeBuilder.new_type('NoneType').build_type()
    NONE = NONE_TYPE.to_instance()

    BOOL = TypeBuilder.new_type('bool').build_type()
    TRUE = BOOL.to_instance(True)
    FALSE = BOOL.to_instance(False)

    INT = TypeBuilder.new_type('int').build_type()
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


def create_binary_operator(name: str, function: str) -> TypeTrait:
    return (
        TypeBuilder.new_trait(name)
        .add_type_parameter('T')
        .add_type_parameter('U')
        .add_function(
            TypeBuilder.new_function(function)
            .add_parameter('self', 'Self')
            .add_parameter('rhs', 'T')
            .add_return_type('U')
            .build_type(nested=True)
        )
        .build_type()
    )


def create_unary_operator(name: str, function: str) -> TypeTrait:
    return (
        TypeBuilder.new_trait(name)
        .add_type_parameter('T')
        .add_function(
            TypeBuilder.new_function(function)
            .add_parameter('self', 'Self')
            .add_return_type('T')
            .build_type(nested=True)
        )
        .build_type()
    )


class BuiltinTraits:
    HASH = (
        TypeBuilder.new_trait('Hash')
        .add_function(
            TypeBuilder.new_function('hash')
            .add_parameter('self', 'Self')
            .add_return_type(BuiltinTypes.STR)
            .build_type(nested=True)
        )
        .build_type()
    )

    ITER = (
        TypeBuilder.new_trait('Iter')
        .add_type_parameter('T')
        .add_function(
            TypeBuilder.new_function('next')
            .add_parameter('self', 'Self')
            .add_return_type('T')
            .build_type(nested=True)
        )
        .build_type()
    )

    ADD = create_binary_operator('Add', 'add')
    SUB = create_binary_operator('Sub', 'sub')
    MULT = create_binary_operator('Mult', 'mult')
    MATMULT = create_binary_operator('Matmult', 'matmult')
    DIV = create_binary_operator('Div', 'div')
    MOD = create_binary_operator('Mod', 'mod')
    POW = create_binary_operator('Pow', 'pow')
    LSHIFT = create_binary_operator('LShift', 'lshift')
    RSHIFT = create_binary_operator('RShift', 'rshift')
    BITOR = create_binary_operator('BitOr', 'bitor')
    BITXOR = create_binary_operator('BitXOr', 'bitxor')
    BITAND = create_binary_operator('BitAnd', 'bitand')
    FLOORDIV = create_binary_operator('FloorDiv', 'floordiv')

    BINARY_OPERATORS = (
        ADD,
        SUB,
        MULT,
        MATMULT,
        DIV,
        MOD,
        POW,
        LSHIFT,
        RSHIFT,
        BITOR,
        BITXOR,
        BITAND,
        FLOORDIV,
    )

    INVERT = create_unary_operator('Invert', 'invert')
    UADD = create_unary_operator('UAdd', 'uadd')
    USUB = create_unary_operator('USub', 'usub')

    UNARY_OPERATORS = (
        INVERT,
        UADD,
        USUB,
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



def create_unary_table(
    trait: TypeTrait,
    type: AnalyzedType,
    output: AnalyzedType,
) -> TraitTable:
    return (
        TypeBuilder.new_trait_table(
            trait.with_parameters([output])
        )
        .add_function(
            TypeBuilder.new_function(trait.name.lower()) # XXX: Get the name elsewhere
            .add_parameter('self', 'Self')
            .add_return_type(type)
            .build_type(nested=True)
        )
        .build_table(type)
    )


def create_binary_table(
    trait: TypeTrait,
    type: AnalyzedType,
    rhs: AnalyzedType,
    output: AnalyzedType,
) -> TraitTable:
    return (
        TypeBuilder.new_trait_table(
            trait.with_parameters([rhs, output])
        )
        .add_function(
            TypeBuilder.new_function(trait.name.lower())
            .add_parameter('self', 'Self')
            .add_parameter('rhs', rhs)
            .add_return_type(output)
            .build_type(nested=True)
        )
        .build_table(type)
    )


def create_unary_tables(
    traits: typing.Iterable[TypeTrait],
    type: AnalyzedType,
    output: AnalyzedType,
) -> None:
    for trait in traits:
        create_unary_table(trait, type, output)


def create_binary_tables(
    traits: typing.Iterable[TypeTrait],
    type: AnalyzedType,
    rhs: AnalyzedType,
    output: AnalyzedType,
) -> None:
    for trait in traits:
        create_binary_table(trait, type, rhs, output)


create_unary_tables(BuiltinTraits.UNARY_OPERATORS, BuiltinTypes.INT, BuiltinTypes.INT) # +int
create_unary_tables((BuiltinTraits.UADD, BuiltinTraits.USUB), BuiltinTypes.FLOAT, BuiltinTypes.FLOAT) # +float

create_binary_tables(
    (
        BuiltinTraits.ADD, # int + int
        BuiltinTraits.SUB,
        BuiltinTraits.MULT,
        BuiltinTraits.DIV,
        BuiltinTraits.MOD,
        BuiltinTraits.POW,
        BuiltinTraits.LSHIFT,
        BuiltinTraits.RSHIFT,
        BuiltinTraits.BITOR,
        BuiltinTraits.BITXOR,
        BuiltinTraits.BITAND,
        BuiltinTraits.FLOORDIV,
    ), 
    BuiltinTypes.INT, BuiltinTypes.INT, BuiltinTypes.INT
)
create_binary_tables(
    (
        BuiltinTraits.ADD, # int + float
        BuiltinTraits.SUB,
        BuiltinTraits.MULT,
        BuiltinTraits.DIV,
        BuiltinTraits.MOD,
        BuiltinTraits.POW,
    ),
    BuiltinTypes.INT, BuiltinTypes.FLOAT, BuiltinTypes.FLOAT
)

create_binary_tables(
    (
        BuiltinTraits.ADD, # float + float
        BuiltinTraits.SUB,
        BuiltinTraits.MULT,
        BuiltinTraits.DIV,
        BuiltinTraits.MOD,
        BuiltinTraits.POW,
    ),
    BuiltinTypes.FLOAT, BuiltinTypes.FLOAT, BuiltinTypes.FLOAT
)
create_binary_tables(
    (
        BuiltinTraits.ADD, # float + int
        BuiltinTraits.SUB,
        BuiltinTraits.MULT,
        BuiltinTraits.DIV,
        BuiltinTraits.MOD,
        BuiltinTraits.POW,
    ),
    BuiltinTypes.FLOAT, BuiltinTypes.INT, BuiltinTypes.FLOAT
)


elt_type = TypeParameter(name='T', owner=BuiltinTypes.INT)
TypeBuilder.new_trait_table(
    BuiltinTraits.ITER.with_parameters([elt_type])
).add_function(
    TypeBuilder.new_function('next')
    .add_parameter('self', 'Self')
    .add_return_type(elt_type)
    .build_type()
).build_table(BuiltinTypes.LIST)

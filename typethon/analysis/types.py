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

    def bind_to(self, type: PolymorphicType) -> typing.Self:
        # Binds the type to a PolymorphicType
        # * For basic types, this simply means returning the type.
        # * For type parameters, this means returning whatever the parameter maps to
        # within the type. For example, if we have a class that is polymorhic over T,
        # calling T.bind_to(Class(int)) should result in int.
        # * For other polymorphic types, this means binding each of the parameters
        # with the other type. For example, [T].bind_to(Class(int)) should result in int.
        # * For function types, this meaning binding each of the argument and the
        # return type to the type. For example, (f(x: T) -> T).bind_to(Class(int))
        # should result in f(x: int) -> int
        return self


@attr.s(kw_only=True, slots=True)
class TraitTable:
    trait: TypeTrait = attr.ib()
    owner: typing.Optional[PolymorphicType] = attr.ib(default=None, repr=str)
    functions: typing.Dict[str, FunctionType] = attr.ib()

    def get_function(self, name: str) -> FunctionType:
        if name not in self.functions:
            assert False, f'<Trait table has no function {name}>'

        function = self.functions[name]
        if self.owner is not None:
            return function.bind_to(self.owner)

        return function

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
    owner: AnalyzedType = attr.ib(default=UNKNOWN, eq=False)  # False because of recursion
    constraint: typing.Optional[AnalyzedType] = attr.ib(default=None)
    # TODO: Figure out when type parameters should be considered equal for binding
    # Overall, the current mechanism for finding type parameters is awful and error
    # prone.

    def get_string(self, *, top_level: bool = True) -> str:
        if top_level:
            owner = self.owner.get_string(top_level=False)
            name = f'{self.name}@{owner}'
        else:
            name = self.name

        if self.constraint is not None:
            return f'|{name}: {self.constraint}|'

        return f'|{name}|'

    def bind_to(self, type: PolymorphicType) -> AnalyzedType:
        mapped_parameter = type.get_mapped_parameter(self)
        if mapped_parameter is not None:
            return mapped_parameter

        return self


@attr.s(kw_only=True, slots=True)
class PolymorphicType(AnalyzedType):
    initial_type: typing.Optional[typing.Self] = attr.ib(default=None, repr=False)
    parameters: typing.List[AnalyzedType] = attr.ib(factory=list)

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

    def get_mapped_parameter(self, parameter: TypeParameter) -> typing.Optional[AnalyzedType]:
        initial_type = self.get_initial_type()

        parameters = zip(initial_type.parameters, self.parameters)
        for initial_parameter, mapped_parameter in parameters:
            if not isinstance(initial_parameter, TypeParameter):
                assert False, '<The initial type is broken>'

            if initial_parameter is parameter: # FIXME?
                return mapped_parameter

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

    def with_parameters(self, parameters: typing.List[AnalyzedType]) -> typing.Self:
        initial_type = self.get_initial_type()
        if len(parameters) != len(initial_type.parameters):
            raise ValueError(f'with_parameters(): must pass the same number of parameters')

        for parameter in parameters:
            if (
                isinstance(parameter, TypeParameter)
                and parameter.owner is initial_type
            ):
                assert False, '<Cannot reuse parameter>'  # Sanity check

        cls = type(self)
        return cls(initial_type=initial_type, name=self.name, parameters=parameters)

    def bind_to(self, type: PolymorphicType) -> typing.Self:
        parameters: typing.List[AnalyzedType] = []

        for parameter in self.parameters:
            parameters.append(parameter.bind_to(type))

        return self.with_parameters(parameters)


@attr.s(kw_only=True, slots=True)
class SelfType(AnalyzedType):
    name: str = attr.ib(default='Self', init=False)
    owner: AnalyzedType = attr.ib(default=UNKNOWN, repr=str)

    def bind_to(self, type: PolymorphicType) -> SelfType:
        return SelfType(owner=type)


@attr.s(kw_only=True, slots=True)
class TypeTrait(PolymorphicType):
    tr_functions: typing.List[FunctionType] = attr.ib(factory=list)

    def with_parameters(self, parameters: typing.List[AnalyzedType]) -> typing.Self:
        trait = super().with_parameters(parameters)

        for tr_function in self.tr_functions:
            trait.tr_functions.append(tr_function.bind_to(trait))

        return trait


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

    def with_parameters(self, parameters: typing.List[AnalyzedType]) -> typing.Self:
        function = super().with_parameters(parameters)

        function.fn_self = self.fn_self
        function.fn_returns = self.fn_returns.bind_to(function)

        for fn_parameter in self.fn_parameters:
            parameter = FunctionParameter(
                name=fn_parameter.name,
                type=fn_parameter.type.bind_to(function),
            )
            function.fn_parameters.append(parameter)

        return function

    def bind_to(self, type: PolymorphicType) -> typing.Self:
        # Unlike the basic polymorphic types, functions type parameters
        # cannot overlap with any other type's as they can only define their own.
        # However, their arguments and return types can overlap with another type's.
        # As a result, we simply reuse our own parameters and bind the arguments
        # and return types with the other type.
        function = self.with_parameters(self.parameters)

        function.fn_returns = self.fn_returns.bind_to(type)
        if self.fn_self is not None:
            function.fn_self = self.fn_self.bind_to(type)

        for fn_parameter in function.fn_parameters:
            fn_parameter.type = fn_parameter.type.bind_to(type)

        return function


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

    def with_parameters(self, parameters: typing.List[AnalyzedType]) -> typing.Self:
        cls = super().with_parameters(parameters)

        for cls_attribute in self.cls_attributes:
            attribute = ClassAttribute(
                name=cls_attribute.name,
                type=cls_attribute.type.bind_to(cls)
            )
            cls.cls_attributes.append(attribute)

        for cls_function in self.cls_functions:
            cls.cls_functions.append(cls_function.bind_to(cls))

        return cls


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

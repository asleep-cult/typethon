from __future__ import annotations

import attr
import enum
import typing

from . import types


T = typing.TypeVar('T')
# TODO: Refactor this code


class TypeBuilderKind(enum.Enum):
    BASIC = enum.auto()
    POLYMORPHIC = enum.auto()
    FUNCTION = enum.auto()
    CLASS = enum.auto()
    TRAIT = enum.auto()
    TRAIT_TABLE = enum.auto()


@attr.s(kw_only=True, slots=True)
class _UnknownTypeParameter(types.AnalyzedType):
    # This class is used to represent Self and type parameters before they are created.
    # The resolver function is called after the actual type is created.
    # This allows for something like f(x: |T|) -> [T], which becomes:
    # TypeBuilder.new_function()
    #   .add_type_parameter('T')
    #   .add_parameter('x', 'T')
    #   .add_return_type('T', lambda type: LIST.with_parameters([type]))
    resolver: typing.Optional[typing.Callable[[types.AnalyzedType], types.AnalyzedType]] = attr.ib(default=None)

    def resolve(self, types: typing.Dict[str, types.AnalyzedType]) -> types.AnalyzedType:
        type = types[self.name]
        if self.resolver is not None:
            return self.resolver(type)

        return type


class TypeBuilder(typing.Generic[T]):
    def __init__(self, name: str, kind: TypeBuilderKind) -> None:
        self.name = name
        self.kind = kind

        if self.kind is not TypeBuilderKind.BASIC:
            self.parameters: typing.List[typing.Tuple[str, typing.Optional[types.AnalyzedType]]] = []

        match self.kind:
            case TypeBuilderKind.FUNCTION:
                self.fn_parameters: typing.Dict[str, types.FunctionParameter] = {}
                self.fn_self = None
                self.fn_returns = None

            case TypeBuilderKind.CLASS:
                self.cls_attributes: typing.Dict[str, types.ClassAttribute] = {}
                self.cls_functions: typing.Dict[str, types.FunctionType] = {}

            case TypeBuilderKind.TRAIT:
                self.tr_functions: typing.Dict[str, types.FunctionType] = {}
            
            case TypeBuilderKind.TRAIT_TABLE:
                self.tb_functions: typing.List[types.FunctionType] = []
                self.tb_trait: types.TypeTrait

    @classmethod
    def new_type(
        cls: typing.Type[TypeBuilder[types.AnalyzedType]], name: str
    ) -> TypeBuilder[types.AnalyzedType]:
        return cls(name, TypeBuilderKind.BASIC)

    @classmethod
    def new_polymorphic_type(
        cls: typing.Type[TypeBuilder[types.PolymorphicType]], name: str
    ) -> TypeBuilder[types.PolymorphicType]:
        return cls(name, TypeBuilderKind.POLYMORPHIC)

    @classmethod
    def new_function(
        cls: typing.Type[TypeBuilder[types.FunctionType]], name: str
    ) -> TypeBuilder[types.FunctionType]:
        return cls(name, TypeBuilderKind.FUNCTION)

    @classmethod
    def new_class(
        cls: typing.Type[TypeBuilder[types.ClassType]], name: str
    ) -> TypeBuilder[types.ClassType]:
        return TypeBuilder(name, TypeBuilderKind.CLASS)

    @classmethod
    def new_trait(
        cls: typing.Type[TypeBuilder[types.TypeTrait]], name: str
    ) -> TypeBuilder[types.TypeTrait]:
        return cls(name, TypeBuilderKind.TRAIT)

    @classmethod
    def new_trait_table(
        cls: typing.Type[TypeBuilder[types.TraitTable]],
        trait: types.TypeTrait,
    ) -> TypeBuilder[types.TraitTable]:
        builder = cls(trait.name, TypeBuilderKind.TRAIT_TABLE)
        builder.tb_trait = trait
        return builder

    def build_type_parameters(self, owner: types.AnalyzedType) -> typing.Generator[types.TypeParameter]:
        for name, constraint in self.parameters:
            yield types.TypeParameter(name=name, owner=owner, constraint=constraint)

    def update_function_types(
        self,
        type_parameters: typing.Dict[str, types.AnalyzedType],
        function: types.FunctionType,
        allow_unknown: bool
    ) -> None:
        for parameter in function.fn_parameters.values():
            if not isinstance(parameter.type, _UnknownTypeParameter):
                continue

            if parameter.type.name == 'Self':
                if function.fn_self is None:
                    function.fn_self = types.SelfType()

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
        type: types.PolymorphicType,
        allow_unknown: bool
    ) -> None:
        type_parameters = {parameter.name: parameter for parameter in type.parameters}

        match type:
            case types.FunctionType():
                self.update_function_types(type_parameters, type, allow_unknown)

            case types.ClassType():
                for attribute in self.cls_attributes.values():
                    if not isinstance(attribute.type, _UnknownTypeParameter):
                        continue

                    if attribute.type.name in type_parameters:
                        attribute.type = attribute.type.resolve(type_parameters)

                    elif not allow_unknown:
                        raise ValueError(
                            f'Encountered unknown attribute {attribute.name}: '
                            f'{attribute.type.name} in {type.name}'
                        )

                for function in self.cls_functions.values():
                    if function.fn_self is not None:
                        function.fn_self.owner = type

                    self.update_function_types(type_parameters, function, allow_unknown)

            case types.TypeTrait():
                for function in self.tr_functions.values():
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
                return typing.cast(T, types.AnalyzedType(name=self.name))

            case TypeBuilderKind.POLYMORPHIC:
                type = types.PolymorphicType(name=self.name)

            case TypeBuilderKind.FUNCTION:
                if self.fn_returns is None:
                    raise ValueError('function requires return type')

                type = types.FunctionType(
                    name=self.name,
                    fn_parameters=self.fn_parameters,
                    fn_returns=self.fn_returns,
                )

                if self.fn_self is not None:
                    self.fn_self.owner = type

            case TypeBuilderKind.CLASS:
                type = types.ClassType(
                    name=self.name,
                    cls_attributes=self.cls_attributes,
                    cls_functions=self.cls_functions,
                )

            case TypeBuilderKind.TRAIT:
                type = types.TypeTrait(name=self.name, tr_functions=self.tr_functions)

        type.parameters.extend(self.build_type_parameters(type))
        self.update_unknown_parameters(type, allow_unknown=nested)

        return typing.cast(T, type)

    def build_table(self, type: types.AnalyzedType) -> types.TraitTable:
        if self.kind is not TypeBuilderKind.TRAIT_TABLE:
            raise ValueError('build_table() is for trait tables')

        parameters = self.build_type_parameters(type)
        type_parameters = {parameter.name: parameter for parameter in parameters}

        for function in self.tb_functions:
            if function.fn_self is not None:
                function.fn_self.owner = type

            self.update_function_types(type_parameters, function, False)

        functions = {function.name: function for function in self.tb_functions}

        table = types.TraitTable(trait=self.tb_trait, functions=functions)
        type.add_trait_table(table)
        return table

    def add_type_parameter(
        self, name: str, constraint: typing.Optional[types.AnalyzedType] = None
    ) -> typing.Self:
        self.parameters.append((name, constraint))
        return self

    def add_parameter(
        self,
        name: str,
        type: typing.Union[types.AnalyzedType, str],
        resolver: typing.Optional[typing.Callable[[types.AnalyzedType], types.AnalyzedType]] = None,
    ) -> typing.Self:
        if self.kind is not TypeBuilderKind.FUNCTION:
            raise TypeError('add_parameter() is for functions')

        if isinstance(type, str):
            type = _UnknownTypeParameter(name=type, resolver=resolver)
        elif resolver is not None:
            raise ValueError('type must be a string to use a resolver')

        self.fn_parameters[name] = types.FunctionParameter(name=name, type=type)
        return self

    def add_return_type(
        self,
        type: typing.Union[str, types.AnalyzedType],
        resolver: typing.Optional[typing.Callable[[types.AnalyzedType], types.AnalyzedType]] = None,
    ) -> typing.Self:
        if self.kind is not TypeBuilderKind.FUNCTION:
            raise TypeError('add_return_type() is for functions')

        if isinstance(type, str):
            type = _UnknownTypeParameter(name=type, resolver=resolver)
        elif resolver is not None:
            raise ValueError('type must be a string to use a resolver')

        self.fn_returns = type
        return self

    def add_function(self, function: types.FunctionType) -> typing.Self:
        if self.kind is TypeBuilderKind.CLASS:
            self.cls_functions[function.name] = function
        elif self.kind is TypeBuilderKind.TRAIT:
            self.tr_functions[function.name] = function
        elif self.kind is TypeBuilderKind.TRAIT_TABLE:
            self.tb_functions.append(function)
        else:
            raise TypeError('add_function() is for functions and traits')

        return self

    def add_attribute(
        self,
        name: str,
        type: typing.Union[types.AnalyzedType, str],
        resolver: typing.Optional[typing.Callable[[types.AnalyzedType], types.AnalyzedType]] = None,
    ) -> typing.Self:
        if self.kind is not TypeBuilderKind.CLASS:
            raise TypeError('add_attribute() is for classes')

        if isinstance(type, str):
            type = _UnknownTypeParameter(name=name, resolver=resolver)
        elif resolver is not None:
            raise ValueError('type must be a string to use a resolver')

        self.cls_attributes[name] = types.ClassAttribute(name=name, type=type)
        return self


class Types:
    # This is meant as a placeholder when the analyzer
    # doesn't care about a type

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

    DICT: types.PolymorphicType
    SET: types.PolymorphicType


def create_binary_operator(name: str, function: str) -> types.TypeTrait:
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


def create_unary_operator(name: str, function: str) -> types.TypeTrait:
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


class Traits:
    HASH = (
        TypeBuilder.new_trait('Hash')
        .add_function(
            TypeBuilder.new_function('hash')
            .add_parameter('self', 'Self')
            .add_return_type(Types.STR)
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


Types.DICT = (
    TypeBuilder.new_polymorphic_type('dict')
    .add_type_parameter('K', Traits.HASH)
    .add_type_parameter('V')
    .build_type()
)
Types.SET = (
    TypeBuilder.new_polymorphic_type('set')
    .add_type_parameter('T', Traits.HASH)
    .build_type()
)



def create_unary_table(
    trait: types.TypeTrait,
    type: types.AnalyzedType,
    output: types.AnalyzedType,
) -> types.TraitTable:
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
    trait: types.TypeTrait,
    type: types.AnalyzedType,
    rhs: types.AnalyzedType,
    output: types.AnalyzedType,
) -> types.TraitTable:
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
    traits: typing.Iterable[types.TypeTrait],
    type: types.AnalyzedType,
    output: types.AnalyzedType,
) -> None:
    for trait in traits:
        create_unary_table(trait, type, output)


def create_binary_tables(
    traits: typing.Iterable[types.TypeTrait],
    type: types.AnalyzedType,
    rhs: types.AnalyzedType,
    output: types.AnalyzedType,
) -> None:
    for trait in traits:
        create_binary_table(trait, type, rhs, output)


create_unary_tables(Traits.UNARY_OPERATORS, Types.INT, Types.INT) # +int
create_unary_tables((Traits.UADD, Traits.USUB), Types.FLOAT, Types.FLOAT) # +float

create_binary_tables(
    (
        Traits.ADD, # int + int
        Traits.SUB,
        Traits.MULT,
        Traits.MOD,
        Traits.POW,
        Traits.LSHIFT,
        Traits.RSHIFT,
        Traits.BITOR,
        Traits.BITXOR,
        Traits.BITAND,
        Traits.FLOORDIV,
    ), 
    Types.INT, Types.INT, Types.INT
)

create_binary_table(
    Traits.DIV,
    Types.INT,
    Types.INT,
    Types.FLOAT,
)

create_binary_tables(
    (
        Traits.ADD, # int + float
        Traits.SUB,
        Traits.MULT,
        Traits.DIV,
        Traits.MOD,
        Traits.POW,
    ),
    Types.INT, Types.FLOAT, Types.FLOAT
)

create_binary_tables(
    (
        Traits.ADD, # float + float
        Traits.SUB,
        Traits.MULT,
        Traits.DIV,
        Traits.MOD,
        Traits.POW,
    ),
    Types.FLOAT, Types.FLOAT, Types.FLOAT
)
create_binary_tables(
    (
        Traits.ADD, # float + int
        Traits.SUB,
        Traits.MULT,
        Traits.DIV,
        Traits.MOD,
        Traits.POW,
    ),
    Types.FLOAT, Types.INT, Types.FLOAT
)

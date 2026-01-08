from __future__ import annotations

import typing
import inspect

from . import types


class TypeBuilder:
    @staticmethod
    def new_type(name: str) -> types.AnalyzedType:
        return types.AnalyzedType(name=name)

    @staticmethod
    def new_function(
        name: str,
        *parameters: types.TypeParameter,
        returns: types.AnalyzedType,
        **kwargs: types.AnalyzedType
    ) -> types.FunctionType:
        fn_parameters: typing.Dict[str, types.FunctionParameter] = {}

        for parameter_name, type in kwargs.items():
            fn_parameters[parameter_name] = types.FunctionParameter(
                name=parameter_name, type=type
            )

        return types.FunctionType(
            name=name,
            parameters=list(parameters),
            fn_parameters=fn_parameters,
            fn_returns=returns,
        )

    @staticmethod
    def new_type_parameter(
        name: str,
        constraint: typing.Optional[types.TypeTrait] = None
    ) -> types.TypeParameter:
        return types.TypeParameter(name=name, constraint=constraint)

    @staticmethod
    def new_polymorphic_type(
        name: str,
        *parameters: types.TypeParameter
    ) -> types.PolymorphicType:
        type = types.PolymorphicType(name=name, parameters=list(parameters))
        for parameter in parameters:
            parameter.owner = type

        return type

    @staticmethod
    def new_trait(
        name: str,
        *parameters: types.TypeParameter,
        **functions: types.FunctionType,
    ) -> types.TypeTrait:
        trait = types.TypeTrait(name=name, parameters=list(parameters), tr_functions=functions)
        for parameter in parameters:
            parameter.owner = trait

        return trait

    @staticmethod
    def new_self_type() -> types.SelfType:
        return types.SelfType()

    @staticmethod
    def new_class(
        name: str,
        *parameters: types.TypeParameter,
        **kwargs: types.AnalyzedType,
    ) -> types.ClassType:
        cls_attributes: typing.Dict[str, types.ClassAttribute] = {}
        cls_functions: typing.Dict[str, types.FunctionType] = {}

        for name, type in kwargs.items():
            if isinstance(type, types.FunctionType):
                cls_functions[name] = type
            else:
                cls_attributes[name] = types.ClassAttribute(name=name, type=type)

        cls = types.ClassType(
            name=name,
            parameters=list(parameters),
            cls_attributes=cls_attributes,
            cls_functions=cls_functions,
        )
        for parameter in parameters:
            parameter.owner = cls

        return cls

    @staticmethod
    def bind_members(type: types.PolymorphicType, cls: type) -> typing.Dict[str, types.FunctionType]:
        members = inspect.getmembers(cls, lambda member: isinstance(member, types.AnalyzedType))
        functions: typing.Dict[str, types.FunctionType] = {}

        for name, member in members:
            match member:
                case types.TypeParameter():
                    member.owner = type
                    type.parameters.append(member)
                case types.FunctionType():
                    member.fn_self = types.SelfType(owner=type)
                    functions[name] = member

        return functions

    @staticmethod
    def trait_from_class(trait_name: str) -> typing.Callable[[type], types.TypeTrait]:
        def wrapped(cls: type) -> types.TypeTrait:
            trait = types.TypeTrait(name=trait_name)

            functions = TypeBuilder.bind_members(trait, cls)
            trait.tr_functions.update(functions)

            return trait
        return wrapped

    @staticmethod
    def new_unaryop_trait(name: str, op: str) -> types.TypeTrait:
        trait = types.TypeTrait(name=name)

        return_type = types.TypeParameter(name='T', owner=trait)
        trait.parameters.append(return_type)

        self_type = types.SelfType(owner=trait)
        function = TypeBuilder.new_function(
            op,
            self=self_type,
            returns=return_type,
        )
        function.fn_self = self_type

        trait.tr_functions[function.name] = function
        return trait

    @staticmethod
    def new_binaryop_trait(name: str, op: str) -> types.TypeTrait:
        trait = types.TypeTrait(name=name)

        rhs_type = types.TypeParameter(name='T', owner=trait)
        return_type = types.TypeParameter(name='U', owner=trait)
        trait.parameters.extend((rhs_type, return_type))

        self_type = types.SelfType(owner=trait)
        function = TypeBuilder.new_function(
            op,
            self=self_type,
            rhs=rhs_type,
            returns=return_type,
        )
        function.fn_self = self_type

        trait.tr_functions[function.name] = function
        return trait

    @staticmethod
    def add_all_traits(type: types.AnalyzedType, *traits: types.TypeTrait) -> None:
        for trait in traits:
            type.add_trait_implementation(trait)


class Types:
    # This is meant as a placeholder when the analyzer
    # doesn't care about a type

    UNIT_TYPE = TypeBuilder.new_type('unit')

    BOOL = TypeBuilder.new_type('bool')
    TRUE = BOOL.to_instance(True)
    FALSE = BOOL.to_instance(False)

    INT = TypeBuilder.new_type('int')
    FLOAT = TypeBuilder.new_type('float')
    COMPLEX = TypeBuilder.new_type('complex')
    STR = TypeBuilder.new_type('str')
    LIST = TypeBuilder.new_polymorphic_type(
        'list',
        TypeBuilder.new_type_parameter('T'),
    )

    DICT: types.PolymorphicType
    SET: types.PolymorphicType


class Ops:
    ADD = TypeBuilder.new_binaryop_trait('Add', 'add')
    SUB = TypeBuilder.new_binaryop_trait('Sub', 'sub')
    MULT = TypeBuilder.new_binaryop_trait('Mult', 'mult')
    MATMULT = TypeBuilder.new_binaryop_trait('Matmult', 'matmult')
    DIV = TypeBuilder.new_binaryop_trait('Div', 'div')
    MOD = TypeBuilder.new_binaryop_trait('Mod', 'mod')
    POW = TypeBuilder.new_binaryop_trait('Pow', 'pow')
    LSHIFT = TypeBuilder.new_binaryop_trait('LShift', 'lshift')
    RSHIFT = TypeBuilder.new_binaryop_trait('RShift', 'rshift')
    BITOR = TypeBuilder.new_binaryop_trait('BitOr', 'bitor')
    BITXOR = TypeBuilder.new_binaryop_trait('BitXOr', 'bitxor')
    BITAND = TypeBuilder.new_binaryop_trait('BitAnd', 'bitand')
    FLOORDIV = TypeBuilder.new_binaryop_trait('FloorDiv', 'floordiv')

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

    INVERT = TypeBuilder.new_unaryop_trait('Invert', 'invert')
    UADD = TypeBuilder.new_unaryop_trait('UAdd', 'uadd')
    USUB = TypeBuilder.new_unaryop_trait('USub', 'usub')

    UNARY_OPERATORS = (
        INVERT,
        UADD,
        USUB,
    )


@TypeBuilder.trait_from_class('Hash')
class Hash:
    self_type = TypeBuilder.new_self_type()
    hash = TypeBuilder.new_function('hash', self=self_type, returns=Types.INT)

Types.DICT = TypeBuilder.new_polymorphic_type(
    'dict',
    TypeBuilder.new_type_parameter('K', Hash),
    TypeBuilder.new_type_parameter('V', Hash),
)

Types.SET = TypeBuilder.new_polymorphic_type(
    'set',
    TypeBuilder.new_type_parameter('T', Hash),
)


@TypeBuilder.trait_from_class('Iter')
class Iter:
    self_type = TypeBuilder.new_self_type()
    next_type = TypeBuilder.new_type_parameter('T')
    next = TypeBuilder.new_function('next', self=self_type, returns=next_type)


@TypeBuilder.trait_from_class('Index')
class Index:
    self_type = TypeBuilder.new_self_type()
    index_type = TypeBuilder.new_type_parameter('T')
    value_type = TypeBuilder.new_type_parameter('V')
    get_item = TypeBuilder.new_function('get_item', self=self_type, index=index_type, returns=value_type)


class Traits:
    HASH = Hash
    ITER = Iter
    INDEX = Index


TypeBuilder.add_all_traits(
    Types.INT,
    Ops.INVERT.with_parameters([Types.INT]),
    Ops.UADD.with_parameters([Types.INT]),
    Ops.USUB.with_parameters([Types.INT]),
    Ops.ADD.with_parameters([Types.INT, Types.INT]),
    Ops.SUB.with_parameters([Types.INT, Types.INT]),
    Ops.MULT.with_parameters([Types.INT, Types.INT]),
    Ops.DIV.with_parameters([Types.INT, Types.FLOAT]),
    Ops.MOD.with_parameters([Types.INT, Types.INT]),
    Ops.POW.with_parameters([Types.INT, Types.INT]),
    Ops.LSHIFT.with_parameters([Types.INT, Types.INT]),
    Ops.RSHIFT.with_parameters([Types.INT, Types.INT]),
    Ops.BITOR.with_parameters([Types.INT, Types.INT]),
    Ops.BITXOR.with_parameters([Types.INT, Types.INT]),
    Ops.BITAND.with_parameters([Types.INT, Types.INT]),
    Ops.FLOORDIV.with_parameters([Types.INT, Types.INT]),

    Ops.ADD.with_parameters([Types.FLOAT, Types.FLOAT]),
    Ops.SUB.with_parameters([Types.FLOAT, Types.FLOAT]),
    Ops.MULT.with_parameters([Types.FLOAT, Types.FLOAT]),
    Ops.DIV.with_parameters([Types.FLOAT, Types.FLOAT]),
    Ops.MOD.with_parameters([Types.FLOAT, Types.FLOAT]),
    Ops.POW.with_parameters([Types.FLOAT, Types.FLOAT]),
)

TypeBuilder.add_all_traits(
    Types.FLOAT,
    Ops.ADD.with_parameters([Types.FLOAT, Types.FLOAT]),
    Ops.SUB.with_parameters([Types.FLOAT, Types.FLOAT]),
    Ops.MULT.with_parameters([Types.FLOAT, Types.FLOAT]),
    Ops.DIV.with_parameters([Types.FLOAT, Types.FLOAT]),
    Ops.MOD.with_parameters([Types.FLOAT, Types.FLOAT]),
    Ops.POW.with_parameters([Types.FLOAT, Types.FLOAT]),

    Ops.ADD.with_parameters([Types.INT, Types.FLOAT]),
    Ops.SUB.with_parameters([Types.INT, Types.FLOAT]),
    Ops.MULT.with_parameters([Types.INT, Types.FLOAT]),
    Ops.DIV.with_parameters([Types.INT, Types.FLOAT]),
    Ops.MOD.with_parameters([Types.INT, Types.FLOAT]),
    Ops.POW.with_parameters([Types.INT, Types.FLOAT]),
)

TypeBuilder.add_all_traits(
    Types.LIST,
    Iter.with_parameters([Types.LIST.parameters[0]]),
    Index.with_parameters([Types.INT, Types.LIST.parameters[0]]),
)

DEBUG = TypeBuilder.new_function('debug', returns=Types.UNIT_TYPE)

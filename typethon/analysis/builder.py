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
        constraint: typing.Optional[types.TypeClass] = None
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
    def new_type_class(
        name: str,
        *parameters: types.TypeParameter,
        **functions: types.FunctionType,
    ) -> types.TypeClass:
        type_class = types.TypeClass(name=name, parameters=list(parameters), cls_functions=functions)
        for parameter in parameters:
            parameter.owner = type_class

        return type_class

    @staticmethod
    def new_self_type() -> types.SelfType:
        return types.SelfType()

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
    def type_class_from_class(class_name: str) -> typing.Callable[[type], types.TypeClass]:
        def wrapped(cls: type) -> types.TypeClass:
            type_class = types.TypeClass(name=class_name)

            functions = TypeBuilder.bind_members(type_class, cls)
            type_class.cls_functions.update(functions)

            return type_class
        return wrapped

    @staticmethod
    def new_unaryop_class(name: str, op: str) -> types.TypeClass:
        type_class = types.TypeClass(name=name)

        return_type = types.TypeParameter(name='T', owner=type_class)
        type_class.parameters.append(return_type)

        self_type = types.SelfType(owner=type_class)
        function = TypeBuilder.new_function(
            op,
            self=self_type,
            returns=return_type,
        )
        function.fn_self = self_type

        type_class.cls_functions[function.name] = function
        return type_class

    @staticmethod
    def new_binaryop_class(name: str, op: str) -> types.TypeClass:
        type_class = types.TypeClass(name=name)

        rhs_type = types.TypeParameter(name='T', owner=type_class)
        return_type = types.TypeParameter(name='U', owner=type_class)
        type_class.parameters.extend((rhs_type, return_type))

        self_type = types.SelfType(owner=type_class)
        function = TypeBuilder.new_function(
            op,
            self=self_type,
            rhs=rhs_type,
            returns=return_type,
        )
        function.fn_self = self_type

        type_class.cls_functions[function.name] = function
        return type_class

    @staticmethod
    def add_all_classes(type: types.AnalyzedType, *type_classes: types.TypeClass) -> None:
        for type_class in type_classes:
            type.add_class_implementation(type_class)


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
    ADD = TypeBuilder.new_binaryop_class('Add', 'add')
    SUB = TypeBuilder.new_binaryop_class('Sub', 'sub')
    MULT = TypeBuilder.new_binaryop_class('Mult', 'mult')
    MATMULT = TypeBuilder.new_binaryop_class('Matmult', 'matmult')
    DIV = TypeBuilder.new_binaryop_class('Div', 'div')
    MOD = TypeBuilder.new_binaryop_class('Mod', 'mod')
    POW = TypeBuilder.new_binaryop_class('Pow', 'pow')
    LSHIFT = TypeBuilder.new_binaryop_class('LShift', 'lshift')
    RSHIFT = TypeBuilder.new_binaryop_class('RShift', 'rshift')
    BITOR = TypeBuilder.new_binaryop_class('BitOr', 'bitor')
    BITXOR = TypeBuilder.new_binaryop_class('BitXOr', 'bitxor')
    BITAND = TypeBuilder.new_binaryop_class('BitAnd', 'bitand')
    FLOORDIV = TypeBuilder.new_binaryop_class('FloorDiv', 'floordiv')

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

    INVERT = TypeBuilder.new_unaryop_class('Invert', 'invert')
    UADD = TypeBuilder.new_unaryop_class('UAdd', 'uadd')
    USUB = TypeBuilder.new_unaryop_class('USub', 'usub')

    UNARY_OPERATORS = (
        INVERT,
        UADD,
        USUB,
    )


@TypeBuilder.type_class_from_class('Hash')
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


@TypeBuilder.type_class_from_class('Iter')
class Iter:
    self_type = TypeBuilder.new_self_type()
    next_type = TypeBuilder.new_type_parameter('T')
    next = TypeBuilder.new_function('next', self=self_type, returns=next_type)


@TypeBuilder.type_class_from_class('Index')
class Index:
    self_type = TypeBuilder.new_self_type()
    index_type = TypeBuilder.new_type_parameter('T')
    value_type = TypeBuilder.new_type_parameter('V')
    get_item = TypeBuilder.new_function('get_item', self=self_type, index=index_type, returns=value_type)


class Classes:
    HASH = Hash
    ITER = Iter
    INDEX = Index


TypeBuilder.add_all_classes(
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

TypeBuilder.add_all_classes(
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

TypeBuilder.add_all_classes(
    Types.LIST,
    Iter.with_parameters([Types.LIST.parameters[0]]),
    Index.with_parameters([Types.INT, Types.LIST.parameters[0]]),
)

DEBUG = TypeBuilder.new_function('debug', returns=Types.UNIT_TYPE)

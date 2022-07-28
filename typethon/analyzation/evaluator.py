from __future__ import annotations

import typing
import enum

from . import types
from . import plugins
from .. import ast
from .scope import Scope, ScopeType
from .symbol import Symbol
from .errors import AnalyzationError, ErrorCategory
from ..parser.visitor import NodeVisitor


OPERATORS = {
    ast.Operator.ADD: ('__add__', '__radd__', '+'),
    ast.Operator.SUB: ('__sub__', '__rsub__', '-'),
    ast.Operator.MULT: ('__mult__', '__rmult__', '*'),
    ast.Operator.MATMULT: ('__matmult__', '__rmatmult__', '@'),
    ast.Operator.DIV: ('__truediv__', '__rtruediv__', '/'),
    ast.Operator.FLOORDIV: ('__floordiv__', '__rfloordiv__', '//'),
    ast.Operator.MOD: ('__mod__', '__rmod__', '%'),
    ast.Operator.POW: ('__pow__', '__rpow__', '**'),
    ast.Operator.LSHIFT: ('__lshift__', '__rlshift__', '<<'),
    ast.Operator.RSHIFT: ('__rshift__', '__rrshift__', '>>'),
    ast.Operator.BITOR: ('__or__', '__ror__', '|'),
    ast.Operator.BITXOR: ('__xor__', '__rxor__', '^'),
    ast.Operator.BITAND: ('__and__', '__rand__', '&'),
}


UNARY_OPERATORS = {
    ast.UnaryOperator.UADD: ('__pos__', '+'),
    ast.UnaryOperator.USUB: ('__neg__', '-'),
    ast.UnaryOperator.INVERT: ('__invert__', '~'),
}


class EvaluatorContext(enum.Enum):
    DEFINITIONS = enum.auto()
    CODE = enum.auto()
    TYPE = enum.auto()


class TypeEvaluator(NodeVisitor[types.Type]):
    def __init__(self, *, definitions: bool = False) -> None:
        self.scope = Scope(ScopeType.GLOBAL)

        if definitions:
            self.ctx = EvaluatorContext.DEFINITIONS
        else:
            self.ctx = EvaluatorContext.CODE

        self.errors: typing.List[AnalyzationError] = []

        self.type = types.TypeInstance(flags=types.TypeFlags.TYPE)
        self.bool_type = types.BoolType(flags=types.TypeFlags.TYPE)
        self.none_type = types.NoneType(flags=types.TypeFlags.TYPE)
        self.ellipsis_type = types.EllipsisType(flags=types.TypeFlags.TYPE)
        self.string_type = types.StringType(flags=types.TypeFlags.TYPE)
        self.integer_type = types.IntegerType(flags=types.TypeFlags.TYPE)
        self.float_type = types.FloatType(flags=types.TypeFlags.TYPE)
        self.complex_type = types.ComplexType(flags=types.TypeFlags.TYPE)
        self.unknown_type = types.UnknownType(flags=types.TypeFlags.TYPE)

        self.none = types.NoneType()
        self.ellipsis = types.EllipsisType()

        self.scope.add_symbol(Symbol('type', self.type))
        self.scope.add_symbol(Symbol('bool', self.bool_type))
        self.scope.add_symbol(Symbol('None', self.none))
        self.scope.add_symbol(Symbol('Ellipsis', self.ellipsis))
        self.scope.add_symbol(Symbol('str', self.string_type))
        self.scope.add_symbol(Symbol('int', self.integer_type))
        self.scope.add_symbol(Symbol('float', self.float_type))
        self.scope.add_symbol(Symbol('complex', self.complex_type))

        self.function_plugin = plugins.FunctionPlugin()
        self.int_plugin = plugins.IntegerPlugin()

    @classmethod
    def evaluate_module(
        cls, module: ast.ModuleNode, *, definitions: bool = False
    ) -> types.ModuleType:
        return cls(definitions=definitions).module(module)

    def module(self, module: ast.ModuleNode) -> types.ModuleType:
        for statement in module.body:
            self.visit_statement(statement)

        return types.ModuleType(scope=self.scope)

    def remove_implicit_values(self, type: types.Type) -> types.Type:
        if isinstance(type, types.LiteralType):
            if not type.flags & types.TypeFlags.IMPLICIT:
                return type
            elif type.kind is types.TypeKind.BOOL:
                return self.bool_type
            elif type.kind is types.TypeKind.STRING:
                return self.string_type
            elif type.kind is types.TypeKind.INTEGER:
                return self.integer_type
            elif type.kind is types.TypeKind.FLOAT:
                return self.float_type
            elif type.kind is types.TypeKind.COMPLEX:
                return self.complex_type

        elif isinstance(type, types.UnionType):
            return types.union(self.remove_implicit_values(type) for type in type.types)

        return type

    def is_evaluating_code(self) -> bool:
        return self.ctx is EvaluatorContext.CODE

    def is_evaluating_type(self) -> bool:
        return self.ctx is EvaluatorContext.TYPE

    def types_compatible(self, first: types.Type, second: types.Type) -> bool:
        return first.kind is second.kind

    def error(
        self,
        category: ErrorCategory,
        message: str,
        *,
        node: typing.Optional[ast.Node] = None,
    ) -> types.UnknownType:
        self.errors.append(AnalyzationError(category=category, message=message, node=node))
        return self.unknown_type

    def getattribute(self, type: types.Type, name: str) -> types.Type:
        attribute = None

        if isinstance(type, types.FunctionType):
            attribute = self.function_plugin.getattribute(name)
        elif isinstance(type, types.IntegerType):
            attribute = self.int_plugin.getattribute(name)

        if attribute is not None:
            instance = types.ObjectType(value=type)
            owner = types.TypeInstance(value=type.to_type())

            if isinstance(attribute, types.FunctionType):
                return self.function_plugin.get(attribute, instance, owner)

            getter = self.getattribute(attribute, '__get__')
            if not types.is_unknown(getter):
                return self.call(getter, type, type.to_type())

            return attribute

        return self.unknown_type

    def getitem(self, type: types.Type, slice: types.Type) -> types.Type:
        func = self.getattribute(type, '__getitem__')
        if types.is_unknown(func):
            return self.unknown_type

        return self.call(func, slice)

    def call(
        self,
        type: types.Type,
        *arguments: types.Type,
        keywords: typing.Optional[typing.Dict[typing.Optional[str], types.Type]] = None,
    ) -> types.Type:
        if isinstance(type, types.MethodType):
            fields = type.get_fields()
            return self.call(fields.function, fields.instance, *arguments)

        if isinstance(type, types.BuiltinFunctionType):
            return type.function(*arguments)

        return self.unknown_type

    def truthness(self, type: types.Type) -> typing.Optional[bool]:
        if isinstance(type, types.BoolType):
            return type.value
        elif isinstance(type, types.NoneType):
            return False
        elif isinstance(type, types.EllipsisType):
            return True
        elif isinstance(
            type, (types.StringType, types.IntegerType, types.FloatType, types.ComplexType)
        ):
            return bool(type.value) if type.value is not None else None
        elif isinstance(type, types.TupleType):
            return type.values is not None and len(type.values) > 0
        elif isinstance(type, types.ListType):
            return type.size > 0 if type.size is not None else None

        return True

    def visit_return_node(self, statement: ast.ReturnNode) -> types.Type:
        value = self.visit_expression(statement.value)

        if not self.scope.is_function_scope():
            msg = 'return statementment not allowed outside of function scope'
            return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=statement)

        function = self.scope.get_function()
        fields = function.get_fields()

        if not self.types_compatible(fields.returns, value):
            msg = f'declared return type {fields.returns} is incompatible with {value}'
            return self.error(ErrorCategory.TYPE_ERROR, msg, node=statement)

        return self.unknown_type

    def visit_boolop_node(self, expression: ast.BoolOpNode) -> types.Type:
        values = [self.visit_expression(value) for value in expression.values]

        if not self.is_evaluating_code():
            msg = 'boolean operation is not valid in this context'
            return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=expression)

        unknown = any(self.truthness(value) is None for value in values)
        if unknown:
            return types.union(values)

        for value in values:
            truthness = self.truthness(value)
            assert truthness is not None

            if expression.op is ast.BoolOperator.AND and not truthness:
                return value
            elif expression.op is ast.BoolOperator.OR and truthness:
                return value

        return values[-1]

    def visit_binop_node(self, expression: ast.BinaryOpNode) -> types.Type:
        left = self.visit_expression(expression.left)
        right = self.visit_expression(expression.right)

        if types.is_unknown(left) or types.is_unknown(right):
            return types.union((left, right))

        operators = OPERATORS[expression.op]

        func = self.getattribute(left, operators[0])
        result = self.call(func, right)

        if types.is_unknown(result):
            func = self.getattribute(right, operators[1])
            result = self.call(func, left)

        if types.is_unknown(result):
            return self.error(
                ErrorCategory.TYPE_ERROR,
                f'operator {operators[2]!r} not supported'
                f' between instances of {left} and {right}',
                node=expression,
            )

        if self.is_evaluating_type() and expression.op is not ast.Operator.BITOR:
            msg = 'only the \'|\' operator is valid in this context'
            return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=expression)
        elif not self.is_evaluating_code():
            msg = 'binary operations are not valid in this context'
            return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=expression)

        return result

    def visit_unaryop_node(self, expression: ast.UnaryOpNode) -> types.Type:
        operand = self.visit_expression(expression.operand)

        if types.is_unknown(operand):
            return self.unknown_type

        if expression.op is ast.UnaryOperator.NOT:
            truthness = self.truthness(operand)
            if truthness is None:
                result = self.bool_type
            else:
                result = self.bool_type.with_value(not truthness)
        else:
            operator = UNARY_OPERATORS[expression.op]

            func = self.getattribute(operand, operator[0])
            result = self.call(func)

            if types.is_unknown(result):
                msg = f'operator {operator[1]!r} not supported for {operand}'
                return self.error(ErrorCategory.TYPE_ERROR, msg, node=expression)

        if not self.is_evaluating_code():
            msg = 'unary operations are not valid in this context'
            return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=expression)

        return result

    def visit_ifexp_node(self, expression: ast.IfExpNode) -> types.Type:
        condition = self.visit_expression(expression.condition)
        body = self.visit_expression(expression.body)
        else_body = self.visit_expression(expression.else_body)

        if not self.is_evaluating_code():
            msg = 'if expressions are not valid in thie context'
            return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=expression)

        truthness = self.truthness(condition)
        if truthness is True:
            return body
        elif truthness is False:
            return else_body

        return types.union((body, else_body))

    def visit_dict_node(self, expression: ast.DictNode) -> types.Type:
        keys: typing.List[types.Type] = []
        values: typing.List[types.Type] = []
        unpacked: typing.List[types.Type] = []

        for elt in expression.elts:
            if elt.key is None:
                value = self.visit_expression(elt.value).to_instance()

                if value.kind is not types.TypeKind.DICT:
                    msg = f'cannot unpack {value} into dictionary'
                    return self.error(ErrorCategory.TYPE_ERROR, msg, node=expression)

                unpacked.append(value)
            else:
                keys.append(self.visit_expression(elt.key).to_instance())
                values.append(self.visit_expression(elt.value).to_instance())

        if self.is_evaluating_type():
            if len(keys) != 1 and len(values) != 1:
                msg = 'dict type should only have one entry'
                return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=expression)

            if unpacked:
                msg = 'cannot unpack into dict type'
                return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=expression)

            fields = types.DictFields(key=keys[0], value=values[0])
            return types.DictType(fields=fields, flags=types.TypeFlags.TYPE)

        if not self.is_evaluating_code():
            msg = 'dictionary is not valid in this context'
            return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=expression)

        for unpack in unpacked:
            get_keys = self.getattribute(unpack, 'keys')
            get_values = self.getattribute(unpack, 'values')

            unpack_keys = self.call(get_keys)
            unpack_values = self.call(get_values)
            assert not types.is_unknown(unpack_keys) and not types.is_unknown(unpack_values)

            keys.append(unpack_keys)
            keys.append(unpack_values)

        key = self.remove_implicit_values(types.union(keys))
        value = self.remove_implicit_values(types.union(values))

        fields = types.DictFields(key=key, value=value)
        return types.DictType(fields=fields)

    def visit_set_node(self, expression: ast.SetNode) -> types.Type:
        elts = [self.visit_expression(elt).to_instance() for elt in expression.elts]

        if self.is_evaluating_type():
            if len(elts) != 1:
                msg = 'set type should only have one entry'
                return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=expression)

            return types.SetType(value=elts[0], flags=types.TypeFlags.TYPE)

        if not self.is_evaluating_code():
            msg = 'set is not valid in this context'
            return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=expression)

        value = self.remove_implicit_values(types.union(elts))
        return types.SetType(value=value)

    def visit_call_node(self, expression: ast.CallNode) -> types.Type:
        func = self.visit_expression(expression.func)

        args = [self.visit_expression(arg) for arg in expression.args]
        kwargs = {kwarg.name: self.visit_expression(kwarg.value) for kwarg in expression.kwargs}

        return self.call(func, *args, keywords=kwargs)

    def visit_constant_node(self, expression: ast.ConstantNode) -> types.Type:
        if not self.is_evaluating_type() and not self.is_evaluating_code():
            msg = 'constant is not valid in this context'
            return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=expression)

        flags = types.TypeFlags.NONE

        if self.is_evaluating_type():
            flags |= types.TypeFlags.IMPLICIT
        else:
            flags |= types.TypeFlags.TYPE

        if expression.type is ast.ConstantType.TRUE:
            return types.BoolType(value=True, flags=flags)

        elif expression.type is ast.ConstantType.FALSE:
            return types.BoolType(value=False, flags=flags)

        elif expression.type is ast.ConstantType.NONE:
            if self.is_evaluating_type():
                return self.none_type

            return self.none

        elif expression.type is ast.ConstantType.ELLIPSIS:
            if self.is_evaluating_type():
                return self.ellipsis_type

            return self.ellipsis

        elif isinstance(expression, ast.StringNode):
            return types.StringType(value=expression.value, flags=flags)

        elif isinstance(expression, ast.IntegerNode):
            return types.IntegerType(value=expression.value, flags=flags)

        elif isinstance(expression, ast.FloatNode):
            return types.FloatType(value=expression.value, flags=flags)

        elif isinstance(expression, ast.ComplexNode):
            return types.ComplexType(value=expression.value, flags=flags)

        return self.error(ErrorCategory.SYNTAX_ERROR, 'invalid constant', node=expression)

    def visit_attribute_node(self, expression: ast.AttributeNode) -> types.Type:
        value = self.visit_expression(expression.value)
        return self.getattribute(value, expression.attr)

    def visit_subscript_node(self, expression: ast.SubscriptNode) -> types.Type:
        value = self.visit_expression(expression.value)
        slice = self.visit_expression(expression.slice)

        result = self.getitem(value, slice)

        if not self.is_evaluating_code():
            msg = 'subscript is not valid in this context'
            return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=expression)

        return result

    def visit_name_node(self, expression: ast.NameNode) -> types.Type:
        symbol = self.scope.get_symbol(expression.value)

        if symbol is None:
            msg = f'{expression.value!r} is not defined'
            return self.error(ErrorCategory.TYPE_ERROR, msg, node=expression)

        return symbol.type

    def visit_list_node(self, expression: ast.ListNode) -> types.Type:
        elts = [self.visit_expression(elt).to_instance() for elt in expression.elts]

        if self.is_evaluating_type():
            if not 0 < len(elts) <= 2:
                msg = 'list type should have between one and two elements'
                return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=expression)

            size: typing.Optional[int] = None

            if len(elts) == 2:
                if not isinstance(elts[1], types.IntegerType):
                    msg = 'second element of list type should be an integer'
                    return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=expression)

                size = elts[1].value

            return types.ListType(value=elts[0], size=size, flags=types.TypeFlags.TYPE)

        value = self.remove_implicit_values(types.union(elts))
        return types.ListType(value=value)

    def visit_tuple_node(self, expression: ast.TupleNode) -> types.Type:
        elts = [self.visit_expression(elt).to_instance() for elt in expression.elts]

        if not self.is_evaluating_type() and not self.is_evaluating_code():
            msg = 'tuple is not valid in this context'
            return self.error(ErrorCategory.SYNTAX_ERROR, msg, node=expression)

        flags = types.TypeFlags.NONE

        if self.is_evaluating_type():
            flags |= types.TypeFlags.TYPE

        return types.TupleType(values=elts, flags=flags)

    def visit_expression(self, expression: typing.Optional[ast.ExpressionNode]) -> types.Type:
        if expression is None:
            return self.none_type

        return super().visit_expression(expression)

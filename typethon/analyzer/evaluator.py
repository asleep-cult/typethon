import typing
import enum

from . import types
from .. import ast
from .scope import Scope, ScopeType
from .errors import ErrorCategory
from .visitor import NodeVisitor


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
    CODE = enum.auto()
    TYPE = enum.auto()


class TypeEvaluator(NodeVisitor[types.Type]):
    def __init__(self) -> None:
        self.scope = Scope(ScopeType.GLOBAL)
        self.ctx = EvaluatorContext.CODE

        self.errors: typing.List[types.ErrorType] = []

        self.bool_type = types.BoolType()
        self.none_type = types.NoneType()
        self.ellipsis_type = types.EllipsisType()
        self.string_type = types.StringType()
        self.integer_type = types.IntegerType()
        self.float_type = types.FloatType()
        self.complex_type = types.ComplexType()
        self.unknown_type = types.UnknownType()

        self.initialize_visitors()

    def remove_implicit_values(self, type: types.Type) -> types.Type:
        if isinstance(type, types.LiteralType):
            if not type.implicit:
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
    ) -> types.ErrorType:
        type = types.ErrorType(category=category, message=message, node=node)
        self.errors.append(type)
        return type

    def getattribute(self, type: types.Type, name: str) -> types.Type:
        return self.unknown_type

    def getitem(self, type: types.Type, slice: types.Type) -> types.Type:
        func = self.getattribute(type, '__getitem__')
        if not types.is_valid(func):
            return self.unknown_type

        return self.call(func, slice)

    def call(
        self,
        type: types.Type,
        *arguments: types.Type,
        keywords: typing.Optional[typing.Dict[typing.Optional[str], types.Type]] = None,
    ) -> types.Type:
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
            return len(type.values) > 0
        elif isinstance(type, types.ListType):
            return type.size > 0 if type.size is not None else None

        return True

    def visit_return_node(self, statement: ast.ReturnNode) -> types.Type:
        value = self.visit_expression(statement.value)

        if not self.scope.is_function_scope():
            return self.error(
                ErrorCategory.SYNTAX_ERROR,
                'return statementment not allowed outside of function scope',
                node=statement,
            )

        function = self.scope.get_function()
        if not self.types_compatible(function.returns, value):
            return self.error(
                ErrorCategory.TYPE_ERROR,
                f'declared return type {function.returns} is incompatible with {value}',
                node=statement,
            )

        return self.unknown_type

    def visit_boolop_node(self, expression: ast.BoolOpNode) -> types.Type:
        values = [self.visit_expression(value) for value in expression.values]

        if not self.is_evaluating_code():
            return self.error(
                ErrorCategory.SYNTAX_ERROR,
                'boolean operation is not valid in this context',
                node=expression,
            )

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

        operators = OPERATORS[expression.op]

        func = self.getattribute(left, operators[0])
        result = self.unknown_type

        if not types.is_unknown(func):
            result = self.call(func, left, right)

        if not types.is_valid(result):
            func = self.getattribute(right, operators[1])
            result = self.call(func, left, right)

        if not types.is_valid(result):
            return self.error(
                ErrorCategory.TYPE_ERROR,
                f'Operator {operators[2]!r} not supported'
                f' between instances of {left} and {right}',
                node=expression,
            )

        if self.is_evaluating_type() and expression.op is not ast.Operator.BITOR:
            return self.error(
                ErrorCategory.SYNTAX_ERROR,
                'only the "|" operator is valid in this context',
                node=expression,
            )
        elif not self.is_evaluating_code():
            return self.error(
                ErrorCategory.SYNTAX_ERROR,
                'binary operations are not valid in this context',
                node=expression,
            )

        return result

    def visit_unaryop_node(self, expression: ast.UnaryOpNode) -> types.Type:
        operand = self.visit_expression(expression.operand)

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

            if not types.is_valid(result):
                return self.error(
                    ErrorCategory.TYPE_ERROR,
                    f'Operator {operator[1]!r} not supported for {operand}',
                    node=expression,
                )

        if not self.is_evaluating_code():
            return self.error(
                ErrorCategory.SYNTAX_ERROR,
                'unary operations are not valid in this context',
                node=expression,
            )

        return result

    def visit_ifexp_node(self, expression: ast.IfExpNode) -> types.Type:
        condition = self.visit_expression(expression.condition)
        body = self.visit_expression(expression.body)
        else_body = self.visit_expression(expression.else_body)

        truthness = self.truthness(condition)
        if truthness is True:
            return body
        elif truthness is False:
            return else_body

        return types.union((body, else_body))

    def visit_dict_node(self, expression: ast.DictNode) -> types.Type:
        error: typing.Optional[types.ErrorType] = None

        keys: typing.List[types.Type] = []
        values: typing.List[types.Type] = []
        unpacked: typing.List[types.Type] = []

        for elt in expression.elts:
            if elt.key is None:
                value = self.visit_expression(elt.value)

                if value.kind is not types.TypeKind.DICT:  # TODO: implements(mapping)
                    error = self.error(
                        ErrorCategory.TYPE_ERROR,
                        f'cannot unpack {value} into dictionary',
                        node=expression,
                    )

                unpacked.append(self.visit_expression(elt.value))
            else:
                keys.append(self.visit_expression(elt.key))
                values.append(self.visit_expression(elt.value))

        if self.is_evaluating_type():
            if len(keys) != 1 and len(values) != 1:
                error = self.error(
                    ErrorCategory.SYNTAX_ERROR,
                    'dict type should only have one entry',
                    node=expression,
                )

            if unpacked:
                error = self.error(
                    ErrorCategory.SYNTAX_ERROR,
                    'cannot unpack into dict type',
                    node=expression,
                )

            if error is not None:
                return self.unknown_type

            return types.DictType(key=keys[0], value=values[0])

        if not self.is_evaluating_code():
            error = self.error(
                ErrorCategory.SYNTAX_ERROR,
                'dictionary is not valid in this context',
                node=expression,
            )

        if error is not None:
            return self.unknown_type

        for unpack in unpacked:
            get_keys = self.getattribute(unpack, 'keys')
            get_values = self.getattribute(unpack, 'values')

            unpack_keys = self.call(get_keys)
            unpack_values = self.call(get_values)
            assert types.is_valid(unpack_keys) and types.is_valid(unpack_values)

            keys.append(unpack_keys)
            keys.append(unpack_values)

        key = self.remove_implicit_values(types.union(keys))
        value = self.remove_implicit_values(types.union(values))
        return types.DictType(key=key, value=value)

    def visit_set_node(self, expression: ast.SetNode) -> types.Type:
        elts = [self.visit_expression(elt) for elt in expression.elts]

        if self.is_evaluating_type():
            if len(elts) != 1:
                return self.error(
                    ErrorCategory.SYNTAX_ERROR,
                    'set type should only have one entry',
                    node=expression,
                )

            return types.SetType(value=elts[0])

        if not self.is_evaluating_code():
            return self.error(
                ErrorCategory.SYNTAX_ERROR,
                'set is not valid in this context',
                node=expression,
            )

        value = self.remove_implicit_values(types.union(elts))
        return types.SetType(value=value)

    def visit_call_node(self, expression: ast.CallNode) -> types.Type:
        func = self.visit_expression(expression.func)

        args = [self.visit_expression(arg) for arg in expression.args]
        kwargs = {kwarg.name: self.visit_expression(kwarg.value) for kwarg in expression.kwargs}

        return self.call(func, *args, keywords=kwargs)

    def visit_constant_node(self, expression: ast.ConstantNode) -> types.Type:
        if not self.is_evaluating_type() and not self.is_evaluating_code():
            return self.error(
                ErrorCategory.SYNTAX_ERROR,
                'constant is not valid in this context',
                node=expression,
            )

        implicit = not self.is_evaluating_type()

        if expression.type is ast.ConstantType.TRUE:
            return types.BoolType(value=True, implicit=implicit)

        elif expression.type is ast.ConstantType.FALSE:
            return types.BoolType(value=False, implicit=implicit)

        elif expression.type is ast.ConstantType.NONE:
            return types.NoneType()

        elif expression.type is ast.ConstantType.ELLIPSIS:
            return types.EllipsisType()

        elif isinstance(expression, ast.StringNode):
            return types.StringType(value=expression.value, implicit=implicit)

        elif isinstance(expression, ast.IntegerNode):
            return types.IntegerType(value=expression.value, implicit=implicit)

        elif isinstance(expression, ast.FloatNode):
            return types.FloatType(value=expression.value, implicit=implicit)

        elif isinstance(expression, ast.ComplexNode):
            return types.ComplexType(value=expression.value, implicit=implicit)

        return self.error(ErrorCategory.SYNTAX_ERROR, 'invalid constant', node=expression)

    def visit_attribute_node(self, expression: ast.AttributeNode) -> types.Type:
        value = self.visit_expression(expression.value)
        return self.getattribute(value, expression.attr)

    def visit_subscript_node(self, expression: ast.SubscriptNode) -> types.Type:
        value = self.visit_expression(expression.value)
        slice = self.visit_expression(expression.slice)

        result = self.getitem(value, slice)

        if not self.is_evaluating_code():
            return self.error(
                ErrorCategory.SYNTAX_ERROR,
                'subscript is not valid in this context',
                node=expression,
            )

        return result

    def visit_list_node(self, expression: ast.ListNode) -> types.Type:
        elts = [self.visit_expression(elt) for elt in expression.elts]

        if self.is_evaluating_type():
            if not 0 < len(elts) <= 2:
                return self.error(
                    ErrorCategory.SYNTAX_ERROR,
                    'list type should have between one and two elements',
                    node=expression,
                )

            size: typing.Optional[int] = None

            if len(elts) == 2:
                if not isinstance(elts[1], types.IntegerType):
                    return self.error(
                        ErrorCategory.SYNTAX_ERROR,
                        'second element of list type should be an integer',
                        node=expression,
                    )

                size = elts[1].value

            return types.ListType(value=elts[0], size=size)

        value = self.remove_implicit_values(types.union(elts))
        return types.ListType(value=value)

    def visit_tuple_node(self, expression: ast.TupleNode) -> types.Type:
        elts = [self.visit_expression(elt) for elt in expression.elts]

        if not self.is_evaluating_type() or self.is_evaluating_code():
            return self.error(
                ErrorCategory.SYNTAX_ERROR,
                'tuple is not valid in this context',
                node=expression,
            )

        return types.TupleType(values=elts)

    def visit_expression(self, expression: typing.Optional[ast.ExpressionNode]) -> types.Type:
        if expression is None:
            return self.none_type

        result = super().visit_expression(expression)
        if types.is_error(result):
            return self.unknown_type

        return result

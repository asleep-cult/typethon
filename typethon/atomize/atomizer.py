from __future__ import annotations

import contextlib
import enum
import typing

from .. import ast
from ..parse.visitor import NodeVisitor
from . import atoms, impls
from .scope import Scope

__all__ = ('Atomizer',)


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


class AtomizerContext(enum.Enum):
    CODE = enum.auto()
    TYPE = enum.auto()


class Atomizer(NodeVisitor[atoms.Atom]):
    def __init__(self) -> None:
        self.ctx = AtomizerContext.CODE

        self.type_impl = impls.TypeImpl(self)
        self.int_impl = impls.IntegerImpl(self)
        self.function_impl = impls.FunctionImpl(self)
        self.method_impl = impls.MethodImpl(self)

        self.scope = Scope.create_global_scope()

    def is_evaluating_code(self) -> bool:
        return self.ctx is AtomizerContext.CODE

    def is_evaluating_type(self) -> bool:
        return self.ctx is AtomizerContext.TYPE

    @contextlib.contextmanager
    def enter_scope(self, scope: Scope) -> typing.Generator[None, None, None]:
        self.scope = scope
        yield
        self.scope = self.scope.get_parent()

    def visit_functiondef_node(self, statement: ast.FunctionDefNode) -> atoms.Atom:
        self.scope = self.scope.create_function_scope()

        parameters: typing.List[atoms.FunctionParameter] = []

        for parameter in statement.parameters:
            if parameter.annotation is None:
                msg = 'parameter must be annotated'
                return atoms.ErrorAtom(atoms.ErrorCategory.TYPE_ERROR, message=msg)

            annotation = self.visit_type_expression(parameter.annotation)
            self.scope.add_symbol(parameter.name, annotation.instantiate())

            default = None
            if parameter.default is not None:
                default = self.visit_expression(parameter.default)

            parameter = atoms.FunctionParameter(
                name=parameter.name, annotation=annotation, kind=parameter.kind, default=default
            )
            parameters.append(parameter)

        returns = None
        if statement.returns is not None:
            returns = self.visit_expression(statement.returns)

        fields = atoms.FunctionFields(
            name=statement.name, parameters=parameters, returns=returns, scope=self.scope
        )
        function = result = atoms.FunctionAtom(fields=fields)

        self.scope = self.scope.get_parent()

        for decorator in reversed(statement.decorators):
            decorator = self.visit_expression(decorator)
            result = self.call(decorator, (result,))

        self.scope.add_symbol(statement.name, result)
        return function

    def visit_return_node(self, statement: ast.ReturnNode) -> atoms.Atom:
        if not self.scope.is_function_scope():
            msg = 'return is not valid in this context'
            return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, msg)

        if statement.value is None:
            return atoms.NONE

        return self.visit_expression(statement.value)

    def get_type(self, atom: atoms.Atom) -> atoms.Atom:
        if atom.is_type():
            return atoms.TypeAtom(atom)

        return atom.uninstantiate()

    def get_attribute(self, atom: atoms.Atom, name: str) -> atoms.Atom:
        if atom.kind is atoms.AtomKind.TYPE:
            attribute = self.type_impl.get_attribute(name)
        elif atom.kind is atoms.AtomKind.INTEGER:
            attribute = self.int_impl.get_attribute(name)
        elif atom.kind is atoms.AtomKind.FUNCTION:
            attribute = self.function_impl.get_attribute(name)
        elif atom.kind is atoms.AtomKind.METHOD:
            attribute = self.method_impl.get_attribute(name)
        else:
            return atoms.UNKNOWN

        if atom.is_type():
            instance = atoms.NONE
        else:
            instance = atoms.ObjectAtom(atom)

        owner = atoms.TypeAtom(atom.uninstantiate())

        if attribute.kind is atoms.AtomKind.FUNCTION:
            return self.function_impl.get(attribute, instance, owner)

        type = self.get_type(attribute)
        getter = self.get_attribute(type, '__get__')

        if getter.kind is not atoms.AtomKind.UNKNOWN:
            return self.call(getter, (attribute, instance, owner))

        return attribute

    def get_item(self, atom: atoms.Atom, slice: atoms.Atom) -> atoms.Atom:
        return atoms.UNKNOWN

    def call(
        self,
        atom: atoms.Atom,
        arguments: typing.Sequence[atoms.Atom] = (),
        keywords: typing.Optional[typing.Mapping[str, atoms.Atom]] = None,
        unpack: typing.Sequence[atoms.Atom] = (),
    ) -> atoms.Atom:
        if isinstance(atom, atoms.FunctionAtom):
            if keywords is not None:
                return self.function_impl.call(atom, *arguments, **keywords)

            return self.function_impl.call(atom, *arguments)

        type = self.get_type(atom)
        function = self.get_attribute(type, '__call__')

        if function.kind is atoms.AtomKind.UNKNOWN:
            return atoms.ErrorAtom(atoms.ErrorCategory.TYPE_ERROR, f'{atom} is not callable')

        arguments = (atom, *arguments)
        return self.call(function, arguments, keywords, unpack)

    def truthness(self, atom: atoms.Atom) -> atoms.BoolAtom:
        if atom.kind is atoms.AtomKind.BOOL and not atom.is_type():
            return atom

        type = self.get_type(atom)
        function = self.get_attribute(type, '__bool__')

        if function.kind is not atoms.AtomKind.UNKNOWN:
            result = self.call(function, (atom,))
            return result.unwrap_as(atoms.BoolAtom)

        return atoms.BoolAtom(True)

    def visit_expr_node(self, statement: ast.ExprNode) -> atoms.Atom:
        return self.visit_expression(statement.expr)

    def visit_boolop_node(self, expression: ast.BoolOpNode) -> atoms.Atom:
        values = [self.visit_expression(value).synthesize() for value in expression.values]

        if not self.is_evaluating_code():
            msg = 'boolean operation is not valid in this context'
            return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, msg)

        unknown = any(self.truthness(value).value is None for value in values)
        if unknown:
            return atoms.union(values)

        for value in values:
            truthness = self.truthness(value).value
            assert truthness is not None

            if expression.op is ast.BoolOperator.AND and not truthness:
                return value
            elif expression.op is ast.BoolOperator.OR and truthness:
                return value

        return values[-1]

    def visit_binaryop_node(self, expression: ast.BinaryOpNode) -> atoms.Atom:
        left = self.visit_expression(expression.left).synthesize()
        right = self.visit_expression(expression.right).synthesize()

        if left.kind is atoms.AtomKind.UNKNOWN or right.kind is atoms.AtomKind.UNKNOWN:
            return atoms.union((left, right))

        operators = OPERATORS[expression.op]

        type = self.get_type(left)
        function = self.get_attribute(type, operators[0])
        print(left, right, type, function)

        result = self.call(function, (left, right))

        if result.kind is atoms.AtomKind.UNKNOWN:
            type = self.get_type(right)
            function = self.get_attribute(type, operators[1])

            result = self.call(function, (right, left))

        return result

    def visit_unaryop_node(self, expression: ast.UnaryOpNode) -> atoms.Atom:
        if not self.is_evaluating_code():
            msg = 'unary operations are not valid in this context'
            return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, msg)

        operand = self.visit_expression(expression.operand).synthesize()

        if operand.kind is atoms.AtomKind.UNKNOWN:
            return atoms.UNKNOWN

        if expression.op is ast.UnaryOperator.NOT:
            truthness = self.truthness(operand).value
            if truthness is None:
                result = atoms.get_type(atoms.BOOL)
            else:
                result = atoms.BoolAtom(not truthness)
        else:
            operator = UNARY_OPERATORS[expression.op]

            type = self.get_type(operand)
            function = self.get_attribute(type, operator[0])

            result = self.call(function, (operand,))

        return result

    def visit_ifexp_node(self, expression: ast.IfExpNode) -> atoms.Atom:
        condition = self.visit_expression(expression.condition).synthesize()
        body = self.visit_expression(expression.body).synthesize()
        else_body = self.visit_expression(expression.else_body).synthesize()

        if not self.is_evaluating_code():
            msg = 'if expressions are not valid in this context'
            return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, msg)

        truthness = self.truthness(condition)
        if truthness.value is True:
            return body
        elif truthness.value is False:
            return else_body

        return atoms.union((body, else_body))

    def visit_dict_node(self, expression: ast.DictNode) -> atoms.Atom:
        keys: typing.List[atoms.Atom] = []
        values: typing.List[atoms.Atom] = []
        unpacked: typing.List[atoms.Atom] = []

        for elt in expression.elts:
            if elt.key is None:
                value = self.visit_expression(elt.value).instantiate()

                if value.kind is not atoms.AtomKind.DICT:
                    msg = f'cannot unpack {value} into dictionary'
                    return atoms.ErrorAtom(atoms.ErrorCategory.TYPE_ERROR, msg)

                unpacked.append(value)
            else:
                keys.append(self.visit_expression(elt.key).instantiate())
                values.append(self.visit_expression(elt.value).instantiate())

        if self.is_evaluating_type():
            if len(keys) != 1 and len(values) != 1:
                msg = 'dict type should only have one entry'
                return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, msg)

            if unpacked:
                msg = 'cannot unpack into dict type'
                return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, msg)

            fields = atoms.DictFields(key=keys[0], value=values[0])
            return atoms.DictAtom(fields, flags=atoms.AtomFlags.TYPE)

        if not self.is_evaluating_code():
            msg = 'dictionary is not valid in this context'
            return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, msg)

        key = self.downgrade_constant(atoms.union(keys))
        value = self.downgrade_constant(atoms.union(values))

        fields = atoms.DictFields(key=key, value=value)
        return atoms.DictAtom(fields)

    def visit_set_node(self, expression: ast.SetNode) -> atoms.Atom:
        elts = [self.visit_expression(elt).synthesize() for elt in expression.elts]

        if self.is_evaluating_type():
            if len(elts) != 1:
                msg = 'set type should only have one entry'
                return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, msg)

            return atoms.SetAtom(elts[0], flags=atoms.AtomFlags.TYPE)

        if not self.is_evaluating_code():
            msg = 'set is not valid in this context'
            return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, msg)

        value = self.downgrade_constant(atoms.union(elts))
        return atoms.SetAtom(value)

    def visit_call_node(self, expression: ast.CallNode) -> atoms.Atom:
        func = self.visit_expression(expression.func).synthesize()

        args = [self.visit_expression(arg).synthesize() for arg in expression.args]
        kwargs: typing.Dict[str, atoms.Atom] = {}
        unpack: typing.List[atoms.Atom] = []

        for kwarg in expression.kwargs:
            value = self.visit_expression(kwarg.value).synthesize()

            if kwarg.name is not None:
                kwargs[kwarg.name] = value
            else:
                unpack.append(value)

        return self.call(func, args, kwargs, unpack)

    def downgrade_constant(self, atom: atoms.Atom) -> atoms.Atom:
        if isinstance(atom, atoms.LiteralAtom):
            if atom.flags & atoms.AtomFlags.IMPLICIT:
                atom = atom.copy()
                atom.value = None

        elif atom.kind is atoms.AtomKind.UNION:
            if atom.values is not None:
                atom = atoms.union(self.downgrade_constant(atom) for atom in atom.values)

        return atom

    def visit_constant_node(self, expression: ast.ConstantNode) -> atoms.Atom:
        if not self.is_evaluating_type() and not self.is_evaluating_code():
            msg = 'constant is not valid in this context'
            return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, msg)

        flags = atoms.AtomFlags.NONE

        if self.is_evaluating_type():
            flags |= atoms.AtomFlags.TYPE
        else:
            flags |= atoms.AtomFlags.IMPLICIT

        if expression.type is ast.ConstantType.TRUE:
            return atoms.BoolAtom(True, flags=flags)

        elif expression.type is ast.ConstantType.FALSE:
            return atoms.BoolAtom(False, flags=flags)

        elif expression.type is ast.ConstantType.NONE:
            if self.is_evaluating_type():
                return atoms.get_type(atoms.NONE)

            return atoms.NONE

        elif expression.type is ast.ConstantType.ELLIPSIS:
            if self.is_evaluating_type():
                return atoms.get_type(atoms.ELLIPSIS)

            return atoms.ELLIPSIS

        elif isinstance(expression, ast.StringNode):
            return atoms.StringAtom(expression.value, flags=flags)

        elif isinstance(expression, ast.IntegerNode):
            return atoms.IntegerAtom(expression.value, flags=flags)

        elif isinstance(expression, ast.FloatNode):
            return atoms.FloatAtom(expression.value, flags=flags)

        elif isinstance(expression, ast.ComplexNode):
            return atoms.ComplexAtom(expression.value, flags=flags)

        return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, 'invalid constant')

    def visit_attribute_node(self, expression: ast.AttributeNode) -> atoms.Atom:
        value = self.visit_expression(expression.value)
        return self.get_attribute(value, expression.attr)

    def visit_subscript_node(self, expression: ast.SubscriptNode) -> atoms.Atom:
        value = self.visit_expression(expression.value)
        slice = self.visit_expression(expression.slice)

        result = self.get_item(value, slice)

        if not self.is_evaluating_code():
            msg = 'subscript is not valid in this context'
            return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, msg)

        return result

    def visit_name_node(self, expression: ast.NameNode) -> atoms.Atom:
        symbol = self.scope.get_symbol(expression.value)

        if symbol is None:
            msg = f'{expression.value!r} is not defined'
            return atoms.ErrorAtom(atoms.ErrorCategory.TYPE_ERROR, msg)

        return symbol.atom

    def visit_list_node(self, expression: ast.ListNode) -> atoms.Atom:
        elts = [self.visit_expression(elt).instantiate() for elt in expression.elts]

        if self.is_evaluating_type():
            if not 0 < len(elts) <= 2:
                msg = 'list type should have between one and two elements'
                return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, msg)

            size: typing.Optional[int] = None

            if len(elts) == 2:
                elt = elts[1]
                if elt.kind is not atoms.AtomKind.INTEGER:
                    msg = 'second element of list type should be an integer'
                    return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, msg)

                size = elt.value

            return atoms.ListAtom(elts[0], size, flags=atoms.AtomFlags.TYPE)

        value = self.downgrade_constant(atoms.union(elts))
        return atoms.ListAtom(value)

    def visit_tuple_node(self, expression: ast.TupleNode) -> atoms.Atom:
        elts = [self.visit_expression(elt).instantiate() for elt in expression.elts]

        if not self.is_evaluating_type() and not self.is_evaluating_code():
            msg = 'tuple is not valid in this context'
            return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, msg)

        flags = atoms.AtomFlags.NONE

        if self.is_evaluating_type():
            flags |= atoms.AtomFlags.TYPE

        return atoms.TupleAtom(elts, flags=flags)

    def visit_slice_node(self, expression: ast.SliceNode) -> atoms.Atom:
        start = self.visit_expression(expression.start) if expression.start is not None else None
        stop = self.visit_expression(expression.stop) if expression.stop is not None else None
        step = self.visit_expression(expression.step) if expression.step is not None else None

        if self.is_evaluating_type():
            msg = 'slice is not valid in this context'
            return atoms.ErrorAtom(atoms.ErrorCategory.SYNTAX_ERROR, msg)

        return atoms.SliceAtom(start=start, stop=stop, step=step)

    def visit_type_expression(self, expression: ast.ExpressionNode) -> atoms.Atom:
        context = self.ctx
        self.ctx = AtomizerContext.TYPE

        result = self.visit_expression(expression)
        self.ctx = context

        return result

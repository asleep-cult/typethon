import typing

from . import types
from .. import ast


class Analyzer:
    def __init__(self, statements: typing.List[ast.StatementNode]) -> None:
        self.statements = statements

    def get_symbol(self, name: str) -> types.Type:
        raise NotImplementedError

    def evaluate_constant(self, expression: ast.ConstantNode) -> types.ConstantType:
        if expression.type is ast.ConstantType.TRUE:
            return types.BoolType(constraint=True)

        elif expression.type is ast.ConstantType.FALSE:
            return types.BoolType(constraint=False)

        elif expression.type is ast.ConstantType.NONE:
            return types.NoneType()

        elif expression.type is ast.ConstantType.ELLIPSIS:
            return types.EllipsisType()

        elif isinstance(expression, ast.StringNode):
            return types.StringType(constraint=expression.value)

        elif isinstance(expression, ast.IntegerNode):
            return types.IntegerType(constraint=expression.value)

        elif isinstance(expression, ast.FloatNode):
            return types.FloatType(constraint=expression.value)

        elif isinstance(expression, ast.ComplexNode):
            return types.ComplexType(constraint=expression.value)

        assert False, 'Invalid Constant'

    def evaluate_type(self, expression: ast.ExpressionNode) -> types.Type:
        if isinstance(expression, ast.ConstantNode):
            return self.evaluate_constant(expression)

        elif isinstance(expression, ast.SetNode):
            if len(expression.elts) != 1:
                assert False, 'set type must have 1 item'

            value = self.evaluate_type(expression.elts[0])
            return types.SetType(value=value)

        elif isinstance(expression, ast.DictNode):
            if len(expression.elts) != 1:
                assert False, 'dict type must have 1 item'

            elt = expression.elts[0]
            if elt.key is None:
                assert False, 'dict type does not support unpacking'

            key = self.evaluate_type(elt.key)
            value = self.evaluate_type(elt.value)

            return types.DictType(key=key, value=value)

        elif isinstance(expression, ast.TupleNode):
            values = [self.evaluate_type(elt) for elt in expression.elts]
            return types.TupleType(values=values)

        elif isinstance(expression, ast.ListNode):
            if not 0 < len(expression.elts) <= 2:
                assert False, 'list type must have 1 or 2 items'

            value = self.evaluate_type(expression.elts[0])
            size = None

            if len(expression.elts) == 2:
                expression = expression.elts[1]
                if not isinstance(expression, ast.IntegerNode):
                    assert False, 'list size must be an integer'

                size = expression.value

            return types.ListType(value=value, size=size)

        assert False, 'Invalid Expression'

    def evaluate_expression(
        self, expression: ast.ExpressionNode, mutable: bool = False
    ) -> types.Type:
        if isinstance(expression, ast.ConstantNode):
            constant = self.evaluate_constant(expression)
            if mutable and isinstance(constant, types.LiteralType):
                constant.constraint = None

            return constant

        elif isinstance(expression, ast.BoolOpNode):
            values = [self.evaluate_expression(value) for value in expression.values]

            if any(value.truthness() is None for value in values):
                return types.union(values)

            for value in values:
                truthness = value.truthness()
                assert truthness is not None

                if expression.op is ast.BoolOperator.AND and not truthness:
                    return value
                elif expression.op is ast.BoolOperator.OR and truthness:
                    return value

            return values[-1]

        elif isinstance(expression, ast.BinaryOpNode):
            right = self.evaluate_expression(expression.right)
            left = self.evaluate_expression(expression.left)

            if expression.op is ast.Operator.ADD:
                return left.add(right)
            elif expression.op is ast.Operator.SUB:
                return left.sub(right)
            elif expression.op is ast.Operator.MULT:
                return left.mult(right)
            elif expression.op is ast.Operator.MATMULT:
                return left.matmult(right)
            elif expression.op is ast.Operator.DIV:
                return left.div(right)
            elif expression.op is ast.Operator.FLOORDIV:
                return left.floordiv(right)
            elif expression.op is ast.Operator.MOD:
                return left.mod(right)
            elif expression.op is ast.Operator.POW:
                return left.pow(right)
            elif expression.op is ast.Operator.LSHIFT:
                return left.lshift(right)
            elif expression.op is ast.Operator.RSHIFT:
                return left.rshift(right)
            elif expression.op is ast.Operator.BITOR:
                return left.bitor(right)
            elif expression.op is ast.Operator.BITXOR:
                return left.bitxor(right)
            elif expression.op is ast.Operator.BITAND:
                return left.bitand(right)

        elif isinstance(expression, ast.UnaryOpNode):
            operand = self.evaluate_expression(expression.operand)

            if expression.op is ast.UnaryOperator.UADD:
                return operand.pos()
            elif expression.op is ast.UnaryOperator.USUB:
                return operand.neg()
            elif expression.op is ast.UnaryOperator.INVERT:
                return operand.invert()

        elif isinstance(expression, ast.SubscriptNode):
            value = self.evaluate_expression(expression.value)
            slice = self.evaluate_expression(expression.slice)

            return value.getitem(slice)

        elif isinstance(expression, ast.SliceNode):
            start = stop = step = None

            if expression.start is not None:
                start = self.evaluate_expression(expression.start)
            if expression.stop is not None:
                stop = self.evaluate_expression(expression.stop)
            if expression.step is not None:
                step = self.evaluate_expression(expression.step)

            return types.SliceType(start=start, stop=stop, step=step)

        elif isinstance(expression, ast.AttributeNode):
            value = self.evaluate_expression(expression.value)
            return value.getattribute(expression.attr)

        elif isinstance(expression, ast.IfExpNode):
            condition = self.evaluate_expression(expression.condition).truthness()

            if condition is True:
                return self.evaluate_expression(expression.body)
            elif condition is False:
                return self.evaluate_expression(expression.else_body)

            return types.union((
                self.evaluate_expression(expression.body),
                self.evaluate_expression(expression.else_body),
            ))

        elif isinstance(expression, ast.CallNode):
            func = self.evaluate_expression(expression.func)

            args = [self.evaluate_expression(arg) for arg in expression.args]
            kwargs = {
                kwarg.name: self.evaluate_expression(kwarg.value)
                for kwarg in expression.kwargs
            }
            return func.call(args, kwargs)

        elif isinstance(expression, ast.SetNode):
            value = types.union(
                self.evaluate_expression(elt, mutable=True) for elt in expression.elts
            )
            return types.SetType(value=value)

        elif isinstance(expression, ast.DictNode):
            keys: typing.List[types.Type] = []
            values: typing.List[types.Type] = []

            for elt in expression.elts:
                value = self.evaluate_expression(elt.value, mutable=True)

                if elt.key is not None:
                    keys.append(self.evaluate_expression(elt.key, mutable=True))
                    values.append(value)
                else:
                    if not isinstance(value, types.DictType):
                        assert False, 'can only unpack dict'

                    keys.append(value.key)
                    values.append(value.value)

            return types.DictType(key=types.union(keys), value=types.union(values))

        elif isinstance(expression, ast.TupleNode):
            values = [self.evaluate_expression(elt) for elt in expression.elts]
            return types.TupleType(values=values)

        elif isinstance(expression, ast.ListNode):
            value = types.union(
                self.evaluate_expression(elt, mutable=True) for elt in expression.elts
            )
            return types.ListType(value=value, size=len(expression.elts))

        assert False, 'Invalid Expression'

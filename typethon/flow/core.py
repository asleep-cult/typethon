from __future__ import annotations

from . import nodes
from .. import ast
from ..analyzation import atoms, AtomEvaluator
from ..parser import NodeVisitor


class FlowCore(NodeVisitor[nodes.AtomFlow]):
    def __init__(self) -> None:
        self.evaluator = AtomEvaluator()

    def requires_flow(self, atom: atoms.Atom) -> bool:
        if isinstance(atom, atoms.LiteralAtom):
            return atom.value is None and atom.kind is not atoms.AtomKind.NONE

        elif atom.kind is atoms.AtomKind.OBJECT:
            return atom.value is None or self.requires_flow(atom.value)

        return not atom.is_type()

    def bind_atom(
        self, expression: ast.ExpressionNode, atom: atoms.Atom
    ) -> nodes.AtomFlow:
        return nodes.AtomFlow(
            startpos=expression.startpos,
            endpos=expression.endpos,
            atom=atom,
        )

    def visit_boolop_node(self, expression: ast.BoolOpNode) -> nodes.AtomFlow:
        atom = self.evaluator.visit_boolop_node(expression)
        if not self.requires_flow(atom):
            return self.bind_atom(expression, atom)

        operands = [self.visit_expression(value) for value in expression.values]

        return nodes.BoolOpFlow(
            startpos=expression.startpos,
            endpos=expression.endpos,
            atom=atom,
            op=expression.op,
            operands=operands,
        )

    def visit_binaryop_node(self, expression: ast.BinaryOpNode) -> nodes.AtomFlow:
        atom = self.evaluator.visit_binaryop_node(expression)
        if not self.requires_flow(atom):
            return self.bind_atom(expression, atom)

        left = self.visit_expression(expression.left)
        right = self.visit_expression(expression.right)

        return nodes.BinaryOpFlow(
            startpos=expression.startpos,
            endpos=expression.endpos,
            atom=atom,
            left=left,
            op=expression.op,
            right=right,
        )

    def visit_constant_node(self, expression: ast.ConstantNode) -> nodes.AtomFlow:
        atom = self.evaluator.visit_constant_node(expression)
        return self.bind_atom(expression, atom)

    def visit_attribute_node(self, expression: ast.AttributeNode) -> nodes.AtomFlow:
        atom = self.evaluator.visit_attribute_node(expression)
        if not self.requires_flow(atom):
            return self.bind_atom(expression, atom)

        value = self.visit_expression(expression.value)

        return nodes.AttributeFlow(
            startpos=expression.startpos,
            endpos=expression.endpos,
            atom=atom,
            value=value,
            attribute=expression.attr,
        )

from __future__ import annotations

import typing

from .. import ast
from ..atomize import atomizer, atoms
from ..parse import NodeVisitor
from . import nodes


class FlowCore(NodeVisitor[nodes.AtomFlow]):
    def __init__(self) -> None:
        self.atomizer = atomizer.Atomizer()

    def requires_flow(self, atom: atoms.Atom) -> bool:
        if isinstance(atom, atoms.LiteralAtom):
            return atom.value is None and atom.kind is not atoms.AtomKind.NONE

        elif atom.kind is atoms.AtomKind.OBJECT:
            return atom.value is None or self.requires_flow(atom.value)

        elif atom.kind is atoms.AtomKind.TUPLE:
            if atom.values is not None:
                return any(self.requires_flow(value) for value in atom.values)

        return not atom.is_type()

    def bind_atom(self, expression: ast.ExpressionNode, atom: atoms.Atom) -> nodes.AtomFlow:
        return nodes.AtomFlow(
            startpos=expression.startpos,
            endpos=expression.endpos,
            atom=atom,
        )

    def visit_boolop_node(self, expression: ast.BoolOpNode) -> nodes.AtomFlow:
        atom = self.atomizer.visit_boolop_node(expression)
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
        atom = self.atomizer.visit_binaryop_node(expression)
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

    def visit_unaryop_node(self, expression: ast.UnaryOpNode) -> nodes.AtomFlow:
        atom = self.atomizer.visit_unaryop_node(expression)
        if not self.requires_flow(atom):
            return self.bind_atom(expression, atom)

        operand = self.visit_expression(expression.operand)

        return nodes.UnaryOpFlow(
            startpos=expression.startpos,
            endpos=expression.endpos,
            atom=atom,
            op=expression.op,
            operand=operand,
        )

    def visit_ifexp_node(self, expression: ast.IfExpNode) -> nodes.AtomFlow:
        atom = self.atomizer.visit_ifexp_node(expression)
        if not self.requires_flow(atom):
            return self.bind_atom(expression, atom)

        condition = self.visit_expression(expression.condition)
        body = self.visit_expression(expression.body)
        else_body = self.visit_expression(expression.else_body)

        return nodes.IfExpFlow(
            startpos=expression.startpos,
            endpos=expression.endpos,
            atom=atom,
            condition=condition,
            body=body,
            else_body=else_body,
        )

    def visit_dict_node(self, expression: ast.DictNode) -> nodes.AtomFlow:
        atom = self.atomizer.visit_dict_node(expression)
        if not self.requires_flow(atom):
            return self.bind_atom(expression, atom)

        elts: typing.List[nodes.DictElt] = []

        for elt in expression.elts:
            key = self.visit_expression(elt.key) if elt.key is not None else None
            value = self.visit_expression(elt.value)

            elts.append(nodes.DictElt(key=key, value=value))

        return nodes.DictFlow(
            startpos=expression.startpos,
            endpos=expression.endpos,
            atom=atom.unwrap_as(atoms.DictAtom),
            elts=elts,
        )

    def visit_set_node(self, expression: ast.SetNode) -> nodes.AtomFlow:
        atom = self.atomizer.visit_set_node(expression)
        if not self.requires_flow(atom):
            return self.bind_atom(expression, atom)

        elts = [self.visit_expression(elt) for elt in expression.elts]

        return nodes.SetFlow(
            startpos=expression.startpos,
            endpos=expression.endpos,
            atom=atom.unwrap_as(atoms.SetAtom),
            elts=elts,
        )

    def visit_call_node(self, expression: ast.CallNode) -> nodes.AtomFlow:
        atom = self.atomizer.visit_call_node(expression)
        if not self.requires_flow(atom):
            return self.bind_atom(expression, atom)

        function = self.visit_expression(expression.func)
        arguments = [self.visit_expression(arg) for arg in expression.args]

        keywords: typing.List[nodes.KeywordArgument] = []

        for argument in expression.kwargs:
            value = self.visit_expression(argument.value)
            keywords.append(nodes.KeywordArgument(name=argument.name, value=value))

        return nodes.CallFlow(
            startpos=expression.startpos,
            endpos=expression.endpos,
            atom=atom,
            function=function,
            arguments=arguments,
            keywords=keywords,
        )

    def visit_constant_node(self, expression: ast.ConstantNode) -> nodes.AtomFlow:
        atom = self.atomizer.visit_constant_node(expression)
        return self.bind_atom(expression, atom)

    def visit_attribute_node(self, expression: ast.AttributeNode) -> nodes.AtomFlow:
        atom = self.atomizer.visit_attribute_node(expression)
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

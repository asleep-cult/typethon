import inspect
import typing

from .. import ast

VisitT = typing.TypeVar('VisitT')


class NodeVisitor(typing.Generic[VisitT]):
    expression_visitors: typing.Dict[
        typing.Type[ast.ExpressionNode], typing.Callable[[ast.ExpressionNode], VisitT]
    ]
    statement_visitors: typing.Dict[
        typing.Type[ast.StatementNode], typing.Callable[[ast.StatementNode], None]
    ]

    def initialize_visitors(self) -> None:
        self.expression_visitors = {}
        self.statement_visitors = {}

        for member in inspect.getmembers(self, inspect.ismethod):
            function = member[1]

            if function.__name__ in ('visit_expression', 'visit_statement'):
                continue

            annotations = inspect.get_annotations(function)

            expression = annotations.get('expression')
            if expression is not None:
                self.expression_visitors[expression] = function

            statement = annotations.get('statement')
            if statement is not None:
                self.statement_visitors[statement] = function

    def visit_functiondef_node(self, statement: ast.FunctionDefNode) -> VisitT:
        raise NotImplementedError

    def visit_classdef_node(self, statement: ast.ClassDefNode) -> VisitT:
        raise NotImplementedError

    def visit_return_node(self, statement: ast.ReturnNode) -> VisitT:
        raise NotImplementedError

    def visit_delete_node(self, statement: ast.DeleteNode) -> VisitT:
        raise NotImplementedError

    def visit_assign_node(self, statement: ast.AssignNode) -> VisitT:
        raise NotImplementedError

    def visit_augassign_node(self, statement: ast.AugAssignNode) -> VisitT:
        raise NotImplementedError

    def visit_annassign_node(self, statement: ast.AnnAssignNode) -> VisitT:
        raise NotImplementedError

    def visit_for_node(self, statement: ast.ForNode) -> VisitT:
        raise NotImplementedError

    def visit_while_node(self, statement: ast.WhileNode) -> VisitT:
        raise NotImplementedError

    def visit_if_node(self, statement: ast.IfNode) -> VisitT:
        raise NotImplementedError

    def visit_raise_node(self, statement: ast.RaiseNode) -> VisitT:
        raise NotImplementedError

    def visit_try_node(self, statement: ast.TryNode) -> VisitT:
        raise NotImplementedError

    def visit_assert_node(self, statement: ast.AssertNode) -> VisitT:
        raise NotImplementedError

    def visit_import_node(self, statement: ast.ImportNode) -> VisitT:
        raise NotImplementedError

    def visit_importfrom_node(self, statement: ast.ImportFromNode) -> VisitT:
        raise NotImplementedError

    def visit_global_node(self, statement: ast.GlobalNode) -> VisitT:
        raise NotImplementedError

    def visit_nonlocal_node(self, statement: ast.NonlocalNode) -> VisitT:
        raise NotImplementedError

    def visit_expr_node(self, statement: ast.ExprNode) -> VisitT:
        raise NotImplementedError

    def visit_pass_node(self, statement: ast.PassNode) -> VisitT:
        raise NotImplementedError

    def visit_break_node(self, statement: ast.BreakNode) -> VisitT:
        raise NotImplementedError

    def visit_continue_node(self, statement: ast.ContinueNode) -> VisitT:
        raise NotImplementedError

    def visit_boolop_node(self, expression: ast.BoolOpNode) -> VisitT:
        raise NotImplementedError

    def visit_binop_node(self, expression: ast.BinaryOpNode) -> VisitT:
        raise NotImplementedError

    def visit_unaryop_node(self, expression: ast.UnaryOpNode) -> VisitT:
        raise NotImplementedError

    def visit_lambda_node(self, expression: ast.LambdaNode) -> VisitT:
        raise NotImplementedError

    def visit_ifexp_node(self, expression: ast.IfExpNode) -> VisitT:
        raise NotImplementedError

    def visit_dict_node(self, expression: ast.DictNode) -> VisitT:
        raise NotImplementedError

    def visit_set_node(self, expression: ast.SetNode) -> VisitT:
        raise NotImplementedError

    def visit_listcomp_node(self, expression: ast.ListCompNode) -> VisitT:
        raise NotImplementedError

    def visit_setcomp_node(self, expression: ast.ExpressionNode) -> VisitT:
        raise NotImplementedError

    def visit_dictcomp_node(self, expression: ast.DictCompNode) -> VisitT:
        raise NotImplementedError

    def visit_genexp_node(self, expression: ast.GeneratorExpNode) -> VisitT:
        raise NotImplementedError

    def visit_await_node(self, expression: ast.AwaitNode) -> VisitT:
        raise NotImplementedError

    def visit_yield_node(self, expression: ast.YieldNode) -> VisitT:
        raise NotImplementedError

    def visit_yieldfrom_node(self, expression: ast.YieldFromNode) -> VisitT:
        raise NotImplementedError

    def visit_compare_node(self, expression: ast.ComparatorNode) -> VisitT:
        raise NotImplementedError

    def visit_call_node(self, expression: ast.CallNode) -> VisitT:
        raise NotImplementedError

    def visit_formattedvalue_node(self, expression: ast.FormattedValueNode) -> VisitT:
        raise NotImplementedError

    def visit_constant_node(self, expression: ast.ConstantNode) -> VisitT:
        raise NotImplementedError

    def visit_attribute_node(self, expression: ast.AttributeNode) -> VisitT:
        raise NotImplementedError

    def visit_subscript_node(self, expression: ast.SubscriptNode) -> VisitT:
        raise NotImplementedError

    def visit_starred_node(self, expression: ast.StarredNode) -> VisitT:
        raise NotImplementedError

    def visit_name_node(self, expression: ast.NameNode) -> VisitT:
        raise NotImplementedError

    def visit_list_node(self, expression: ast.ListNode) -> VisitT:
        raise NotImplementedError

    def visit_tuple_node(self, expression: ast.TupleNode) -> VisitT:
        raise NotImplementedError

    def visit_slice_node(self, expression: ast.SliceNode) -> VisitT:
        raise NotImplementedError

    def visit_expression(self, expression: ast.ExpressionNode) -> VisitT:
        if isinstance(expression, ast.ConstantNode):
            return self.visit_constant_node(expression)
        else:
            visitor = self.expression_visitors.get(type(expression))

        if visitor is not None:
            return visitor(expression)

        raise TypeError(f'No visitor implemented for {expression.__class__.__name__!r}')

    def visit_statement(self, statement: ast.StatementNode) -> None:
        visitor = self.statement_visitors.get(type(statement))
        if visitor is not None:
            return visitor(statement)

        raise TypeError(f'No visitor implemented for {statement.__class__.__name__!r}')

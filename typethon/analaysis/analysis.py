import attr
import enum
import typing

from . import types
from .initialization import TypedNode
from .resolution import SymbolNode
from ..diagnostics import DiagnosticReporter
from ..syntax.typethon import ast


AnalysisUnit = typing.Union[types.Type, types.TypeInstance]


class AnalysisFlags(enum.Flag):
    NONE = 0
    ALLOW_BREAK = enum.auto()
    ALLOW_CONTINUE = enum.auto()


@attr.s(kw_only=True, slots=True)
class AnalysisContext:
    flags: AnalysisFlags = attr.ib()
    returnable_type: typing.Optional[types.Type] = attr.ib()
    self_type: typing.Optional[types.Type] = attr.ib()


@attr.s(kw_only=True, slots=True)
class TypeAnalyzer:
    diagnostics: DiagnosticReporter = attr.ib()
    module: ast.ModuleNode = attr.ib()
    resolved_symbols: typing.Dict[int, SymbolNode] = attr.ib()
    type_nodes: typing.Dict[int, types.Type] = attr.ib()
    declaration_nodes: typing.Dict[int, types.TypeInstance] = attr.ib(factory=dict)

    def report_error(
        self,
        node: ast.Node,
        message: str,
        *format: str,
    ) -> None:
        self.diagnostics.report_error((node.start, node.end), message, *format)

    def assert_instance(
        self,
        unit: AnalysisUnit,
        node: ast.Node,
        as_what: str
    ) -> typing.TypeGuard[types.TypeInstance]:
        if isinstance(unit, types.TypeInstance):
            return True

        self.report_error(node, f'Cannot use type as {as_what}')
        return False

    def get_type_node(self, node: TypedNode) -> types.Type:
        if node.id in self.type_nodes:
            return self.type_nodes[node.id]

        assert False, f'Failed to resolve type {node!r}'

    def get_type_or_declaration_node(self, node: TypedNode) -> AnalysisUnit:
        if node.id in self.declaration_nodes:
            return self.declaration_nodes[node.id]

        if node.id in self.type_nodes:
            return self.type_nodes[node.id]

        assert False, f'Failed to resolve the type or declaration {node!r}'

    def analyze_block(self, ctx: AnalysisContext, body: typing.List[ast.StatementNode]) -> None:
        for statement in body:
            self.analyze_statement(ctx, statement)

    def analyze_statement(self, ctx: AnalysisContext, statement: ast.StatementNode) -> None:
        match statement:
            case ast.TypeDeclarationNode() | ast.SumTypeNode():
                self.get_type_node(statement)

            case ast.FunctionDefNode():
                function_type = self.get_type_node(statement)
                assert isinstance(function_type, types.FunctionType)

                for parameter in statement.parameters:
                    instance = types.to_instance(function_type.parameters[parameter.name])
                    self.declaration_nodes[parameter.id] = instance

                if statement.body is not None:
                    inner_ctx = AnalysisContext(
                        flags=AnalysisFlags.NONE,
                        returnable_type=function_type.returns,
                        self_type=ctx.self_type,
                    )
                    self.analyze_block(inner_ctx, statement.body)

            case ast.ClassDefNode():
                class_type = self.get_type_node(statement)
                assert isinstance(class_type, types.TypeClass)

                inner_ctx = AnalysisContext(
                    flags=AnalysisFlags.NONE,
                    returnable_type=None,
                    self_type=class_type,
                )
                self.analyze_block(inner_ctx, statement.body)

            case ast.UseNode():
                type = self.get_type_node(statement.type)
                inner_ctx = AnalysisContext(
                    flags=AnalysisFlags.NONE,
                    returnable_type=None,
                    self_type=type,
                )
                self.analyze_block(inner_ctx, statement.body)

            case ast.UseForNode():
                type = self.get_type_node(statement.type)
                type_class = self.get_type_node(statement.type_class)
                inner_ctx = AnalysisContext(
                    flags=AnalysisFlags.NONE,
                    returnable_type=None,
                    self_type=type,
                )
                self.analyze_block(inner_ctx, statement.body)

            case ast.DeclarationNode():
                type = types.SingletonType.UNDECLARED
                if statement.type is not None:
                    type = self.get_type_node(statement.type)

                if statement.value is not None:
                    value = self.analyze_expression(statement.value)
                    assert type is value and False, 'TODO!'

                self.declaration_nodes[statement.id] = types.to_instance(type)

            case ast.ForNode():
                iterator = self.analyze_expression(statement.iterator)
                assert iterator # TODO
                inner_ctx = AnalysisContext(
                    flags=ctx.flags | AnalysisFlags.ALLOW_BREAK | AnalysisFlags.ALLOW_CONTINUE,
                    returnable_type=ctx.returnable_type,
                    self_type=ctx.self_type,
                )
                self.analyze_block(inner_ctx, statement.body)

            case ast.WhileNode():
                self.analyze_expression(statement.condition)
                inner_ctx = AnalysisContext(
                    flags=ctx.flags | AnalysisFlags.ALLOW_BREAK | AnalysisFlags.ALLOW_CONTINUE,
                    returnable_type=ctx.returnable_type,
                    self_type=ctx.self_type,
                )
                self.analyze_block(inner_ctx, statement.body)

            case ast.IfNode():
                self.analyze_expression(statement.condition)
                self.analyze_block(ctx, statement.body)
                if statement.else_statement is not None:
                    self.analyze_block(ctx, statement.else_statement.body)

            case ast.ReturnNode():
                if not ctx.returnable_type is not None:
                    self.report_error(statement, 'Return is only valid in functions')

                if statement.value is not None:
                    unit = self.analyze_expression(statement.value)
                    if not self.assert_instance(unit, statement.value, 'return value'):
                        return
                else:
                    unit = types.UNIT

                # TODO: is unit compativle with ctx.returnable_type

            case ast.BreakNode():
                if not ctx.flags & AnalysisFlags.ALLOW_BREAK:
                    self.report_error(statement, 'Break is only valid in for or while loops')

            case ast.ContinueNode():
                if not ctx.flags & AnalysisFlags.ALLOW_CONTINUE:
                    self.report_error(statement, 'Continue is only valid in for or while loops')

            case ast.ExprNode():
                self.analyze_expression(statement.expr)

    def analyze_expression(self, expression: ast.ExpressionNode) -> AnalysisUnit:
        match expression:
            case ast.NameNode():
                if expression.id not in self.resolved_symbols:
                    return types.SingletonType.INVALID

                node = self.resolved_symbols[expression.id]
                return self.get_type_or_declaration_node(node)

            case ast.CompareNode():
                # I just realized the comparator chaning doesn't even work like this,
                # I will need to fix it.
                unit = self.analyze_expression(expression.left)
                comparators: typing.List[
                    typing.Tuple[ast.CmpOperatorKind, types.TypeInstance]
                ] = []

                for comparator in expression.comparators:
                    comparator_unit = self.analyze_expression(comparator.value)
                    if self.assert_instance(comparator_unit, comparator, 'comparison value'):
                        comparators.append((comparator.op, comparator_unit))

                if not self.assert_instance(unit, expression, 'comparison value'):
                    return types.to_instance(types.SingletonType.BOOL)

                for i, (operator, instance) in enumerate(comparators):
                    # TODO!
                    self.report_error(
                        expression.comparators[i],
                        'Unsupported comparison between {0} {1} and {2}',
                        str(operator),
                        str(unit),
                        str(instance),
                    )

                return types.to_instance(types.SingletonType.BOOL)

        self.report_error(expression, 'Failed to determine type of expression')
        return types.SingletonType.INVALID

    def analyze_module(self) -> None:
        ctx = AnalysisContext(
            flags=AnalysisFlags.NONE,
            returnable_type=None,
            self_type=None,
        )
        self.analyze_block(ctx, self.module.body)

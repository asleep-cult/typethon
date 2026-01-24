import attr
import enum
import typing

from . import types
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
    type_nodes: typing.Dict[int, types.Type] = attr.ib(factory=dict)
    declaraion_nodes: typing.Dict[int, types.TypeInstance] = attr.ib(factory=dict)
    # We don't need to think about scoping at all because the SymbolResolver
    # maps every single NameNode to a SymbolNode (which may be a declaration,
    # or a class, or a function, or a type parameter, etc.)

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

    def create_struct_declaration(self, node: ast.TypeDeclarationNode) -> types.StructType:
        assert isinstance(node.type, ast.StructTypeNode)

        fields: typing.Dict[str, types.Type] = {}
        struct_type = types.StructType(name=node.name, is_declaration=True, fields=fields)
        self.type_nodes[node.id] = struct_type

        for field in node.type.fields:
            fields[field.name] = self.evaulate_type_expression(field.type)

        return struct_type

    def create_tuple_declaration(self, node: ast.TypeDeclarationNode) -> types.TupleType:
        assert isinstance(node.type, ast.TupleTypeNode)

        elts: typing.List[types.Type] = []
        tuple_type = types.TupleType(name=node.name, is_declaration=True, elts=elts)
        self.type_nodes[node.id] = tuple_type

        for elt in node.type.elts:
            elts.append(self.evaulate_type_expression(elt))

        return tuple_type

    def create_sum_type(self, node: ast.SumTypeNode) -> types.SumType:
        fields: typing.Dict[str, typing.Optional[types.DataType]] = {}
        sum_type = types.SumType(name=node.name, types=fields)
        self.type_nodes[node.id] = sum_type

        for field in node.fields:
            if field.data_type is not None:
                assert False, 'TODO!'
            else:
                fields[field.name] = None

        return sum_type

    def create_function(self, node: ast.FunctionDefNode) -> types.FunctionType:
        parameters: typing.Dict[str, types.Type] = {}
        function_type = types.FunctionType(
            name=node.name,
            parameters=parameters,
            returns=types.SingletonType.INVALID,
        )
        self.type_nodes[node.id] = function_type

        for parameter in node.parameters:
            parameters[parameter.name] = self.evaulate_type_expression(parameter.annotation)

        function_type.returns = self.evaulate_type_expression(node.returns)
        return function_type

    def create_type_class(self, node: ast.ClassDefNode) -> types.TypeClass:
        functions: typing.Dict[str, types.FunctionType] = {}
        type_class = types.TypeClass(name=node.name, functions=functions)
        self.type_nodes[node.id] = type_class

        for statement in node.body:
            if isinstance(statement, ast.FunctionDefNode):
                function = self.get_type_node(statement)
                assert isinstance(function, types.FunctionType)
                functions[statement.name] = function

        return type_class

    def create_type_parameter(self, node: ast.TypeParameterNode) -> types.TypeParameter:
        type_parameter = types.TypeParameter(name=node.name)
        self.type_nodes[node.id] = type_parameter
        return type_parameter

    def get_type_node(self, node: SymbolNode) -> types.Type:
        if node.id in self.type_nodes:
            return self.type_nodes[node.id]

        match node:
            case ast.SumTypeNode():
                return self.create_sum_type(node)
            case ast.TypeDeclarationNode():
                if isinstance(node, ast.StructTypeNode):
                    return self.create_struct_declaration(node)
                elif isinstance(node, ast.TupleTypeNode):
                    return self.create_tuple_declaration(node)
                else:
                    assert False, 'TODO!'
            case ast.TypeParameterNode():
                return self.create_type_parameter(node)
            case ast.ClassDefNode():
                return self.create_type_class(node)
            case ast.FunctionDefNode():
                return self.create_function(node)
            case (
                ast.DeclarationNode()
                | ast.FunctionParameterNode()
                | ast.LambdaParameterNode()
            ):
                assert False, f'Declaration nodes are not valid in this context'

    def get_type_or_declaration_node(self, node: SymbolNode) -> AnalysisUnit:
        if node.id in self.declaraion_nodes:
            return self.declaraion_nodes[node.id]

        match node:
            case (
                ast.DeclarationNode()
                | ast.FunctionParameterNode()
                | ast.LambdaParameterNode()
            ):
                assert False, f'Encountered declaration {node!r} before it was declaraed'
            case _:
                return self.get_type_node(node)

    def evaulate_type_expression(
        self,
        type_expression: ast.TypeExpressionNode,
    ) -> types.Type:
        match type_expression:
            case ast.NameNode():
                if type_expression.id not in self.resolved_symbols:
                    return types.SingletonType.INVALID

                node = self.resolved_symbols[type_expression.id]
                return self.get_type_node(node)
            case ast.SelfTypeNode():
                return types.SingletonType.SELF
            case ast.TypeParameterNode():
                return self.get_type_node(type_expression)
            case ast.TypeCallNode():
                type = self.evaulate_type_expression(type_expression.type)
                assert False, 'TODO!'
            case ast.TypeAttributeNode():
                type = self.evaulate_type_expression(type_expression.type)
                assert False, 'TODO!'
            case ast.ListTypeNode():
                assert False, 'TODO!'
            case ast.StructTypeNode():
                assert False, 'TODO!'
            case ast.TupleTypeNode():
                assert False, 'TODO!'

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
                    self.declaraion_nodes[parameter.id] = instance

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
                type = self.evaulate_type_expression(statement.type)
                inner_ctx = AnalysisContext(
                    flags=AnalysisFlags.NONE,
                    returnable_type=None,
                    self_type=type,
                )
                self.analyze_block(inner_ctx, statement.body)

            case ast.UseForNode():
                type = self.evaulate_type_expression(statement.type)
                type_class = self.evaulate_type_expression(statement.type_class)
                inner_ctx = AnalysisContext(
                    flags=AnalysisFlags.NONE,
                    returnable_type=None,
                    self_type=type,
                )
                self.analyze_block(inner_ctx, statement.body)

            case ast.DeclarationNode():
                type = types.SingletonType.UNDECLARED
                if statement.type is not None:
                    type = self.evaulate_type_expression(statement.type)

                if statement.value is not None:
                    value = self.analyze_expression(statement.value)
                    assert type is value and False, 'TODO!'

                self.declaraion_nodes[statement.id] = types.to_instance(type)

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

                print(unit)
                # TODO: is unit compativle with ctx.returnable_type

            case ast.BreakNode():
                if not ctx.flags & AnalysisFlags.ALLOW_BREAK:
                    self.report_error(statement, 'Break is only valid in for or while loops')

            case ast.ContinueNode():
                if not ctx.flags & AnalysisFlags.ALLOW_CONTINUE:
                    self.report_error(statement, 'Break is only valid in for or while loops')

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

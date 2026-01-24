import attr
import enum
import typing

from ..diagnostics import DiagnosticReporter
from ..syntax.typethon import ast


class ScopeKind(enum.Enum):
    MODULE = enum.auto()
    CLASS = enum.auto()
    USE = enum.auto()
    FUNCTION = enum.auto()
    BLOCK = enum.auto()
    DECLARATION = enum.auto()
    LAMBDA = enum.auto()


@attr.s(kw_only=True, slots=True)
class SymbolScope:
    node_id: int = attr.ib()
    kind: ScopeKind = attr.ib()
    type_declarations: typing.Dict[
        str, typing.Union[ast.SumTypeNode, ast.TypeDeclarationNode]
    ] = attr.ib(factory=dict)
    type_parameters: typing.Dict[str, ast.TypeParameterNode] = attr.ib(factory=dict)
    classes: typing.Dict[str, ast.ClassDefNode] = attr.ib(factory=dict)
    functions: typing.Dict[str, ast.FunctionDefNode] = attr.ib(factory=dict)
    declarations: typing.Dict[
        str,
        typing.Union[
            ast.DeclarationNode,
            ast.FunctionParameterNode,
            ast.LambdaParameterNode,
        ],
    ] = attr.ib(factory=dict)


SymbolNode = typing.Union[
    ast.SumTypeNode,
    ast.TypeDeclarationNode,
    ast.TypeParameterNode,
    ast.ClassDefNode,
    ast.FunctionDefNode,
    ast.DeclarationNode,
    ast.FunctionParameterNode,
    ast.LambdaParameterNode,
]


class SymbolResolver:
    def __init__(
        self,
        diagnostics: DiagnosticReporter,
        module: ast.ModuleNode,
    ) -> None:
        self.diagnostics = diagnostics
        self.module = module
        self.scopes: typing.Dict[int, SymbolScope] = {}
        self.scope_stack: typing.List[SymbolScope] = []
        self.resolved_symbols: typing.Dict[int, SymbolNode] = {}

    def get_current_scope(self) -> SymbolScope:
        return self.scope_stack[-1]

    def create_scope(self, node_id: int, kind: ScopeKind) -> SymbolScope:
        scope = SymbolScope(node_id=node_id, kind=kind)
        self.scopes[node_id] = scope
        return scope

    def initialize_symbols_for_block(
        self,
        scope: SymbolScope,
        body: typing.List[ast.StatementNode]
    ) -> None:
        for statement in body:
            self.initialize_symbols_for_statement(scope, statement)

    def initialize_symbols_for_statement(
        self,
        scope: SymbolScope,
        statement: ast.StatementNode,
    ) -> None:
        match statement:
            case ast.FunctionDefNode():
                scope.functions[statement.name] = statement
                scope = self.create_scope(statement.id, ScopeKind.FUNCTION)
                for parameter in statement.parameters:
                    self.initialize_type_parameters(scope, parameter.annotation)
                    scope.declarations[parameter.name] = parameter

                self.initialize_type_parameters(scope, statement.returns)
                if statement.body is not None:
                    self.initialize_symbols_for_block(scope, statement.body)

            case ast.ClassDefNode():
                scope.classes[statement.name] = statement
                scope = self.create_scope(statement.id, ScopeKind.CLASS)
                for parameter in statement.parameters:
                    self.initialize_type_parameters(scope, parameter)

                self.initialize_symbols_for_block(scope, statement.body)

            case ast.TypeDeclarationNode():
                scope.type_declarations[statement.name] = statement
                scope = self.create_scope(statement.id, ScopeKind.DECLARATION)
                self.initialize_type_parameters(scope, statement.type)

            case ast.SumTypeNode():
                scope.type_declarations[statement.name] = statement
                scope = self.create_scope(statement.id, ScopeKind.DECLARATION)

                for field in statement.fields:
                    if field.data_type is not None:
                        # XXX: If the type parameter syntax going to be
                        # problematic for unions?
                        self.initialize_type_parameters(scope, field.data_type)

            case ast.UseNode():
                scope = self.create_scope(statement.id, ScopeKind.USE)
                self.initialize_type_parameters(scope, statement.type)
                self.initialize_symbols_for_block(scope, statement.body)

            case ast.UseForNode():
                scope = self.create_scope(statement.id, ScopeKind.USE)
                self.initialize_type_parameters(scope, statement.type)
                self.initialize_type_parameters(scope, statement.type_class)
                self.initialize_symbols_for_block(scope, statement.body)

            case ast.DeclarationNode():
                # TODO: What about shadowing?
                scope.declarations[statement.target] = statement
                if statement.value is not None:
                    self.initialize_lambda_scopes(statement.value)

            case ast.ForNode() | ast.WhileNode():
                self.create_scope(statement.id, ScopeKind.BLOCK)
                self.initialize_symbols_for_block(scope, statement.body)

            case ast.IfNode():
                self.create_scope(statement.id, ScopeKind.BLOCK)
                self.initialize_symbols_for_block(scope, statement.body)

                if statement.else_statement is not None:
                    self.create_scope(statement.else_statement.id, ScopeKind.BLOCK)
                    self.initialize_symbols_for_block(scope, statement.else_statement.body)

            case ast.ReturnNode():
                if statement.value is not None:
                    self.initialize_lambda_scopes(statement.value)

            case ast.ExprNode():
                self.initialize_lambda_scopes(statement.expr)

    def initialize_lambda_scopes(
        self,
        expression: ast.ExpressionNode,
    ) -> None:
        for subexpression in ast.walk_expressions(expression):
            if isinstance(subexpression, (ast.ExpressionLambdaNode, ast.BlockLambdaNode)):
                scope = self.create_scope(subexpression.id, ScopeKind.LAMBDA)
                for parameter in subexpression.parameters:
                    scope.declarations[parameter.name] = parameter

                if isinstance(subexpression, ast.BlockLambdaNode):
                    self.initialize_symbols_for_block(scope, subexpression.body)
                else:
                    self.initialize_lambda_scopes(subexpression.body)

    def initialize_type_parameters(
        self,
        scope: SymbolScope,
        type_expression: ast.TypeExpressionNode,
    ) -> None:
        for subexpression in ast.walk_type_expressions(type_expression):
            if isinstance(subexpression, ast.TypeParameterNode):
                scope.type_parameters[subexpression.name] = subexpression

    def enter_node(self, node: ast.Node) -> SymbolScope:
        if node.id not in self.scopes:
            raise ValueError(f'Failed to locate scope for {node!r}')

        scope = self.scopes[node.id]
        self.scope_stack.append(scope)
        return scope

    def exit_node(self, node: ast.Node) -> SymbolScope:
        scope = self.scope_stack.pop()
        if scope.node_id != node.id:
            raise ValueError(f'Stack top mismatch when exiting node {node!r}')

        return scope

    def resolve_symbol(
        self,
        name: str,
        *,
        include_declarations: bool = True,
        include_functions: bool = True,
    ) -> typing.Optional[SymbolNode]:
        first_iteration = True
        can_access_type_parameters = True
        can_access_class_parameters = True
        can_access_declarations = include_declarations

        for scope in reversed(self.scope_stack):
            if can_access_declarations:
                if name in scope.declarations:
                    return scope.declarations[name]

            if can_access_type_parameters:
                if name in scope.type_parameters:
                    return scope.type_parameters[name]

            if (
                scope.kind is ScopeKind.CLASS
                and can_access_class_parameters
            ):
                if name in scope.type_parameters:
                    return scope.type_parameters[name]

                can_access_class_parameters = False

            if include_functions and name in scope.functions:
                return scope.functions[name]

            if name in scope.type_declarations:
                return scope.type_declarations[name]

            if name in scope.classes:
                return scope.classes[name]

            if (
                scope.kind is not ScopeKind.BLOCK
                and scope.kind is not ScopeKind.LAMBDA
            ):
                can_access_declarations = False
                can_access_type_parameters = False

                if not first_iteration:
                    can_access_class_parameters = False

            if first_iteration:
                first_iteration = False

    def resolve_symbols_for_block(self, statements: typing.List[ast.StatementNode]) -> None:
        for statement in statements:
            self.resolve_symbols_for_statement(statement)

    def resolve_symbols_for_statement(self, statement: ast.StatementNode) -> None:
        match statement:
            case ast.FunctionDefNode():
                self.enter_node(statement)

                for parameter in statement.parameters:
                    self.resolve_symbols_for_type_expression(parameter.annotation)

                self.resolve_symbols_for_type_expression(statement.returns)
                if statement.body is not None:
                    self.resolve_symbols_for_block(statement.body)

                self.exit_node(statement)

            case ast.ClassDefNode():
                self.enter_node(statement)
                self.resolve_symbols_for_block(statement.body)
                self.exit_node(statement)

            case ast.TypeDeclarationNode():
                self.enter_node(statement)
                self.resolve_symbols_for_type_expression(statement.type)
                self.exit_node(statement)

            case ast.SumTypeNode():
                self.enter_node(statement)

                for field in statement.fields:
                    if field.data_type is not None:
                        self.resolve_symbols_for_type_expression(field.data_type)

                self.exit_node(statement)

            case ast.UseNode() | ast.UseForNode():
                self.enter_node(statement)
                self.resolve_symbols_for_block(statement.body)
                self.exit_node(statement)

            case ast.DeclarationNode():
                if statement.value is not None:
                    self.resolve_symbols_for_expression(statement.value)

            case ast.ForNode() | ast.WhileNode():
                self.enter_node(statement)
                self.resolve_symbols_for_block(statement.body)
                self.exit_node(statement)

            case ast.IfNode():
                self.enter_node(statement)
                self.resolve_symbols_for_block(statement.body)
                self.exit_node(statement)

                if statement.else_statement is not None:
                    self.enter_node(statement.else_statement)
                    self.resolve_symbols_for_block(statement.else_statement.body)
                    self.exit_node(statement.else_statement)

            case ast.ReturnNode():
                if statement.value is not None:
                    self.resolve_symbols_for_expression(statement.value)

            case ast.ExprNode():
                self.resolve_symbols_for_expression(statement.expr)

    def resolve_symbols_for_type_expression(
        self,
        type_expression: ast.TypeExpressionNode,
    ) -> None:
        for subexpression in ast.walk_type_expressions(type_expression):
            if isinstance(subexpression, ast.NameNode):
                node = self.resolve_symbol(
                    subexpression.value,
                    include_declarations=False,
                    include_functions=False,
                )
                if node is None:
                    self.diagnostics.report_error(
                        (subexpression.start, subexpression.end),
                        'Unable to resolve type symbol `{0}`',
                        subexpression.value,
                    )
                else:
                    self.resolved_symbols[subexpression.id] = node

    def resolve_symbols_for_expression(self, expression: ast.ExpressionNode) -> None:
        for subexpression in ast.walk_expressions(expression):
            if isinstance(subexpression, ast.NameNode):
                node = self.resolve_symbol(subexpression.value)
                if node is None:
                    self.diagnostics.report_error(
                        (subexpression.start, subexpression.end),
                        'Unable to resolve symbol `{0}`',
                        subexpression.value,
                    )
                else:
                    self.resolved_symbols[subexpression.id] = node
            elif isinstance(subexpression, (ast.ExpressionLambdaNode, ast.BlockLambdaNode)):
                self.enter_node(subexpression)

                if isinstance(subexpression, ast.BlockLambdaNode):
                    self.resolve_symbols_for_block(subexpression.body)
                else:
                    self.resolve_symbols_for_expression(subexpression.body)

                self.exit_node(subexpression)

    def resolve_module_symbols(self) -> typing.Dict[int, SymbolNode]:
        scope = self.create_scope(self.module.id, ScopeKind.MODULE)
        self.initialize_symbols_for_block(scope, self.module.body)

        self.enter_node(self.module)
        self.resolve_symbols_for_block(self.module.body)
        self.exit_node(self.module)

        return self.resolved_symbols

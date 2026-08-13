from __future__ import annotations

import enum
import typing

import attr

from ..syntax.typethon import ast

if typing.TYPE_CHECKING:
    from . import asg


@attr.s(kw_only=True, slots=True)
class LocalDef:
    name: str = attr.ib()
    node_id: ast.NodeId = attr.ib()


class ScopeKind(enum.Enum):
    MODULE = enum.auto()
    CLASS = enum.auto()
    USE = enum.auto()
    FUNCTION = enum.auto()
    BLOCK = enum.auto()
    DEFINITION = enum.auto()
    LAMBDA = enum.auto()


@attr.s(kw_only=True, slots=True)
class SymbolScope:
    node_id: ast.NodeId = attr.ib()
    kind: ScopeKind = attr.ib()
    type_definitions: dict[str, asg.DefinitionId] = attr.ib(factory=dict)
    type_parameters: dict[str, asg.DefinitionId] = attr.ib(factory=dict)
    class_defs: dict[str, asg.DefinitionId] = attr.ib(factory=dict)
    function_defs: dict[str, asg.DefinitionId] = attr.ib(factory=dict)
    local_definitions: dict[str, LocalDef] = attr.ib(factory=dict)


class DefKind(enum.Enum):
    MODULE = enum.auto()
    STRUCT = enum.auto()
    TUPLE = enum.auto()
    SUM = enum.auto()
    VARIANT = enum.auto()
    FUNCTION = enum.auto()
    CLASS = enum.auto()
    TYPE_PARAMETER = enum.auto()
    FIELD = enum.auto()
    USE = enum.auto()
    NEW_TYPE = enum.auto()


class ResultKind(enum.Enum):
    ERROR = enum.auto()


@attr.s(kw_only=True, slots=True)
class DefResult:
    kind: DefKind = attr.ib()
    def_id: asg.DefinitionId = attr.ib()


@attr.s(kw_only=True, slots=True)
class LocalResult:
    node_id: ast.NodeId = attr.ib()


type ResolvedSymbol = DefResult | LocalResult | typing.Literal[ResultKind.ERROR]


@attr.s(kw_only=True, slots=True)
class SymbolResolver:
    # Prior to resolving symbols, the resolver must initialize all definitions and type parameters.
    # The resolver is subsequently used by AsgLowering for path and name resolution.
    # AsgLowering is responsible for calling the add_local_definition because it is the only
    # case where a name cannot be used in its scope before it has been defined.

    asg_ctx: asg.AsgContext = attr.ib()
    scopes: dict[ast.NodeId, SymbolScope] = attr.ib(factory=dict)
    scope_stack: list[SymbolScope] = attr.ib(factory=list)

    def create_scope(
        self,
        node_id: ast.NodeId,
        kind: ScopeKind,
    ) -> SymbolScope:
        scope = SymbolScope(node_id=node_id, kind=kind)
        self.scopes[node_id] = scope

        def_id = self.asg_ctx.def_nodes.get(node_id)
        param_index = self.asg_ctx.def_index.def_params.get(def_id)
        if param_index is not None:
            scope.type_parameters.update(param_index.paremeters)

        return scope

    def initialize_symbols_for_block(
        self,
        parent_id: asg.DefinitionId,
        scope: SymbolScope,
        body: list[ast.StatementNode],
    ) -> None:
        for statement in body:
            self.initialize_symbols_for_statement(parent_id, scope, statement)

    def add_local_definition(
        self,
        name: str,
        parent_id: asg.DefinitionId,
        node_id: ast.NodeId,
    ) -> None:
        scope = self.scope_stack[-1]
        definition = LocalDef(
            name=name,
            node_id=node_id,
        )
        scope.local_definitions[name] = definition

    def initialize_symbols_for_statement(
        self,
        parent_id: asg.DefinitionId,
        scope: SymbolScope,
        statement: ast.StatementNode,
    ) -> None:
        match statement:
            case ast.FunctionDefNode():
                def_id = self.asg_ctx.def_id_for_node(statement.id)
                scope.function_defs[statement.name] = def_id
                scope = self.create_scope(statement.id, ScopeKind.FUNCTION)

                for parameter in statement.parameters:
                    self.add_local_definition(parameter.name, def_id, parameter.id)

                if statement.body is not None:
                    self.initialize_symbols_for_block(def_id, scope, statement.body)

            case ast.ClassDefNode():
                def_id = self.asg_ctx.def_id_for_node(statement.id)
                scope.class_defs[statement.name] = def_id

                scope = self.create_scope(statement.id, ScopeKind.CLASS)
                self.initialize_symbols_for_block(def_id, scope, statement.body)

            case ast.TypeDefinitionNode():
                def_id = self.asg_ctx.def_id_for_node(statement.id)
                scope.type_definitions[statement.name] = def_id

            case ast.SumTypeNode():
                def_id = self.asg_ctx.def_id_for_node(statement.id)
                scope.type_definitions[statement.name] = def_id

            case ast.UseNode():
                def_id = self.asg_ctx.def_id_for_node(statement.id)
                scope = self.create_scope(statement.id, ScopeKind.USE)
                self.initialize_symbols_for_block(def_id, scope, statement.body)

            case ast.UseAsNode():
                def_id = self.asg_ctx.def_id_for_node(statement.id)
                scope = self.create_scope(statement.id, ScopeKind.USE)
                self.initialize_symbols_for_block(def_id, scope, statement.body)

            case ast.ForNode():
                self.create_scope(statement.id, ScopeKind.BLOCK)
                self.initialize_lambdas(parent_id, statement.target)
                self.initialize_lambdas(parent_id, statement.iterator)
                self.initialize_symbols_for_block(parent_id, scope, statement.body)

            case ast.WhileNode():
                self.create_scope(statement.id, ScopeKind.BLOCK)
                self.initialize_lambdas(parent_id, statement.condition)
                self.initialize_symbols_for_block(parent_id, scope, statement.body)

            case ast.IfNode():
                self.create_scope(statement.id, ScopeKind.BLOCK)
                self.initialize_lambdas(parent_id, statement.condition)
                self.initialize_symbols_for_block(parent_id, scope, statement.body)

                if statement.else_statement is not None:
                    self.create_scope(statement.else_statement.id, ScopeKind.BLOCK)
                    self.initialize_symbols_for_block(
                        parent_id, scope, statement.else_statement.body
                    )

            case ast.AssignNode() | ast.AugAssignNode():
                self.initialize_lambdas(parent_id, statement.target)
                if statement.value is not None:
                    self.initialize_lambdas(parent_id, statement.value)

            case ast.ReturnNode() if statement.value is not None:
                self.initialize_lambdas(parent_id, statement.value)

            case ast.ExprNode():
                self.initialize_lambdas(parent_id, statement.expr)

    def initialize_lambdas(
        self,
        parent_id: asg.DefinitionId,
        expression: ast.ExpressionNode,
    ) -> None:
        for subexpression in ast.walk_expressions(expression):
            if isinstance(subexpression, ast.LambdaNode):
                def_id = self.asg_ctx.def_index.def_id(
                    DefKind.FUNCTION, subexpression.id
                )
                self.asg_ctx.record_parent(def_id, parent_id)
                self.asg_ctx.def_index.index_block(def_id, subexpression.body)

                for parameter in subexpression.parameters:
                    if parameter.type is not None:
                        self.asg_ctx.def_index.index_type_parameters(
                            parent_id, def_id, parameter.type
                        )

                if subexpression.returns is not None:
                    self.asg_ctx.def_index.index_type_parameters(
                        parent_id, def_id, subexpression.returns
                    )

                scope = self.create_scope(subexpression.id, ScopeKind.LAMBDA)
                for parameter in subexpression.parameters:
                    self.add_local_definition(parameter.name, def_id, parameter.id)

                self.initialize_symbols_for_block(def_id, scope, subexpression.body)

    def enter_node(self, node: ast.Node) -> SymbolScope:
        if node.id not in self.scopes:
            raise ValueError(f"Failed to locate scope for {node!r}")

        scope = self.scopes[node.id]
        self.scope_stack.append(scope)
        return scope

    def exit_node(self, node: ast.Node) -> SymbolScope:
        scope = self.scope_stack.pop()
        if scope.node_id != node.id:
            raise ValueError(f"Stack top mismatch when exiting node {node!r}")

        return scope

    def resolve_symbol(
        self,
        name: str,
        *,
        include_local_definitions: bool = True,
        include_functions: bool = True,
        include_type_parameters: bool = True,
        include_type_definitions: bool = True,
        include_classes: bool = True,
    ) -> ResolvedSymbol:
        first_iteration = True
        can_access_type_parameters = include_type_parameters
        can_access_class_parameters = True
        can_access_definitions = include_local_definitions

        for scope in reversed(self.scope_stack):
            if can_access_definitions and name in scope.local_definitions:
                return LocalResult(node_id=scope.local_definitions[name].node_id)

            if can_access_type_parameters and name in scope.type_parameters:
                return DefResult(
                    kind=DefKind.TYPE_PARAMETER, def_id=scope.type_parameters[name]
                )

            if scope.kind is ScopeKind.CLASS and can_access_class_parameters:
                if name in scope.type_parameters:
                    return DefResult(
                        kind=DefKind.TYPE_PARAMETER, def_id=scope.type_parameters[name]
                    )

                can_access_class_parameters = False

            if include_functions and name in scope.function_defs:
                return DefResult(
                    kind=DefKind.FUNCTION, def_id=scope.function_defs[name]
                )

            if include_type_definitions and name in scope.type_definitions:
                def_id = scope.type_definitions[name]
                def_kind = self.asg_ctx.def_index.def_kinds[def_id]
                return DefResult(kind=def_kind, def_id=def_id)

            if include_classes and name in scope.class_defs:
                return DefResult(kind=DefKind.CLASS, def_id=scope.class_defs[name])

            if scope.kind is not ScopeKind.BLOCK and scope.kind is not ScopeKind.LAMBDA:
                can_access_definitions = False
                can_access_type_parameters = False

                if not first_iteration:
                    can_access_class_parameters = False

            if first_iteration:
                first_iteration = False

        return ResultKind.ERROR

    def resolve_attribute(
        self,
        value: ResolvedSymbol,
        name: str,
    ) -> ResolvedSymbol:
        return ResultKind.ERROR

    def resolve_symbols_for_type_expression(
        self, type_expression: ast.TypeExpressionNode
    ) -> None:
        match type_expression:
            case ast.NameNode():
                result = self.resolve_symbol(type_expression.value)
                self.asg_ctx.syms_resolved[type_expression.id] = result

            case ast.TypeCallNode():
                self.resolve_symbols_for_type_expression(type_expression.type)
                for argument in type_expression.args:
                    self.resolve_symbols_for_type_expression(argument)

            case ast.TypeAttributeNode():
                self.resolve_symbols_for_type_expression(type_expression.type)
                result = self.asg_ctx.syms_resolved.get(type_expression.type.id)
                if result is not None:
                    attribute = self.resolve_attribute(result, type_expression.attr)
                    if attribute is not ResultKind.ERROR:
                        self.asg_ctx.syms_resolved[type_expression.id] = attribute

            case ast.ListTypeNode():
                self.resolve_symbols_for_type_expression(type_expression.elt)

            case ast.StructTypeNode():
                for field in type_expression.fields:
                    self.resolve_symbols_for_type_expression(field.type)

            case ast.TupleTypeNode():
                for elt in type_expression.elts:
                    self.resolve_symbols_for_type_expression(elt)

    def resolve_symbols_for_block(self, statements: list[ast.StatementNode]) -> None:
        for statement in statements:
            self.resolve_symbols_for_statement(statement)

    def resolve_symbols_for_statement(
        self,
        statement: ast.StatementNode,
    ) -> None:
        match statement:
            case ast.TypeDefinitionNode():
                self.resolve_symbols_for_type_expression(statement.type)

            case ast.SumTypeNode():
                for variant in statement.variants:
                    if variant.type is not None:
                        self.resolve_symbols_for_type_expression(variant.type)

            case ast.FunctionDefNode():
                for parameter in statement.parameters:
                    self.resolve_symbols_for_type_expression(parameter.annotation)

                self.resolve_symbols_for_type_expression(statement.returns)

                if statement.body is not None:
                    self.enter_node(statement)
                    self.resolve_symbols_for_block(statement.body)
                    self.exit_node(statement)

            case ast.ClassDefNode():
                self.enter_node(statement)
                self.resolve_symbols_for_block(statement.body)
                self.exit_node(statement)

            case ast.UseNode():
                self.enter_node(statement)
                self.resolve_symbols_for_type_expression(statement.type)
                self.resolve_symbols_for_block(statement.body)
                self.exit_node(statement)

            case ast.UseAsNode():
                self.enter_node(statement)
                self.resolve_symbols_for_type_expression(statement.type)
                self.resolve_symbols_for_type_expression(statement.type_class)
                self.exit_node(statement)

            case ast.ForNode():
                self.enter_node(statement)
                self.resolve_symbols_for_expression(statement.target)
                self.resolve_symbols_for_expression(statement.iterator)
                self.resolve_symbols_for_block(statement.body)
                self.exit_node(statement)

            case ast.WhileNode():
                self.enter_node(statement)
                self.resolve_symbols_for_expression(statement.condition)
                self.resolve_symbols_for_block(statement.body)
                self.exit_node(statement)

            case ast.IfNode():
                self.enter_node(statement)
                self.resolve_symbols_for_expression(statement.condition)
                self.resolve_symbols_for_block(statement.body)
                self.exit_node(statement)

                if statement.else_statement is not None:
                    self.enter_node(statement.else_statement)
                    self.resolve_symbols_for_block(statement.else_statement.body)
                    self.exit_node(statement.else_statement)

            case ast.AssignNode() | ast.AugAssignNode():
                self.resolve_symbols_for_expression(statement.target)
                if statement.value is not None:
                    self.resolve_symbols_for_expression(statement.value)

            case ast.ReturnNode() if statement.value is not None:
                self.resolve_symbols_for_expression(statement.value)

            case ast.ExprNode():
                self.resolve_symbols_for_expression(statement.expr)

    def resolve_symbols_for_expression(self, expression: ast.ExpressionNode) -> None:
        match expression:
            case ast.LambdaNode():
                self.enter_node(expression)
                for parameter in expression.parameters:
                    if parameter.type is not None:
                        self.resolve_symbols_for_type_expression(parameter.type)

                if expression.returns is not None:
                    self.resolve_symbols_for_type_expression(expression.returns)

                self.resolve_symbols_for_block(expression.body)
                self.exit_node(expression)

            case ast.AnnotatedNode():
                self.resolve_symbols_for_expression(expression.value)
                self.resolve_symbols_for_type_expression(expression.type)

            case ast.BoolOpNode():
                for value in expression.values:
                    self.resolve_symbols_for_expression(value)

            case ast.BinaryOpNode():
                self.resolve_symbols_for_expression(expression.left)
                self.resolve_symbols_for_expression(expression.right)

            case ast.UnaryOpNode():
                self.resolve_symbols_for_expression(expression.operand)

            case ast.CompareNode():
                self.resolve_symbols_for_expression(expression.left)
                for comparator in expression.comparators:
                    self.resolve_symbols_for_expression(comparator.value)

            case ast.CallNode():
                self.resolve_symbols_for_expression(expression.callable)
                for argument in expression.args:
                    self.resolve_symbols_for_expression(argument)

            case ast.AttributeNode():
                self.resolve_symbols_for_expression(expression.value)
                result = self.asg_ctx.syms_resolved.get(expression.value.id)
                if result is not None:
                    attribute = self.resolve_attribute(result, expression.attr)
                    if attribute is not ResultKind.ERROR:
                        self.asg_ctx.syms_resolved[expression.id] = attribute

            case ast.SubscriptNode():
                self.resolve_symbols_for_expression(expression.value)

            case ast.StructNode():
                for field in expression.fields:
                    self.resolve_symbols_for_expression(field.value)

            case ast.TupleNode():
                for elt in expression.elts:
                    self.resolve_symbols_for_expression(elt)

            case ast.ListNode():
                for elt in expression.elts:
                    self.resolve_symbols_for_expression(elt)

            case ast.SliceNode():
                if expression.start_index is not None:
                    self.resolve_symbols_for_expression(expression.start_index)

                if expression.stop_index is not None:
                    self.resolve_symbols_for_expression(expression.stop_index)

                if expression.step_index is not None:
                    self.resolve_symbols_for_expression(expression.step_index)

            case ast.NameNode():
                result = self.resolve_symbol(expression.value)
                self.asg_ctx.syms_resolved[expression.id] = result

    def resolve_symbols_for_module(self, module: ast.ModuleNode) -> None:
        def_id = self.asg_ctx.def_id_for_node(module.id)
        scope = self.create_scope(module.id, ScopeKind.MODULE)
        self.initialize_symbols_for_block(def_id, scope, module.body)

        self.enter_node(module)
        self.resolve_symbols_for_block(module.body)
        self.exit_node(module)

import attr
import enum
import typing

from . import hir
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
    type_declarations: dict[str, hir.TypeDeclaration] = attr.ib(factory=dict)
    type_parameters: dict[str, hir.TypeParameter] = attr.ib(factory=dict)
    class_defs: dict[str, hir.ClassDef] = attr.ib(factory=dict)
    function_defs: dict[str, hir.FunctionDef] = attr.ib(factory=dict)
    local_declarations: dict[str, hir.LocalDeclaration] = attr.ib(factory=dict)


ResolvedSymbol = typing.Union[
    hir.TypeDeclaration,
    hir.TypeParameter,
    hir.ClassDef,
    hir.FunctionDef,
    hir.LocalDeclaration,
]

ResolvedAttribute = typing.Union[
    hir.TypeDeclaration,
    hir.TypeParameter,
    hir.ClassDef,
    hir.FunctionDef,
]


class SymbolResolver:
    def __init__(
        self,
        hir_ctx: hir.HirContext,
        module: ast.ModuleNode,
    ) -> None:
        self.hir_ctx = hir_ctx
        self.module = module
        self.scopes: dict[int, SymbolScope] = {}
        self.scope_stack: list[SymbolScope] = []

    def create_scope(self, node_id: int, kind: ScopeKind) -> SymbolScope:
        scope = SymbolScope(node_id=node_id, kind=kind)
        self.scopes[node_id] = scope
        return scope

    def initialize_symbols_for_block(
        self,
        owner_field: hir.HirField,
        scope: SymbolScope,
        body: list[ast.StatementNode]
    ) -> None:
        for statement in body:
            self.initialize_symbols_for_statement(owner_field, scope, statement)

    def initialize_symbols_for_statement(
        self,
        owner_field: hir.HirField,
        scope: SymbolScope,
        statement: ast.StatementNode,
    ) -> None:
        match statement:
            case ast.FunctionDefNode():
                function_def = hir.FunctionDef(name=statement.name)
                scope.function_defs[statement.name] = function_def
                scope = self.create_scope(statement.id, ScopeKind.FUNCTION)

                for parameter in statement.parameters:
                    self.initialize_type_parameters(
                        scope,
                        parameter.annotation,
                        primary_field=function_def,
                        secondary_field=owner_field,
                    )
                    scope.local_declarations[parameter.name] = hir.LocalDeclaration(
                        name=parameter.name,
                        node_id=parameter.id,
                    )

                self.initialize_type_parameters(
                    scope,
                    statement.returns,
                    primary_field=function_def,
                    secondary_field=owner_field,
                )
                if statement.body is not None:
                    self.initialize_symbols_for_block(function_def, scope, statement.body)

                self.hir_ctx.fields[statement.id] = function_def
                if isinstance(owner_field, (hir.ModuleDef, hir.ClassDef, hir.UseDef)):
                    owner_field.functions[function_def.name] = function_def

            case ast.ClassDefNode():
                class_def = hir.ClassDef(name=statement.name)
                scope.class_defs[statement.name] = class_def
                scope = self.create_scope(statement.id, ScopeKind.CLASS)
                for parameter in statement.parameters:
                    self.initialize_type_parameters(
                        scope,
                        parameter,
                        primary_field=class_def,
                        secondary_field=owner_field,
                    )

                self.initialize_symbols_for_block(class_def, scope, statement.body)

                self.hir_ctx.fields[statement.id] = class_def
                if isinstance(owner_field, hir.ModuleDef):
                    owner_field.classes[class_def.name] = class_def

            case ast.TypeDeclarationNode():
                match statement.type:
                    case ast.StructTypeNode():
                        declaration = hir.StructDef(name=statement.name, is_declaration=True)
                    case ast.TupleTypeNode():
                        declaration = hir.TupleDef(name=statement.name, is_declaration=True)
                    case _:
                        declaration = hir.AliasDef(name=statement.name)

                scope.type_declarations[statement.name] = declaration
                scope = self.create_scope(statement.id, ScopeKind.DECLARATION)
                self.initialize_type_parameters(
                    scope,
                    statement.type,
                    primary_field=declaration,
                    secondary_field=owner_field,
                )

                self.hir_ctx.fields[statement.id] = declaration
                if isinstance(owner_field, hir.ModuleDef):
                    owner_field.types[declaration.name] = declaration

            case ast.SumTypeNode():
                sum_def = hir.SumDef(name=statement.name)
                scope.type_declarations[statement.name] = sum_def
                scope = self.create_scope(statement.id, ScopeKind.DECLARATION)

                for field in statement.fields:
                    if field.data_type is not None:
                        # XXX: If the type parameter syntax going to be
                        # problematic for unions?
                        self.initialize_type_parameters(
                            scope,
                            field.data_type,
                            primary_field=sum_def,
                            secondary_field=owner_field,
                        )

                self.hir_ctx.fields[statement.id] = sum_def
                if isinstance(owner_field, hir.ModuleDef):
                    owner_field.types[sum_def.name] = sum_def

            case ast.UseNode():
                scope = self.create_scope(statement.id, ScopeKind.USE)
                use_def = hir.UseDef()
                self.hir_ctx.fields[statement.id] = use_def

                self.initialize_type_parameters(
                    scope,
                    statement.type,
                    primary_field=use_def,
                    secondary_field=owner_field,
                )
                self.initialize_symbols_for_block(use_def, scope, statement.body)

            case ast.UseForNode():
                scope = self.create_scope(statement.id, ScopeKind.USE)
                use_def = hir.UseDef()
                self.hir_ctx.fields[statement.id] = use_def

                self.initialize_type_parameters(
                    scope,
                    statement.type,
                    primary_field=use_def,
                    secondary_field=owner_field,
                )
                self.initialize_type_parameters(
                    scope,
                    statement.type_class,
                    primary_field=use_def,
                    secondary_field=owner_field,
                )
                self.initialize_symbols_for_block(use_def, scope, statement.body)

            case ast.DeclarationNode():
                # TODO: What about shadowing?
                scope.local_declarations[statement.target] = hir.LocalDeclaration(
                    name=statement.target,
                    node_id=statement.id,
                )
                if statement.value is not None:
                    self.initialize_lambdas(owner_field, statement.value)

            case ast.ForNode():
                self.create_scope(statement.id, ScopeKind.BLOCK)
                self.initialize_symbols_for_block(owner_field, scope, statement.body)
                self.initialize_lambdas(owner_field, statement.iterator)

            case ast.WhileNode():
                self.create_scope(statement.id, ScopeKind.BLOCK)
                self.initialize_symbols_for_block(owner_field, scope, statement.body)
                self.initialize_lambdas(owner_field, statement.condition)

            case ast.IfNode():
                self.create_scope(statement.id, ScopeKind.BLOCK)
                self.initialize_symbols_for_block(owner_field, scope, statement.body)
                self.initialize_lambdas(owner_field, statement.condition)

                if statement.else_statement is not None:
                    self.create_scope(statement.else_statement.id, ScopeKind.BLOCK)
                    self.initialize_symbols_for_block(owner_field, scope, statement.else_statement.body)

            case ast.ReturnNode():
                if statement.value is not None:
                    self.initialize_lambdas(owner_field, statement.value)

            case ast.ExprNode():
                self.initialize_lambdas(owner_field, statement.expr)

    def initialize_lambdas(
        self,
        owner_field: hir.HirField,
        expression: ast.ExpressionNode,
    ) -> None:
        for subexpression in ast.walk_expressions(expression):
            if isinstance(subexpression, (ast.ExpressionLambdaNode, ast.BlockLambdaNode)):
                scope = self.create_scope(subexpression.id, ScopeKind.LAMBDA)
                for parameter in subexpression.parameters:
                    scope.local_declarations[parameter.name] = hir.LocalDeclaration(
                        name=parameter.name,
                        node_id=parameter.id,
                    )

                function_def = hir.FunctionDef(name='lambda')
                self.hir_ctx.fields[subexpression.id] = function_def

                if isinstance(subexpression, ast.BlockLambdaNode):
                    self.initialize_symbols_for_block(
                        function_def,
                        scope,
                        subexpression.body,
                    )
                else:
                    self.initialize_lambdas(function_def, subexpression.body)

    def initialize_type_parameters(
        self,
        scope: SymbolScope,
        type_expression: ast.TypeExpressionNode,
        *,
        primary_field: hir.HirField,
        secondary_field: hir.HirField,
    ) -> None:
        primary_generics = self.hir_ctx.generics.get(primary_field.id)

        if isinstance(secondary_field, hir.UseDef):
            secondary_generics = self.hir_ctx.generics.get(secondary_field.id)
        else:
            secondary_generics = None

        for subexpression in ast.walk_type_expressions(type_expression):
            if isinstance(subexpression, ast.TypeParameterNode):
                if primary_generics is None:
                    primary_generics = hir.Generics(owner=secondary_generics)
                    self.hir_ctx.generics[primary_field.id] = primary_generics

                if not primary_generics.has_parameter_named(subexpression.name):
                    scope.type_parameters[subexpression.name] = hir.TypeParameter(
                        name=subexpression.name,
                    )

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
        include_local_declarations: bool = True,
        include_functions: bool = True,
        include_type_parameters: bool = True,
    ) -> typing.Optional[ResolvedSymbol]:
        first_iteration = True
        can_access_type_parameters = include_type_parameters
        can_access_class_parameters = True
        can_access_declarations = include_local_declarations

        for scope in reversed(self.scope_stack):
            if can_access_declarations:
                if name in scope.local_declarations:
                    return scope.local_declarations[name]

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

            if include_functions and name in scope.function_defs:
                return scope.function_defs[name]

            if name in scope.type_declarations:
                return scope.type_declarations[name]

            if name in scope.class_defs:
                return scope.class_defs[name]

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

    def resolve_attribute(
        self,
        field: hir.HirField,
        name: str,
    ) -> typing.Optional[ResolvedAttribute]:
        match field:
            case hir.ModuleDef():
                return (
                    field.classes.get(name)
                    or field.functions.get(name)
                    or field.classes.get(name)
                )

            case hir.ClassDef():
                return field.functions.get(name)

import attr
import enum

from . import asg
from ..syntax.typethon import ast
from ..syntax import tokens


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
    type_declarations: dict[str, asg.TypeDeclaration] = attr.ib(factory=dict)
    type_parameters: dict[str, asg.TypeParameter] = attr.ib(factory=dict)
    class_defs: dict[str, asg.ClassDef] = attr.ib(factory=dict)
    function_defs: dict[str, asg.FunctionDef] = attr.ib(factory=dict)
    local_declarations: dict[str, asg.LocalDeclaration] = attr.ib(factory=dict)


type ResolvedSymbol = (
    asg.TypeDeclaration | asg.TypeParameter | asg.ClassDef | asg.FunctionDef | asg.LocalDeclaration
)

type ResolvedAttribute = asg.TypeDeclaration | asg.ClassDef | asg.FunctionDef


class SymbolResolver:
    # Prior to resolving symbols, the resolver must initialize all fields and type parameters.
    # The resolver is subsequently used by AsgLowering for path and name resolution.
    # AsgLowering is responsible for calling the add_local_declaration because it is the only
    # case where a name cannot be used in its scope before it has been defined.

    def __init__(
        self,
        asg_ctx: asg.AsgContext,
        module: ast.ModuleNode,
    ) -> None:
        self.asg_ctx = asg_ctx
        self.module = module
        self.scopes: dict[int, SymbolScope] = {}
        self.scope_stack: list[SymbolScope] = []

    def create_scope(self, node_id: int, kind: ScopeKind) -> SymbolScope:
        scope = SymbolScope(node_id=node_id, kind=kind)
        self.scopes[node_id] = scope
        return scope

    def initialize_symbols_for_block(
        self, owner_field: asg.AsgField, scope: SymbolScope, body: list[ast.StatementNode]
    ) -> None:
        for statement in body:
            self.initialize_symbols_for_statement(owner_field, scope, statement)

    def add_local_declaration(
        self,
        name: str,
        statement: ast.AssignNode,
    ) -> asg.LocalDeclaration:
        scope = self.scope_stack[-1]
        declaration = asg.LocalDeclaration(
            name=name,
            node_id=statement.id,
        )
        scope.local_declarations[name] = declaration
        return declaration

    def initialize_symbols_for_statement(
        self,
        owner_field: asg.AsgField,
        scope: SymbolScope,
        statement: ast.StatementNode,
    ) -> None:
        match statement:
            case ast.FunctionDefNode():
                function_def = asg.FunctionDef(name=statement.name)
                scope.function_defs[statement.name] = function_def
                scope = self.create_scope(statement.id, ScopeKind.FUNCTION)

                for parameter in statement.parameters:
                    self.initialize_type_parameters(
                        scope,
                        parameter.annotation,
                        primary_field=function_def,
                        secondary_field=owner_field,
                    )
                    declaration = asg.LocalDeclaration(
                        name=parameter.name,
                        node_id=parameter.id,
                    )
                    scope.local_declarations[parameter.name] = declaration
                    function_def.parameter_declarations[parameter.name] = declaration

                self.initialize_type_parameters(
                    scope,
                    statement.returns,
                    primary_field=function_def,
                    secondary_field=owner_field,
                )
                if statement.body is not None:
                    self.initialize_symbols_for_block(function_def, scope, statement.body)

                self.asg_ctx.fields[statement.id] = function_def
                if isinstance(owner_field, (asg.ModuleDef, asg.ClassDef, asg.UseDef)):
                    owner_field.functions[function_def.name] = function_def

            case ast.ClassDefNode():
                class_def = asg.ClassDef(name=statement.name)
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

                self.asg_ctx.fields[statement.id] = class_def
                if isinstance(owner_field, asg.ModuleDef):
                    owner_field.classes[class_def.name] = class_def

            case ast.TypeDeclarationNode():
                match statement.type:
                    case ast.StructTypeNode():
                        declaration = asg.StructDef(name=statement.name, is_declaration=True)
                    case ast.TupleTypeNode():
                        declaration = asg.TupleDef(name=statement.name, is_declaration=True)
                    case _:
                        assert False, "Not Implemented"
                        declaration = asg.AliasDef(name=statement.name)

                scope.type_declarations[statement.name] = declaration
                scope = self.create_scope(statement.id, ScopeKind.DECLARATION)
                self.initialize_type_parameters(
                    scope,
                    statement.type,
                    primary_field=declaration,
                    secondary_field=owner_field,
                )

                self.asg_ctx.fields[statement.id] = declaration
                if isinstance(owner_field, asg.ModuleDef):
                    owner_field.types[declaration.name] = declaration

            case ast.SumTypeNode():
                sum_def = asg.SumDef(name=statement.name)
                scope.type_declarations[statement.name] = sum_def
                scope = self.create_scope(statement.id, ScopeKind.DECLARATION)

                for field in statement.fields:
                    if field.type is not None:
                        # XXX: Is the type parameter syntax going to be
                        # problematic for unions?
                        self.initialize_type_parameters(
                            scope,
                            field.type,
                            primary_field=sum_def,
                            secondary_field=owner_field,
                        )

                self.asg_ctx.fields[statement.id] = sum_def
                if isinstance(owner_field, asg.ModuleDef):
                    owner_field.types[sum_def.name] = sum_def

            case ast.UseNode():
                scope = self.create_scope(statement.id, ScopeKind.USE)
                use_def = asg.UseDef()
                self.asg_ctx.fields[statement.id] = use_def

                self.initialize_type_parameters(
                    scope,
                    statement.type,
                    primary_field=use_def,
                    secondary_field=owner_field,
                )
                self.initialize_symbols_for_block(use_def, scope, statement.body)

            case ast.UseForNode():
                scope = self.create_scope(statement.id, ScopeKind.USE)
                use_def = asg.UseDef()
                self.asg_ctx.fields[statement.id] = use_def

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
                    self.initialize_symbols_for_block(
                        owner_field, scope, statement.else_statement.body
                    )

            case ast.AssignNode() | ast.AugAssignNode():
                self.initialize_lambdas(owner_field, statement.target)
                if statement.value is not None:
                    self.initialize_lambdas(owner_field, statement.value)

            case ast.ReturnNode():
                if statement.value is not None:
                    self.initialize_lambdas(owner_field, statement.value)

            case ast.ExprNode():
                self.initialize_lambdas(owner_field, statement.expr)

    def initialize_lambdas(
        self,
        owner_field: asg.AsgField,
        expression: ast.ExpressionNode,
    ) -> None:
        for subexpression in ast.walk_expressions(expression):
            if isinstance(subexpression, (ast.ExpressionLambdaNode, ast.BlockLambdaNode)):
                scope = self.create_scope(subexpression.id, ScopeKind.LAMBDA)
                for parameter in subexpression.parameters:
                    scope.local_declarations[parameter.name] = asg.LocalDeclaration(
                        name=parameter.name,
                        node_id=parameter.id,
                    )

                function_def = asg.FunctionDef(name="lambda")
                self.asg_ctx.fields[subexpression.id] = function_def

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
        primary_field: asg.AsgField,
        secondary_field: asg.AsgField,
    ) -> None:
        primary_generics = self.asg_ctx.generics.get(primary_field.id)

        # I have made the questionable syntactic decision of allowing type paramters
        # to be referred to without being explicitly defined first.
        # If a type paramter is referred to, it is subsequently defined.
        # Rather than def f<T>(x: T), it is simply def f(x: 't).
        # This complicates matters for the compiler because there are instances
        # where we might want to refer to a type paramter defined in the context
        # of the outside field, and there are other instances where a type parameter
        # of the same name should define a new one in the contex of the current field.
        # Here are two examples of both cases respectively:
        # class A('t):
        #   def f(x: 't) -> 't
        # ...
        # def f(x: 't) -> 't:
        #   def g(y: 't) -> 't
        # In the second example, both `f` and `g` have their own type parameter named `t`.
        # The composition of the Generics instance is responsible for this behavior.
        # Anytime the compiler encounters a type paramter `t`, it looks through the structure
        # recursively for any parameter of the same name. If that is not found, it simply
        # creates a new one, and inserts it into the Generic's parameters. As a result,
        # the compiler only ascribes a Generics.owner value in contexts where the outside
        # field's type parameters can be utilized.
        if isinstance(secondary_field, (asg.UseDef, asg.ClassDef)):
            secondary_generics = self.asg_ctx.generics.get(secondary_field.id)
        else:
            secondary_generics = None

        for subexpression in ast.walk_type_expressions(type_expression):
            if isinstance(subexpression, ast.TypeParameterNode):
                if primary_generics is None:
                    primary_generics = asg.Generics(owner=secondary_generics)
                    self.asg_ctx.generics[primary_field.id] = primary_generics

                if not primary_generics.has_parameter_named(subexpression.name):
                    type_parameter = asg.TypeParameter(
                        name=subexpression.name,
                    )
                    scope.type_parameters[subexpression.name] = type_parameter
                    primary_generics.parameters[subexpression.name] = type_parameter

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
        include_local_declarations: bool = True,
        include_functions: bool = True,
        include_type_parameters: bool = True,
        include_type_declarations: bool = True,
        include_classes: bool = True,
    ) -> ResolvedSymbol | None:
        first_iteration = True
        can_access_type_parameters = include_type_parameters
        can_access_class_parameters = True
        can_access_declarations = include_local_declarations

        for scope in reversed(self.scope_stack):
            if can_access_declarations and name in scope.local_declarations:
                    return scope.local_declarations[name]

            if can_access_type_parameters and name in scope.type_parameters:
                    return scope.type_parameters[name]

            if scope.kind is ScopeKind.CLASS and can_access_class_parameters:
                if name in scope.type_parameters:
                    return scope.type_parameters[name]

                can_access_class_parameters = False

            if include_functions and name in scope.function_defs:
                return scope.function_defs[name]

            if include_type_declarations and name in scope.type_declarations:
                return scope.type_declarations[name]

            if include_classes and name in scope.class_defs:
                return scope.class_defs[name]

            if scope.kind is not ScopeKind.BLOCK and scope.kind is not ScopeKind.LAMBDA:
                can_access_declarations = False
                can_access_type_parameters = False

                if not first_iteration:
                    can_access_class_parameters = False

            if first_iteration:
                first_iteration = False

    def resolve_attribute(
        self,
        field: asg.AsgPathResult,
        name: str,
    ) -> ResolvedAttribute | None:
        match field:
            case asg.ModuleDef():
                return (
                    field.classes.get(name) or field.functions.get(name) or field.classes.get(name)
                )

            case asg.ClassDef():
                return field.functions.get(name)

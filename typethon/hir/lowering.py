from . import hir
from . import code
from .resolution import SymbolResolver, ScopeKind
from ..syntax.typethon import ast


class HirLowering:
    resolver: SymbolResolver
    module: ast.ModuleNode
    resolver: SymbolResolver

    def __init__(
        self,
        hir_ctx: hir.HirContext,
        module: ast.ModuleNode,
    ) -> None:
        self.hir_ctx = hir_ctx
        self.module = module
        self.resolver = SymbolResolver(hir_ctx, module)

    def report_error(
        self,
        node: ast.Node,
        message: str,
        *format: str,
    ) -> None:
        self.hir_ctx.diagnostics.report_error((node.start, node.end), message, *format)

    def create_path_resursive(
        self,
        path: hir.Path,
        type_expression: ast.TypeAttributeNode | ast.TypeCallNode | ast.NameNode,
    ) -> hir.HirPathResult:
        match type_expression:
            case ast.TypeAttributeNode():
                match type_expression.type:
                    case ast.TypeAttributeNode() | ast.TypeCallNode() | ast.NameNode():
                        field = self.create_path_resursive(path, type_expression.type)
                    case _:
                        field = self.lower_type_expression(type_expression.type)
                        # If it could've been a path, it must've been matched by the previous case.
                        # If we are here, the node is one of the following:
                        # | SelfTypeNode            Self.foo
                        # | TypeParameterNode       't.foo
                        # | ListTypeNode            [...].foo
                        # | DataTypeNode            { x: y }.foo / (x,).foo
                        # This will almost always create an error in the next step,
                        # but we will leave it up to the next segment to carry the error.
                        # Additionally, if we are here, the path cannot have any segments yet
                        # because it is syntactically impossible (i.e foo.(x,) is a syntax error)

                        assert not isinstance(field, hir.Path)
                        segment = hir.PathSegment(name="type-expr", result=field)
                        path.segments.append(segment)

                result = self.resolver.resolve_attribute(field, type_expression.attr)
                if result is None:
                    # Unresolved attribute
                    result = hir.HirError(node=type_expression)

                segment = hir.PathSegment(name=type_expression.attr, result=result)
                path.segments.append(segment)
                return result

            case ast.TypeCallNode():
                match type_expression.type:
                    case ast.TypeAttributeNode() | ast.TypeCallNode() | ast.NameNode():
                        field = self.create_path_resursive(path, type_expression.type)
                    case _:
                        field = self.lower_type_expression(type_expression.type)
                        assert not isinstance(field, hir.Path)

                        segment = hir.PathSegment(name="type-expr", result=field)
                        path.segments.append(segment)

                segment = path.segments[-1]
                for argument in type_expression.args:
                    type = self.lower_type_expression(argument)
                    segment.arguments.append(type)

                return field

            case ast.NameNode():
                result = self.resolver.resolve_symbol(
                    type_expression.value,
                    include_local_declarations=False,
                    include_functions=False,
                    include_type_parameters=False,
                )
                if result is None:
                    # Unresolved symbol
                    result = hir.HirError(node=type_expression)

                assert not isinstance(
                    result, (hir.FunctionDef, hir.LocalDeclaration, hir.TypeParameter)
                )
                segment = hir.PathSegment(name=type_expression.value, result=result)
                path.segments.append(segment)
                return result

    def lower_type_expression(
        self,
        type_expression: ast.TypeExpressionNode,
    ) -> hir.HirType:
        match type_expression:
            case ast.TypeParameterNode():
                symbol = self.resolver.resolve_symbol(
                    type_expression.name,
                    include_local_declarations=False,
                    include_functions=False,
                )
                # XXX: Will this ever fail?
                # We should probably get it from generics instead
                assert isinstance(symbol, hir.TypeParameter)
                return symbol

            case ast.TypeCallNode() | ast.TypeAttributeNode() | ast.NameNode():
                path = hir.Path()
                self.create_path_resursive(path, type_expression)
                return path

            case ast.ListTypeNode():
                elt = self.lower_type_expression(type_expression.elt)
                return hir.ListType(elt=elt)

            case ast.SelfTypeNode():
                assert False, "TODO!"

            case ast.StructTypeNode():
                struct_def = hir.StructDef(name="inline-struct", is_declaration=False)
                for field in type_expression.fields:
                    struct_def.fields[field.name] = self.lower_type_expression(field.type)

                return struct_def

            case ast.TupleTypeNode():
                tuple_def = hir.TupleDef(name="inline-tuple", is_declaration=False)
                for elt in type_expression.elts:
                    tuple_def.elts.append(self.lower_type_expression(elt))

                return tuple_def

    def lower_block(
        self,
        block: list[ast.StatementNode],
        hir_body: code.HirBody,
    ) -> None:
        for statement in block:
            self.lower_statement(statement, hir_body)

    def lower_statement(
        self,
        statement: ast.StatementNode,
        hir_body: code.HirBody,
    ) -> None:
        match statement:
            case ast.FunctionDefNode():
                function_def = self.hir_ctx.fields[statement.id]
                assert isinstance(function_def, hir.FunctionDef)
                self.resolver.enter_node(statement)

                for parameter in statement.parameters:
                    type = self.lower_type_expression(parameter.annotation)
                    function_def.parameters[parameter.name] = type

                function_def.returns = self.lower_type_expression(statement.returns)

                if statement.body is not None:
                    function_def.body = code.HirBody()
                    self.lower_block(statement.body, function_def.body)

                self.resolver.exit_node(statement)

            case ast.ClassDefNode():
                class_def = self.hir_ctx.fields[statement.id]
                assert isinstance(class_def, hir.ClassDef)
                self.resolver.enter_node(statement)

                for substatement in statement.body:
                    if isinstance(substatement, ast.FunctionDefNode):
                        self.lower_statement(substatement, hir_body)
                        function_def = self.hir_ctx.fields[statement.id]
                        assert isinstance(function_def, hir.FunctionDef)

                        class_def.functions[substatement.name] = function_def
                    else:
                        self.report_error(substatement, "Only functions are allowed in class body")

                self.resolver.exit_node(statement)

            case ast.UseNode() | ast.UseForNode():
                use_def = self.hir_ctx.fields[statement.id]
                assert isinstance(use_def, hir.UseDef)

                self.resolver.enter_node(statement)
                use_def.type = self.lower_type_expression(statement.type)

                if isinstance(statement, ast.UseForNode):
                    use_def.type_class = self.lower_type_expression(statement.type_class)

                for substatement in statement.body:
                    if isinstance(substatement, ast.FunctionDefNode):
                        self.lower_statement(substatement, hir_body)
                        function_def = self.hir_ctx.fields[statement.id]
                        assert isinstance(function_def, hir.FunctionDef)

                        use_def.functions[substatement.name] = function_def
                    else:
                        self.report_error(substatement, "Only functions are allowed in class body")

                self.resolver.exit_node(statement)

            case ast.DeclarationNode():
                type = None
                if statement.type is not None:
                    type = self.lower_type_expression(statement.type)

                value = None
                if statement.value is not None:
                    value = self.lower_expression(statement.value)

                declaration = self.resolver.add_local_declaration(statement)
                hir_code = code.Declaration(
                    node_id=statement.id,
                    local_declaration=declaration,
                    type=type,
                    value=value,
                )
                hir_body.statements.append(hir_code)

            case ast.ForNode():
                hir_code = code.For(
                    node_id=statement.id,
                    target=self.lower_expression(statement.target),
                    iterator=self.lower_expression(statement.iterator),
                    body=code.HirBody(),
                )
                self.resolver.enter_node(statement)
                self.lower_block(statement.body, hir_code.body)
                self.resolver.exit_node(statement)
                hir_body.statements.append(hir_code)

            case ast.WhileNode():
                hir_code = code.While(
                    node_id=statement.id,
                    condition=self.lower_expression(statement.condition),
                    body=code.HirBody(),
                )
                self.resolver.enter_node(statement)
                self.lower_block(statement.body, hir_code.body)
                self.resolver.exit_node(statement)
                hir_body.statements.append(hir_code)

            case ast.IfNode():
                hir_code = code.If(
                    node_id=statement.id,
                    condition=self.lower_expression(statement.condition),
                    body=code.HirBody(),
                    else_body=code.HirBody(),
                )

                self.resolver.enter_node(statement)
                self.lower_statement(statement, hir_code.body)
                self.resolver.exit_node(statement)

                if statement.else_statement is not None:
                    self.resolver.enter_node(statement.else_statement)
                    self.lower_block(statement.else_statement.body, hir_code.else_body)
                    self.resolver.exit_node(statement.else_statement)

                hir_body.statements.append(hir_code)

            case ast.ReturnNode():
                value = (
                    self.lower_expression(statement.value) if statement.value is not None else None
                )
                hir_code = code.Return(
                    node_id=statement.id,
                    value=value,
                )
                hir_body.statements.append(hir_code)

            case ast.ContinueNode():
                hir_code = code.Continue(node_id=statement.id)
                hir_body.statements.append(hir_code)

            case ast.BreakNode():
                hir_code = code.Break(node_id=statement.id)
                hir_body.statements.append(hir_code)

            case ast.ExprNode():
                hir_code = code.Expr(
                    node_id=statement.id,
                    expr=self.lower_expression(statement.expr),
                )
                hir_body.statements.append(hir_code)

    def lower_expression(self, expression: ast.ExpressionNode) -> code.Expression:
        """
        AssignNode
        | AugAssignNode
        | ExpressionLambdaNode
        | BlockLambdaNode
        | BoolOpNode
        | BinaryOpNode
        | UnaryOpNode
        | CompareNode
        | CallNode
        | ConstantNode
        | AttributeNode
        | SubscriptNode
        | NameNode
        | ListNode
        | TupleNode
        | SliceNode
        """
        # XXX: It will be impossible to add arguments to a path outside of a type context
        # due to ambiguity. We could end up with two different syntaxes for passing arguments
        # like in Rust (T<>, T::<>) albeit for entirely different reasons. AS far as I know,
        # Rust merely does it for easier parsing, but in out case, it is literally impossible
        # to tell the difference between a function call and passing type parameters because
        # they use the same syntax. Even just checking whether something is a type while
        # constructing the HIR wouldn't suffice because type instantiation is already T().
        # So to recap, T(...) would have three meanings: calling a type constructor,
        # initializing a new instance of a type, calling a function.
        # So, going forward we have two options:
        #   1) Add a special syntax for passing type parameters, but only in the context of code
        #   blocks. (Not happening)
        #       def f(x: Generic(Parameter))
        #       Generic:(Parameter)()
        #   2) Just change the syntax for passing type parameters.
        #       def f(x: Generic[Parameter])
        #        Generic[Parameter]()
        #   3) Change the type initialization syntax and disambiguate between function calls
        #   and the syntax for passing parameters by checking is its a type.
        #       def f(x: Generic(Parameter))
        #       Generic(Parameter)
        #       f(Generic(Parameter) {})
        # The third is arguably the most correct, type constructors are just functions over types,
        # but the instantiation syntax is completely unexpected for Python. If I can think of
        # a better instantiation syntax, I will certainly choose the third option.
        match expression:
            case ast.NameNode() | ast.AttributeNode():
                ...

    def lower_module(self) -> None:
        module = hir.ModuleDef()
        scope = self.resolver.create_scope(self.module.id, ScopeKind.MODULE)
        self.resolver.initialize_symbols_for_block(module, scope, self.module.body)

        module_body = code.HirBody()
        self.resolver.enter_node(self.module)
        self.lower_block(self.module.body, module_body)
        self.resolver.exit_node(self.module)

        print(module_body.statements)

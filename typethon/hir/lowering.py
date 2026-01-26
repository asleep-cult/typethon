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

    def create_type_path_recursive(
        self,
        path: hir.Path,
        type_expression: ast.TypeAttributeNode | ast.TypeCallNode | ast.NameNode,
    ) -> hir.HirPathResult:
        match type_expression:
            case ast.TypeAttributeNode():
                match type_expression.type:
                    case ast.TypeAttributeNode() | ast.TypeCallNode() | ast.NameNode():
                        field = self.create_type_path_recursive(path, type_expression.type)
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
                        field = self.create_type_path_recursive(path, type_expression.type)
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
                self.create_type_path_recursive(path, type_expression)
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
                        function_def = self.hir_ctx.fields[substatement.id]
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
                self.lower_block(statement.body, hir_code.body)
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

    def create_path_recursive(
        self,
        path: hir.Path,
        expression: ast.AttributeNode | ast.CallNode | ast.NameNode,
    ) -> hir.HirPathResult | code.Expression:
        # This is pretty confusing, but this function transforms attribute/call/name exprs
        # into a path as much as possible, then begins creating hir.Call/hir.Attribute
        # nodes if the node is not part of the path. This means that in some cases,
        # the function might return hir code that already contains the path, and in other
        # cases the return value is a junk value used to recursively resolve the tree.
        # In that case, the only relevant part is the provided path which will
        # have been mutated to contain the proper segments.
        # Also, when we encounter a call node, we must be able to tell whether we are still
        # in a path. If so, the arguments themselves must be a path too because paths are
        # the only way to refer to a type from the context of an expression. That is to say,
        # there is no expression that can resolve to a type except a name, which is not the
        # case for type expressions where obviously everything is a type. The ambiguity between
        # paths and calls would be unresolvable if the call syntax were used for type
        # instantiation, so there is currently no syntax for it.
        match expression:
            case ast.AttributeNode():
                match expression.value:
                    case ast.AttributeNode() | ast.CallNode() | ast.NameNode():
                        field = self.create_path_recursive(path, expression.value)
                    case _:
                        field = self.lower_expression(expression.value)
                        assert not path.segments
                        return code.Attribute(node_id=expression.id, attr=expression.attr, value=field)

                assert not isinstance(field, hir.Path)
                if isinstance(field, code.HirCode):
                    return code.Attribute(node_id=expression.id, attr=expression.attr, value=field)

                result = self.resolver.resolve_attribute(field, expression.attr)
                if result is None:
                    result = hir.HirError(node=expression)

                segment = hir.PathSegment(name=expression.attr, result=result)
                path.segments.append(segment)
                if isinstance(result, hir.FunctionDef):
                    return code.Path(node_id=expression.id, path=path)

                return result

            case ast.CallNode():
                match expression.callee:
                    case ast.AttributeNode() | ast.CallNode() | ast.NameNode():
                        field = self.create_path_recursive(path, expression.callee)
                    case _:
                        field = self.lower_expression(expression.callee)

                assert not isinstance(field, hir.Path)
                if not isinstance(field, code.HirCode):
                    segment = path.segments[-1]

                    for argument in expression.args:
                        argument = self.lower_expression(argument)
                        if not isinstance(argument, code.Path):
                            assert False, 'Calling type requires path argument'

                        segment.arguments.append(argument.path)

                    return field

                arguments: list[code.Expression] = []
                for argument in expression.args:
                    arguments.append(self.lower_expression(argument))

                return code.Call(node_id=expression.id, callee=field, args=arguments)

            case ast.NameNode():
                result = self.resolver.resolve_symbol(expression.value)
                if result is None:
                    # Unresolved symbol
                    result = hir.HirError(node=expression)

                segment = hir.PathSegment(name=expression.value, result=result)
                path.segments.append(segment)
                if isinstance(result, (hir.FunctionDef, hir.LocalDeclaration)):
                    return code.Path(node_id=expression.id, path=path)

                return result

    def lower_expression(self, expression: ast.ExpressionNode) -> code.Expression:
        match expression:
            case ast.NameNode() | ast.AttributeNode() | ast.CallNode():
                path = hir.Path()
                result = self.create_path_recursive(path, expression)
                if isinstance(result, code.HirCode):
                    return result

                return code.Path(node_id=expression.id, path=path)

            case ast.AssignNode():
                target = self.lower_expression(expression.target)
                value = self.lower_expression(expression.value)
                return code.Assignment(node_id=expression.id, target=target, value=value)

            case ast.ExpressionLambdaNode() | ast.BlockLambdaNode():
                function_def = self.hir_ctx.fields[expression.id]
                assert isinstance(function_def, hir.FunctionDef)
                self.resolver.enter_node(expression)

                for parameter in expression.parameters:
                    function_def.parameters[parameter.name] = hir.INFERRED

                function_def.returns = hir.INFERRED

                function_def.body = code.HirBody()
                if isinstance(expression, ast.BlockLambdaNode):
                    self.lower_block(expression.body, function_def.body)
                else:
                    hir_code = code.Return(
                        node_id=expression.body.id,
                        value=self.lower_expression(expression.body),
                    )
                    function_def.body.statements.append(hir_code)

                self.resolver.exit_node(expression)

            case ast.BoolOpNode():
                values: list[code.Expression] = []
                for value in expression.values:
                    values.append(self.lower_expression(value))

                return code.BoolOp(
                    node_id=expression.id,
                    op=expression.op,
                    values=values,
                )

            case ast.BinaryOpNode():
                left = self.lower_expression(expression.left)
                right = self.lower_expression(expression.right)
                return code.BinaryOp(node_id=expression.id, left=left, op=expression.op, right=right)

            case ast.UnaryOpNode():
                return code.UnaryOp(
                    node_id=expression.id,
                    op=expression.op,
                    operand=self.lower_expression(expression.operand),
                )

            case ast.CompareNode():
                comparators: list[code.Comparator] = []
                for comparator in expression.comparators:
                    comparator = code.Comparator(
                        node_id=comparator.id,
                        op=comparator.op,
                        value=self.lower_expression(comparator.value),
                    )
                    comparators.append(comparator)

                return code.Compare(
                    node_id=expression.id,
                    left=self.lower_expression(expression.left),
                    comparators=comparators,
                )

            case ast.SubscriptNode():
                slices: list[code.Expression] = []
                for slice in expression.slices:
                    slices.append(self.lower_expression(slice))

                return code.Subscript(
                    node_id=expression.id,
                    value=self.lower_expression(expression.value),
                    slices=slices,
                )

            case ast.ListNode():
                elts: list[code.Expression] = []
                for elt in expression.elts:
                    elts.append(self.lower_expression(elt))

                return code.List(node_id=expression.id, elts=elts)

            case ast.TupleNode():
                elts: list[code.Expression] = []
                for elt in expression.elts:
                    elts.append(self.lower_expression(elt))

                return code.Tuple(node_id=expression.id, elts=elts)

            case ast.SliceNode():
                start = None
                if expression.start_index is not None:
                    start = self.lower_expression(expression.start_index)

                stop = None
                if expression.stop_index is not None:
                    stop = self.lower_expression(expression.stop_index)

                step = None
                if expression.step_index is not None:
                    step = self.lower_expression(expression.step_index)

                return code.Slice(node_id=expression.id, start=start, stop=stop, step=step)

            case ast.IntegerNode():
                return code.Integer(node_id=expression.id, value=expression.value)

            case ast.FloatNode():
                return code.Float(node_id=expression.id, value=expression.value)

            case ast.ComplexNode():
                return code.Complex(node_id=expression.id, value=expression.value)

            case ast.StringNode():
                return code.String(node_id=expression.id, value=expression.value)

            case ast.ConstantNode():
                return code.Constant(node_id=expression.id, kind=expression.kind)

    def lower_module(self) -> hir.ModuleDef:
        module = hir.ModuleDef()
        scope = self.resolver.create_scope(self.module.id, ScopeKind.MODULE)
        self.resolver.initialize_symbols_for_block(module, scope, self.module.body)

        module.body = code.HirBody()
        self.resolver.enter_node(self.module)
        self.lower_block(self.module.body, module.body)
        self.resolver.exit_node(self.module)

        return module

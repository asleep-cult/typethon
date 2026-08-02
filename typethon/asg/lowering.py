from . import asg
from .resolution import SymbolResolver, ScopeKind
from ..syntax.typethon import ast


class AsgLowering:
    resolver: SymbolResolver
    module: ast.ModuleNode

    def __init__(
        self,
        asg_ctx: asg.AsgContext,
        module: ast.ModuleNode,
    ) -> None:
        self.asg_ctx = asg_ctx
        self.module = module
        self.resolver = SymbolResolver(asg_ctx, module)

    def report_error(
        self,
        node: ast.Node,
        message: str,
        *format: str,
    ) -> None:
        self.asg_ctx.diagnostics.report_error((node.start, node.end), message, *format)

    def create_type_path_recursive(
        self,
        path: asg.Path,
        type_expression: ast.TypeAttributeNode | ast.TypeCallNode | ast.NameNode,
    ) -> asg.AsgPathResult:
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

                        assert not isinstance(field, asg.Path)
                        segment = asg.PathSegment(name="type-expr", result=field)
                        path.segments.append(segment)

                result = self.resolver.resolve_attribute(field, type_expression.attr)
                if result is None:
                    # Unresolved attribute
                    result = asg.AsgError(node=type_expression)

                segment = asg.PathSegment(name=type_expression.attr, result=result)
                path.segments.append(segment)
                return result

            case ast.TypeCallNode():
                match type_expression.type:
                    case ast.TypeAttributeNode() | ast.TypeCallNode() | ast.NameNode():
                        field = self.create_type_path_recursive(path, type_expression.type)
                    case _:
                        field = self.lower_type_expression(type_expression.type)
                        assert not isinstance(field, asg.Path)

                        segment = asg.PathSegment(name="type-expr", result=field)
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
                    result = asg.AsgError(node=type_expression)

                assert not isinstance(
                    result, (asg.FunctionDef, asg.LocalDeclaration, asg.TypeParameter)
                )
                segment = asg.PathSegment(name=type_expression.value, result=result)
                path.segments.append(segment)
                return result

    def lower_type_expression(
        self,
        type_expression: ast.TypeExpressionNode,
    ) -> asg.AsgType:
        match type_expression:
            case ast.TypeParameterNode():
                symbol = self.resolver.resolve_symbol(
                    type_expression.name,
                    include_local_declarations=False,
                    include_functions=False,
                )
                # XXX: Will this ever fail?
                # We should probably get it from generics instead
                assert isinstance(symbol, asg.TypeParameter)
                return symbol

            case ast.TypeCallNode() | ast.TypeAttributeNode() | ast.NameNode():
                path = asg.Path()
                self.create_type_path_recursive(path, type_expression)
                return path

            case ast.ListTypeNode():
                elt = self.lower_type_expression(type_expression.elt)
                return asg.ListType(elt=elt)

            case ast.SelfTypeNode():
                assert False, "TODO!"

            case ast.StructTypeNode():
                struct_def = asg.StructDef(name="inline-struct", is_declaration=False)
                for field in type_expression.fields:
                    struct_def.fields[field.name] = self.lower_type_expression(field.type)

                return struct_def

            case ast.TupleTypeNode():
                tuple_def = asg.TupleDef(name="inline-tuple", is_declaration=False)
                for elt in type_expression.elts:
                    tuple_def.elts.append(self.lower_type_expression(elt))

                return tuple_def

    def lower_block(
        self,
        block: list[ast.StatementNode],
        asg_body: asg.AsgBody,
    ) -> None:
        for statement in block:
            self.lower_statement(statement, asg_body)

    def lower_statement(
        self,
        statement: ast.StatementNode,
        asg_body: asg.AsgBody,
    ) -> None:
        match statement:
            case ast.TypeDeclarationNode():
                type_def = self.asg_ctx.fields[statement.id]
                self.resolver.enter_node(statement)

                match statement.type:
                    case ast.StructTypeNode():
                        assert isinstance(type_def, asg.StructDef)
                        for field in statement.type.fields:
                            type_def.fields[field.name] = self.lower_type_expression(field.type)

                    case ast.TupleTypeNode():
                        assert isinstance(type_def, asg.TupleDef)
                        for elt in statement.type.elts:
                            type_def.elts.append(self.lower_type_expression(elt))

                    case _:
                        assert False, 'TODO!'

                self.resolver.exit_node(statement)

            case ast.SumTypeNode():
                sum_def = self.asg_ctx.fields[statement.id]
                assert isinstance(sum_def, asg.SumDef)

                self.resolver.enter_node(statement)
                for field in statement.fields:
                    type = asg.UNIT
                    if field.type is not None:
                        type = self.lower_type_expression(field.type)

                    sum_def.types[field.name] = type

                self.resolver.exit_node(statement)

            case ast.FunctionDefNode():
                function_def = self.asg_ctx.fields[statement.id]
                assert isinstance(function_def, asg.FunctionDef)
                self.resolver.enter_node(statement)

                for parameter in statement.parameters:
                    type = self.lower_type_expression(parameter.annotation)
                    function_def.parameters[parameter.name] = type

                function_def.returns = self.lower_type_expression(statement.returns)

                if statement.body is not None:
                    function_def.body = asg.AsgBody()
                    self.lower_block(statement.body, function_def.body)

                self.resolver.exit_node(statement)

            case ast.ClassDefNode():
                class_def = self.asg_ctx.fields[statement.id]
                assert isinstance(class_def, asg.ClassDef)
                self.resolver.enter_node(statement)

                for substatement in statement.body:
                    if isinstance(substatement, ast.FunctionDefNode):
                        self.lower_statement(substatement, asg_body)
                        function_def = self.asg_ctx.fields[substatement.id]
                        assert isinstance(function_def, asg.FunctionDef)

                        class_def.functions[substatement.name] = function_def
                    else:
                        self.report_error(substatement, "Only functions are allowed in class body")

                self.resolver.exit_node(statement)

            case ast.UseNode() | ast.UseForNode():
                use_def = self.asg_ctx.fields[statement.id]
                assert isinstance(use_def, asg.UseDef)

                self.resolver.enter_node(statement)
                use_def.type = self.lower_type_expression(statement.type)

                if isinstance(statement, ast.UseForNode):
                    use_def.type_class = self.lower_type_expression(statement.type_class)

                for substatement in statement.body:
                    if isinstance(substatement, ast.FunctionDefNode):
                        self.lower_statement(substatement, asg_body)
                        function_def = self.asg_ctx.fields[substatement.id]
                        assert isinstance(function_def, asg.FunctionDef)

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
                asg_code = asg.Declaration(
                    node_id=statement.id,
                    local_declaration=declaration,
                    type=type,
                    value=value,
                )
                asg_body.statements.append(asg_code)

            case ast.ForNode():
                asg_code = asg.For(
                    node_id=statement.id,
                    target=self.lower_expression(statement.target),
                    iterator=self.lower_expression(statement.iterator),
                    body=asg.AsgBody(),
                )
                self.resolver.enter_node(statement)
                self.lower_block(statement.body, asg_code.body)
                self.resolver.exit_node(statement)
                asg_body.statements.append(asg_code)

            case ast.WhileNode():
                asg_code = asg.While(
                    node_id=statement.id,
                    condition=self.lower_expression(statement.condition),
                    body=asg.AsgBody(),
                )
                self.resolver.enter_node(statement)
                self.lower_block(statement.body, asg_code.body)
                self.resolver.exit_node(statement)
                asg_body.statements.append(asg_code)

            case ast.IfNode():
                asg_code = asg.If(
                    node_id=statement.id,
                    condition=self.lower_expression(statement.condition),
                    body=asg.AsgBody(),
                    else_body=asg.AsgBody(),
                )

                self.resolver.enter_node(statement)
                self.lower_block(statement.body, asg_code.body)
                self.resolver.exit_node(statement)

                if statement.else_statement is not None:
                    self.resolver.enter_node(statement.else_statement)
                    self.lower_block(statement.else_statement.body, asg_code.else_body)
                    self.resolver.exit_node(statement.else_statement)

                asg_body.statements.append(asg_code)

            case ast.AssignNode():
                target = self.lower_expression(statement.target)
                value = self.lower_expression(statement.value)
                asg_code = asg.Assignment(node_id=statement.id, target=target, value=value)
                asg_body.statements.append(asg_code)

            case ast.AugAssignNode():
                target = self.lower_expression(statement.target)
                value = self.lower_expression(statement.value)
                asg_code = asg.AugAssignment(node_id=statement.id, target=target, op=statement.op, value=value)
                asg_body.statements.append(asg_code)

            case ast.ReturnNode():
                value = (
                    self.lower_expression(statement.value) if statement.value is not None else None
                )
                asg_code = asg.Return(
                    node_id=statement.id,
                    value=value,
                )
                asg_body.statements.append(asg_code)

            case ast.ContinueNode():
                asg_code = asg.Continue(node_id=statement.id)
                asg_body.statements.append(asg_code)

            case ast.BreakNode():
                asg_code = asg.Break(node_id=statement.id)
                asg_body.statements.append(asg_code)

            case ast.ExprNode():
                asg_code = asg.Expr(
                    node_id=statement.id,
                    expr=self.lower_expression(statement.expr),
                )
                asg_body.statements.append(asg_code)

    def create_path_recursive(
        self,
        path: asg.Path,
        expression: ast.AttributeNode | ast.CallNode | ast.NameNode,
    ) -> asg.AsgPathResult | asg.Expression:
        # This is pretty confusing, but this function transforms attribute/call/name exprs
        # into a path as much as possible, then begins creating asg.Call/asg.Attribute
        # nodes if the node is not part of the path. This means that in some cases,
        # the function might return asg code that already contains the path, and in other
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
                        return asg.Attribute(node_id=expression.id, attr=expression.attr, value=field)

                assert not isinstance(field, asg.Path)
                if isinstance(field, asg.AsgCode):
                    return asg.Attribute(node_id=expression.id, attr=expression.attr, value=field)

                result = self.resolver.resolve_attribute(field, expression.attr)
                if result is None:
                    result = asg.AsgError(node=expression)

                segment = asg.PathSegment(name=expression.attr, result=result)
                path.segments.append(segment)
                if isinstance(result, asg.FunctionDef):
                    return asg.CoPath(node_id=expression.id, path=path)

                return result

            case ast.CallNode():
                match expression.callee:
                    case ast.AttributeNode() | ast.CallNode() | ast.NameNode():
                        field = self.create_path_recursive(path, expression.callee)
                    case _:
                        field = self.lower_expression(expression.callee)

                assert not isinstance(field, asg.Path)
                if not isinstance(field, asg.AsgCode):
                    segment = path.segments[-1]

                    for argument in expression.args:
                        argument = self.lower_expression(argument)
                        if not isinstance(argument, asg.CoPath):
                            assert False, 'Calling type requires path argument'

                        segment.arguments.append(argument.path)

                    return field

                arguments: list[asg.Expression] = []
                for argument in expression.args:
                    arguments.append(self.lower_expression(argument))

                return asg.Call(node_id=expression.id, callee=field, args=arguments)

            case ast.NameNode():
                result = self.resolver.resolve_symbol(expression.value)
                if result is None:
                    # Unresolved symbol
                    result = asg.AsgError(node=expression)

                segment = asg.PathSegment(name=expression.value, result=result)
                path.segments.append(segment)
                if isinstance(result, (asg.FunctionDef, asg.LocalDeclaration)):
                    return asg.CoPath(node_id=expression.id, path=path)

                return result

    def lower_expression(self, expression: ast.ExpressionNode) -> asg.Expression:
        match expression:
            case ast.NameNode() | ast.AttributeNode() | ast.CallNode():
                path = asg.Path()
                result = self.create_path_recursive(path, expression)
                if isinstance(result, asg.AsgCode):
                    return result

                return asg.CoPath(node_id=expression.id, path=path)

            case ast.ExpressionLambdaNode() | ast.BlockLambdaNode():
                function_def = self.asg_ctx.fields[expression.id]
                assert isinstance(function_def, asg.FunctionDef)
                self.resolver.enter_node(expression)

                for parameter in expression.parameters:
                    function_def.parameters[parameter.name] = asg.INFERRED

                function_def.returns = asg.INFERRED

                function_def.body = asg.AsgBody()
                if isinstance(expression, ast.BlockLambdaNode):
                    self.lower_block(expression.body, function_def.body)
                else:
                    asg_code = asg.Return(
                        node_id=expression.body.id,
                        value=self.lower_expression(expression.body),
                    )
                    function_def.body.statements.append(asg_code)

                self.resolver.exit_node(expression)

            case ast.AnnotatedNode():
                return asg.Annotated(
                    node_id=expression.id,
                    value=self.lower_expression(expression.value),
                    type=self.lower_type_expression(expression.type),
                )

            case ast.BoolOpNode():
                values: list[asg.Expression] = []
                for value in expression.values:
                    values.append(self.lower_expression(value))

                return asg.BoolOp(
                    node_id=expression.id,
                    op=expression.op,
                    values=values,
                )

            case ast.BinaryOpNode():
                left = self.lower_expression(expression.left)
                right = self.lower_expression(expression.right)
                return asg.BinaryOp(node_id=expression.id, left=left, op=expression.op, right=right)

            case ast.UnaryOpNode():
                return asg.UnaryOp(
                    node_id=expression.id,
                    op=expression.op,
                    operand=self.lower_expression(expression.operand),
                )

            case ast.CompareNode():
                comparators: list[asg.Comparator] = []
                for comparator in expression.comparators:
                    comparator = asg.Comparator(
                        node_id=comparator.id,
                        op=comparator.op,
                        value=self.lower_expression(comparator.value),
                    )
                    comparators.append(comparator)

                return asg.Compare(
                    node_id=expression.id,
                    left=self.lower_expression(expression.left),
                    comparators=comparators,
                )

            case ast.SubscriptNode():
                slices: list[asg.Expression] = []
                for slice in expression.slices:
                    slices.append(self.lower_expression(slice))

                return asg.Subscript(
                    node_id=expression.id,
                    value=self.lower_expression(expression.value),
                    slices=slices,
                )

            case ast.StructNode():
                fields: dict[str, asg.Expression] = {}
                for field in expression.fields:
                    fields[field.name] = self.lower_expression(field.value)

                return asg.Struct(node_id=expression.id, fields=fields)

            case ast.ListNode():
                elts: list[asg.Expression] = []
                for elt in expression.elts:
                    elts.append(self.lower_expression(elt))

                return asg.List(node_id=expression.id, elts=elts)

            case ast.TupleNode():
                elts: list[asg.Expression] = []
                for elt in expression.elts:
                    elts.append(self.lower_expression(elt))

                return asg.Tuple(node_id=expression.id, elts=elts)

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

                return asg.Slice(node_id=expression.id, start=start, stop=stop, step=step)

            case ast.IntegerNode():
                return asg.Integer(node_id=expression.id, value=expression.value)

            case ast.FloatNode():
                return asg.Float(node_id=expression.id, value=expression.value)

            case ast.ComplexNode():
                return asg.Complex(node_id=expression.id, value=expression.value)

            case ast.StringNode():
                return asg.String(node_id=expression.id, value=expression.value)

            case ast.ConstantNode():
                return asg.Constant(node_id=expression.id, kind=expression.kind)

    def lower_module(self) -> asg.ModuleDef:
        module = asg.ModuleDef()
        scope = self.resolver.create_scope(self.module.id, ScopeKind.MODULE)
        self.resolver.initialize_symbols_for_block(module, scope, self.module.body)

        module.body = asg.AsgBody()
        self.resolver.enter_node(self.module)
        self.lower_block(self.module.body, module.body)
        self.resolver.exit_node(self.module)

        return module

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
                        result = self.create_type_path_recursive(path, type_expression.type)
                    case _:
                        result = self.lower_type_expression(type_expression.type)
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

                        assert not isinstance(result, asg.Path)
                        segment = asg.PathSegment(name="type-expr", result=result)
                        path.segments.append(segment)

                result = self.resolver.resolve_attribute(result, type_expression.attr)
                if result is None:
                    # Unresolved attribute
                    result = asg.AsgError(node=type_expression)

                segment = asg.PathSegment(name=type_expression.attr, result=result)
                path.segments.append(segment)
                return result

            case ast.TypeCallNode():
                match type_expression.type:
                    case ast.TypeAttributeNode() | ast.TypeCallNode() | ast.NameNode():
                        result = self.create_type_path_recursive(path, type_expression.type)
                    case _:
                        result = self.lower_type_expression(type_expression.type)
                        assert not isinstance(result, asg.Path)

                        segment = asg.PathSegment(name="type-expr", result=result)
                        path.segments.append(segment)

                segment = path.segments[-1]
                for argument in type_expression.args:
                    type = self.lower_type_expression(argument)
                    segment.arguments.append(type)

                return result

            case ast.NameNode():
                result = self.resolver.resolve_symbol(
                    type_expression.value,
                    include_local_definitions=False,
                    include_functions=False,
                    include_type_parameters=False,
                )
                if result is None:
                    # Unresolved symbol
                    result = asg.AsgError(node=type_expression)

                assert not isinstance(
                    result, (asg.FunctionDef, asg.LocalDef, asg.TypeParameter)
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
                    include_local_definitions=False,
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
                struct_def = asg.StructDef(name="inline-struct", is_definition=False)
                for field in type_expression.fields:
                    type = self.lower_type_expression(field.type)
                    struct_field = asg.StructField(name=field.name, type=type)

                    self.asg_ctx.definitions[struct_field.def_id] = struct_field
                    struct_def.fields[field.name] = struct_field

                self.asg_ctx.definitions[struct_def.def_id] = struct_def
                return struct_def

            case ast.TupleTypeNode():
                tuple_def = asg.TupleDef(name="inline-tuple", is_definition=False)
                for i, elt in enumerate(type_expression.elts):
                    type = self.lower_type_expression(elt)
                    tuple_elt = asg.TupleElt(index=i, type=type)

                    self.asg_ctx.definitions[tuple_elt.def_id] = tuple_elt
                    tuple_def.elts.append(tuple_elt)

                self.asg_ctx.definitions[tuple_def.def_id] = tuple_def
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
            case ast.TypeDefinitionNode():
                type_def = self.asg_ctx.definitions[statement.id]
                self.resolver.enter_node(statement)

                match statement.type:
                    case ast.StructTypeNode():
                        assert isinstance(type_def, asg.StructDef)
                        for field in statement.type.fields:
                            type = self.lower_type_expression(field.type)
                            struct_field = asg.StructField(name=field.name, type=type)

                            self.asg_ctx.add_definition(type_def.def_id, struct_field)
                            type_def.fields[field.name] = struct_field

                    case ast.TupleTypeNode():
                        assert isinstance(type_def, asg.TupleDef)
                        for i, elt in enumerate(statement.type.elts):
                            type = self.lower_type_expression(elt)
                            tuple_elt = asg.TupleElt(index=i, type=type)

                            self.asg_ctx.add_definition(type_def.def_id, tuple_elt)
                            type_def.elts.append(tuple_elt)

                    case _:
                        assert False, 'TODO!'

                self.resolver.exit_node(statement)

            case ast.SumTypeNode():
                sum_def = self.asg_ctx.definitions[statement.id]
                assert isinstance(sum_def, asg.SumDef)

                self.resolver.enter_node(statement)
                for field in statement.fields:
                    type = asg.UNIT
                    if field.type is not None:
                        type = self.lower_type_expression(field.type)

                    type = asg.AliasDef(name=field.name, type=type)
                    self.asg_ctx.add_definition(sum_def.def_id, type)
                    sum_def.types[field.name] = type

                self.resolver.exit_node(statement)

            case ast.FunctionDefNode():
                function_def = self.asg_ctx.definitions[statement.id]
                assert isinstance(function_def, asg.FunctionDef)
                self.resolver.enter_node(statement)

                for parameter in statement.parameters:
                    asg_parameter = function_def.parameters[parameter.name]
                    asg_parameter.type = self.lower_type_expression(parameter.annotation)

                function_def.returns = self.lower_type_expression(statement.returns)

                if statement.body is not None:
                    function_def.body = asg.AsgBody()
                    self.lower_block(statement.body, function_def.body)

                self.resolver.exit_node(statement)

            case ast.ClassDefNode():
                class_def = self.asg_ctx.definitions[statement.id]
                assert isinstance(class_def, asg.ClassDef)
                self.resolver.enter_node(statement)

                for substatement in statement.body:
                    if isinstance(substatement, ast.FunctionDefNode):
                        self.lower_statement(substatement, asg_body)
                        function_def = self.asg_ctx.definitions[substatement.id]
                        assert isinstance(function_def, asg.FunctionDef)

                        class_def.functions[substatement.name] = function_def
                    else:
                        self.report_error(substatement, "Only functions are allowed in class body")

                self.resolver.exit_node(statement)

            case ast.UseNode() | ast.UseForNode():
                use_def = self.asg_ctx.definitions[statement.id]
                assert isinstance(use_def, asg.UseDef)

                self.resolver.enter_node(statement)
                use_def.type = self.lower_type_expression(statement.type)

                if isinstance(statement, ast.UseForNode):
                    use_def.type_class = self.lower_type_expression(statement.type_class)

                for substatement in statement.body:
                    if isinstance(substatement, ast.FunctionDefNode):
                        self.lower_statement(substatement, asg_body)
                        function_def = self.asg_ctx.definitions[substatement.id]
                        assert isinstance(function_def, asg.FunctionDef)

                        use_def.functions[substatement.name] = function_def
                    else:
                        self.report_error(substatement, "Only functions are allowed in class body")

                self.resolver.exit_node(statement)

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
                target_node = statement.target
                type = None
                if isinstance(target_node, ast.AnnotatedNode):
                    type = self.lower_type_expression(target_node.type)
                    target_node = target_node.value

                if not isinstance(target_node, (ast.NameNode, ast.AttributeNode)):
                    assert False, 'Unassignable target'

                value = None
                if statement.value is not None:
                    value = self.lower_expression(statement.value)

                match target_node:
                    case ast.NameNode():
                        definition = self.resolver.resolve_symbol(
                            target_node.value,
                            include_functions=False,
                            include_type_parameters=False,
                            include_local_definitions=False,
                            include_classes=False,
                        )
                        if definition is None:
                            definition = self.resolver.add_local_definition(target_node.value, statement)

                            asg_code = asg.Local(
                                node_id=statement.id,
                                local_definition=definition,
                                type=type,
                                value=value,
                            )
                        else:
                            assert isinstance(definition, asg.LocalDef)
                            path = asg.Path()
                            segment = asg.PathSegment(name=target_node.value, result=definition)
                            path.segments.append(segment)
                            co_path = asg.CoPath(node_id=target_node.id, path=path)

                            if value is None:
                                assert type is not None
                                asg_code = asg.Annotated(node_id=statement.id, value=co_path, type=type)
                                asg_code = asg.Expr(node_id=statement.id, expr=asg_code)
                            else:
                                asg_code = asg.Assignment(
                                    node_id=statement.id,
                                    target=co_path,
                                    type=type,
                                    value=value,
                                )
                        
                        asg_body.statements.append(asg_code)

                    case ast.AttributeNode():
                        target = self.lower_expression(target_node)
                        if value is None:
                            assert type is not None  # Type and value cannot be None

                            asg_code = asg.Annotated(
                                node_id=statement.target.id,
                                value=target,
                                type=type,
                            )
                            asg_code = asg.Expr(node_id=statement.id, expr=asg_code)
                        else:
                            asg_code = asg.Assignment(
                                node_id=statement.id,
                                target=target,
                                type=type,
                                value=value,
                            )

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
                        path_result = self.create_path_recursive(path, expression.value)
                    case _:
                        lowered_expression = self.lower_expression(expression.value)
                        assert not path.segments
                        return asg.Attribute(node_id=expression.id, attr=expression.attr, value=lowered_expression)

                assert not isinstance(path_result, asg.Path)
                if isinstance(path_result, asg.AsgCode):
                    return asg.Attribute(node_id=expression.id, attr=expression.attr, value=path_result)

                attribute = self.resolver.resolve_attribute(path_result, expression.attr)
                if attribute is None:
                    attribute = asg.AsgError(node=expression)

                segment = asg.PathSegment(name=expression.attr, result=attribute)
                path.segments.append(segment)
                if isinstance(attribute, asg.FunctionDef):
                    return asg.CoPath(node_id=expression.id, path=path)

                return attribute

            case ast.CallNode():
                match expression.callable:
                    case ast.AttributeNode() | ast.CallNode() | ast.NameNode():
                        result = self.create_path_recursive(path, expression.callable)
                    case _:
                        result = self.lower_expression(expression.callable)

                assert not isinstance(result, asg.Path)
                if not isinstance(result, asg.AsgCode):
                    segment = path.segments[-1]

                    for argument in expression.args:
                        argument = self.lower_expression(argument)
                        if not isinstance(argument, asg.CoPath):
                            assert False, 'Calling type requires path argument'

                        segment.arguments.append(argument.path)

                    return result

                arguments: list[asg.Expression] = []
                for argument in expression.args:
                    arguments.append(self.lower_expression(argument))

                return asg.Call(node_id=expression.id, callable=result, args=arguments)

            case ast.NameNode():
                result = self.resolver.resolve_symbol(expression.value)
                if result is None:
                    # Unresolved symbol
                    result = asg.AsgError(node=expression)

                segment = asg.PathSegment(name=expression.value, result=result)
                path.segments.append(segment)
                if isinstance(result, (asg.FunctionDef, asg.LocalDef)):
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

            case ast.LambdaNode():
                function_def = self.asg_ctx.definitions[expression.id]
                assert isinstance(function_def, asg.FunctionDef)
                self.resolver.enter_node(expression)

                for parameter in expression.parameters:
                    asg_parameter = function_def.parameters[parameter.name]
                    if parameter.type is not None:
                        asg_parameter.type = self.lower_type_expression(parameter.type)
                    else:
                        asg_parameter.type = asg.INFERRED

                if expression.returns is not None:
                    function_def.returns = self.lower_type_expression(expression.returns)
                else:
                    function_def.returns = asg.INFERRED

                function_def.body = asg.AsgBody()
                self.lower_block(expression.body, function_def.body)
                # TODO: Automatic reutrn insertion

                self.resolver.exit_node(expression)
                return asg.Lambda(node_id=expression.id, function_def=function_def)

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

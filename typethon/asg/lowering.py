import typing

import attr

from ..syntax.typethon import ast
from . import asg
from .resolution import DefKind, LocalResult, ResultKind


@attr.s(kw_only=True, slots=True)
class AsgLowering:
    asg_ctx: asg.AsgContext = attr.ib()

    def report_error(
        self,
        node: ast.Node,
        message: str,
        *format: str,
    ) -> None:
        self.asg_ctx.diagnostics.report_error((node.start, node.end), message, *format)

    def lower_def(self, def_id: asg.DefinitionId) -> asg.AsgDefinition:
        if def_id in self.asg_ctx.defs:
            return self.asg_ctx.defs[def_id]

        match self.asg_ctx.def_index.def_kinds[def_id]:
            case DefKind.MODULE:
                assert False
            case DefKind.STRUCT:
                definition = self.lower_struct(def_id)
            case DefKind.TUPLE:
                definition = self.lower_tuple(def_id)
            case DefKind.SUM:
                definition = self.lower_sum(def_id)
            case DefKind.VARIANT:
                definition = self.lower_variant(def_id)
            case DefKind.FUNCTION:
                definition = self.lower_function(def_id)
            case DefKind.CLASS:
                assert False
            case DefKind.TYPE_PARAMETER:
                node = self.asg_ctx.node_for_def_id(def_id)
                assert isinstance(node, ast.TypeParameterNode)
                definition = asg.TypeParameterDef(def_id=def_id, name=node.name)
            case DefKind.FIELD:
                definition = self.lower_field(def_id)
            case DefKind.USE:
                assert False
            case DefKind.NEW_TYPE:
                definition = self.lower_new_type(def_id)

        self.asg_ctx.defs[def_id] = definition
        return definition

    def lower_field(self, def_id: asg.DefinitionId) -> asg.StructField | asg.TupleElt:
        parent_id = self.asg_ctx.parent_id(def_id)
        assert parent_id is not None
        node = self.asg_ctx.node_for_def_id(def_id)

        match self.asg_ctx.def_index.def_kinds[parent_id]:
            case DefKind.STRUCT:
                assert isinstance(node, ast.StructTypeFieldNode)
                type = self.lower_path(node.type)
                return asg.StructField(def_id=def_id, name=node.name, type=type)
            case DefKind.TUPLE:
                assert isinstance(node, ast.TupleEltNode)
                type = self.lower_path(node.value)
                return asg.TupleElt(def_id=def_id, index=node.index, type=type)
            case _:
                assert False, "Invalid field owner"

    def lower_struct(self, def_id: asg.DefinitionId) -> asg.StructDef:
        node = self.asg_ctx.node_for_def_id(def_id)
        if isinstance(node, ast.TypeDefinitionNode):
            parent_node = node
            struct = node.type
            assert isinstance(struct, ast.StructTypeNode)
        else:
            parent_id = self.asg_ctx.parent_id(def_id)
            assert parent_id is not None
            parent_node = self.asg_ctx.node_for_def_id(parent_id)
            assert isinstance(parent_node, ast.SumTypeVariantNode)
            struct = node

        assert isinstance(struct, ast.StructTypeNode)
        fields: dict[str, asg.StructField] = {}
        for field in struct.fields:
            field_def_id = self.asg_ctx.def_id_for_node_id(field.id)
            result = self.lower_field(field_def_id)
            assert isinstance(result, asg.StructField)
            fields[field.name] = result

        return asg.StructDef(
            def_id=def_id,
            name=parent_node.name,
            fields=fields,
        )

    def lower_tuple(self, def_id: asg.DefinitionId) -> asg.TupleDef:
        node = self.asg_ctx.node_for_def_id(def_id)
        if isinstance(node, ast.TypeDefinitionNode):
            parent_node = node
            tuple = node.type
            assert isinstance(tuple, ast.TupleNode)
        else:
            parent_id = self.asg_ctx.parent_id(def_id)
            assert parent_id is not None
            parent_node = self.asg_ctx.node_for_def_id(parent_id)
            assert isinstance(parent_node, ast.SumTypeVariantNode)
            tuple = node

        assert isinstance(tuple, ast.TupleNode)
        elts: list[asg.TupleElt] = []
        for elt in tuple.elts:
            elt_def_id = self.asg_ctx.def_id_for_node_id(elt.id)
            result = self.lower_field(elt_def_id)
            assert isinstance(result, asg.TupleElt)
            elts.append(result)

        return asg.TupleDef(
            def_id=def_id,
            name=parent_node.name,
            elts=elts,
        )

    def lower_variant(self, def_id: asg.DefinitionId) -> asg.SumVariant:
        node = self.asg_ctx.node_for_def_id(def_id)
        assert isinstance(node, ast.SumTypeVariantNode)

        type = None
        if node.of_type is not None:
            node_id = (
                node.of_type.id if isinstance(node.of_type.type, ast.TypeParameterNode) else node.of_type.type.id
            )
            type_def_id = self.asg_ctx.def_id_for_node_id(node_id)
            type = self.lower_def(type_def_id)
            assert isinstance(type, (asg.StructDef, asg.TupleDef, asg.NewTypeDef))

        return asg.SumVariant(def_id=def_id, name=node.name, type=type)

    def lower_sum(self, def_id: asg.DefinitionId) -> asg.SumDef:
        node = self.asg_ctx.node_for_def_id(def_id)
        assert isinstance(node, ast.SumTypeNode)

        variants: dict[str, asg.SumVariant] = {}
        for variant in node.variants:
            variant_def_id = self.asg_ctx.def_id_for_node_id(variant.id)
            variants[variant.name] = self.lower_variant(variant_def_id)

        return asg.SumDef(def_id=def_id, name=node.name, variants=variants)

    def lower_path(self, path_expression: ast.ExpressionNode) -> asg.AsgPathExpression:
        match path_expression:
            case ast.NameNode():
                result = self.asg_ctx.syms_resolved[path_expression.id]
                if isinstance(result, LocalResult):
                    assert False, "Type contains local def"
                elif result == ResultKind.UNDEFINED:
                    assert False, f"Undefined name {path_expression.value}"

                segment = asg.PathSegment(name=path_expression.value, result=result)
                return asg.Path(segments=[segment])

            case ast.ConstantNode():
                if path_expression.kind is not ast.ConstantKind.SELF:
                    assert False, "Invalid constant in path expression"

                assert False, "Not implemented"

            case ast.TypeParameterNode():
                def_id = self.asg_ctx.def_id_for_node_id(path_expression.id)
                type_parameter = self.lower_def(def_id)
                assert isinstance(type_parameter, asg.TypeParameterDef)
                return type_parameter

            case ast.CallNode():
                path = self.lower_path(path_expression.callable)
                if not isinstance(path, asg.Path):
                    segment = asg.ExpressionPathSegment(expression=path)
                    path = asg.Path(segments=[segment])

                for argument in path_expression.args:
                    path_argument = self.lower_path(argument)
                    path.segments[-1].arguments.append(path_argument)

                return path

            case ast.AttributeNode():
                path = self.lower_path(path_expression.value)
                if not isinstance(path, asg.Path):
                    segment = asg.ExpressionPathSegment(expression=path)
                    path = asg.Path(segments=[segment])

                result = self.asg_ctx.syms_resolved.get(path_expression.id)
                assert not isinstance(result, LocalResult)

                if result is not None:
                    assert result != ResultKind.UNDEFINED
                    segment = asg.PathSegment(name=path_expression.attr, result=result)
                else:
                    segment = asg.UnresolvedPathSegment(name=path_expression.attr)

                path.segments.append(segment)
                return path

            case ast.ListNode():
                assert len(path_expression.elts) == 1, "List path must have one node"
                path = self.lower_path(path_expression.elts[0])
                return asg.PathList(elt=path)

            case ast.StructTypeNode():
                fields: dict[str, asg.AsgPathExpression] = {}
                for field in path_expression.fields:
                    fields[field.name] = self.lower_path(field.type)

                return asg.PathStruct(fields=fields)

            case ast.TupleNode():
                elts = [self.lower_path(elt.value) for elt in path_expression.elts]
                return asg.PathTuple(elts=elts)

            case _:
                assert False, f"{path_expression} is not valid as a path expression"

    def lower_new_type(self, def_id: asg.DefinitionId) -> asg.NewTypeDef:
        node = self.asg_ctx.node_for_def_id(def_id)
        if isinstance(node, ast.TypeDefinitionNode):
            parent_node = node
            new_type = node.type
        else:
            assert isinstance(node, ast.VariantOfTypeNode)

            parent_id = self.asg_ctx.parent_id(def_id)
            parent_node = self.asg_ctx.node_for_def_id(parent_id) if parent_id is not None else None
            assert isinstance(parent_node, ast.SumTypeVariantNode)
            new_type = node.type

        type = self.lower_path(new_type)
        return asg.NewTypeDef(
            def_id=def_id,
            name=parent_node.name,
            type=type,
        )

    def lower_function(self, def_id: asg.DefinitionId) -> asg.FunctionDef:
        node = self.asg_ctx.node_for_def_id(def_id)
        assert isinstance(node, (ast.FunctionDefNode, ast.LambdaNode))

        parameters: dict[str, asg.FunctionParameter] = {}
        for parameter in node.parameters:
            parameter_def = asg.FunctionParameter(
                name=parameter.name,
                type=self.lower_path(parameter.type) if parameter.type is not None else None,
            )
            parameters[parameter.name] = parameter_def

        returns = self.lower_path(node.returns) if node.returns is not None else None

        body = None
        if node.body is not None:
            lowering = CodeLowering(
                asg_lowering=self,
                statements=node.body,
                body=asg.AsgBody(),
            )
            body = lowering.lower()

        return asg.FunctionDef(
            def_id=def_id,
            name=node.name if isinstance(node, ast.FunctionDefNode) else "<anonymous function>",
            parameters=parameters,
            returns=returns,
            body=body,
        )


@attr.s(kw_only=True, slots=True)
class CodeLowering:
    asg_lowering: AsgLowering = attr.ib()
    statements: list[ast.StatementNode] = attr.ib()
    body: asg.AsgBody = attr.ib()

    @property
    def asg_ctx(self) -> asg.AsgContext:
        return self.asg_lowering.asg_ctx

    def lower(self) -> asg.AsgBody:
        for statement in self.statements:
            result = self.lower_statement(statement)
            if result is not None:
                self.body.statements.append(result)

        return self.body

    def lower_statement(self, statement: ast.StatementNode) -> asg.Statement | None:
        match statement:
            case ast.IfNode():
                lowering = CodeLowering(
                    asg_lowering=self.asg_lowering,
                    statements=statement.body,
                    body=asg.AsgBody(),
                )
                body = lowering.lower()

                else_body = None
                if statement.else_statement is not None:
                    lowering = CodeLowering(
                        asg_lowering=self.asg_lowering,
                        statements=statement.else_statement.body,
                        body=asg.AsgBody(),
                    )
                    else_body = lowering.lower()

                return asg.If(
                    code_id=self.asg_ctx.code_id(statement),
                    condition=self.lower_expression(statement.condition),
                    body=body,
                    else_body=else_body,
                )

            case ast.AssignNode():
                # TODO: Consider adding an asg target that holds name and optional type
                # and allow constructs such as:
                #   - x: int += 10
                #   - for x: int in range(10)

                target = self.lower_expression(statement.target)
                type = None

                if isinstance(target, asg.Ascribe):
                    type = target.type
                    target = target.value

                assert isinstance(target, (asg.Name, asg.Attribute))
                return asg.Assign(
                    code_id=self.asg_ctx.code_id(statement),
                    target=target,
                    type=type,
                    value=self.lower_expression(statement.value),
                )

            case ast.AugAssignNode():
                target = self.lower_target(statement.target)
                return asg.AugAssign(
                    code_id=self.asg_ctx.code_id(statement),
                    target=target,
                    op=statement.op,
                    value=self.lower_expression(statement.value),
                )

            case ast.ForNode():
                lowering = CodeLowering(
                    asg_lowering=self.asg_lowering,
                    statements=statement.body,
                    body=asg.AsgBody(),
                )
                body = lowering.lower()

                return asg.For(
                    code_id=self.asg_ctx.code_id(statement),
                    target=self.lower_target(statement.target),
                    iterator=self.lower_expression(statement.iterator),
                    body=body,
                )

            case ast.WhileNode():
                lowering = CodeLowering(
                    asg_lowering=self.asg_lowering,
                    statements=statement.body,
                    body=asg.AsgBody(),
                )
                body = lowering.lower()

                return asg.While(
                    code_id=self.asg_ctx.code_id(statement),
                    condition=self.lower_expression(statement.condition),
                    body=body,
                )

            case ast.BreakNode():
                # TODO: check for loop
                return asg.Break(code_id=self.asg_ctx.code_id(statement))

            case ast.ContinueNode():
                # TODO: check for loop
                return asg.Continue(code_id=self.asg_ctx.code_id(statement))

            case ast.ReturnNode():
                # TODO: check for function
                return asg.Return(
                    code_id=self.asg_ctx.code_id(statement),
                    value=self.lower_expression(statement.value)
                    if statement.value is not None
                    else None,
                )

            case ast.ExprNode():
                return asg.Expr(
                    code_id=self.asg_ctx.code_id(statement),
                    expr=self.lower_expression(statement.expr),
                )

    def lower_target(self, expression: ast.ExpressionNode) -> asg.Name | asg.Attribute:
        result = self.lower_expression(expression)
        assert isinstance(result, (asg.Name, asg.Attribute)), "Invalid assignment target"
        return result

    def lower_expression(self, expression: ast.ExpressionNode) -> asg.Expression:
        match expression:
            case ast.LambdaNode():
                function_def = self.asg_lowering.lower_def(
                    self.asg_ctx.def_id_for_node_id(expression.id)
                )
                assert isinstance(function_def, asg.FunctionDef)

                return asg.Lambda(
                    code_id=self.asg_ctx.code_id(expression),
                    function_def=function_def,
                )

            case ast.AscribeNode():
                return asg.Ascribe(
                    code_id=self.asg_ctx.code_id(expression),
                    value=self.lower_expression(expression.value),
                    type=self.asg_lowering.lower_path(expression.type),
                )

            case ast.BoolOpNode():
                return asg.BoolOp(
                    code_id=self.asg_ctx.code_id(expression),
                    op=expression.op,
                    values=[self.lower_expression(expression) for expression in expression.values],
                )

            case ast.BinaryOpNode():
                return asg.BinaryOp(
                    code_id=self.asg_ctx.code_id(expression),
                    left=self.lower_expression(expression.left),
                    op=expression.op,
                    right=self.lower_expression(expression.right),
                )

            case ast.UnaryOpNode():
                return asg.UnaryOp(
                    code_id=self.asg_ctx.code_id(expression),
                    op=expression.op,
                    operand=self.lower_expression(expression.operand),
                )

            case ast.CompareNode():
                comparators: list[asg.Comparator] = []

                for comparator in expression.comparators:
                    inner_code_id = self.asg_ctx.code_id(comparator)
                    comparator = asg.Comparator(
                        code_id=inner_code_id,
                        op=comparator.op,
                        value=self.lower_expression(comparator.value),
                    )
                    comparators.append(comparator)

                return asg.Compare(
                    code_id=self.asg_ctx.code_id(expression),
                    left=self.lower_expression(expression.left),
                    comparators=comparators,
                )

            case ast.CallNode():
                return asg.Call(
                    code_id=self.asg_ctx.code_id(expression),
                    callable=self.lower_expression(expression.callable),
                    args=[self.lower_expression(argument) for argument in expression.args],
                )

            case ast.IntegerNode():
                return asg.Integer(
                    code_id=self.asg_ctx.code_id(expression),
                    value=expression.value,
                )

            case ast.FloatNode():
                return asg.Float(
                    code_id=self.asg_ctx.code_id(expression),
                    value=expression.value,
                )

            case ast.ComplexNode():
                return asg.Complex(
                    code_id=self.asg_ctx.code_id(expression),
                    value=expression.value,
                )

            case ast.StringNode():
                return asg.String(
                    code_id=self.asg_ctx.code_id(expression),
                    value=expression.value,
                )

            case ast.AttributeNode():
                return asg.Attribute(
                    code_id=self.asg_ctx.code_id(expression),
                    result=self.asg_ctx.syms_resolved.get(expression.id),
                    value=self.lower_expression(expression.value),
                    attr=expression.attr,
                )

            case ast.SubscriptNode():
                return asg.Subscript(
                    code_id=self.asg_ctx.code_id(expression),
                    value=self.lower_expression(expression.value),
                    slices=[self.lower_expression(slice) for slice in expression.slices],
                )

            case ast.NameNode():
                return asg.Name(
                    name=expression.value,
                    resolved=self.asg_ctx.syms_resolved[expression.id],
                )

            case ast.RecordNode():
                fields: dict[str, asg.RecordField] = {}
                for field in expression.fields:
                    fields[field.name] = asg.RecordField(
                        name=field.name,
                        value=self.lower_expression(field.value),
                    )

                return asg.Record(
                    code_id=self.asg_ctx.code_id(expression),
                    fields=fields,
                )

            case ast.TupleNode():
                return asg.AmbiguousTuple(
                    code_id=self.asg_ctx.code_id(expression),
                    elts=[self.lower_expression(elt.value) for elt in expression.elts],
                )

            case ast.ListNode():
                return asg.AmbiguousList(
                    code_id=self.asg_ctx.code_id(expression),
                    elts=[self.lower_expression(elt) for elt in expression.elts],
                )

            case ast.SliceNode():
                start = (
                    self.lower_expression(expression.start_index)
                    if expression.start_index is not None
                    else None
                )
                stop = (
                    self.lower_expression(expression.stop_index)
                    if expression.stop_index is not None
                    else None
                )
                step = (
                    self.lower_expression(expression.step_index)
                    if expression.step_index is not None
                    else None
                )
                return asg.Slice(
                    code_id=self.asg_ctx.code_id(expression),
                    start=start,
                    stop=stop,
                    step=step,
                )

            case ast.ConstantNode():
                if expression.kind is ast.ConstantKind.SELF:
                    assert False, "No implemente"

                elif expression.kind is ast.ConstantKind.ELLIPSIS:
                    assert False, "No implemented"

            case ast.TypeParameterNode() | ast.StructTypeNode():
                path_expression = self.asg_lowering.lower_path(expression)
                assert isinstance(path_expression, (asg.TypeParameterDef, asg.PathStruct))

                return asg.CoPathExpression(
                    code_id=self.asg_ctx.code_id(expression),
                    expression=path_expression,
                )

import attr
import typing

from ..syntax.typethon import ast
from .resolution import DefKind, LocalResult, ResultKind
from . import asg


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

    def lower_def(self, def_id: asg.DefinitionId) -> asg.Definition:
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
                type = self.lower_type(node.type)
                return asg.StructField(def_id=def_id, name=node.name, type=type)
            case DefKind.TUPLE:
                assert isinstance(node, ast.TupleTypeEltNode)
                type = self.lower_type(node.type)
                return asg.TupleElt(def_id=def_id, index=node.index, type=type)
            case _:
                assert False, "Invalid field owner"

    def lower_struct(self, def_id: asg.DefinitionId) -> asg.StructDef:
        struct  = self.asg_ctx.node_for_def_id(def_id)
        assert isinstance(struct, ast.StructTypeNode)

        parent_id = self.asg_ctx.parent_id(def_id)
        parent_node = self.asg_ctx.node_for_def_id(parent_id) if parent_id is not None else None
        if isinstance(parent_node, (ast.TypeDefinitionNode, ast.SumTypeVariantNode)):
            name = parent_node.name
            is_definition = True
        else:
            name = "<anonymous struct>"
            is_definition = False

        assert isinstance(struct, ast.StructTypeNode)
        fields: dict[str, asg.StructField] = {}
        for field in struct.fields:
            field_def_id = self.asg_ctx.def_id_for_node_id(field.id)
            result = self.lower_field(field_def_id)
            assert isinstance(result, asg.StructField)
            fields[field.name] = result

        return asg.StructDef(
            def_id=def_id,
            name=name,
            is_definition=is_definition,
            fields=fields,
        )

    def lower_tuple(self, def_id: asg.DefinitionId) -> asg.TupleDef:
        tuple = self.asg_ctx.node_for_def_id(def_id)
        assert isinstance(tuple, ast.TupleTypeNode)

        parent_id = self.asg_ctx.parent_id(def_id)
        parent_node = self.asg_ctx.node_for_def_id(parent_id) if parent_id is not None else None
        if isinstance(parent_node, (ast.TypeDefinitionNode, ast.SumTypeVariantNode)):
            name = parent_node.name
            is_definition = True
        else:
            name = "<anonymous tuple>"
            is_definition = False

        assert isinstance(tuple, ast.TupleTypeNode)
        elts: list[asg.TupleElt] = []
        for elt in tuple.elts:
            elt_def_id = self.asg_ctx.def_id_for_node_id(elt.id)
            result = self.lower_field(elt_def_id)
            assert isinstance(result, asg.TupleElt)
            elts.append(result)

        return asg.TupleDef(
            def_id=def_id,
            name=name,
            is_definition=is_definition,
            elts=elts,
        )

    def lower_variant(self, def_id: asg.DefinitionId) -> asg.SumVariant:
        node = self.asg_ctx.node_for_def_id(def_id)
        assert isinstance(node, ast.SumTypeVariantNode)

        type = None
        if node.type is not None:
            type_def_id = self.asg_ctx.def_id_for_node_id(node.type.id)
            type = self.lower_def(type_def_id)
            assert isinstance(type, (asg.StructDef, asg.TupleDef, asg.AliasDef))

        return asg.SumVariant(def_id=def_id, name=node.name, type=type)

    def lower_sum(self, def_id: asg.DefinitionId) -> asg.SumDef:
        node = self.asg_ctx.node_for_def_id(def_id)
        assert isinstance(node, ast.SumTypeNode)

        variants: dict[str, asg.SumVariant] = {}
        for variant in node.variants:
            variant_def_id = self.asg_ctx.def_id_for_node_id(variant.id)
            variants[variant.name] = self.lower_variant(variant_def_id)

        return asg.SumDef(def_id=def_id, name=node.name, variants=variants)

    def lower_type(self, type_expression: ast.TypeExpressionNode) -> asg.AsgType:
        match type_expression:
            case ast.NameNode():
                result = self.asg_ctx.syms_resolved[type_expression.id]
                if isinstance(result, LocalResult):
                    assert False, "Type contains local def"
                elif result == ResultKind.ERROR:
                    assert False, f"Undefined name {type_expression.value}"

                segment = asg.PathSegment(name=type_expression.value, result=result)
                return asg.Path(segments=[segment])

            case ast.SelfTypeNode():
                assert False, "Not Implemented"

            case ast.TypeParameterNode():
                def_id = self.asg_ctx.def_id_for_node_id(type_expression.id)
                type_parameter = self.lower_def(def_id)
                assert isinstance(type_parameter, asg.TypeParameterDef)
                return type_parameter

            case ast.TypeCallNode():
                path = self.lower_type(type_expression.type)
                if not isinstance(path, asg.Path):
                    segment = asg.ExprPathSegment(expression=path)
                    path = asg.Path(segments=[segment])

                for argument in type_expression.args:
                    type_argument = self.lower_type(argument)
                    path.segments[-1].arguments.append(type_argument)

                return path

            case ast.TypeAttributeNode():
                path = self.lower_type(type_expression.type)
                if not isinstance(path, asg.Path):
                    segment = asg.ExprPathSegment(expression=path)
                    path = asg.Path(segments=[segment])

                result = self.asg_ctx.syms_resolved.get(type_expression.id)
                assert not isinstance(result, LocalResult)

                if result is not None:
                    assert result != ResultKind.ERROR
                    segment = asg.PathSegment(name=type_expression.attr, result=result)
                else:
                    segment = asg.DynamicPathSegment(name=type_expression.attr)

                path.segments.append(segment)
                return path

            case ast.ListTypeNode():
                type = self.lower_type(type_expression.elt)
                return asg.ListType(elt=type)

            case ast.StructTypeNode():
                def_id = self.asg_ctx.def_id_for_node_id(type_expression.id)
                return self.lower_struct(def_id)

            case ast.TupleTypeNode():
                def_id = self.asg_ctx.def_id_for_node_id(type_expression.id)
                return self.lower_tuple(def_id)

    def lower_new_type(self, def_id: asg.DefinitionId) -> asg.AliasDef:
        node = self.asg_ctx.node_for_def_id(def_id)

        parent_id = self.asg_ctx.parent_id(def_id)
        assert parent_id is not None
        parent_node = self.asg_ctx.node_for_def_id(parent_id)

        match parent_node:
            case ast.TypeDefinitionNode():
                assert node is parent_node.type

                type = self.lower_type(node)
                return asg.AliasDef(def_id=def_id, name=parent_node.name, type=type)
            case ast.SumTypeVariantNode():
                assert node is parent_node.type

                type = self.lower_type(node)
                return asg.AliasDef(def_id=def_id, name=parent_node.name, type=type)
            case _:
                assert False, f"Invalid parent for alias: {parent_node}"

    def lower_function(self, def_id: asg.DefinitionId) -> asg.FunctionDef:
        node = self.asg_ctx.node_for_def_id(def_id)
        assert isinstance(node, ast.FunctionDefNode)

        parameters: dict[str, asg.FunctionParameter] = {}
        for parameter in node.parameters:
            parameter_def = asg.FunctionParameter(
                name=parameter.name,
                type=self.lower_type(parameter.annotation)
            )
            parameters[parameter.name] = parameter_def

        returns = self.lower_type(node.returns)
        return asg.FunctionDef(
            def_id=def_id,
            name=node.name,
            parameters=parameters,
            returns=returns,
        )

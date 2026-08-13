from __future__ import annotations

import typing

import attr

from ..syntax.typethon import ast
from . import resolution

if typing.TYPE_CHECKING:
    from . import asg


@attr.s(kw_only=True, slots=True)
class TypeParamIndex:
    paremeters: dict[str, asg.DefinitionId] = attr.ib(factory=dict)


# TODO: Indexing should construct an index table for sum types, modules, classes
# functions. (Anywhere definitions can be created.)
# I think in some cases it will be useless but maybe it should be done regardless
# for consistency?
# The most obvious example is for module.Type
# A less obvious example is SumType.Variant
# Obviously function.Type in def function(): type Type = ...
# is not possible, which is why it would be useless in some cases.
# There is no path syntax that would allow you to access Type
# besides the regular lexical scope. There's also no notion of modules
# that aren't files.

@attr.s(kw_only=True, slots=True)
class DefIndexing:
    asg_ctx: asg.AsgContext = attr.ib()
    def_params: dict[asg.DefinitionId, TypeParamIndex] = attr.ib(factory=dict)
    def_kinds: dict[asg.DefinitionId, resolution.DefKind] = attr.ib(factory=dict)

    def def_id(
        self, def_kind: resolution.DefKind, node_id: ast.NodeId
    ) -> asg.DefinitionId:
        def_id = self.asg_ctx.def_id(node_id)
        self.def_kinds[def_id] = def_kind
        return def_id

    def index_type_parameters(
        self,
        parent_id: asg.DefinitionId,
        def_id: asg.DefinitionId,
        type_expression: ast.TypeExpressionNode,
    ) -> None:
        use_parent = self.def_kinds[parent_id] in (
            resolution.DefKind.STRUCT,
            resolution.DefKind.TUPLE,
            resolution.DefKind.SUM,
            resolution.DefKind.USE,
            resolution.DefKind.CLASS,
        )
        param_index = self.def_params.get(def_id)
        parent_param_index = self.def_params.get(parent_id) if use_parent else None

        for subexpression in ast.walk_type_expressions(type_expression):
            if not isinstance(subexpression, ast.TypeParameterNode):
                continue

            param_def_id = None
            if parent_param_index is not None:
                param_def_id = parent_param_index.paremeters.get(subexpression.name)

            if param_def_id is None:
                if param_index is not None:
                    param_def_id = param_index.paremeters.get(subexpression.name)
                else:
                    param_index = TypeParamIndex()
                    self.def_params[def_id] = param_index

            if param_def_id is None:
                param_def_id = self.def_id(
                    resolution.DefKind.TYPE_PARAMETER, subexpression.id
                )
                assert param_index is not None
                param_index.paremeters[subexpression.name] = param_def_id
                self.asg_ctx.record_parent(param_def_id, def_id)

            self.asg_ctx.record_node(param_def_id, subexpression.id)

    def index_struct(self, struct: ast.StructTypeNode) -> asg.DefinitionId:
        def_id = self.def_id(resolution.DefKind.STRUCT, struct.id)

        for field in struct.fields:
            field_def_id = self.def_id(resolution.DefKind.FIELD, field.id)
            self.asg_ctx.record_parent(field_def_id, def_id)

        return def_id

    def index_tuple(self, tuple: ast.TupleTypeNode) -> asg.DefinitionId:
        def_id = self.def_id(resolution.DefKind.TUPLE, tuple.id)

        for elt in tuple.elts:
            elt_def_id = self.def_id(resolution.DefKind.FIELD, elt.id)
            self.asg_ctx.record_parent(elt_def_id, def_id)

        return def_id

    def index_block(
        self, parent_id: asg.DefinitionId, statements: list[ast.StatementNode]
    ) -> None:
        for statement in statements:
            self.index_statement(parent_id, statement)

    def index_statement(
        self, parent_id: asg.DefinitionId, statement: ast.StatementNode
    ) -> None:
        match statement:
            case ast.TypeDefinitionNode():
                match statement.type:
                    case ast.StructTypeNode():
                        def_id = self.index_struct(statement.type)
                    case ast.TupleTypeNode():
                        def_id = self.index_tuple(statement.type)
                    case _:
                        # TODO: type UserId = int
                        # Should UserId be an alias or a new type
                        def_id = self.def_id(
                            resolution.DefKind.NEW_TYPE, statement.type.id
                        )

                # type T = { ... }
                # ^^^^^    ^^^^^^^ Node ids both point to the same def id
                self.asg_ctx.record_node(def_id, statement.id)
                self.asg_ctx.record_parent(def_id, parent_id)

                self.index_type_parameters(parent_id, def_id, statement.type)

            case ast.SumTypeNode():
                def_id = self.def_id(resolution.DefKind.SUM, statement.id)
                self.asg_ctx.record_parent(def_id, parent_id)

                for variant in statement.variants:
                    variant_def_id = self.def_id(resolution.DefKind.VARIANT, variant.id)
                    self.asg_ctx.record_parent(variant_def_id, def_id)

                    type_def_id = None
                    match variant.type:
                        case ast.StructTypeNode():
                            type_def_id = self.index_struct(variant.type)
                        case ast.TupleTypeNode():
                            type_def_id = self.index_tuple(variant.type)
                        case _:
                            if variant.type is not None:
                                type_def_id = self.def_id(
                                    resolution.DefKind.NEW_TYPE, variant.type.id
                                )

                    if type_def_id is not None:
                        assert variant.type is not None
                        # type T = ( V1 of { ... } | V2 of { ... } )
                        # ^^^^^^     ^^    ^^^^^^^
                        # 1 is a sum, 2 is a variant, 3 is a struct; all with different def ids
                        self.asg_ctx.record_parent(type_def_id, variant_def_id)
                        self.index_type_parameters(parent_id, def_id, variant.type)
                        # All type parameters belong to the sum, not the variant!

            case ast.FunctionDefNode():
                def_id = self.def_id(resolution.DefKind.FUNCTION, statement.id)
                self.asg_ctx.record_parent(def_id, parent_id)

                for parameter in statement.parameters:
                    self.index_type_parameters(parent_id, def_id, parameter.annotation)

                self.index_type_parameters(parent_id, def_id, statement.returns)

            case ast.ClassDefNode():
                def_id = self.def_id(resolution.DefKind.CLASS, statement.id)
                self.asg_ctx.record_parent(def_id, parent_id)

                if statement.parameters:
                    param_index = TypeParamIndex()
                    self.def_params[def_id] = param_index

                    for type_parameter in statement.parameters:
                        param_def_id = self.def_id(
                            resolution.DefKind.TYPE_PARAMETER, type_parameter.id
                        )
                        param_index.paremeters[type_parameter.name] = param_def_id

                for substatement in statement.body:
                    if not isinstance(substatement, ast.FunctionDefNode):
                        assert False, "Only functions should appear in class body"

                    self.index_statement(def_id, substatement)

            case ast.UseNode() | ast.UseAsNode():
                def_id = self.def_id(resolution.DefKind.USE, statement.id)
                self.asg_ctx.record_parent(def_id, parent_id)

                for substatement in statement.body:
                    if not isinstance(substatement, ast.FunctionDefNode):
                        assert False, "Only functions should appear in class body"

                    self.index_statement(def_id, substatement)

                self.index_type_parameters(parent_id, def_id, statement.type)
                if isinstance(statement, ast.UseAsNode):
                    self.index_type_parameters(parent_id, def_id, statement.type_class)

            case ast.ForNode():
                self.index_block(parent_id, statement.body)

            case ast.WhileNode():
                self.index_block(parent_id, statement.body)

            case ast.IfNode():
                self.index_block(parent_id, statement.body)
                if statement.else_statement is not None:
                    self.index_block(parent_id, statement.else_statement.body)

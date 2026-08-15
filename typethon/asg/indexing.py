from __future__ import annotations

import typing

import attr

from ..syntax.typethon import ast
from . import resolution

if typing.TYPE_CHECKING:
    from . import asg


@attr.s(kw_only=True, slots=True)
class TypeParamIndex:
    parameters: dict[str, asg.DefinitionId] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class IndexedEntry:
    own_index: DefIndex | None = attr.ib(default=None)
    result: resolution.DefResult = attr.ib()


@attr.s(kw_only=True, slots=True)
class DefIndex:
    parent: DefIndex | None = attr.ib()
    def_id: asg.DefinitionId | None = attr.ib()
    node_id: ast.NodeId = attr.ib()
    entries: dict[str, IndexedEntry] = attr.ib(factory=dict)

    def get_def_id(self) -> asg.DefinitionId:
        if self.def_id is not None:
            return self.def_id

        assert self.parent is not None
        return self.parent.get_def_id()


# In general, the strategy for type definitions is as follows:
# If a struct/tuple/alias is created in a type definition, the node
# for the type is is stored as the type definition statement.
# The node id for the type expression within the statement is merely
# mapped to the definition id. In other words, the statement and
# expression node ids are both mapped to the resulting definition, but
# when retrieving the node from the def id, it will always give the
# statement.
# ...
# type Type = { ... }
# ^^^ (1)     ^^^ (2) [ AST - node ids ]
# ^^^^^^^^^^^^^^^ (3) [ ASG - def ids ]
# node_defs => { 3 : TypeDefinitionNode("Type", 1) }
# def_nodes => { 1: 3, 2: 3 }
# ...
# Within a sum variant, everything receives its own def id:
# ...
# type Sum = Var1 of { ... } | Var2 of { ... }
# ^^^ (1)    ^ (2)   ^^^^ (3)  ^ (4)   ^^^^ (5) [ AST - node ids ]
# ^^^ (6)    ^ (7)   ^^^^ (8)  ^ (9)   ^^^^ (10) [ ASG - def ids ]
# node_defs => { 6 : SumTypeNode("Sum", 1), 7: SumTypeVariantNode("Var1", 2), 8: StructDefNode(..., 3) }
# def_nodes => { 6: 1, 7: 2, 8: 3, 9: 4, 10: 5 }
# def_parents [ def id: def id ] => { 2: 1, 3: 2, 4: 1, 5: 4 }
# ...
# For ASG there are two cases where a struct/tuple is nominal:
#   1) when the def id is mapped to a type definition node
#   2) when the parent is a sum variant
# In all other cases, the definition assumes the name "<anonymous struct/tuple>"
# and it's type is structural. The type system will encode structural types
# as meaning: compatible with any other structural type of the same form.


@attr.s(kw_only=True, slots=True)
class DefIndexing:
    asg_ctx: asg.AsgContext = attr.ib()
    def_params: dict[asg.DefinitionId, TypeParamIndex] = attr.ib(factory=dict)
    def_kinds: dict[asg.DefinitionId, resolution.DefKind] = attr.ib(factory=dict)
    def_indexes: dict[asg.DefinitionId, DefIndex] = attr.ib(factory=dict)
    block_indexes: dict[ast.NodeId, DefIndex] = attr.ib(factory=dict)

    def def_index(self, node_id: ast.NodeId, parent: DefIndex | None) -> DefIndex:
        def_id = self.asg_ctx.def_nodes.get(node_id)
        index = DefIndex(parent=parent, def_id=def_id, node_id=node_id)

        if def_id is not None:
            self.def_indexes[def_id] = index
        else:
            self.block_indexes[node_id] = index

        return index

    def def_result(self, def_id: asg.DefinitionId) -> resolution.DefResult:
        return resolution.DefResult(kind=self.def_kinds[def_id], def_id=def_id)

    def def_id(self, def_kind: resolution.DefKind, node: ast.Node) -> asg.DefinitionId:
        def_id = self.asg_ctx.def_id(node)
        self.def_kinds[def_id] = def_kind
        return def_id

    def search_for_parameter(
        self,
        def_id: asg.DefinitionId,
        parameter: ast.TypeParameterNode,
    ) -> asg.DefinitionId | None:
        own_params = self.def_params.get(def_id)
        parent_id = self.asg_ctx.parent_id(def_id)

        use_parent = parent_id is not None and self.def_kinds[parent_id] in (
            resolution.DefKind.STRUCT,
            resolution.DefKind.TUPLE,
            resolution.DefKind.SUM,
            resolution.DefKind.USE,
            resolution.DefKind.CLASS,
            resolution.DefKind.FIELD,
        )
        if own_params is not None:
            result = own_params.parameters.get(parameter.name)
            if result is not None:
                return result

        if use_parent:
            return self.search_for_parameter(parent_id, parameter)

    def get_defining_index(
        self,
        def_id: asg.DefinitionId,
    ) -> TypeParamIndex:
        # This function is called after searching for the parameter.
        # We must now define it on the narrowest possible parameter index.
        parent_id = self.asg_ctx.parent_id(def_id)
        def_kind = self.def_kinds[def_id]

        if def_kind in (
            resolution.DefKind.SUM,
            resolution.DefKind.USE,
            resolution.DefKind.CLASS,
            resolution.DefKind.FUNCTION,
        ) or parent_id is None:
            # Unambiguously defined on this definition
            param_index = self.def_params.get(def_id)
            if param_index is None:
                param_index = TypeParamIndex()
                self.def_params[def_id] = param_index

            return param_index

        elif def_kind in (resolution.DefKind.FIELD, resolution.DefKind.VARIANT):
            # Unambiguously defined on the outer definition
            return self.get_defining_index(parent_id)

        elif def_kind in (resolution.DefKind.STRUCT, resolution.DefKind.TUPLE, resolution.DefKind.NEW_TYPE):
            parent_kind = self.def_kinds[parent_id]
            # We are a nested type and cannot own the parameter
            if parent_kind in (
                resolution.DefKind.STRUCT,
                resolution.DefKind.TUPLE,
                resolution.DefKind.FIELD,
                resolution.DefKind.VARIANT,
            ):
                return self.get_defining_index(parent_id)

            param_index = self.def_params.get(def_id)
            if param_index is None:
                param_index = TypeParamIndex()
                self.def_params[def_id] = param_index

            return param_index

        # Probably missing some edge cases
        assert False, f"{self.asg_ctx.node_for_def_id(def_id)!r}"

    def index_type_expression(
        self,
        def_id: asg.DefinitionId,
        type_expression: ast.TypeExpressionNode,
    ) -> None:
        for subexpression in ast.walk_type_expressions(type_expression):
            match subexpression:
                case ast.StructTypeNode() if (
                    subexpression.id not in self.asg_ctx.def_nodes
                ):
                    struct_def_id = self.index_struct(def_id, subexpression)
                    self.asg_ctx.record_parent(struct_def_id, def_id)
                case ast.TupleTypeNode() if (
                    subexpression.id not in self.asg_ctx.def_nodes
                ):
                    tuple_def_id = self.index_tuple(def_id, subexpression)
                    self.asg_ctx.record_parent(tuple_def_id, def_id)

            if not isinstance(subexpression, ast.TypeParameterNode):
                continue

            param_def_id = self.search_for_parameter(def_id, subexpression)
            if param_def_id is None:
                param_def_id = self.def_id(
                    resolution.DefKind.TYPE_PARAMETER, subexpression
                )

                param_index = self.get_defining_index(def_id)
                param_index.parameters[subexpression.name] = param_def_id

            self.asg_ctx.record_node(param_def_id, subexpression.id)

    def index_struct(self, parent_id: asg.DefinitionId, node: ast.StructTypeNode | ast.TypeDefinitionNode) -> asg.DefinitionId:
        # Struct definition may point to struct type or type definition ast
        if isinstance(node, ast.TypeDefinitionNode):
            struct = node.type
            assert isinstance(struct, ast.StructTypeNode)
        else:
            struct = node

        def_id = self.def_id(resolution.DefKind.STRUCT, node)
        self.asg_ctx.record_parent(def_id, parent_id)
        self.asg_ctx.record_node(def_id, struct.id)
        # type T = { ... }
        # ^^^^^^   ^^^^^^^ Node ids both point to the same def id.

        for field in struct.fields:
            field_def_id = self.def_id(resolution.DefKind.FIELD, field)
            self.asg_ctx.record_parent(field_def_id, def_id)
            self.index_type_expression(field_def_id, field.type)

        return def_id

    def index_tuple(self, parent_id: asg.DefinitionId, node: ast.TupleTypeNode | ast.TypeDefinitionNode) -> asg.DefinitionId:
        # Tuple definition may point to struct type or type definition ast
        if isinstance(node, ast.TypeDefinitionNode):
            tuple = node.type
            assert isinstance(tuple, ast.TupleTypeNode)
        else:
            tuple = node

        def_id = self.def_id(resolution.DefKind.TUPLE, node)
        self.asg_ctx.record_parent(def_id, parent_id)
        self.asg_ctx.record_node(def_id, tuple.id)

        for elt in tuple.elts:
            elt_def_id = self.def_id(resolution.DefKind.FIELD, elt)
            self.asg_ctx.record_parent(elt_def_id, def_id)
            self.index_type_expression(elt_def_id, elt.type)

        return def_id

    def index_block(self, index: DefIndex, statements: list[ast.StatementNode]) -> None:
        for statement in statements:
            self.index_statement(index, statement)

    def index_function(
        self, index: DefIndex, statement: ast.FunctionDefNode
    ) -> tuple[asg.DefinitionId, DefIndex | None]:
        def_id = self.def_id(resolution.DefKind.FUNCTION, statement)
        parent_id = index.get_def_id()
        self.asg_ctx.record_parent(def_id, parent_id)

        for parameter in statement.parameters:
            self.index_type_expression(def_id, parameter.annotation)

        self.index_type_expression(def_id, statement.returns)

        subindex = None
        if statement.body is not None:
            subindex = self.def_index(statement.id, index)
            self.index_block(subindex, statement.body)

        return def_id, subindex

    def index_statement(
        self,
        index: DefIndex,
        statement: ast.StatementNode,
    ) -> None:
        # The index is the DefIndex this statement resides in.
        # index.get_def_id is the parent def id.
        parent_id = index.get_def_id()

        match statement:
            case ast.TypeDefinitionNode():
                match statement.type:
                    case ast.StructTypeNode():
                        def_id = self.index_struct(parent_id, statement)
                    case ast.TupleTypeNode():
                        def_id = self.index_tuple(parent_id, statement)
                    case _:
                        # NEW_TYPE node may point to type definition statement
                        def_id = self.def_id(
                            resolution.DefKind.NEW_TYPE, statement
                        )
                        self.asg_ctx.record_parent(def_id, parent_id)
                        self.index_type_expression(def_id, statement.type)

                index.entries[statement.name] = IndexedEntry(
                    result=self.def_result(def_id)
                )

            case ast.SumTypeNode():
                def_id = self.def_id(resolution.DefKind.SUM, statement)
                self.asg_ctx.record_parent(def_id, parent_id)

                subindex = self.def_index(statement.id, index)
                index.entries[statement.name] = IndexedEntry(
                    own_index=subindex, result=self.def_result(def_id)
                )

                for variant in statement.variants:
                    variant_def_id = self.def_id(resolution.DefKind.VARIANT, variant)
                    self.asg_ctx.record_parent(variant_def_id, def_id)
                    subindex.entries[variant.name] = IndexedEntry(
                        result=self.def_result(variant_def_id)
                    )

                    type_def_id = None
                    match variant.type:
                        case ast.StructTypeNode():
                            type_def_id = self.index_struct(variant_def_id, variant.type)
                        case ast.TupleTypeNode():
                            type_def_id = self.index_tuple(variant_def_id, variant.type)
                        case _:
                            if variant.type is not None:
                                type_def_id = self.def_id(
                                    resolution.DefKind.NEW_TYPE, variant.type
                                )
                                self.asg_ctx.record_parent(type_def_id, variant_def_id)
                                self.index_type_expression(type_def_id, variant.type)

                    # type T = ( V1 of { ... } | V2 of { ... } )
                    # ^^^^^^     ^^    ^^^^^^^
                    # 1 is a sum, 2 is a variant, 3 is a struct; all with different def ids

            case ast.FunctionDefNode():
                def_id, subindex = self.index_function(index, statement)
                index.entries[statement.name] = IndexedEntry(
                    own_index=subindex, result=self.def_result(def_id)
                )

            case ast.ClassDefNode():
                def_id = self.def_id(resolution.DefKind.CLASS, statement)
                parent_id = index.get_def_id()
                self.asg_ctx.record_parent(def_id, parent_id)

                if statement.parameters:
                    param_index = TypeParamIndex()
                    self.def_params[def_id] = param_index

                    for type_parameter in statement.parameters:
                        param_def_id = self.def_id(
                            resolution.DefKind.TYPE_PARAMETER, type_parameter
                        )
                        param_index.parameters[type_parameter.name] = param_def_id

                subindex = self.def_index(statement.id, index)
                index.entries[statement.name] = IndexedEntry(
                    own_index=subindex, result=self.def_result(def_id)
                )

                for substatement in statement.body:
                    if not isinstance(substatement, ast.FunctionDefNode):
                        assert False, "Only functions should appear in class body"

                    self.index_statement(subindex, substatement)

            case ast.UseNode() | ast.UseAsNode():
                def_id = self.def_id(resolution.DefKind.USE, statement)
                parent_id = index.get_def_id()
                self.asg_ctx.record_parent(def_id, parent_id)

                for substatement in statement.body:
                    if not isinstance(substatement, ast.FunctionDefNode):
                        assert False, "Only functions should appear in class body"

                    function_def_id, subindex = self.index_function(index, substatement)
                    # TODO: These must go somewhere.
                    # I am mimicking Rust by using the outside index ("module" in Rust terms) as the parent
                    # for functions in use statements. In an impl block in Rust, the self path refers to
                    # the outside module. I don't know why but for now this is how it will be done.

                self.index_type_expression(def_id, statement.type)
                if isinstance(statement, ast.UseAsNode):
                    self.index_type_expression(def_id, statement.type_class)

            case ast.ForNode():
                subindex = self.def_index(statement.id, index)
                self.index_block(subindex, statement.body)

            case ast.WhileNode():
                subindex = self.def_index(statement.id, index)
                self.index_block(subindex, statement.body)

            case ast.IfNode():
                subindex = self.def_index(statement.id, index)
                self.index_block(subindex, statement.body)

                if statement.else_statement is not None:
                    subindex = self.def_index(statement.id, index)
                    self.index_block(subindex, statement.else_statement.body)

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

    def def_id(
        self, def_kind: resolution.DefKind, node: ast.Node
    ) -> asg.DefinitionId:
        def_id = self.asg_ctx.def_id(node)
        self.def_kinds[def_id] = def_kind
        return def_id

    def index_type_expression(
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
            match subexpression:
                case ast.StructTypeNode() if subexpression.id not in self.asg_ctx.def_nodes:
                    struct_def_id = self.index_struct(subexpression)
                    self.asg_ctx.record_parent(struct_def_id, def_id)
                case ast.TupleTypeNode() if subexpression.id not in self.asg_ctx.def_nodes:
                    tuple_def_id = self.index_tuple(subexpression)
                    self.asg_ctx.record_parent(tuple_def_id, def_id)

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
                    resolution.DefKind.TYPE_PARAMETER, subexpression
                )
                assert param_index is not None
                param_index.paremeters[subexpression.name] = param_def_id
                self.asg_ctx.record_parent(param_def_id, def_id)

            self.asg_ctx.record_node(param_def_id, subexpression.id)

    def index_struct(self, struct: ast.StructTypeNode) -> asg.DefinitionId:
        def_id = self.def_id(resolution.DefKind.STRUCT, struct)

        for field in struct.fields:
            field_def_id = self.def_id(resolution.DefKind.FIELD, field)
            self.asg_ctx.record_parent(field_def_id, def_id)

        return def_id

    def index_tuple(self, tuple: ast.TupleTypeNode) -> asg.DefinitionId:
        def_id = self.def_id(resolution.DefKind.TUPLE, tuple)

        for elt in tuple.elts:
            elt_def_id = self.def_id(resolution.DefKind.FIELD, elt)
            self.asg_ctx.record_parent(elt_def_id, def_id)

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
            self.index_type_expression(parent_id, def_id, parameter.annotation)

        self.index_type_expression(parent_id, def_id, statement.returns)

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
        match statement:
            case ast.TypeDefinitionNode():
                match statement.type:
                    case ast.StructTypeNode():
                        def_id = self.index_struct(statement.type)
                    case ast.TupleTypeNode():
                        def_id = self.index_tuple(statement.type)
                    case _:
                        def_id = self.def_id(
                            resolution.DefKind.NEW_TYPE, statement.type
                        )

                index.entries[statement.name] = IndexedEntry(
                    result=self.def_result(def_id)
                )
                parent_id = index.get_def_id()
                self.asg_ctx.record_parent(def_id, parent_id)
                self.asg_ctx.record_node(def_id, statement.id)
                # type T = { ... }
                # ^^^^^^   ^^^^^^^ Node ids both point to the same def id.

                self.index_type_expression(parent_id, def_id, statement.type)

            case ast.SumTypeNode():
                def_id = self.def_id(resolution.DefKind.SUM, statement)
                parent_id = index.get_def_id()
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
                            type_def_id = self.index_struct(variant.type)
                        case ast.TupleTypeNode():
                            type_def_id = self.index_tuple(variant.type)
                        case _:
                            if variant.type is not None:
                                type_def_id = self.def_id(
                                    resolution.DefKind.NEW_TYPE, variant.type
                                )

                    if type_def_id is not None:
                        assert variant.type is not None
                        # type T = ( V1 of { ... } | V2 of { ... } )
                        # ^^^^^^     ^^    ^^^^^^^
                        # 1 is a sum, 2 is a variant, 3 is a struct; all with different def ids
                        self.asg_ctx.record_parent(type_def_id, variant_def_id)
                        self.index_type_expression(parent_id, def_id, variant.type)
                        # All type parameters belong to the sum, not the variant!

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
                        param_index.paremeters[type_parameter.name] = param_def_id

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

                self.index_type_expression(parent_id, def_id, statement.type)
                if isinstance(statement, ast.UseAsNode):
                    self.index_type_expression(parent_id, def_id, statement.type_class)

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

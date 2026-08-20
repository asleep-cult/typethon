import attr

from .. import asg
from . import typeinfo, types


@attr.s(kw_only=True, slots=True)
class InitializationStore:
    adts: dict[asg.DefinitionId, typeinfo.AdtInfo] = attr.ib(factory=dict)
    generics: dict[asg.DefinitionId, typeinfo.GenericsInfo] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class TypeInitializer:
    asg_ctx: asg.AsgContext = attr.ib(repr=False)
    store: InitializationStore = attr.ib()

    def lower_path_segment(
        self,
        def_id: asg.DefinitionId,
        segment: asg.PathSegment,
    ) -> types.Type | None:
        arguments: list[types.Type] = []
        for argument in segment.arguments:
            arguments.append(self.lower_path_expression(def_id, argument))

        match segment.result.kind:
            case asg.DefKind.CLASS:
                assert False, "Not implemented"
            case asg.DefKind.STRUCT | asg.DefKind.TUPLE | asg.DefKind.SUM | asg.DefKind.NEW_TYPE:
                info = self.store.adts[segment.result.def_id]
                return types.Adt(info=info, args=arguments)
            case asg.DefKind.VARIANT:
                assert False, "Variant is not usable in path expression"
            case asg.DefKind.FUNCTION:
                assert False, "Function is not usable in path expression"
            case asg.DefKind.TYPE_PARAMETER | asg.DefKind.FIELD | asg.DefKind.USE:
                assert False, f"{segment.result.kind} should not appear within a field"
            case asg.DefKind.MODULE:
                if arguments:
                    assert False, "Cannot parameterize this type"    

    def lower_path_expression(self, def_id: asg.DefinitionId, path_expression: asg.AsgPathExpression) -> types.Type:
        match path_expression:
            case asg.Path():
                result = None
                initial_segment = path_expression.segments[0]
                if isinstance(initial_segment, asg.ExpressionPathSegment):
                    if initial_segment.arguments:
                        # In future, HKT?: 't('u)
                        assert False, "Path expression should not have arguments"

                    result = self.lower_path_expression(def_id, initial_segment.expression)
                    segments = path_expression.segments[1:]
                else:
                    segments = path_expression.segments

                for segment in segments:
                    match segment:
                        case asg.PathSegment():
                            result = self.lower_path_segment(def_id, segment)
                        case asg.UnresolvedPathSegment():
                            ...
                        case asg.ExpressionPathSegment():
                            assert False, "Expression segment should onlt appear as first segment"

                    # TODO: When can/can't args leak into the next segment?

                if result is None:
                    assert False, f"Failed to find path result: {path_expression!r}"

                return result

            case asg.TypeParameterDef():
                generics = self.generics_of(def_id)
                index = generics.index_map[path_expression.def_id]
                return types.Parameter(name=path_expression.name, index=index)

            case asg.PathList():
                return types.List(elt=self.lower_path_expression(def_id, path_expression.elt))

            case asg.PathStruct():
                fields: dict[str, types.Type] = {}
                for name, field in path_expression.fields.items():
                    fields[name] = self.lower_path_expression(def_id, field)

                return types.Struct(fields=fields)

            case asg.PathTuple():
                return types.Tuple(
                    elts=[self.lower_path_expression(def_id, elt) for elt in path_expression.elts]
                )

    def get_identity_parameters(self, def_id: asg.DefinitionId) -> list[types.Parameter]:
        generics = self.generics_of(def_id)
        if generics.parent_id is None:
            return [
                types.Parameter(name=parameter.name, index=parameter.index)
                for parameter in generics.parameters
            ]

        parameters = self.get_identity_parameters(generics.parent_id)
        for parameter in generics.parameters:
            parameters.append(types.Parameter(name=parameter.name, index=parameter.index))

        return parameters

    def type_of(self, def_id: asg.DefinitionId) -> types.Binder:
        definition = self.asg_ctx.asg_lowering.lower_def(def_id)

        match definition:
            case asg.StructDef() | asg.TupleDef() | asg.SumDef():
                adt = self.store.adts[def_id]
                type = types.Adt(
                    info=adt,
                    args=self.get_identity_parameters(def_id),
                )
            case asg.StructField() | asg.TupleElt():
                type = self.lower_path_expression(def_id, definition.type)
            case asg.NewTypeDef():
                assert definition.type is not None
                type = self.lower_path_expression(def_id, definition.type)
            case asg.FunctionDef():
                assert False, "Not implemented"
            case _:
                assert False, f"{definition!r}"

        return types.Binder(type=type)

    def generics_of(self, def_id: asg.DefinitionId) -> typeinfo.GenericsInfo:
        if def_id in self.store.generics:
            return self.store.generics[def_id]

        parent_count = 0
        index_map: dict[asg.DefinitionId, int] = {}

        parent_id = self.asg_ctx.parent_id(def_id)
        parent_kind = self.asg_ctx.def_kind(parent_id) if parent_id is not None else None
        use_parent = parent_kind in (
            asg.DefKind.STRUCT,
            asg.DefKind.TUPLE,
            asg.DefKind.SUM,
            asg.DefKind.USE,
            asg.DefKind.CLASS,
            asg.DefKind.FIELD,
        )
        if use_parent:
            assert parent_id is not None
            parent_generics = self.generics_of(parent_id)
            parent_count = parent_generics.get_count()
            index_map |= parent_generics.index_map

        parameters: list[typeinfo.ParameterInfo] = []
        own_generics = self.asg_ctx.def_index.def_params.get(def_id)
        if own_generics is not None:
            for i, param_def_id in enumerate(own_generics.parameters.values()):
                parameter = self.asg_ctx.asg_lowering.lower_def(param_def_id)
                assert isinstance(parameter, asg.TypeParameterDef)

                parameter_type = typeinfo.ParameterInfo(
                    def_id=param_def_id,
                    name=parameter.name,
                    index=parent_count + i,
                )
                parameters.append(parameter_type)
                index_map[param_def_id] = i

        generics_info = typeinfo.GenericsInfo(
            def_id=def_id,
            parent_id=parent_id,
            parent_count=parent_count,
            parameters=parameters,
            index_map=index_map,
        )
        self.store.generics[def_id] = generics_info
        return generics_info

    def initialize_struct_variant(self, struct_def: asg.StructDef) -> typeinfo.AdtVariant:
        variant = typeinfo.AdtVariant(def_id=struct_def.def_id, name=struct_def.name)
        for field in struct_def.fields.values():
            variant.fields.append(typeinfo.VariantField(def_id=field.def_id, name=field.name))

        return variant

    def initialize_tuple_variant(self, tuple_def: asg.TupleDef) -> typeinfo.AdtVariant:
        variant = typeinfo.AdtVariant(def_id=tuple_def.def_id, name=tuple_def.name)
        for elt in tuple_def.elts:
            variant.fields.append(typeinfo.VariantField(def_id=elt.def_id, name=None))

        return variant

    def initialize_struct(self, struct_def: asg.StructDef) -> typeinfo.AdtInfo:
        variant = self.initialize_struct_variant(struct_def)
        adt = typeinfo.AdtInfo(def_id=struct_def.def_id, variants=[variant])

        self.store.adts[adt.def_id] = adt
        return adt

    def initialize_tuple(self, tuple_def: asg.TupleDef) -> typeinfo.AdtInfo:
        variant = self.initialize_tuple_variant(tuple_def)
        adt = typeinfo.AdtInfo(def_id=tuple_def.def_id, variants=[variant])

        self.store.adts[adt.def_id] = adt
        return adt

    def initialize_sum_type(self, sum_def: asg.SumDef) -> typeinfo.AdtInfo:
        adt = typeinfo.AdtInfo(def_id=sum_def.def_id)

        for variant in sum_def.variants.values():
            match variant.type:
                case asg.StructDef():
                    adt.variants.append(self.initialize_struct_variant(variant.type))
                case asg.TupleDef():
                    adt.variants.append(self.initialize_tuple_variant(variant.type))
                case asg.NewTypeDef():
                    adt.variants.append(typeinfo.AdtVariant(def_id=variant.type.def_id, name=variant.type.name))

        self.store.adts[adt.def_id] = adt
        return adt

    def initialize_types(self) -> None:
        for def_id, def_kind in self.asg_ctx.def_index.def_kinds.items():
            parent_id = self.asg_ctx.parent_id(def_id)
            if parent_id is None:
                continue

            parent_def_kind = self.asg_ctx.def_kind(parent_id)
            if parent_def_kind is not asg.DefKind.VARIANT:
                # Children of a sum def become variants of the adt, skip them
                match def_kind:
                    case asg.DefKind.STRUCT:
                        definition = self.asg_ctx.asg_lowering.lower_def(def_id)
                        assert isinstance(definition, asg.StructDef)
                        self.initialize_struct(definition)
                    case asg.DefKind.TUPLE:
                        definition = self.asg_ctx.asg_lowering.lower_def(def_id)
                        assert isinstance(definition, asg.TupleDef)
                        self.initialize_tuple(definition)
                    case asg.DefKind.SUM:
                        definition = self.asg_ctx.asg_lowering.lower_def(def_id)
                        assert isinstance(definition, asg.SumDef)
                        self.initialize_sum_type(definition)

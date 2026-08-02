import attr

from . import types
from .. import asg


@attr.s(kw_only=True, slots=True)
class TypeChecker:
    type_ctx: types.TypeContext = attr.ib()
    module: asg.ModuleDef = attr.ib()

    def create_types(self) -> None:
        for field in self.type_ctx.asg_ctx.fields.values():
            self.create_type_for_field(field)

    def create_type_for_field(self, field: asg.AsgField, *, is_declaration: bool = True) -> None:
        match field:
            case asg.StructDef():
                type = types.StructType(asg_id=field.id, name=field.name, is_declaration=is_declaration)
            case asg.TupleDef():
                type = types.TupleType(asg_id=field.id, name=field.name, is_declaration=is_declaration)
            case asg.SumDef():
                assert False, 'Not implemented'
            case asg.AliasDef():
                assert False, 'Not implemented'
            case asg.FunctionDef():
                type = types.FunctionType(asg_id=field.id, name=field.name)
            case asg.ClassDef():
                type = types.ClassType(asg_id=field.id, name=field.name)
            case asg.UseDef():
                assert False, 'Not implemented'
            case _:
                return

        self.type_ctx.types[field.id] = type
        if field.id in self.type_ctx.asg_ctx.generics:
            generics = self.type_ctx.asg_ctx.generics[field.id]
            assert isinstance(type, types.PolymorphicType)

            for name, parameter in generics.parameters.items():
                parameter = types.TypeParameter(asg_id=parameter.id, name=name)
                self.type_ctx.types[parameter.asg_id] = parameter
                type.parameters[name] = parameter

    def initialize_types(self) -> None:
        for field in self.type_ctx.asg_ctx.fields.values():
            self.initialize_type_fields(field)

    def initialize_type_fields(self, field: asg.AsgField) -> None:
        type = self.type_ctx.types.get(field.id)

        match field:
            case asg.StructDef():
                assert isinstance(type, types.StructType)
                for struct_field in field.fields:
                    type.fields[field.id] = self.evaluate_asg_type(field.fields[struct_field])

            case asg.TupleDef():
                assert isinstance(type, types.TupleType)
                for elt in field.elts:
                    type.elts.append(self.evaluate_asg_type(elt))

            case asg.FunctionDef():
                assert isinstance(type, types.FunctionType)
                for name, parameter in field.parameters.items():
                    if parameter != asg.INFERRED:
                        type.parameters[name] = self.evaluate_asg_type(parameter)
                    else:
                        type.parameters[name] = None

                if field.returns != asg.INFERRED:
                    type.returns = self.evaluate_asg_type(field.returns)

    def validate_path_segment(self, segment: asg.PathSegment) -> None:
        # TODO: Chck every segment result, evaluate its type, check if its polymorphic,
        # substitute type arguments, etc.
        ...

    def evaluate_asg_type(self, asg_type: asg.AsgType) -> types.Type:
        match asg_type:
            case asg.Path():
                for segment in asg_type.segments:
                    self.validate_path_segment(segment)

                result = asg_type.get_result()
                if isinstance(result, (asg.ModuleDef, asg.FunctionDef, asg.UseDef, asg.LocalDeclaration)):
                    assert False, f'{result!r} is not a valid type'

                return self.evaluate_asg_type(result)

            case asg.StructDef() | asg.TupleDef() | asg.SumDef() | asg.AliasDef():
                self.create_type_for_field(asg_type, is_declaration=False)
                return self.type_ctx.types[asg_type.id]

            case asg.ListType():
                elt = self.evaluate_asg_type(asg_type.elt)
                return types.ListType(asg_id=-1, elt=elt)

        if isinstance(asg_type, asg.AsgError):
            assert False, f"{asg_type!r}"

        if asg_type.id not in self.type_ctx.types:
            assert False, f"Cannot find type {asg_type!r}"

        return self.type_ctx.types[asg_type.id]

    def check_block(self, field: asg.ModuleDef | asg.FunctionDef, statements: list[asg.Statement]) -> None:
        for statement in statements:
            self.check_statement(field, statement)

    def check_statement(self, field: asg.ModuleDef | asg.FunctionDef, statement: asg.Statement) -> None:
        match statement:
            case asg.Declaration():
                ...
            case asg.For():
                ...
            case asg.While():
                ...
            case asg.If():
                ...
            case asg.Assignment():
                ...
            case asg.AugAssignment():
                ...
            case asg.Return():
                assert isinstance(field, asg.FunctionDef)

                function = self.type_ctx.types[field.id]
                assert isinstance(function, types.FunctionType)

                if statement.value is not None:
                    type = self.check_expression(statement.value)
                else:
                    assert False

                if not self.unify(type, function.returns, {}):
                    assert False, f'{type} and {function.returns}'
            case asg.Break():
                ...
            case asg.Continue():
                ...
            case asg.Expr():
                self.check_expression(statement.expr)

    def check_expression(self, expression: asg.Expression) -> types.Type:
        ...

    def unify(self, type1: types.Type, type2: types.Type, substitution: dict[str, types.Type]) -> bool:
        if isinstance(type1, types.TypeParameter):
            type1 = type1.resolve(substitution)

        if isinstance(type2, types.TypeParameter):
            type2 = type2.resolve(substitution)

        if type1.id == type2.id:
            return True

        if isinstance(type1, types.TypeParameter):
            if type2.has_type_parameter(type1, substitution):
                return False

            substitution[type1.id] = type2
            return True

        if isinstance(type2.id, types.TypeParameter):
            return self.unify(type2, type1, substitution)

        if isinstance(type1, types.PolymorphicType) and isinstance(type2, types.PolymorphicType):
            if (
                len(type1.parameters) != len(type2.parameters)
                or type1.get_parent_id() != type2.get_parent_id()
            ):
                return False

            for parameter1, parameter2 in zip(type1.parameters, type2.parameters):
                if not self.unify(parameter1, parameter2, substitution):
                    return False

        return False

    def check_module(self) -> None:
        self.create_types()
        self.initialize_types()

        if self.module.body is not None:
            self.check_block(self.module, self.module.body.statements)

        for field in self.type_ctx.asg_ctx.fields.values():
            if isinstance(field, asg.FunctionDef) and field.body is not None:
                self.check_block(field, field.body.statements)

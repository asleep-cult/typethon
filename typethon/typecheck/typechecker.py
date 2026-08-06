import attr

from . import types
from .. import asg


@attr.s(kw_only=True, slots=True)
class TypeChecker:
    type_ctx: types.TypeContext = attr.ib()
    module: asg.ModuleDef = attr.ib()

    def get_asg_fields(self) -> dict[int, asg.AsgField]:
        return self.type_ctx.asg_ctx.fields

    def get_asg_generics(self) -> dict[int, asg.Generics]:
        return self.type_ctx.asg_ctx.generics

    def create_types(self) -> None:
        for field in self.get_asg_fields().values():
            self.create_type_for_field(field)

    def create_type_for_field(self, field: asg.AsgField) -> None:
        match field:
            case asg.StructDef():
                type = types.StructType(asg_id=field.id, name=field.name, is_declaration=field.is_declaration)
            case asg.TupleDef():
                type = types.TupleType(asg_id=field.id, name=field.name, is_declaration=field.is_declaration)
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

        generics = self.get_asg_generics()
        if field.id in generics:
            assert isinstance(type, types.PolymorphicType)

            for parameter_name, parameter in generics[field.id].parameters.items():
                parameter = types.TypeParameter(asg_id=parameter.id, name=parameter_name)
                self.type_ctx.types[parameter.asg_id] = parameter
                type.parameters[parameter_name] = parameter

    def initialize_types(self) -> None:
        for field in self.get_asg_fields().values():
            self.initialize_type(field)

    def initialize_type(self, field: asg.AsgField) -> None:
        type = self.type_ctx.types.get(field.id)

        match field:
            case asg.StructDef():
                assert isinstance(type, types.StructType)
                for field_name in field.fields:
                    type.fields[field.id] = self.get_type_for_field(field.fields[field_name])

            case asg.TupleDef():
                assert isinstance(type, types.TupleType)
                for elt in field.elts:
                    type.elts.append(self.get_type_for_field(elt))

            case asg.FunctionDef():
                assert isinstance(type, types.FunctionType)
                for parameter_name, parameter in field.parameters.items():
                    if parameter != asg.INFERRED:
                        type.parameters[parameter_name] = self.get_type_for_field(parameter)
                    else:
                        type.parameters[parameter_name] = None

                if field.returns != asg.INFERRED:
                    type.returns = self.get_type_for_field(field.returns)

    def validate_path_segment(self, segment: asg.PathSegment) -> None:
        # TODO: Chck every segment result, evaluate its type, check if its polymorphic,
        # substitute type arguments, etc.
        ...

    def get_type_for_field(self, field: asg.AsgType) -> types.Type:
        if isinstance(field, asg.Path):
            for segment in field.segments:
                self.validate_path_segment(segment)

            path_result = field.get_result()
            if isinstance(path_result, (asg.FunctionDef, asg.LocalDeclaration)):
                assert False, f'{path_result!r} is not a valid type'

            field = path_result

        match field:
            case asg.AsgError():
                assert False, f'{field!r}'
            case asg.ListType():
                elt = self.get_type_for_field(field.elt)
                return types.ListType(asg_id=-1, elt=elt)
            case _:
                result = field

        if result.id in self.type_ctx.types:
            return self.type_ctx.types[result.id]

        if isinstance(result, asg.TypeParameter):
            assert False, f'Failed to initialize type parameter {result!r}'

        return self.create_type_for_field(result)

    def check_code(self, field: asg.ModuleDef | asg.FunctionDef) -> None:
        if field.body is not None:
            substitutions: dict[int, types.Type] = {}
            type_environment: dict[int, types.Type] = {}

            if isinstance(field, asg.FunctionDef):
                function_type = self.type_ctx.types[field.id]
                assert isinstance(function_type, types.FunctionType)

                for name, declaration in field.parameter_declarations.items():
                    type = function_type.parameters[name]
                    assert type is not None
                    type_environment[declaration.id] = type

            for statement in field.body.statements:
                self.check_statement(field, statement, substitutions, type_environment)

    def check_statement(
        self,
        field: asg.ModuleDef | asg.FunctionDef,
        statement: asg.Statement,
        type_substitutions: dict[int, types.Type],
        type_environment: dict[int, types.Type],
    ) -> None:
        match statement:
            case asg.Declaration():
                if statement.type is not None:
                    type = self.get_type_for_field(statement.type)

                    if statement.value is not None:
                        value_type = self.synthesize_expression(statement.value, type_environment)
                        if not self.unify(type, value_type, type_substitutions):
                            assert False, f'Assignment type and value are incompatible {type} != {value_type}'
                else:
                    assert statement.value is not None
                    type = self.synthesize_expression(statement.value, type_environment)

                type_environment[statement.local_declaration.id] = type
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
                if not isinstance(field, asg.FunctionDef):
                    assert False, 'Return only valid in function'

                function = self.type_ctx.types[field.id]
                assert isinstance(function, types.FunctionType)

                if statement.value is not None:
                    type = self.synthesize_expression(statement.value, type_environment)
                else:
                    assert False

                if not self.unify(type, function.returns, type_substitutions):
                    assert False, f'{type} and {function.returns}'
            case asg.Break():
                ...
            case asg.Continue():
                ...
            case asg.Expr():
                self.synthesize_expression(statement.expr, type_environment)

    def synthesize_expression(self, expression: asg.Expression, type_environment: dict[int, types.Type]) -> types.Type:
        """
        CoPath
        | Annotated
        | BoolOp
        | BinaryOp
        | UnaryOp
        | Compare
        | Call
        | Integer
        | Float
        | Complex
        | String
        | Constant
        | Attribute
        | Subscript
        | Struct
        | Tuple
        | List
        | Slice
        """
        match expression:
            case asg.CoPath():
                result = expression.path.get_result()
                print(result)
                assert isinstance(result, asg.LocalDeclaration)
                return type_environment[result.id]

    def unify(self, type1: types.Type, type2: types.Type, substitutions: dict[int, types.Type]) -> bool:
        if isinstance(type1, types.TypeParameter):
            type1 = type1.resolve(substitutions)

        if isinstance(type2, types.TypeParameter):
            type2 = type2.resolve(substitutions)

        if type1.id == type2.id:
            return True

        if isinstance(type1, types.TypeParameter):
            if type2.has_type_parameter(type1, substitutions):
                return False

            substitutions[type1.id] = type2
            return True

        if isinstance(type2, types.TypeParameter):
            return self.unify(type2, type1, substitutions)

        if isinstance(type1, types.PolymorphicType) and isinstance(type2, types.PolymorphicType):
            if (
                len(type1.parameters) != len(type2.parameters)
                or type1.get_parent_id() != type2.get_parent_id()
            ):
                return False

            for parameter1, parameter2 in zip(type1.parameters, type2.parameters):
                if not self.unify(parameter1, parameter2, substitutions):
                    return False

        return False

    def check_module(self) -> None:
        self.create_types()
        self.initialize_types()

        self.check_code(self.module)
        for field in self.get_asg_fields().values():
            if isinstance(field, asg.FunctionDef):
                self.check_code(field)

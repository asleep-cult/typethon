from __future__ import annotations

import typing

from . import types
from .context import AnalysisContext, ContextFlags
from ..syntax import ast
from .scope import Scope, Symbol, UNRESOLVED

T = typing.TypeVar('T', bound=ast.StatementNode)


class TypeAnalyzer:
    def __init__(
        self,
        module: ast.ModuleNode,
        *,
        ctx: typing.Optional[AnalysisContext] = None
    ) -> None:
        self.module = module
        self.module_scope = Scope()

        if ctx is None:
            ctx = AnalysisContext()

        self.ctx = ctx

    def initialize_types(
        self,
        scope: Scope,
        statements: typing.List[ast.StatementNode],
    ) -> None:
        # This function serves as the first pass, initializing all types
        # in the list of statements as a TypeParameter or PolymorphicType
        for statement in statements:
            if isinstance(statement, ast.FunctionDefNode):
                type = types.FunctionType(propagated=False, name=statement.name)
                parameters = self.walk_function_parameters(statement)

            elif isinstance(statement, ast.ClassDefNode):
                type = types.ClassType(propagated=False, name=statement.name)
                parameters = self.walk_class_parameters(statement)

            else:
                continue

            scope.add_symbol(Symbol(name=statement.name, type=type))
            child_scope = scope.create_child_scope(statement.name)

            for parameter in parameters:
                type_parameter = types.TypeParameter(name=parameter.name, owner=type)

                symbol = Symbol(name=parameter.name, type=type_parameter)
                child_scope.add_symbol(symbol)
                type.parameters.append(type_parameter)

            if statement.body is not None:
                self.initialize_types(child_scope, statement.body)

    def walk_function_parameters(
        self, statement: ast.FunctionDefNode,
    ) -> typing.Generator[ast.TypeParameterNode]:
        for parameter in statement.parameters:
            if parameter.annotation is not None:
                yield from self.walk_type_parameters(parameter.annotation)

    def walk_class_parameters(
        self, statement: ast.ClassDefNode
    ) -> typing.Generator[ast.TypeParameterNode]:
        assignments = self.filter_statements(statement.body, ast.AnnAssignNode)
        for assignment in assignments:
            yield from self.walk_type_parameters(assignment.annotation)

    def filter_statements(
        self,
        statements: typing.List[ast.StatementNode],
        type: typing.Type[T],
    ) -> typing.Iterator[T]:
        return (statement for statement in statements if isinstance(statement, type))

    def walk_type_parameters(
        self, expression: ast.TypeExpressionNode
    ) -> typing.Generator[ast.TypeParameterNode]:
        # TODO: Technically TypeAttributeNode.value and ast.TypeCallNode could
        # contain a type parameter (i.e |T|.x, |T|()), but as far as I know
        # (without thinking too hard about it), they are both meaningless
        # and should result in a syntax error
        match expression:
            case ast.TypeParameterNode():
                yield expression

                if expression.constraint is not None:
                    yield from self.walk_type_parameters(expression.constraint)

            case ast.TypeCallNode():
                for argument in expression.args:
                    yield from self.walk_type_parameters(argument)

            case ast.DictTypeNode():
                yield from self.walk_type_parameters(expression.key)
                yield from self.walk_type_parameters(expression.value)

            case ast.SetTypeNode():
                yield from self.walk_type_parameters(expression.elt)

            case ast.ListTypeNode():
                yield from self.walk_type_parameters(expression.elt)

    def propagate_types(
        self,
        scope: Scope,
        statements: typing.List[ast.StatementNode],
    ) -> None:
        # This function propagetes the fn_returns and fn_paramaters fields for
        # function types, and the cls_attributes and cls_functions fields for 
        # class types.
        for statement in statements:
            match statement:
                case ast.FunctionDefNode():
                    function = scope.get_symbol(statement.name).type
                    assert isinstance(function, types.FunctionType)

                    function_scope = scope.get_child_scope(statement.name)

                    for parameter in statement.parameters:
                        if parameter.annotation is None:
                            assert False, f'<Please provide annotation {parameter.name}>'

                        type = self.evaluate_annotation(
                            function_scope,
                            function,
                            parameter.annotation,
                        )
                        function.fn_parameters[parameter.name] = type

                    if statement.returns is None:
                        assert False, f'<Please provide return value>'

                    function.fn_returns = self.evaluate_annotation(
                        function_scope,
                        function,
                        statement.returns,
                    )
                    function.complete_propagation()

                    if statement.body is not None:
                        self.propagate_types(function_scope, statement.body)

                case ast.ClassDefNode():
                    cls = scope.get_symbol(statement.name).type
                    assert isinstance(cls, types.ClassType)

                    class_scope = scope.get_child_scope(statement.name)

                    assignments = self.filter_statements(statement.body, ast.AnnAssignNode)
                    for assignment in assignments:
                        type = self.evaluate_type_expression(
                            class_scope, assignment.annotation
                        )
                        cls.cls_attributes[assignment.target.value] = type

                    functions = self.filter_statements(statement.body, ast.FunctionDefNode)
                    for function in functions:
                        cls_function = class_scope.get_symbol(function.name).type
                        assert isinstance(cls_function, types.FunctionType)
                        cls.cls_functions[function.name] = cls_function

                    cls.complete_propagation()
                    self.propagate_types(class_scope, statement.body)

    def evaluate_annotation(
        self,
        scope: Scope,
        owner: types.AnalyzedType,
        expression: ast.TypeExpressionNode,
    ) -> types.AnalyzedType:
        type = self.evaluate_type_expression(scope, expression)

        if isinstance(type, types.PolymorphicType):
            # If a type is polymorphic over T, the caller is responsible
            # for defining the type of T.
            for parameter in type.uninitialized_parameters():
                if parameter.owner != owner:
                    assert False, f'<Use {type.name}(|T|)>'

        return type

    def evaluate_type_expression(
        self,
        scope: Scope,
        expression: ast.TypeExpressionNode,
    ) -> types.AnalyzedType:
        match expression:
            case ast.TypeNameNode():
                symbol = scope.get_symbol(expression.value)
                if symbol is UNRESOLVED:
                    assert False, f'<Unresolved symbol {expression.value}>'

                return symbol.type

            case ast.TypeParameterNode():
                symbol = scope.get_symbol(expression.name)
                assert isinstance(symbol.type, types.TypeParameter)

                if expression.constraint is not None:
                    symbol.type.constraint = self.evaluate_type_expression(
                        scope,
                        expression.constraint,
                    )

                return symbol.type

            case ast.TypeCallNode():
                callee = self.evaluate_type_expression(scope, expression.type)
                if not isinstance(callee, types.PolymorphicType):
                    assert False, f'<{callee} is not polymorphic>'

                if not callee.is_polymorphic():
                    assert False, f'<{callee} is already parameterized>'

                arguments = [self.evaluate_type_expression(scope, arg) for arg in expression.args]
                return callee.with_parameters(arguments)

            case ast.TypeAttributeNode():
                type = self.evaluate_type_expression(scope, expression.value)
                return type.access_attribute(expression.attr)

            case ast.DictTypeNode():
                key = self.evaluate_type_expression(scope, expression.key)
                value = self.evaluate_type_expression(scope, expression.value)

                return types.DICT.with_parameters([key, value])

            case ast.SetTypeNode():
                elt = self.evaluate_type_expression(scope, expression.elt)
                return types.SET.with_parameters([elt])

            case ast.ListTypeNode():
                elt = self.evaluate_type_expression(scope, expression.elt)
                return types.LIST.with_parameters([elt])

    def check_type_compatibility(
        self,
        type: types.AnalyzedType,
        value: types.AnalyzedType, 
    ) -> None:
        if not isinstance(value, types.InstanceOfType):
            # TODO: Make def f(x: type(|T|)), f(int) valid
            assert False, f'<Expected instance, got {value}>'

        match type:
            case types.TypeParameter():
                if isinstance(value.type, types.TypeParameter):
                    # XXX: Should this ever be possible?
                    assert type == value.type, f'Incompatible type parameters {type}, {value}'

                # TODO: Check for constraints
            case types.FunctionType():
                assert False, 'Not implemented'
            case types.ClassType():
                assert False, 'Not implemented'
            case types.PolymorphicType():
                assert (
                    isinstance(value.type, types.PolymorphicType)
                    and type.get_initial_type() == value.type.get_initial_type()
                )

                parameters = zip(type.parameters, value.type.parameters)
                for parameter_type, parameter_value in parameters:
                    self.check_type_compatibility(parameter_type, parameter_value)

            case unknown:
                assert False, f'Unknown type {unknown}'

    def analyze_types(
        self,
        scope: Scope,
        ctx: AnalysisContext,
        statements: typing.List[ast.StatementNode],
    ) -> None:
        for statement in statements:
            match statement:
                case ast.FunctionDefNode() if statement.body is not None:
                    function_scope = scope.get_child_scope(statement.name)
                    function = scope.get_symbol(statement.name).type
                    assert (
                        isinstance(function, types.FunctionType)
                        and function.propagated
                    )

                    for name, type in function.fn_parameters.items():
                        instance = types.InstanceOfType(name=type.name, type=type)
                        symbol = Symbol(name=name, type=instance)
                        function_scope.add_symbol(symbol)

                    inner_ctx = ctx.create_inner_context(function)
                    inner_ctx.flags |= ContextFlags.ALLOW_RETURN
                    self.analyze_types(function_scope, inner_ctx, statement.body)

                case ast.ClassDefNode():
                    class_scope = scope.get_child_scope(statement.name)
                    cls = scope.get_symbol(statement.name).type
                    assert (
                        isinstance(cls, types.ClassType)
                        and cls.propagated
                    )

                    inner_ctx = ctx.create_inner_context(cls)
                    self.analyze_types(class_scope, inner_ctx, statement.body)

                case ast.ReturnNode():
                    if not ctx.flags & ContextFlags.ALLOW_RETURN:
                        assert False, '<Return is not valid in this context>'

                    if statement.value is not None:
                        type = self.analyze_type(scope, ctx, statement.value)
                        if not isinstance(ctx.outer_type, types.FunctionType):
                            assert False, '<unreachable>'

                        self.check_type_compatibility(ctx.outer_type.fn_returns, type)
                        ctx.return_hook(type, statement)

                case ast.AssignNode():
                    type = self.analyze_type(scope, ctx, statement.value)
                    if not isinstance(type, types.InstanceOfType):
                        assert False, f'<Cannot asssign {type}, did you mean {type}()>'

                    self.analyze_assignment(scope, type, statement.targets)
                    ctx.assign_hook(type, statement)

                case ast.ExprNode():
                    # The expression is unused
                    type = self.analyze_type(scope, ctx, statement.expr)
                    ctx.expr_hook(type, statement)

    def analyze_assignment(
        self,
        scope: Scope,
        value: types.InstanceOfType,
        targets: typing.List[ast.ExpressionNode],
    ) -> None:
        for target in targets:
            if not isinstance(target, ast.NameNode):
                # TODO: Allow unpacking, the parser needs fixing here as well
                assert False, 'Non-variable assignment implemented'

            # TODO: check for type coherency
            scope.add_symbol(Symbol(name=target.value, type=value))

    def analyze_type(
        self,
        scope: Scope,
        ctx: AnalysisContext,
        expression: ast.ExpressionNode,
    ) -> types.AnalyzedType:
        match expression:
            case ast.BinaryOpNode():
                left = self.analyze_type(scope, ctx, expression.left)
                right = self.analyze_type(scope, ctx, expression.right)
                assert left is right # TODO: check for type coherency

                ctx.binary_op_hook(left, expression)
                return left

            case ast.NameNode():
                symbol = scope.get_symbol(expression.value)
                if symbol is UNRESOLVED:
                    assert False, f'<{symbol.name} is unresolved>'

                # TODO: We will probably need to add InstanceOfType
                # because right now we cannot differentiate betweeen
                # something def f(x: |T|) -> T: return T / return x
                ctx.name_hook(symbol.type, expression)
                return symbol.type
            # XXX: I don't know if constants should be handled like this
            case ast.IntegerNode():
                type = types.IntegerConstantType(name='<const int>', value=expression.value)
                ctx.constant_hook(type, expression)
                return type

            case ast.FloatNode():
                type = types.FloatConstantType(name='<const float>', value=expression.value)
                ctx.constant_hook(type, expression)
                return type

            case ast.ComplexNode():
                type = types.ComplexConstantType(name='<const complex>', value=expression.value)
                ctx.constant_hook(type, expression)
                return type

            case ast.StringNode():
                type = types.StringConstantType(name='<const str>', value=expression.value)
                ctx.constant_hook(type, expression)
                return type

            case ast.CallNode():
                function = self.analyze_type(scope, ctx, expression.func)
                if isinstance(function, types.FunctionType):
                    type = self.analyze_function_call(scope, function, expression)
                    ctx.call_hook(type, expression)
                    return type

        assert False, f'<Unable to determine type of {expression}>'

    def analyze_function_call(
        self,
        scope: Scope,
        function: types.FunctionType,
        node: ast.CallNode,
    ) -> types.AnalyzedType:
        return function.fn_returns

    def analyze_module(self) -> None:
        self.initialize_types(self.module_scope, self.module.body)
        self.propagate_types(self.module_scope, self.module.body)
        self.analyze_types(self.module_scope, self.ctx, self.module.body)

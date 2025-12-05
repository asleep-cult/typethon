from __future__ import annotations

import typing

from . import types
from ..syntax import ast
from .scope import Scope, Symbol, UNRESOLVED


class TypeAnalyzer:
    def __init__(self, module: ast.ModuleNode) -> None:
        self.module = module
        self.module_scope = Scope()

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
                parameters = self.get_function_parameters(statement)

            elif isinstance(statement, ast.ClassDefNode):
                type = types.ClassType(propagated=False, name=statement.name)
                parameters = self.get_class_parameters(statement)

            else:
                continue

            scope.add_symbol(Symbol(name=statement.name, type=type))
            child_scope = scope.create_child_scope(statement.name)

            for parameter in parameters:
                type_parameter = types.TypeParameter(name=parameter.name, owner=type)

                child_scope.add_symbol(
                    Symbol(name=parameter.name, type=type_parameter)
                )
                type.parameters.append(type_parameter)

            if statement.body is not None:
                self.initialize_types(child_scope, statement.body)

    def get_function_parameters(
        self, statement: ast.FunctionDefNode,
    ) -> typing.List[ast.TypeParameterNode]:
        parameters: typing.List[ast.TypeParameterNode] = []

        for parameter in statement.parameters:
            if parameter.annotation is not None:
                parameters.extend(
                    self.walk_type_parameters(parameter.annotation)
                )

        return parameters

    def get_class_parameters(
        self, statement: ast.ClassDefNode
    ) -> typing.List[ast.TypeParameterNode]:
        parameters: typing.List[ast.TypeParameterNode] = []

        for node in statement.body:
            if isinstance(node, ast.AnnAssignNode):
                parameters.extend(
                    self.walk_type_parameters(node.annotation)
                )

        return parameters

    def walk_type_parameters(
        self, expression: ast.TypeExpressionNode
    ) -> typing.Generator[ast.TypeParameterNode]:
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
                        function.fn_parameters.append(type)

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
                if parameter.owner is not owner:
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

    def analyze_module(self) -> None:
        self.initialize_types(self.module_scope, self.module.body)
        self.propagate_types(self.module_scope, self.module.body)

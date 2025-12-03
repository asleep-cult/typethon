from __future__ import annotations

import typing

from . import types
from ..syntax import ast
from .scope import Scope, Symbol

class TypeAnalyzer:
    def __init__(self, module: ast.ModuleNode) -> None:
        self.module = module
        self.module_scope = Scope()

    def evaluate_type_expression(
        self,
        scope: Scope,
        expression: ast.TypeExpressionNode,
    ) -> types.AnalyzedType:
        match expression:
            case ast.TypeNameNode():
                symbol = scope.get_symbol(expression.value)
                if symbol is None:
                    assert False, f'<{expression.value} is undefined>'

                return symbol.type

            case ast.TypeParameterNode():
                type = types.TypeParameter(name=expression.name)

                if expression.constraint is not None:
                    type.constraint = self.evaluate_type_expression(
                        scope,
                        expression.constraint,
                    )

                scope.add_symbol(Symbol(name=expression.name, type=type))
                return type

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

    def analyze_statement(self, scope: Scope, statement: ast.StatementNode) -> None:
        match statement:
            case ast.FunctionDefNode():
                function_scope = scope.create_child_scope()
                parameters: typing.List[types.AnalyzedType] = []

                for parameter in statement.parameters:
                    if parameter.annotation is None:
                        assert False, f'<Please provide annotation {parameter.name}>'

                    # We need to lazily evaluate the annotations
                    type = self.evaluate_type_expression(function_scope, parameter.annotation)
                    if isinstance(type, types.PolymorphicType):
                        if type.is_hollow():
                            assert False, f'<Use {type.name}(|T|)>'

                        parameters.extend(type.uninitialized_parameters())

                    function_scope.add_symbol(Symbol(name=parameter.name, type=type))

                if statement.returns is None:
                    assert False, f'<Please provide return value>'

                returns = self.evaluate_type_expression(function_scope, statement.returns)
                if statement.body is not None:
                    self.analyze_block(function_scope, statement.body)

                type = types.FunctionType(name=statement.name, parameters=parameters, returns=returns)
                print(function_scope.symbols)
                scope.add_symbol(Symbol(name=statement.name, type=type))

    def analyze_block(self, scope: Scope, statements: typing.List[ast.StatementNode]) -> None:
        for statement in statements:
            self.analyze_statement(scope, statement)

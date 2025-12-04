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
            match statement:
                case ast.FunctionDefNode():
                    function_scope = scope.create_child_scope(statement.name)

                    for parameter in statement.parameters:
                        if parameter.annotation is not None:
                            self.initialize_type_parameters(function_scope, parameter.annotation)

                    if statement.body is not None:
                        self.initialize_types(function_scope, statement.body)

                    parameters = [symbol.type for symbol in function_scope.get_all_symbols()]
                    # TODO: Use a new class called TypeReference then replace it,
                    # or just use FunctionType and mutate it 
                    type = types.PolymorphicType(name=statement.name, parameters=parameters)

                    scope.add_symbol(Symbol(name=statement.name, type=type))

                case ast.ClassDefNode():
                    class_scope = scope.create_child_scope(statement.name)
                    self.initialize_types(class_scope, statement.body)

                    parameters = [symbol.type for symbol in class_scope.get_all_symbols()]
                    type = types.PolymorphicType(name=statement.name, parameters=parameters)

                    scope.add_symbol(Symbol(name=statement.name, type=type))

                case ast.AnnAssignNode:
                    self.initialize_type_parameters(scope, statement.annotation)

    def initialize_type_parameters(
        self, scope: Scope, expression: ast.TypeExpressionNode
    ) -> None:
        match expression:
            case ast.TypeParameterNode():
                type = types.TypeParameter(name=expression.name)
                scope.add_symbol(Symbol(name=expression.name, type=type))

                if expression.constraint is not None:
                    self.initialize_type_parameters(scope, expression.constraint)

            case ast.TypeCallNode():
                for argument in expression.args:
                    self.initialize_type_parameters(scope, argument)

            case ast.DictTypeNode():
                self.initialize_type_parameters(scope, expression.key)
                self.initialize_type_parameters(scope, expression.value)

            case ast.SetTypeNode():
                self.initialize_type_parameters(scope, expression.elt)

            case ast.ListTypeNode():
                self.initialize_type_parameters(scope, expression.elt)

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

    def analyze_statement(self, scope: Scope, statement: ast.StatementNode) -> None:
        match statement:
            case ast.FunctionDefNode():
                function_scope = scope.get_child_scope(statement.name)

                parameters: typing.List[types.AnalyzedType] = []
                fn_parameters: typing.List[types.AnalyzedType] = []

                for parameter in statement.parameters:
                    if parameter.annotation is None:
                        assert False, f'<Please provide annotation {parameter.name}>'

                    type = self.evaluate_type_expression(function_scope, parameter.annotation)
                    fn_parameters.append(type)

                    if isinstance(type, types.PolymorphicType):
                        if type.is_hollow():
                            assert False, f'<Use {type.name}(|T|)>'

                        parameters.extend(type.uninitialized_parameters())

                if statement.returns is None:
                    assert False, f'<Please provide return value>'

                fn_returns = self.evaluate_type_expression(function_scope, statement.returns)
                if statement.body is not None:
                    self.analyze_block(function_scope, statement.body)

                type = types.FunctionType(
                    name=statement.name,
                    parameters=parameters, 
                    fn_parameters=fn_parameters,
                    fn_returns=fn_returns,
                )
                scope.add_symbol(Symbol(name=statement.name, type=type))

            case ast.ClassDefNode():
                initial_class = scope.get_symbol(statement.name)
                assert isinstance(initial_class.type, types.PolymorphicType)

                class_scope = scope.get_child_scope(statement.name)
                self.analyze_block(class_scope, statement.body)

                type = types.ClassType(
                    name=statement.name,
                    parameters=initial_class.type.parameters
                )
                scope.add_symbol(Symbol(name=statement.name, type=type))

    def analyze_block(self, scope: Scope, statements: typing.List[ast.StatementNode]) -> None:
        for statement in statements:
            self.analyze_statement(scope, statement)

    def analyze_module(self) -> None:
        self.initialize_types(self.module_scope, self.module.body)
        self.analyze_block(self.module_scope, self.module.body)

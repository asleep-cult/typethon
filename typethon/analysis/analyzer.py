from __future__ import annotations

import typing

from . import types
from ..syntax import ast
from .scope import Scope, Symbol, VariableSymbol, UNRESOLVED


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
        for node in statement.body:
            if isinstance(node, ast.AnnAssignNode):
                yield from self.walk_type_parameters(node.annotation)

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
        # function types. TODO: Add cls_attributes and cls_functions or use the scope?
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

    def analyze_types(
        self, scope: Scope, statements: typing.List[ast.StatementNode]
    ) -> None:
        # TODO: Add hooks so that the analyzer can be used to
        # generate an intermediate representation where every expression 
        # becomes associated with a type. (I think this will require
        # hooks to be associated with specific blocks containing
        # their own stack of types?)
        # i.e. for a function such as
        # def f(x: int) -> int: return x + x
        # the analyzer would create ExpressionHooks(type=FunctionType(name='f', ...))
        # and it would call
        #   hooks.load_name(NameNode('x'), int) Add int to stack
        #   hooks.load_name(NameNode('x'), int) Add int to stack
        #   hooks.binary_op(BinaryOp(...), int) Pop two types off the stack
        #       for the left and right hand types, then add int
        # Using this method, ExpressionHooks could create it's own typed
        # syntax tree (or whatever else it wants)
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
                        symbol = VariableSymbol(name=name, type=type)
                        function_scope.add_symbol(symbol)

                    self.analyze_types(function_scope, statement.body)

                case ast.ClassDefNode():
                    class_scope = scope.get_child_scope(statement.name)
                    self.analyze_types(class_scope, statement.body)

                case ast.ReturnNode():
                    if statement.value is not None:
                        type = self.analyze_type(scope, statement.value)
                        # TODO: check for type coherency

                case ast.AssignNode():
                    type = self.analyze_type(scope, statement.value)
                    self.analyze_assignment(scope, type, statement.targets)

                case ast.ExprNode():
                    # The expression is unused
                    self.analyze_type(scope, statement.expr)

    def analyze_assignment(
        self,
        scope: Scope,
        value: types.AnalyzedType,
        targets: typing.List[ast.ExpressionNode],
    ) -> None:
        for target in targets:
            if not isinstance(target, ast.NameNode):
                # TODO: Allow unpacking, the parser needs fixing here as well
                assert False, 'Non-variable assignment implemented'

            # TODO: check for type coherency
            scope.add_symbol(VariableSymbol(name=target.value, type=value))

    def analyze_type(
        self, scope: Scope, expression: ast.ExpressionNode
    ) -> types.AnalyzedType:
        match expression:
            case ast.NameNode:
                symbol = scope.get_symbol(expression.value)
                if symbol is UNRESOLVED:
                    assert False, f'<{symbol.name} is unresolved>'

                return symbol.type
            # XXX: I don't know if constants should be handled like this
            case ast.IntegerNode():
                return types.IntegerConstantType(
                    name='<const int>', value=expression.value
                )

            case ast.FloatNode():
                return types.FloatConstantType(
                    name='<const float>', value=expression.value
                )

            case ast.ComplexNode():
                return types.ComplexConstantType(
                    name='<const complex>', value=expression.value
                )

            case ast.StringNode():
                return types.StringConstantType(
                    name='<const str>', value=expression.value
                )

            case ast.CallNode():
                function = self.analyze_type(scope, expression.func)
                if isinstance(function, types.FunctionType):
                    return self.analyze_function_call(scope, function, expression)

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
        self.analyze_types(self.module_scope, self.module.body)

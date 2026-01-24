import attr
import typing

from . import types
from .resolution import SymbolNode
from ..diagnostics import DiagnosticReporter
from ..syntax.typethon import ast

TypedNode = typing.Union[
    SymbolNode,
    ast.TypeExpressionNode,
]


# TODO: What is the best way to represent polymorphic types and unbound
# parameters??? I will need to do more research
@attr.s(kw_only=True, slots=True)
class TypeInitializer:
    # The purpose of this is to evaluate all type expressions and initialize
    # all types defined in the module.
    diagnostics: DiagnosticReporter = attr.ib()
    module: ast.ModuleNode = attr.ib()
    resolved_symbols: typing.Dict[int, SymbolNode] = attr.ib()
    # We don't need to think about scoping at all because the SymbolResolver
    # maps every single NameNode to a SymbolNode (which may be a declaration,
    # or a class, or a function, or a type parameter, etc.)
    type_nodes: typing.Dict[int, types.Type] = attr.ib(factory=dict)
    # This contains every function, sum type, tuple/struct declaration, class,
    # type parameter, and the evaluated result of any type expression that isn't
    # inherently stored in another type, such as declaration annotations, and
    # the types for use statements. (Those are the only two as of now.)

    def create_struct_declaration(self, node: ast.TypeDeclarationNode) -> types.StructType:
        assert isinstance(node.type, ast.StructTypeNode)

        fields: typing.Dict[str, types.Type] = {}
        struct_type = types.StructType(name=node.name, is_declaration=True, fields=fields)
        self.type_nodes[node.id] = struct_type

        for field in node.type.fields:
            fields[field.name] = self.evaulate_type_expression(field.type)

        return struct_type

    def create_tuple_declaration(self, node: ast.TypeDeclarationNode) -> types.TupleType:
        assert isinstance(node.type, ast.TupleTypeNode)

        elts: typing.List[types.Type] = []
        tuple_type = types.TupleType(name=node.name, is_declaration=True, elts=elts)
        self.type_nodes[node.id] = tuple_type

        for elt in node.type.elts:
            elts.append(self.evaulate_type_expression(elt))

        return tuple_type

    def create_sum_type(self, node: ast.SumTypeNode) -> types.SumType:
        fields: typing.Dict[str, typing.Optional[types.DataType]] = {}
        sum_type = types.SumType(name=node.name, types=fields)
        self.type_nodes[node.id] = sum_type

        for field in node.fields:
            if field.data_type is not None:
                assert False, 'TODO!'
            else:
                fields[field.name] = None

        return sum_type

    def create_function(self, node: ast.FunctionDefNode) -> types.FunctionType:
        parameters: typing.Dict[str, types.Type] = {}
        function_type = types.FunctionType(
            name=node.name,
            parameters=parameters,
            returns=types.SingletonType.INVALID,
        )
        self.type_nodes[node.id] = function_type

        for parameter in node.parameters:
            parameters[parameter.name] = self.evaulate_type_expression(parameter.annotation)

        function_type.returns = self.evaulate_type_expression(node.returns)
        return function_type

    def create_type_class(self, node: ast.ClassDefNode) -> types.TypeClass:
        functions: typing.Dict[str, types.FunctionType] = {}
        type_class = types.TypeClass(name=node.name, functions=functions)
        self.type_nodes[node.id] = type_class

        for statement in node.body:
            if isinstance(statement, ast.FunctionDefNode):
                function = self.initialize_type_node(statement)
                assert isinstance(function, types.FunctionType)
                functions[statement.name] = function

        return type_class

    def create_type_parameter(self, node: ast.TypeParameterNode) -> types.TypeParameter:
        type_parameter = types.TypeParameter(name=node.name)
        self.type_nodes[node.id] = type_parameter
        return type_parameter

    def initialize_type_node(self, node: SymbolNode) -> types.Type:
        if node.id in self.type_nodes:
            return self.type_nodes[node.id]

        match node:
            case ast.SumTypeNode():
                return self.create_sum_type(node)
            case ast.TypeDeclarationNode():
                if isinstance(node.type, ast.StructTypeNode):
                    return self.create_struct_declaration(node)
                elif isinstance(node.type, ast.TupleTypeNode):
                    return self.create_tuple_declaration(node)
                else:
                    assert False, 'TODO!'
            case ast.TypeParameterNode():
                return self.create_type_parameter(node)
            case ast.ClassDefNode():
                return self.create_type_class(node)
            case ast.FunctionDefNode():
                return self.create_function(node)
            case (
                ast.DeclarationNode()
                | ast.FunctionParameterNode()
                | ast.LambdaParameterNode()
            ):
                assert False, f'Declaration nodes are not valid in this context'

    def evaulate_type_expression(
        self,
        type_expression: ast.TypeExpressionNode,
    ) -> types.Type:
        match type_expression:
            case ast.NameNode():
                if type_expression.id not in self.resolved_symbols:
                    return types.SingletonType.INVALID

                node = self.resolved_symbols[type_expression.id]
                return self.initialize_type_node(node)
            case ast.SelfTypeNode():
                return types.SingletonType.SELF
            case ast.TypeParameterNode():
                return self.initialize_type_node(type_expression)
            case ast.TypeCallNode():
                type = self.evaulate_type_expression(type_expression.type)
                assert False, 'TODO!'
            case ast.TypeAttributeNode():
                type = self.evaulate_type_expression(type_expression.type)
                assert False, 'TODO!'
            case ast.ListTypeNode():
                assert False, 'TODO!'
            case ast.StructTypeNode():
                assert False, 'TODO!'
            case ast.TupleTypeNode():
                assert False, 'TODO!'

    def evaluate_and_store_type_expression(
        self,
        type_expression: ast.TypeExpressionNode,
    ) -> None:
        type = self.evaulate_type_expression(type_expression)
        self.type_nodes[type_expression.id] = type

    def initialize_block(self, body: typing.List[ast.StatementNode]) -> None:
        for statement in body:
            self.initialize_statement(statement)

    def initialize_statement(self, statement: ast.StatementNode) -> None:
        match statement:
            case ast.TypeDeclarationNode() | ast.SumTypeNode():
                self.initialize_type_node(statement)

            case ast.FunctionDefNode():
                function_type = self.initialize_type_node(statement)
                assert isinstance(function_type, types.FunctionType)

                if statement.body is not None:
                    self.initialize_block(statement.body)

            case ast.ClassDefNode():
                class_type = self.initialize_type_node(statement)
                assert isinstance(class_type, types.TypeClass)
                self.initialize_block(statement.body)

            case ast.UseNode():
                self.evaulate_type_expression(statement.type)
                self.initialize_block(statement.body)

            case ast.UseForNode():
                self.evaluate_and_store_type_expression(statement.type)
                self.evaluate_and_store_type_expression(statement.type_class)
                self.initialize_block(statement.body)

            case ast.DeclarationNode():
                if statement.type is not None:
                    self.evaluate_and_store_type_expression(statement.type)

                if statement.value is not None:
                    self.initialize_expression(statement.value)

            case ast.ForNode():
                self.initialize_expression(statement.iterator)
                self.initialize_block(statement.body)

            case ast.WhileNode():
                self.initialize_expression(statement.condition)
                self.initialize_block(statement.body)

            case ast.IfNode():
                self.initialize_block(statement.body)
                if statement.else_statement is not None:
                    self.initialize_block(statement.else_statement.body)

            case ast.ReturnNode():
                if statement.value is not None:
                    self.initialize_expression(statement.value)

            case ast.ExprNode():
                self.initialize_expression(statement.expr)

    def initialize_expression(self, expression: ast.ExpressionNode) -> None:
        for subexpression in ast.walk_expressions(expression):
            if isinstance(subexpression, (ast.ExpressionLambdaNode, ast.BlockLambdaNode)):
                parameters: typing.Dict[str, types.Type] = {}
                function_type = types.FunctionType(
                    name='lambda',
                    parameters=parameters,
                    returns=types.SingletonType.INFERRED,
                )
                self.type_nodes[subexpression.id] = function_type

                for parameter in subexpression.parameters:
                    parameters[parameter.name] = types.SingletonType.INFERRED

                if isinstance(subexpression, ast.ExpressionLambdaNode):
                    self.initialize_expression(subexpression.body)
                else:
                    self.initialize_block(subexpression.body)

    def initialize_module(self) -> typing.Dict[int, types.Type]:
        self.initialize_block(self.module.body)
        return self.type_nodes

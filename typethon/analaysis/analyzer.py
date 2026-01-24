import attr
import typing

from . import types
from .resolution import SymbolNode
from ..diagnostics import DiagnosticReporter
from ..syntax.typethon import ast


@attr.s(kw_only=True, slots=True)
class TypeAnalyzer:
    diagnostics: DiagnosticReporter = attr.ib()
    module: ast.ModuleNode = attr.ib()
    resolved_symbols: typing.Dict[int, SymbolNode] = attr.ib()
    type_nodes: typing.Dict[int, types.Type] = attr.ib(factory=dict)

    def report_error(
        self,
        node: ast.Node,
        message: str,
        *format: str,
    ) -> None:
        self.diagnostics.report_error((node.start, node.end), message, *format)

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
        function_type = types.FunctionType(name=node.name, parameters=parameters)
        self.type_nodes[node.id] = function_type

        for parameter in node.parameters:
            parameters[parameter.name] = self.evaulate_type_expression(parameter.annotation)

        return function_type

    def create_type_class(self, node: ast.ClassDefNode) -> types.TypeClass:
        functions: typing.Dict[str, types.FunctionType] = {}
        type_class = types.TypeClass(name=node.name, functions=functions)
        self.type_nodes[node.id] = type_class

        for statement in node.body:
            if isinstance(statement, ast.FunctionDefNode):
                function = self.get_type_node(statement)
                assert isinstance(function, types.FunctionType)
                functions[statement.name] = function

        return type_class

    def create_type_parameter(self, node: ast.TypeParameterNode) -> types.TypeParameter:
        type_parameter = types.TypeParameter(name=node.name)
        self.type_nodes[node.id] = type_parameter
        return type_parameter

    def get_type_node(self, node: SymbolNode) -> types.Type:
        if node.id in self.type_nodes:
            return self.type_nodes[node.id]

        match node:
            case ast.SumTypeNode():
                return self.create_sum_type(node)
            case ast.TypeDeclarationNode():
                if isinstance(node, ast.StructTypeNode):
                    return self.create_struct_declaration(node)
                elif isinstance(node, ast.TupleTypeNode):
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
                assert False, 'Unreachable'

    def evaulate_type_expression(
        self,
        type_expression: ast.TypeExpressionNode,
    ) -> types.Type:
        match type_expression:
            case ast.NameNode():
                if type_expression.id not in self.resolved_symbols:
                    return types.SingletonType.INVALID

                node = self.resolved_symbols[type_expression.id]
                return self.get_type_node(node)
            case ast.SelfTypeNode():
                return types.SingletonType.SELF
            case ast.TypeParameterNode():
                return self.get_type_node(type_expression)
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

    def analyze_block(self, body: typing.List[ast.StatementNode]) -> None:
        for statement in body:
            self.analyze_statement(statement)

    def analyze_statement(self, statement: ast.StatementNode) -> None:
        match statement:
            case ast.FunctionDefNode():
                function_type = self.get_type_node(statement)
                assert isinstance(function_type, types.FunctionType)

                if statement.body is not None:
                    self.analyze_block(statement.body)

            case ast.ClassDefNode():
                class_type = self.get_type_node(statement)
                assert isinstance(class_type, types.TypeClass)

                self.analyze_block(statement.body)

            case ast.UseNode():
                type = self.evaulate_type_expression(statement.type)
                assert type # TODO
                self.analyze_block(statement.body)

            case ast.UseForNode():
                type = self.evaulate_type_expression(statement.type)
                type_class = self.evaulate_type_expression(statement.type_class)
                assert type_class # TODO
                self.analyze_block(statement.body)

            case ast.DeclarationNode():
                assert False, 'TODO'

            case ast.ForNode():
                iterator = self.analyze_expression(statement.iterator)
                assert iterator # TODO
                self.analyze_block(statement.body)

            case ast.WhileNode():
                self.analyze_expression(statement.condition)
                self.analyze_block(statement.body)

            case ast.IfNode():
                self.analyze_block(statement.body)

                if statement.else_statement is not None:
                    self.analyze_block(statement.else_statement.body)

    def analyze_expression(self, expression: ast.ExpressionNode) -> types.Type:
        ...

    def analyze_module(self) -> None:
        self.analyze_block(self.module.body)

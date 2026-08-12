import attr
from .initializer import TypeInitializer
from .. import asg


@attr.s(kw_only=True, slots=True)
class TypeChecker:
    init: TypeInitializer = attr.ib()

    def check_body(self, body: asg.AsgBody) -> None:
        for statement in body.statements:
            self.check_statement(statement)

    def check_statement(self, statement: asg.Statement) -> None:
        match statement:
            case asg.Local():
                ...
            case asg.While():
                ...
            case asg.If():
                ...
            case asg.Expr():
                self.synthesize_expression(statement.expr)

    def synthesize_expression(self, expression: asg.Expression) -> None:
        match expression:
            case asg.Attribute():
                assert isinstance(expression.value, asg.Resolved)

                defn = self.init.store.adts[expression.value.result.def_id]
                field = next(
                    field for field in defn.variants[0].fields if field.name == expression.attr
                )
                print(self.init.type_of(field.def_id))

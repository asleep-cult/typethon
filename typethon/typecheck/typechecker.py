import attr

from .. import asg


@attr.s(kw_only=True, slots=True)
class TypeChecker:
    asg_ctx: asg.AsgContext = attr.ib()
    module: asg.ModuleDef = attr.ib()

    # asg_ctx.fields will contian the following
    # ModuleDef | StructDef | TupleDef | SumDef | AliasDef | FunctionDef | ClassDef | UseDef

    # We can start by creating a type for every definition.
    # Paths can be transformed rather easily, just check if the resolved segment requires
    # arguments, if so, check the if the segment's arguments are correct.

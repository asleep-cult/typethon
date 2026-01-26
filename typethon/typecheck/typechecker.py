import attr

from .. import hir


@attr.s(kw_only=True, slots=True)
class TypeChecker:
    hir_ctx: hir.HirContext = attr.ib()
    module: hir.ModuleDef = attr.ib()

    # hir_ctx.fields will contian the following
    # ModuleDef | StructDef | TupleDef | SumDef | AliasDef | FunctionDef | ClassDef | UseDef

    # We can start by creating a type for every definition.
    # Paths can be transformed rather easily, just check if the resolved segment requires
    # arguments, if so, check the if the segment's arguments are correct.

    # There's still no way to explicity pass type parameters to a function.
    # We could probably solve this by simply adding an expression annotation syntax.
    # def f(x: 't) -> 'u
    # f(y: str): int
    # This would also conveniently (weirdly and hackishly) solve the lambda annotation syntax issue.

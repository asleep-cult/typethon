class ParserGeneratorError(Exception):
    ...


class ParserAutomatonError(Exception):
    ...


class StackUnderflowError(ParserAutomatonError):
    ...


class DeadlockError(ParserAutomatonError):
    ...


class UnexpectedTokenError(ParserAutomatonError):
    ...

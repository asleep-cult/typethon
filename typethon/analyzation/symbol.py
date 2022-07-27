from .types import Type


class Symbol:
    def __init__(self, name: str, type: Type) -> None:
        self.name = name
        self.type = type

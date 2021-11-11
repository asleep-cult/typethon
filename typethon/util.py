from typing import Iterable, TypeVar

T = TypeVar('T')


def singletoniter(arg: T) -> Iterable[T]:
    yield arg

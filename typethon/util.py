from typing import Iterable, Union

def iter_strings(strings: Union[str, Iterable[str]]) -> Iterable[str]:
    if isinstance(strings, str):
        yield strings
    else:
        yield from strings

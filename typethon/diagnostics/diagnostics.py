import enum
import typing

import attr


class DiagnosticLevel(enum.Enum):
    INFO = enum.auto()
    WARNING = enum.auto()
    ERROR = enum.auto()


@attr.s(kw_only=True, slots=True)
class DiagnosticInfo:
    level: DiagnosticLevel = attr.ib()
    message: str = attr.ib()
    start: int = attr.ib()
    end: int = attr.ib()


class DiagnosticReporter:
    def __init__(self, source: str) -> None:
        self.source = source
        self.diagnostics: typing.List[DiagnosticInfo] = []

    def has_error(self) -> bool:
        return any(diagnostic.level is DiagnosticLevel.ERROR for diagnostic in self.diagnostics)

    def report(
        self,
        level: DiagnosticLevel,
        span: typing.Tuple[int, int],
        message: str,
        *format: str,
    ) -> None:
        info = DiagnosticInfo(
            level=level,
            message=message.format(*format),
            start=span[0],
            end=span[1],
        )
        self.diagnostics.append(info)

    def report_error(
        self,
        span: typing.Tuple[int, int],
        message: str,
        *format: str,
    ) -> None:
        self.report(DiagnosticLevel.ERROR, span, message, *format)

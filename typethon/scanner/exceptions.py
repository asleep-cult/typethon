from ..metadata import __issues__


class BadEncodingDeclaration(Exception):
    pass


class FatalScannerError(Exception):
    def __init__(self, message, scanner):
        self.message = message
        self.scanner = scanner

    def __str__(self):
        return self.message + f'\nThis should never happen, please open an issue at {__issues__}'

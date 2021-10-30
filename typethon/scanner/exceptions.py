class BadEncodingDeclaration(Exception):
    pass


class InvalidSyntaxError(Exception):
    def __init__(self, message, *, ctx):
        self.message = message
        self.ctx = ctx

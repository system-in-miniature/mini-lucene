class QuerySyntaxError(ValueError):
    def __init__(self, message: str, offset: int, source: str) -> None:
        self.message = message
        self.offset = offset
        self.source = source
        super().__init__(f"{message} at offset {offset}\n{source}\n{' ' * offset}^")

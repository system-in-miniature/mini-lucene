class MiniLuceneError(Exception):
    """Base exception for MiniLucene domain failures."""


class IndexAlreadyExistsError(MiniLuceneError):
    pass


class IndexNotFoundError(MiniLuceneError):
    pass


class SchemaMismatchError(MiniLuceneError):
    pass


class WriterAlreadyOpenError(MiniLuceneError):
    pass


class AlreadyClosedError(MiniLuceneError):
    pass


class CloseError(MiniLuceneError):
    def __init__(self, errors: tuple[BaseException, ...]) -> None:
        self.errors = errors
        super().__init__(
            f"close encountered {len(errors)} cleanup error(s)"
        )

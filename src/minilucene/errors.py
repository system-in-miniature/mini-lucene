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

"""Expected failures that can be presented directly to the operator."""


class BookingError(Exception):
    """Base class for controlled application errors."""


class ValidationError(BookingError):
    pass


class NotFoundError(BookingError):
    pass


class BookingConflictError(BookingError):
    pass


class OperationNotAllowedError(BookingError):
    pass


class StorageError(BookingError):
    pass


class StorageBusyError(StorageError):
    pass

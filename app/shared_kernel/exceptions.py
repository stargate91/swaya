class DomainException(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class NotFoundException(DomainException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)

class BadRequestException(DomainException):
    def __init__(self, message: str):
        super().__init__(message, status_code=400)

# Config exceptions

class InvalidOptionException(Exception):
    pass

class ReferenceException(Exception):
    pass

class RequiredReferenceException(ReferenceException):
    pass

class InvalidPathException(ReferenceException):
    pass

class InconsistentReferenceTypeException(ReferenceException):
    pass


# Dependency exceptions

class CyclicDependencyException(Exception):
    pass


# Build exceptions

class InvalidDefaultFileException(Exception):
    pass

class RedundantDefaultException(Exception):
    pass


# Other

class EverythingHasBrokenException(Exception):
    pass

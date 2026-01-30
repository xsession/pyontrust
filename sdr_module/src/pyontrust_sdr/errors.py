class SdrError(Exception):
    """Base error for pyontrust_sdr."""


class DeviceNotFound(SdrError):
    pass


class StreamOverrun(SdrError):
    pass


class UnsupportedRate(SdrError):
    pass


class DriverError(SdrError):
    pass


class GraphValidationError(SdrError):
    pass

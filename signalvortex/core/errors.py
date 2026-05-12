"""Custom exceptions for SignalVortex."""

class SignalVortexError(Exception):
    """Base exception for all SignalVortex errors."""
    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(message)
        self.original_error = original_error

class DataSourceError(SignalVortexError):
    """Raised when a data source fails (e.g. API error, network issue)."""
    pass

class AnalysisError(SignalVortexError):
    """Raised when an analysis module fails (e.g. math error, insufficient data)."""
    pass

class ConfigError(SignalVortexError):
    """Raised when configuration is missing or invalid."""
    pass

class CriticalError(SignalVortexError):
    """Raised when a critical failure occurs that requires immediate termination."""
    pass

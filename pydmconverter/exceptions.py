class ConverterError(Exception):
    """Base exception for converter errors."""

    pass


class AttributeConversionError(ConverterError):
    """Raised when an EDM attribute cannot be converted to its PyDM equivalent."""

    def __init__(self, attr_name: str, value, widget_name: str, cause: Exception = None):
        self.attr_name = attr_name
        self.value = value
        self.widget_name = widget_name
        msg = f"Failed to convert attribute '{attr_name}'={value!r} on widget {widget_name}"
        if cause:
            msg += f": {cause}"
        super().__init__(msg)

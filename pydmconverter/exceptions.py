class ConverterError(Exception):
    """Base exception for converter errors."""
    pass


class UnsupportedWidgetError(ConverterError):
    """Raised when an EDM widget type has no PyDM mapping."""

    def __init__(self, widget_name: str):
        self.widget_name = widget_name
        super().__init__(f"Unsupported widget type: {widget_name}")


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


class ColorConversionError(ConverterError):
    """Raised when a color value cannot be converted."""

    def __init__(self, color_value: str):
        self.color_value = color_value
        super().__init__(f"Could not convert color: {color_value}")

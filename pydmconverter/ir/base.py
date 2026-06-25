"""Pydantic base for Screen IR models.

Mirrors ``canopy.contracts.base.CanopyModel`` exactly: snake_case Python attributes
serialize as camelCase on the wire (``schemaVersion``, ``targetProperty``,
``alarmSensitive``) and either casing is accepted on input. When this package is
lifted into ``src/canopy/converter/``, swap this base for ``CanopyModel`` and the
field shapes carry over unchanged.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class IRModel(BaseModel):
    """Pydantic v2 base for all Screen IR DTOs.

    Uses the ``to_camel`` alias generator so no per-field ``Field(alias=...)`` is
    needed. ``populate_by_name`` lets callers construct models with snake_case
    keyword arguments; serialization to the wire uses camelCase via
    ``model_dump(by_alias=True)``.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        validate_by_name=True,
    )

"""Qt ``.ui`` front-end: parses PyDM/Qt Designer ``.ui`` XML into SourceNode trees
for the shared IR builder.

``.ui`` already speaks Qt/PyDM, so widget classes and property names map near-directly
through Beaver's ``qtMapping``/``qtPropMap`` — no EDM-style translation table needed.
"""

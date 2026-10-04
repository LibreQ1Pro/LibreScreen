"""Copying values of Moonraker's JSON into the program state."""

from librescreen.util.cpp import jget


def read_fields(target, source, fields):
    """Copy the keys of the JSON object ``source`` that are present into attributes of ``target``.

    ``fields`` is a list of ``(attribute, key, conversion)``.
    """
    for attr, key, convert in fields:
        value = jget(source, key)
        if value is not None:
            setattr(target, attr, convert(value))

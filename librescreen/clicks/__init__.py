"""What a click on the screen does: ``handle`` looks the page up in the tables of the modules of this package."""

import logging

from librescreen.clicks import guide, levelling, move_filament, printing, system

log = logging.getLogger(__name__)

HANDLERS = {}
for _module in (guide, printing, move_filament, levelling, system):
    for _page, _handler in _module.HANDLERS.items():
        assert _page not in HANDLERS, _page
        HANDLERS[_page] = _handler


def handle(page_id, widget_id, type_id):
    log.debug("+++++++++++++++++++%s", page_id)
    log.debug("+++++++++++++++++++%s", widget_id)
    log.debug("+++++++++++++++++++%s", type_id)
    handler = HANDLERS.get(page_id)
    if handler is not None:
        handler(page_id, widget_id)

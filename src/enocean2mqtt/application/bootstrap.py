"""Composition root: the single place where the concrete daemon (and its overlay) is chosen.

Keeping wiring here — rather than in ``cli.main`` or scattered across ``__init__`` — means the rest
of the code depends only on the typed ``Config`` and the ports; swapping the overlay or injecting
fakes is a one-line change at this seam.
"""

from __future__ import annotations

import logging

from enocean2mqtt.application.daemon import EnoceanDaemon
from enocean2mqtt.domain.config import Config

logger = logging.getLogger("enocean2mqtt.application.bootstrap")


def bootstrap(config, sensors):
    """Build the wired daemon for *config* + *sensors*, selecting the overlay.

    *config* may be a raw options mapping or an already-built :class:`Config`; it is normalised (and
    validated) here. Returns an unstarted daemon — the caller invokes ``.run()``.
    """
    config = Config.from_mapping(config)

    if config.overlay == "ha":
        # Imported lazily so a non-HA deployment need not import the overlay (and its deps).
        from enocean2mqtt.homeassistant.ha_bridge import HomeAssistantBridge

        logger.info("Selected overlay : Home Assistant")
        return HomeAssistantBridge(config, sensors)

    logger.info("Selected overlay : None")
    return EnoceanDaemon(config, sensors)

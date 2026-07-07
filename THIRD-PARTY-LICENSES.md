# Third-party licenses

Copyright © 2024–2026 Christian Theis. This project is distributed under **GPL-3.0** (see `LICENSE`) —
required because the consolidated
daemon and Home Assistant add-on derive from GPL-3.0 upstreams. It bundles the following
third-party component under its own (GPL-compatible) license:

## EnOcean protocol library — `src/enocean2mqtt/protocol/`

- Origin: `mak-gitdev/enocean` (a fork of `kipe/enocean`), forked from
  `7956cce9365ae13dc057ba8bb09e2934fe5a1b2f`, then folded into this project as
  `enocean2mqtt.protocol` (renamed, restructured, type-hinted).
- License: **MIT** — full text in
  [`src/enocean2mqtt/protocol/LICENSE`](src/enocean2mqtt/protocol/LICENSE).
- Copyright (c) 2014-2016 Kimmo Huoman.
- Modifications: the EEP parser was migrated from BeautifulSoup to the stdlib
  `xml.etree.ElementTree`, and the package was refactored/renamed. MIT permits
  modification; the notice above is retained per the MIT terms.

MIT is permissive and GPL-compatible, so including it in this GPL-3.0 work is allowed.

## Daemon + Home Assistant overlay — `src/enocean2mqtt/`

The consolidated daemon and its Home Assistant overlay are derived works (heavily modified, not
1:1 copies) of the following GPL-3.0 upstreams. Their copyright/authorship notices are retained
here (the notices previously carried as source-file headers) as required by GPL-3.0:

- `embyt/enocean-mqtt` — Copyright © 2020 embyt GmbH; author Roman Morawek
  <roman.morawek@embyt.com>. GPL-3.0. (Origin of the daemon core: `cli.py`, `communicator.py`.)
- `mak-gitdev/HA_enoceanmqtt` — author Marc Alexandre K.
  <marcalexandrek-developer@yahoo.fr>. GPL-3.0. (Origin of the Home Assistant overlay:
  `homeassistant/ha_communicator.py`, `homeassistant/device_manager.py`.)
- `mak-gitdev/hidden-addon` — the Home Assistant add-on packaging. GPL-3.0.

This project's own GPL-3.0 license (`LICENSE`) is inherited from these upstreams.

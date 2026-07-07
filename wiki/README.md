# Wiki source

These markdown files are the source for the project's **GitHub Wiki** — the home for all
**user-facing documentation**. GitHub serves wikis from a separate git repository
(`<repo>.wiki.git`), so they aren't published just by living here; publish them with:

```bash
# 1. Enable the Wiki: repo → Settings → Features → Wikis (tick it), then create any page once
#    in the web UI so the wiki repo exists.
# 2. Push these files into it:
git clone https://github.com/t-ice/enocean-mqtt-ha.wiki.git
cp wiki/*.md enocean-mqtt-ha.wiki/
cd enocean-mqtt-ha.wiki
git add . && git commit -m "Publish wiki" && git push
```

## Pages
- `Home.md` — landing page (GitHub shows it as the wiki front page).
- `_Sidebar.md` / `_Footer.md` — navigation shown on every page.
- User guides: `Getting-Started`, `Configuration-(devices.yaml)`, `Eltako-Setup`,
  `Raspberry-Pi-Transceiver`, `Teach-In`, `Supported-Devices`, `Examples`, `Troubleshooting`, `FAQ`.

Internal navigation uses GitHub wiki links (`[[Page Title]]`); images use raw `githubusercontent`
URLs (the PNG/SVG sources live in the main repo under `docs/img/`).

**Developer / reference docs** (architecture, testing, EEP/ESP3 compliance, Eltako coverage) stay in
the main repo under [`docs/`](../docs) — versioned and reviewed with the code, and linked from the
sidebar's "Reference" group.

# Dimora — Website Studio

Dimora is the web client for the Apartment Booking engine. It turns the terminal
workflow into a two-sided product: **guests** search and book apartments, **hosts**
publish and manage them. The interface is available in Italian, English and German.

The studio is a separate delivery layer. It talks to the existing REST API and never
duplicates business rules: capacity, overlap detection and pricing remain in
`apartment_booking/database.py`, exactly as for the CLI.

## Running locally

Start the API, then the studio, from the repository root:

```bash
docker compose up --build --detach --wait web   # API on http://127.0.0.1:8000
python3 website-studio/serve.py                  # Dimora on http://127.0.0.1:8080
```

Open http://127.0.0.1:8080, choose **Enter as a guest** or **Enter as a host**, and
you are in. Configuration is optional:

| Setting | Flag | Environment variable | Default |
| --- | --- | --- | --- |
| API base URL | `--api` | `BOOKING_API_URL` | `http://127.0.0.1:8000` |
| Bind address | `--host` | `STUDIO_HOST` | `127.0.0.1` |
| Port | `--port` | `STUDIO_PORT` | `8080` |

`serve.py` uses only the Python standard library. It serves `public/` and forwards
`/api/*` to the booking API, so the browser sees a single origin: no CORS changes to
the Flask service and a strict Content Security Policy for the client.

## The experience

- **Landing.** A centred promise over a slow aurora, a live count of available stays,
  how each role works, four guarantees and the most popular apartments, all from the
  live API. The header is open at the top and draws in to a glass pill as the page
  scrolls. At the end, the page lifts like a curtain to uncover the footer.
- **Entry.** Two doors: *Enter as a guest* or *Enter as a host*. The left panel shows
  the role's mark and line, and changes as you point at either door.
- **Workspaces.** A side panel holds the role's sections, the light/dark switch and
  the profile menu with sign-out. Screens open on a compact heading with their main
  action; the language choice sits in a footer pinned to the bottom of the screen.

## Feature coverage

Every CLI command has a web equivalent.

| CLI command | Role | Dimora screen |
| --- | --- | --- |
| `apartment view` | both | Explore (guest), Listings (host) |
| `apartment search` | guest | Explore → dates and guests |
| `booking create` | guest | Explore → Book |
| `booking view` | both | My trips (guest, own bookings), Reservations (host, all) |
| `booking change` | guest | My trips → Change |
| `booking cancel` | guest | My trips → Cancel |
| `apartment add` | host | Listings → New listing |
| `apartment update` | host | Listings → Price |
| `apartment remove` | host | Listings → Remove |

Hosts also get an overview with key figures, next arrivals and 30-day occupancy,
all derived from the same API data.

## Architecture

```
website-studio/
├── serve.py             Static server + same-origin API proxy (stdlib)
├── public/
│   ├── index.html       Single entry point
│   ├── assets/brand/    Logo and favicon
│   ├── assets/fonts/    Self-hosted variable fonts and their licences
│   ├── styles/          tokens → base → components → layout → pages
│   └── src/
│       ├── main.js      Composition root: state, routing, guards, global events
│       ├── routes.js    Route table with access rules
│       ├── config.js    Constants and navigation model
│       ├── core/        html escaping, i18n, formatting, router, motion, storage
│       ├── services/    API client, booking gateway, role sessions
│       ├── ui/          components, chrome, dialogs, toasts, forms, icons
│       ├── i18n/        it.js · en.js · de.js
│       └── views/       landing, entry, guest/*, host/*
├── tests/               node:test suites and Python unittest for serve.py
└── docs/brand.md        Name, voice, palette, typography, motion
```

Dependencies point downwards only: `views → ui → services → core`. Views receive a
context object (session, query, navigation) instead of reaching for globals, and
each screen is mounted into a fresh root so its listeners are discarded with it.

There is no build step and no third-party runtime dependency: native ES modules,
the `<dialog>` element, `Intl` for numbers, dates and plurals, and two self-hosted
fonts.

## Interaction design

- **Recognition over recall.** Guests pick apartments and bookings from cards; the
  CLI's typed names and date ranges are never required.
- **Error prevention.** Date pickers reject past or inverted ranges, guest steppers
  stop at capacity, and removing a listing with bookings requires typing its name.
- **Visibility of system status.** Live price breakdowns, skeleton loaders,
  toasts, and a before/after difference when a booking changes.
- **Recoverable errors.** API messages are mapped to localised copy with a retry
  action; conflicts (dates just taken, duplicate names) are explained in context.
- **No repetition.** Each control appears once per screen: language in the footer,
  theme and profile in the side panel, the screen's main action in its heading.
- **Shareable state.** Search criteria and filters live in the URL.
- **Accessibility.** Semantic landmarks, skip link, labelled controls, inline
  errors linked with `aria-describedby`, focus moved to each new page heading,
  keyboard-operable dialogs and menus, WCAG AA contrast in both themes, and every
  animation disabled under `prefers-reduced-motion`.
- **Responsive.** The side panel becomes a bottom tab bar on phones, dialogs become
  bottom sheets, and tables reflow into cards.

## Security notes

- All dynamic text is rendered through an escaping template tag (`core/html.js`).
- CSP forbids inline scripts and inline styles; style values are set through the CSSOM.
- Fonts are served from the studio itself: no requests to third parties.
- The proxy forwards only `Content-Type`/`Accept` upstream and
  `Content-Type`/`Retry-After`/`Allow` back, caps bodies at 64 KB, hides dotfiles and
  directory listings, and binds to `127.0.0.1` by default.
- **Demo profiles, not accounts.** The booking API has no authentication, so
  entering as a role opens that role's demo profile (guest: Tom Springer, host:
  Sebastiano Druda). A guest's trips are the bookings made under the profile's name.
  Before any public deployment the API needs real authentication and per-user
  authorisation.

## Tests

```bash
cd website-studio
npm test        # node --test (i18n parity, rendering, formatting, services) + unittest (serve.py)
```

The same checks run on GitHub Actions in the `Website` workflow whenever
`website-studio/` changes. Node 20 or newer is required for the JavaScript tests
only; the app itself needs just a modern browser.

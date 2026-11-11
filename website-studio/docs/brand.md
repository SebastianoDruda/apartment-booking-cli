# Dimora brand guide

## Name

**Dimora** is Italian for *dwelling*, a place where you stay. It is short, easy to say
in Italian, English and German, and it describes both sides of the product: the
apartment a guest books and the home a host opens.

**Tagline**

| Italiano | English | Deutsch |
| --- | --- | --- |
| Ovunque, come a casa. | Anywhere feels like home. | Überall wie zu Hause. |

## Mark

An arched doorway inside a terracotta tile. The arch refers to Mediterranean
architecture and to an open door; the dot is the keyhole. Source files:
`public/assets/brand/logo.svg` and `favicon.svg`.

Each role has its own mark built on the same arch: a suitcase on terracotta for
guests and a key on sage for hosts. They identify the entry page and the workspace.

## Voice

- **Short.** One idea per line. Headlines rarely pass six words.
- **Said once.** No control, claim or label is repeated on the same screen.
- **Warm and direct.** Speak to the person: *Where to next, Tom?*
- **Concrete.** *Nights × rate = total* rather than *transparent pricing solutions*.
- **Calm when things fail.** Say what happened and what to do next.
- **Natural in each language.** Each version is written idiomatically, not translated
  word for word. Italian uses informal *tu*, German uses *du*.

## Colour

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `--brand` | `#B84A26` terracotta | `#E57A52` | Primary actions, accents |
| `--paper` | `#FBF7F1` cream | `#100E0C` | Page background |
| `--ink` | `#1A1612` | `#F4EEE6` | Text |
| `--sage` | `#47705A` | `#86B897` | Success, hosts, live status |
| `--gold` | `#C08A22` | `#E2B65A` | Highlights, data |
| `--info` | `#2D5B8A` | `#94BDE6` | Upcoming status |
| `--danger` | `#B42318` | `#F2877A` | Destructive actions, errors |

Text and primary buttons meet WCAG AA contrast in both themes. Apartment artwork
draws on a Mediterranean and alpine palette (terracotta, ochre, sand, sage, lagoon,
sea, dusk, rose) and each listing keeps the same colour and motif everywhere.

## Typography

- **Display:** Bricolage Grotesque, a warm grotesque with optical sizes. Tight
  tracking for headlines; the accent word of a headline takes the brand colour.
- **Text and UI:** Manrope, clean and highly legible at small sizes.

Both are variable fonts under the SIL Open Font License, served from
`public/assets/fonts/` with their licences. No external font requests are made, which
matters for privacy rules such as the GDPR.

## Motion

Slow aurora gradients, a header that draws in to a pill as you scroll, a page that
lifts like a curtain to reveal the footer, reveals on scroll, counters that count up
and light that follows the cursor. Motion explains state (a booking ring on a new
trip, a filling occupancy bar) and never blocks input. All of it is switched off when the system asks for reduced motion.

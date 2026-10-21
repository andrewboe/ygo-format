# ygo-format

Format-aware Yu-Gi-Oh! card data and an [MCP](https://modelcontextprotocol.io) server, so an AI assistant
can build and check decks from real data instead of memory. It knows **TCG Advanced** (the current
Forbidden & Limited list) and **Genesys** (points, the 100-point cap, no Link or Pendulum Monsters).

Card text, ban status, Genesys points, legality and tournament meta all come from live sources,
cached on your machine:

| Source | Used for |
|---|---|
| [YGOProDeck API](https://ygoprodeck.com/api-guide/) | card text, stats, archetypes, TCG/OCG dates, Genesys points |
| [Project Ignis LFLists](https://github.com/ProjectIgnis/LFLists) | TCG F&L list (the stricter of it and YGOProDeck is used) |
| [Yugioh Meta](https://www.yugiohmeta.com) | recent tournament tops, deck shares, card inclusion |
| [YGOResources](https://db.ygoresources.com) | official OCG FAQ and Q&A rulings |

Nothing from these sources is bundled; the server fetches and caches it on first use.

## Tools

| Tool | What it does |
|---|---|
| `search_cards` | Search the legal card pool by text, regex, name, archetype, type, attribute, level, points |
| `card_lookup` | One card: full text, stats, status in every format, alt passcodes, rulings links |
| `archetype` | An archetype's members and support cards, with limits or points |
| `validate_deck` | Legality of a deck (.ydk, `ydke://` URL or plain list) with every card's status or points |
| `finalize_deck` / `saved_decks` | Save a deck only if it is legal (.ydk + `ydke://` + text list); list saved decks |
| `find_links` | Bridges between engines: searchers into the deck, what it reaches, Extra Deck options, Special Summon locks |
| `meta_snapshot` | Recent tops for a format: deck shares, top 8s, wins, how many lists are still legal, staples |
| `meta_inclusion` | How a card is played across tops, or a deck type's card inclusion table |
| `card_rulings` | Official Q&As for a card, optionally only those involving a second card or certain words |
| `find_lines` / `line_result` | *Optional.* Engine-searched turn-1 lines for a specific 5-card hand (needs [ygo-sim](https://github.com/andrewboe/ygo-sim)) |

Every answer carries a `data` block saying when the card data was fetched and which F&L list it reflects.

The repo also ships a Claude Code skill, [`skills/ygo-deckbuilding`](skills/ygo-deckbuilding/SKILL.md),
that tells the assistant how to use these tools: format first, every card fact from a tool, validate
before showing a list, rulings quoted with their date, and hand lines only on request.

## Install

Short version (details, other MCP clients and troubleshooting in [docs/INSTALL.md](docs/INSTALL.md)):

Windows (PowerShell):

```powershell
git clone https://github.com/andrewboe/ygo-format.git
cd ygo-format
py -3 -m venv .venv
.venv\Scripts\python -m pip install -e .
claude mcp add --scope user ygo-format -- "$PWD\.venv\Scripts\python.exe" -m ygoformat.mcp_server
```

macOS / Linux:

```bash
git clone https://github.com/andrewboe/ygo-format.git
cd ygo-format
python3 -m venv .venv
.venv/bin/python -m pip install -e .
claude mcp add --scope user ygo-format -- "$PWD/.venv/bin/python" -m ygoformat.mcp_server
```

Then ask Claude something like *"Is this Genesys list under 100 points?"* or *"Build me a Destiny HERO
deck for TCG Advanced."*

## Limits

- `find_links` parses card text with rules, not an engine: treat its ruling flags as unverified, and
  Fusion Summon spells are not modelled as links yet.
- `card_rulings` returns OCG rulings; TCG rulings can differ.
- `find_lines` is a search, not a solver, and is slow (about 10 s at quick depth, 1–4 min deeper).
- Known tool problems from real use are logged in [docs/format_mcp_dryrun.md](docs/format_mcp_dryrun.md).

## Development

```bash
.venv/Scripts/python -m pip install -e ".[test]"
.venv/Scripts/python -m pytest
```

Tests run offline against pinned fixtures in `tests/fixtures`. Design notes: [docs/format_mcp_scope.md](docs/format_mcp_scope.md)
(written while the code lived in ygo-sim, so module paths there say `ygosim`).

This project was split out of [ygo-sim](https://github.com/andrewboe/ygo-sim) at commit `6aa4d34`;
ygo-sim now depends on it for card data and formats.

Licensed under the [MIT License](LICENSE). Card data, rulings and meta are fetched from the sources above
and remain theirs. Yu-Gi-Oh! is a trademark of Konami. This project is not affiliated with or endorsed by Konami.

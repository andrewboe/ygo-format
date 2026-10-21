# Installing ygo-format

ygo-format is a Python package with a stdio MCP server. Any MCP client can run it; the steps below
cover Claude Code and Claude Desktop.

## Requirements

- Python 3.10 or newer (tested on 3.12).
- Internet access on first use. The first tool call downloads the card database from YGOProDeck and
  builds a local index (about 30 MB on disk; a few seconds on a fast connection, up to a minute on a
  slow one). The first `meta_snapshot` / `meta_inclusion` call also downloads recent tournament lists
  (about 20 seconds). After that the data is re-checked at most once a day (meta: every 12 hours).
- Optional, for line search only: Windows with WSL and a working [ygo-sim](https://github.com/andrewboe/ygo-sim)
  checkout (see the last section).

## 1. Install the package

Windows (PowerShell):

```powershell
git clone https://github.com/andrewboe/ygo-format.git
cd ygo-format
py -3 -m venv .venv
# (or: python -m venv .venv, with Python 3.10+)
.venv\Scripts\python -m pip install -e .
```

macOS / Linux:

```bash
git clone https://github.com/andrewboe/ygo-format.git
cd ygo-format
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Check that it starts (it waits for an MCP client on stdin; stop it with Ctrl+C):

```bash
.venv/bin/python -m ygoformat.mcp_server      # Windows: .venv\Scripts\python -m ygoformat.mcp_server
```

## 2. Register the server

### Claude Code

Use the venv's Python with an absolute path. `--scope user` makes the tools available in every project.

```powershell
# Windows, from the ygo-format folder
claude mcp add --scope user ygo-format -- "$PWD\.venv\Scripts\python.exe" -m ygoformat.mcp_server
```

```bash
# macOS / Linux, from the ygo-format folder
claude mcp add --scope user ygo-format -- "$PWD/.venv/bin/python" -m ygoformat.mcp_server
```

Run `claude mcp list` and check that `ygo-format` shows as connected. Restart any open Claude Code
sessions so they pick it up.

### Claude Desktop (or another MCP client)

Add an entry to the client's MCP config (for Claude Desktop: Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "ygo-format": {
      "command": "C:\\path\\to\\ygo-format\\.venv\\Scripts\\python.exe",
      "args": ["-m", "ygoformat.mcp_server"]
    }
  }
}
```

On macOS / Linux use `/path/to/ygo-format/.venv/bin/python`. Restart the client afterwards.

## 3. Install the skill (recommended, Claude Code)

The `ygo-deckbuilding` skill tells Claude how to use the tools well: pin the format first, take every
card fact from a tool, validate every list, quote rulings with their date, and only run line searches
when you ask for a hand's line.

```powershell
# Windows
Copy-Item -Recurse skills\ygo-deckbuilding "$env:USERPROFILE\.claude\skills\"
```

```bash
# macOS / Linux
mkdir -p ~/.claude/skills && cp -r skills/ygo-deckbuilding ~/.claude/skills/
```

## 4. Try it

Ask Claude, for example:

- "Is this deck legal in TCG Advanced?" (paste a .ydk, a `ydke://` URL or a list)
- "What are the top decks in Genesys right now, and how many points do they use?"
- "Build me a Destiny HERO deck for TCG Advanced and save it."
- "Does Ash Blossom stop Fusion Destiny's lock?" (it will quote the official Q&A)

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `YGO_FORMAT_DATA` | `%LOCALAPPDATA%\ygo-format` (Windows), `$XDG_DATA_HOME/ygo-format` or `~/.local/share/ygo-format` | Where the card index, meta cache, rulings cache, saved decks and line-search jobs live |
| `YGOSIM_HOME` | unset | Path to a ygo-sim checkout; turns on `find_lines` / `line_result` |

Set them in the MCP registration, for example:

```bash
claude mcp add --scope user -e YGO_FORMAT_DATA=D:/ygo-data ygo-format -- "<venv python>" -m ygoformat.mcp_server
```

or with an `"env": {...}` block in the JSON config. Saved decks are in `<data dir>/decks/`.

## Optional: line search (`find_lines`)

`find_lines` searches a real game engine (EDOPro) for the turn-1 lines a specific 5-card hand can
make. It runs ygo-sim's `wsl/line_finder.py` in WSL, so it needs:

1. Windows with WSL (Ubuntu).
2. A ygo-sim checkout with its WSL engine and runtime set up as described in ygo-sim's README
   (phase 2: the goldfish simulator on ygopro-core, with the engine build and card scripts under
   `~/ygo` inside WSL).
3. `YGOSIM_HOME` pointing at that checkout in the server's environment:

   ```powershell
   claude mcp add --scope user -e YGOSIM_HOME=C:\path\to\ygo-sim ygo-format -- "$PWD\.venv\Scripts\python.exe" -m ygoformat.mcp_server
   ```

Without it, every other tool works and `find_lines` returns an error saying line search is not set up.
Cards from sets newer than the engine's scripts make a search fail; the result names them.

## Troubleshooting

- **First call is slow or times out:** the card index is being built. Call the tool again after a minute.
- **`stale: true` in the `data` block:** the last check against YGOProDeck failed for over 7 days.
  Check your connection; answers still work from the cache.
- **`card_rulings` says the request failed:** YGOResources (db.ygoresources.com) could not be reached.
  Some routers fail to resolve it; try another DNS server. Cached rulings still work.
- **`legal: null` from `validate_deck`:** a card name or passcode could not be matched. The
  `parse_errors` list says which; fix the name and call again.
- **Tools don't appear in Claude Code:** run `claude mcp list`, check that the Python path is the venv's
  and absolute, and restart the session.

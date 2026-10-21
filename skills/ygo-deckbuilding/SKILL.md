---
name: ygo-deckbuilding
description: Build, tune or review Yu-Gi-Oh! TCG decks for TCG Advanced or Genesys with the ygo-format MCP tools, so card text, ban status, Genesys points, meta claims and legality come from data rather than memory. Use for requests like "build me a Destiny HERO deck for the current Genesys meta", "find bridges into other engines under the points cap", "what should I side against X", "is this list legal", "how many points does this cost", or "here's my hand, give me the line".
---

# Yu-Gi-Oh! deckbuilding with ygo-format

Every fact about a card comes from a tool call, never from memory. That covers its text, Type or
Attribute, what it searches, its ban status and its Genesys points. Memory is where past mistakes
came from: Cambroraster treated as a non-Link, a banned Herald, Cupsy's limit, wrong passcodes.

## Format first

Pin the format before anything else: `tcg_advanced` or `genesys`.
- If the user didn't say, ask. Answer with Advanced only when the context makes it obvious.
- **Genesys:**
  - There is no Forbidden & Limited list.
  - Link and Pendulum Monsters are banned in every zone.
  - Main + Extra + Side points must fit the cap: 100 by default, but ask if the event uses another.
- **Advanced:** the F&L list applies, using the stricter of YGOProDeck and Project Ignis.

## Workflow

1. **Meta.** Call `meta_snapshot(format)` for deck shares, how many recent lists are still legal, and staples.
   - Say how fresh the data is, and that legality is judged by today's list or points.
   - Use `meta_inclusion(card=...)` or `meta_inclusion(deck_type=...)` for "what do people play" questions.
2. **Engine.** Call `archetype(name, format)` for members, with points or limits, and support.
   - Membership is by name (case-sensitive).
   - Read the card text that comes back. Don't assume what a card does.
3. **Draft.** Build the list from cards you have actually looked up.
   - Use `search_cards` for gaps: hand traps within points, "Level 4 DARK Warrior extenders", or `mentions="X"`.
4. **Links.** Call `find_links(format, decklist=...)` for searchers into the deck, what it already reaches, bridges into other engines, Extra Deck options and lock conflicts.
   - In Genesys it only suggests cards that fit the points left.
   - Treat `breaks_deck_locks` and `its_lock` as real problems.
   - Treat `ruling_flags` as unverified.
5. **Validate.** Call `validate_deck` on every list before showing it, including after each swap.
   - `legal: null` means an input problem, such as an unknown or ambiguous name or a bad passcode. Fix it and call again; never drop the card.
6. **Finalize.** When the user settles on a list, call `finalize_deck(format, name, decklist)`.
   - It refuses illegal decks.
   - Give them the `.ydk` path and the `ydke://` URL.
   - Follow-up questions can pass that `.ydk` path to `validate_deck` or `find_links`.
   - Use `saved_decks` to find earlier ones.

## Hand lines (only on request)

`find_lines` / `line_result` search a real engine (EDOPro in WSL) for turn-1 lines from one exact hand.
They are slow and noisy, so they are a teaching tool, not a validation step.
- **Run it only when the user asks for the line for a specific hand** ("here's my 5, give me the line",
  "how does this hand combo"). Don't run it to check a deck you built, and don't put it in briefs for
  other sessions unless the user asked for lines.
- **Depth:** start with `depth="quick"` (~10 s). Use `normal` or `deep` (~1–4 min) only when the user
  asks, or when quick returns nothing better than passing; say which depth you used.
- **Deck:** pass `saved_deck` when the user means a saved list. Run one job at a time; parallel jobs slow
  each other down. Wait for the result with a background `until [ -s <data dir>/line_jobs/<id>/result.json ]`
  loop (data dir: `YGO_FORMAT_DATA`, or the default in docs/INSTALL.md), not by polling `line_result`.
- **Don't trust the raw result blindly.** Scoring can rank passing above an unfinished line, the step log
  can leave out materials or show bare "Yes" prompts, and lines can contain pointless actions
  (negating your own cards). If the best line is "End the turn" or looks wrong, say so and give your own
  reading of the card text, marked as untested.
- **Draws are not part of the hand.** Only the 5 hand cards are stacked; the rest of the deck sits in a
  fixed order the search can see, so anything drawn mid-line (Vision, Engage!, Pot of Desires, Diamond
  Dude…) is luck the engine "knew" in advance. Find which cards were drawn: any card the line uses from
  the hand that was neither in the starting 5 nor added by a "Select to add to hand" step. Never present
  a drawn card as available. Build the answer from the starting 5 plus searched cards only, and give
  steps that need a drawn card as "if you draw X" with a fallback for when you don't.

**Answer format.** Turn the engine's line into a lesson, checked against card text:
1. **Numbered steps**, one action each, in the engine's order. For each step:
   - what you do and which card effect makes it legal (cost vs. effect, once-per-turn, conditions);
   - what it adds, sends or summons.
2. **Lock timeline.** Mark the step where each Special Summon lock starts (for example
   "**Lock on from here:** DARK HERO only") and which later summons it allows or forbids.
   Check that every summon after a lock obeys it.
3. **End board**: each card, and what it does on the opponent's turn (negate, destroy, Quick Effect
   that needs a location such as the GY, or nothing). Add the cards left in hand.
4. **Caveats**: choke points (where Ash or a hand trap stops the line and what still happens),
   LP or other costs, things destroyed later (e.g. "destroyed in the End Phase of next turn"), and any
   step whose ruling is unverified (`card_rulings`). Mention unused cards and a possible improvement,
   marked as untested.

Present the line as "found by engine search", not as proven or optimal.

## How to answer

- Show the list by zone with counts. In Genesys, also show the points per card and the total against the cap.
- Quote the data's "as of" date when stating points or ban status.
- For every suggested bridge or tech card, give its link as the tool reported it: what it searches or summons, and why. Add its points or limit, and any lock it imposes or breaks.
- **Rulings.** When a line depends on cost vs. effect, missing the timing, once-per-turn wording or an interaction between cards, call `card_rulings(card, with_card=other)`, or use `query="..."`.
  - Quote the official answer, with its date.
  - It is an OCG ruling; say so if the TCG could differ.
  - If no Q&A covers the case, say the ruling is unverified and give the `card_url`. Never fill the gap with a guess.
- Combos are your reading of card text, not tested lines. Say "this should work because…", never "this works".
- If a tool says the data is stale, or YGOProDeck has a newer database, say so before relying on it.

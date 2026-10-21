# ygo-format MCP dry run: multi-engine D-HERO (2026-10-20)

End-to-end use of the ygo-format tools to build four Destiny HERO decks for TCG Advanced
(2026.10 TCG list, data as of 2026-10-20T21:00Z, YGOProDeck db 147.37). Decks saved with
finalize_deck as `D-HERO <idea>`. This file records only what went wrong with the tools.

## Tool problems found

### find_lines / line_result

1. **One unscripted card fails the whole job, and only after it is queued.**
   Input: the Dresden reference list (Extra had Skyborne Blue Cularsaw, 51307986, TCG 2026-10-08, no OCG
   release). `find_lines` returned `status: running`; `line_result` then returned `failed`,
   `"the engine can't play some cards"`, `missing: [{passcode: 51307986, name: null, ...}]`.
   - The check could run synchronously in `find_lines` and fail fast.
   - `name: null` although the MCP knows the card; resolve it from the card DB.
   - The `line_result` description says unplayable cards "are reported", which reads as "reported
     and skipped". Either drop Extra Deck cards the engine lacks (with a warning) or say clearly
     that the job fails.
2. **Silent "do nothing" result with no diagnostics.**
   Input: hand `[Vision HERO Faris, Destiny HERO - Malicious, Ash Blossom, Mulcharmy Fuwalos,
   Dominus Impulse]`, deck "D-HERO Vision" (normal depth). Result: a single line,
   `steps: ["End the turn"]`, score 3.5 (hand traps held). Faris's own text gives at least
   "discard Malicious → SS Faris → place a Vision HERO; banish Malicious → SS Malicious", so two
   bodies and a Link are reachable. Either the search never found Faris's hand effect, or every
   line scored below passing. `log.txt` in `data/line_jobs/<id>/` is empty and the result has no
   root-action count, so it is impossible to tell which. Suggest: report the number of legal root
   actions and the best non-pass line's score even when passing wins.
   Same again for hand `[Winged Kuriboh Sabatiel LV10, Masked HERO Furnace, Ash, Fuwalos, Dominus]`
   (deck "D-HERO Masked Change"): best line "End the turn", score **4.5**, vs 3.5 for passing with
   the Faris hand. The extra point suggests Sabatiel (it has an opponent's-turn Quick Effect) is
   tagged as a held hand trap, so using it as the deck's main starter (reveal → search Fusion
   Destiny) is scored as a loss. Starters with a defensive mode need to be excluded from
   "hand traps held", or the score should compare against the board they enable.
   The second line from the same job: `"Activate Mulcharmy Fuwalos"` on your own turn 1, then Furnace
   adds Polymerization and discards that same Polymerization — the search wastes rollouts on
   moves no player would make.
   Third case, **deep** depth: hand `[Destiny HERO - Malicious, Destiny HERO - Dreadnought Servant,
   Terraforming, Ash, Fuwalos]`, deck "D-HERO Link Fusion". Best line again "End the turn" (2.5).
   The runners-up (2.44) stop half-way: Terraforming → Dark City → search, but Dreadnought Servant
   is *Set as a monster* instead of Special Summoned by its own effect (Field Spell face-up), and
   the line has no "End the turn" step, so it looks truncated. Development that is merely
   unfinished scores below passing, which is the core bias: any partial line loses to holding cards.
3. **Step log omits selections.** Link and Fusion steps often list one material, e.g.
   `"Special Summon Xtra HERO Cross Crusader", "Select to Link Material: Destiny HERO - Malicious (field)"`
   (Link-2), `"Select to Fusion Material: Masked HERO Dusk Crow (field)"` for Contrast HERO Chaos
   (needs 2 "Masked HERO"), and Dusk Crow's search target is not shown before Furnace appears.
   Bare `"Yes"` steps (Dreadmaster's optional revive) have no context. Lines can't be replayed by a
   human from the log alone.
4. **Odd self-targeting in a best line.** `"Activate Contrast HERO Chaos", "Select: Contrast HERO Chaos (field)"`
   (negating its own effects) appears in the top line for the baseline hand. Harmless for scoring,
   but it shows the line is not pruned of pointless actions, and `Xtra HERO Infernal Devicer` is
   summoned at the end of lines just to be there.
4b. **Engine findings that changed the decks (working as intended, recorded for context).**
   - "D-HERO Link Fusion": no line in any run used Proxy F Magician, I:P Masquerena, S:P Little
     Knight or Wonder Driver; Doom Overlord's and Fusion Destiny's DARK-HERO locks close them off.
   - "D-HERO Branded", hand `[Branded Fusion, Doom Overlord, Ash, Fuwalos, Dominus]`: the best line
     (Destro-Dogma, Dangerous, Dusktopia) keeps Branded Fusion in hand; the Branded route only won
     from the Aluber hand.
   It would help if a result could say "card X was never used in any line", as a deck-tuning signal.
4c. **"live" counts a card in the wrong location.** Deck "D-HERO Fiendsmith", hand
   `[Fiendsmith Engraver, Doom Overlord, Ash, Fuwalos, Purulia]`, deep: the best line lists
   `Lacrima the Crimson Tears` (on the field) as live, but its Quick Effect works only "if this
   card is in your GY". It only becomes live if something sends it there (e.g. Destroyer Phoenix
   destroying it). Liveness should check the effect's location condition.
4d. **Normal vs deep give different answers for the same hand.** The same hand at normal depth
   returned a pure D-HERO line (5.0) as best, with Engraver used only to search Fiendsmith in
   Paradise; deep found the merged Fiendsmith → D-HERO line (5.61). Worth stating in the tool
   description that normal can miss cross-engine lines, or seeding the search with
   "play the lock-free engine first" orderings when the deck has Special Summon locks.
4e. **Pointless own-board negation.** `"Activate Fiendsmith's Desirae", "Select: Fiendsmith's
   Agnumday (field), Fiendsmith's Sequence (field)"` (negating its own Links) appears in a scored
   line, the same pattern as Contrast HERO Chaos in item 4.
5. **elapsed/estimate.** `estimate_minutes: 1` for normal depth, actual `elapsed_s` 53–95 s; fine,
   but with 2–3 jobs submitted together they appear to run concurrently and slow each other
   (95 s). No queue position is reported.

### find_links

6. **Oversized output.** `find_links(decklist=<41-card reference list>, limit=15)` returned ~20k
   tokens. Most of it is `your_deck_reaches`, where Reinforcement of the Army alone produces
   "(no archetype) count 245" plus Six Samurai, Noble Knight, Ninja, Junk, Battlin' Boxer,
   Amazoness, Heroic, Tellarknight, Phantom Knights and Gouki entries, none relevant to a HERO deck.
   Generic searchers should be collapsed into one line ("RotA reaches 400+ Warriors").
7. **Bridges ignore the deck's own locks.** Bridges to Gem-, Shaddoll, Metalfoes, Red-Eyes,
   Memento, Predaplant, Frightfur come from Winged Kuriboh Sabatiel LV10 searching any "Fusion"
   Spell, but Sabatiel's own lock ("cannot Special Summon from the Extra Deck, except HERO
   monsters") makes those fusions unusable. `deck_locks` lists the lock, yet bridges don't apply it.
8. **Missed lock: Branded Fusion.** `find_links(cards=[Fallen of Albaz, Branded Fusion, Aluber,
   Fusion Destiny, Destiny HERO - Malicious, Destiny HERO - Doom Overlord])`: `deck_locks` has Fusion
   Destiny and Doom Overlord but not Branded Fusion's "You cannot Special Summon from the Extra
   Deck, except Fusion Monsters, the turn you activate this card". The parser seems to only catch
   "for the rest of this turn" / "the turn you activate this effect" wording.
9. **Albaz Fusions missing from extra_deck_options.** Same input: Lubellion ("1 DARK monster +
   Fallen of Albaz"), Mirrorjade, Brigrand etc. are not listed; Alba-Lenatus and Khaos Starsource
   Dragon are. Either the material parser misses reversed order / named materials, or `limit=6`
   cut the list; there is no "N more" indicator, so the caller can't tell.
10. **Extra Deck options by type only produce dead suggestions.** Elemental HERO Nova Master,
    Great Tornado, The Shining, Absolute Zero, Escuridao, Wake Up Your Elemental HERO are offered
    for a deck with no Elemental HERO main-deck monster (Xtra HERO Links are tagged
    "Elemental HERO" by YGOProDeck, which is probably what matches). Fighting Flame Dragon, Filia
    Regis and Curse of Dragon need Dragons the deck doesn't have.
11. **Weak or non-bridges.** "Reaches your" via a *cost* that banishes a HERO from the GY
    (Masked HERO Koga, Elemental HERO Divine Neos, Magistery Alchemist) is not a way into the deck.
    Evil Mind is listed as a top searcher with evidence `"4+: Add 1 HERO monster..."` but the
    condition "If you control a Fiend monster" and "4+ monsters in your opponent's GY" is cut, so
    it looks live on turn 1 when it is not.
12. **`reaches_your` is alphabetical and capped at 6.** Every entry shows "Contrast HERO Chaos,
    Destiny HERO - Dark Angel, Denier, Destro-Dogma, ..." regardless of what the card actually
    fetches best; useful targets (Malicious, Doom Overlord) are hidden. A count plus the most
    relevant targets would help.
13. **Fusion Summon spells/effects still not modelled** (known gap): Fusion Destiny, Polymerization,
    Branded Fusion, Lubellion, Dusktopia and Proxy F Magician — the actual engine of every deck here —
    never show up as links.

### meta_snapshot / meta_inclusion

14. **"Destiny HERO" deck type unknown, no near miss.** `meta_inclusion(deck_type="Destiny HERO")`
    → 0 lists and `similar_deck_types: []`; `deck_type="HERO"` suggests "HEROs". The fuzzy match
    should find "HEROs" from "Destiny HERO" too.
15. **Recent tops missing.** The Dresden WCQ Top 8 list (2026-10-17, YGOProDeck 739651) is not in
    the data: `meta_inclusion(card="Destiny HERO - Doom Overlord")` → playing 0 of 672 lists. The
    window says `2026-08-23 .. 2026-10-18`, so a 10-17 event should be in range; either Yugioh Meta
    hasn't ingested it or it was dropped as unmatched (`unmatched_lists: 18`). No way to see which.
16. **legal_now is nearly useless right after a list change.** `legal_now: 1` of 672 lists (every
    deck type 0) because of Called by the Grave / Triple Tactics Talent / Albion. True, but it would
    help to also report "legal after N swaps" or which card blocks most lists.

### card_rulings

17. **`with_card` matches on the Q&A's card list, not on the interaction.**
    `card_rulings("Dark City at Midnight", with_card="Destiny HERO - Dreadmaster")` returned a
    Break the Destiny Q&A about "specifically lists" wording, which says nothing about Dark City's
    "treated as a Special Summon with Clock Tower Prison" summoning Dreadmaster. The interaction the
    decks rely on is therefore unverified, but the result looks like an answer.
17b. **Crash on a fresh card.** `card_rulings("Destiny HERO - Destro-Dogma", query="Fusion Summon")`
    and the same without `query` both return
    `"YGOResources request failed (ValueError: invalid literal for int() with base 10: '0.5')"`.
    Also `card_rulings("Fiendsmith's Requiem", with_card="Lacrima the Crimson Tears")`, while
    `card_rulings("Fiendsmith's Sanct")` works. Likely cause: `rulings.py:160` sorts
    `faqData.entries` with `key=lambda kv: int(kv[0])`, and some cards have a fractional FAQ entry
    key such as `"0.5"`. Sort with `float()` instead. The `except Exception` at line ~149 then
    reports it as "YGOResources request failed", which blames the network for a parsing bug.
18. **Oversized omnibus Q&As without `with_card`.** `card_rulings("Fusion Destiny")` returns the
    Prohibition/Psi-Blocker and Macro Cosmos omnibus entries with 40–70-card `cards` lists;
    `card_rulings("Destiny HERO - Doom Overlord")` returns only a Ghost Belle omnibus whose answer
    text never mentions Doom Overlord. Suggest ranking Q&As whose question/answer names the card
    above ones that only list it, and trimming `cards` to a count.

### validate_deck / card_lookup

19. **validate_deck output is large** (every card echoed with zone, type, limit; ~4k tokens for 70
    cards). A `compact` mode (problems + totals + resolved_names) would cover most calls.
20. **Alternate-art passcodes are silently normalised.** The YGOProDeck page uses Ash Blossom
    14558128; validate_deck reports 14558127 with no `resolved_names`/alt note. Harmless for
    legality, worth a note when mapping a reference list.
21. **archetype tags are inconsistent** (from YGOProDeck): Xtra HERO Links and Contrast HERO Chaos
    carry archetype "Elemental HERO", Masked HERO Dusk Crow / Furnace / Dark Law carry "HERO",
    D Cubed carries "Destiny HERO". This feeds problem 10.

### Data gaps (not tool bugs)

- Skyborne Blue Cularsaw has no engine script yet (see 1).
- YGOResources has no Q&A for Lubellion × Mirrorjade, Mask Change × Furnace, or Wonder Driver
  beyond FAQ text, so those steps stay "unverified".

## Second run: Artmage Power Patron (2026-10-20)

Built "Artmage Power Patron" (tcg_advanced, 2026.10 TCG, data as of 2026-10-20T21:00Z, YGOProDeck
db 147.37), saved as `data/decks/artmage-power-patron.tcg_advanced.ydk`. New problems only; known
ones (17b rulings crash, step logs dropping materials) are noted where they hit again.

### Data / legality

22. **Cards every TCG top plays are marked "not TCG-released".** Artmage Varnish -Alteration-
    (74011784), Artmage Vandalism -Assault- (1122030) and Artmage Pact -Awakening- (23599634) have
    `tcg_date: null` and `formats: ['OCG', 'Master Duel']` with no card_sets in `data/cards.json`,
    so `archetype` / `validate_deck` / `finalize_deck` reject them. Yet `meta_inclusion(deck_type=
    "Artmage")` shows each at 100% of 21 lists, all labelled "Tournament Meta Decks (TCG)" from WCQ
    Regionals (e.g. Nimes 2026-09-13 Top 8, Rende 2026-09-27 2nd), and gives them no legality flag
    (no `limit_now`, no `legal`). One of the two is wrong, and the user can't tell which.
    - `meta_inclusion` / `meta_snapshot` staples should carry the same `legal` / `why_not` as
      `validate_deck`, so a card the validator will reject is visible in the meta table.
    - When a card has no TCG date but shows up in TCG-tagged tournament lists, say so
      ("no TCG set in YGOProDeck; played in N TCG tops") instead of a flat "not TCG-released".
      Cross-checking the Project Ignis TCG cdb/lflist would settle most cases.
    - The saved deck excludes the three cards; its notes give the swap if they're confirmed legal.

### find_links

23. **Special Summon locks missed.** `deck_locks` reports only Acropolis. It misses:
    - Artmage Power Patron: "You cannot Special Summon from the Extra Deck, except Fusion Monsters"
      (OCG FAQ: a Continuous Effect that applies in the Monster Zone). It is the archetype's
      namesake lock and affects every Synchro/Xyz/Link in the Extra Deck.
    - Artmage Movement -Pedigree- / Peripeteia -Turmoil-: "cannot Special Summon from the Extra
      Deck the turn you activate either of this card's effects, except Fusion Monsters".
      Peripeteia was even listed in `into_your_deck`/bridges without its lock.
    - Beyond the Pendulum: "cannot activate monster effects" unless you Pendulum Summon. That isn't
      a Special Summon lock, but it's the same class of turn-wide restriction and kills a combo.
    Likely cause: the lock parser expects "cannot Special Summon for the rest of this turn, except"
    and misses "cannot Special Summon from the Extra Deck, except" and "the turn you activate".
24. **False `breaks_deck_locks` on every Extra Deck option.** Nerva, Azamina Moa Regina, Skyborne
    Blue Cularsaw, Galaxy-Eyes Solflare Dragon and others are all flagged as breaking Acropolis, whose
    lock explicitly exempts "or from the Extra Deck". The exception clause isn't parsed. The same
    happens for main-deck cards that only Special Summon from the Extra Deck.

### card_rulings

25. **17b hits most of this engine.** The `int('0.5')` crash also hits Nervedo the Shadebeast Power
    Patron, Vidolium the Unstable Power Patron of Unity and Artmage Non-Finito, while Artmage Power
    Patron, Medius the Pure, Acropolis and Theorealize Past Lull work. So the Nervedo × Pendulum
    Treasure ("added to your Extra Deck face-up") and Nervedo-in-Pendulum-Zone × Past Lull ("control
    an Artmage card") interactions can't be checked from the tool.

### find_lines / line_result

26. **Engine names differ from card-DB names.** The hand was given as "Kuriboh - Multiply!"
    (YGOProDeck/validate_deck name), but line_result reports it as "Multiplying Kuriboh!" in `hand`,
    `steps`, `board` and `live`. Map engine names back to DB names (or show both) so results match
    the decklist.
27. **A face-down Set monster counts as "live".** Hand `[Acropolis, Impasto, Vidolium, Kuriboh -
    Multiply!, Fuwalos]`: three of four lines Set Kuriboh face-down and list it under `live`.
    Its effects are a hand effect (Special Summon itself) and Quick Effects it can't use while face-down,
    so Setting it throws away the interruption it would have had in hand. The probe turn or
    card_tags treat "on field" as live regardless of face-down.
28. **Lines use cards drawn mid-combo, without saying so.** Artmage Finmel's "then you can draw 1
    card" draws from the shuffled deck. In two lines, cards that were never in the hand or searched
    then appear: Medius Normal Summoned, Graflare in `hand_left`, a second Past Lull. The line can't
    be reproduced from the 5-card hand, and `steps` doesn't show what was drawn. Log draws
    ("Draw: X"), and flag or down-weight lines that depend on them.
29. **More step-log gaps** (extends 2): "Activate Nervedo" doesn't say whether it's the Pendulum
    activation or the monster effect; Acropolis activations omit the discarded Spell/Trap and the
    declared name; Non-Finito's alternative summon omits the discard; Artmage Power Patron's second
    "Activate" (GY search) omits what it added. Line 1 of the Acropolis hand shows
    "Use Artmage Peripeteia -Turmoil-'s effect" for a card that was never shown being added.
30. **Runtime estimates ignore concurrency.** Three jobs submitted together (2 normal, 1 deep):
    the normal ones took 185 s and 196 s against a 1-minute estimate. `line_result` kept reporting
    `estimate_minutes: 2` for the deep one, which finished in 356 s. `log.txt` stayed empty the whole
    time, so there was no progress to show.
31. **Deep search still wastes rollouts on own-turn hand traps.** Deep hand `[Artmage Power Patron,
    Medius, Pendulum Treasure, Ash, Fuwalos]`, line 6: "Activate Mulcharmy Fuwalos" and "Activate Ash
    Blossom" on your own turn 1 with nothing to respond to, then Set Medius face-down (losing its
    on-summon search). Same class as problem 2. Deep's best line (5.8) was the same shape as the
    normal-depth lines: Medius → Artmage Power Patron → Non-Finito, Pendulum Treasure → Nervedo →
    second Power Patron. Neither depth found a Nerva or Diactorus end board from this hand.

## Third run: Fairy Tail (Invoked/Magistus) (2026-10-20)

Built "Fairy Tail Competitive" (tcg_advanced, 2026.10 TCG, data as of 2026-10-20T21:00Z, YGOProDeck
db 147.37), saved as `data/decks/fairy-tail-competitive.tcg_advanced.ydk`. New problems only; known
ones are noted where they hit again.

### search_cards / card_lookup

32. **Numeric `text` / `pattern` rejected.** `search_cards(text="1850")` and `pattern="1850"` fail
    with a pydantic `string_type` error (`input_value=1850, input_type=int`). The schema leaves
    `text`/`pattern` (and the other filters) untyped, so the client sends a bare number. Declare
    them as `string` (and the numeric ones as `integer`) in the tool schema.
33. **Dangling quoted names aren't flagged.** Fairy Tail - Matchgiru and Fairy Tail Ball both say
    "add 1 ... or 1 \"Fairy Tale Tails\"", but no such card exists: `card_lookup("Fairy Tale Tails")`
    → `match: none`, and `search_cards(name="Fairy Tale")` finds only an unrelated Field Spell. It is
    probably a YGOProDeck typo for "Fairy Tail Tales" (a real Fairy Tail Continuous Spell). The engine's
    prompt text has the same typo. `card_lookup`'s `mentions` should mark quoted names that don't
    resolve to a card, and suggest the closest one.

### meta_inclusion

34. **Unmatched meta card names (extends 26).** Both Fairy Tail deck types list "Empire of Endymion"
    at 100% with `unmatched_name: true`, no passcode and no legality. The DB name is "Endymion
    Empire" (34041788). The engine uses the meta spelling: the hand was given as "Endymion Empire"
    but line_result echoes "Empire of Endymion" everywhere. One alias table (DB ↔ engine ↔ Yugioh
    Meta) would fix 26 and this one.

### find_links

35. **Locks aren't checked against your own Extra Deck.** `deck_locks` lists Matchgiru / Once Upon
    a Fairy Tail ("cannot Special Summon ... except Spellcaster monsters") and Genia of the Ring
    ("from the Extra Deck ... except Spellcaster"). It doesn't say which of the deck's own Extra
    Deck monsters those locks block: Invoked Sorath (Pyro), Invoked Baybarron (Illusion),
    Hyperinvoked Aeon (Fiend) and S:P Little Knight (Warrior). That is the real sequencing
    constraint of the deck. Only outside suggestions get `breaks_deck_locks`. All 8
    `extra_deck_options` (Aiwass, Azamina, Cularsaw, ...) break the locks, so lock-compatible
    options should rank first.

### card_rulings

36. **17b also hits Magistus Chorozo** (`int('0.5')`). That leaves unverified the step the engine
    relies on most: Chorozo's contact summon using a Magistus monster equipped in the Spell & Trap
    Zone (via Spenta or Endymion) as the "Fusion, Synchro, Xyz, or Link" material. Problem 18 also
    hit again: `card_rulings("Tails of the Fairy Tails")` returns only two omnibus Q&As (Soul
    Exchange / Solemn Judgment lists, around 80 cards each).

### find_lines / line_result

37. **Scoring treats extenders and soft effects like hard negates.** On the deep hand `[Luna, Regulus,
    Ash, Fuwalos, Lacrima]`, line 1 (5.27) ends on Wiccat + Luna + a Set Once Upon a Fairy Tail +
    a Set Lacrima, and all four count as `live`. Line 4 (5.04) ends on Zoroa, the Magistus
    Verethragna (monster-effect negate + destroy) with Ninaruru and Artemis equipped as fuel, plus
    Luna, Lacrima and Ball, and still holds Ash, Fuwalos, Snow and Regulus. Line 4 is clearly the
    stronger board but ranks fourth. Once Upon (an extender) and Luna's bounce (which the opponent
    can stop by sending a same-name card) shouldn't score like a Zoroa negate.
38. **Normal depth misses the archetype's own payoff.** On hand `[Ball, Instant Fusion, Ash,
    Purulia, Droplet]`, no line made Teller of Fairy Tails (the deck's Quick negate). Line 1 adds
    Tails of the Fairy Tails and ends with it in `hand_left`. Line 6 again activates Purulia and
    Ash on your own turn 1 (problem 31). Problem 30 hit again: the normal jobs took 194 s and 255 s
    against a 1-minute estimate, while queued behind the Artmage jobs.

## Fourth run: Sky Striker Radiant Typhoon (2026-10-20)

Built "Sky Striker Radiant Typhoon" (tcg_advanced, 2026.10 TCG, data as of 2026-10-20T21:00Z, YGOProDeck
db 147.37), saved as `data/decks/sky-striker-radiant-typhoon.tcg_advanced.ydk`. New problems only.

### find_lines / line_result

39. **"Live" ignores activation conditions (Sky Striker's empty Main Monster Zone).** Widow Anchor, Hornet
    Drones, Shark Cannon and Linkage all need "no monsters in your Main Monster Zone". Hand `[Raye, Engage!,
    Widow Anchor, Hey, Space Trunade!, Ghost Ogre]`, line 1 ends with a face-down Raye in the MMZ and
    still lists Linkage + Widow Anchor as `live`. Line 2 ends with Shizuku in an MMZ beside Zero in the EMZ
    and lists Widow Anchor + Hornet Drones as `live`. The probe should test that the card can be activated
    from the end state, not just that it's Set.
40. **Fuwalos counted as a held hand trap when it can't be used.** Fuwalos needs "you control no cards", but
    every Sky Striker line that ends with a Set card or monster still scores it in `hand_left`. Same
    class as 27: hand traps should be checked against their own activation condition.
41. **Mandate scored live with no way to use it.** In the deep Eldam/Linkage/Vision hand, the set
    Radiant Typhoon Mandate is `live`, but its effects need 3 Quick-Plays in the GY (1 there) or an MST
    activation (none in hand or Set).
42. **Engine name "Spatial Trunade" ≠ DB name "Hey, Space Trunade!"** (extends 26/34). Its steps also say
    "Select to return to the Deck: Raye (hand)" for what the card text calls placing on the bottom of the
    Deck.
43. **Extends 2/29: whole summons are unlogged.** Shizuku, Hayate, Amatsu and Kagari appear as "Special
    Summon X" with no material and no summoning card. "Use Kagari's effect" / "Use Zero's effect" often omit
    what was added. The deep line 1 never shows Vision's discard. Without these the Link chains (Zero
    "Cannot be used as Link Material", Kagari/Shizuku once-per-turn) can't be checked.

### find_links

44. **"No monsters in your Main Monster Zone" isn't treated as a lock-class condition.** `deck_locks`
    lists only Linkage's Extra Deck lock. It doesn't flag that every Radiant Typhoon main-deck monster
    turns off Engage/Widow Anchor/Hornet Drones/Shark Cannon. That conflict is what decides this
    pile. It also misses the real bridge the engine found (Eldam + Swen → Camellia, "2 Effect Monsters",
    clearing the MMZ). `extra_deck_options` listed only non-Sky Striker Xyz/Fusions.
45. **False `breaks_deck_locks` on Shizuku** (extends 24): Sky Striker Ace - Shizuku is flagged as breaking
    Linkage's lock "except Sky Striker Ace monsters", which it satisfies.

### card_rulings

46. **17b variant `int('1.5')`.** Radiant Typhoon Vision and Radiant Typhoon Mandate fail with
    `invalid literal for int() with base 10: '1.5'`. Also: the generic Q&A 24006 (≈150 cards listed)
    comes back in full on every related card (Fonix, Vortex), costing several thousand tokens per call.
    Trim `cards` or collapse Q&As already shown.
### Fairy Tail run, follow-up: find_links (2026-10-20)

47. **find_links never surfaced Verre or Genni, the Maid of Endymion, although both are core
    Endymion support for this deck.** Three separate causes, confirmed against `cards.sqlite`:
    - **`TREATED` keeps only the first archetype.** `links.py:45` matches only the first quoted name
      in `always treated as a "Magistus" and "Witchcrafter" card`. Verre Magic - Lacrima of Light
      therefore isn't Witchcrafter, so Verre's search ("add 1 Witchcrafter Spell/Trap") never links
      to Lacrima. Magia Magic - Thunder of Judgment ("Magistus" and "Endymion") loses its second tag
      the same way.
    - **"1 monster that mentions it" loses the mention.** Endymion Empire's "Add 1 Regulus, the
      Prince of Endymion or 1 monster that mentions it" is stored as `{"names": [Regulus]}` plus a
      bare `{"kinds": ["monster"]}`. The bare filter has specificity 0 and is skipped, so Empire →
      Verre (which mentions Regulus) is never a link. The pronoun "it" should resolve to the quoted
      name before it, giving `{"mentions": [...]}`. The same wording is common ("a card that
      mentions it").
    - **Your own archetypes are sorted last, then truncated.** In `linkfind.py:202`,
      `your_deck_reaches` sorts groups by `(tag in deck_tags, -count)` and then cuts at `[:limit]`.
      Support from your own archetypes that the list doesn't run yet, here the "Endymion" group
      (Lacrima's summon reaches Verre and Genni), lands after the 272-card "(no archetype)" group and
      the Magician, Charmer and Gravekeeper groups, and is dropped. Missing cards from your own
      archetype should come first, with their own section if needed.
    - The two maids did appear once, under `bridges` → engine "Witchcrafter" ("your cards reach it"),
      with no evidence of which card reaches them. That reads as a side engine, not as Endymion
      cards the deck should run.
    - The meta data didn't help either. The 14 TCG Fairy Tail tops play Witchcrafter Genni
      (Yugioh Meta id 60c2b3ad…, the 2019 card), and `meta_inclusion` shows Genni, the Maid at 0
      and Verre at 1 of 672 lists. The OCG Magistus Fairy Tail lists in `ygom_top_decks_60d.json`
      play both maids. An "OCG tops play X that TCG tops don't" hint would have caught it.
    - **Fixed (uncommitted, 2026-10-20).** `links.py`: `TREATED` and `treated_as()` keep every quoted
      name ("Magistus" and "Witchcrafter"; "Zubaba", "Gagaga", "Gogogo", and "Dododo"), which
      corrects 15 cards. `_resolve_it()` turns "that mentions it" into the quoted name before it.
      `linkfind.py`: new `your_archetypes_unplayed` section, listing members of your archetypes you
      don't run, with `reached_by` (your add/summon/Set effects that fetch them, costs excluded, no
      "from your Deck" for Extra Deck monsters), `reaches_your` and `reaches_unplayed`, ranked with a
      two-way-link bonus. `your_deck_reaches` now lists your own archetypes first. Link tables were
      rebuilt in `data/cards.sqlite`. On this deck Verre ranks 3rd, with Endymion Empire and Lacrima
      as evidence, and Genni 11th (via Lacrima, and it fetches Verre). The MCP server needs a restart
      to use the new code.

## Fix pass (2026-10-21): find_links, locks, card_rulings, meta

**Fixed**
- **card_rulings**
  - 17b/25/36/46: fractional FAQ keys ("0.5", "1.5") sort as numbers, so they no longer crash.
  - Parsing bugs are now reported as bugs, not as network errors.
  - 17/18/46: Q&As whose text names the card(s) rank first (`names_in_text`). Omnibus `cards` lists are cut to 8 names plus a count. With `with_card`, the note says when no Q&A discusses both cards.
- **Locks**
  - 8/23: locks with a type-only filter ("except Fusion Monsters": Branded Fusion, Artmage) are no longer dropped.
  - The except-clause stops at ", also" or ", the turn ...", which fixes Linkage's junk filter and the false Shizuku break (45).
  - 24: "except ... or from the Extra Deck" now exempts Extra Deck summons. `non-"X"` locks (Vaylantz) keep X.
  - 23: "you cannot activate monster effects" is listed as a restriction.
  - 44: "no monsters in your Main Monster Zone" is listed as a condition, with the deck's main-deck monster count.
- **find_links**
  - Fairy Tail #1 and 11: a fetch is add, Special Summon, Set or Fusion Summon, and never a cost. An Extra Deck monster can't be fetched from the hand or Deck. One rule now covers every section.
  - 13: Fusion Summon effects are links ("lists a 'Destiny HERO' monster as material" matches the Fusions that list one). Fusion Destiny, Branded Fusion and Artmage now fetch their Fusions.
  - 7: a bridge's own lock filters its targets, so Sabatiel no longer bridges to non-HERO Fusions. Engines your deck's locks would mostly block are marked `mostly_blocked_by_deck_locks` and ranked last.
  - 35: `deck_locks` lists which of your own cards each lock blocks; on Fairy Tail, Matchgiru blocks 12. Lock-compatible `extra_deck_options` rank first.
  - 6: output is now 16–20k characters on these decks (was 24–32k, about 70k on the first run). Changes behind that:
    - searchers by Attribute/Type collapse into `generic_searchers`, one line each;
    - examples are names only;
    - one evidence line per item;
    - `more_not_shown` counts what was cut.
  - 12: `fetches_your` lists the most-played targets first, plus `fetches_count`.
  - Fairy Tail #4: Attribute/Type-only fetches can't outrank named searchers on hit count.
  - 11: evidence keeps the effect's condition for bullet effects (Evil Mind's "If you control a Fiend monster").
  - Sabatiel's search no longer picks up the later lock's `except "HERO"` as an exclusion.
- **Meta**
  - 14: deck-type suggestions match by word ("Destiny HERO" or "D-HERO" finds "HEROs").
  - 16: `most_common_blockers` names the cards that make recent lists illegal now.
  - 26/34: Yugioh Meta aliases (Empire of Endymion, Stellarnova Binding, Arrow of Regulus, Reeshaddoll Wendikuruhu).
- **card_lookup**
  - 33: `unresolved_mentions` flags quoted names that match no card, with the closest names ("Fairy Tale Tails" → "Fairy Tail Tales").

**Renamed in find_links output:** `reaches_your` → `fetches_your`, `reached_by` → `fetched_by`, `reaches_unplayed` → `fetches_unplayed`.

**Not changed:** 9 and 10 are only partly addressed. Materials are still matched by type: lock-compatible options now rank first and nothing is hidden (`more_not_shown`), but whether a summon is achievable isn't modelled. The find_lines / line_result items (1–5, 4c–4e, 40–43) and data gaps (15, El Shaddoll Meshachrer, Shadowreaver Knight 21, Layer 19) are outside these files.

## Live use: Sky Striker RT Vision hand (2026-10-21)

48. **find_lines builds lines on draws it can see in advance.** `wsl/line_finder.py` (in ygo-sim) stacks only
    the 5 hand cards and writes the rest of the Main Deck in the saved .ydk order with `shuffle1=False`, so
    every mid-line draw is fixed and visible to the search. Hand `[Engage!, Forbidden Droplet, Radiant
    Typhoon Vision, Linkage!, Droll & Lock Bird]` (quick depth): the best line used Reinforcement of the
    Army and Radiant Typhoon Mandate, which Vision drew because they were the last cards in the file. The
    user didn't draw them, and the line fell apart at "use Reinforcement to add Raye". The step log never
    names drawn cards (`"Yes: Draw 1 card?"`), so they look like hand cards.
    Fix (engine side): shuffle the non-hand cards with a per-restart seed, so restarts see different
    draws; record each draw in the step log (`"Draw: <card>"`) and as `drawn` per line; prefer, or
    score separately, lines that don't use drawn cards. Skill updated meanwhile: drawn cards are
    "if you draw X" steps, never part of the line.

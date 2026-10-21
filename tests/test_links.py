"""Link extraction rules and find_links, on hand-written texts and the pinned fixture."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ygoformat import carddata
from ygoformat.linkfind import find_links
from ygoformat.links import extract_card, parse_descriptor, parse_materials

FIX = Path(__file__).parent / "fixtures"
NAMES = frozenset({"Polymerization", "Redox, Dragon Ruler of Boulders", "X-Head Cannon", "Y-Dragon Head",
                   "Z-Metal Tank", "Rescue-ACE Hydrant", "Destiny HERO - Malicious"})


def effects(text):
    return extract_card(text, NAMES)["effects"]


def test_archetype_search():
    (e,) = effects('When this card is Normal or Special Summoned: You can activate 1 of these effects.\n'
                   '● Add 1 "HERO" monster from your Deck to your hand.')
    assert e["verb"] == "add" and e["zones"] == ["Deck"]
    assert e["filter"] == {"archetypes": ["HERO"], "kinds": ["monster"]}
    assert "optional 'When' trigger (can miss the timing)" in e["flags"]


def test_named_card_with_comma_and_name_lists():
    (e,) = effects('Special Summon 1 "Redox, Dragon Ruler of Boulders" from your Deck.')
    assert e["filter"] == {"names": ["Redox, Dragon Ruler of Boulders"]}
    (e,) = effects('You can Special Summon 1 "X-Head Cannon", "Y-Dragon Head", or "Z-Metal Tank" from your Deck.')
    assert e["filter"]["names"] == ["X-Head Cannon", "Y-Dragon Head", "Z-Metal Tank"]


def test_stats_types_and_exclusions():
    (e,) = effects("Add 1 Level 4 or lower Warrior monster from your Deck to your hand.")
    assert e["filter"] == {"level": [0, 4], "races": ["Warrior"], "kinds": ["monster"]}
    (e,) = effects('You can Special Summon 1 "Batteryman" monster, except "Batteryman Charger", from your hand or Deck.')
    assert e["filter"]["archetypes"] == ["Batteryman"] and e["filter"]["exclude"] == ["Batteryman Charger"]
    assert e["zones"] == ["hand", "Deck"]
    (e,) = effects("Special Summon 1 Fish, Sea Serpent, or Aqua monster from your GY.")
    assert set(e["filter"]["races"]) == {"Fish", "Sea Serpent", "Aqua"}
    (e,) = effects('Special Summon 1 non-Ritual "Prediction Princess" monster from your Deck.')
    assert e["filter"]["not_kinds"] == ["ritual"]
    (e,) = effects('Special Summon 1 " Dragonmaid " monster from your GY.')
    assert e["filter"]["archetypes"] == ["Dragonmaid"]


def test_cost_vs_effect_and_hard_opt():
    banish, add = effects('You can banish 1 Fish monster from your hand or GY; add 1 "Ghoti" monster from your Deck '
                          'to your hand. You can only use this effect of "X" once per turn.')
    assert banish["cost"] is True and add["cost"] is False  # before ';' is cost, after is effect
    assert "hard once per turn" in add["flags"]


def test_self_summon_is_not_a_link():
    assert effects("You can Special Summon this card from your hand.") == []


def test_lock_clause():
    (lk,) = extract_card('Fusion Summon 1 Fusion Monster, also for the rest of this turn after this card resolves, '
                         'you cannot Special Summon monsters, except DARK "HERO" monsters.', NAMES)["locks"]
    assert lk["scope"] == "all" and lk["filter"] == {"archetypes": ["HERO"], "attributes": ["DARK"], "kinds": ["monster"]}
    assert lk["evidence"].startswith("you cannot Special Summon")
    (lk,) = extract_card("you cannot Special Summon monsters from the Extra Deck, except Link Monsters.", NAMES)["locks"]
    assert lk["scope"] == "extra" and lk["filter"] == {"kinds": ["link"]}


def test_materials():
    comps = parse_materials('1 Level 6 or higher "HERO" monster + 1 "Destiny HERO" monster', NAMES)
    assert [c["filter"] for c in comps] == [{"archetypes": ["HERO"], "level": [6, 99], "kinds": ["monster"]},
                                           {"archetypes": ["Destiny HERO"], "kinds": ["monster"]}]
    comps = parse_materials("1 Tuner + 1+ non-Tuner monsters", NAMES)
    assert comps[0]["filter"]["kinds"] == ["tuner"] and comps[1]["filter"]["not_kinds"] == ["tuner"]
    comps = parse_materials('"Elemental HERO Avian" or "Elemental HERO Burstinatrix" + 1 "HERO" monster', NAMES)
    assert comps[0]["filter"]["names"] == ["Elemental HERO Avian", "Elemental HERO Burstinatrix"]
    assert parse_materials("Must be Special Summoned with \"Mask Change\".", NAMES) is None


def test_descriptor_card_name_vs_archetype():
    assert parse_descriptor('"Polymerization"', NAMES) == {"names": ["Polymerization"]}
    assert parse_descriptor('"Polymerization" Spell', NAMES)["archetypes"] == ["Polymerization"]


@pytest.fixture(scope="module")
def con():
    con = carddata.connect(":memory:")
    dump = json.loads((FIX / "genesys_subset.json").read_text(encoding="utf-8"))
    carddata.build(con, dump, (FIX / "tcg_lflist.conf").read_text(encoding="utf-8"), {},
                   {"database_version": "fixture", "last_update": "2026-10-20"}, datetime(2026, 10, 20, tzinfo=timezone.utc))
    return con


DHERO = {"main": ["3 Destiny HERO - Malicious", "3 Destiny HERO - Dreadnought Servant", "3 Destiny HERO - Diamond Dude",
                  "Fusion Destiny"]}


def test_find_links_dhero(con):
    r = find_links(con, "genesys", decklist=DHERO, as_of="2026-10-20")
    into = {x["name"]: x for x in r["into_your_deck"]}
    assert "Elemental HERO Stratos" in into and "Elemental HERO Shadow Mist" in into
    assert "Destiny HERO - Malicious" in into["Elemental HERO Stratos"]["fetches_your"]
    # Stratos is WIND: Fusion Destiny's "except DARK HERO monsters" lock is flagged.
    assert any("Fusion Destiny" in b for b in into["Elemental HERO Stratos"]["breaks_deck_locks"])
    extra = {x["name"] for x in r["extra_deck_options"]}
    assert {"Destiny HERO - Destroyer Phoenix Enforcer", "Destiny HERO - Dystopia"} <= extra
    reach = {e.split(" (")[0] for g in r["your_deck_reaches"] for e in g["examples"]}
    assert "Polymerization" in reach  # Dreadnought Servant adds "Polymerization"
    assert any(b["engine"] == "Elemental HERO" for b in r["bridges"])
    assert r["deck_locks"][0]["card"] == "Fusion Destiny"


def test_find_links_respects_points_budget(con):
    deck = {"main": DHERO["main"] + ["Destiny HERO - Dark Angel"]}  # 3 + 100 points: nothing left
    r = find_links(con, "genesys", decklist=deck, as_of="2026-10-20")
    assert r["points"]["max_points_per_suggestion"] < 0
    assert r["into_your_deck"] == [] and r["extra_deck_options"] == []
    r = find_links(con, "genesys", decklist=deck, max_points=10, as_of="2026-10-20")
    assert "Destiny HERO - Destroyer Phoenix Enforcer" in {x["name"] for x in r["extra_deck_options"]}  # 7 points


def test_find_links_with_cards_and_bad_names(con):
    r = find_links(con, "tcg_advanced", cards=["Destiny HERO - Malicious"], as_of="2026-10-20")
    assert "Elemental HERO Stratos" in {x["name"] for x in r["into_your_deck"]}
    r = find_links(con, "tcg_advanced", cards=["D-HERO Malicous"])
    assert r["error"].startswith("input problems") and r["parse_errors"]


def test_treated_as_every_quoted_archetype():
    from ygoformat.links import treated_as
    assert treated_as('(This card is always treated as a "Magistus" and "Witchcrafter" card.)') == \
        ("Magistus", "Witchcrafter")
    assert treated_as('(This card is always treated as a "Zubaba", "Gagaga", "Gogogo", and "Dododo" card.)') == \
        ("Zubaba", "Gagaga", "Gogogo", "Dododo")
    assert treated_as('(This card is always treated as a "Witchcrafter" card.)') == ("Witchcrafter",)


def test_mentions_it_resolves_to_the_named_card():
    names = NAMES | {"Regulus, the Prince of Endymion"}
    by_name, by_mention, _ = extract_card(
        'When this card is activated: Add 1 "Regulus, the Prince of Endymion" or 1 monster that mentions it from '
        'your Deck to your hand, then you can Special Summon 1 Spellcaster monster from your hand.', names)["effects"]
    assert by_name["filter"] == {"names": ["Regulus, the Prince of Endymion"]}
    assert by_mention["filter"] == {"mentions": ["Regulus, the Prince of Endymion"], "kinds": ["monster"]}


def test_find_links_lists_own_archetype_cards_not_run(con):
    r = find_links(con, "genesys", decklist=DHERO, as_of="2026-10-20")
    unplayed = {x["name"]: x for x in r["your_archetypes_unplayed"]}
    assert "Destiny HERO - Dreadmaster" in unplayed  # a Destiny HERO the list doesn't run
    assert "Destiny HERO - Malicious" in unplayed["Destiny HERO - Dreadmaster"]["fetches_your"]
    assert not set(unplayed) & {"Destiny HERO - Malicious", "Destiny HERO - Diamond Dude"}  # already in the deck


# ---------------------------------------------------------------- locks, fusions, fetch rules (dry-run fixes)

def locks(text):
    return extract_card(text, NAMES)["locks"]


def test_lock_clause_ends_where_the_sentence_moves_on():
    # Linkage!: the old parser read past ", also" and produced a junk DARK/LIGHT filter.
    (lk, mmz) = locks('If you control no monsters in your Main Monster Zone: You cannot Special Summon monsters from the '
                      'Extra Deck for the rest of this turn after this card resolves, except "Sky Striker Ace" monsters, '
                      'also send 1 other card you control to the GY.')
    assert lk["scope"] == "extra" and lk["filter"] == {"archetypes": ["Sky Striker Ace"], "kinds": ["monster"]}
    assert mmz["scope"] == "empty_mmz"
    # Branded Fusion: the except clause comes before "the turn you activate this card".
    (lk,) = locks("You cannot Special Summon from the Extra Deck, except Fusion Monsters, the turn you activate this card.")
    assert lk["scope"] == "extra" and lk["filter"] == {"kinds": ["fusion"]}


def test_lock_extra_deck_exemption_and_non_archetype():
    (lk,) = locks('you cannot Special Summon monsters, except "Artmage" monsters or from the Extra Deck.')
    assert lk["scope"] == "main" and lk["filter"] == {"archetypes": ["Artmage"], "kinds": ["monster"]}
    (lk,) = locks('you cannot Special Summon non-"Vaylantz" monsters for the rest of this turn, except from the Extra Deck.')
    assert lk["scope"] == "main" and lk["filter"] == {"archetypes": ["Vaylantz"], "kinds": ["monster"]}


def test_later_lock_except_is_not_a_search_exclusion():
    (e,) = effects('add 1 "Polymerization" Spell or "Fusion" Spell from your Deck to your hand, and if you do, shuffle '
                   'this card into the Deck, also for the rest of this turn, you cannot Special Summon from the Extra '
                   'Deck, except "HERO" monsters.')
    assert "exclude" not in e["filter"]


def test_condition_kept_in_evidence_for_bullets():
    effs = effects('If you control a Fiend monster: Activate 1 of these effects;\n● 1+: Draw 1 card.\n'
                   '● 4+: Add 1 "HERO" monster from your Deck to your hand.')
    assert effs[0]["evidence"].startswith("If you control a Fiend monster")


def test_fusion_summon_effects():
    (e,) = effects('Fusion Summon 1 Fusion Monster from your Extra Deck that lists a "Destiny HERO" monster as '
                   'material, using monsters from your hand or Deck as Fusion Material.')
    assert e["verb"] == "fusion" and e["zones"] == ["Extra Deck"]
    assert e["filter"] == {"kinds": ["fusion"], "material_mentions": ["Destiny HERO"]}
    assert "materials from: hand, Deck" in e["flags"]
    (e,) = effects('Fusion Summon 1 Fusion Monster that mentions "Blue-Eyes White Dragon" or "Blue-Eyes Ultimate '
                   'Dragon" as material, by shuffling the Fusion Materials listed on it from your hand.')
    assert e["filter"]["material_mentions"] == ["Blue-Eyes White Dragon", "Blue-Eyes Ultimate Dragon"]


def test_fetch_rules(con):
    from ygoformat.formats import FORMATS
    from ygoformat.linkfind import _pool
    from datetime import date
    pool = _pool(con, FORMATS["genesys"], date(2026, 10, 20))
    by = {f.name: f for f in pool.facts.values()}
    src = by["Elemental HERO Stratos"].cid
    search = {"verb": "add", "zones": ["Deck"], "filter": {"archetypes": ["Destiny HERO"], "kinds": ["monster"]},
              "cost": False}
    assert pool.fetches(src, search, by["Destiny HERO - Malicious"])
    assert not pool.fetches(src, search, by["Destiny HERO - Dystopia"])  # Extra Deck monster: not in the Deck
    assert not pool.fetches(src, {**search, "cost": True}, by["Destiny HERO - Malicious"])  # a cost is not a fetch
    assert not pool.fetches(src, {**search, "verb": "banish"}, by["Destiny HERO - Malicious"])
    fusion = {"verb": "fusion", "zones": ["Extra Deck"], "cost": False,
              "filter": {"kinds": ["fusion"], "material_mentions": ["Destiny HERO"]}}
    assert pool.fetches(src, fusion, by["Destiny HERO - Dystopia"])  # '2 "Destiny HERO" monsters'
    assert not pool.fetches(src, fusion, by["Destiny HERO - Malicious"])


def test_find_links_deck_locks_block_own_cards_and_rank_options(con):
    deck = {"main": DHERO["main"] + ["Elemental HERO Stratos", "Reinforcement of the Army"],
            "extra": ["Destiny HERO - Dystopia"]}
    r = find_links(con, "tcg_advanced", decklist=deck, as_of="2026-10-20")
    lock = next(x for x in r["deck_locks"] if x["card"] == "Fusion Destiny")
    assert lock["kind"] == "all" and "Elemental HERO Stratos" in lock["blocks_your"]  # WIND, not DARK
    # Fusion Destiny now fetches the D-HERO Fusions it can summon, so they show as reachable.
    reach = {e.split(" (")[0] for g in r["your_deck_reaches"] for e in g["examples"]}
    assert "Destiny HERO - Destroyer Phoenix Enforcer" in reach
    # Reinforcement (any Level 4 or lower Warrior) is a generic searcher: one line, not an archetype group.
    assert any(g["card"] == "Reinforcement of the Army" for g in r["generic_searchers"])
    # Lock-compatible Extra Deck options come before ones that break a deck lock.
    flags = [("breaks_deck_locks" in x) for x in r["extra_deck_options"]]
    assert flags == sorted(flags)

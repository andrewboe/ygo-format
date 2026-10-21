"""find_links: cards that connect to a deck, from the link graph in links.py.

Sections: members of your archetypes the list doesn't run yet, outside cards that fetch your cards,
what your cards already fetch outside the list (by archetype; generic searchers collapsed), bridges
into other engines, Extra Deck monsters your monsters can be material for, and the deck's own locks
with what they block. Everything respects the format (legal cards only) and, for Genesys, the
points left.

A fetch is an add / Special Summon / Set / Fusion Summon effect, never a cost, and an Extra Deck
monster can't be fetched from the hand or Deck.
"""
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import date

from .formats import FORMATS, DeckInputError, card_status, parse_input, resolve
from .links import Facts, facts_of, matches, specificity

HUB_ARCHETYPES = 8  # an effect reaching more archetypes than this is generic, not a bridge
FETCH_VERBS = ("add", "summon", "set", "fusion")
SUMMON_LOCKS = ("all", "extra", "main")
EVIDENCE_CHARS = 150


class Pool:
    """Everything find_links needs, loaded once per index build, format and day."""

    def __init__(self, con: sqlite3.Connection, spec, day: date):
        mentions = defaultdict(set)
        for cid, m in con.execute("SELECT canonical_id, mention FROM mentions"):
            mentions[cid].add(m)
        rows = con.execute("SELECT * FROM cards WHERE passcode = canonical_id "
                           "AND type NOT IN ('Token','Skill Card')").fetchall()
        self.facts = {r["canonical_id"]: facts_of(r, frozenset(mentions[r["canonical_id"]])) for r in rows}
        self.tag = {r["canonical_id"]: r["archetype"] for r in rows}
        self.status = {r["canonical_id"]: card_status(con, spec, r, day) for r in rows}
        self.effects = defaultdict(list)
        for r in con.execute("SELECT * FROM effects"):
            self.effects[r["canonical_id"]].append({
                "verb": r["verb"], "zones": r["zones"].split(","), "filter": json.loads(r["filter"]),
                "evidence": r["evidence"], "cost": bool(r["cost"]), "flags": json.loads(r["flags"])})
        self.materials = {}
        for r in con.execute("SELECT * FROM materials"):
            self.materials[r["canonical_id"]] = (json.loads(r["components"]), r["line"])
            if r["canonical_id"] in self.facts:
                self.facts[r["canonical_id"]].material_quotes = frozenset(re.findall(r'"([^"]+)"', r["line"]))
        self.locks = defaultdict(list)
        for r in con.execute("SELECT * FROM locks"):
            self.locks[r["canonical_id"]].append({"scope": r["scope"], "filter": json.loads(r["filter"]),
                                                  "evidence": r["evidence"]})
        self._targets: dict[str, list[int]] = {}

    def fetches(self, src: int, e: dict, dst: Facts) -> bool:
        """Does effect e of card src fetch dst? (add/summon/Set/Fusion, not a cost, zone-possible.)"""
        if e["cost"] or e["verb"] not in FETCH_VERBS or e["filter"].get("names") == [self.facts[src].name]:
            return False
        zones = set(e["zones"])
        if dst.is_extra and zones <= {"hand", "Deck"}:
            return False  # an Extra Deck monster is never in your hand or Deck
        if not dst.is_extra and zones == {"Extra Deck"}:
            return False
        return matches(dst, e["filter"])

    def targets(self, src: int, e: dict) -> list[int]:
        key = json.dumps([e["verb"], e["zones"], e["filter"]], sort_keys=True)
        if key not in self._targets:
            self._targets[key] = [cid for cid, c in self.facts.items() if self.fetches(src, e, c)]
        return self._targets[key]


_POOLS: dict[tuple, Pool] = {}


def _pool(con: sqlite3.Connection, spec, day: date) -> Pool:
    fetch = con.execute("SELECT max(fetch_id) FROM fetches").fetchone()[0]
    path = con.execute("PRAGMA database_list").fetchone()[2] or f"memory:{id(con)}"
    key = (path, fetch, spec.key, day)
    if key not in _POOLS:
        _POOLS.clear()  # keep one pool in memory
        _POOLS[key] = Pool(con, spec, day)
    return _POOLS[key]


def _strong(f: dict) -> bool:
    """Names, archetypes, quoted mentions or listed materials: a deliberate link, not a shared Attribute."""
    return bool(f.get("names") or f.get("archetypes") or f.get("mentions") or f.get("material_mentions"))


def blocks(lock: dict, c: Facts) -> bool:
    """Would this Special Summon lock stop c from being Special Summoned?"""
    if lock["scope"] not in SUMMON_LOCKS or not c.is_monster:
        return False
    if lock["scope"] == "extra" and not c.is_extra or lock["scope"] == "main" and c.is_extra:
        return False
    return not matches(c, lock["filter"])


def _brief(pool: Pool, cid: int, spec) -> dict:
    c, st = pool.facts[cid], pool.status[cid]
    out = {"name": c.name, "passcode": cid, "type": c.type}
    if spec.points:
        out["points"] = st.get("points", 0)
    if spec.limits and st["limit"] < 3:
        out["limit"] = st["limit"]
    if pool.tag.get(cid):
        out["archetype"] = pool.tag[cid]
    return out


def _label(pool: Pool, cid: int, spec) -> str:
    """'Name (5 pts)' / 'Name (Limited)' / 'Name': a compact example entry."""
    st = pool.status[cid]
    if spec.points and st.get("points"):
        return f"{pool.facts[cid].name} ({st['points']} pts)"
    if spec.limits and st["limit"] < 3:
        return f"{pool.facts[cid].name} ({st.get('status')})"
    return pool.facts[cid].name


def _evidence(e: dict) -> dict:
    out = {"how": f"{e['verb']} from {', '.join(e['zones'])}", "evidence": e["evidence"][:EVIDENCE_CHARS]}
    if e["flags"]:
        out["ruling_flags"] = list(e["flags"])
    return out


def _deck_counts(con, cards, ydk_path, ydk_text, decklist) -> tuple[Counter, list[str]]:
    counts: Counter = Counter()
    errors: list[str] = []
    if cards is not None:
        pids = []
        for q in cards:
            pid, note = resolve(con, q)
            if pid is None:
                errors.append(note)
            else:
                pids.append(pid)
    else:
        deck = parse_input(con, ydk_path, ydk_text, decklist)
        errors += deck.errors
        pids = [p for z in deck.zones.values() for p in z]
    for p in pids:
        row = con.execute("SELECT canonical_id FROM cards WHERE passcode = ?", (p,)).fetchone()
        if row is None:
            errors.append(f"unknown passcode {p}")
        else:
            counts[row[0]] += 1
    return counts, errors


def find_links(con: sqlite3.Connection, format: str, ydk_path: str | None = None, ydk_text: str | None = None,
               decklist: dict | None = None, cards: list[str] | None = None, archetypes: list[str] | None = None,
               max_points: int | None = None, point_cap: int | None = None, limit: int = 8,
               as_of: str | None = None) -> dict:
    spec = FORMATS.get(format)
    if spec is None:
        raise DeckInputError(f"unknown format {format!r}; known: {', '.join(FORMATS)}")
    if cards is None and ydk_path is None and ydk_text is None and decklist is None:
        raise DeckInputError("pass a deck (ydk_path, ydk_text, decklist) or a list of cards")
    day = date.fromisoformat(as_of) if as_of else date.today()
    counts, errors = _deck_counts(con, cards, ydk_path, ydk_text, decklist)
    if errors:
        return {"error": "input problems; nothing was guessed", "parse_errors": errors}
    pool = _pool(con, spec, day)
    in_deck = set(counts)
    more: dict[str, int] = {}

    def cut(name: str, items: list, n: int = limit) -> list:
        if len(items) > n:
            more[name] = len(items) - n
        return items[:n]

    used = sum(pool.status[c].get("points", 0) * n for c, n in counts.items() if c in pool.status)
    budget = max_points
    if spec.points and budget is None and cards is None:
        budget = (point_cap if point_cap is not None else spec.default_cap) - used
    if not archetypes:
        tags = Counter(pool.tag[c] for c in in_deck if pool.tag.get(c))
        archetypes = [t for t, n in tags.most_common() if n >= 2] or [t for t, _ in tags.most_common(1)]
    deck_tags = set(archetypes)
    deck_locks = [(pool.facts[c].name, lk) for c in sorted(in_deck) for lk in pool.locks.get(c, [])]
    summon_locks = [(src, lk) for src, lk in deck_locks if lk["scope"] in SUMMON_LOCKS]

    def ok(cid: int) -> bool:
        st = pool.status.get(cid)
        return bool(st and st["legal"] and cid not in in_deck and (budget is None or st.get("points", 0) <= budget))

    def broken_by(cid: int) -> list[str]:
        return [src for src, lk in summon_locks if blocks(lk, pool.facts[cid])]

    def item(cid: int, extra: dict) -> dict:
        out = {**_brief(pool, cid, spec), **extra}
        if broken := broken_by(cid):
            out["breaks_deck_locks"] = sorted(set(broken))
        own = [lk for lk in pool.locks.get(cid, []) if lk["scope"] in SUMMON_LOCKS]
        if own:
            n = sum(1 for d in in_deck if any(blocks(lk, pool.facts[d]) for lk in own))
            out["its_lock"] = {"text": own[0]["evidence"][:EVIDENCE_CHARS], "your_monsters_it_blocks": n}
        return out

    def by_copies(cids) -> list[str]:  # what a card fetches, most-played targets first
        return [pool.facts[c].name for c in sorted(cids, key=lambda c: (-counts[c], pool.facts[c].name))]

    # A. outside cards whose effects fetch your cards
    into = []
    for cid, effs in pool.effects.items():
        if not ok(cid):
            continue
        hits, best, best_score = set(), None, 0
        for e in effs:
            if not specificity(e["filter"]):
                continue
            m = {d for d in in_deck if pool.fetches(cid, e, pool.facts[d])}
            if m:
                hits |= m
                # By name/archetype beats a shared Attribute or Type, however many cards that happens to hit.
                s = len(m) * 4 if _strong(e["filter"]) else min(len(m), 4)
                if s > best_score:
                    best, best_score = e, s
        if hits:
            into.append((best_score, cid, hits, best))
    into.sort(key=lambda t: (-t[0], bool(broken_by(t[1])), pool.status[t[1]].get("points", 0)))
    into_deck = [item(cid, {"fetches_your": by_copies(hits)[:4], "fetches_count": len(hits), **_evidence(e)})
                 for _, cid, hits, e in cut("into_your_deck", into)]

    # B. what your cards already fetch outside the list: by archetype for deliberate links; searchers
    # by Attribute/Type ("add 1 Level 4 or lower Warrior") collapse to one line each.
    groups: dict[str, dict] = {}
    generic = []
    for d in sorted(in_deck):
        for e in pool.effects.get(d, []):
            if not specificity(e["filter"]):
                continue
            found = [t for t in pool.targets(d, e) if ok(t)]
            if not found:
                continue
            if not _strong(e["filter"]):
                generic.append({"card": pool.facts[d].name, "fetches_count": len(found), **_evidence(e)})
                continue
            for t in found:
                g = groups.setdefault(pool.tag.get(t) or "(no archetype)", {"cards": set(), "via": {}})
                g["cards"].add(t)
                g["via"].setdefault(pool.facts[d].name, _evidence(e))
    # Your own archetypes first: support you could run but don't is the most useful find.
    ordered = sorted(groups.items(), key=lambda kv: (kv[0] not in deck_tags, -len(kv[1]["cards"])))
    deck_reaches = [
        {"archetype": tag, "count": len(g["cards"]),
         "examples": [_label(pool, c, spec) for c in
                      sorted(g["cards"], key=lambda c: (bool(broken_by(c)), pool.status[c].get("points", 0),
                                                        pool.facts[c].name))[:4]],
         "via": [{"card": k, **v} for k, v in list(g["via"].items())[:1]]}
        for tag, g in cut("your_deck_reaches", ordered)]
    generic.sort(key=lambda g: -g["fetches_count"])

    # B2. members of your archetypes (by tag, name or "always treated as") that the list doesn't run,
    # ranked by how tightly they connect: your cards that fetch them, and your cards they fetch.
    def strong_hits(src: int, dst: int) -> dict | None:
        """src's first deliberate fetch (by name, archetype, mention or listed material) of dst."""
        for e in pool.effects.get(src, []):
            if _strong(e["filter"]) and pool.fetches(src, e, pool.facts[dst]):
                return e
        return None

    unplayed = []
    for cid, c in pool.facts.items():
        if not ok(cid) or not (pool.tag.get(cid) in deck_tags or any(t in c.name or t in c.treated for t in deck_tags)):
            continue
        reached_by = [(d, e) for d in in_deck if (e := strong_hits(d, cid))]
        reaches = [d for d in in_deck if strong_hits(cid, d)]
        if reached_by or reaches:
            unplayed.append([cid, reached_by, reaches])
    # Links between unplayed members count too (Genni, the Maid -> Verre, the Maid): add them as a pair.
    cands = [u[0] for u in unplayed]
    for u in unplayed:
        u.append([o for o in cands if o != u[0] and strong_hits(u[0], o)])

    # A two-way link (your cards fetch it and it fetches yours) is the strongest sign it belongs; a link
    # through another unplayed card counts for less, or broad searchers win on partners alone.
    def score(u) -> int:
        _, by, reaches, partners = u
        return (2 * len(by) + 2 * len(reaches) + min(len(partners), 2)
                + (3 if by and reaches else 2 if by and partners else 0))
    unplayed.sort(key=lambda u: (-score(u), pool.status[u[0]].get("points", 0), pool.facts[u[0]].name))
    own_unplayed = [item(cid, {
        "fetched_by": [{"card": pool.facts[d].name, **_evidence(e)} for d, e in reached_by[:1]],
        "fetches_your": by_copies(reaches)[:4],
        **({"fetches_unplayed": sorted(pool.facts[o].name for o in partners)[:4]} if partners else {})})
        for cid, reached_by, reaches, partners in cut("your_archetypes_unplayed", unplayed)]

    # C. bridges: a card tied to your deck that belongs to, or fetches, another archetype. Targets the
    # card's own lock forbids don't count (Sabatiel searches any "Fusion" Spell, but only HERO may follow).
    bridges: dict[str, dict] = {}
    linked = [(cid, "fetches your cards") for _, cid, _, e in into[:60] if _strong(e["filter"])]
    linked += [(c, "your cards fetch it") for g in groups.values() for c in sorted(g["cards"])[:20]]
    for cid, why in linked:
        own_locks = [lk for lk in pool.locks.get(cid, []) if lk["scope"] in SUMMON_LOCKS]
        engines = set()
        if (own := pool.tag.get(cid)) and own not in deck_tags:
            engines.add(own)
        for e in pool.effects.get(cid, []):
            if not _strong(e["filter"]):  # "add 1 DARK monster" reaches every DARK archetype: not a bridge
                continue
            reached = {pool.tag[t] for t in pool.targets(cid, e)
                       if pool.tag.get(t) and pool.tag[t] not in deck_tags and ok(t)
                       and not any(blocks(lk, pool.facts[t]) for lk in own_locks)}
            if len(reached) <= HUB_ARCHETYPES:  # e.g. anything named "...Fusion" spans dozens: a hub, not a bridge
                engines |= reached
        for b in engines:
            bridges.setdefault(b, {"engine": b, "via": {}})["via"].setdefault(pool.facts[cid].name, why)
    by_tag = defaultdict(list)
    for c, t in pool.tag.items():
        if t and ok(c):
            by_tag[t].append(c)
    bridge_list = []
    for b in bridges.values():
        mons = [c for c in by_tag[b["engine"]] if pool.facts[c].is_monster]
        blocked = Counter(src for c in mons for src in set(broken_by(c)))
        row = {"engine": b["engine"], "engine_cards_in_budget": len(by_tag[b["engine"]]),
               "via": [{"card": k, "link": v} for k, v in list(b["via"].items())[:3]], "connections": len(b["via"])}
        # A lock in your deck that stops most of the engine's monsters makes the bridge a sequencing problem.
        if mons and (heavy := [src for src, n in blocked.items() if n >= len(mons) / 2]):
            row["mostly_blocked_by_deck_locks"] = sorted(heavy)
        bridge_list.append(row)
    bridge_list.sort(key=lambda b: ("mostly_blocked_by_deck_locks" in b, -b["connections"]))
    bridge_list = cut("bridges", bridge_list)

    # D. Extra Deck monsters your monsters can be material for; lock-compatible and named/archetype
    # materials first.
    deck_mons = [(d, counts[d]) for d in in_deck if pool.facts[d].is_monster]
    extra = []
    for cid, (comps, line) in pool.materials.items():
        if not ok(cid):
            continue
        score = 0
        for comp in comps:
            matched = [(d, n) for d, n in deck_mons if matches(pool.facts[d], comp["filter"])]
            if sum(n for _, n in matched) < comp["count"]:
                break
            score += specificity(comp["filter"])
            if set(comp["filter"].get("archetypes", [])) & deck_tags or \
                    any(pool.tag.get(d) in deck_tags for d, _ in matched if comp["filter"].get("names")):
                score += 3
        else:
            if score:
                extra.append((bool(broken_by(cid)), -score, pool.status[cid].get("points", 0), cid, line))
    extra.sort()
    extra_deck = [item(cid, {"materials": line}) for *_, cid, line in cut("extra_deck_options", extra)]

    # E. your deck's own locks and conditions, with what they block in your list.
    lock_rows = []
    main_monsters = sum(n for d, n in counts.items() if pool.facts[d].is_monster and not pool.facts[d].is_extra)
    for src, lk in deck_locks:
        row = {"card": src, "kind": lk["scope"], "text": lk["evidence"][:EVIDENCE_CHARS]}
        if lk["scope"] in SUMMON_LOCKS:
            hit = sorted({pool.facts[d].name for d in in_deck if blocks(lk, pool.facts[d])})
            row["blocks_your"], row["blocks_count"] = hit[:8], len(hit)
        elif lk["scope"] == "empty_mmz":
            row["your_main_deck_monsters"] = main_monsters
            row["note"] = "needs no monsters in your Main Monster Zone; each main-deck monster you summon turns it off"
        lock_rows.append(row)

    out = {
        "format": spec.title, "deck_cards": len(in_deck), "deck_archetypes": sorted(deck_tags),
        "your_archetypes_unplayed": own_unplayed,
        "into_your_deck": into_deck, "your_deck_reaches": deck_reaches,
        "generic_searchers": cut("generic_searchers", generic, 5), "bridges": bridge_list,
        "extra_deck_options": extra_deck, "deck_locks": lock_rows,
        "notes": ["Links come from rule-based parsing of card text: add / Special Summon / Set / Fusion Summon "
                  "effects (not costs), materials and Special Summon locks. Nothing here is a verified ruling: "
                  "check ruling_flags and card_rulings.",
                  "Extra Deck options are checked by material type only, not by whether the summon is achievable."],
    }
    if more:
        out["more_not_shown"] = more
    if spec.points:
        out["points"] = {"deck_uses": used, "max_points_per_suggestion": budget}
    return out

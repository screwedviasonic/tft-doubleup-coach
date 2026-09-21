"""Heuristic autopsy generator matching tone of reviews/*.md."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any


SUPPORTISH = {
    "soraka", "lulu", "yuumi", "janna", "nami", "sona", "bard", "milio",
    "renata", "karma", "ivern", "zilean", "taric", "thresh", "braum",
    "rakan", "lillia", "alune",
}
TANKISH = {
    "rammus", "sett", "malphite", "amumu", "fiddlesticks", "fiddlesticks18",
    "warwick", "alistar", "gnar", "gnarsmall", "yorick", "kobuko", "hecarim",
    "reksai", "vi", "vi18", "ornn", "sion", "cho", "chogath", "galio",
    "leona", "poppy", "shen", "zac", "mundo", "tahmkench",
}
AP_ITEMS = {
    "rabadonsdeathcap", "archangelsstaff", "bluebuff", "jeweledgauntlet",
    "spearofshojin", "nashorstooth", "ionic spark", "ionicspark",
    "morellonomicon", "giantslayer", "guardbreaker", "hextechgunblade",
}
AD_ITEMS = {
    "infinityedge", "deathblade", "guinsoosrageblade", "bloodthirster",
    "titansresolve", "handofjustice", "lastwhisper", "giantslayer",
    "edgeofnight", "runaanshurricane", "krakenslayer",
}


def _parse_board(board: list[str]) -> list[dict]:
    """Parse board strings like Rammus★3[DragonsClaw,Warmogs] or Yunara★★★[IE]."""
    units = []
    for entry in board or []:
        # Prefer Name★N[items] (summaries.json style)
        m = re.match(r"^([A-Za-z0-9_]+)★(\d+)(?:\[([^\]]*)\])?$", entry)
        if m:
            name, tier_s, items_s = m.group(1), m.group(2), m.group(3)
            tier = int(tier_s)
        else:
            # Alternate: Name★★★[items] (repeated stars)
            m2 = re.match(r"^([A-Za-z0-9_]+)(★+)(?:\[([^\]]*)\])?$", entry)
            if m2:
                name, stars, items_s = m2.group(1), m2.group(2), m2.group(3)
                tier = len(stars)
            else:
                units.append({"name": entry, "tier": 1, "items": [], "raw": entry})
                continue
        items = [i.strip() for i in (items_s or "").split(",") if i.strip()]
        units.append({"name": name, "tier": tier, "items": items, "raw": entry})
    return units


def _trait_verticals(traits: list[str]) -> list[tuple[str, int]]:
    out = []
    for t in traits or []:
        if ":" in t:
            name, n = t.rsplit(":", 1)
            try:
                out.append((name, int(n)))
            except ValueError:
                out.append((name, 0))
        else:
            out.append((t, 0))
    out.sort(key=lambda x: -x[1])
    return out


def _pretty_trait(name: str) -> str:
    return re.sub(r"\d+$", "", name).replace("UniqueTrait", "").replace("18", "")


def _unit_base(name: str) -> str:
    return re.sub(r"\d+$", "", name).lower()


def _itemized(units: list[dict]) -> list[dict]:
    return [u for u in units if u["items"]]


def _naked(units: list[dict]) -> list[dict]:
    return [u for u in units if not u["items"] and u["tier"] <= 2]


def _find_support_overitemized(units: list[dict]) -> list[dict]:
    bad = []
    for u in units:
        base = _unit_base(u["name"])
        if base in SUPPORTISH and len(u["items"]) >= 2:
            ap_count = sum(1 for i in u["items"] if i.replace(" ", "").lower() in AP_ITEMS or "deathcap" in i.lower() or "rabadon" in i.lower())
            if ap_count >= 2 or len(u["items"]) >= 3:
                bad.append(u)
    return bad


def _star3_carries(units: list[dict]) -> list[dict]:
    return [u for u in units if u["tier"] >= 3]


def _fillers_at_high_level(units: list[dict], level: int | None) -> list[dict]:
    if not level or level < 9:
        return []
    return [u for u in units if u["tier"] == 1 and not u["items"]]


def _finished_units(units: list[dict]) -> list[dict]:
    return [u for u in units if len(u["items"]) >= 2]


def generate_autopsy(summary: dict[str, Any], partner_hint: str = "Tudon") -> dict[str, Any]:
    """Return structured autopsy + markdown matching reviews/*.md tone."""
    place = summary.get("placement")
    level = summary.get("level")
    last_round = summary.get("last_round")
    gold = summary.get("gold_left")
    traits = summary.get("traits") or []
    board = _parse_board(summary.get("board") or [])
    partner_board = _parse_board(summary.get("partner_board") or [])
    partner_name = summary.get("partner_name") or partner_hint
    if "#" in str(partner_name):
        partner_short = partner_name.split("#")[0]
    else:
        partner_short = partner_name
    partner_place = summary.get("partner_placement")
    set_name = summary.get("set") or "TFT"
    set_label = str(set_name).replace("TFTSet", "Set ")
    match_id = summary.get("match_id") or "unknown"
    when = summary.get("when") or datetime.now().strftime("%Y-%m-%d %H:%M")

    verticals = _trait_verticals(traits)
    top_traits = [f"**{_pretty_trait(n)} {c}**" for n, c in verticals[:3] if c >= 3]
    trait_phrase = ", ".join(top_traits) if top_traits else "a mixed board"

    board_bits = [u["raw"] for u in board[:6]]
    partner_bits = [u["name"] for u in partner_board[:5]]

    # --- Lobby story ---
    if place and partner_place and place <= 2 and partner_place <= 2:
        story = (
            f"You and {partner_short} closed as the winning pair. "
            f"You capped on a {trait_phrase} board at level {level}; "
            f"{partner_short} ran a different shell ({' / '.join(partner_bits) or 'unknown'}). "
            f"Duo win-con was aligned: you both lived to late with real boards."
        )
    elif place and place <= 4 and partner_place and partner_place <= 4:
        story = (
            f"Pair top-4 (you #{place}, {partner_short} #{partner_place}). "
            f"You ended on {trait_phrase} at level {level}, last round {last_round}. "
            f"Board snapshot: {', '.join(board_bits)}."
        )
    elif place and partner_place and place >= 7 and partner_place >= 7:
        story = (
            f"Pair out early-ish (round {last_round}). "
            f"You died on a {trait_phrase} board"
            + (f" with {board[0]['raw']}" if board else "")
            + f". {partner_short} was on a loose {' / '.join(partner_bits) or 'unfinished'} shell — also unfinished."
        )
    else:
        story = (
            f"You #{place} · {partner_short} #{partner_place}. "
            f"Level {level}, last round {last_round}, {gold} gold left. "
            f"Ended on {trait_phrase}. "
            f"Board: {', '.join(board_bits)}."
        )

    rights: list[dict] = []
    wrongs: list[dict] = []

    # --- Rights heuristics ---
    star3 = _star3_carries(board)
    if star3:
        u = star3[0]
        rights.append({
            "title": f"{u['name']} ★{u['tier']} with a real core",
            "detail": (
                f"{u['raw']} is a legitimate carry package."
                if u["items"]
                else f"Hitting ★3 {u['name']} is real board strength."
            ),
            "confidence": "high",
        })

    finished = _finished_units(board)
    if len(finished) >= 3:
        rights.append({
            "title": "Item distribution looks intentional",
            "detail": (
                f"Multiple units are \"done\" ({', '.join(u['name'] for u in finished[:4])}), "
                "not one stuffed carry + empty board."
            ),
            "confidence": "medium-high",
        })

    if gold is not None and gold <= 5 and place and place <= 4:
        rights.append({
            "title": "Tempo to late",
            "detail": (
                f"Round {last_round}, level {level}, {gold} gold: "
                "you spent to stay alive and still had a finished-ish board."
            ),
            "confidence": "high",
        })
    elif gold is not None and gold <= 3:
        rights.append({
            "title": "You weren't sitting on gold",
            "detail": f"{gold} gold left: not a \"greeded 50 interest and died\" death.",
            "confidence": "high",
        })

    if level and level >= 9 and any(c >= 6 for _, c in verticals):
        rights.append({
            "title": "Cap / vertical commitment",
            "detail": (
                f"{_pretty_trait(verticals[0][0])} {verticals[0][1]} at {level} "
                "is a real win-out board, not a half-pivot."
            ),
            "confidence": "high from end-state",
        })

    tanks = [u for u in board if _unit_base(u["name"]) in TANKISH]
    if tanks and any(u["items"] for u in tanks):
        rights.append({
            "title": "Frontline attempt",
            "detail": (
                f"{' + '.join(u['name'] for u in tanks[:2])} shows you knew the board needed tanks."
            ),
            "confidence": "medium",
        })

    # Duo complementarity
    my_names = {_unit_base(u["name"]) for u in board}
    partner_names = {_unit_base(u["name"]) for u in partner_board}
    overlap = my_names & partner_names - {"base", "ad", "ap", "?"}
    if partner_board and len(overlap) <= 2 and place and place <= 4:
        rights.append({
            "title": "Duo complementarity",
            "detail": (
                f"You're {_pretty_trait(verticals[0][0]) if verticals else 'your'}-leaning; "
                f"{partner_short}'s board isn't a clone of yours. "
                "Less self-contest risk than both slamming the same legendaries."
            ),
            "confidence": "medium — inferred",
        })

    # --- Wrongs heuristics ---
    support_bad = _find_support_overitemized(board)
    if support_bad:
        u = support_bad[0]
        naked = [x["name"] for x in _naked(board) if _unit_base(x["name"]) not in SUPPORTISH][:3]
        wrongs.append({
            "title": f"{u['name']} itemization is a red flag",
            "detail": (
                f"{u['raw']} while {', '.join(naked) or 'other carries'} look item-naked. "
                "That's stacking on a support/secondary instead of finishing a second damage threat or a real tank."
            ),
            "confidence": "high from end-state",
        })

    if place and partner_place and place >= 7 and partner_place >= 7:
        wrongs.append({
            "title": "Pair both weak at the same time",
            "detail": (
                f"#{partner_place} + #{place} means neither board was stabilizing. "
                "In Double Up, one partner usually needs to be the \"HP sponge / fast 8\" while the other highrolls. "
                "Here both look mid-rolled."
            ),
            "confidence": "high duo-level confidence",
        })

    fillers = _fillers_at_high_level(board, level)
    if fillers and place and place <= 3:
        wrongs.append({
            "title": f"{' / '.join(u['name'] + ' ★1' for u in fillers[:2])} as level-{level} fillers",
            "detail": (
                "Fine for trait/count, but they signal you hit high level with some dead weight. "
                "Not a throw; just the difference between 1st and 2nd individual boards."
            ),
            "confidence": "medium",
        })

    # Tank underleveled vs carry
    if star3 and tanks:
        carry = star3[0]
        weak_tanks = [t for t in tanks if t["tier"] < carry["tier"] and t["tier"] <= 2]
        if weak_tanks and place and place >= 5:
            wrongs.append({
                "title": f"{weak_tanks[0]['name']} still ★{weak_tanks[0]['tier']} while {carry['name']} is ★{carry['tier']}",
                "detail": (
                    "Tank underleveled relative to carry; board probably bled HP before the caster came online every fight."
                ),
                "confidence": "medium",
            })

    naked_traits = [u for u in board if not u["items"] and u["tier"] <= 2 and _unit_base(u["name"]) not in TANKISH]
    if len(naked_traits) >= 3 and any(c >= 5 for _, c in verticals) and place and place >= 5:
        wrongs.append({
            "title": " / ".join(f"{u['name']} ★{u['tier']}" for u in naked_traits[:3]),
            "detail": (
                f"Trait bots without items; {_pretty_trait(verticals[0][0])} {verticals[0][1]} "
                "was \"wide\" but not \"strong.\""
            ),
            "confidence": "medium",
        })

    if last_round and last_round <= 31 and place and place >= 6:
        wrongs.append({
            "title": f"Died level {level} round {last_round}",
            "detail": (
                "Suggests you never found a stable stage-4 board, or lost too much HP early and never recovered. "
                "API can't see which."
            ),
            "confidence": "limitation",
        })

    if level and level <= 7 and place and place >= 5:
        wrongs.append({
            "title": f"Stuck at level {level}",
            "detail": "Low level into mid/late usually means econ or tempo broke. End-state can't show the cause.",
            "confidence": "medium",
        })

    if len(overlap) >= 4:
        wrongs.append({
            "title": "Heavy unit overlap with partner",
            "detail": (
                f"Shared pool ({', '.join(sorted(overlap)[:5])}) — self-contest risk. "
                "One of you should have flexed earlier."
            ),
            "confidence": "medium — inferred",
        })

    # Always note API limits
    wrongs.append({
        "title": "Unknown augment / portal / midgame",
        "detail": (
            "API can't see augments reliably, portals, or whether you highrolled the vertical or forced it from a weak 3-2. "
            "Don't overfit one game's end-state."
        ),
        "confidence": "limitation",
    })

    # Cap to ~3 rights / ~3 wrongs (keep limitation as 4th note if needed)
    rights = rights[:3]
    # Prefer substantive wrongs; keep one limitation
    substantive = [w for w in wrongs if w["confidence"] != "limitation"]
    limitations = [w for w in wrongs if w["confidence"] == "limitation"]
    wrongs = (substantive[:3] + limitations[:1])[:4]

    # Ensure at least some content
    if not rights:
        rights.append({
            "title": "Survived to a readable end-state",
            "detail": f"Level {level}, round {last_round} — enough board data to coach from.",
            "confidence": "low",
        })

    # --- Double Up note ---
    if place and partner_place and place <= 2 and partner_place <= 2:
        duo_note = (
            f"Partner took #{partner_place} board strength while you took #{place} — "
            "that's a successful pair result. Keep doing \"different verticals, same win timing.\""
        )
    elif place and partner_place and place >= 7 and partner_place >= 7:
        duo_note = (
            "When you're both contested / both weak, the fix is usually "
            "**one stabilizes (2-star frontline + econ)** while the other rolls for the spike — "
            "not both greed for verticals."
        )
    elif place and partner_place and abs(place - partner_place) >= 3:
        duo_note = (
            f"Large placement gap (you #{place}, {partner_short} #{partner_place}). "
            "One board carried the pair — talk about who should be the stabilizer next lobby."
        )
    else:
        duo_note = (
            f"Pair result: you #{place}, {partner_short} #{partner_place}. "
            "Before stage 4, align win-cons so you're not both mid-rolling the same spike timing."
        )

    # --- Drill ---
    if support_bad:
        drill = (
            "After every augment / big item slam: **\"Who is my #2 itemized unit?\"** "
            "If the answer is a support with stacked carry items, reassign before the next PVP round."
        )
    elif place and partner_place and place >= 7 and partner_place >= 7:
        drill = (
            "Next lobby: explicitly pick roles — **you stabilize OR you spike**. "
            "Say it out loud at 2-1. If both say \"spike,\" one flexes to frontline econ."
        )
    elif len(overlap) >= 3:
        drill = (
            f"Before stage 4, name out loud: **\"My win-con is X; {partner_short}'s is Y; we are not contesting Z.\"** "
            "If both names share 3+ contested units, one of you flexes."
        )
    else:
        drill = (
            f"Before stage 4, name out loud: **\"My win-con is X; {partner_short}'s is Y; we are not contesting Z.\"** "
            "If both names share 3+ contested units, one of you flexes."
        )

    api_limits = [
        "Augments often missing from TFT match API",
        "total_damage_to_players often 0",
        "No midgame / portal / HP curve — end-state only",
        "partner_group_id often missing — partner inferred from adjacent placements (1-2, 3-4, 5-6, 7-8)",
    ]

    header = (
        f"# Autopsy — {match_id} ({_ord(place)}) — {when} CT\n"
        f"{set_label} Double Up · You #{place} · {partner_short} #{partner_place} · "
        f"Level {level} · Last round {last_round} · {gold} gold left"
    )

    def _fmt_points(items: list[dict], wrong: bool = False) -> str:
        lines = []
        for i, it in enumerate(items, 1):
            conf = it.get("confidence", "")
            conf_s = f" ({conf})" if conf else ""
            lines.append(f"{i}. **{it['title']}** — {it['detail']}{conf_s}")
        return "\n".join(lines)

    rights_header = "## What you did right"
    wrongs_header = (
        "## What went wrong / almost cost you"
        if place and place <= 4
        else "## What went wrong (likely)"
    )

    markdown = "\n".join([
        header,
        "",
        "## Lobby story",
        story,
        "",
        rights_header,
        _fmt_points(rights),
        "",
        wrongs_header,
        _fmt_points(wrongs, wrong=True),
        "",
        "## Double Up note",
        duo_note,
        "",
        "## One drill from this game",
        drill,
        "",
        "## API limits (label)",
        "\n".join(f"- {x}" for x in api_limits),
        "",
    ])

    return {
        "match_id": match_id,
        "when": when,
        "placement": place,
        "partner_placement": partner_place,
        "partner_name": partner_name,
        "level": level,
        "last_round": last_round,
        "gold_left": gold,
        "set": set_name,
        "traits": traits,
        "board": summary.get("board") or [],
        "partner_board": summary.get("partner_board") or [],
        "lobby_story": story,
        "rights": rights,
        "wrongs": wrongs,
        "double_up_note": duo_note,
        "drill": drill,
        "api_limits": api_limits,
        "markdown": markdown,
        "dry_run": summary.get("_dry_run", False),
    }


def _ord(n: int | None) -> str:
    if n is None:
        return "?"
    return f"{n}{'th' if 11 <= n <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def update_patterns_ledger(ledger_path, autopsy: dict, max_entries: int = 50) -> str:
    """Append a short entry and refresh hypotheses section. Returns new markdown."""
    from pathlib import Path

    path = Path(ledger_path)
    existing = path.read_text() if path.exists() else "# Pattern ledger\n\n"

    place = autopsy.get("placement")
    mid = autopsy.get("match_id")
    when = autopsy.get("when")
    drill = autopsy.get("drill", "").replace("\n", " ")
    entry = f"- {when} · {mid} · place #{place} · drill: {drill[:120]}"

    # Collect recent places from existing + new for batch stats
    lines = existing.splitlines()
    # Find or create Recent autopsies section
    if "## Recent autopsies" not in existing:
        existing = existing.rstrip() + "\n\n## Recent autopsies\n"
        lines = existing.splitlines()

    new_lines = []
    in_recent = False
    recent_count = 0
    inserted = False
    for line in lines:
        if line.strip() == "## Recent autopsies":
            in_recent = True
            new_lines.append(line)
            new_lines.append(entry)
            inserted = True
            recent_count = 1
            continue
        if in_recent:
            if line.startswith("## ") and "Recent" not in line:
                in_recent = False
                new_lines.append(line)
                continue
            if line.startswith("- ") and recent_count < max_entries:
                new_lines.append(line)
                recent_count += 1
            elif not line.startswith("- "):
                new_lines.append(line)
            # skip older entries beyond max
            continue
        new_lines.append(line)

    if not inserted:
        new_lines.append("")
        new_lines.append("## Recent autopsies")
        new_lines.append(entry)

    # Hypotheses block — keep seed ideas, add note about latest
    text = "\n".join(new_lines).rstrip() + "\n"
    if "## Standing drill" not in text:
        text += (
            "\n## Standing drill\n"
            "Before stage 4: name your win-con, partner's win-con, and the contested pool to avoid.\n"
        )
    path.write_text(text)
    return text

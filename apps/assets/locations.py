"""Location tree helpers (trees are small per organization, so they are built in memory)."""

from .models import Location

SEP = " › "


def tree(organization) -> dict:
    locs = list(Location.objects.for_org(organization))
    by_id = {loc.pk: loc for loc in locs}
    children: dict = {}
    for loc in locs:
        children.setdefault(loc.parent_id, []).append(loc)
    return {"by_id": by_id, "children": children}


def paths(organization) -> dict[int, str]:
    t = tree(organization)
    out = {}
    for pk in t["by_id"]:
        names, cur, seen = [], t["by_id"][pk], set()
        while cur is not None and cur.pk not in seen:
            seen.add(cur.pk)
            names.append(cur.name)
            cur = t["by_id"].get(cur.parent_id)
        out[pk] = SEP.join(reversed(names))
    return out


def descendant_ids(organization, location_id: int) -> set[int]:
    t = tree(organization)
    out, stack = set(), [location_id]
    while stack:
        pk = stack.pop()
        if pk in out:
            continue
        out.add(pk)
        stack.extend(c.pk for c in t["children"].get(pk, []))
    return out


def ordered_choices(organization) -> list[tuple[int, str]]:
    """(id, indented label) in tree order — for selects."""
    t = tree(organization)
    out = []

    def walk(parent_id, depth):
        for loc in sorted(t["children"].get(parent_id, []), key=lambda x: x.name.lower()):
            out.append((loc.pk, ("— " * depth) + loc.name, loc))
            walk(loc.pk, depth + 1)

    walk(None, 0)
    return out

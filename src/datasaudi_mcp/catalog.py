"""In-memory cube catalog + schema index (R12). Isolates the one piece of mutable
state so the rest of the code stays pure. Also home to search (R10/R11), did-you-mean
(R8), and member listing (R9)."""

from __future__ import annotations

import difflib

from .errors import DataSaudiError


class Catalog:
    def __init__(self, by_name: dict[str, dict]) -> None:
        self._by_name = by_name

    @classmethod
    def from_cubes(cls, cubes: list[dict]) -> "Catalog":
        return cls({c["name"]: c for c in cubes})

    def names(self) -> list[str]:
        return list(self._by_name)

    def get(self, cube: str) -> dict:
        try:
            return self._by_name[cube]
        except KeyError:
            raise DataSaudiError(f"no cube named {cube!r}") from None

    def levels_of(self, cube: str) -> list[str]:
        """R7: ALL levels across all hierarchies (not just the deepest)."""
        out: list[str] = []
        for dim in self.get(cube).get("dimensions", []):
            for hier in dim.get("hierarchies", []):
                out.extend(lvl["name"] for lvl in hier.get("levels", []))
        return out

    def has_level(self, cube: str, level: str) -> bool:
        """R9 support: confirm a level exists before a members query."""
        return level in self.levels_of(cube)

    def measures_of(self, cube: str) -> list[str]:
        return [m["name"] for m in self.get(cube).get("measures", [])]

    def domain_of(self, cube: str) -> str:
        """R10 domain tag: use the source's own topic annotation when present."""
        return self.get(cube).get("annotations", {}).get("topic_en", "") or ""

    def _compact(self, cube: str) -> dict:
        c = self.get(cube)
        return {"name": c["name"], "caption": c.get("caption", c["name"]),
                "domain": self.domain_of(cube)}

    def search(self, query: str, scope: str = "catalog", locale: str = "en") -> list[dict]:
        """R10/R11: compact search. scope=catalog -> name/caption/topic;
        measures -> measure names; levels -> level names (searches drillable LEVEL
        names, not member values). 'members' is accepted as a backward-compatible
        alias for 'levels'. locale='ar' also searches the Arabic catalog annotations
        (topic_ar/subtopic_ar/source_name_ar), which the /cubes payload already carries."""
        q = query.strip().lower()
        out: list[dict] = []
        for name, c in self._by_name.items():
            hay: list[str] = []
            if scope == "catalog":
                ann = c.get("annotations", {})
                hay = [name, c.get("caption", ""), ann.get("topic_en", ""),
                       ann.get("subtopic_en", ""), ann.get("source_name", "")]
                if locale == "ar":
                    hay += [ann.get("topic_ar", ""), ann.get("subtopic_ar", ""),
                            ann.get("source_name_ar", ""), ann.get("table_ar", "")]
            elif scope == "measures":
                hay = [m["name"] for m in c.get("measures", [])]
            elif scope in ("levels", "members"):  # 'members' kept as an alias
                hay = self.levels_of(name)
            if any(q in (h or "").lower() for h in hay):
                out.append(self._compact(name))
        return out

    def did_you_mean(self, cube: str, n: int = 3) -> list[str]:
        """R8: nearest cube names for an unknown cube."""
        return difflib.get_close_matches(cube, list(self._by_name), n=n, cutoff=0.5)

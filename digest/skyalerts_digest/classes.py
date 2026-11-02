"""ALeRCE class names -> plain-English labels, display groups, blurbs, and priority tiers.

Ported verbatim from web/lib/classes.ts. Class names come from upstream data,
so anything unknown falls back to a neutral "other".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ClassGroup = Literal["stochastic", "transient", "variable", "solar", "other"]


@dataclass(frozen=True)
class ClassInfo:
    name: str | None
    label: str
    group: ClassGroup
    blurb: str


@dataclass(frozen=True)
class GroupInfo:
    id: ClassGroup
    label: str


# Order matches the categorical colour slots in web/lib/classes.ts.
GROUPS: tuple[GroupInfo, ...] = (
    GroupInfo(id="stochastic", label="Active galaxies"),
    GroupInfo(id="transient", label="Explosions & outbursts"),
    GroupInfo(id="variable", label="Variable stars"),
    GroupInfo(id="solar", label="Solar system"),
    GroupInfo(id="other", label="Other & unclassified"),
)

KNOWN: dict[str, tuple[str, ClassGroup, str]] = {
    "SN": (
        "Supernova",
        "transient",
        "An exploding star, brightening over days and fading over weeks.",
    ),
    "SNIa": (
        "Type Ia supernova",
        "transient",
        "A white dwarf blown apart. Their even brightness makes them cosmic yardsticks.",
    ),
    "SNIbc": (
        "Type Ib/c supernova",
        "transient",
        "A massive star that lost its outer layers before collapsing.",
    ),
    "SNIIn": (
        "Type IIn supernova",
        "transient",
        "A supernova slamming into gas the star shed before it died.",
    ),
    "SNIIb": (
        "Type IIb supernova",
        "transient",
        "A massive star that kept only a thin shell of hydrogen before collapsing.",
    ),
    "SNII": (
        "Type II supernova",
        "transient",
        "A massive star whose core collapsed while still wrapped in hydrogen.",
    ),
    "SLSN": (
        "Superluminous supernova",
        "transient",
        "A rare explosion ten or more times brighter than a normal supernova.",
    ),
    "TDE": (
        "Tidal disruption event",
        "transient",
        "A star torn apart by a supermassive black hole.",
    ),
    "KN": (
        "Kilonova",
        "transient",
        "The glow left behind when two neutron stars merge.",
    ),
    "CV/Nova": (
        "Cataclysmic variable",
        "transient",
        "A white dwarf flaring as it pulls gas off a companion star.",
    ),
    "AGN": (
        "Active galactic nucleus",
        "stochastic",
        "A feeding supermassive black hole flickering at the heart of a galaxy.",
    ),
    "QSO": (
        "Quasar",
        "stochastic",
        "A very distant, very luminous active galactic nucleus.",
    ),
    "Blazar": (
        "Blazar",
        "stochastic",
        "An active galaxy with its jet pointed almost straight at us.",
    ),
    "YSO": (
        "Young stellar object",
        "stochastic",
        "A newborn star still gathering gas and dust.",
    ),
    "VS": (
        "Variable star",
        "variable",
        "A star whose brightness changes over time.",
    ),
    "RRL": (
        "RR Lyrae star",
        "variable",
        "An old star pulsing on a steady rhythm of about half a day.",
    ),
    "CEP": (
        "Cepheid",
        "variable",
        "A pulsing giant whose period reveals its true brightness.",
    ),
    "DSCT": (
        "Delta Scuti star",
        "variable",
        "A star that pulses every few hours.",
    ),
    "E": (
        "Eclipsing binary",
        "variable",
        "Two stars taking turns blocking each other's light.",
    ),
    "LPV": (
        "Long-period variable",
        "variable",
        "A swollen red giant that brightens and dims over months.",
    ),
    "RRLab": (
        "RR Lyrae star (ab)",
        "variable",
        "An RR Lyrae star pulsing in its fundamental mode.",
    ),
    "RRLc": (
        "RR Lyrae star (c)",
        "variable",
        "An RR Lyrae star pulsing in its first overtone.",
    ),
    "Periodic-Other": (
        "Periodic variable",
        "variable",
        "A star that repeats on a regular schedule.",
    ),
    "Transient": (
        "Transient",
        "transient",
        "Something that appears or flares once, rather than repeating.",
    ),
    "Stochastic": (
        "Irregular variable",
        "stochastic",
        "Brightness that wanders without a fixed rhythm.",
    ),
    "Periodic": (
        "Periodic variable",
        "variable",
        "Brightness that repeats on a regular schedule.",
    ),
    "nuclear": (
        "At a galaxy core",
        "other",
        "Sits at the centre of its host galaxy.",
    ),
    "off-nuclear": (
        "Away from a galaxy core",
        "other",
        "Sits away from the centre of its host galaxy.",
    ),
    "asteroid": (
        "Asteroid",
        "solar",
        "A solar-system body caught moving across the field.",
    ),
    "bogus": (
        "Artifact",
        "other",
        "Not a real sky source: a glitch in the image subtraction.",
    ),
}

# Ranking tiers for "notable" ordering. Keep in step with ingest enrichment tiers and web.
TRANSIENT_CLASSES: tuple[str, ...] = (
    "SN",
    "SNIa",
    "SNIbc",
    "SNII",
    "SLSN",
    "TDE",
    "KN",
    "CV/Nova",
)
LOW_PRIORITY_CLASSES: tuple[str, ...] = ("AGN", "QSO", "Blazar")
ARTIFACT_CLASS: str = "bogus"
ASTEROID_CLASS: str = "asteroid"


def class_info(name: str | None) -> ClassInfo:
    if name and name in KNOWN:
        label, group, blurb = KNOWN[name]
        return ClassInfo(name=name, label=label, group=group, blurb=blurb)
    return ClassInfo(
        name=name, label=name if name is not None else "Unclassified", group="other", blurb=""
    )


def group_of(name: str | None) -> ClassGroup:
    return class_info(name).group

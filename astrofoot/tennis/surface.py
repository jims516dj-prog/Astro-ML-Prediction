"""Court surface of a tournament. ESPN does not publish it, so: known tournaments by name or city, then
the season (clay in spring, grass from mid-June to mid-July), else hard. Approximate by design."""
from __future__ import annotations

import re

CLAY = ["roland garros", "french open", "monte carlo", "monte-carlo", "madrid", "rome", "internazionali",
        "barcelona", "hamburg", "buenos aires", "rio", "santiago", "cordoba", "córdoba", "estoril", "munich",
        "bmw open", "geneva", "lyon", "bastad", "båstad", "gstaad", "umag", "kitzbuhel", "kitzbühel", "bucharest",
        "marrakech", "houston", "u.s. men's clay", "us men's clay", "charleston", "bogota", "bogotá", "stuttgart porsche",
        "prague", "rabat", "strasbourg", "palermo", "lausanne", "budapest", "bad gastein", "parma", "warsaw",
        "iasi", "iași", "portoroz", "rouen", "saint-malo", "sao paulo", "são paulo", "quito", "sardegna", "cagliari",
        "belgrade", "banja luka", "parma", "florianopolis", "acapulco 2000", "casablanca", "nice", "dusseldorf",
        "düsseldorf", "oeiras", "kozerki", "porsche tennis grand prix", "mutua madrid", "open parc"]
GRASS = ["wimbledon", "queen's", "queens", "halle", "s-hertogenbosch", "'s-hertogenbosch", "libema", "rosmalen",
         "eastbourne", "mallorca", "newport", "hall of fame", "nottingham", "birmingham", "berlin ladies",
         "bad homburg", "stuttgart mercedes", "boss open", "terra wortmann", "cinch", "rothesay", "ilkley",
         "surbiton", "hertogenbosch"]


def surface(event: str, venue: str = "", day: str = "") -> str:
    t = f"{event} {venue}".lower()
    if any(re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", t) for k in GRASS):
        return "grass"
    if any(re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", t) for k in CLAY):
        return "clay"
    return "hard"

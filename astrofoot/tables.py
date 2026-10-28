"""Reference tables shared by the classical engines and the lattice.

Where a table comes from the build spec (Chokoisky 4.1 / 5.3, star list) it is copied
verbatim. Where the spec only cites a book page, the standard textbook version is used
and flagged VERIFY so it can be checked against the book before a lattice version freeze.
"""

BODIES = ["Su", "Mo", "Me", "Ve", "Ma", "Ju", "Sa", "Ur", "Ne", "Pl", "Ra"]  # Ke = Ra + 180
GRAHAS = ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"]
CLASSICAL7 = ["Su", "Mo", "Me", "Ve", "Ma", "Ju", "Sa"]
INVISIBLE = {"Ra", "Ke", "Ur", "Ne", "Pl"}
SIGNS = ["Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi"]
SIGN_NAMES = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
              "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
BODY_NAMES = {"Su": "Sun", "Mo": "Moon", "Me": "Mercury", "Ve": "Venus", "Ma": "Mars",
              "Ju": "Jupiter", "Sa": "Saturn", "Ur": "Uranus", "Ne": "Neptune", "Pl": "Pluto",
              "Ra": "Rahu (North Node)", "Ke": "Ketu (South Node)", "PF": "Part of Fortune"}

# Traditional rulers by sign index (Frawley, Rao, Chokoisky all use these for lordship)
RULER = ["Ma", "Ve", "Me", "Mo", "Su", "Me", "Ve", "Ma", "Ju", "Sa", "Sa", "Ju"]
OWN_SIGNS = {p: [i for i, r in enumerate(RULER) if r == p] for p in CLASSICAL7}
EXALT = {"Su": 0, "Mo": 1, "Me": 5, "Ve": 11, "Ma": 9, "Ju": 3, "Sa": 6, "Ra": 1, "Ke": 7}
DEBIL = {p: (s + 6) % 12 for p, s in EXALT.items()}
DETRIMENT = {p: [(s + 6) % 12 for s in OWN_SIGNS[p]] for p in CLASSICAL7}
MOOLATRIKONA = {"Su": 4, "Mo": 1, "Ma": 0, "Me": 5, "Ju": 8, "Ve": 6, "Sa": 10}
DIG_BALA_HOUSE = {"Ju": 1, "Me": 1, "Su": 10, "Ma": 10, "Sa": 7, "Mo": 4, "Ve": 4}

# Naisargika (natural) friendships, Parashara. VERIFY vs Rao p.39 (nodes vary by school).
_F = {
    "Su": ("Mo Ma Ju", "Me", "Ve Sa"),
    "Mo": ("Su Me", "Ma Ju Ve Sa", ""),
    "Ma": ("Su Mo Ju", "Ve Sa", "Me"),
    "Me": ("Su Ve", "Ma Ju Sa", "Mo"),
    "Ju": ("Su Mo Ma", "Sa", "Me Ve"),
    "Ve": ("Me Sa", "Ma Ju", "Su Mo"),
    "Sa": ("Me Ve", "Ju", "Su Mo Ma"),
    "Ra": ("Me Ve Sa", "Ju", "Su Mo Ma"),
    "Ke": ("Ma Ve Sa", "Ju Me", "Su Mo"),
}
FRIENDSHIP = {}
for _p, (_fr, _ne, _en) in _F.items():
    for _q in _fr.split():
        FRIENDSHIP[(_p, _q)] = "friend"
    for _q in _ne.split():
        FRIENDSHIP[(_p, _q)] = "neutral"
    for _q in _en.split():
        FRIENDSHIP[(_p, _q)] = "enemy"


def relation(p: str, q: str) -> str:
    if p == q:
        return "friend"
    return FRIENDSHIP.get((p, q), "neutral")


# Rao numerology (spec §5.3)
NUMBER_PLANET = {1: "Su", 2: "Mo", 3: "Ju", 4: "Ra", 5: "Me", 6: "Ve", 7: "Ke", 8: "Sa", 9: "Ma"}
WEEKDAY_LORD = ["Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Su"]  # Python weekday(): Monday=0
JERSEY_COLOR_PLANET = {"maroon": "Su", "white": "Mo", "red": "Ma", "green": "Me", "gold": "Ju",
                       "yellow": "Ve", "black": "Sa", "blue": "Sa", "brown": "Ra", "grey": "Ke"}

# Nakshatras (sidereal), Vimshottari lords and periods
NAKSHATRAS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu",
              "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta",
              "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
              "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
              "Uttara Bhadrapada", "Revati"]
DASHA_ORDER = ["Ke", "Ve", "Su", "Mo", "Ma", "Ra", "Ju", "Sa", "Me"]
DASHA_YEARS = {"Ke": 7, "Ve": 20, "Su": 6, "Mo": 10, "Ma": 7, "Ra": 18, "Ju": 16, "Sa": 19, "Me": 17}
NAK_LORD = [DASHA_ORDER[i % 9] for i in range(27)]

# 108 nakshatra-pada syllables (standard Avakahada chakra). VERIFY vs Chokoisky table 7.1 p.142.
PADA_SYLLABLES = (
    "chu che cho la | li lu le lo | a i u e | o va vi vu | ve vo ka ki | ku gha ng chha | "
    "ke ko ha hi | hu he ho da | di du de do | ma mi mu me | mo ta ti tu | te to pa pi | "
    "pu sha na tha | pe po ra ri | ru re ro ta | ti tu te to | na ni nu ne | no ya yi yu | "
    "ye yo ba bi | bu dha bha dha | be bo ja ji | ju je jo gha | ga gi gu ge | go sa si su | "
    "se so da di | du tha jha da | de do cha chi"
).replace("|", " ").split()
assert len(PADA_SYLLABLES) == 108

# Chokoisky table 4.1 (spec §6.5): effect of a planet ON a D1 cusp, per axis (1/7, 4/10, 6/12).
# "+" good for the team owning the cusp, "-" bad, "M" Mercury depends on rulership,
# "UR"/"NE" depend on retrograde status.
CHOK_D1 = {
    "Su": "---", "Mo": "---", "Ma": "+-+", "Ra": "+++", "Ju": "+++", "Sa": "-++",
    "Me": "MM+", "Ke": "---", "Ve": "+++", "Ur": "UUU", "Ne": "NNN", "Pl": "-+-",
}
# Chokoisky table 5.3 (spec §6.6): effect on D9 1/7 cusp. Mars, Mercury, Venus reverse vs D1.
CHOK_D9 = {"Su": "-", "Mo": "-", "Ma": "-", "Ra": "+", "Ju": "+", "Sa": "-", "Me": "+",
           "Ke": "-", "Ve": "-", "Ur": "U", "Ne": "N", "Pl": "-"}

# Chokoisky yogataras (spec §6.9), sidereal longitudes; points to the team the star touches.
STARS = {
    "Regulus": (126.0, 7.0), "Pollux": (89.5, 7.0), "Vega": (261.5, 7.0),
    "Spica": (179.92, -7.0), "Antares": (226.0, 0.0), "Algol": (56.0, -4.0),
    "Wasat": (85.0, -4.0), "Hyades": (42.0, 3.0),
}

MALEFICS = {"Sa", "Ma", "Su", "Ra", "Ke"}
BENEFICS = {"Ju", "Ve", "Me", "Mo"}
# Vedic special aspects (house offsets counted inclusively: 7 = opposite sign)
GRAHA_DRISHTI = {"Ma": (4, 7, 8), "Ju": (5, 7, 9), "Sa": (3, 7, 10), "Ra": (5, 7, 9),
                 "Ke": (5, 7, 9)}
PTOLEMAIC = {0: "conjunction", 60: "sextile", 90: "square", 120: "trine", 180: "opposition"}
# Average daily motion, used to normalise speeds (stations = near-zero ratio)
MEAN_SPEED = {"Su": 0.9856, "Mo": 13.176, "Me": 1.383, "Ve": 1.2, "Ma": 0.524, "Ju": 0.083,
              "Sa": 0.033, "Ur": 0.012, "Ne": 0.006, "Pl": 0.004, "Ra": 0.053}
CHALDEAN = ["Sa", "Ju", "Ma", "Su", "Ve", "Me", "Mo"]

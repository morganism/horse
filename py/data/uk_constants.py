"""Static reference data for UK and Irish racing."""

UK_VENUES = [
    {"name": "Cheltenham",      "country": "GB", "surface": "turf", "race_types": ["hurdle", "chase", "bumper"], "straight_furlongs": 3.5},
    {"name": "Ascot",           "country": "GB", "surface": "turf", "race_types": ["flat"], "straight_furlongs": 2.5},
    {"name": "Newmarket",       "country": "GB", "surface": "turf", "race_types": ["flat"], "straight_furlongs": 4.0},
    {"name": "Epsom",           "country": "GB", "surface": "turf", "race_types": ["flat"], "straight_furlongs": 3.5},
    {"name": "Haydock",         "country": "GB", "surface": "turf", "race_types": ["flat", "hurdle", "chase"], "straight_furlongs": 2.0},
    {"name": "Sandown",         "country": "GB", "surface": "turf", "race_types": ["flat", "hurdle", "chase"], "straight_furlongs": 2.0},
    {"name": "York",            "country": "GB", "surface": "turf", "race_types": ["flat"], "straight_furlongs": 3.0},
    {"name": "Goodwood",        "country": "GB", "surface": "turf", "race_types": ["flat"], "straight_furlongs": 2.5},
    {"name": "Kempton",         "country": "GB", "surface": "aw",   "race_types": ["flat"], "straight_furlongs": 1.5},
    {"name": "Lingfield",       "country": "GB", "surface": "aw",   "race_types": ["flat", "hurdle", "chase"], "straight_furlongs": 1.5},
    {"name": "Chester",         "country": "GB", "surface": "turf", "race_types": ["flat"], "straight_furlongs": 1.0},
    {"name": "Doncaster",       "country": "GB", "surface": "turf", "race_types": ["flat", "hurdle", "chase"], "straight_furlongs": 3.0},
    {"name": "Newbury",         "country": "GB", "surface": "turf", "race_types": ["flat", "hurdle", "chase"], "straight_furlongs": 2.5},
    {"name": "Leicester",       "country": "GB", "surface": "turf", "race_types": ["flat", "hurdle", "chase"], "straight_furlongs": 2.0},
    {"name": "Nottingham",      "country": "GB", "surface": "turf", "race_types": ["flat"], "straight_furlongs": 2.5},
    {"name": "Windsor",         "country": "GB", "surface": "turf", "race_types": ["flat"], "straight_furlongs": 1.5},
    {"name": "Wolverhampton",   "country": "GB", "surface": "aw",   "race_types": ["flat"], "straight_furlongs": 1.5},
    {"name": "Leopardstown",    "country": "IE", "surface": "turf", "race_types": ["flat", "hurdle", "chase"], "straight_furlongs": 2.0},
    {"name": "Curragh",         "country": "IE", "surface": "turf", "race_types": ["flat"], "straight_furlongs": 2.5},
    {"name": "Fairyhouse",      "country": "IE", "surface": "turf", "race_types": ["hurdle", "chase", "bumper"], "straight_furlongs": 2.0},
    {"name": "Punchestown",     "country": "IE", "surface": "turf", "race_types": ["hurdle", "chase", "bumper"], "straight_furlongs": 2.0},
    {"name": "Galway",          "country": "IE", "surface": "turf", "race_types": ["flat", "hurdle", "chase"], "straight_furlongs": 1.5},
    {"name": "Navan",           "country": "IE", "surface": "turf", "race_types": ["flat", "hurdle", "chase"], "straight_furlongs": 2.0},
    {"name": "Thurles",         "country": "IE", "surface": "turf", "race_types": ["hurdle", "chase"], "straight_furlongs": 2.0},
    {"name": "Gowran Park",     "country": "IE", "surface": "turf", "race_types": ["flat", "hurdle", "chase"], "straight_furlongs": 1.5},
]

# (name, base_win_rate) - flat rate before ability adjustment
JOCKEYS = [
    ("Frankie Dettori",    0.22), ("Ryan Moore",          0.24), ("William Buick",      0.20),
    ("Oisin Murphy",       0.19), ("Tom Marquand",        0.15), ("James Doyle",        0.17),
    ("Andrea Atzeni",      0.14), ("Silvestre de Sousa",  0.14), ("Robert Havlin",      0.12),
    ("Harry Bentley",      0.11), ("Colin Keane",         0.20), ("Shane Foley",        0.18),
    ("Seamie Heffernan",   0.19), ("Wayne Lordan",        0.16), ("Billy Lee",          0.13),
    ("Patrick Mullins",    0.17), ("Paul Townend",        0.24), ("Rachael Blackmore",  0.22),
    ("Danny Mullins",      0.18), ("Jack Kennedy",        0.21), ("Davy Russell",       0.17),
    ("AP McCoy",           0.23), ("Harry Cobden",        0.20), ("Nico de Boinville",  0.19),
    ("Barry Geraghty",     0.20), ("Mark Walsh",          0.21), ("Sam Twiston-Davies", 0.16),
    ("Noel Fehily",        0.15), ("Tom Scudamore",       0.14), ("Aidan Coleman",      0.14),
]

# (name, base_win_rate)
TRAINERS = [
    ("Aidan O'Brien",      0.28), ("John Gosden",         0.25), ("Nicky Henderson",    0.23),
    ("Willie Mullins",     0.29), ("Gordon Elliott",      0.26), ("Henry de Bromhead",  0.22),
    ("Charlie Appleby",    0.24), ("Roger Varian",        0.21), ("Mark Johnston",      0.18),
    ("Ralph Beckett",      0.19), ("Andrew Balding",      0.17), ("Marcus Tregoning",   0.14),
    ("Dermot Weld",        0.22), ("Jim Bolger",          0.20), ("Jessica Harrington", 0.21),
    ("Joseph O'Brien",     0.20), ("Paul Nicholls",       0.24), ("Colin Tizzard",      0.19),
    ("Philip Hobbs",       0.17), ("Kim Bailey",          0.14), ("Dan Skelton",        0.18),
    ("Evan Williams",      0.13), ("Donald McCain",       0.13), ("Brian Ellison",      0.12),
    ("Tim Easterby",       0.13), ("Richard Fahey",       0.15), ("Kevin Ryan",         0.13),
    ("Michael Bell",       0.14), ("Sir Michael Stoute",  0.22), ("Hugo Palmer",        0.16),
]

GOING_BY_SURFACE = {
    "turf": {
        "summer":  ["Firm", "Good to Firm", "Good"],
        "spring":  ["Good", "Good to Soft", "Soft"],
        "autumn":  ["Good", "Good to Soft", "Soft", "Heavy"],
        "winter":  ["Soft", "Heavy", "Good to Soft"],
    },
    "aw": {
        "any":     ["Standard", "Standard to Slow", "Slow"],
    },
}

# Flat racing typical distances (furlongs)
FLAT_DISTANCES = [5, 5.5, 6, 6.5, 7, 8, 9, 10, 12, 14, 16, 18, 20]
# Hurdle distances (furlongs)
HURDLE_DISTANCES = [16, 17, 18, 20, 21, 24]
# Chase distances
CHASE_DISTANCES = [16, 20, 24, 25, 28, 32]

RACE_NAME_PREFIXES = [
    "EBF", "Betfair", "Paddy Power", "Coral", "William Hill",
    "Sky Bet", "Bet365", "Ladbrokes", "Unibet", "BetVictor",
]
RACE_NAME_SUFFIXES = [
    "Novice Stakes", "Handicap", "Conditions Stakes", "Maiden Stakes",
    "Claiming Stakes", "Selling Stakes", "Novice Hurdle", "Beginners Chase",
    "Novice Chase", "Handicap Hurdle", "Handicap Chase", "Grade 1 Hurdle",
    "Grade 1 Chase", "Listed Stakes", "Group 3", "Group 2", "Group 1",
    "Bumper", "National Hunt Flat",
]

HORSE_NAME_PARTS = [
    # Prefixes / words
    "Dark", "Golden", "Silver", "Shadow", "Thunder", "Storm", "Night",
    "Star", "Fire", "Ice", "Royal", "Noble", "Swift", "Bold", "Brave",
    "Wild", "Free", "Sea", "Sky", "Sun", "Moon", "Red", "Black", "Blue",
    "Mist", "Frost", "Dawn", "Dusk", "Light", "Mighty", "Iron", "Steel",
    # Suffixes / words
    "Wind", "Flame", "Spirit", "Heart", "Force", "Strike", "Blade", "Arrow",
    "Dance", "Song", "Dream", "Vision", "Quest", "Trail", "Path", "Way",
    "Ridge", "Peak", "Vale", "Moor", "Glen", "Brook", "Chase", "Flight",
    "Charge", "Sprint", "Gallop", "Stride", "Bolt", "Flash", "Ray", "Glow",
    "Prince", "King", "Queen", "Knight", "Baron", "Duke", "Earl", "Lord",
    "Ace", "Hero", "Legend", "Champion", "Victor", "Conquer", "Reign",
]

OWNERS = [
    "Coolmore Stud", "Godolphin", "Juddmonte Farms", "Cheveley Park Stud",
    "Sheikh Mohammed", "HH Aga Khan", "Newgate Stud", "King Power Racing",
    "Gigginstown House Stud", "Ryanair", "J P McManus", "Michael O'Leary",
    "Mrs J Magnier", "Middleham Park Racing", "Qatar Racing",
    "Calumet Farm", "Ballymore Properties", "OTI Racing", "Kennet Valley TH",
    "Saeed Suhail", "Hamdan Al Maktoum", "Weld Racing Partnership",
]

SIRES = [
    "Galileo", "Frankel", "Dubawi", "Sea The Stars", "Danehill",
    "Montjeu", "Sadler's Wells", "Night of Thunder", "Kingman",
    "Dark Angel", "Invincible Spirit", "Lope de Vega", "Zoffany",
    "Fastnet Rock", "So You Think", "Oscar", "Presenting", "Stowaway",
    "Walk In The Park", "Flemensfirth", "Kayf Tara", "Milan", "Jeremy",
]

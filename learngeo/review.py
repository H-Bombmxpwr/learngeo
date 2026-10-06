"""Corrections from a whole-dataset review, 2026-09-22.

Every country's imported record was read field by field -- capitals,
currencies, languages, leaders, cities, landmarks, economy, famous people,
wars -- and anything plainly wrong was corrected here. The review was
AI-assisted: these values come from general knowledge, not from a source
opened and read on the day, which is the bar `provenance.py` holds its
records to. So they are filed separately, the country page says so, and
anything here that later gets checked against a source should move into
`provenance.FACTS`.

What was wrong, by kind, so the same mistakes are recognisable if a refetch
brings them back:

* Every euro-area country had no currency at all; France had the CFP franc,
  Cyprus "All-Russian Classifier of Currencies", Lithuania its 1990s
  talonas, Ireland "Irish euro coin".
* Language lists missing the main language (Brazil listed German, Italian and
  Japanese but not Portuguese; Germany had only minority languages; Vietnam
  had no Vietnamese), Factbook parse debris ("English ( but by 1%",
  "Including Bariba and Fulfulde"), and official-language lists built from
  regional languages (Russia with Yakut and Tuvan but not Russian).
* City lists counting a city's own districts as further cities -- Brooklyn
  and Queens, Pest and Buda, Bucharest's sectors, Yerevan's districts,
  Singapore's housing estates -- which made "largest city" and "rank this
  city" questions wrong.
* Stale office-holders left alongside their successors, and a few missing
  heads of government (India had no prime minister).
* Famous people filed under a country they are not from (Frank Sinatra under
  Italy, Tina Turner under Switzerland), and monarchs of several realms
  listed as a past leader of each, which made "which country did X lead?"
  have several right answers.
"""
from .data_util import wiki_url

REVIEWED = "2026-09-22"


def ent(name, title=None, qid=None):
    return {"name": name, "qid": qid, "wiki": wiki_url(title or name)}


EURO = ent("Euro", qid="Q4916")

# --------------------------------------------------------------------------
# Simple fields: the whole value is replaced
# --------------------------------------------------------------------------
CURRENCIES = {iso: [EURO] for iso in (
    "AD AT BE BG HR CY EE FI FR DE GR IE IT XK LV LT LU MT MC ME NL PT SM SK "
    "SI ES VA").split()}
CURRENCIES.update({
    "AO": [ent("Kwanza", "Angolan kwanza")],
    "AR": [ent("Argentine peso")],
    "BO": [ent("Boliviano", "Bolivian boliviano")],
    "CL": [ent("Chilean peso")],
    "CU": [ent("Cuban peso")],
    "ET": [ent("Birr", "Ethiopian birr")],
    "GH": [ent("Ghanaian cedi")],
    "GW": [ent("West African CFA franc")],
    "KI": [ent("Australian dollar")],
    "KR": [ent("South Korean won")],
    "LS": [ent("Loti", "Lesotho loti"), ent("South African rand")],
    "MH": [ent("United States dollar")],
    "ML": [ent("West African CFA franc")],
    "MX": [ent("Mexican peso")],
    "NA": [ent("Namibian dollar"), ent("South African rand")],
    "PE": [ent("Sol", "Peruvian sol")],
    "SV": [ent("United States dollar")],
    "TL": [ent("United States dollar")],
    "VE": [ent("Venezuelan bolívar")],
    "ZW": [ent("Zimbabwe Gold"), ent("United States dollar")],
})

CAPITALS = {
    "BJ": [ent("Porto-Novo"), ent("Cotonou")],
    "ID": [ent("Jakarta")],
    "IL": [ent("Jerusalem")],
    "NR": [ent("Yaren", "Yaren District")],
    "PK": [ent("Islamabad")],
    "PS": [ent("Ramallah"), ent("East Jerusalem")],
    "GQ": [ent("Malabo"), ent("Ciudad de la Paz")],
}

GOVERNMENT_TYPE = {
    "AD": "Parliamentary co-principality",
    "BF": "Military junta",
    "BZ": "Parliamentary democracy under a constitutional monarchy",
    "CA": "Federal parliamentary democracy under a constitutional monarchy",
    "CI": "Presidential republic",
    "CY": "Presidential republic",
    "MH": "Parliamentary republic in free association with the US",
    "ML": "Military junta",
    "NE": "Military junta",
    "SD": "Military-led transitional government",
}

FOUNDED = {
    "BA": "1992", "BT": "1907", "DK": "800", "EC": "1830", "FR": "1958",
    "IE": "1922", "KW": "1961", "LA": "1953", "LR": "1847", "LY": "1951",
    "MA": "789", "MN": "1911", "NG": "1960", "NZ": "1907", "AO": "1975",
    "PT": "1143", "QA": "1971", "RU": "1991", "SA": "1932", "SE": "900",
    "SL": "1961", "SM": "301", "SY": "1946", "TH": "1782", "TL": "2002",
    "TT": "1962", "US": "1776", "VE": "1811",
}

CALLING_CODE = {"TR": "+90", "DO": "+1809", "VA": "+39"}

HIGHEST_POINT = {
    "US": [ent("Denali")],
    "IN": [ent("Kangchenjunga")],
    "RS": [ent("Midžor")],
    "TZ": [ent("Mount Kilimanjaro")],
    "BH": [ent("Jabal ad Dukhan", "Mountain of Smoke")],
}

CLIMATE_ZONE = {
    "AO": "Tropical", "BT": "Highland or alpine", "CN": "Temperate",
    "CV": "Desert or arid", "CY": "Mediterranean", "GE": "Temperate",
    "GR": "Mediterranean", "IL": "Mediterranean", "JP": "Temperate",
    "KP": "Continental", "LY": "Desert or arid", "MN": "Continental",
    "NP": "Highland or alpine", "PS": "Mediterranean", "PT": "Mediterranean",
    "SI": "Temperate", "TM": "Desert or arid", "TN": "Mediterranean",
}

# Several were a decade stale. Rounded where the figure is an estimate.
POPULATION = {
    "CA": 41_500_000, "GB": 69_300_000, "IN": 1_450_000_000,
    "IQ": 46_118_793, "KE": 52_400_000, "MV": 515_132, "MW": 20_700_000,
    "MZ": 34_000_000, "NA": 3_022_401, "NE": 26_000_000, "NG": 232_700_000,
    "PG": 10_300_000, "PK": 241_499_431, "SO": 18_700_000, "TZ": 61_741_120,
}

AREA = {"BA": 51_209.0}

# --------------------------------------------------------------------------
# Languages
# --------------------------------------------------------------------------
# Factbook names that are phrases rather than language names, and names that
# differ from the one every other country uses for the same language.
LANG_RENAME = {
    "Afghan Persian or Dari": "Dari", "Persian Farsi": "Persian",
    "Standard Chinese or Mandarin": "Mandarin Chinese",
    "Bahasa Indonesia": "Indonesian", "Bahasa Malaysia": "Malay",
    "Kiswahili or Swahili": "Swahili", "Kiswahili": "Swahili",
    "Kingwana": "Swahili", "IsiZulu or Zulu": "Zulu",
    "IsiXhosa or Xhosa": "Xhosa", "Sepedi or Pedi": "Northern Sotho",
    "Setswana or Tswana": "Tswana", "Castilian Spanish": "Spanish",
    "Castilian": "Spanish", "Bokmal Norwegian": "Norwegian (Bokmål)",
    "Nynorsk Norwegian": "Norwegian (Nynorsk)",
    "Moldovan/Romanian": "Romanian", "Maithali": "Maithili",
    "Sangho": "Sango", "Ganda or Luganda": "Luganda",
    "Shikomoro": "Comorian", "Hakka dialects": "Hakka",
    "Chinese dialects": "Chinese", "Uzbeki": "Uzbek", "Turkmani": "Turkmen",
    "Tigrigna": "Tigrinya", "Aranese <5": "Aranese", "Mossi": "Mooré",
    "Sranang Tongo": "Sranan Tongo", "Min Nan": "Taiwanese Hokkien",
    "Approximately 16 indigenous languages": "Formosan languages",
    "Ethnic languages include Dinka": "Dinka",
    "Persian Farsi ": "Persian",
}

# Rows that are not a language at all.
LANG_DROP = {
    "no answer", "undeclared or unknown", "two mother tongues",
    "multilingual", "two languages", "thai and other languages",
    "tongan and other language", "spanish and indigenous languages",
    "samoan/english", "13 minority languages", "kiunguja",
    "many local languages", "numerous indigenous languages",
    "indian dialects", "tribal languages",
}


def L(name, share=None, official=False, status=None):
    row = {"name": name, "share": share, "official": official,
           "speakers": None}
    if status:
        row["status"] = status
    return row


# Countries whose list was wrong as a whole, replaced outright.
LANGUAGES = {
    "BR": [L("Portuguese", official=True), L("Indigenous languages"),
           L("Brazilian Sign Language")],
    "DE": [L("German", official=True), L("Turkish"), L("Russian"),
           L("Danish"), L("Frisian"), L("Sorbian")],
    "VN": [L("Vietnamese", official=True), L("English"), L("French"),
           L("Chinese"), L("Khmer")],
    "BJ": [L("French", official=True), L("Fon"), L("Yoruba"), L("Bariba"),
           L("Fula")],
    "CI": [L("French", official=True), L("Dyula"), L("Baoulé"), L("Bété"),
           L("Senufo")],
    "EG": [L("Arabic", official=True), L("English"), L("French")],
    "SB": [L("Pijin"), L("English", 2.0, official=True),
           L("Indigenous languages")],
    "LR": [L("English", 20.0, official=True), L("Kpelle"), L("Bassa")],
    "CG": [L("French", official=True), L("Lingala"), L("Kituba"),
           L("Kikongo")],
    "PH": [L("Filipino", official=True), L("English", official=True),
           L("Cebuano"), L("Ilocano"), L("Hiligaynon")],
    "TL": [L("Tetum", 36.7, official=True), L("Portuguese", official=True),
           L("Mambai", 16.6), L("Makasai", 10.5), L("Indonesian"),
           L("English")],
    "PY": [L("Guarani", 80.3, official=True), L("Spanish", 61.5, official=True)],
    "MX": [L("Spanish", 99.2, official=True), L("Indigenous languages", 6.0)],
    "TH": [L("Thai", 97.1, official=True), L("Chinese"), L("Malay")],
    "TO": [L("Tongan", 98.9, official=True), L("English", official=True)],
    "WS": [L("Samoan", 97.8, official=True), L("English", official=True)],
}

# Additions and flag changes to a list that is otherwise right.
LANG_ADD = {
    "GH": [(0, L("English", official=True))],
    "NA": [(None, L("English", 3.4, official=True))],
    "ZM": [(None, L("English", 2.0, official=True))],
    "PK": [(None, L("English", official=True))],
    "BF": [(None, L("French", status="working"))],
    "IQ": [(1, L("Kurdish", official=True))],
    "IE": [(1, L("Irish", official=True))],
    "DZ": [(1, L("Tamazight", official=True))],
    "MA": [(1, L("Tamazight", official=True))],
    "MH": [(None, L("English", official=True))],
    "MU": [(None, L("English"))],
}
LANG_FLAGS = {
    ("MD", "Romanian"): {"official": True},
    ("KG", "Kyrgyz"): {"official": True},
    ("KZ", "Russian"): {"official": True},
    ("KI", "Gilbertese"): {"official": True},
    ("CF", "Sango"): {"official": True},
    ("CI", "French"): {"official": True},
    ("EG", "Arabic"): {"official": True},
    ("ML", "French"): {"official": False, "status": "working"},
    ("BW", "Setswana"): {"status": "national"},
}

OFFICIAL_LANGUAGES = {
    "AF": ["Pashto", "Dari"], "AG": ["English"], "CN": ["Standard Chinese"],
    "GN": ["French"], "MW": ["English", "Chichewa"], "PH": ["Filipino", "English"],
    "PL": ["Polish"], "RU": ["Russian"], "SE": ["Swedish"], "SL": ["English"],
    "US": ["English"], "UY": ["Spanish"],
    "ZW": ["English", "Shona", "Northern Ndebele"],
}

# --------------------------------------------------------------------------
# Leaders
# --------------------------------------------------------------------------
# Stale office-holders the import left next to their successors. A name alone
# removes every role; (name, role) removes just that one.
LEADER_REMOVE = {
    "AL": ["Ilir Meta"], "AU": ["Peter Cosgrove"],
    "BG": ["Kiril Petkov", ("Rumen Radev", "head_of_state")],
    "BJ": ["Patrice Talon"], "CD": ["Ilunga Ilunkamba Sylvestre"],
    "CF": ["François Bozizé"], "CY": ["Nikos Anastasiades"],
    "EE": ["Kaja Kallas"], "GH": ["Nana Akufo-Addo"],
    "GW": ["Rui Duarte de Barros"], "KP": ["Kim Jae-ryong"],
    "KW": ["Sabah Al-Khalid Al-Sabah"], "KZ": ["Älihan Smaiylov"],
    "LI": ["Gerard Batliner", "Walter Kieber"],
    "LU": ["Joseph Bech", "Pierre Dupong"], "LY": ["Aguila Saleh Issa"],
    "MG": ["Andry Rajoelina", "Ruphin Zafisambo"],
    "MM": ["Myint Swe"], "MU": ["Pravind Jugnauth"],
    "MW": ["Lazarus Chakwera", "Peter Mutharika"],
    "NE": ["Hassoumi Massoudou"], "NP": ["Pushpa Kamal Dahal"],
    "NR": ["Lionel Aingimea", "Russ J Kun", "Sprent Dabwido"],
    "PS": ["Mohammad Shtayyeh"], "SD": ["Abdalla Hamdok"],
    "SM": ["Maria Luisa Berti", "Manuel Ciavatta"],
    "SO": ["Mohamed Hussein Roble"], "SZ": ["Edeupa Yerimin"],
    "TH": ["Paetongtarn Shinawatra", "Phumtham Wechayachai"],
    "TR": ["Süleyman Demirel", "Turgut Özal"],
    "TW": ["Wu Den-yih", "Lien Chan", "Frank Hsieh"],
    "VU": ["Bob Loughman"], "WS": ["Tuilaʻepa Saʻilele Malielegaoi",
                                   "Fiamē Naomi Mataʻafa"],
    "ZM": ["Edgar Lungu"],
}

HOS, HOG = "head_of_state", "head_of_government"
LEADER_ADD = {
    "CD": [("Judith Suminwa", HOG, "2024")],
    "FR": [("Emmanuel Macron", HOS, "2017")],
    "GW": [("Horta Inta-A", HOS, "2025"), ("Ilídio Vieira Té", HOG, "2025")],
    "IN": [("Narendra Modi", HOG, "2014")],
    "KW": [("Ahmad Abdullah Al-Ahmad Al-Sabah", HOG, "2024")],
    "KZ": [("Olzhas Bektenov", HOG, "2024")],
    "MG": [("Herintsalama Rajaonarivelo", HOG, "2025")],
    "MM": [("Min Aung Hlaing", HOS, "2024")],
    "MU": [("Navin Ramgoolam", HOG, "2024")],
    "MW": [("Peter Mutharika", HOS, "2025"), ("Peter Mutharika", HOG, "2025")],
    "NP": [("Balendra Shah", HOG, "2026")],
    "NR": [("David Adeang", HOG, "2023")],
    "RS": [("Đuro Macut", HOG, "2025")],
    "SD": [("Kamil Idris", HOG, "2025")],
    "SO": [("Hamza Abdi Barre", HOG, "2022")],
    "SZ": [("Russell Dlamini", HOG, "2023")],
    "TD": [("Allamaye Halina", HOG, "2025")],
    "TH": [("Anutin Charnvirakul", HOG, "2025")],
    "TW": [("Cho Jung-tai", HOG, "2024")],
    "VU": [("Jotham Napat", HOG, "2025")],
    "WS": [("Laʻauli Leuatea Schmidt", HOG, "2025")],
}

# --------------------------------------------------------------------------
# Cities: districts of one city are not further cities
# --------------------------------------------------------------------------
# Only lists that were wrong are replaced; populations are city proper,
# rounded where the census is old.
CITIES = {
    "AM": [("Yerevan", 1_086_700), ("Gyumri", 112_300), ("Vanadzor", 76_000)],
    "AO": [("Luanda", 2_776_168), ("Lubango", 600_000), ("Huambo", 595_000),
           ("Benguela", 555_000)],
    "AT": [("Vienna", 1_691_468), ("Graz", 303_270), ("Linz", 204_846),
           ("Salzburg", 157_000), ("Innsbruck", 132_000)],
    "CO": [("Bogotá", 7_901_653), ("Medellín", 2_612_958), ("Cali", 2_280_522),
           ("Barranquilla", 1_326_588), ("Cartagena", 1_059_626)],
    "EE": [("Tallinn", 394_024), ("Tartu", 97_000), ("Narva", 53_000),
           ("Pärnu", 51_000)],
    "GN": [("Conakry", 1_928_389), ("Nzérékoré", 226_426), ("Kankan", 221_428),
           ("Kindia", 181_000)],
    "GW": [("Bissau", 439_704), ("Gabú", 49_371), ("Bafatá", 22_500)],
    "HN": [("Tegucigalpa", 850_848), ("San Pedro Sula", 801_259),
           ("Choloma", 250_000), ("La Ceiba", 222_055)],
    "HU": [("Budapest", 1_741_041), ("Debrecen", 202_402), ("Szeged", 160_766),
           ("Miskolc", 150_000), ("Pécs", 140_000)],
    "IQ": [("Baghdad", 7_216_000), ("Mosul", 1_683_000), ("Erbil", 1_612_700),
           ("Basra", 1_326_564)],
    "JM": [("Kingston", 937_700), ("Portmore", 182_153),
           ("Spanish Town", 147_152), ("Montego Bay", 110_115)],
    "KE": [("Nairobi", 4_397_073), ("Mombasa", 1_208_333),
           ("Nakuru", 570_674), ("Ruiru", 490_120), ("Eldoret", 475_716)],
    "MX": [("Mexico City", 9_209_944), ("Tijuana", 1_922_523),
           ("León", 1_721_215), ("Puebla", 1_692_181),
           ("Ecatepec de Morelos", 1_645_352)],
    "NL": [("Amsterdam", 931_298), ("Rotterdam", 670_610),
           ("The Hague", 566_221), ("Utrecht", 374_238),
           ("Eindhoven", 246_417)],
    "NZ": [("Auckland", 1_693_000), ("Christchurch", 403_000),
           ("Wellington", 215_000), ("Hamilton", 185_300),
           ("Tauranga", 158_300)],
    "PK": [("Karachi", 18_868_021), ("Lahore", 13_004_135),
           ("Faisalabad", 3_691_999), ("Rawalpindi", 3_357_612),
           ("Gujranwala", 2_415_980)],
    "PW": [("Koror", 11_200)],
    "RO": [("Bucharest", 1_877_155), ("Cluj-Napoca", 286_598),
           ("Iași", 271_692), ("Timișoara", 250_849), ("Constanța", 263_688)],
    "RS": [("Belgrade", 1_197_714), ("Novi Sad", 368_967), ("Niš", 249_501),
           ("Kragujevac", 171_628), ("Subotica", 123_000)],
    "SA": [("Riyadh", 6_924_566), ("Jeddah", 3_751_722), ("Mecca", 2_427_924),
           ("Medina", 1_477_023), ("Dammam", 1_386_166)],
    "SB": [("Honiara", 92_000)],
    "SG": [("Singapore", 5_917_600)],
    "SK": [("Bratislava", 475_000), ("Košice", 229_000), ("Prešov", 82_927),
           ("Žilina", 80_000), ("Nitra", 76_000)],
    "SO": [("Mogadishu", 2_587_183), ("Hargeisa", 1_200_000),
           ("Berbera", 242_344), ("Kismayo", 234_852)],
    "SR": [("Paramaribo", 240_000), ("Lelydorp", 19_000)],
    "TJ": [("Dushanbe", 863_400), ("Khujand", 187_500), ("Bokhtar", 116_000),
           ("Kulob", 105_000)],
    "US": [("New York City", 8_258_035), ("Los Angeles", 3_820_914),
           ("Chicago", 2_664_452), ("Houston", 2_314_157),
           ("Phoenix", 1_650_070)],
}

# Where only one or two rows were districts, drop just those.
CITY_DROP = {
    "BT": ["Tsirang"], "CI": ["Abobo"], "CR": ["San Francisco"],
    "DJ": ["Balbala"], "GM": ["Bununka Kunda"], "IE": ["South Dublin"],
    "IL": ["West Jerusalem"], "JO": ["Ḩayy Khildā"], "KG": ["Manas"],
    "KH": ["Takeo"], "LA": ["Ban Khoan"], "LB": ["Ra’s Bayrūt"],
    "MK": ["Čair"], "MM": ["Hlaingthaya"], "MR": ["Dar Naim"],
    "MY": ["Kampung Baru Subang"], "PA": ["Juan Díaz"], "SS": ["Winejok"],
    "TT": ["Mon Repos"], "UZ": ["Yunusobod"], "ZA": ["Soweto"],
    "BS": ["Killarney"],
}
CITY_ADD = {"KG": [("Jalal-Abad", 123_239)], "ZA": [("Gqeberha", 1_190_000)],
            "CN": [], "IE": [("Waterford", 60_000)]}
CITY_POP = {("CN", "Beijing"): 21_858_000}

# --------------------------------------------------------------------------
# Landmarks
# --------------------------------------------------------------------------
LANDMARK_REMOVE = {
    "IE": ["Giant's Causeway"],   # County Antrim, Northern Ireland: the UK
    "AM": ["Mount Ararat"],       # Armenia's symbol, but it stands in Turkey
}
LANDMARK_ADD = {
    "AM": ["Tatev Monastery"],
    "AG": ["Nelson's Dockyard"], "BH": ["Qal'at al-Bahrain"],
    "CV": ["Pico do Fogo"], "KM": ["Mount Karthala"], "DJ": ["Lake Assal"],
    "DM": ["Boiling Lake"], "GQ": ["Monte Alén National Park"],
    "SZ": ["Mlilwane Wildlife Sanctuary"], "FM": ["Nan Madol"],
    "GA": ["Lopé National Park"], "GD": ["Grand Anse Beach"],
    "GW": ["Bijagós Archipelago"],
    "KI": ["Phoenix Islands Protected Area"],
    "XK": ["Visoki Dečani"], "LS": ["Maletsunyane Falls"],
    "LR": ["Sapo National Park"], "LI": ["Vaduz Castle"],
    "MH": ["Bikini Atoll"], "MR": ["Banc d'Arguin National Park"],
    "MC": ["Monte Carlo Casino"], "PW": ["Rock Islands"],
    "KN": ["Brimstone Hill Fortress"], "LC": ["Pitons"],
    "VC": ["Tobago Cays"], "WS": ["To Sua Ocean Trench"],
    "SM": ["Three Towers of San Marino"], "SC": ["Vallée de Mai"],
    "SL": ["Bunce Island"], "SB": ["Marovo Lagoon"],
    "ST": ["Pico Cão Grande"], "SR": ["Central Suriname Nature Reserve"],
    "TL": ["Cristo Rei of Dili"], "TO": ["Haʻamonga ʻa Maui"],
    "TV": ["Funafuti Conservation Area"], "VU": ["Mount Yasur"],
    "CM": ["Mount Cameroon"], "NR": ["Anibare Bay"],
    "BI": ["Kibira National Park"], "BZ": ["Belize Barrier Reef"],
}

# --------------------------------------------------------------------------
# Economy
# --------------------------------------------------------------------------
def P(*pairs):
    return [{"name": n, "share": s} for n, s in pairs]


ECONOMY = {
    # The Factbook line for Dominica broke on "Bahamas, The".
    "DM": {"export_partners": P(("Bahamas", 13.0), ("Saudi Arabia", 11.0),
                                ("Iceland", 10.0), ("Guyana", 7.0))},
    # "Kazakhstan 92%" is a data error in the source.
    "GM": {"export_partners": []},
    "BS": {"export_partners": P(("USA", 36.0))},
    # The source omits Russia, which takes the majority of Belarus's exports.
    "BY": {"export_partners": P(("Russia", None), ("China", None),
                                ("Kazakhstan", None))},
    "FR": {"resources": ["coal", "iron ore", "bauxite", "zinc", "uranium",
                         "antimony"]},
    "US": {"industries": ["steel", "motor vehicles", "aerospace",
                          "telecommunications", "chemicals", "electronics"]},
    "CI": {"exports": ["cocoa beans", "gold", "crude petroleum",
                       "refined petroleum", "rubber"],
           "industries": ["food processing", "wood products",
                          "oil refining", "gold mining", "textiles"],
           "resources": ["petroleum", "natural gas", "diamonds",
                         "manganese", "iron ore", "cobalt"]},
    "ML": {"industries": ["food processing", "construction",
                          "gold mining", "phosphate mining"]},
    "PG": {"industries": ["mining", "palm oil processing", "plywood",
                          "petroleum products", "construction", "tourism"]},
}

# --------------------------------------------------------------------------
# People
# --------------------------------------------------------------------------
# Not from this country, or not a person. Anyone left on more than one
# country's list is dropped from all of them by `_dedupe_people`, since
# "X is from which country?" then has more than one right answer.
FAMOUS_REMOVE = {
    "AM": ["Armenians"], "AT": ["Bertolt Brecht", "Anna Netrebko"],
    "AU": ["Russell Crowe", "J. M. Coetzee"],
    "BE": ["Pierre-Joseph Proudhon", "Claude Lévi-Strauss"],
    "BO": ["Simón Bolívar"], "CA": ["Elon Musk", "Jessica Alba"],
    "CH": ["Igor Stravinsky", "Hermann Hesse", "Percy Bysshe Shelley",
           "Alain Delon", "Tina Turner"],
    "CY": ["Greeks"], "DO": ["Mario Vargas Llosa"], "DZ": ["Miriam Makeba"],
    "EC": ["Simón Bolívar"], "ES": ["Simón Bolívar"],
    "FR": ["James Joyce", "Le Corbusier"], "GA": ["Samuel L. Jackson"],
    "GB": ["Friedrich Engels", "Oscar Wilde", "George Bernard Shaw",
           "Jimmy Wales"],
    "GH": ["Stevie Wonder"], "GQ": ["Lamine Yamal"],
    "GR": ["Greeks", "Tom Hanks", "Maria Meneghini Callas"],
    "HR": ["Garry Kasparov"],
    "HU": ["Nikola Tesla", "Josip Broz Tito", "Philipp Lenard"],
    "IE": ["Mel Gibson"],
    "IT": ["Robert De Niro", "Frank Sinatra", "John", "Benedict XVI"],
    "MA": ["Lamine Yamal"],
    "MX": ["Hernán Cortés", "Leon Trotsky", "José Martí", "Luis Buñuel"],
    "NO": ["Willy Brandt"], "PE": ["Giuseppe Garibaldi", "Leo XIV"],
    "PS": ["Palestinians"], "RO": ["Maia Sandu"],
    "RS": ["Steven Seagal", "Steve Wozniak"], "RU": ["Steven Seagal"],
    "SA": ["Idi Amin"], "SD": ["Leni Riefenstahl"], "SE": ["Willy Brandt"],
    "TL": ["António Guterres"], "UA": ["Ukrainians"],
    "AE": ["Gérard Depardieu"], "US": ["Marlene Dietrich"],
    "VA": ["Benedict XVI", "Leo XIV", "Paul VI", "John Paul I", "Pius XI"],
}
PAST_LEADER_REMOVE = {"VA": ["John"], "TW": ["Sun Yat-sen", "Yuan Shikai"]}

# --------------------------------------------------------------------------
# Wars: imported rows that are not wars, or not this country's
# --------------------------------------------------------------------------
WAR_REMOVE = {
    "CY": ["Ionian Revolt"], "SA": ["list of wars involving Saudi Arabia"],
    "BW": ["Kivu conflict"], "SG": ["Third Indochina War"],
    "MY": ["Third Indochina War"], "IN": ["Third Indochina War"],
    "SD": ["Iran–Iraq War"], "GE": ["Second Chechen War"],
    "IS": ["Kosovo War"], "CU": ["Shaba II"], "MA": ["Shaba II"],
    "UA": ["Transnistria War"], "KP": ["Indochina Wars", "Third Indochina War"],
    "KR": ["Indochina Wars"], "NZ": ["Indochina Wars"],
    "PH": ["Indochina Wars"],
    "CA": ["American Indian Wars", "Third Indochina War"],
    "MX": ["American Indian Wars", "Yaqui Wars"],
}


# --------------------------------------------------------------------------
# Applying it
# --------------------------------------------------------------------------

def _names(rows):
    return [(r.get("name") if isinstance(r, dict) else r) or "" for r in rows or []]


def apply(countries):
    """Merge every correction over the loaded dataset, in place."""
    changed = {}

    def mark(iso, field):
        changed.setdefault(iso, set()).add(field)

    for table, field in ((CURRENCIES, "currencies"), (CAPITALS, "capitals"),
                         (GOVERNMENT_TYPE, "government_type"),
                         (FOUNDED, "founded"), (CALLING_CODE, "calling_code"),
                         (HIGHEST_POINT, "highest_point"),
                         (CLIMATE_ZONE, "climate_zone"),
                         (POPULATION, "population"), (AREA, "area")):
        for iso, value in table.items():
            if iso in countries:
                countries[iso][field] = value
                mark(iso, field)

    _apply_languages(countries, mark)
    _apply_leaders(countries, mark)
    _apply_cities(countries, mark)
    _apply_landmarks(countries, mark)

    for iso, fields in ECONOMY.items():
        c = countries.get(iso)
        if c:
            c.setdefault("economy", {}).update(fields)
            mark(iso, "economy")

    for iso, names in WAR_REMOVE.items():
        c = countries.get(iso)
        if c:
            c["wars"] = [w for w in c.get("wars") or []
                         if w.get("name") not in names]
            mark(iso, "wars")
    # The import spells some wars with a hyphen and some with an en dash, so
    # Canada fought the War in Afghanistan twice.
    for iso, c in countries.items():
        seen, kept = set(), []
        for w in c.get("wars") or []:
            key = (w.get("name") or "").lower().replace("–", "-")
            if key not in seen:
                seen.add(key)
                kept.append(w)
        if len(kept) != len(c.get("wars") or []):
            c["wars"] = kept

    _dedupe_people(countries, mark)

    for iso, fields in changed.items():
        countries[iso]["reviewed"] = {"date": REVIEWED,
                                      "fields": sorted(fields)}
    return countries


def _apply_languages(countries, mark):
    # One name -> (qid, wiki) map, so a renamed or added language links to the
    # same topic page as the same language elsewhere.
    known = {}
    for c in countries.values():
        for row in (c.get("languages") or []) + (c.get("official_languages") or []):
            if isinstance(row, dict) and row.get("name") and row.get("qid"):
                known.setdefault(row["name"].strip().lower(),
                                 (row["qid"], row.get("wiki")))

    def link(row):
        qid, wiki = known.get(row["name"].lower(), (None, None))
        row.setdefault("qid", qid)
        if not row.get("qid"):
            row["qid"] = qid
        if not row.get("wiki"):
            row["wiki"] = wiki or wiki_url(row["name"] + " language")
        return row

    for iso, c in countries.items():
        rows = [r for r in c.get("languages") or [] if isinstance(r, dict)]
        before = [(r.get("name"), r.get("official")) for r in rows]
        if iso in LANGUAGES:
            rows = [dict(r) for r in LANGUAGES[iso]]
        else:
            out = []
            for r in rows:
                name = (r.get("name") or "").strip()
                if name.lower() in LANG_DROP:
                    continue
                new = LANG_RENAME.get(name, name)
                if new != r.get("name"):
                    r = dict(r, name=new, qid=None, wiki=None)
                out.append(r)
            rows = out
            for pos, row in LANG_ADD.get(iso, []):
                if any(r["name"] == row["name"] for r in rows):
                    continue
                rows.insert(len(rows) if pos is None else pos, dict(row))
        # Renames can collapse two rows into one (Comoros had "Shikomoro"
        # and "Comorian"); keep the first, but not its lesser official flag.
        seen = {}
        for r in rows:
            if r["name"] in seen:
                seen[r["name"]]["official"] = (seen[r["name"]].get("official")
                                               or r.get("official"))
                continue
            seen[r["name"]] = r
        rows = [link(r) for r in seen.values()]
        for (flag_iso, name), flags in LANG_FLAGS.items():
            if flag_iso == iso:
                for r in rows:
                    if r["name"] == name:
                        r.update(flags)
        if [(r.get("name"), r.get("official")) for r in rows] != before:
            c["languages"] = rows
            mark(iso, "languages")

    for iso, names in OFFICIAL_LANGUAGES.items():
        c = countries.get(iso)
        if c:
            c["official_languages"] = [link({"name": n}) for n in names]
            mark(iso, "official_languages")


def _apply_leaders(countries, mark):
    for iso, drops in LEADER_REMOVE.items():
        c = countries.get(iso)
        if not c:
            continue
        keep = []
        for p in c.get("leaders") or []:
            gone = any(d == p.get("name") or d == (p.get("name"), p.get("role"))
                       for d in drops)
            if not gone:
                keep.append(p)
        c["leaders"] = keep
        mark(iso, "leaders")
    for iso, adds in LEADER_ADD.items():
        c = countries.get(iso)
        if not c:
            continue
        for name, role, start in adds:
            if any(p.get("name") == name and p.get("role") == role
                   for p in c.get("leaders") or []):
                continue
            c.setdefault("leaders", []).append({
                "name": name, "role": role, "start": start, "end": None,
                "image": None, "wiki": wiki_url(name)})
        mark(iso, "leaders")


def _apply_cities(countries, mark):
    for iso, rows in CITIES.items():
        c = countries.get(iso)
        if c:
            old = {x.get("name"): x for x in c.get("cities") or []}
            c["cities"] = [dict(old.get(n, {}), name=n, population=pop,
                                wiki=(old.get(n) or {}).get("wiki") or wiki_url(n))
                           for n, pop in rows]
            mark(iso, "cities")
    for iso, names in CITY_DROP.items():
        c = countries.get(iso)
        if c:
            c["cities"] = [x for x in c.get("cities") or []
                           if x.get("name") not in names]
            mark(iso, "cities")
    for iso, rows in CITY_ADD.items():
        c = countries.get(iso)
        if c and rows:
            for n, pop in rows:
                if n not in _names(c.get("cities")):
                    c.setdefault("cities", []).append(
                        {"name": n, "population": pop, "wiki": wiki_url(n)})
            mark(iso, "cities")
    for (iso, name), pop in CITY_POP.items():
        for x in (countries.get(iso) or {}).get("cities") or []:
            if x.get("name") == name:
                x["population"] = pop
                mark(iso, "cities")
    # Largest first: the rank questions read the order.
    for iso in countries:
        cities = countries[iso].get("cities")
        if cities:
            cities.sort(key=lambda x: -(x.get("population") or 0))


def _apply_landmarks(countries, mark):
    for iso, names in LANDMARK_REMOVE.items():
        c = countries.get(iso)
        if c:
            c["landmarks"] = [m for m in c.get("landmarks") or []
                              if m.get("name") not in names]
            mark(iso, "landmarks")
    for iso, names in LANDMARK_ADD.items():
        c = countries.get(iso)
        if not c:
            continue
        marks = c.setdefault("landmarks", [])
        for name in names:
            if name not in _names(marks):
                marks.append({"name": name, "wiki": wiki_url(name)})
        mark(iso, "landmarks")


def _dedupe_people(countries, mark):
    for iso, names in FAMOUS_REMOVE.items():
        c = countries.get(iso)
        if c:
            c["famous"] = [p for p in c.get("famous") or []
                           if p.get("name") not in names]
            mark(iso, "famous")
    for iso, names in PAST_LEADER_REMOVE.items():
        c = countries.get(iso)
        if c:
            c["past_leaders"] = [p for p in c.get("past_leaders") or []
                                 if p.get("name") not in names]
            mark(iso, "past_leaders")
    # A person on two countries' lists makes "which country?" ambiguous:
    # Elizabeth II was a past leader of fifteen of them.
    for field in ("famous", "past_leaders"):
        owners = {}
        for iso, c in countries.items():
            for name in set(_names(c.get(field))):
                owners.setdefault(name, set()).add(iso)
        shared = {n for n, isos in owners.items() if len(isos) > 1}
        for iso, c in countries.items():
            rows = c.get(field) or []
            kept, seen = [], set()
            for p in rows:
                n = p.get("name")
                if n in shared or n in seen:
                    continue
                seen.add(n)
                kept.append(p)
            if len(kept) != len(rows):
                c[field] = kept
                mark(iso, field)


def fields(country):
    """The fields this review changed on one country, for its page."""
    return ((country or {}).get("reviewed") or {}).get("fields") or []

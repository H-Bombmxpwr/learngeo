"""Learning trails layered over the imported atlas, without guessing missing facts.

Civilizations describe territorial overlap, not national ancestry. Dates belong
to the polity/culture as a whole; country-specific scope is stated separately.
"""
from urllib.parse import quote


def wiki(title):
    return "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_"), safe="()")


def civilization(name, dates, places, scope, symbol, kind, article, image=None):
    return dict(name=name, dates=dates, places=places.split(), scope=scope,
                symbol=symbol, kind=kind, source=wiki(article), image=image)


CIVILIZATIONS = [
    civilization("Sumer", "c. 4500–1900 BCE", "IQ", "City-states of southern Mesopotamia, in present-day southern Iraq.",
                 "City and divine emblems survive in art. The object called the Standard of Ur is not a cloth flag; its original function is uncertain.", "Artifact, not a flag", "Sumer"),
    civilization("Maya civilization", "Preclassic c. 2000 BCE–250 CE; Classic c. 250–900 CE; later kingdoms continued", "MX GT BZ HN SV", "Southern Mexico, Guatemala, Belize and parts of Honduras and El Salvador; many separate polities, not one Maya empire. Maya peoples and cultures continue today.",
                 "Royal emblems and glyphs identified particular rulers and cities. No single flag represented this entire civilization.", "No single national flag", "Maya civilization"),
    civilization("Aztec Triple Alliance", "1428–1521 CE", "MX", "An alliance centered on Tenochtitlan, Texcoco and Tlacopan, with tributary territories across parts of central Mexico.",
                 "Military banners and city emblems existed. Mexico's modern national flag is not an Aztec flag.", "Banners and city emblems", "Aztec Empire"),
    civilization("Inca Empire", "c. 1438–1533 CE; successor resistance continued to 1572", "PE BO EC CL AR", "An Andean empire centered at Cusco, covering portions of these modern countries, not their full territory.",
                 "The rainbow flag often labeled an Inca flag is modern. The flag of Cusco does not establish an ancient national-flag design.", "Modern attribution disputed", "Flag of Cusco"),
    civilization("Ancient Egypt", "c. 3100–30 BCE", "EG", "The Nile valley and delta; borders changed greatly between dynasties.",
                 "Royal and religious standards existed; no single modern-style national flag is documented here.", "No national flag", "Ancient Egypt"),
    civilization("Indus Valley civilization", "c. 3300–1300 BCE; urban peak c. 2600–1900 BCE", "PK IN", "Settlements in present-day Pakistan and northwestern India, rather than all of either country.",
                 "Seals preserve animal motifs and an undeciphered script. They are not evidence of a national flag.", "No known flag", "Indus Valley Civilisation"),
    civilization("Achaemenid Empire", "c. 550–330 BCE", "IR IQ TR EG PK AF", "An empire centered in Iran; parts of these modern countries were held at different times, not for its entire lifespan.",
                 "Ancient accounts describe an eagle standard. Modern flag reconstructions should not be mistaken for a surviving national flag.", "Reported standard", "Achaemenid Empire"),
    civilization("Roman Empire", "27 BCE–476 CE in the West; eastern empire continued to 1453", "IT FR ES PT GB DE GR TR EG TN", "Includes only parts of some modern states: much of Britain south of Scotland, and areas west of the Rhine or south of the Danube in Germany.",
                 "The aquila was a legion's eagle standard, not a national flag. No original legionary eagle is known to survive.", "Military standard", "Aquila (Roman)"),
    civilization("Sasanian Empire", "224–651 CE", "IR IQ", "Centered in Iran and Mesopotamia; its wider frontiers shifted over time.",
                 "The Derafsh Kaviani is described as a royal banner. Its familiar modern drawings are reconstructions, not surviving cloth.", "Reconstructed royal banner", "Derafsh Kaviani"),
    civilization("Bourbon Restoration in France", "1814–1815 and 1815–1830", "FR", "Restored French monarchy, interrupted by Napoleon's Hundred Days.",
                 "A plain white royal flag replaced the revolutionary tricolour.", "Historical flag", "Flag of France", "bourbon-white.svg"),
    civilization("German Empire", "1871–1918", "DE", "A predecessor state whose borders differed from modern Germany.",
                 "Black, white and red horizontal bands; distinct from the modern black, red and gold.", "Historical flag", "Flag of Germany", "german-empire.svg"),
    civilization("Qing dynasty", "1636–1912; rule in Beijing began in 1644", "CN MN", "A Manchu-led empire that included present-day China and Mongolia; its borders changed through conquest and treaties.",
                 "The yellow dragon flag shown belongs to 1889–1912, not the entire dynasty and not ancient China.", "Historical flag · 1889–1912", "Qing dynasty", "qing.svg"),
]

ART = {
    "Sasanian Empire": ("sasanian.svg", "Derafsh Kaviani flag of the late Sassanid Empire.svg", "Oneasy; public domain on Wikimedia Commons. Modern artist's reconstruction."),
    "Qing dynasty": ("qing.svg", "Flag of China (1889–1912).svg", "Vector by Sodacan; public domain on Wikimedia Commons."),
}
for era in CIVILIZATIONS:
    if era["name"] in ART:
        filename, commons, credit = ART[era["name"]]
        era.update(image=filename, credit=credit,
                   image_source="https://commons.wikimedia.org/wiki/File:" + quote(commons.replace(" ", "_")))

# Short editorial milestones, not a claim to cover the whole country's history.
TIMELINES = {
    "FR": [("1789", "The French Revolution begins, challenging absolute monarchy."), ("1804", "Napoleon becomes emperor."), ("1958", "The Fifth Republic is established.")],
    "DE": [("1871", "German unification creates the German Empire."), ("1933–1945", "Nazi dictatorship, the Holocaust and the Second World War reshape Europe."), ("1949", "Two German states are established."), ("1990", "German reunification ends the division into East and West.")],
    "CA": [("Before European colonization", "Diverse First Nations and Inuit societies already inhabit these lands."), ("1867", "Confederation brings four provinces into the Dominion of Canada."), ("1982", "The Constitution is patriated and the Charter of Rights and Freedoms takes effect.")],
    "IN": [("c. 2600–1900 BCE", "The Indus civilization's major urban centers flourish across parts of today's India and Pakistan."), ("1947", "Independence and Partition create India and Pakistan amid mass displacement and violence."), ("1950", "India's Constitution takes effect and the country becomes a republic.")],
    "JP": [("1603", "The Tokugawa shogunate begins."), ("1868", "The Meiji Restoration begins a major political and social transformation."), ("1945", "Japan surrenders at the end of the Second World War."), ("1947", "The postwar Constitution takes effect.")],
    "ZA": [("1910", "The Union of South Africa is formed under white minority rule."), ("1948", "The National Party takes power and expands apartheid into a systematic state policy."), ("1994", "The first democratic national election with universal adult suffrage is held.")],
}

RELIGION = {
    "US": dict(official="No established national religion; the First Amendment prohibits federal establishment of religion.", largest="Christianity", year="2020 estimates (Pew, published 2025)", groups=[("Christianity", 64)], note="All-age population estimate. This is affiliation, not attendance or belief intensity; only the largest religious group is shown.", source="https://www.pewresearch.org/2025/06/09/religion-in-north-america/"),
    "AU": dict(official="No established national religion; the Commonwealth is constitutionally barred from establishing one.", largest="Christianity", year="2021 census", groups=[("Christianity", 43.9), ("No religion", 38.9), ("Islam", 3.2), ("Hinduism", 2.7)], note="Selected categories. The largest religious group need not be a majority of the population.", source="https://www.abs.gov.au/articles/religious-affiliation-australia"),
    "PK": dict(official="Islam is the state religion.", largest="Islam", year="Country overview; no percentages shown", groups=[], note="Most Muslims identify as Sunni; Shia communities and non-Muslim minorities also live here.", source=wiki("Religion in Pakistan")),
    "EG": dict(official="Islam is the state religion.", largest="Islam", year="Country overview; no percentages shown", groups=[], note="Most Muslims are Sunni. Egypt also has a longstanding Coptic Christian community; estimates of minority shares vary.", source=wiki("Religion in Egypt")),
    "IR": dict(official="Twelver Ja'fari Shia Islam is the official religion and school of law.", largest="Islam (official population classification)", year="Context; no percentages shown", groups=[], note="Official religious categories and anonymous surveys can give very different pictures of personal belief. Do not interpret official classification as a measure of private practice.", source=wiki("Religion in Iran")),
    "SA": dict(official="Islam is the state religion.", largest="Islam", year="Country overview; no percentages shown", groups=[], note="Citizenship and total-resident population are different denominators. Non-Muslim migrant communities are part of the resident population.", source=wiki("Religion in Saudi Arabia")),
    "CA": dict(official="No established state religion.", largest="Christianity", year="2021 census", groups=[("Christianity", 53.3), ("No religion or secular perspectives", 34.6)], note="Selected census categories; affiliation is not a measure of religious practice.", source="https://www150.statcan.gc.ca/n1/daily-quotidien/221026/dq221026b-eng.htm"),
    "IN": dict(official="No state religion; constitutionally secular republic.", largest="Hinduism", year="2011 census", groups=[("Hinduism", 79.8), ("Islam", 14.2), ("Christianity", 2.3), ("Sikhism", 1.7)], note="Historical census snapshot, not a claim about today's percentages. Selected categories are shown.", source="https://www.pib.gov.in/newsite/printrelease.aspx?lang=2&reg=3&relid=126326"),
    "ZA": dict(official="No established state religion.", largest="Christianity", year="2022 census", groups=[("Christianity", 85.3), ("Traditional African religion", 7.8)], note="Selected self-reported affiliation/belief categories.", source="https://census.statssa.gov.za/assets/documents/2022/P03014_Census_2022_Statistical_Release.pdf"),
    "JP": dict(official="No state religion under the postwar Constitution.", largest=None, year="Context, not a population ranking", groups=[], note="Shinto and Buddhism are major traditions and practices can overlap. Shrine or temple membership counts are not mutually exclusive population shares.", source=wiki("Religion in Japan")),
    "FR": dict(official="Secular republic; no national state religion. Local legal exceptions include Alsace-Moselle.", largest=None, year="Context, not a population ranking", groups=[], note="Catholicism has a major historical role. Surveys of identity, belief and practice measure different things; no percentage is inferred from the imported religion list.", source=wiki("Religion in France")),
    "DE": dict(official="No state church; recognized religious communities can have public-law status.", largest=None, year="Context, not a population ranking", groups=[], note="Catholic and Protestant traditions have shaped the country. Church membership and self-reported belief are different measures, so no population ranking is inferred here.", source=wiki("Religion in Germany")),
}

TRIVIA = {
    "FR": [("Which revolution began in 1789?", "The French Revolution.", "History of France"), ("Was the French flag always the tricolour?", "No. The restored Bourbon monarchy used a white flag; the tricolour returned in 1830.", "Flag of France")],
    "DE": [("In what year was Germany reunified?", "1990. The Berlin Wall opened in 1989; reunification followed the next year.", "History of Germany")],
    "CA": [("When did Canada's maple-leaf flag first fly officially?", "15 February 1965. Confederation took place much earlier, in 1867.", "Flag of Canada")],
    "IN": [("What is the wheel on India's flag?", "The Ashoka Chakra, with 24 spokes.", "Flag of India"), ("Did independence and becoming a republic happen together?", "No. Independence was in 1947; the republic began in 1950.", "History of India")],
    "JP": [("What does Hinomaru refer to?", "Japan's sun-disc flag. Its long use predates its statutory designation in 1999.", "Flag of Japan")],
    "ZA": [("What major change does South Africa's 1994 flag accompany?", "The transition to democracy and the first national election with universal adult suffrage.", "Flag of South Africa")],
}


def apply(countries):
    for iso, c in countries.items():
        c["civilizations"] = [dict(name=e["name"], wiki=e["source"]) for e in CIVILIZATIONS if iso in e["places"]]


def dossier(world, iso):
    c = world.get(iso)
    name = c["name"]
    title = (c.get("wiki_url") or wiki(name)).split("/wiki/")[-1]
    article_name = {"CN": "China", "US": "the United States", "GB": "the United Kingdom"}.get(iso, name)
    history_source = (wiki("History of " + article_name) if iso in TIMELINES
                      else (c.get("wiki_url") or wiki(name)) + "#History")
    trivia = [dict(question=q, answer=a, source=wiki(s)) for q, a, s in TRIVIA.get(iso, [])]
    # Reuse imported facts with an explicit provenance label, not fabricated trivia.
    for question, values in [
        ("What capital or capitals are recorded for " + name + "?", c.get("capitals")),
        ("Which currencies are used in " + name + "?", c.get("currencies")),
        ("Which languages are recorded for " + name + "?", c.get("languages")),
    ]:
        answer = ", ".join(v.get("name", "") if isinstance(v, dict) else v for v in values or [])
        if answer:
            trivia.append(dict(question=question, answer=answer, source=c.get("wiki_url") or wiki(name), imported=True))
    neighbours = [world.name(i) for i in world.neighbours(iso)]
    if neighbours:
        trivia.append(dict(question="Which countries share a recorded land border with " + name + "?",
                           answer=", ".join(neighbours) + ".", source=c.get("wiki_url") or wiki(name), imported=True))
    for question, value in [
        ("Which side of the road do people drive on?", c.get("drives_on")),
        ("What international calling code is recorded here?", c.get("calling_code")),
    ]:
        if value:
            trivia.append(dict(question=question, answer=str(value), source=c.get("wiki_url") or wiki(name), imported=True))
    eras = []
    for e in CIVILIZATIONS:
        if iso in e["places"]:
            eras.append(dict(e, related=[world.get(i) for i in e["places"] if i != iso and world.get(i)]))
    religion = dict(RELIGION[iso], official_source=wiki("Religion in " + article_name)) if iso in RELIGION else None
    return dict(eras=eras, timeline=TIMELINES.get(iso, []), history_source=history_source,
                religion=religion, trivia=trivia,
                reading=[("History", "History"), ("Culture", "Culture"), ("Geography", "Geography"), ("Religion", "Religion")],
                article="https://en.wikipedia.org/wiki/" + title)

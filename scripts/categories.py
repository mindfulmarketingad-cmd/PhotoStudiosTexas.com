"""Strict statewide category evidence for PhotoStudiosTexas.com. Stdlib only.

A studio qualifies for a category only when something it (or its Google
listing) published says so: its Google listing categories, its business name,
its listing description, or text on its own website (title, descriptions,
headings, menu links, and sentences on the homepage). A generic "photographer"
with no mention of the service never counts. Matching is word-bounded and has
explicit exclusions (for example "family-owned", "wedding venue", "promo").

generate_category_evidence() is run by scripts/generate_category_evidence.py,
which writes data/category-evidence.json. The site build reads that file; it
never guesses.
"""

from __future__ import annotations

import re

# id, slug, singular label (chip), page h1, short plural noun, spec id used for filter chips
CATEGORIES = [
    ("portraits", "portrait-studios", "Portraits", "Portrait Studios in Texas", "portrait studios"),
    ("family", "family-photo-studios", "Family", "Family Photo Studios in Texas", "family photo studios"),
    ("headshots", "headshot-studios", "Headshots", "Headshot Studios in Texas", "headshot studios"),
    ("weddings", "wedding-photo-studios", "Weddings", "Wedding Photo Studios in Texas", "wedding photo studios"),
    ("prom", "prom-photo-studios", "Prom", "Prom Photo Studios in Texas", "prom photo studios"),
    ("maternity", "maternity-photo-studios", "Maternity", "Maternity Photo Studios in Texas", "maternity photo studios"),
    ("christmas", "christmas-photo-studios", "Christmas", "Christmas Photo Studios in Texas", "christmas photo studios"),
    ("graduation", "graduation-photo-studios", "Graduation", "Graduation Photo Studios in Texas", "graduation photo studios"),
    ("natural-light", "natural-light-photo-studios", "Natural light", "Natural Light Photo Studios in Texas", "natural light photo studios"),
    ("prop-rental", "photo-prop-rentals", "Photo prop rental", "Photo Prop Rentals in Texas", "photo prop rentals"),
    ("newborn", "newborn-photo-studios", "Newborn & baby", "Newborn Photo Studios in Texas", "newborn photo studios"),
    ("seniors", "senior-photo-studios", "Seniors", "Senior Photo Studios in Texas", "senior photo studios"),
    ("quinceanera", "quinceanera-photo-studios", "Quinceañera", "Quinceañera Photo Studios in Texas", "quinceañera photo studios"),
    ("boudoir", "boudoir-photo-studios", "Boudoir", "Boudoir Photo Studios in Texas", "boudoir photo studios"),
    ("commercial", "commercial-photo-studios", "Commercial & product", "Commercial Photo Studios in Texas", "commercial photo studios"),
    ("real-estate", "real-estate-photo-studios", "Real estate", "Real Estate Photo Studios in Texas", "real estate photo studios"),
    ("events", "event-photo-studios", "Events", "Event Photo Studios in Texas", "event photo studios"),
    ("pets", "pet-photo-studios", "Pets", "Pet Photo Studios in Texas", "pet photo studios"),
    ("passport", "passport-photo-studios", "Passport & ID", "Passport Photo Studios in Texas", "passport photo studios"),
    ("rental", "photo-studios-for-rent", "Studio rental", "Photo Studios for Rent in Texas", "photo studios for rent"),
    ("video", "video-production-studios", "Video production", "Video Production Studios in Texas", "video production studios"),
    ("drone", "aerial-drone-photo-studios", "Aerial & drone", "Aerial and Drone Photo Studios in Texas", "aerial and drone photo studios"),
    ("photo-booth", "photo-booths", "Photo booths", "Photo Booths in Texas", "photo booths"),
    ("restoration", "photo-restoration-studios", "Photo restoration", "Photo Restoration Studios in Texas", "photo restoration studios"),
    ("classes", "photography-classes", "Classes & workshops", "Photography Classes in Texas", "photography classes"),
    ("models", "model-portfolio-studios", "Model portfolios", "Model Portfolio Studios in Texas", "model portfolio studios"),
]
NAMED_CITY_IDS = ("portraits", "family", "headshots", "weddings", "prom", "maternity", "christmas", "graduation", "natural-light", "prop-rental")

CAT_BY_ID = {c[0]: c for c in CATEGORIES}
CAT_IDS = [c[0] for c in CATEGORIES]
LISTING_SUBTYPES = {
    "portraits": {"portrait studio"},
    "weddings": {"wedding photographer"},
    "commercial": {"commercial photographer"},
    "drone": {"aerial photographer", "drone service"},
    "video": {"video production service", "videographer", "film production company"},
    "photo-booth": {"photo booth"},
    "restoration": {"photo restoration service"},
    "classes": {"photography class", "photography school"},
    "models": {"model portfolio studio"},
    "passport": {"passport photo processor"},
}

# A homepage/subpage sentence only counts as evidence when it reads like the studio describing what it offers.
OFFER = re.compile(
    r"special|\boffer|services?\b|packages?|\bwe (?:photograph|capture|shoot|provide|do|love to)\b|\bi (?:photograph|capture|shoot|provide|do|love to)\b"
    r"|(?:starts?|starting)\s+(?:at|from)|\$\s?\d|\bbook\b|galler(?:y|ies)|collections?\b|including|include|such as|focus|available|"
    r"photographer\b(?!s)|photography\b|portfolio",
    re.I,
)
NOT_OFFER = re.compile(
    r"worked with|hired|recommend|thank you|thanks|amazing|loved|highly|took me under|assist(?:ed|ing)?\b|second photographer|"
    r"\bmy (?:husband|wife|daughter|son|mom|dad|sister|brother|friend|fianc)|\bwas (?:so|very|such|absolutely|the best)|had the (?:pleasure|opportunity)|"
    r"experience with|restor(?:e|ation|ing)|repair|damaged|scan(?:ning)?\b|digiti[sz]|heirloom|prom dress|bridesmaid|"
    r"picking out|\bour (?:daughter|son)\b|let me know|reviews?\b|testimonial|rating|lessons? learned|my (?:own )?wedding|tips|how to|why you|workshops?|mentor|educat|\bteach|courses?\b|\bperfect for\b|\bideal for\b|\bgreat for\b|\bour (?:boy|girl|baby|little)|\bsessions? (?:with|was|were)\b|have used|used this studio|i am a photographer with",
    re.I,
)
SERVICE_WORDS = re.compile(r"wedding|bridal|famil(?:y|ies)|portrait|headshot|newborn|maternity|senior|graduat|engagement|branding|birthday|prom|couples|children|kids|baby|babies|boudoir|event|quincea|christmas|holiday|santa|grads?\b|newborn|senior|commercial|product|branding|drone|aerial|passport|videograph|cinematograph|booth|restoration|workshop|portfolio|real estate|pets?\b", re.I)
RENTAL_NAME = re.compile(r"\b(?:rentals?|rent|self[- ]?(?:service|portrait|photo|shoot|studio)|selfie|photo ?booth|cyc|loft|space|spaces|rooms?|hourly|venue|sets?)\b", re.I)
RENTAL_SITE = re.compile(
    r"studio\s+(?:rentals?|for\s+rent)|hourly\s+bookings?|rent(?:al)?\s+(?:the|our|a)\s+(?:\w+\s+){0,2}(?:studio|space)|(?:hourly|daily)\s+(?:rental|rate)|"
    r"self[- ]?(?:serve|service|shoot|portrait|photo)|selfie\s+(?:studio|museum)|photographers?\s+(?:can|may|to)\s+(?:rent|book)|rentable|"
    r"book\s+(?:our|the)\s+(?:studio|space)|space\s+rentals?",
    re.I,
)

PHOTO_CTX = r"photo|portrait|session|shoot|picture|studio|camera|image|capture|gown|album|print"

# Short texts: name, titles, descriptions, headings, menu labels, URL paths.
SHORT = {
    "portraits": re.compile(r"\bportrait(?:s|ure)?\b(?!\s*(?:mode|orientation|lens|format|layout|size|view|style\s+print))", re.I),
    "headshots": re.compile(r"\bhead\s?-?shots?\b|\bacting\s+(?:photos|portraits)\b|\blinkedin\s+(?:profile\s+)?(?:photos?|portraits?)\b", re.I),
    "weddings": re.compile(r"\bwedding(?:s)?\b|\bbridal\b|\belopement(?:s)?\b", re.I),
    "prom": re.compile(r"\bproms?\b", re.I),
    "maternity": re.compile(r"\bmaternity\b|\bpregnancy\s+(?:photo\w*|portrait\w*|session\w*|shoot\w*)\b|\bexpecting\s+(?:mother|mom|mama)s?\s+(?:photo|portrait|session)", re.I),
    "family": re.compile(
        r"\bfamil(?:y|ies)\s*(?:&|and)?\s*(?:photo\w*|portrait\w*|session\w*|picture\w*|shoot\w*|mini[- ]?session\w*|headshot\w*|photographer\w*|kids|children|couples)\b"
        r"|(?:photo\w*|portrait\w*|session\w*|picture\w*|shoot\w*|photographer\w*)\s+(?:of|for|with)\s+(?:your\s+|the\s+|a\s+|our\s+)?famil(?:y|ies)\b"
        r"|^\s*(?:families|family)(?:\s*(?:&|and|\+)\s*\w+)?\s*$"
        r"|\b(?:couples|seniors?|newborns?|maternity|children|kids|babies|weddings?|portraits?)\s*(?:,|&|and|\||/)\s*(?:and\s+)?famil(?:y|ies)\b(?!\s+(?:reunions?|gatherings?|events?|members?|business|owned))"
        r"|\bfamil(?:y|ies)\s*(?:,|&|and|\||/)\s*(?:couples|seniors?|newborns?|maternity|children|kids|babies|weddings?|portraits?|pets?)\b",
        re.I),
    "christmas": re.compile(
        r"\bchristmas\s+(?:photo|portrait|session|mini|minis|shoot|picture|photography|experience)"
        r"|\b(?:photo|portrait|session|mini|minis|shoot|picture|photography)\w*\s+(?:of|for|with)?\s*(?:christmas|santa)\b"
        r"|\bholiday\s+(?:mini|minis|photo|portrait|session|shoot|picture|photography)\w*"
        r"|\b(?:mini|minis|photo|portrait|session|shoot|picture|photography)\w*\s+(?:for\s+)?(?:the\s+)?holidays?\b"
        r"|\bsanta(?:\s+claus)?(?:'s)?\s+(?:photo|portrait|session|picture|shoot|mini|experience|visit|portraits)"
        r"|\b(?:photos?|portraits?|pictures?|sessions?)\s+with\s+santa"
        r"|\bmagic of santa\b|\bchristmas\s+minis?\b|\bxmas\s+(?:photo|portrait|session|mini)"
        r"|^\s*(?:christmas(?:\s+minis?)?|holiday\s+minis?|santa(?:\s+(?:photos?|portraits?|sessions?|minis?))?)\s*$",
        re.I),
    "graduation": re.compile(
        r"\bgraduation(?:s)?\b|\bgraduates?\b|\bgrads?\b(?!\s+(?:school|student|program|degree|studies))"
        r"|\bcap\s*(?:and|&|\+)\s*gown\b|\bsenior\s+graduation|\bcollege\s+grads?"
        r"|\bgrad\s+(?:photo|portrait|session|shoot|picture|package|mini|photographer)",
        re.I),
    "newborn": re.compile(
        r"\bnewborns?\b|\bcake\s*smash\b|\binfants?\s+(?:photo|portrait|session|shoot)"
        r"|\bbab(?:y|ies)\s+(?:photo|portrait|session|shoot|photography)"
        r"|^\s*(?:newborns?|cake\s*smash|bab(?:y|ies))\s*$", re.I),
    "seniors": re.compile(
        r"\bsenior\s+(?:photo|portrait|session|pictures?|photographer|minis?|pics?)"
        r"|\bhigh\s+school\s+seniors?\b|\bseniors?\s+(?:photo|portrait|session|pictures?|photographer|minis?)"
        r"|\bclass of 20\d\d\b|^\s*(?:seniors?|high\s+school\s+seniors?)\s*$", re.I),
    "quinceanera": re.compile(
        r"\bquincea[nñ]eras?\b|\bquinces?\b|\bxv\s*(?:a[nñ]os)?\b|\b15\s+a[nñ]os\b", re.I),
    "boudoir": re.compile(r"\bboudoir\b", re.I),
    "commercial": re.compile(
        r"\bcommercial\s+(?:photo|photography|photographer)"
        r"|\bproduct\s+(?:photo|photography|photographer|shots?)"
        r"|\be-?commerce\s+(?:photo|photography)"
        r"|\bbranding\s+(?:photo|photos|session|shoot|photography)"
        r"|\bcorporate\s+(?:photo|photography)(?!\s*headshots?)", re.I),
    "real-estate": re.compile(
        r"\breal\s*estate\s+(?:photo|photography|photographer|media|video)"
        r"|\blisting\s+photos?\b|\bproperty\s+(?:photo|photography|photographer)"
        r"|\barchitectural\s+(?:photo|photography)|^\s*real\s*estate\s*$", re.I),
    "events": re.compile(
        r"\bevents?\s+(?:photo|photography|photographer|coverage|videography)"
        r"|\b(?:photo|photography|photographer|coverage)\s+(?:of|for)\s+(?:your\s+|the\s+)?events?"
        r"|\bparty\s+(?:photo|photography|photographer)|^\s*events?\s*$", re.I),
    "pets": re.compile(
        r"\bpets?\s+(?:photo|portrait|session|photography|photographer|pics?|pictures?)"
        r"|\b(?:dog|canine|cat|equine|horse)\s+(?:photo|portrait|session|photography)"
        r"|\bpet\s+portraits?\b|^\s*(?:pets?|pet\s+photography|dog\s+photography)\s*$", re.I),
    "passport": re.compile(r"\bpassport\s+(?:photos?|pictures?|portraits?)\b|\bvisa\s+photos?\b|\bid\s+photos?\b", re.I),
    "rental": re.compile(
        r"\bstudio\s+rentals?\b|\brental\s+studios?\b|\bstudio\s+for\s+rent\b"
        r"|\brent\s+(?:our|the|a)\s+(?:photo\s+|photography\s+)?studios?"
        r"|\bhourly\s+(?:studio\s+)?rentals?\b|\bself[- ](?:service|portrait|shoot)\s+studios?", re.I),
    "video": re.compile(
        r"\bvideograph(?:y|er|ers)?\b|\bvideo\s+productions?\b|\bcinematograph(?:y|er)?"
        r"|\b(?:wedding|event)\s+films?\b|\bvideo\s+services?\b|^\s*(?:video|videography|films?)\s*$", re.I),
    "drone": re.compile(
        r"\bdrone\s+(?:photo|photography|photographer|video|operator|services?|shots?)"
        r"|\baerial\s+(?:photo|photography|photographer|video|shots?|drone)|\buav\b"
        r"|^\s*(?:drone|aerial|drone\s+photography|aerial\s+photography)\s*$", re.I),
    "photo-booth": re.compile(r"\bphoto\s*booths?\b|\bselfie\s+booths?\b|\b360\s+(?:photo\s*)?booths?\b|\bphotobooths?\b", re.I),
    "restoration": re.compile(
        r"\bphoto\s+restoration\b|\brestor(?:e|ation|ing)\s+(?:old\s+)?(?:photos?|photographs?|pictures?)"
        r"|\bphoto\s+repair\b|^\s*(?:restoration|photo\s+restoration)\s*$", re.I),
    "classes": re.compile(
        r"\bphotography\s+(?:classes|class|workshops?|courses?|lessons?|schools?|mentorship)"
        r"|\bphoto\s+(?:classes|class|workshops?|lessons?)"
        r"|\bworkshops?\s+for\s+photographers|^\s*(?:classes|workshops?|photography\s+classes)\s*$", re.I),
    "models": re.compile(
        r"\bmodel\s+portfolios?\b|\bmodeling\s+(?:photo|photos|portfolio|headshots?|photography)"
        r"|\bcomp\s+cards?\b|^\s*(?:model\s+portfolios?|modeling)\s*$", re.I),
    "natural-light": re.compile(
        r"natural[- ]lights?\s+(?:outdoor\s+|on[- ]location\s+)?(?:photo\s+)?(?:studios?|photography|photographers?|sessions?|portraits?|minis?|space|room|lifestyle)"
        r"|(?:all[- ]white,?\s+)?natural[- ]lights?\s+(?:and\s+studio\s+)?(?:photography|photographers?|studios?)"
        r"|\b(?:daylight|sunlit|sun[- ]lit|naturally[- ]lit)\s+(?:photo\s+)?(?:studios?|space|room|floor|photography)"
        r"|\bnorth[- ]facing\s+windows?"
        r"|\bwindow[- ]lights?\s+(?:studios?|portraits?|photography|sessions?)"
        r"|\bspecializ(?:e|es|ed|ing)\s+in\s+(?:[a-z,&/ ]{0,40})?natural[- ]lights?"
        r"|\b(?:studios?|space|room)\s+(?:with |featuring |filled with |that (?:has|have|features) )?(?:beautiful |soft |ample |abundant |bright |gorgeous )?natural[- ]lights?(?:ing)?"
        r"|\b(?:feature[sd]?|featuring|filled with|ample|abundant|bright)\s+(?:beautiful )?(?:natural[- ]lights?|natural lighting)"
        r"|\bnatural[- ]lights?\s+(?:portrait|lifestyle)\s+photographers?"
        r"|\bproviding\s+natural[- ]lights?"
        r"|\bnatural[- ]lights?\s+and\s+studios?"
        r"|\bnatural[- ]lights?\s+enters"
        r"|\bnatural[- ]lights?\s*(?:&|and)\s+(?:all\s+)?lighting"
        r"|^\s*natural[- ]lights?\s*$",
        re.I),
    "prop-rental": re.compile(
        r"\bprop[- ]rentals?\b|\bbackdrop[- ]rentals?\b"
        r"|\b(?:photo(?:graphy)?\s+)?(?:studio\s+)?equipment\s+rentals?\b"
        r"|\b(?:camera|grip|lighting)\s+(?:and\s+(?:studio\s+)?)?rentals?\b"
        r"|\bprop\s+library\b|\bbackdrop\s+library\b"
        r"|\bset[- ]rentals?\b|\brent the sets\b|\bphotography\s+set\s+rentals?\b"
        r"|\brent(?:al|als|ing)?\s+(?:of\s+|our\s+|the\s+|a\s+)?(?:photo\s+|photography\s+)?(?:props?|backdrops?|sets?)\b"
        r"|\b(?:props?|photo(?:graphy)?\s+equipment)\s+(?:for\s+)?(?:rent|rentals?|renters?|photographers?|content creators?)"
        r"|\bbackdrops?\s+(?:for\s+)?(?:rent|rentals?|renters?)",
        re.I),
}


# Sentences from a website body (weaker source: require a service context in the sentence).
BODY = {
    "portraits": re.compile(r"\bportrait(?:s|ure)?\b", re.I),
    "headshots": SHORT["headshots"],
    "weddings": re.compile(r"\bwedding(?:s)?\b|\bbridal\b|\belopement(?:s)?\b", re.I),
    "prom": SHORT["prom"],
    "maternity": re.compile(r"\bmaternity\b|\bpregnancy\s+(?:photo\w*|portrait\w*|session\w*|shoot\w*)", re.I),
    "family": SHORT["family"],
    "christmas": SHORT["christmas"],
    "graduation": SHORT["graduation"],
    "newborn": SHORT["newborn"],
    "seniors": SHORT["seniors"],
    "quinceanera": SHORT["quinceanera"],
    "boudoir": SHORT["boudoir"],
    "commercial": SHORT["commercial"],
    "real-estate": SHORT["real-estate"],
    "events": SHORT["events"],
    "pets": SHORT["pets"],
    "passport": SHORT["passport"],
    "rental": SHORT["rental"],
    "video": SHORT["video"],
    "drone": SHORT["drone"],
    "photo-booth": SHORT["photo-booth"],
    "restoration": SHORT["restoration"],
    "classes": SHORT["classes"],
    "models": SHORT["models"],
    "natural-light": SHORT["natural-light"],
    "prop-rental": SHORT["prop-rental"],
}
BODY_CTX = {
    "portraits": re.compile(r"photograph|photos?\b|session|studio|specializ|offer|capture|shoot|book|packages?|sittings?", re.I),
    "headshots": re.compile(r".", re.I),
    "weddings": re.compile(r"photograph|photos?\b|photography|cinematograph|videograph|film\b|session|capture|coverage|packages?|shoot", re.I),
    "prom": re.compile(r"photo|portrait|picture|session|studio|dance|homecoming|formal|senior", re.I),
    "maternity": re.compile(PHOTO_CTX + r"|bump|expecting", re.I),
    "family": re.compile(r".", re.I),
    "christmas": re.compile(r"photo|portrait|session|mini|shoot|picture|studio|santa|holiday|christmas", re.I),
    "graduation": re.compile(r"photo|portrait|session|shoot|picture|studio|cap|gown|senior|diploma|graduate", re.I),
    "newborn": re.compile(r"photo|portrait|session|shoot|picture|studio|newborn|baby|infant|smash", re.I),
    "seniors": re.compile(r"photo|portrait|session|shoot|picture|studio|senior|graduation|school", re.I),
    "quinceanera": re.compile(r"photo|portrait|session|shoot|picture|studio|quince|coverage", re.I),
    "boudoir": re.compile(r"photo|portrait|session|shoot|studio|boudoir", re.I),
    "commercial": re.compile(r"photo|photography|session|shoot|studio|product|brand|commercial", re.I),
    "real-estate": re.compile(r"photo|photography|video|media|listing|property|aerial", re.I),
    "events": re.compile(r"photo|photography|videograph|coverage|shoot|studio|event", re.I),
    "pets": re.compile(r"photo|portrait|session|shoot|picture|studio|pet|dog|cat", re.I),
    "passport": re.compile(r"photo|picture|passport|visa|id", re.I),
    "rental": re.compile(r"rent|studio|hourly|space|book", re.I),
    "video": re.compile(r"video|film|cinema|production|shoot|coverage", re.I),
    "drone": re.compile(r"drone|aerial|photo|video|uav", re.I),
    "photo-booth": re.compile(r"booth|photo|rental|event", re.I),
    "restoration": re.compile(r"restor|repair|photo|scan|digit", re.I),
    "classes": re.compile(r"class|workshop|course|lesson|school|mentor|teach|learn", re.I),
    "models": re.compile(r"model|portfolio|comp card|headshot|photo", re.I),
    "natural-light": re.compile(r"photo|portrait|session|shoot|studio|space|room|light|window|photography|photographer", re.I),
    "prop-rental": re.compile(r"rent|rental|prop|backdrop|set|equipment|library|camera|grip|lighting", re.I),
}

# Exclusions applied to any matched text.
EXCLUDE = {
    "weddings": re.compile(
        r"wedding\s+(?:venue|planner|planning|dress|gown|cake|invitation|favors?|florist|flowers?|dj|band|chapel|hall|reception|rental|decor|coordinator|catering|caterer|officiant|jewelry|rings?|registry|shop|boutique|barn|ceremony space)s?\b"
        r"|(?:venue|chapel|hall|barn)\s+for\s+weddings?|weddings?\s+and\s+events?\s+venue|bridal\s+(?:shop|boutique|salon|gown|boudoir|beauty|makeup|hair)s?\b",
        re.I),
    "maternity": re.compile(r"maternity\s+(?:clothing|clothes|wear|leave|care|ward|hospital|store|boutique|shop|bra|insurance|nurse|center|centre|medical|health|services?)\b|pregnancy\s+(?:care|resource|help|center|centre|test|clinic|support)", re.I),
    "family": re.compile(r"\bfamil(?:y|ies)[- ](?:owned|run|operated|business|friendly|oriented|centered|style|first|tradition|company|farm|legacy)\b|\b(?:our|my|a|the|your|their)\s+family\s+(?:business|owned|is|of|has|and\s+I)\b", re.I),
    "portraits": re.compile(r"\bportrait\s+(?:mode|orientation|lens|format|layout|view|painting|artist|drawing)s?\b|\b(?:painted|drawn|charcoal|pencil|oil)\s+portraits?\b", re.I),
    "headshots": re.compile(r"$^"),
    "prom": re.compile(r"$^"),
    "christmas": re.compile(
        r"closed?\s+(?:for\s+)?(?:the\s+)?(?:christmas|holidays?)"
        r"|(?:christmas|holiday)\s+(?:hours?|closure|closings?|schedule|break|weekend|travel|office)"
        r"|happy\s+holidays|merry\s+christmas|season'?s\s+greetings"
        r"|(?:closed|out of office|unavailable)\s+(?:on|through|from|during).{0,40}(?:christmas|holiday)"
        r"|christmas\s+(?:gift\s+cards?|gifts?(?!\s+session)|tree(?:s|\s+farm)?(?!\s+photo)|decor|ornaments?|market)"
        r"|holiday\s+(?:gift\s+cards?|hours?|closure|closings?|schedule)"
        r"|\bchristmas\s+20\d\d\b(?!\s+(?:mini|session|photo|portrait))"
        r"|\b(?:christmas|holiday)\s+(?:galler(?:y|ies)|albums?)\b"
        r"|tree\s+farm(?!\s+photo)",
        re.I),
    "graduation": re.compile(
        r"graduation\s+(?:gowns?|dresses?|caps?(?!\s+and\s+gown)|announcements?|invitations?|party\s+(?:venue|rental)|hall|supplies|tickets?)"
        r"|\b(?:cap\s*(?:and|&)\s*gown)\s+(?:rental|rentals|sales?|shop|store|seller)"
        r"|(?:rent|sale|shop|store|buy)\s+(?:a\s+|your\s+)?(?:cap\s*(?:and|&)\s*gown|graduation\s+gown)"
        r"|undergraduate|graduate\s+(?:school|program|degree|student|studies)"
        r"|(?:nyip|college|university|institute)\s+graduate|\bgraduate\s+of\b"
        r"|\b(?:i'?m|i am|we are|she is|he is)\s+(?:a\s+)?(?:proud\s+)?graduate"
        r"|(?:high\s+)?school\s+(?:district|campus)\b|yearbook\s+contract"
        r"|gown\s+(?:shop|store|rental|seller)"
        r"|beyond the cap and gown|congrats(?:ulations)?\s+to\s+(?:all\s+)?graduates"
        r"|after graduation"
        r"|flower walls?",
        re.I),
    "newborn": re.compile(r"baby\s+(?:store|shop|clothes|clothing|sitting|sitter|formula|gear)|newborn\s+(?:care|nurs|hospital|unit)", re.I),
    "seniors": re.compile(r"senior\s+(?:living|care|center|citizens?|discount|community|housing|homes?|meals?)", re.I),
    "quinceanera": re.compile(r"quincea[nñ]era\s+(?:venue|hall|dress|gown|planner|planning|decor|rental|shop|boutique)", re.I),
    "boudoir": re.compile(r"$^"),
    "commercial": re.compile(r"commercial\s+(?:real\s+estate|property|lease|space|kitchen|driver|insurance)", re.I),
    "real-estate": re.compile(r"real\s+estate\s+(?:agent|agency|broker|office|listings? for sale|for sale)|realtor\.com", re.I),
    "events": re.compile(r"event\s+(?:venue|venues|space|hall|planner|planning|rental|center|centre)|party\s+(?:venue|rental|hall)", re.I),
    "pets": re.compile(r"\b(?:vet(?:erinarian)?|pet\s+(?:store|shop|groom|boarding|sitter|food|adoption))\b", re.I),
    "passport": re.compile(r"passport\s+(?:office|agency|services?|application|renewal)(?!\s+photo)", re.I),
    "rental": re.compile(r"$^"),
    "video": re.compile(r"\byoutube\b|watch the video|music videos? (?:and|&) ,|tiktok", re.I),
    "drone": re.compile(r"$^"),
    "photo-booth": re.compile(r"$^"),
    "restoration": re.compile(r"restor(?:e|ing|ation)\s+(?:the|my|our)\s+(?:faith|trust|confidence|emotion|relationship)", re.I),
    "classes": re.compile(r"took a (?:class|workshop)|attended (?:a |the )?(?:class|workshop)|photography school graduate", re.I),
    "models": re.compile(r"role models?|model (?:home|home|airplane|train|car)\b|model released", re.I),
    "natural-light": re.compile(
        r"natural[- ]look|naturally[- ]looking"
        r"|sunlit\s+(?:veranda|aisle|ceremony|reception|garden|afternoon|morning|day|charm)"
        r"|embraced natural light"
        r"|depend on natural light"
        r"|must have (?:good )?natural light"
        r"|emanating from the sun"
        r"|mimic the natural light"
        r"|drawn to natural light"
        r"|capturing natural light"
        r"|capture natural light"
        r"|using natural light and"
        r"|golden natural light"
        r"|natural light charm"
        r"|perfect for natural light portraits",
        re.I),
    "prop-rental": re.compile(
        r"(?:stunning|perfect|beautiful|ideal|scenic|serene)\s+backdrop"
        r"|backdrop for (?:your |the )?(?:wedding|portraits?|photos?|photographers?|creatives?|event)"
        r"|pose your (?:baby|child|subject).{0,40}props"
        r"|(?:two|our|different)\s+props"
        r"|short[- ]term rental|rental properties"
        r"|styled with .{0,30}props"
        r"|using (?:our |the |different )?props"
        r"|props and outfits provided"
        r"|choose your favorite"
        r"|fake snow"
        r"|perfect backdrop for (?:your |the )?(?:wedding|portraits?|photos?)",
        re.I),
}


NONPHOTO_SUBTYPES = {
    "wedding venue", "wedding chapel", "banquet hall", "event venue", "event planner", "wedding planner",
    "party planner", "bridal shop", "maternity store", "baby store", "baby clothing store", "pregnancy care center",
    "medical clinic", "hair salon", "hairdresser", "beauty salon", "clothing store", "boutique", "dance school",
    "dance hall", "music school", "church", "coworking space", "recording studio", "wedding service",
    "full dress rental service", "party equipment rental service", "dj service", "catering food and drink supplier",
    "winery", "garden", "event management company", "conference center", "festival hall", "live music venue",
    "art school", "senior high school", "meeting planning service", "party store", "women's clothing store",
    "children's party service", "farm", "retreat center", "makerspace",
}
PHOTOGRAPHER_SUBTYPES = {
    "photographer", "portrait studio", "wedding photographer", "commercial photographer", "photography service",
    "aerial photographer", "model portfolio studio", "photo agency",
}
PHOTO_NAME = re.compile(r"photo|portrait|image|picture|camera|lens|foto|film|video|cinema|studio|capture|moments|memories|shutter|pixel|click|snap", re.I)

SOURCE_LABEL = {
    "listing categories": "its Google listing categories",
    "business name": "its business name",
    "listing description": "its Google listing description",
    "booking page": "its booking page link",
    "website title": "its website title",
    "website description": "its website description",
    "website heading": "a heading on its website",
    "website menu": "a menu link on its website",
    "website text": "text on its website",
}
STRONG_ORDER = ["listing categories", "business name", "listing description", "website title", "website description",
                "website heading", "website menu", "booking page", "website text"]


def _short_hit(cat: str, text: str) -> str | None:
    if not text:
        return None
    if EXCLUDE[cat].search(text):
        return None
    m = SHORT[cat].search(text)
    return m.group(0) if m else None


def _body_hit(cat: str, text: str) -> str | None:
    if not text or EXCLUDE[cat].search(text):
        return None
    if cat in {"natural-light", "prop-rental"}:
        # The phrase itself is the offering (a "natural light studio" sentence need not also
        # say "we offer"). Still drop testimonials and review blurbs.
        if re.search(r"testimonial|reviews?\b|thank you|thanks|worked with|hired|recommend|"
                     r"\bmy (?:husband|wife|daughter|son|mom|dad|sister|brother|friend|fianc)", text, re.I):
            return None
        if not BODY[cat].search(text) or not BODY_CTX[cat].search(text):
            return None
        return BODY[cat].search(text).group(0)
    if NOT_OFFER.search(text) or not OFFER.search(text):
        return None
    words = {w.lower() for w in SERVICE_WORDS.findall(text)}
    if len(words) < 1:
        return None
    if not BODY[cat].search(text) or not BODY_CTX[cat].search(text):
        return None
    return BODY[cat].search(text).group(0)


def photographer_like(studio: dict) -> bool:
    subtypes = {s.lower() for s in studio.get("subtypes") or []}
    if subtypes & PHOTOGRAPHER_SUBTYPES:
        return True
    if not (subtypes & NONPHOTO_SUBTYPES):
        return True
    return bool(re.search(r"photo|portrait|image|picture|camera|lens|foto|capture|shutter", studio.get("name") or "", re.I))


def rental_like(studio: dict, enrich: dict, evidence: dict) -> bool:
    """Space-rental and self-service studios provide a room, not the photography."""
    subtypes = {s.lower() for s in studio.get("subtypes") or []}
    if subtypes & PHOTOGRAPHER_SUBTYPES:
        return False
    if RENTAL_NAME.search(studio.get("name") or ""):
        return True
    probe = " | ".join(filter(None, [
        (evidence or {}).get("title"), *((evidence or {}).get("meta") or []),
        (enrich or {}).get("title"), (enrich or {}).get("description"), studio.get("description"),
    ]))
    return bool(RENTAL_SITE.search(probe))


def _path_text(path: str) -> str | None:
    path = (path or "").strip()
    segs = [p for p in path.strip("/").split("/") if p]
    if not segs or len(segs) > 2:
        return None
    if re.match(r"^(blog|news|post|posts|20\d\d|tag|category|author|page|wp-)", segs[0], re.I):
        return None
    return re.sub(r"[-_.]+", " ", " ".join(segs))


def generate_category_evidence(studio: dict, enrich: dict | None, evidence: dict | None) -> dict[str, list[dict]]:
    """category id -> ordered evidence list [{'source', 'text'}]. Empty when nothing qualifies."""
    enrich = enrich or {}
    evidence = evidence or {}
    found: dict[str, list[dict]] = {}

    def add(cat: str, source: str, text: str, page: str = "", hit: str = "") -> None:
        items = found.setdefault(cat, [])
        if any(i["source"] == source for i in items):
            return
        clean = re.sub(r"\s+", " ", text).strip()
        if len(clean) > 200 and hit and hit.lower() in clean.lower():
            at = clean.lower().index(hit.lower())
            start = max(0, min(at - 80, len(clean) - 200))
            clean = ("\u2026" if start else "") + clean[start:start + 200] + ("\u2026" if start + 200 < len(clean) else "")
        elif len(clean) > 200:
            clean = clean[:200]
        item = {"source": source, "text": clean}
        if page:
            item["page"] = page
        items.append(item)

    subtypes = {s.lower() for s in studio.get("subtypes") or []}
    for cat_id, wanted in LISTING_SUBTYPES.items():
        hit = subtypes & {s.lower() for s in wanted}
        if hit:
            add(cat_id, "listing categories", "Google category: " + next(iter(sorted(hit))).title())

    shorts = [("business name", studio.get("name") or ""),
              ("listing description", studio.get("description") or ""),
              ("booking page", re.sub(r"[-_/.]+", " ", (studio.get("booking_link") or "").split("//", 1)[-1]))]
    ok_enrich = str(enrich.get("status")) in {"200"}
    ok_evid = str(evidence.get("status")) == "200"
    if ok_enrich or ok_evid:
        titles = [evidence.get("title") if ok_evid else None, enrich.get("title") if ok_enrich else None]
        for t in titles:
            if t:
                shorts.append(("website title", t))
        metas = (evidence.get("meta") if ok_evid else []) or []
        if ok_enrich and enrich.get("description"):
            metas = list(metas) + [enrich["description"]]
        for m in metas:
            shorts.append(("website description", m))
        heads = list((evidence.get("headings") if ok_evid else []) or [])
        topics = list(enrich.get("topics") or []) if ok_enrich else []
        for h in heads:
            shorts.append(("website heading", h))
        links = list((evidence.get("links") if ok_evid else []) or [])
        for label, path in links:
            if label:
                shorts.append(("website menu", label))
            pt = _path_text(path)
            if pt:
                shorts.append(("website menu", pt))
        for t in topics:
            # enrichment topics mix menu labels (<=40 chars) and headings
            shorts.append(("website menu" if len(t) <= 40 else "website heading", t))
    for source, text in shorts:
        for cat in CAT_IDS:
            hit = _short_hit(cat, text)
            if hit:
                add(cat, source, text, hit=hit)
    if ok_evid:
        for sentence in evidence.get("snippets") or []:
            for cat in CAT_IDS:
                hit = _body_hit(cat, sentence)
                if hit:
                    add(cat, "website text", sentence, hit=hit)
        for sub in evidence.get("pages") or []:
            page = sub.get("path") or ""
            if re.search(r"/(?:blog|news|post|posts|20\d\d|tag|category|author|single-post)(/|$)", page, re.I) or re.match(r"^/(?:blog|news|post|posts|20\d\d|tag|category|author|single-post)(/|$)", page, re.I):
                continue
            sub_shorts = [("website title", sub.get("title") or "")]
            sub_shorts += [("website description", m) for m in sub.get("meta") or []]
            sub_shorts += [("website heading", h) for h in sub.get("headings") or []]
            for source, text in sub_shorts:
                for cat in CAT_IDS:
                    hit = _short_hit(cat, text)
                    if hit:
                        add(cat, source, text, page, hit)
            for sentence in sub.get("snippets") or []:
                for cat in CAT_IDS:
                    hit = _body_hit(cat, sentence)
                    if hit:
                        add(cat, "website text", sentence, page, hit)

    if rental_like(studio, enrich, evidence):
        for cat in list(found):
            if cat in {"rental", "natural-light", "prop-rental"}:
                continue
            kept = [i for i in found[cat] if i["source"] in {"listing categories", "business name"}]
            if kept:
                found[cat] = kept
            else:
                del found[cat]
    # A venue, planner, boutique or clinic is not a photographer: keep only explicit photo-service evidence.
    if not photographer_like(studio):
        for cat in list(found):
            if cat in {"natural-light", "prop-rental", "rental"}:
                continue
            kept = [i for i in found[cat]
                    if i["source"] == "listing categories"
                    or (re.search(r"photo|portrait|session|shoot|cinemato|videograph|film", i["text"], re.I)
                        and i["source"] in {"business name", "website title", "website description", "website heading", "website text"})]
            if kept:
                found[cat] = kept
            else:
                del found[cat]
    for cat, items in found.items():
        items.sort(key=lambda i: STRONG_ORDER.index(i["source"]))
        found[cat] = items[:3]
    return found

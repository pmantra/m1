"""
Configs for static insurance questionnaire data. sourced from:
https://docs.google.com/spreadsheets/d/1bWH7545CItE8Xh2LhMc9HHvp2wXuUUUihyx0gKlvu-A/edit#gid=1444629045
"""
from common.constants import Environment
from wallet.models.constants import ReimbursementRequestExpenseTypes

ORGID_TO_HDHP_PLAN_NAME_MAP_UPDATED_1_1 = {
    26: "FORTIVEHDHP2024",  # Fortive Corp
    34: "M4MHDHP2024",  # Maven Clinic Users
    38: "HIREVUEHDHP2024",  # Hirevue
    39: "SEQUOIAHDHP2024",  # Sequoia Capital
    61: "WORKDAYHDHP2024",  # Workday
    62: "SOFIHDHP2024",  # SoFi
    70: "DATADOGHDHP2024",  # Datadog
    75: "MEDALLIAHDHP2024",  # Medallia
    83: "AVALONBAYHDHP2024",  # AvalonBay Communities
    98: "ELBITHDHP2024",  # Elbit Systems of America
    107: "WSGRHDHP2024",  # Wilson Sonsini Goodrich & Rosati
    114: "INSIDERHDHP2024",  # Insider Inc
    126: "LightspeedHDHP2024",  # Lightspeed Venture Partners
    148: "RESPIRAHDHP2024",  # Respira Technologies Inc
    149: "VARDEHDHP2024",  # Varde Partners
    151: "ACCESSOHDHP2024",  # accesso
    164: "DESMARAISHDHP2024",  # Desmarais
    168: "CHIMEHDHP2024",  # Chime
    175: "VALUEACTHDHP2024",  # ValueAct Capital
    184: "GOLDENHIPPHDHP2024",  # Golden Hippo Group LLC
    188: "LOCUSTHDHP2024",  # Locust Street Group
    193: "HEARSTHDHP2024",  # Hearst
    194: "DOCUSIGNHDHP2024",  # Docusign
    217: "CHECKRHDHP2024",  # Checkr Inc
    220: "VICIHDHP2024",  # Vici Properties
    221: "BIOMARINHDHP2024",  # Biomarin Pharmaceutical Inc
    228: "CLARIHDHP2024",  # Clari Inc
    229: "INQTELHDHP2024",  # In-Q-Tel
    230: "FERRARAHDHP2024",  # Ferrara Candy Company
    231: "GENATLHDHP2024",  # General Atlantic
    232: "GenmabHDHP2024",  # Genmab
    235: "POLENHDHP2024",  # Polen Capital Management
    236: "GUNDERSONHDHP2024",  # Gunderson Dettmer
    237: "RAMBUSHDHP2024",  # Rambus
    240: "AAHHDHP2024",  # Advocate Aurora Health
    241: "RIVIERAHDHP2024",  # Riviera Partners
    243: "AAHPTEHDHP2024",  # Advocate Aurora Health (PTE)
    246: "RIDECELLHDHP2024",  # Ridecell
    247: "INNOCENCEHDHP2024",  # Innocence Project
    248: "SAKSCOMHDHP2024",  # Saks com
    250: "FREMONTHDHP2024",  # Fremont Group L L C
    251: "IVPHDHP2024",  # IVP
    252: "REMITLYHDHP2024",  # Remitly Inc
    258: "UDEMYHDHP2024",  # Udemy
    259: "NateraHDHP2024",  # Natera
    260: "PRYSMHDHP2024",  # Prysm Capital
    263: "CONTENTFULHDHP2024",  # Contentful
    266: "GOFUNDMEHDHP2024",  # GoFundMe Inc
    267: "THISLIFEHDHP2024",  # This American Life
    272: "EverlyHDHP2024",  # Everly_Health
    273: "ALECTORHDHP2024",  # Alector   Inc
    276: "KOHLERHDHP2024",  # Kohler
    278: "HOLMUSKHDHP2024",  # Holmusk
    280: "DFAHDHP2024",  # Dimensional Fund Advisors
    285: "GHDUSHDHP2024",  # GHD Inc  - US
    287: "TREELINEHDHP2024",  # Treeline Biosciences
    288: "LCATTERTONHDHP2024",  # L Catterton
    289: "LOVITTHDHP2024",  # Lovitt & Touche
    293: "M4MPROVIDERHDHP24",  # Maven4Maven Providers
    294: "CVCHDHP2024",  # CVC
    303: "LOVEVERYHDHP2024",  # Lovevery
    305: "IMPACTJUSTHDHP2024",  # Impact Justice
    307: "SMITHHDHP2024",  # SMITH&SAINT
    319: "FARALLONHDHP2024",  # Farallon Capital Management
    320: "VYNAMICHDHP2024",  # Vynamic
    328: "SOUNDCLOUDHDHP2024",  # SoundCloud
    332: "APAXHDHP2024",  # Apax Partners LLP - UK
    334: "INSIGHTHDHP2024",  # Insight Partners
    336: "BDTHDHP2024",  # BDT Capital Partners
    342: "UNDEADHDHP2024",  # Undead Labs LLC
    343: "AEAHDHP2024",  # AEA Investors
    346: "CONCENTRICHDHP2024",  # Concentric
    349: "WEBFLOWHDHP2024",  # Webflow
    350: "CWEEHDHP2024",  # CWEE
    353: "ANDURILHDHP2024",  # Anduril Industries
    355: "BRIGADEHDHP2024",  # Brigade Capital Management  LP
    358: "LIGHTSPARKHDHP2024",  # Lightspark Group Inc
    359: "NOMIHEALTHHDHP2024",  # Nomi Health
    361: "INSIDERINTELHDHP24",  # Insider Intelligence
    371: "VARIANTHDHP2024",  # Variant Fund
    376: "645VENTUREHDHP2024",  # 645 Ventures
    380: "WillkieHDHP2024",  # Willkie Farr & Gallagher LLP
    386: "COLORHLTHHDHP2024",  # Color Health
    388: "EDELMANHDHP2024",  # Edelman
    391: "SPRINGWORKHDHP2024",  # SpringWorks Therapeutics
    392: "ANTARESHDHP2024",  # Antares Capital LP
    393: "BLUEVINEHDHP2024",  # Bluevine
    405: "MNTNHDHP2024",  # MNTN  Inc
    414: "CRIBLHDHP2024",  # Cribl
    416: "OLIVEAIHDHP2024",  # Olive AI
    418: "ECSHDHP2024",  # ECS Federal
    419: "ChanZuckHDHP2024",  # Chan Zuckerberg Biohub
    420: "GUMGUMHDHP2024",  # GumGum
    421: "APEXHDHP2024",  # Apex Systems
    422: "ASGNHDHP2024",  # ASGN
    423: "SLALOMMEDHDHP2024",  # Slalom Consulting - Medical Plan
    424: "CREATIVECIRHDHP24",  # Creative Circle
    425: "GenedxHDHP2024",  # GeneDx
    430: "PACKARDHDHP2024",  # Packard Medical Group
    432: "CYBERCODERHDHP2024",  # CyberCoders
    436: "MCDERMOTTHDHP2024",  # McDermott International
    441: "IPGHDHP2024",  # IPG
    444: "LINDENHDHP2024",  # Linden Lab
    448: "OAKHDHP2024",  # Oak HC/FT
    454: "PERSONAHDHP2024",  # Persona
    456: "CORASERVHDHP2024",  # Cora Services
    457: "MACH49HDHP2024",  # Mach 49
    466: "ARTICULATEHDHP2024",  # Articulate
    468: "VISTAEQHDHP2024",  # Vista Equity Partners  LLC
    471: "VITAHDHP2024",  # The Vita Companies
    472: "MERCARIHDHP2024",  # Mercari US
    474: "COINTRACKRHDHP2024",  # CoinTracker
    475: "KINGESTHDHP2024",  # King Estate Winery
    478: "AFSPHDHP2024",  # American Foundation for Suicide Prevention
    480: "ISSAHDHP2024",  # International Sports Sciences Association
    486: "APPLOVINHDHP2024",  # Applovin
    487: "POLYAIHDHP2024",  # PolyAI Limited
    490: "BASSBERRYHDHP2024",  # Bass  Berry & Sims
    493: "STASHFINHDHP2024",  # Stash Financials  Inc
    497: "ACUITYHDHP2024",  # Acuity MD  Inc
    499: "BAKERPOSTTXHDHP24",  # Baker and Hostetler  LLP - Texas Post-Tax
    500: "BAKERPRETXHDHP24",  # Baker and Hostetler  LLP - Texas Pre-Tax
    501: "BAKERPOSTHDHP2024",  # Baker and Hostetler  LLP - Non-Texas Post-Tax
    502: "BAKERPREHDHP2024",  # Baker and Hostetler  LLP - Non-Texas Pre-Tax
    503: "NUNAHEALTHHDHP2024",  # NunaHealth
    504: "CONCENADVHDHP2024",  # Concentric Advisors Parallel Inc
    509: "CPNOAETNAHDHP24",  # Creative Planning - Direct
    515: "HOMECHEFHDHP2024",  # Home Chef
    516: "LOGICUSSINHDHP2024",  # LogicMonitor - US & Singapore
    517: "ASTRANISHDHP2024",  # Astranis
    519: "CPAETNAHDHP24",  # Creative Planning - Aetna
    529: "WILLBLAIRHDHP2024",  # William Blair & Company
    537: "WELLTOWERHDHP2024",  # Welltower
    543: "2UHDHP2024",  # 2U
    553: "MSGUNIONHDHP2024",  # The Madison Square Garden - Union
    561: "ZAILABHDHP2024",  # Zai Lab
    566: "STANDCOGHDHP2024",  # Standard Cognition
    568: "CREDENCEHDHP2024",  # Credence Management
    570: "DIAMONDHILHDHP2024",  # Diamond Hill Investment Group, Inc.
    583: "COBBSALLENHDHP2024",  # Cobbs Allen
    584: "PROSKAUERHDHP2024",  # Proskauer
    597: "FourSeasonHDHP2024",  # Four Seasons Hotels and Resorts
    599: "HELLMANFRIEDHDHP24",  # Hellman & Friedman
    601: "PUBLICISHDHP2024",  # Publicis Groupe
    603: "MAGNETARHDHP2024",  # Magnetar Capital LLC
    608: "CRANKSTARTHDHP2024",  # Crankstart
    610: "WAWAHDHP2024",  # Wawa - Benefits Eligible
    613: "DAWNBCBSHDHP2024",  # Dawn Foods - BCBS
    614: "DAWNDIRECTHDHP2024",  # Dawn Foods - Direct
    619: "ONNITHDHP2024",  # Onnit Labs  Inc
    620: "MorganStanHDHP2024",  # Morgan Stanley US
    627: "LENDLEASEMEDHDHP24",  # Lendlease - Medical Plan Enrolled
    629: "MSDHDHP2024",  # MSD
    630: "LENDLEASEMEDHDHP24",  # Lendlease Non-medically Enrolled
    631: "ALIOHDHP2024",  # Alio
    646: "PipeTechHDHP2024",  # Pipe Technologies
    652: "PutnamHDHP2024",  # Putnam Associates
    653: "ThumbtackUSHDHP24",  # Thumbtack (US)
    657: "MAYNEHDHP2024",  # Mayne Pharma (US)
    682: "ARCOHDHP2024",  # ARCO Construction
    683: "CoatueHDHP2024",  # Coatue Management  L L C
    693: "RothschildHDHP2024",  # Rothschild and Co
    694: "NorthSixHDHP2024",  # North Six
    701: "PatientSqHDHP2024",  # Patient Square Capital
    717: "CARMOTHDHP2024",  # Carmot Therapeutics
    731: "HERMESHDHP2024",  # Hermes of Paris
    744: "SOURCEGRAPHDHP2024",  # Sourcegraph
}

ORGID_TO_HDHP_PLAN_NAME_MAP_UPDATED_5_1 = {
    15: "BumbleHDHP2024",  # Bumble
    108: "BIORATHERHDHP2024",  # Biora Therapeutics
    182: "SYNNEXHDHP2024",  # Synnex
    187: "CENTERBRIDHDHP2024",  # Centerbridge Partners
    209: "CoterieHDHP2024",  # Coterie
    284: "TRADEWEBHDHP2024",  # Tradeweb
    296: "HoneycombHDHP2024",  # Honeycomb
    300: "PIMCOHDHP2024",  # Pimco
    302: "ABRYHDHP2024",  # Abry
    304: "WITHOTTERHDHP2024",  # With Otter, Inc.
    311: "ACLUHDHP2024",  # ACLU of Southern California
    321: "RZEROHDHP2024",  # R-Zero
    344: "HGHDHP2024",  # Hg Capital
    347: "TakeTwoHDHP2024",  # Take-Two US
    382: "ACCELHDHP2024",  # Accel
    426: "KHTFFHDHP2024",  # Kellogg, Hansen, Todd, Figel, & Frederick, PLLC
    574: "StemcellHDHP2024",  # STEMCELL
    580: "CINVENHDHP2024",  # Cinven
    582: "ALTERNATIVESHDHP24",  # Alternatives
    588: "CodaHDHP2024",  # Coda
    600: "RainesHDHP2024",  # Raines International, Inc
    621: "bswiftAetnaHDHP24",  # bswift - Aetna
    622: "bswiftNoAetHDHP24",  # bswift - Non-Aetna
    677: "LeftLaneHDHP2024",  # Left Lane Capital LLC
    687: "TaoUSHDHP2024",  # Tao Group - US
    702: "KippHDHP2024",  # KIPP Foundation
    703: "PolpatHDHP2024",  # Polpat LLC (Ballmer Group)
    711: "SacKingsHDHP2024",  # Sacramento Kings
    748: "XtrHDHP2024",  # Xtr
}

ORGID_TO_HDHP_PLAN_NAME_MAP_UPDATED_8_1 = {
    56: "INDEXVENTHDHP2024",  # Index_Ventures
    185: "EMERGENCEHDHP2024",  # Emergence_Capital_Partners
    215: "REDESIGNHDHP2024",  # Redesign Health
    279: "CDRHDHP2024",  # Clayton Dubilier & Rice
    281: "EngNo1HDHP2024",  # Engine No 1 LLP
    322: "TRIBUTARYHDHP2024",  # Tributary LLP
    337: "CausewayHDHP2024",  # Causeway Capital Management
    338: "1PassHDHP2024",  # AgileBits 1Password
    373: "CapMoneyHDHP2024",  # Capitalize Money
    374: "VANNEVARHDHP2024",  # Vannevar Labs
    396: "TWOSIGMAHDHP2024",  # Two Sigma
    401: "GymsharkHDHP2024",  # Gymshark
    408: "GRTUSHDHP2024",  # GRT US Holdings, Inc.
    443: "ACLUOFSCHDHP2024",  # ACLU
    562: "REFPOINTHDHP2024",  # Reference Point, LLC
    604: "CrestviewHDHP2024",  # Crestview Advisors, LLC
    646: "PipeTechHDHP2024",  # Pipe Technologies
    676: "PSGHDHP2024",  # PSG Equity
    680: "SelendyHDHP2024",  # Selendy Gay PLLC
    692: "ALIFEHDHP2024",  # Alife Health
    694: "NorthSixHDHP2024",  # North Six
    701: "PatientSqHDHP2024",  # Patient Square Capital
    704: "NNAFHDHP2024",  # National Network of Abortion Funds
    752: "VikingHDHP2024",  # Viking Global Investors
    753: "RaineGroupHDHP2024",  # RAINE GROUP LLC
    754: "SilverLakeHDHP2024",  # Silver Lake
    755: "PAISBOAHDHP2024",  # PAISBOA
    809: "HGGCHDHP2024",  # HGGC
    812: "MillerHDHP2024",  # Miller Brothers
}

ORGID_TO_HDHP_PLAN_NAME_MAP = {
    **ORGID_TO_HDHP_PLAN_NAME_MAP_UPDATED_1_1,
    **ORGID_TO_HDHP_PLAN_NAME_MAP_UPDATED_5_1,
    **ORGID_TO_HDHP_PLAN_NAME_MAP_UPDATED_8_1,
}

# these orgs do not provide medical benefits through wallet.
ADOPTION_AND_SURRGOGACY_ONLY_ORG_IDS = {
    25,  # AXIS Capital
    110,  # ServiceTitan
    112,  # Danaher
    160,  # Schindler_Group
    169,  # Huntington_Ingalls_Industries
    170,  # Dentsu
    193,  # Hearst
    239,  # Scotts Miracle-Gro
    240,  # Advocate Aurora Health
    243,  # Advocate Aurora Health PTE
    309,  # Columbia University - Medical Plan Only
    314,  # Columbia University - Non-Medical Plan Only
    352,  # Elevance Health Medical Plan Full-Time
    354,  # Veeam Software
    364,  # Elevance Health Non-Medical Full-Time
    365,  # Elevance Health Medical Plan Part-Time
    366,  # Elevance Health Non-Medical Part-Time
    372,  # Brown Brothers Harriman
    397,  # L'Oreal Non-Medical
    410,  # Celanese
    413,  # Hubbell
    428,  # Yahoo US
    440,  # LVMH
    447,  # AlixPartners - Aetna
    451,  # Franklin County
    458,  # Incyte - Aetna
    459,  # Incyte - Medical Opt-Out
    492,  # Symetra
    505,  # VS&Co - Aetna
    507,  # VS&Co - Anthem
    510,  # Hellmann - non-Aetna
    511,  # Hellmann - Aetna
    520,  # CVS - Aetna Medical
    522,  # CVS - Non-Aetna
    538,  # WW - Aetna Medical
    539,  # WW - Non-Medical
    548,  # Cantor Fitzgerald - Aetna
    637,  # VS&Co - Non-Medical
    643,  # Davita (Fulltime benefits Eligible)
    645,  # Holder Construction
    650,  # Estee Lauder Companies
    665,  # Axis Capital International
    776,  # The Hain Celestial Group-Medical Opt Outs
    778,  # The Hain Celestial Group-UHC Enrolled US Employee
}

# Orgs that were onboarded to MMB in 2024 do not need to take the survey
ONBOARDED_TO_MMB_IN_2024_ORG_IDS = {
    68,  # The Hartford
    71,  # Cozen
    620,  # Morgan Stanley
    863,  # Galway
    904,  # Diligent
    2018,  # OhioHealth Corporation
    2054,  # PwC
}

# Used to override and block survey from showing
# Useful for orgs that have plans that start in the future
DO_NOT_SHOW_SURVEY_ORG_IDS = {}

MEDICAL_EXPENSE_TYPES = {
    ReimbursementRequestExpenseTypes.FERTILITY,
    ReimbursementRequestExpenseTypes.PRESERVATION,
    ReimbursementRequestExpenseTypes.MATERNITY,
    ReimbursementRequestExpenseTypes.MENOPAUSE,
}


# Launch the survey 60 days in advance in QA to help with testing.
MAX_SURVEY_DAYS_IN_ADVANCE = (
    30 if Environment.current() == Environment.PRODUCTION else 60
)


ANNUAL_INSURANCE_FORM_DP_WALLET_SCREENER_BRANCHING = (
    "annual_insurance_form_dp_wallet_screener_branching"
)


CONTENTFUL_WIDGET_MAPPING = {
    "text": "text_box",
    "dropdown": "dropdown",
    "date-calendar": "datepicker",
    "radio-buttons": "radio_button",
}
CONTENTFUL_WIDGETS_WITH_OPTIONS = {"dropdown", "radio-buttons"}

PAYER_PLAN_TITLE = "Payer & Plan name"

# orgs that need special handling - with thier non prod analogs
ORG_ID_AMAZON = 2441 if Environment.current() == Environment.PRODUCTION else 133
ORG_ID_OHIO = 2018 if Environment.current() == Environment.PRODUCTION else 867

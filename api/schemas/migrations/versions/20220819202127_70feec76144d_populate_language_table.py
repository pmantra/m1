"""populate language table

Revision ID: 70feec76144d
Revises: 567b535a29c9
Create Date: 2022-08-19 20:21:27.427584+00:00

"""
import csv
from models.base import db

from models.profiles import Language


# revision identifiers, used by Alembic.
revision = "70feec76144d"
down_revision = "5ed17d0000e5"
branch_labels = None
depends_on = None

"""
    id = Column(Integer, primary_key=True)
    name = Column(String(70), nullable=False, unique=True)
    abbreviation = Column(String(10), nullable=True, unique=True)
    iso_639_3 = Column("iso-639-3", String(10), nullable=True, unique=True)
    inverted_name = Column(String(255), nullable=True)
"""


def upgrade():
    lines = language_csv.splitlines()
    reader = csv.reader(lines)

    for language_data in reader:
        # get and update if exists
        lang = Language.query.filter(Language.name == language_data[2]).first()
        if not lang:
            lang = Language(name=language_data[2])  # create if does not exist

        lang.iso_639_3 = language_data[0]
        lang.inverted_name = language_data[1]

        db.session.add(lang)

    db.session.commit()


def downgrade():
    db.session.query(Language).delete()
    db.session.commit()


# ISO_639,Language_Name,Uninverted_Name,L1_Users,All_Users
language_csv = """eng,English,English,372861280,1452470600
cmn,"Chinese, Mandarin",Mandarin Chinese,919855240,1118583240
hin,Hindi,Hindi,343930570,602197470
spa,Spanish,Spanish,474706420,548333560
fra,French,French,79867770,274067040
arb,"Arabic, Standard",Standard Arabic,0,273989700
ben,Bengali,Bengali,233672060,272674940
rus,Russian,Russian,154042490,258177060
por,Portuguese,Portuguese,232433540,257659540
urd,Urdu,Urdu,70249640,231295440
ind,Indonesian,Indonesian,43627350,198996350
deu,"German, Standard",Standard German,75572140,134624440
jpn,Japanese,Japanese,125277770,125398770
pcm,"Pidgin, Nigerian",Nigerian Pidgin,4650000,120650000
mar,Marathi,Marathi,83146310,99146310
tel,Telugu,Telugu,82730900,95730900
tur,Turkish,Turkish,82227130,88097430
tam,Tamil,Tamil,78430340,86430340
yue,"Chinese, Yue",Yue Chinese,85174320,85576320
vie,Vietnamese,Vietnamese,84596090,85341090
tgl,Tagalog,Tagalog,28150160,82312160
wuu,"Chinese, Wu",Wu Chinese,81754390,81817790
kor,Korean,Korean,81721660,81721660
pes,"Persian, Iranian",Iranian Persian,56377510,77377510
hau,Hausa,Hausa,50770700,77063700
arz,"Arabic, Egyptian Spoken",Egyptian Spoken Arabic,74826320,74826320
swh,Swahili,Swahili,16056500,71416500
jav,Javanese,Javanese,68278400,68278400
ita,Italian,Italian,64820960,67901060
pnb,"Punjabi, Western",Western Punjabi,66441240,66441240
guj,Gujarati,Gujarati,56952870,61952870
tha,Thai,Thai,20685590,60685590
kan,Kannada,Kannada,43644310,58644310
amh,Amharic,Amharic,32366560,57466560
bho,Bhojpuri,Bhojpuri,52303000,52463000
pan,"Punjabi, Eastern",Eastern Punjabi,48123470,51723470
nan,"Chinese, Min Nan",Min Nan Chinese,49287990,49674990
cjy,"Chinese, Jinyu",Jinyu Chinese,47100000,47100000
yor,Yoruba,Yoruba,43612560,45612560
hak,"Chinese, Hakka",Hakka Chinese,43817190,44065190
mya,Burmese,Burmese,32953240,42953240
apd,"Arabic, Sudanese Spoken",Sudanese Spoken Arabic,33332360,42332360
pol,Polish,Polish,39962150,40627150
arq,"Arabic, Algerian Spoken",Algerian Spoken Arabic,34659600,40259600
lin,Lingala,Lingala,20252520,40252520
ory,Odia,Odia,34459890,39759890
hsn,"Chinese, Xiang",Xiang Chinese,37400000,37400000
mal,Malayalam,Malayalam,36512270,37212270
mai,Maithili,Maithili,33890000,34085000
ary,"Arabic, Moroccan Spoken",Moroccan Spoken Arabic,28238230,33358230
ukr,Ukrainian,Ukrainian,27429350,33229350
snd,Sindhi,Sindhi,33215040,33215040
sun,Sunda,Sunda,32400000,32400000
apc,"Arabic, North Levantine Spoken",North Levantine Spoken Arabic,29777280,31436280
ibo,Igbo,Igbo,30775190,30775190
pbu,"Pashto, Northern",Northern Pashto,28812800,30172800
prs,Dari,Dari,9452210,29452210
zul,Zulu,Zulu,12104600,27804600
uzn,"Uzbek, Northern",Northern Uzbek,27743550,27743550
skr,Saraiki,Saraiki,26219000,26219000
npi,Nepali,Nepali,16697000,25377000
nld,Dutch,Dutch,22838930,24443930
aec,"Arabic, Sa’idi Spoken",Sa’idi Spoken Arabic,24100000,24100000
ron,Romanian,Romanian,24053460,24053460
gan,"Chinese, Gan",Gan Chinese,22200000,22200000
som,Somali,Somali,21834630,21930230
mag,Magahi,Magahi,20735600,20746400
pbt,"Pashto, Southern",Southern Pashto,16252400,19732400
xho,Xhosa,Xhosa,8216300,19216300
gaz,"Oromo, West Central",West Central Oromo,19196000,19196000
zlm,Malay,Malay,16185270,19185270
acm,"Arabic, Mesopotamian Spoken",Mesopotamian Spoken Arabic,19063530,19063530
ars,"Arabic, Najdi Spoken",Najdi Spoken Arabic,18153010,18153010
khm,Khmer,Khmer,16951230,17951230
afr,Afrikaans,Afrikaans,7331780,17631780
sin,Sinhala,Sinhala,15504670,17504670
fuv,"Fulfulde, Nigerian",Nigerian Fulfulde,16585000,16585000
hne,Chhattisgarhi,Chhattisgarhi,16300000,16300000
ceb,Cebuano,Cebuano,15942480,15942480
kmr,"Kurdish, Northern",Northern Kurdish,15703920,15703920
asm,Assamese,Assamese,15326200,15326200
tts,"Thai, Northeastern",Northeastern Thai,15000000,15000000
azb,"Azerbaijani, South",South Azerbaijani,14629370,14629370
bar,Bavarian,Bavarian,14539000,14539000
nya,Chichewa,Chichewa,14380700,14380700
bam,Bamanankan,Bamanankan,4181800,14181800
tsn,Setswana,Setswana,5895730,13745730
nso,"Sotho, Northern",Northern Sotho,4631000,13731000
sot,"Sotho, Southern",Southern Sotho,5624700,13524700
ces,Czech,Czech,10732560,13414560
ell,Greek,Greek,13228770,13287270
kin,Kinyarwanda,Kinyarwanda,13133980,13133980
swe,Swedish,Swedish,9923910,13073910
ctg,Chittagonian,Chittagonian,13000000,13000000
dcc,Deccan,Deccan,12800000,12800000
ajp,"Arabic, South Levantine Spoken",South Levantine Spoken Arabic,12711300,12711300
kaz,Kazakh,Kazakh,12692300,12692300
ayn,"Arabic, Sanaani Spoken",Sanaani Spoken Arabic,12567960,12567960
hun,Hungarian,Hungarian,12560490,12560490
dyu,Jula,Jula,2226000,12504000
wol,Wolof,Wolof,5926290,12266290
sck,Sadri,Sadri,5131180,12131225
wes,"Pidgin, Cameroon",Cameroon Pidgin,,12000000
acq,"Arabic, Ta’izzi-Adeni Spoken",Ta’izzi-Adeni Spoken Arabic,11821100,11821100
aeb,"Arabic, Tunisian Spoken",Tunisian Spoken Arabic,11709020,11709020
mnp,"Chinese, Min Bei",Min Bei Chinese,11520000,11520000
syl,Sylheti,Sylheti,10020000,11520000
run,Rundi,Rundi,11253950,11253950
kng,Koongo,Koongo,6236500,11236500
swc,"Swahili, Congo",Congo Swahili,2043000,11143000
lug,Ganda,Ganda,5613450,11003450
sna,Shona,Shona,7365590,10865590
cdo,"Chinese, Min Dong",Min Dong Chinese,10817580,10817580
rkt,Rangpuri,Rangpuri,10476000,10801000
acw,"Arabic, Hijazi Spoken",Hijazi Spoken Arabic,10792400,10792400
ibb,Ibibio,Ibibio,6259000,10759000
afb,"Arabic, Gulf Spoken",Gulf Spoken Arabic,10656700,10656700
uig,Uyghur,Uyghur,10410782,10410782
srp,Serbian,Serbian,10300476,10300476
ayp,"Arabic, North Mesopotamian Spoken",North Mesopotamian Spoken Arabic,10252460,10252460
tir,Tigrigna,Tigrigna,9852220,10004220
tso,Tsonga,Tsonga,6603500,10003500
bgc,Haryanvi,Haryanvi,9810000,9810000
hae,"Oromo, Eastern",Eastern Oromo,9710000,9710000
heb,Hebrew,Hebrew,6087050,9387050
aka,Akan,Akan,8329800,9329800
cat,Catalan,Catalan,4141310,9241310
azj,"Azerbaijani, North",North Azerbaijani,9219960,9219960
knc,"Kanuri, Yerwa",Yerwa Kanuri,8325500,8825500
pst,"Pashto, Central",Central Pashto,8490000,8490000
gax,"Oromo, Borana-Arsi-Guji",Borana-Arsi-Guji Oromo,8448600,8448600
bul,Bulgarian,Bulgarian,8280370,8280370
kri,Krio,Krio,817900,8237900
tgk,Tajik,Tajik,8195120,8195120
hat,Haitian Creole,Haitian Creole,8175940,8175940
kik,Gikuyu,Gikuyu,8150000,8150000
suk,Sukuma,Sukuma,8130000,8130000
mos,Mòoré,Mòoré,7984800,7984800
rwr,Marwari,Marwari,7855400,7856410
mad,Madura,Madura,7790900,7790900
sat,Santhali,Santhali,7620200,7621180
plt,"Malagasy, Merina",Merina Malagasy,7546100,7546100
slk,Slovak,Slovak,5206080,7251080
kas,Kashmiri,Kashmiri,7131000,7131000
lua,Luba-Kasai,Luba-Kasai,6360000,7060000
umb,Umbundu,Umbundu,6980000,6980000
vah,Varhadi-Nagpuri,Varhadi-Nagpuri,6970000,6970000
kab,Amazigh,Amazigh,6819200,6819200
ins,Indian Sign Language,Indian Sign Language,6815000,6815000
hrv,Croatian,Croatian,5505010,6765010
tuk,Turkmen,Turkmen,6655340,6655340
gug,"Guaraní, Paraguayan",Paraguayan Guaraní,6540000,6540000
ilo,Ilocano,Ilocano,6482100,6482100
gsw,"German, Swiss",Swiss German,6434400,6434400
hil,Hiligaynon,Hiligaynon,6246880,6246880
nod,"Thai, Northern",Northern Thai,6029500,6029500
bjj,Kanauji,Kanauji,6000000,6000000
nap,Napoletano-Calabrese,Napoletano-Calabrese,5700000,5700000
fub,"Fulfulde, Adamawa",Adamawa Fulfulde,3005500,5685500
fin,Finnish,Finnish,5023640,5679640
bns,Bundeli,Bundeli,5630000,5630000
dan,Danish,Danish,5613190,5613190
ewe,Éwé,Éwé,5023560,5523560
mup,Malvi,Malvi,5440000,5440000
fuc,Pulaar,Pulaar,5398700,5398700
czh,"Chinese, Huizhou",Huizhou Chinese,5380000,5380000
ayl,"Arabic, Libyan Spoken",Libyan Spoken Arabic,5343050,5343050
tat,Tatar,Tatar,5314450,5314450
nor,Norwegian,Norwegian,5307770,5307770
uzs,"Uzbek, Southern",Southern Uzbek,4756100,5296100
ckb,"Kurdish, Central",Central Kurdish,5266050,5266050
kam,Kamba,Kamba,4660000,5260000
luo,Dholuo,Dholuo,5255000,5255000
sag,Sango,Sango,617000,5217000
kir,Kyrgyz,Kyrgyz,5132100,5132100
shi,Tachelhit,Tachelhit,5118000,5118000
ayh,"Arabic, Hadrami Spoken",Hadrami Spoken Arabic,5113000,5113000
lir,Liberian English,Liberian English,113000,5113000
lmn,Lambadi,Lambadi,5080000,5080000
san,Sanskrit,Sanskrit,24800,5027800
gpe,Ghanaian Pidgin English,Ghanaian Pidgin English,2000,5002000
bew,Betawi,Betawi,5000000,5000000
ktu,Kituba,Kituba,4200000,5000000
mey,Hassaniyya,Hassaniyya,4883500,4883500
min,Minangkabau,Minangkabau,4880000,4880000
fuf,Pular,Pular,4778200,4778200
tzm,"Tamazight, Central Atlas",Central Atlas Tamazight,4740000,4740000
ssw,Swati,Swati,2314500,4714500
scn,Sicilian,Sicilian,4700000,4700000
shn,Shan,Shan,4685000,4685000
bci,Baoulé,Baoulé,4654060,4654060
tiv,Tiv,Tiv,4560000,4560000
sou,"Thai, Southern",Southern Thai,4508200,4508200
lao,Lao,Lao,3705160,4505160
sid,Sidamo,Sidamo,4340000,4441000
rif,Tarifit,Tarifit,4399000,4399000
bug,Bugis,Bugis,3898800,4398800
awa,Awadhi,Awadhi,4352000,4397400
dje,Zarma,Zarma,4330100,4330100
mtr,Mewari,Mewari,4210000,4210000
"""

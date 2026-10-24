from functools import lru_cache
from typing import Dict, Optional, Tuple

from services.localization import resolve_language


_RESPONSES: Dict[str, Dict[str, str]] = {
    "soil": {
        "en": "For general soil health, start with a soil test through a local agricultural laboratory or extension service. Use the results to guide nutrient decisions; retain suitable crop residues, add well-matured organic matter where appropriate, rotate crops (including legumes when suitable), and reduce erosion. Exact amendments depend on your soil test and crop.",
        "mr": "मातीच्या आरोग्यासाठी स्थानिक कृषी प्रयोगशाळा किंवा कृषी सेवा केंद्रातून मातीची तपासणी करून घ्या. तपासणीच्या निष्कर्षांनुसार पोषकद्रव्यांचे नियोजन करा; योग्य पीक-अवशेष शेतात ठेवा, आवश्यकतेनुसार पूर्ण कुजलेले सेंद्रिय पदार्थ वापरा, पिकांची फेरपालट करा आणि मृदा धूप कमी करा. नेमक्या सुधारणा माती तपासणी व पिकावर अवलंबून असतात.",
        "hi": "मिट्टी के स्वास्थ्य के लिए स्थानीय कृषि प्रयोगशाला या कृषि सेवा केंद्र से मिट्टी की जाँच कराएँ। जाँच के नतीजों के अनुसार पोषक तत्वों का निर्णय लें; उपयुक्त फसल-अवशेष खेत में रखें, जरूरत के अनुसार अच्छी तरह सड़ी जैविक सामग्री डालें, फसल चक्र अपनाएँ और मिट्टी का कटाव घटाएँ। सही सुधार मिट्टी की जाँच और फसल पर निर्भर करते हैं।",
        "ml": "മണ്ണിന്റെ പൊതുവായ ആരോഗ്യം മെച്ചപ്പെടുത്താൻ ആദ്യം പ്രാദേശിക കാർഷിക ലബോറട്ടറിയിലോ കൃഷി സേവന കേന്ദ്രത്തിലോ മണ്ണ് പരിശോധന നടത്തുക. ഫലങ്ങൾ അനുസരിച്ച് പോഷകങ്ങളുടെ ഉപയോഗം തീരുമാനിക്കുക; അനുയോജ്യമായ വിളാവശിഷ്ടങ്ങൾ നിലനിർത്തുക, ആവശ്യമായിടത്ത് നന്നായി പഴുത്ത ജൈവവളം ചേർക്കുക, വിളപരിവർത്തനം നടത്തുക, മണ്ണൊലിപ്പ് കുറയ്ക്കുക. ആവശ്യമായ മണ്ണ് ഭേദഗതികൾ പരിശോധനാഫലത്തെയും വിളയെയും ആശ്രയിച്ചിരിക്കുന്നു.",
    },
    "irrigation": {
        "en": "For general irrigation decisions, check root-zone soil moisture and recent rainfall rather than following a fixed schedule. Avoid prolonged waterlogging, and pay closer attention to crop water needs during flowering and fruit or grain development. Exact timing depends on the crop, soil, growth stage, and local weather; current weather is not verified here.",
        "mr": "सिंचनाचा निर्णय ठरावीक वेळापत्रकावर न घेता मुळांच्या भागातील ओलावा आणि अलीकडील पाऊस तपासून घ्या. पाणी साचून राहणे टाळा आणि फुलोरा तसेच फळ किंवा दाणे भरण्याच्या काळात पिकाच्या पाण्याच्या गरजेकडे विशेष लक्ष द्या. योग्य वेळ पीक, माती, वाढीचा टप्पा आणि स्थानिक हवामानावर अवलंबून असते; सध्याचे हवामान येथे पडताळलेले नाही.",
        "hi": "सिंचाई का निर्णय तय समय-सारणी के बजाय जड़ों के पास मिट्टी की नमी और हाल की वर्षा देखकर लें। लंबे समय तक पानी जमा न रहने दें और फूल आने तथा फल या दाना बनने के समय फसल की पानी की जरूरत पर विशेष ध्यान दें। सही समय फसल, मिट्टी, बढ़वार के चरण और स्थानीय मौसम पर निर्भर करता है; यहाँ मौजूदा मौसम की पुष्टि नहीं की गई है।",
        "ml": "ജലസേചനം തീരുമാനിക്കുമ്പോൾ നിശ്ചിത സമയക്രമം മാത്രം പിന്തുടരാതെ വേരുകൾക്കടുത്തുള്ള മണ്ണിലെ ഈർപ്പവും സമീപകാല മഴയും പരിശോധിക്കുക. വെള്ളം ദീർഘനേരം കെട്ടിനിൽക്കുന്നത് ഒഴിവാക്കുക; പൂവിടുമ്പോഴും പഴം അല്ലെങ്കിൽ ധാന്യം വളരുമ്പോഴും വിളയുടെ ജലാവശ്യത്തിൽ കൂടുതൽ ശ്രദ്ധിക്കുക. ശരിയായ സമയം വിള, മണ്ണ്, വളർച്ചാഘട്ടം, പ്രാദേശിക കാലാവസ്ഥ എന്നിവയെ ആശ്രയിക്കുന്നു; നിലവിലെ കാലാവസ്ഥ ഇവിടെ പരിശോധിച്ചിട്ടില്ല.",
    },
    "fertilizer": {
        "en": "For fertilizer decisions, first use a soil test and follow crop- and region-specific recommendations from your local agricultural extension service. Apply nutrients only as indicated for the crop and growth stage; avoid guessing a dose or mixing products. This general guidance does not replace a soil test.",
        "mr": "खताचा निर्णय घेण्यापूर्वी माती तपासणी करा आणि स्थानिक कृषी सेवा केंद्राच्या पीक व प्रदेशानुसार दिलेल्या शिफारशी पाळा. पीक आणि वाढीच्या टप्प्यासाठी सुचवलेलीच पोषकद्रव्ये वापरा; मात्रा अंदाजाने ठरवू नका किंवा उत्पादने मिसळू नका. हे सर्वसाधारण मार्गदर्शन माती तपासणीचा पर्याय नाही.",
        "hi": "उर्वरक का निर्णय लेने से पहले मिट्टी की जाँच कराएँ और स्थानीय कृषि सेवा की फसल तथा क्षेत्र के अनुसार दी गई सलाह मानें। फसल और बढ़वार के चरण के लिए सुझाए गए पोषक तत्व ही दें; मात्रा का अनुमान न लगाएँ और उत्पादों को न मिलाएँ। यह सामान्य जानकारी मिट्टी की जाँच का विकल्प नहीं है।",
        "ml": "വളപ്രയോഗം തീരുമാനിക്കുന്നതിന് മുമ്പ് മണ്ണ് പരിശോധന നടത്തുകയും പ്രാദേശിക കൃഷി സേവനകേന്ദ്രത്തിന്റെ വിളയ്ക്കും പ്രദേശത്തിനും അനുയോജ്യമായ നിർദേശങ്ങൾ പാലിക്കുകയും ചെയ്യുക. വിളയ്ക്കും വളർച്ചാഘട്ടത്തിനും ശുപാർശ ചെയ്ത പോഷകങ്ങൾ മാത്രം നൽകുക; അളവ് ഊഹിക്കുകയോ ഉൽപ്പന്നങ്ങൾ കലർത്തുകയോ ചെയ്യരുത്. ഈ പൊതുവായ നിർദേശം മണ്ണ് പരിശോധനയ്ക്ക് പകരമല്ല.",
    },
    "pest": {
        "en": "For general pest and disease management, inspect plants regularly and record where and when symptoms appear. Confirm the cause before treating: several problems look alike. Use field sanitation and other locally recommended integrated pest-management practices. This chat cannot diagnose a specific crop problem from text alone; ask a local agricultural expert before treatment, especially before using a pesticide.",
        "mr": "कीड व रोग व्यवस्थापनासाठी पिकांची नियमित पाहणी करा आणि लक्षणे कुठे व केव्हा दिसतात याची नोंद ठेवा. उपचारापूर्वी कारणाची खात्री करा—अनेक समस्या सारख्या दिसू शकतात. शेताची स्वच्छता आणि स्थानिकरीत्या शिफारस केलेल्या एकात्मिक कीड व्यवस्थापन पद्धती वापरा. केवळ मजकुरावरून येथे विशिष्ट रोगनिदान करता येत नाही; उपचारापूर्वी, विशेषतः कीटकनाशक वापरण्यापूर्वी, स्थानिक कृषी तज्ज्ञांचा सल्ला घ्या.",
        "hi": "कीट और रोग प्रबंधन के लिए पौधों की नियमित जाँच करें और लक्षण कहाँ तथा कब दिखते हैं, इसका रिकॉर्ड रखें। उपचार से पहले कारण की पुष्टि करें—कई समस्याएँ एक जैसी दिख सकती हैं। खेत की सफाई और स्थानीय रूप से सुझाए गए एकीकृत कीट प्रबंधन उपाय अपनाएँ। केवल लिखे हुए संदेश से यहाँ किसी खास फसल की बीमारी का निदान नहीं किया जा सकता; उपचार से पहले, खासकर कीटनाशक इस्तेमाल करने से पहले, स्थानीय कृषि विशेषज्ञ से सलाह लें।",
        "ml": "കീട-രോഗ നിയന്ത്രണത്തിനായി ചെടികൾ പതിവായി പരിശോധിക്കുകയും ലക്ഷണങ്ങൾ എവിടെയും എപ്പോഴുമാണ് കാണുന്നതെന്ന് രേഖപ്പെടുത്തുകയും ചെയ്യുക. ചികിത്സയ്ക്ക് മുമ്പ് കാരണം ഉറപ്പാക്കുക; പല പ്രശ്നങ്ങളും ഒരുപോലെ തോന്നാം. വയൽ ശുചിത്വവും പ്രാദേശികമായി ശുപാർശ ചെയ്യുന്ന സംയോജിത കീടനിയന്ത്രണ രീതികളും പിന്തുടരുക. എഴുത്ത് മാത്രം ഉപയോഗിച്ച് ഇവിടെ പ്രത്യേക വിളപ്രശ്നം നിർണയിക്കാനാവില്ല; ചികിത്സയ്ക്ക് മുമ്പ്, പ്രത്യേകിച്ച് കീടനാശിനി ഉപയോഗിക്കുന്നതിന് മുമ്പ്, പ്രാദേശിക കാർഷിക വിദഗ്ധനോട് ചോദിക്കുക.",
    },
}

_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "soil": (
        "soil health", "soil quality", "soil", "मिट्टी", "मृदा", "माती", "जमीन",
        "മണ്ണ്", "മണ്ണിന്റെ",
    ),
    "irrigation": (
        "irrigation", "water my crop", "watering", "पानी", "सिंचाई", "सिंचन",
        "पाणी", "पाणी द्यावे", "ജലസേചനം", "നനയ്ക്കുക",
    ),
    "fertilizer": (
        "fertilizer", "fertiliser", "nutrient", "manure", "खाद", "उर्वरक",
        "खत", "खते", "सेंद्रिय खत", "വളം", "പോഷകം",
    ),
    "pest": (
        "pest", "insect", "disease", "कीट", "कीड़े", "रोग", "कीड", "किड",
        "किडी", "रोग", "കീടം", "രോഗം",
    ),
}

_SOURCE_LABELS = {
    "en": "Local general guidance (not generated by Gemini):",
    "mr": "स्थानिक सर्वसाधारण मार्गदर्शन (Gemini ने तयार केलेले नाही):",
    "hi": "स्थानीय सामान्य जानकारी (Gemini द्वारा तैयार नहीं):",
    "ml": "പ്രാദേശിക പൊതുവായ മാർഗ്ഗനിർദേശം (Gemini സൃഷ്ടിച്ച മറുപടിയല്ല):",
}

@lru_cache(maxsize=32)
def _cached_local_answer(topic: str, language: str) -> str:
    return f"{_SOURCE_LABELS[language]}\n\n{_RESPONSES[topic][language]}"


def local_agricultural_answer(message: str, language: str) -> Optional[str]:
    """Return a cautious, fixed local FAQ answer only for supported topics."""
    language = resolve_language(language)
    if language not in _SOURCE_LABELS:
        return None

    normalized = message.casefold()
    for topic, keywords in _KEYWORDS.items():
        if any(keyword.casefold() in normalized for keyword in keywords):
            return _cached_local_answer(topic, language)
    return None


def unavailable_answer(language: str) -> str:
    return _UNAVAILABLE[language]

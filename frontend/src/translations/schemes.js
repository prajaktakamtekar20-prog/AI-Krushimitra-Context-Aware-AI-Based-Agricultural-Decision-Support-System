const schemeNames = {
  'pm-kisan': {
    en: 'Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)',
    mr: 'प्रधानमंत्री किसान सन्मान निधी (PM-KISAN)',
    hi: 'प्रधानमंत्री किसान सम्मान निधि (PM-KISAN)',
    ml: 'പ്രധാനമന്ത്രി കിസാൻ സമ്മാൻ നിധി (PM-KISAN)'
  },
  pmfby: {
    en: 'Pradhan Mantri Fasal Bima Yojana (PMFBY)',
    mr: 'प्रधानमंत्री पीक विमा योजना (PMFBY)',
    hi: 'प्रधानमंत्री फसल बीमा योजना (PMFBY)',
    ml: 'പ്രധാനമന്ത്രി ഫസൽ ബീമാ യോജന (PMFBY)'
  },
  'kisan-credit-card': {
    en: 'Kisan Credit Card (KCC)',
    mr: 'किसान क्रेडिट कार्ड (KCC)',
    hi: 'किसान क्रेडिट कार्ड (KCC)',
    ml: 'കിസാൻ ക്രെഡിറ്റ് കാർഡ് (KCC)'
  },
  'soil-health-card': {
    en: 'Soil Health Card Scheme',
    mr: 'मृदा आरोग्य पत्रिका योजना',
    hi: 'मृदा स्वास्थ्य कार्ड योजना',
    ml: 'മണ്ണിന്റെ ആരോഗ്യ കാർഡ് പദ്ധതി'
  },
  'mahadbt-schemes': {
    en: 'MahaDBT — Agriculture and Related Services',
    mr: 'महाडीबीटी — कृषी व संबंधित सेवा',
    hi: 'महाडीबीटी — कृषि और संबंधित सेवाएँ',
    ml: 'മഹാഡിബിടി — കൃഷിയും അനുബന്ധ സേവനങ്ങളും'
  },
  'mahadbt-agriculture': {
    en: 'MahaDBT — Agriculture and Related Services',
    mr: 'महाडीबीटी — कृषी व संबंधित सेवा',
    hi: 'महाडीबीटी — कृषि और संबंधित सेवाएँ',
    ml: 'മഹാഡിബിടി — കൃഷിയും അനുബന്ധ സേവനങ്ങളും'
  },
  'maha-krushi-sanvad': {
    en: 'Farm Mechanization Subsidy (Maharashtra)',
    mr: 'शेतकी यांत्रिकीकरण अनुदान (महाराष्ट्र)',
    hi: 'कृषि मशीनीकरण सब्सिडी (महाराष्ट्र)',
    ml: 'കാർഷിക യന്ത്രവൽക്കരണ സബ്സിഡി (മഹാരാഷ്ട്ര)'
  },
  'maha-farm-mechanisation': {
    en: 'Farm Mechanization Subsidy (Maharashtra)',
    mr: 'शेतकी यांत्रिकीकरण अनुदान (महाराष्ट्र)',
    hi: 'कृषि मशीनीकरण सब्सिडी (महाराष्ट्र)',
    ml: 'കാർഷിക യന്ത്രവൽക്കരണ സബ്സിഡി (മഹാരാഷ്ട്ര)'
  },
  'magel-tyala-shettale': {
    en: 'Magel Tyala Shettale',
    mr: 'मागेल त्याला शेततळे',
    hi: 'मागेल त्याला शेततळे',
    ml: 'മാഗേൽ ത്യാല ഷേത്തളേ'
  },
  'maha-farm-pond': {
    en: 'Magel Tyala Shettale (Farm Pond) and Water Conservation Works',
    mr: 'मागेल त्याला शेततळे व जलसंधारण कामे',
    hi: 'मागेल त्याला शेततळे और जल संरक्षण कार्य',
    ml: 'മാഗേൽ ത്യാല ഷേത്തളേ (കൃഷിക്കുളം)യും ജലസംരക്ഷണ പ്രവർത്തനങ്ങളും'
  },
  'pm-kusum': {
    en: 'PM-KUSUM',
    mr: 'पीएम-कुसुम',
    hi: 'पीएम-कुसुम',
    ml: 'പി.എം.-കുസും'
  },
  pmksy: {
    en: 'Pradhan Mantri Krishi Sinchayee Yojana (PMKSY)',
    mr: 'प्रधानमंत्री कृषी सिंचन योजना (PMKSY)',
    hi: 'प्रधानमंत्री कृषि सिंचाई योजना (PMKSY)',
    ml: 'പ്രധാനമന്ത്രി കൃഷി സിഞ്ചായി യോജന (PMKSY)'
  },
  'solar-pump-sauri': {
    en: 'PM-KUSUM',
    mr: 'पीएम-कुसुम',
    hi: 'पीएम-कुसुम',
    ml: 'പി.എം.-കുസും'
  },
  'organic-farming-mission': {
    en: 'Organic Farming Mission',
    mr: 'सेंद्रिय शेती अभियान',
    hi: 'जैविक खेती मिशन',
    ml: 'ജൈവകൃഷി ദൗത്യം'
  },
  'myscheme-india': {
    en: 'myScheme — Government Scheme Directory',
    mr: 'myScheme — सरकारी योजना निर्देशिका',
    hi: 'myScheme — सरकारी योजना निर्देशिका',
    ml: 'myScheme — സർക്കാർ പദ്ധതി ഡയറക്ടറി'
  },
  'myscheme-directory': {
    en: 'myScheme — Government Scheme Directory',
    mr: 'myScheme — शासकीय योजना निर्देशिका',
    hi: 'myScheme — सरकारी योजना निर्देशिका',
    ml: 'myScheme — സർക്കാർ പദ്ധതി ഡയറക്ടറി'
  }
}

const levelLabels = {
  central: { en: 'Central Government', mr: 'केंद्र सरकार', hi: 'केंद्र सरकार', ml: 'കേന്ദ്ര സർക്കാർ' },
  state: { en: 'State Government', mr: 'राज्य सरकार', hi: 'राज्य सरकार', ml: 'സംസ്ഥാന സർക്കാർ' }
}

const documentStatusLabels = {
  typically_mandatory: { en: 'Usually Required', mr: 'सहसा आवश्यक', hi: 'आमतौर पर आवश्यक', ml: 'സാധാരണയായി ആവശ്യമാണ്' },
  conditional: { en: 'Conditional', mr: 'सशर्त', hi: 'शर्तों के अनुसार', ml: 'നിബന്ധനാപരമായി' },
  optional: { en: 'Optional', mr: 'ऐच्छिक', hi: 'वैकल्पिक', ml: 'ഐച്ഛികം' },
  not_applicable: { en: 'N/A', mr: 'लागू नाही', hi: 'लागू नहीं', ml: 'ബാധകമല്ല' }
}

const departmentLabels = {
  'Ministry of Agriculture & Farmers Welfare': {
    en: 'Ministry of Agriculture & Farmers Welfare',
    mr: 'कृषी व शेतकरी कल्याण मंत्रालय',
    hi: 'कृषि और किसान कल्याण मंत्रालय',
    ml: 'കൃഷി, കർഷക ക്ഷേമ മന്ത്രാലയം'
  },
  'Ministry of New and Renewable Energy': {
    en: 'Ministry of New and Renewable Energy',
    mr: 'नवीन व नवीकरणीय ऊर्जा मंत्रालय',
    hi: 'नवीन और नवीकरणीय ऊर्जा मंत्रालय',
    ml: 'പുതിയതും പുനരുപയോഗിക്കാവുന്നതുമായ ഊർജ മന്ത്രാലയം'
  },
  'Department of Agriculture, Maharashtra': {
    en: 'Department of Agriculture, Maharashtra',
    mr: 'कृषी विभाग, महाराष्ट्र',
    hi: 'कृषि विभाग, महाराष्ट्र',
    ml: 'കൃഷി വകുപ്പ്, മഹാരാഷ്ട്ര'
  },
  'Department of Agriculture, Government of Maharashtra': {
    en: 'Department of Agriculture, Government of Maharashtra',
    mr: 'महाराष्ट्र शासनाचा कृषी विभाग',
    hi: 'महाराष्ट्र सरकार का कृषि विभाग',
    ml: 'മഹാരാഷ്ട്ര സർക്കാരിന്റെ കൃഷിവകുപ്പ്'
  },
  'Department of Agriculture, Government of Maharashtra (often SMAM / state top-up)': {
    en: 'Department of Agriculture, Government of Maharashtra (often SMAM / state top-up)',
    mr: 'महाराष्ट्र शासनाचा कृषी विभाग (बहुतेक वेळा SMAM / राज्याच्या अतिरिक्त अनुदानासह)',
    hi: 'महाराष्ट्र सरकार का कृषि विभाग (अक्सर SMAM / राज्य की अतिरिक्त सहायता के साथ)',
    ml: 'മഹാരാഷ്ട്ര സർക്കാരിന്റെ കൃഷിവകുപ്പ് (സാധാരണയായി SMAM / സംസ്ഥാനത്തിന്റെ അധിക സഹായത്തോടെ)'
  },
  'Department of Financial Services / NABARD / Scheduled Banks': {
    en: 'Department of Financial Services / NABARD / Scheduled Banks',
    mr: 'वित्तीय सेवा विभाग / नाबार्ड (NABARD) / अनुसूचित बँका',
    hi: 'वित्तीय सेवा विभाग / नाबार्ड (NABARD) / अनुसूचित बैंक',
    ml: 'ധനകാര്യ സേവന വകുപ്പ് / നബാർഡ് (NABARD) / ഷെഡ്യൂൾഡ് ബാങ്കുകൾ'
  },
  'Ministry of Agriculture & Farmers Welfare / Department of Agriculture & Farmers Welfare': {
    en: 'Ministry of Agriculture & Farmers Welfare / Department of Agriculture & Farmers Welfare',
    mr: 'कृषी आणि शेतकरी कल्याण मंत्रालय / कृषी आणि शेतकरी कल्याण विभाग',
    hi: 'कृषि एवं किसान कल्याण मंत्रालय / कृषि एवं किसान कल्याण विभाग',
    ml: 'കൃഷി, കർഷക ക്ഷേമ മന്ത്രാലയം / കൃഷി, കർഷക ക്ഷേമ വകുപ്പ്'
  },
  'Ministry of Agriculture & Farmers Welfare / Department of Water Resources (component-wise)': {
    en: 'Ministry of Agriculture & Farmers Welfare / Department of Water Resources (component-wise)',
    mr: 'कृषी आणि शेतकरी कल्याण मंत्रालय / जलसंपदा विभाग (घटकानुसार)',
    hi: 'कृषि एवं किसान कल्याण मंत्रालय / जल संसाधन विभाग (घटकानुसार)',
    ml: 'കൃഷി, കർഷക ക്ഷേമ മന്ത്രാലയം / ജലവിഭവ വകുപ്പ് (ഘടകമനുസരിച്ച്)'
  },
  'Government of Maharashtra / Direct Benefit Transfer portal': {
    en: 'Government of Maharashtra / Direct Benefit Transfer portal',
    mr: 'महाराष्ट्र शासन / थेट लाभ हस्तांतरण (DBT) पोर्टल',
    hi: 'महाराष्ट्र सरकार / प्रत्यक्ष लाभ अंतरण (DBT) पोर्टल',
    ml: 'മഹാരാഷ്ട്ര സർക്കാർ / ഡയറക്ട് ബെനിഫിറ്റ് ട്രാൻസ്ഫർ (DBT) പോർട്ടൽ'
  },
  'Ministry of Agriculture & Farmers Welfare / State Agriculture Departments': {
    en: 'Ministry of Agriculture & Farmers Welfare / State Agriculture Departments',
    mr: 'कृषी आणि शेतकरी कल्याण मंत्रालय / राज्य कृषी विभाग',
    hi: 'कृषि एवं किसान कल्याण मंत्रालय / राज्य कृषि विभाग',
    ml: 'കൃഷി, കർഷക ക്ഷേമ മന്ത്രാലയം / സംസ്ഥാന കൃഷി വകുപ്പുകൾ'
  },
  'Government of India (National Government Services Portal / myScheme)': {
    en: 'Government of India (National Government Services Portal / myScheme)',
    mr: 'भारत सरकार (राष्ट्रीय सरकारी सेवा पोर्टल / myScheme)',
    hi: 'भारत सरकार (राष्ट्रीय सरकारी सेवा पोर्टल / myScheme)',
    ml: 'ഇന്ത്യാ സർക്കാർ (ദേശീയ സർക്കാർ സേവന പോർട്ടൽ / myScheme)'
  }
}

const schemeDescriptions = {
  'maha-farm-mechanisation': {
    en: 'Subsidy on notified farm machinery and implements when the corresponding MahaDBT service is open. Eligible machines, farmer categories, and subsidy percentages are in the current guidelines.',
    mr: 'संबंधित MahaDBT सेवा सुरू असताना अधिसूचित कृषी यंत्रे आणि उपकरणांवर अनुदान दिले जाते. पात्र यंत्रे, शेतकऱ्यांच्या श्रेणी आणि अनुदानाची टक्केवारी सध्याच्या मार्गदर्शक तत्त्वांनुसार ठरते.',
    hi: 'संबंधित MahaDBT सेवा उपलब्ध होने पर अधिसूचित कृषि मशीनों और उपकरणों पर सब्सिडी दी जाती है। पात्र मशीनें, किसान श्रेणियाँ और सब्सिडी की प्रतिशत दरें वर्तमान दिशानिर्देशों के अनुसार निर्धारित होती हैं।',
    ml: 'ബന്ധപ്പെട്ട MahaDBT സേവനം ലഭ്യമാകുമ്പോൾ വിജ്ഞാപനം ചെയ്ത കാർഷിക യന്ത്രങ്ങൾക്കും ഉപകരണങ്ങൾക്കും സബ്‌സിഡി ലഭിക്കും. അർഹമായ യന്ത്രങ്ങൾ, കർഷകരുടെ വിഭാഗങ്ങൾ, സബ്‌സിഡി ശതമാനങ്ങൾ എന്നിവ നിലവിലെ മാർഗ്ഗനിർദ്ദേശങ്ങൾ അനുസരിച്ചായിരിക്കും.'
  },
  'kisan-credit-card': {
    en: 'Short-term credit for cultivation, post-harvest, and farm-related needs through banks, with interest subvention as notified by the Government of India from time to time. Exact limit and interest rate are decided by the lending bank.',
    mr: 'बँकांमार्फत शेती, कापणीनंतरची कामे आणि शेतीशी संबंधित गरजांसाठी अल्पकालीन कर्ज दिले जाते. भारत सरकार वेळोवेळी जाहीर करत असलेल्या नियमानुसार व्याज सवलत लागू होऊ शकते. कर्जाची नेमकी मर्यादा आणि व्याजदर कर्ज देणारी बँक ठरवते.',
    hi: 'बैंकों के माध्यम से खेती, कटाई के बाद के कार्यों और कृषि संबंधी आवश्यकताओं के लिए अल्पकालीन ऋण दिया जाता है। भारत सरकार द्वारा समय-समय पर अधिसूचित नियमों के अनुसार ब्याज में छूट लागू हो सकती है। ऋण की सटीक सीमा और ब्याज दर ऋण देने वाला बैंक निर्धारित करता है।',
    ml: 'കൃഷി, വിളവെടുപ്പിന് ശേഷമുള്ള പ്രവർത്തനങ്ങൾ, കൃഷിയുമായി ബന്ധപ്പെട്ട ആവശ്യങ്ങൾ എന്നിവയ്ക്കായി ബാങ്കുകൾ വഴി ഹ്രസ്വകാല വായ്പ ലഭിക്കുന്നു. കേന്ദ്ര സർക്കാർ കാലാകാലങ്ങളിൽ പ്രഖ്യാപിക്കുന്ന വ്യവസ്ഥകൾ പ്രകാരം പലിശ ഇളവ് ലഭിക്കാം. വായ്പയുടെ കൃത്യമായ പരിധിയും പലിശനിരക്കും വായ്പ നൽകുന്ന ബാങ്കാണ് തീരുമാനിക്കുന്നത്.'
  },
  'maha-farm-pond': {
    en: 'Maharashtra farm-pond / farm-water storage assistance as implemented through the Agriculture Department and MahaDBT when the service is open. Dimensions, lining, and subsidy are as per the current government resolution.',
    mr: 'कृषी विभाग आणि MahaDBT मार्फत सेवा सुरू असताना महाराष्ट्रातील शेततळे व शेतातील पाणी साठवण सुविधांसाठी मदत दिली जाते. शेततळ्याचे आकारमान, अस्तरीकरण आणि अनुदान हे सध्याच्या शासन निर्णयानुसार ठरते.',
    hi: 'कृषि विभाग और MahaDBT के माध्यम से सेवा उपलब्ध होने पर महाराष्ट्र में खेत-तालाब और खेत में पानी के भंडारण के लिए सहायता दी जाती है। तालाब के आयाम, लाइनिंग और सब्सिडी वर्तमान सरकारी आदेश के अनुसार निर्धारित होते हैं।',
    ml: 'കൃഷിവകുപ്പും MahaDBT സംവിധാനവും വഴി സേവനം ലഭ്യമാകുമ്പോൾ മഹാരാഷ്ട്രയിൽ കൃഷിക്കുളങ്ങൾക്കും കൃഷിയിടത്തിലെ ജലസംഭരണത്തിനും സഹായം നൽകുന്നു. കുളത്തിന്റെ അളവുകൾ, ലൈനിംഗ്, സബ്‌സിഡി എന്നിവ നിലവിലെ സർക്കാർ ഉത്തരവനുസരിച്ചായിരിക്കും.'
  },
  'mahadbt-agriculture': {
    en: 'Single Maharashtra portal for many farmer-facing DBT schemes (farm mechanisation, micro-irrigation, horticulture, etc.). Each service has its own eligibility, documents, and opening dates.',
    mr: 'शेती यांत्रिकीकरण, सूक्ष्म सिंचन, फलोत्पादन इत्यादी शेतकऱ्यांसाठीच्या अनेक DBT योजनांसाठी महाराष्ट्राचे एकच पोर्टल आहे. प्रत्येक सेवेसाठी स्वतंत्र पात्रता निकष, आवश्यक कागदपत्रे आणि अर्ज सुरू होण्याच्या तारखा असतात.',
    hi: 'कृषि यंत्रीकरण, सूक्ष्म सिंचाई, बागवानी आदि किसानों से संबंधित अनेक DBT योजनाओं के लिए महाराष्ट्र का यह एकल पोर्टल है। प्रत्येक सेवा के लिए पात्रता मानदंड, आवश्यक दस्तावेज़ और आवेदन शुरू होने की तारीखें अलग-अलग होती हैं।',
    ml: 'കാർഷിക യന്ത്രവൽക്കരണം, സൂക്ഷ്മ ജലസേചനം, തോട്ടകൃഷി തുടങ്ങിയ കർഷകർക്കായുള്ള നിരവധി DBT പദ്ധതികൾക്കായി മഹാരാഷ്ട്രയിൽ ഉപയോഗിക്കുന്ന ഏക പോർട്ടലാണിത്. ഓരോ സേവനത്തിനും പ്രത്യേക യോഗ്യതാ മാനദണ്ഡങ്ങളും ആവശ്യമായ രേഖകളും അപേക്ഷ ആരംഭിക്കുന്ന തീയതികളും ഉണ്ടായിരിക്കും.'
  },
  'pm-kusum': {
    en: 'Support for solar agriculture pumps and solarisation of existing grid-connected pumps, implemented by states. Component-wise CFA and farmer contribution are notified by MNRE and the state implementing agency.',
    mr: 'राज्यांमार्फत सौर कृषी पंप आणि विद्यमान वीज-जोडणी असलेल्या पंपांचे सौर ऊर्जेत रूपांतर करण्यासाठी मदत दिली जाते. प्रत्येक घटकासाठी केंद्राची आर्थिक मदत (CFA) आणि शेतकऱ्याचा हिस्सा MNRE व राज्य अंमलबजावणी संस्थेद्वारे जाहीर केला जातो.',
    hi: 'राज्यों के माध्यम से सौर कृषि पंपों और मौजूदा ग्रिड से जुड़े पंपों को सौर ऊर्जा आधारित बनाने के लिए सहायता दी जाती है। प्रत्येक घटक के लिए केंद्रीय वित्तीय सहायता (CFA) और किसान का योगदान MNRE तथा राज्य की कार्यान्वयन एजेंसी द्वारा अधिसूचित किया जाता है।',
    ml: 'സംസ്ഥാനങ്ങൾ മുഖേന സോളാർ കാർഷിക പമ്പുകൾ സ്ഥാപിക്കുന്നതിനും നിലവിലുള്ള വൈദ്യുതി ഗ്രിഡുമായി ബന്ധിപ്പിച്ച പമ്പുകൾ സൗരോർജ്ജത്തിലേക്ക് മാറ്റുന്നതിനും സഹായം നൽകുന്നു. ഓരോ ഘടകത്തിനുമുള്ള കേന്ദ്ര സാമ്പത്തിക സഹായവും (CFA) കർഷകന്റെ വിഹിതവും MNREയും സംസ്ഥാന നടപ്പാക്കൽ ഏജൻസിയും പ്രഖ്യാപിക്കുന്നു.'
  },
  'pm-kisan': {
    en: 'Income support of ₹6,000 per year to eligible farmer families, paid in three equal instalments of ₹2,000, subject to current Government of India rules.',
    mr: 'पात्र शेतकरी कुटुंबांना दरवर्षी ₹६,००० आर्थिक मदत दिली जाते. ही रक्कम भारत सरकारच्या सध्याच्या नियमांनुसार ₹२,००० च्या तीन समान हप्त्यांमध्ये दिली जाते.',
    hi: 'पात्र किसान परिवारों को प्रति वर्ष ₹6,000 की आर्थिक सहायता दी जाती है। भारत सरकार के वर्तमान नियमों के अनुसार यह राशि ₹2,000 की तीन समान किस्तों में दी जाती है।',
    ml: 'അർഹരായ കർഷക കുടുംബങ്ങൾക്ക് പ്രതിവർഷം ₹6,000 സാമ്പത്തിക സഹായം നൽകുന്നു. കേന്ദ്ര സർക്കാരിന്റെ നിലവിലെ നിയമങ്ങൾ പ്രകാരം ഈ തുക ₹2,000 വീതമുള്ള മൂന്ന് തുല്യ ഗഡുക്കളായി നൽകുന്നു.'
  },
  pmfby: {
    en: 'Crop insurance cover against notified yield losses, prevented sowing, mid-season adversity, and post-harvest losses where the state has notified the crop, area, and season. Sum insured and premium subsidy follow the current season notification.',
    mr: 'राज्याने संबंधित पीक, क्षेत्र आणि हंगाम अधिसूचित केलेला असल्यास, अधिसूचित उत्पादनातील नुकसान, पेरणी न होणे, हंगामाच्या मध्यातील प्रतिकूल परिस्थिती आणि कापणीनंतरचे नुकसान यासाठी पीक विमा संरक्षण मिळू शकते. विमा रक्कम आणि प्रीमियमवरील अनुदान हे चालू हंगामाच्या अधिसूचनेनुसार ठरते.',
    hi: 'यदि राज्य ने संबंधित फसल, क्षेत्र और मौसम को अधिसूचित किया है, तो अधिसूचित उपज में नुकसान, बुवाई न हो पाना, मौसम के मध्य में प्रतिकूल परिस्थितियाँ और कटाई के बाद होने वाले नुकसान के लिए फसल बीमा कवर मिल सकता है। बीमित राशि और प्रीमियम सब्सिडी वर्तमान मौसम की अधिसूचना के अनुसार निर्धारित होती है।',
    ml: 'സംസ്ഥാനം ബന്ധപ്പെട്ട വിള, പ്രദേശം, സീസൺ എന്നിവ വിജ്ഞാപനം ചെയ്തിട്ടുണ്ടെങ്കിൽ വിജ്ഞാപനം ചെയ്ത വിളവിലെ നഷ്ടം, വിതയ്ക്കാൻ കഴിയാതിരിക്കുക, മധ്യകാല പ്രതികൂല സാഹചര്യം, വിളവെടുപ്പിന് ശേഷമുള്ള നഷ്ടം എന്നിവയ്ക്കെതിരെ വിള ഇൻഷുറൻസ് പരിരക്ഷ ലഭിക്കും. ഇൻഷ്വർ ചെയ്ത തുകയും പ്രീമിയം സബ്‌സിഡിയും നിലവിലെ സീസൺ വിജ്ഞാപനം അനുസരിച്ചായിരിക്കും.'
  },
  'pmksy': {
    en: "Support for irrigation, including 'Per Drop More Crop' micro-irrigation (drip/sprinkler) and other PMKSY components implemented by states. Subsidy rates and unit costs are notified by the state implementing agency.",
    mr: "'प्रति थेंब अधिक पीक' या सूक्ष्म सिंचन उपक्रमासह (ठिबक/तुषार सिंचन) आणि राज्यांमार्फत राबविल्या जाणाऱ्या PMKSY च्या इतर घटकांसाठी सिंचन सहाय्य दिले जाते. अनुदानाचे दर आणि प्रति युनिट खर्च राज्य अंमलबजावणी संस्था जाहीर करते.",
    hi: "'प्रति बूंद अधिक फसल' सूक्ष्म सिंचाई (ड्रिप/स्प्रिंकलर) और राज्यों द्वारा लागू PMKSY के अन्य घटकों सहित सिंचाई के लिए सहायता दी जाती है। सब्सिडी दरें और प्रति इकाई लागत राज्य की कार्यान्वयन एजेंसी द्वारा अधिसूचित की जाती हैं।",
    ml: "'ഓരോ തുള്ളിയിലും കൂടുതൽ വിളവ്' എന്ന സൂക്ഷ്മ ജലസേചന പദ്ധതിയും (ഡ്രിപ്പ്/സ്പ്രിങ്ക്ലർ) സംസ്ഥാനങ്ങൾ നടപ്പിലാക്കുന്ന PMKSYയുടെ മറ്റ് ഘടകങ്ങളും ഉൾപ്പെടെ ജലസേചനത്തിന് സഹായം നൽകുന്നു. സബ്‌സിഡി നിരക്കുകളും യൂണിറ്റ് ചെലവുകളും സംസ്ഥാന നടപ്പാക്കൽ ഏജൻസി വിജ്ഞാപനം ചെയ്യുന്നു."
  },
  'soil-health-card': {
    en: 'Soil sample testing and a Soil Health Card with nutrient status and fertilizer recommendations. It is an advisory service, not a cash transfer.',
    mr: 'मातीच्या नमुन्यांची तपासणी करून पोषक स्थिती आणि खतांच्या शिफारशींसह मृदा आरोग्य पत्रिका दिली जाते. ही रोख रक्कम हस्तांतरण योजना नसून सल्ला सेवा आहे.',
    hi: 'मिट्टी के नमूने की जाँच और पोषक स्थिति तथा उर्वरक सिफारिशों वाला मृदा स्वास्थ्य कार्ड प्रदान किया जाता है। यह नकद अंतरण नहीं, बल्कि सलाह सेवा है।',
    ml: 'മണ്ണിന്റെ സാമ്പിൾ പരിശോധന നടത്തി പോഷക നിലയും വളപ്രയോഗ ശുപാർശകളും ഉൾപ്പെട്ട മണ്ണിന്റെ ആരോഗ്യ കാർഡ് നൽകുന്നു. ഇത് പണ കൈമാറ്റമല്ല, ഉപദേശ സേവനമാണ്.'
  },
  'myscheme-directory': {
    en: 'National directory to discover central and state schemes. It is not itself a benefit scheme. Use it to find official scheme pages.',
    mr: 'केंद्र आणि राज्य योजनांचा शोध घेण्यासाठी राष्ट्रीय निर्देशिका. ही स्वतः लाभ योजना नाही. अधिकृत योजना पृष्ठे शोधण्यासाठी तिचा वापर करा.',
    hi: 'केंद्र और राज्य योजनाओं को खोजने के लिए राष्ट्रीय निर्देशिका। यह स्वयं कोई लाभ योजना नहीं है। आधिकारिक योजना पृष्ठ खोजने के लिए इसका उपयोग करें।',
    ml: 'കേന്ദ്ര-സംസ്ഥാന പദ്ധതികൾ കണ്ടെത്താനുള്ള ദേശീയ ഡയറക്ടറിയാണിത്. ഇത് സ്വയം ഒരു ആനുകൂല്യ പദ്ധതിയല്ല. ഔദ്യോഗിക പദ്ധതി പേജുകൾ കണ്ടെത്താൻ ഇത് ഉപയോഗിക്കുക.'
  }
}

const documentTranslations = {
  'pm-kisan': {
    aadhaar: {
      en: ['Aadhaar', 'Used for identity and DBT authentication on the official portal.'],
      mr: ['आधार', 'अधिकृत पोर्टलवर ओळख आणि DBT प्रमाणीकरणासाठी वापरले जाते.'],
      hi: ['आधार', 'आधिकारिक पोर्टल पर पहचान और DBT प्रमाणीकरण के लिए उपयोग किया जाता है।'],
      ml: ['ആധാർ', 'ഔദ്യോഗിക പോർട്ടലിൽ തിരിച്ചറിയലിനും DBT പ്രാമാണീകരണത്തിനും ഉപയോഗിക്കുന്നു.']
    },
    land_record: {
      en: ['Land ownership record (7/12 extract / Record of Rights)', 'PM-KISAN is linked to cultivable land records.'],
      mr: ['जमीन मालकीचा दाखला (७/१२ उतारा / हक्क अभिलेख)', 'PM-KISAN लागवडीयोग्य जमीन अभिलेखांशी जोडलेली आहे.'],
      hi: ['भूमि स्वामित्व अभिलेख (7/12 उतारा / अधिकार अभिलेख)', 'PM-KISAN खेती योग्य भूमि अभिलेखों से जुड़ी है।'],
      ml: ['ഭൂമി ഉടമസ്ഥാവകാശ രേഖ (7/12 പകർപ്പ് / അവകാശ രേഖ)', 'PM-KISAN കൃഷിയോഗ്യ ഭൂമി രേഖകളുമായി ബന്ധിപ്പിച്ചിരിക്കുന്നു.']
    },
    bank_passbook: {
      en: ['Bank passbook / cancelled cheque (account details)', 'Benefit is transferred to a bank account linked for DBT. Enter details only on the official portal, never in this app.'],
      mr: ['बँक पासबुक / रद्द केलेला धनादेश (खाते तपशील)', 'लाभ DBT साठी जोडलेल्या बँक खात्यात हस्तांतरित केला जातो. तपशील फक्त अधिकृत पोर्टलवर भरा, या ॲपमध्ये कधीही नाही.'],
      hi: ['बैंक पासबुक / रद्द किया हुआ चेक (खाते का विवरण)', 'लाभ DBT से जुड़े बैंक खाते में स्थानांतरित किया जाता है। विवरण केवल आधिकारिक पोर्टल पर दर्ज करें, इस ऐप में कभी नहीं।'],
      ml: ['ബാങ്ക് പാസ്‌ബുക്ക് / റദ്ദാക്കിയ ചെക്ക് (അക്കൗണ്ട് വിവരങ്ങൾ)', 'DBT-യുമായി ബന്ധിപ്പിച്ച ബാങ്ക് അക്കൗണ്ടിലേക്കാണ് ആനുകൂല്യം കൈമാറുന്നത്. വിവരങ്ങൾ ഔദ്യോഗിക പോർട്ടലിൽ മാത്രം നൽകുക, ഈ ആപ്പിൽ ഒരിക്കലും നൽകരുത്.']
    },
    photo: {
      en: ['Passport-size photograph', 'May be requested during CSC or state registration.'],
      mr: ['पासपोर्ट आकाराचा फोटो', 'CSC किंवा राज्य नोंदणीदरम्यान मागितला जाऊ शकतो.'],
      hi: ['पासपोर्ट आकार का फोटो', 'CSC या राज्य पंजीकरण के दौरान मांगा जा सकता है।'],
      ml: ['പാസ്‌പോർട്ട് വലുപ്പത്തിലുള്ള ഫോട്ടോ', 'CSC അല്ലെങ്കിൽ സംസ്ഥാന രജിസ്ട്രേഷൻ സമയത്ത് ആവശ്യപ്പെട്ടേക്കാം.']
    },
    'soil-health-card': {
      identity: {
        en: ['Aadhaar or farmer identity used by the state', 'Needed if you register on the portal or at a Raithu/Krishi office.'],
        mr: ['आधार किंवा राज्याने वापरलेली शेतकरी ओळख', 'पोर्टलवर किंवा रैथू/कृषी कार्यालयात नोंदणी करताना आवश्यक.'],
        hi: ['आधार या राज्य द्वारा उपयोग की जाने वाली किसान पहचान', 'पोर्टल या रैथु/कृषि कार्यालय में पंजीकरण करते समय आवश्यक।'],
        ml: ['ആധാർ അല്ലെങ്കിൽ സംസ്ഥാനം ഉപയോഗിക്കുന്ന കർഷക തിരിച്ചറിയൽ', 'പോർട്ടലിലോ റൈതു/കൃഷി ഓഫീസിലോ രജിസ്റ്റർ ചെയ്യുമ്പോൾ ആവശ്യമാണ്.']
      },
      land_record: {
        en: ['Land details / survey number', 'Sample is linked to a plot.'],
        mr: ['जमिनीचे तपशील / सर्वेक्षण क्रमांक', 'नमुना एका भूखंडाशी जोडलेला असतो.'],
        hi: ['भूमि विवरण / सर्वे नंबर', 'नमूना एक भूखंड से जुड़ा होता है।'],
        ml: ['ഭൂമി വിവരങ്ങൾ / സർവേ നമ്പർ', 'സാമ്പിൾ ഒരു പ്ലോട്ടുമായി ബന്ധിപ്പിച്ചിരിക്കുന്നു.']
      }
    }
  }
}

const stepTranslations = {
  'pm-kisan': {
    1: {
      en: ['Check eligibility', 'Confirm you are a farmer family with cultivable land in records and that you are not in a notified exclusion category.'],
      mr: ['पात्रता तपासा', 'अभिलेखांमध्ये लागवडीयोग्य जमीन असलेले शेतकरी कुटुंब आहात आणि अधिसूचित अपवर्जन श्रेणीत नाही याची खात्री करा.'],
      hi: ['पात्रता जाँचें', 'सुनिश्चित करें कि अभिलेखों में खेती योग्य भूमि वाला किसान परिवार है और आप अधिसूचित बहिष्करण श्रेणी में नहीं आते।'],
      ml: ['അർഹത പരിശോധിക്കുക', 'രേഖകളിൽ കൃഷിയോഗ്യമായ ഭൂമിയുള്ള കർഷക കുടുംബമാണെന്നും വിജ്ഞാപനം ചെയ്ത ഒഴിവാക്കൽ വിഭാഗത്തിൽപ്പെടുന്നില്ലെന്നും ഉറപ്പാക്കുക.']
    },
    2: {
      en: ['Gather documents', 'Keep Aadhaar, land record, and bank passbook ready. Do not share OTP or banking password with anyone, including this app.'],
      mr: ['कागदपत्रे गोळा करा', 'आधार, जमीन अभिलेख आणि बँक पासबुक तयार ठेवा. या ॲपसह कोणाशीही OTP किंवा बँकिंग पासवर्ड शेअर करू नका.'],
      hi: ['दस्तावेज़ एकत्र करें', 'आधार, भूमि अभिलेख और बैंक पासबुक तैयार रखें। इस ऐप सहित किसी के साथ OTP या बैंकिंग पासवर्ड साझा न करें।'],
      ml: ['രേഖകൾ ശേഖരിക്കുക', 'ആധാർ, ഭൂമി രേഖ, ബാങ്ക് പാസ്‌ബുക്ക് എന്നിവ തയ്യാറാക്കുക. ഈ ആപ്പ് ഉൾപ്പെടെ ആരുമായും OTP അല്ലെങ്കിൽ ബാങ്കിംഗ് പാസ്‌വേഡ് പങ്കിടരുത്.']
    },
    3: {
      en: ['Open the official portal', 'Use https://pmkisan.gov.in only. Beware of lookalike websites.'],
      mr: ['अधिकृत पोर्टल उघडा', 'फक्त https://pmkisan.gov.in वापरा. बनावट दिसणाऱ्या संकेतस्थळांपासून सावध रहा.'],
      hi: ['आधिकारिक पोर्टल खोलें', 'केवल https://pmkisan.gov.in का उपयोग करें। मिलती-जुलती नकली वेबसाइटों से सावधान रहें।'],
      ml: ['ഔദ്യോഗിക പോർട്ടൽ തുറക്കുക', 'https://pmkisan.gov.in മാത്രം ഉപയോഗിക്കുക. സമാനമായി തോന്നുന്ന വ്യാജ വെബ്‌സൈറ്റുകളെ സൂക്ഷിക്കുക.']
    },
    4: {
      en: ['Register or sign in on the government site', 'New farmers typically use Farmer Corner / new registration. Existing beneficiaries can check status with Aadhaar. Authentication happens on the government website, not here.'],
      mr: ['सरकारी संकेतस्थळावर नोंदणी करा किंवा साइन इन करा', 'नवीन शेतकरी सामान्यतः Farmer Corner / नवीन नोंदणी वापरतात. विद्यमान लाभार्थी आधारद्वारे स्थिती तपासू शकतात. प्रमाणीकरण सरकारी संकेतस्थळावर होते, येथे नाही.'],
      hi: ['सरकारी वेबसाइट पर पंजीकरण या साइन इन करें', 'नए किसान सामान्यतः Farmer Corner / नए पंजीकरण का उपयोग करते हैं। मौजूदा लाभार्थी आधार से स्थिति जाँच सकते हैं। प्रमाणीकरण सरकारी वेबसाइट पर होता है, यहाँ नहीं।'],
      ml: ['സർക്കാർ വെബ്‌സൈറ്റിൽ രജിസ്റ്റർ ചെയ്യുക അല്ലെങ്കിൽ സൈൻ ഇൻ ചെയ്യുക', 'പുതിയ കർഷകർ സാധാരണയായി Farmer Corner / പുതിയ രജിസ്ട്രേഷൻ ഉപയോഗിക്കുന്നു. നിലവിലെ ഗുണഭോക്താക്കൾക്ക് ആധാർ ഉപയോഗിച്ച് നില പരിശോധിക്കാം. പ്രാമാണീകരണം സർക്കാർ വെബ്‌സൈറ്റിലാണ് നടക്കുന്നത്, ഇവിടെ അല്ല.']
    },
    5: {
      en: ['Locate the registration or correction form', 'Follow Farmer Corner links on the official site. Menu labels can change; use the portal help / FAQ if unsure.'],
      mr: ['नोंदणी किंवा दुरुस्तीचा फॉर्म शोधा', 'अधिकृत संकेतस्थळावरील Farmer Corner दुवे वापरा. मेनूची नावे बदलू शकतात; शंका असल्यास पोर्टलची मदत / FAQ वापरा.'],
      hi: ['पंजीकरण या सुधार फॉर्म खोजें', 'आधिकारिक वेबसाइट पर Farmer Corner लिंक का पालन करें। मेनू के नाम बदल सकते हैं; संदेह होने पर पोर्टल की सहायता / FAQ देखें।'],
      ml: ['രജിസ്ട്രേഷൻ അല്ലെങ്കിൽ തിരുത്തൽ ഫോം കണ്ടെത്തുക', 'ഔദ്യോഗിക സൈറ്റിലെ Farmer Corner ലിങ്കുകൾ പിന്തുടരുക. മെനു പേരുകൾ മാറാം; സംശയമുണ്ടെങ്കിൽ പോർട്ടൽ സഹായം / FAQ ഉപയോഗിക്കുക.']
    },
    6: {
      en: ['Enter farmer and land details', 'Fill name, Aadhaar, bank, and land details exactly as in official records.'],
      mr: ['शेतकरी आणि जमिनीचे तपशील भरा', 'नाव, आधार, बँक आणि जमीन तपशील अधिकृत अभिलेखांप्रमाणेच भरा.'],
      hi: ['किसान और भूमि विवरण दर्ज करें', 'नाम, आधार, बैंक और भूमि विवरण आधिकारिक अभिलेखों के अनुसार ही भरें।'],
      ml: ['കർഷകന്റെയും ഭൂമിയുടെയും വിവരങ്ങൾ നൽകുക', 'പേര്, ആധാർ, ബാങ്ക്, ഭൂമി വിവരങ്ങൾ ഔദ്യോഗിക രേഖകളിലുള്ളതുപോലെ തന്നെ പൂരിപ്പിക്കുക.']
    },
    7: {
      en: ['Upload documents if asked', 'Upload only on the official site or at an authorised CSC.'],
      mr: ['विचारल्यास कागदपत्रे अपलोड करा', 'कागदपत्रे फक्त अधिकृत संकेतस्थळावर किंवा अधिकृत CSC वर अपलोड करा.'],
      hi: ['माँगे जाने पर दस्तावेज़ अपलोड करें', 'दस्तावेज़ केवल आधिकारिक वेबसाइट या अधिकृत CSC पर ही अपलोड करें।'],
      ml: ['ആവശ്യപ്പെട്ടാൽ രേഖകൾ അപ്‌ലോഡ് ചെയ്യുക', 'ഔദ്യോഗിക സൈറ്റിലോ അംഗീകൃത CSC-യിലോ മാത്രം രേഖകൾ അപ്‌ലോഡ് ചെയ്യുക.']
    },
    8: {
      en: ['Review and submit', 'Check every field before submit. State/district officials verify records.'],
      mr: ['तपासून सबमिट करा', 'सबमिट करण्यापूर्वी प्रत्येक फील्ड तपासा. राज्य/जिल्हा अधिकारी अभिलेखांची पडताळणी करतात.'],
      hi: ['समीक्षा करें और सबमिट करें', 'सबमिट करने से पहले हर फ़ील्ड जाँचें। राज्य/जिला अधिकारी अभिलेखों का सत्यापन करते हैं।'],
      ml: ['പരിശോധിച്ച് സമർപ്പിക്കുക', 'സമർപ്പിക്കുന്നതിന് മുമ്പ് എല്ലാ ഫീൽഡുകളും പരിശോധിക്കുക. സംസ്ഥാന/ജില്ലാ ഉദ്യോഗസ്ഥർ രേഖകൾ പരിശോധിക്കും.']
    },
    9: {
      en: ['Save the acknowledgement', 'Note the registration/acknowledgement number shown by the portal.'],
      mr: ['पोचपावती जतन करा', 'पोर्टलने दाखवलेला नोंदणी/पोचपावती क्रमांक नोंदवा.'],
      hi: ['पावती सुरक्षित रखें', 'पोर्टल द्वारा दिखाया गया पंजीकरण/पावती नंबर नोट करें।'],
      ml: ['സ്വീകാര്യപത്രം സംരക്ഷിക്കുക', 'പോർട്ടൽ കാണിക്കുന്ന രജിസ്ട്രേഷൻ/സ്വീകാര്യപത്ര നമ്പർ കുറിച്ചുവെക്കുക.']
    },
    10: {
      en: ['Check status', 'Use Beneficiary Status on pmkisan.gov.in. Follow up with the State Nodal Officer if payment is pending after verification.'],
      mr: ['स्थिती तपासा', 'pmkisan.gov.in वरील Beneficiary Status वापरा. पडताळणीनंतर पेमेंट प्रलंबित असल्यास राज्य नोडल अधिकाऱ्याशी संपर्क करा.'],
      hi: ['स्थिति जाँचें', 'pmkisan.gov.in पर Beneficiary Status का उपयोग करें। सत्यापन के बाद भुगतान लंबित हो तो राज्य नोडल अधिकारी से संपर्क करें।'],
      ml: ['നില പരിശോധിക്കുക', 'pmkisan.gov.in-ലെ Beneficiary Status ഉപയോഗിക്കുക. പരിശോധനയ്ക്ക് ശേഷം പണമടയ്ക്കൽ വൈകുകയാണെങ്കിൽ സംസ്ഥാന നോഡൽ ഓഫീസറെ ബന്ധപ്പെടുക.']
    },
    'soil-health-card': {
      1: { en: ['See if a card already exists', 'Search on https://www.soilhealth.dac.gov.in using the options published on the portal.'], mr: ['കാർഡ് നിലവിലുണ്ടോ എന്ന് പരിശോധിക്കുക', 'പോർട്ടലിൽ നൽകിയിരിക്കുന്ന ഓപ്ഷനുകൾ ഉപയോഗിച്ച് https://www.soilhealth.dac.gov.in ൽ തിരയുക.'], hi: ['देखें कि कार्ड पहले से है या नहीं', 'पोर्टल पर दिए विकल्पों का उपयोग करके https://www.soilhealth.dac.gov.in पर खोजें।'], ml: ['കാർഡ് നിലവിലുണ്ടോ എന്ന് പരിശോധിക്കുക', 'പോർട്ടലിൽ പ്രസിദ്ധീകരിച്ച ഓപ്ഷനുകൾ ഉപയോഗിച്ച് https://www.soilhealth.dac.gov.in ൽ തിരയുക.'] },
      2: { en: ['Contact local agriculture office if no recent card', 'Village sampling is usually scheduled by the department.'], mr: ['अलीकडील कार्ड नसेल तर स्थानिक कृषी कार्यालयाशी संपर्क करा', 'गावातील नमुना संकलन विभागाकडून सामान्यतः ठरवले जाते.'], hi: ['हाल का कार्ड न हो तो स्थानीय कृषि कार्यालय से संपर्क करें', 'गाँव में नमूना लेना सामान्यतः विभाग द्वारा तय किया जाता है।'], ml: ['പുതിയ കാർഡ് ഇല്ലെങ്കിൽ പ്രാദേശിക കൃഷി ഓഫീസുമായി ബന്ധപ്പെടുക', 'ഗ്രാമത്തിലെ സാമ്പിൾ ശേഖരണം സാധാരണയായി വകുപ്പ് നിശ്ചയിക്കുന്നു.'] },
      3: { en: ['Use only the official soil health portal', 'https://www.soilhealth.dac.gov.in'], mr: ['फक्त अधिकृत मृदा आरोग्य पोर्टल वापरा', 'https://www.soilhealth.dac.gov.in'], hi: ['केवल आधिकारिक मृदा स्वास्थ्य पोर्टल का उपयोग करें', 'https://www.soilhealth.dac.gov.in'], ml: ['ഔദ്യോഗിക മണ്ണിന്റെ ആരോഗ്യ പോർട്ടൽ മാത്രം ഉപയോഗിക്കുക', 'https://www.soilhealth.dac.gov.in'] },
      4: { en: ['Do not share OTPs here', 'Any login is on the government site only.'], mr: ['येथे OTP शेअर करू नका', 'कोणतेही लॉगिन फक्त सरकारी संकेतस्थळावर करा.'], hi: ['यहाँ OTP साझा न करें', 'कोई भी लॉगिन केवल सरकारी वेबसाइट पर करें।'], ml: ['ഇവിടെ OTP പങ്കിടരുത്', 'ഏത് ലോഗിനും സർക്കാർ സൈറ്റിൽ മാത്രം നടത്തുക.'] },
      5: { en: ['Locate farmer search / print card', 'Portal menus change; use Help on the site.'], mr: ['शेतकरी शोध / कार्ड प्रिंट पर्याय शोधा', 'पोर्टल मेनू बदलतात; संकेतस्थळावरील मदत वापरा.'], hi: ['किसान खोज / कार्ड प्रिंट विकल्प खोजें', 'पोर्टल मेनू बदलते हैं; वेबसाइट पर सहायता लें।'], ml: ['കർഷക തിരയൽ / കാർഡ് പ്രിന്റ് കണ്ടെത്തുക', 'പോർട്ടൽ മെനുകൾ മാറാം; സൈറ്റിലെ സഹായം ഉപയോഗിക്കുക.'] },
      6: { en: ['Provide survey number and farmer details if registering a sample', 'Follow lab instructions for sampling depth and bags.'], mr: ['नमुना नोंदवत असल्यास सर्वेक्षण क्रमांक आणि शेतकरी तपशील द्या', 'नमुना खोली आणि पिशव्यांसाठी प्रयोगशाळेच्या सूचना पाळा.'], hi: ['नमूना पंजीकृत करते समय सर्वे नंबर और किसान विवरण दें', 'नमूने की गहराई और थैलियों के लिए प्रयोगशाला के निर्देशों का पालन करें।'], ml: ['സാമ്പിൾ രജിസ്റ്റർ ചെയ്യുമ്പോൾ സർവേ നമ്പറും കർഷക വിവരങ്ങളും നൽകുക', 'സാമ്പിൾ ആഴവും ബാഗുകളും സംബന്ധിച്ച ലാബ് നിർദേശങ്ങൾ പാലിക്കുക.'] },
      7: { en: ['No document upload is required in this app', 'Physical soil sample is submitted to the designated lab.'], mr: ['या ॲपमध्ये कागदपत्रे अपलोड करण्याची गरज नाही', 'भौतिक मातीचा नमुना नियुक्त प्रयोगशाळेत द्या.'], hi: ['इस ऐप में दस्तावेज़ अपलोड की आवश्यकता नहीं है', 'भौतिक मिट्टी का नमूना निर्धारित प्रयोगशाला में जमा करें।'], ml: ['ഈ ആപ്പിൽ രേഖകൾ അപ്‌ലോഡ് ചെയ്യേണ്ടതില്ല', 'ഭൗതിക മണ്ണ് സാമ്പിൾ നിശ്ചിത ലാബിൽ സമർപ്പിക്കുക.'] },
      8: { en: ['Wait for lab results', 'Recommendations appear on the card after testing.'], mr: ['प्रयोगशाळेच्या निकालांची प्रतीक्षा करा', 'तपासणीनंतर शिफारशी कार्डवर दिसतात.'], hi: ['प्रयोगशाला के परिणाम की प्रतीक्षा करें', 'जाँच के बाद सिफारिशें कार्ड पर दिखाई देती हैं।'], ml: ['ലാബ് ഫലങ്ങൾക്കായി കാത്തിരിക്കുക', 'പരിശോധനയ്ക്ക് ശേഷം ശുപാർശകൾ കാർഡിൽ കാണിക്കും.'] },
      9: { en: ['Download or collect the card', 'Print from the portal if available.'], mr: ['कार्ड डाउनलोड करा किंवा घ्या', 'उपलब्ध असल्यास पोर्टलवरून प्रिंट करा.'], hi: ['कार्ड डाउनलोड या प्राप्त करें', 'उपलब्ध होने पर पोर्टल से प्रिंट करें।'], ml: ['കാർഡ് ഡൗൺലോഡ് ചെയ്യുക അല്ലെങ്കിൽ വാങ്ങുക', 'ലഭ്യമെങ്കിൽ പോർട്ടലിൽ നിന്ന് പ്രിന്റ് എടുക്കുക.'] },
      10: { en: ['Follow fertilizer advice with local extension', 'The card is advisory. Confirm doses with a local officer for your crop.'], mr: ['स्थानिक विस्तार अधिकाऱ्याच्या मदतीने खतांचा सल्ला पाळा', 'कार्ड सल्लागार आहे. आपल्या पिकासाठी मात्रा स्थानिक अधिकाऱ्याकडून निश्चित करा.'], hi: ['स्थानीय विस्तार अधिकारी की सहायता से उर्वरक सलाह अपनाएँ', 'कार्ड सलाहकारी है। अपनी फसल के लिए मात्रा स्थानीय अधिकारी से पक्का करें।'], ml: ['പ്രാദേശിക വിപുലീകരണ ഉദ്യോഗസ്ഥന്റെ സഹായത്തോടെ വള നിർദേശം പാലിക്കുക', 'കാർഡ് ഉപദേശപരമാണ്. നിങ്ങളുടെ വിളയ്ക്കുള്ള അളവ് പ്രാദേശിക ഉദ്യോഗസ്ഥനോട് സ്ഥിരീകരിക്കുക.'] }
    },
    'myscheme-directory': {
      1: { en: ['Use myScheme only as a directory', 'It does not replace PM-KISAN, PMFBY, or MahaDBT applications.'], mr: ['myScheme ഒരു निर्देशिका म्हणूनच वापरा', 'हे PM-KISAN, PMFBY किंवा MahaDBT अर्जांची जागा घेत नाही.'], hi: ['myScheme का उपयोग केवल निर्देशिका के रूप में करें', 'यह PM-KISAN, PMFBY या MahaDBT आवेदन का विकल्प नहीं है।'], ml: ['myScheme ഒരു ഡയറക്ടറിയായി മാത്രം ഉപയോഗിക്കുക', 'ഇത് PM-KISAN, PMFBY അല്ലെങ്കിൽ MahaDBT അപേക്ഷകൾക്ക് പകരമല്ല.'] },
      2: { en: ['Search agriculture / farmer filters', 'Apply filters for your state.'], mr: ['कृषी / शेतकरी फिल्टर शोधा', 'आपल्या राज्यासाठी फिल्टर लागू करा.'], hi: ['कृषि / किसान फ़िल्टर खोजें', 'अपने राज्य के लिए फ़िल्टर लागू करें।'], ml: ['കൃഷി / കർഷക ഫിൽട്ടറുകൾ തിരയുക', 'നിങ്ങളുടെ സംസ്ഥാനത്തിനുള്ള ഫിൽട്ടറുകൾ പ്രയോഗിക്കുക.'] },
      3: { en: ['Open https://www.myscheme.gov.in', 'Official Government of India directory.'], mr: ['https://www.myscheme.gov.in उघडा', 'भारत सरकारची अधिकृत निर्देशिका.'], hi: ['https://www.myscheme.gov.in खोलें', 'भारत सरकार की आधिकारिक निर्देशिका।'], ml: ['https://www.myscheme.gov.in തുറക്കുക', 'ഇന്ത്യാ സർക്കാരിന്റെ ഔദ്യോഗിക ഡയറക്ടറി.'] },
      4: { en: ['No password should be entered in AI-KrushiMitra', 'If myScheme asks you to sign in, do it there.'], mr: ['AI-KrushiMitra मध्ये पासवर्ड टाकू नका', 'myScheme ने साइन इन मागितल्यास तेथेच करा.'], hi: ['AI-KrushiMitra में पासवर्ड दर्ज न करें', 'myScheme साइन इन माँगे तो वहीं करें।'], ml: ['AI-KrushiMitra-ൽ പാസ്‌വേഡ് നൽകരുത്', 'myScheme സൈൻ ഇൻ ആവശ്യപ്പെട്ടാൽ അവിടെ തന്നെ ചെയ്യുക.'] },
      5: { en: ['Open the scheme detail on myScheme', 'Then click through to the implementing department URL.'], mr: ['myScheme वर योजना तपशील उघडा', 'त्यानंतर अंमलबजावणी विभागाच्या URL वर जा.'], hi: ['myScheme पर योजना विवरण खोलें', 'फिर कार्यान्वयन विभाग के URL पर जाएँ।'], ml: ['myScheme-ൽ പദ്ധതി വിശദാംശങ്ങൾ തുറക്കുക', 'തുടർന്ന് നടപ്പാക്കുന്ന വകുപ്പിന്റെ URL-ലേക്ക് പോകുക.'] },
      6: { en: ['Read eligibility on the implementing site', 'Prefer the department PDF/GR.'], mr: ['अंमलबजावणी करणाऱ्या संकेतस्थळावरील पात्रता वाचा', 'विभागाचा PDF/GR प्राधान्याने पहा.'], hi: ['कार्यान्वयन वेबसाइट पर पात्रता पढ़ें', 'विभाग के PDF/GR को प्राथमिकता दें।'], ml: ['നടപ്പാക്കുന്ന സൈറ്റിലെ അർഹത വായിക്കുക', 'വകുപ്പിന്റെ PDF/GR-ന് മുൻഗണന നൽകുക.'] },
      7: { en: ['Apply only on the implementing portal', 'PM-KISAN, PMFBY, MahaDBT, banks, etc.'], mr: ['फक्त अंमलबजावणी पोर्टलवर अर्ज करा', 'PM-KISAN, PMFBY, MahaDBT, बँका इत्यादी.'], hi: ['केवल कार्यान्वयन पोर्टल पर आवेदन करें', 'PM-KISAN, PMFBY, MahaDBT, बैंक आदि।'], ml: ['നടപ്പാക്കൽ പോർട്ടലിൽ മാത്രം അപേക്ഷിക്കുക', 'PM-KISAN, PMFBY, MahaDBT, ബാങ്കുകൾ തുടങ്ങിയവ.'] },
      8: { en: ['Submit on that official portal', 'Not in this app.'], mr: ['त्या अधिकृत पोर्टलवर सबमिट करा', 'या ॲपमध्ये नाही.'], hi: ['उस आधिकारिक पोर्टल पर सबमिट करें', 'इस ऐप में नहीं।'], ml: ['ആ ഔദ്യോഗിക പോർട്ടലിൽ സമർപ്പിക്കുക', 'ഈ ആപ്പിൽ അല്ല.'] },
      9: { en: ["Save that portal's acknowledgement", 'myScheme may not store your application.'], mr: ['त्या पोर्टलची पोचपावती जतन करा', 'myScheme तुमचा अर्ज जतन करेलच असे नाही.'], hi: ['उस पोर्टल की पावती सुरक्षित रखें', 'myScheme आपका आवेदन संग्रहीत नहीं कर सकता है।'], ml: ['ആ പോർട്ടലിന്റെ സ്വീകാര്യപത്രം സംരക്ഷിക്കുക', 'myScheme നിങ്ങളുടെ അപേക്ഷ സംഭരിക്കണമെന്നില്ല.'] },
      10: { en: ['Follow up with the implementing department', 'Use the status tool of the scheme you applied to.'], mr: ['अंमलबजावणी विभागाशी पाठपुरावा करा', 'ज्या योजनेसाठी अर्ज केला तिचे स्थिती साधन वापरा.'], hi: ['कार्यान्वयन विभाग से संपर्क करें', 'जिस योजना के लिए आवेदन किया है उसका स्थिति उपकरण उपयोग करें।'], ml: ['നടപ്പാക്കുന്ന വകുപ്പുമായി പിന്തുടരുക', 'അപേക്ഷിച്ച പദ്ധതിയുടെ സ്റ്റാറ്റസ് ഉപകരണം ഉപയോഗിക്കുക.'] }
    }
  }
}

const localized = (map, value, language, fallback = value) =>
  map[value]?.[language] || (language === 'en' ? map[value]?.en || fallback : fallback)

const localizedUnavailable = {
  mr: 'या योजनेसाठी तपशील अधिकृत पोर्टलवरील सध्याच्या मार्गदर्शक तत्त्वांनुसार तपासा.',
  hi: 'इस योजना का विवरण आधिकारिक पोर्टल के वर्तमान दिशानिर्देशों के अनुसार जाँचें।',
  ml: 'ഈ പദ്ധതിയുടെ വിശദാംശങ്ങൾ ഔദ്യോഗിക പോർട്ടലിലെ നിലവിലെ മാർഗനിർദേശങ്ങൾ അനുസരിച്ച് പരിശോധിക്കുക.'
}

const localizedDocumentName = (document, language) => {
  const name = String(document?.name || '').toLowerCase()
  const labels = {
    aadhaar: { mr: 'आधार', hi: 'आधार', ml: 'ആധാർ' },
    identity: { mr: 'ओळखपत्र', hi: 'पहचान प्रमाण', ml: 'തിരിച്ചറിയൽ രേഖ' },
    land: { mr: 'जमीन अभिलेख', hi: 'भूमि अभिलेख', ml: 'ഭൂമി രേഖ' },
    passbook: { mr: 'बँक पासबुक / खाते तपशील', hi: 'बैंक पासबुक / खाते का विवरण', ml: 'ബാങ്ക് പാസ്‌ബുക്ക് / അക്കൗണ്ട് വിവരങ്ങൾ' },
    cheque: { mr: 'रद्द केलेला धनादेश', hi: 'रद्द किया हुआ चेक', ml: 'റദ്ദാക്കിയ ചെക്ക്' },
    photo: { mr: 'छायाचित्र', hi: 'फोटो', ml: 'ഫോട്ടോ' },
    quotation: { mr: 'विक्रेत्याचे कोटेशन', hi: 'विक्रेता कोटेशन', ml: 'വിൽപ്പനക്കാരന്റെ ക്വട്ടേഷൻ' },
    electricity: { mr: 'वीज जोडणी तपशील', hi: 'बिजली कनेक्शन का विवरण', ml: 'വൈദ്യുതി കണക്ഷൻ വിവരങ്ങൾ' },
    water: { mr: 'पाणी स्रोताचा पुरावा', hi: 'जल स्रोत का प्रमाण', ml: 'ജലസ്രോതസ്സിന്റെ തെളിവ്' },
    crop: { mr: 'पीक तपशील', hi: 'फसल विवरण', ml: 'വിള വിവരങ്ങൾ' }
  }
  const key = Object.keys(labels).find(candidate => name.includes(candidate))
  return key ? labels[key][language] : localizedUnavailable[language]
}

const localizedStepLabel = (step, language) => {
  const n = Number(step?.step)
  const labels = {
    1: { mr: 'पात्रता तपासा', hi: 'पात्रता जाँचें', ml: 'അർഹത പരിശോധിക്കുക' },
    2: { mr: 'कागदपत्रे गोळा करा', hi: 'दस्तावेज़ एकत्र करें', ml: 'രേഖകൾ ശേഖരിക്കുക' },
    3: { mr: 'अधिकृत पोर्टल उघडा', hi: 'आधिकारिक पोर्टल खोलें', ml: 'ഔദ്യോഗിക പോർട്ടൽ തുറക്കുക' },
    4: { mr: 'सरकारी संकेतस्थळावर नोंदणी करा', hi: 'सरकारी वेबसाइट पर पंजीकरण करें', ml: 'സർക്കാർ വെബ്‌സൈറ്റിൽ രജിസ്റ്റർ ചെയ്യുക' },
    5: { mr: 'अर्जाचा फॉर्म शोधा', hi: 'आवेदन फॉर्म खोजें', ml: 'അപേക്ഷാ ഫോം കണ്ടെത്തുക' },
    6: { mr: 'तपशील भरा', hi: 'विवरण दर्ज करें', ml: 'വിവരങ്ങൾ നൽകുക' },
    7: { mr: 'कागदपत्रे अपलोड करा', hi: 'दस्तावेज़ अपलोड करें', ml: 'രേഖകൾ അപ്‌ലോഡ് ചെയ്യുക' },
    8: { mr: 'तपासून सबमिट करा', hi: 'समीक्षा करके सबमिट करें', ml: 'പരിശോധിച്ച് സമർപ്പിക്കുക' },
    9: { mr: 'पोचपावती जतन करा', hi: 'पावती सुरक्षित रखें', ml: 'സ്വീകാര്യപത്രം സംരക്ഷിക്കുക' },
    10: { mr: 'स्थिती तपासा', hi: 'स्थिति जाँचें', ml: 'നില പരിശോധിക്കുക' }
  }
  return labels[n]?.[language] || localizedUnavailable[language]
}

export const localizeSchemeName = (scheme, language) =>
  schemeNames[scheme?.id]?.[language]
  || (language === 'mr' && scheme?.official_name_mr)
  || (language === 'hi' && scheme?.official_name_hi)
  || schemeNames[scheme?.id]?.en
  || (language === 'en' ? scheme?.official_name : localizedUnavailable[language])
  || ''

export const localizeGovernmentLevel = (value, language) =>
  localized(levelLabels, value, language, language === 'en' ? value : localizedUnavailable[language])

export const localizeDocumentStatus = (value, language) =>
  localized(documentStatusLabels, value, language, value)

export const localizeDepartment = (value, language) =>
  localized(departmentLabels, value, language, language === 'en' ? value : localizedUnavailable[language])

export const localizeSchemeDescription = (scheme, language) =>
  schemeDescriptions[scheme?.id]?.[language]
  || scheme?.[`benefits_summary_${language}`]
  || (language === 'en' ? scheme?.benefits_summary : localizedUnavailable[language])

export const localizeDocument = (schemeId, document, language) => {
  const translated = documentTranslations[schemeId]?.[document?.id]?.[language]
  if (!translated && language !== 'en') {
    return { name: localizedDocumentName(document, language), why: localizedUnavailable[language] }
  }
  return {
    name: translated?.[0] || document?.name || '',
    why: translated?.[1] || document?.why || ''
  }
}

export const localizeApplicationStep = (schemeId, step, language) => {
  const translated = stepTranslations[schemeId]?.[step?.step]?.[language]
  if (!translated && language !== 'en') {
    return { title: localizedStepLabel(step, language), detail: localizedUnavailable[language] }
  }
  return {
    title: translated?.[0] || step?.title || '',
    detail: translated?.[1] || step?.detail || ''
  }
}

const sourceTranslations = {
    'soil-health-card': {
      en: 'Official Soil Health Card portal of DAC&FW.',
      mr: 'DAC&FW चे अधिकृत मृदा आरोग्य पत्रिका पोर्टल.',
      hi: 'DAC&FW का आधिकारिक मृदा स्वास्थ्य कार्ड पोर्टल।',
      ml: 'DAC&FW-യുടെ ഔദ്യോഗിക മണ്ണിന്റെ ആരോഗ്യ കാർഡ് പോർട്ടൽ.'
    },
    'myscheme-directory': {
      en: 'Included so farmers have an official search tool when a scheme is missing from this curated list.',
      mr: 'या निवडक यादीत योजना नसल्यास शेतकऱ्यांकडे अधिकृत शोध साधन असावे म्हणून समाविष्ट केले आहे.',
      hi: 'इस चयनित सूची में योजना न होने पर किसानों के पास आधिकारिक खोज उपकरण रहे, इसलिए इसे शामिल किया गया है।',
      ml: 'ഈ തിരഞ്ഞെടുത്ത പട്ടികയിൽ പദ്ധതി ഇല്ലാത്തപ്പോൾ കർഷകർക്ക് ഔദ്യോഗിക തിരയൽ ഉപകരണം ലഭിക്കാനാണ് ഇത് ഉൾപ്പെടുത്തിയിരിക്കുന്നത്.'
    },
    'pm-kisan': {
      en: 'Facts taken from the official PM-KISAN portal (pmkisan.gov.in). Final eligibility is decided by the government, not this app.',
      mr: 'अधिकृत PM-KISAN पोर्टल (pmkisan.gov.in) वरील माहिती. अंतिम पात्रता सरकार ठरवते, हे ॲप नाही.',
      hi: 'तथ्य आधिकारिक PM-KISAN पोर्टल (pmkisan.gov.in) से लिए गए हैं। अंतिम पात्रता सरकार तय करती है, यह ऐप नहीं।',
      ml: 'ഔദ്യോഗിക PM-KISAN പോർട്ടലിൽ (pmkisan.gov.in) നിന്നുള്ള വിവരങ്ങളാണിത്. അന്തിമ അർഹത സർക്കാർ തീരുമാനിക്കും, ഈ ആപ്പ് അല്ല.'
    }
  }

  const deadlineTranslations = {
    'soil-health-card': {
      en: 'Sampling is periodic, not a farmer lottery with a single deadline.',
      mr: 'नमुना संकलन कालावधीने होते; शेतकऱ्यांसाठी एकच अंतिम तारीख नसते.',
      hi: 'नमूना लेना समय-समय पर होता है; किसानों के लिए एक ही अंतिम समय-सीमा नहीं है।',
      ml: 'സാമ്പിൾ ശേഖരണം കാലാനുസൃതമാണ്; കർഷകർക്ക് ഒരൊറ്റ അവസാന തീയതിയില്ല.'
    },
    'myscheme-directory': {
      en: 'Not an application scheme.',
      mr: 'ही अर्ज करण्याची योजना नाही.',
      hi: 'यह आवेदन योजना नहीं है।',
      ml: 'ഇത് അപേക്ഷാ പദ്ധതിയല്ല.'
    },
    'pm-kisan': {
      en: 'No single national application deadline. Instalments follow Government of India release calendar.',
      mr: 'देशभरासाठी एकच अर्जाची अंतिम तारीख नाही. हप्ते भारत सरकारच्या वितरण दिनदर्शिकेनुसार दिले जातात.',
      hi: 'देशभर में आवेदन की कोई एक अंतिम समय-सीमा नहीं है। किस्तें भारत सरकार के जारी करने के कैलेंडर के अनुसार होती हैं।',
      ml: 'രാജ്യവ്യാപകമായി ഒരൊറ്റ അപേക്ഷാ അവസാന തീയതിയില്ല. ഗഡുക്കൾ കേന്ദ്ര സർക്കാരിന്റെ വിതരണ കലണ്ടർ അനുസരിച്ചാണ്.'
    }
  }

export const localizeSource = (scheme, language) =>
    sourceTranslations[scheme?.id]?.[language]
    || (language === 'en' ? scheme?.source_notes || '' : localizedUnavailable[language])

export const localizeDeadline = (scheme, language) =>
    deadlineTranslations[scheme?.id]?.[language]
    || (language === 'en' ? scheme?.deadline_note || '' : localizedUnavailable[language])

const exactTextTranslations = {
  'Scheme is listed as central / all-India.': {
    en: 'Scheme is listed as central / all-India.',
    mr: 'ही योजना केंद्र / संपूर्ण भारतासाठी सूचीबद्ध आहे.',
    hi: 'यह योजना केंद्र / पूरे भारत के लिए सूचीबद्ध है।',
    ml: 'ഈ പദ്ധതി കേന്ദ്ര / ഇന്ത്യ മുഴുവൻ ബാധകമായി പട്ടികപ്പെടുത്തിയിരിക്കുന്നു.'
  },
  'This is an official directory, not a benefit. Use it to find implementing portals.': {
    en: 'This is an official directory, not a benefit. Use it to find implementing portals.',
    mr: 'ही अधिकृत निर्देशिका आहे, लाभ योजना नाही. अंमलबजावणी करणारी पोर्टल्स शोधण्यासाठी तिचा वापर करा.',
    hi: 'यह लाभ नहीं, बल्कि एक आधिकारिक निर्देशिका है। कार्यान्वयन पोर्टल खोजने के लिए इसका उपयोग करें।',
    ml: 'ഇത് ഒരു ആനുകൂല്യമല്ല, ഔദ്യോഗിക ഡയറക്ടറിയാണ്. നടപ്പാക്കൽ പോർട്ടലുകൾ കണ്ടെത്താൻ ഇത് ഉപയോഗിക്കുക.'
  },
  'Land tenure': {
    en: 'Land tenure',
    mr: 'जमिनीचा हक्क',
    hi: 'भूमि स्वामित्व स्थिति',
    ml: 'ഭൂമി കൈവശാവകാശം'
  }
}

export const localizeMatchText = (text, language) => {
  if (!text) return text
  if (exactTextTranslations[text]?.[language]) return exactTextTranslations[text][language]
  const acres = text.match(/^Landholding of about ([0-9.]+) acres is on the farmer profile\.$/)
  if (acres) {
    const n = acres[1]
    return {
      en: `Landholding of about ${n} acres is on the farmer profile.`,
      mr: `शेतकरी प्रोफाइलमध्ये सुमारे ${n} एकर जमीन आहे.`,
      hi: `किसान प्रोफ़ाइल में लगभग ${n} एकड़ भूमि दर्ज है।`,
      ml: `കർഷകന്റെ പ്രൊഫൈലിൽ ഏകദേശം ${n} ഏക്കർ ഭൂമിയുണ്ട്.`
    }[language]
  }
  const profileAcres = text.match(/^Landholding on profile: about ([0-9.]+) acres \(not always required for this scheme\)\.$/)
  if (profileAcres) {
    const n = profileAcres[1]
    return {
      en: `Landholding on profile: about ${n} acres (not always required for this scheme).`,
      mr: `प्रोफाइलवरील जमीनधारणा सुमारे ${n} एकर आहे (या योजनेसाठी नेहमी आवश्यक नाही).`,
      hi: `प्रोफ़ाइल में लगभग ${n} एकड़ भूमि है (इस योजना के लिए हमेशा आवश्यक नहीं)।`,
      ml: `പ്രൊഫൈലിൽ ഏകദേശം ${n} ഏക്കർ ഭൂമിയുണ്ട് (ഈ പദ്ധതിക്ക് എല്ലായ്പ്പോഴും ആവശ്യമില്ല).`
    }[language]
  }
  const crop = text.match(/^Profile crop is '([^']+)'\. Confirm it is notified for your village this season\.$/)
  if (crop) {
    return {
      en: text,
      mr: `प्रोफाइलवरील पीक '${crop[1]}' आहे. या हंगामात ते तुमच्या गावासाठी अधिसूचित आहे याची खात्री करा.`,
      hi: `प्रोफ़ाइल की फसल '${crop[1]}' है। सुनिश्चित करें कि यह इस मौसम में आपके गाँव के लिए अधिसूचित है।`,
      ml: `പ്രൊഫൈലിലെ വിള '${crop[1]}' ആണ്. ഈ സീസണിൽ നിങ്ങളുടെ ഗ്രാമത്തിന് ഇത് വിജ്ഞാപനം ചെയ്തിട്ടുണ്ടെന്ന് ഉറപ്പാക്കുക.`
    }[language]
  }
  const irrigation = text.match(/^Irrigation method '([^']+)' is relevant to this scheme\.$/)
  if (irrigation) {
    return {
      en: text,
      mr: `सिंचन पद्धत '${irrigation[1]}' या योजनेसाठी संबंधित आहे.`,
      hi: `सिंचाई विधि '${irrigation[1]}' इस योजना के लिए प्रासंगिक है।`,
      ml: `ജലസേചന രീതി '${irrigation[1]}' ഈ പദ്ധതിക്ക് പ്രസക്തമാണ്.`
    }[language]
  }
  if (text === 'Gender is optional here; fill it only if a scheme guideline uses it.') {
    return {
      en: text,
      mr: 'येथे लिंग ऐच्छिक आहे; योजनेच्या मार्गदर्शक तत्त्वांमध्ये आवश्यक असल्यासच ते भरा.',
      hi: 'यहाँ लिंग वैकल्पिक है; योजना दिशानिर्देश में उपयोग होने पर ही भरें।',
      ml: 'ഇവിടെ ലിംഗം ഐച്ഛികമാണ്; പദ്ധതി മാർഗനിർദേശത്തിൽ ആവശ്യപ്പെട്ടാൽ മാത്രം നൽകുക.'
    }[language]
  }
  if (text === 'District is not provided; some schemes are notified at district level.') {
    return {
      en: text,
      mr: 'जिल्हा दिलेला नाही; काही योजना जिल्हास्तरावर अधिसूचित केल्या जातात.',
      hi: 'जिला उपलब्ध नहीं है; कुछ योजनाएँ जिला स्तर पर अधिसूचित होती हैं।',
      ml: 'ജില്ല നൽകിയിട്ടില്ല; ചില പദ്ധതികൾ ജില്ലാതലത്തിൽ വിജ്ഞാപനം ചെയ്യപ്പെടുന്നു.'
    }[language]
  }
  if (text === 'State of residence / farm is not provided.') {
    return {
      en: text,
      mr: 'निवासाचे / शेताचे राज्य दिलेले नाही.',
      hi: 'निवास / खेत का राज्य उपलब्ध नहीं है।',
      ml: 'താമസിക്കുന്ന / കൃഷിയിടത്തിന്റെ സംസ്ഥാനം നൽകിയിട്ടില്ല.'
    }[language]
  }
  const field = exactTextTranslations[text]
  return field?.[language] || (language === 'en' ? text : localizedUnavailable[language])
}

export const localizeFieldName = (field, language) => ({
  state: { en: 'State', mr: 'राज्य', hi: 'राज्य', ml: 'സംസ്ഥാനം' },
  district: { en: 'District', mr: 'जिल्हा', hi: 'जिला', ml: 'ജില്ല' },
  landholding: { en: 'Landholding', mr: 'जमीनधारणा', hi: 'भूमि धारण', ml: 'ഭൂമിയുടെ വിസ്തീർണം' },
  land_tenure: { en: 'Land tenure', mr: 'जमिनीचा हक्क', hi: 'भूमि स्वामित्व स्थिति', ml: 'ഭൂമി കൈവശാവകാശം' },
  crop: { en: 'Crop', mr: 'पीक', hi: 'फसल', ml: 'വിള' },
  irrigation: { en: 'Irrigation', mr: 'सिंचन', hi: 'सिंचाई', ml: 'ജലസേചനം' },
  farmer_category: { en: 'Farmer category', mr: 'शेतकरी श्रेणी', hi: 'किसान श्रेणी', ml: 'കർഷക വിഭാഗം' }
}[field]?.[language] || (language === 'en' ? field : localizedUnavailable[language]))

export const localizeSchemeCrop = (value, language) => ({
  all: { en: 'All Crops', mr: 'सर्व पिके', hi: 'सभी फसलें', ml: 'എല്ലാ വിളകളും' },
  notified: { en: 'Notified Crops', mr: 'अधिसूचित पिके', hi: 'अधिसूचित फसलें', ml: 'വിജ്ഞാപനം ചെയ്ത വിളകൾ' },
  corn: { en: 'Corn (Maize)', mr: 'मका', hi: 'मक्का', ml: 'ചോളം' },
  maize: { en: 'Corn (Maize)', mr: 'मका', hi: 'मक्का', ml: 'ചോളം' },
  rainfed: { en: 'Rainfed', mr: 'पावसावर आधारित', hi: 'वर्षा आधारित', ml: 'മഴയെ ആശ്രയിച്ചുള്ള' }
}[String(value).toLowerCase()]?.[language] || (language === 'en' ? value : localizedUnavailable[language]))

export const localizeSchemeCategory = (value, language) =>
  dropdownCategoryLabels[String(value).toLowerCase()]?.[language]
  || (language === 'en' ? value : localizedUnavailable[language])

const dropdownCategoryLabels = {
  farmer_support: { en: 'Farmer Support', mr: 'शेतकरी सहाय्य', hi: 'किसान सहायता', ml: 'കർഷക സഹായം' },
  income_support: { en: 'Income Support', mr: 'उत्पन्न सहाय्य', hi: 'आय सहायता', ml: 'വരുമാന സഹായം' },
  crop_insurance: { en: 'Crop Insurance', mr: 'पीक विमा', hi: 'फसल बीमा', ml: 'വിള ഇൻഷുറൻസ്' },
  credit: { en: 'Credit / Loans', mr: 'कर्ज / पत', hi: 'ऋण / क्रेडिट', ml: 'വായ്പ / ക്രെഡിറ്റ്' },
  irrigation: { en: 'Irrigation', mr: 'सिंचन', hi: 'सिंचाई', ml: 'ജലസേചനം' },
  infrastructure: { en: 'Infrastructure', mr: 'पायाभूत सुविधा', hi: 'बुनियादी ढाँचा', ml: 'അടിസ്ഥാന സൗകര്യം' },
  subsidy: { en: 'Subsidy', mr: 'अनुदान', hi: 'सब्सिडी', ml: 'സബ്‌സിഡി' },
  advisory: { en: 'Advisory', mr: 'सल्ला', hi: 'सलाह', ml: 'ഉപദേശം' },
  soil: { en: 'Soil', mr: 'माती', hi: 'मृदा', ml: 'മണ്ണ്' },
  energy: { en: 'Energy', mr: 'ऊर्जा', hi: 'ऊर्जा', ml: 'ഊർജം' },
  farm_equipment: { en: 'Farm Equipment', mr: 'शेती उपकरणे', hi: 'कृषि उपकरण', ml: 'കാർഷിക ഉപകരണങ്ങൾ' },
  equipment: { en: 'Farm Equipment', mr: 'शेती उपकरणे', hi: 'कृषि उपकरण', ml: 'കാർഷിക ഉപകരണങ്ങൾ' },
  information: { en: 'Information', mr: 'माहिती', hi: 'जानकारी', ml: 'വിവരം' },
  horticulture: { en: 'Horticulture', mr: 'फलोत्पादन', hi: 'बागवानी', ml: 'തോട്ടകൃഷി' }
}

export const localizeSchemeBenefit = (value, language) => ({
  direct_benefit_transfer: { en: 'Direct Benefit (DBT)', mr: 'थेट लाभ (DBT)', hi: 'प्रत्यक्ष लाभ (DBT)', ml: 'നേരിട്ടുള്ള ആനുകൂല്യം (DBT)' },
  insurance: { en: 'Crop Insurance', mr: 'पीक विमा', hi: 'फसल बीमा', ml: 'വിള ഇൻഷുറൻസ്' },
  credit: { en: 'Credit / Loan', mr: 'कर्ज / पत', hi: 'ऋण / क्रेडिट', ml: 'വായ്പ / ക്രെഡിറ്റ്' },
  subsidy: { en: 'Subsidy', mr: 'अनुदान', hi: 'सब्सिडी', ml: 'സബ്‌സിഡി' },
  infrastructure: { en: 'Infrastructure', mr: 'पायाभूत सुविधा', hi: 'बुनियादी ढाँचा', ml: 'അടിസ്ഥാന സൗകര്യം' },
  advisory: { en: 'Advisory', mr: 'सल्ला', hi: 'सलाह', ml: 'ഉപദേശം' },
  information: { en: 'Information', mr: 'माहिती', hi: 'जानकारी', ml: 'വിവരം' }
}[String(value).toLowerCase()]?.[language] || (language === 'en' ? value : localizedUnavailable[language]))

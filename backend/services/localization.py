from typing import Dict


LANGUAGE_NAMES = {
    "en": "English",
    "mr": "Marathi (मराठी)",
    "hi": "Hindi (हिंदी)",
    "ml": "Malayalam (മലയാളം)",
}

_MESSAGES: Dict[str, Dict[str, str]] = {
    "en": {
        "ai_unavailable": "The AI provider could not be reached. Check the backend network connection and provider status, then retry.",
        "ai_not_configured": "AI chat is not configured on the server. Set GEMINI_API_KEY (or OPENAI_API_KEY) in the backend environment.",
        "ai_auth_error": "The configured AI provider rejected its credentials or model access. Check the backend API key and enabled model, then try again.",
        "ai_rate_limited": "The AI provider is temporarily rate-limiting requests. Please wait a moment and try again.",
        "ai_quota_exceeded": "The Gemini API project quota is exhausted. Check the Google AI usage and billing settings before retrying.",
        "ai_provider_quota_exceeded": "The OpenAI API quota or billing limit was reached. Check OpenAI usage and billing before retrying.",
        "ai_timeout": "The AI provider took too long to respond. Please retry; if this continues, check provider status and backend network access.",
        "ai_dns_error": "The backend could not resolve the AI provider's address. Check DNS and backend network access.",
        "ai_connection_error": "The backend could not connect to the AI provider. Check outbound network access and provider status.",
        "ai_provider_error": "The AI provider returned a server error. Please try again later.",
        "ai_model_unavailable": "The configured AI model is unavailable to this API key. Check the model name and access.",
        "invalid_message": "Message cannot be empty.",
        "message_too_long": "Please keep your message under 8,000 characters.",
        "invalid_language": "Unsupported language. Choose English, Marathi, Hindi, or Malayalam.",
        "invalid_image": "The uploaded file is not a supported image. Please upload a JPG, PNG, or WebP image.",
        "symptoms_unavailable": "No distinct symptoms could be confidently described from the provided image.",
        "image_too_large": "The image exceeds the 10 MB limit. Please choose a smaller image.",
        "image_type_mismatch": "The file contents do not match the selected image type. Upload a valid JPG, PNG, or WebP image.",
        "disease_server_error": "The image could not be analyzed because of a server error. Please retry.",
        "disease_analysis_failed": "Disease analysis could not be completed by the server. Please retry.",
        "disease_result_empty": "Disease analysis returned no result. Please retry with another image.",
        "low_quality": "The image is too unclear for a reliable diagnosis. Upload a well-lit, close-up photo of one leaf.",
        "non_plant": "The image does not appear to show a recognizable plant or crop. Upload a clear close-up photo of a plant.",
        "unsupported_crop": "This crop is not supported by the current disease model. Its prediction was not changed; ask the AI Assistant for general guidance or consult an agricultural expert.",
        "disease_unavailable": "Disease analysis is temporarily unavailable. Please try again later with a clear, close-up photo.",
        "disease_auth_error": "Gemini rejected the configured API key or the key does not have access to the configured vision models. Check GEMINI_API_KEY in backend/.env and enable Gemini API/model access.",
        "disease_quota_error": "The Gemini API project quota is exhausted. Check the Google AI usage and billing settings before retrying.",
        "disease_rate_limited": "Gemini is temporarily rate-limiting requests. Please wait before trying again.",
        "disease_model_error": "The configured Gemini vision models are unavailable to this API key. Check model access and backend model configuration.",
        "disease_model_unavailable": "The trained crop disease model could not be loaded. Check the backend TensorFlow/Keras installation and model files.",
        "disease_provider_unavailable": "The visual analysis provider is temporarily unavailable. The local model could not provide a verified result for this image; please retry later.",
        "disease_configuration_error": "Disease analysis is not configured on this server. Configure the vision provider or restore the trained local model.",
        "disease_processing_error": "The image could not be processed by the disease analysis service. Please retry with a supported image.",
        "weather_unavailable": "Weather service is unavailable. Please try again later.",
        "diagnosis_uncertain": "Crop or disease identification is uncertain. The image does not provide enough reliable evidence. Please upload a clear, well-lit close-up of one leaf or ask a local agricultural expert to confirm.",
        "translation_unavailable": "A reliable translation of this diagnosis is unavailable right now. No translated diagnosis is being shown; please try again later.",
        "translation_quota_unavailable": "Diagnosis translation is unavailable because the configured translation provider reported an exhausted API quota. Check provider usage and billing before retrying.",
    },
    "mr": {
        "ai_unavailable": "AI सहाय्यक तात्पुरता उपलब्ध नाही. कोणतेही उत्तर तयार केलेले नाही; कृपया थोड्या वेळाने पुन्हा प्रयत्न करा.",
        "ai_not_configured": "सर्व्हरवर AI चॅट कॉन्फिगर केलेले नाही. बॅकएंड वातावरणात GEMINI_API_KEY (किंवा OPENAI_API_KEY) सेट करा.",
        "ai_auth_error": "कॉन्फिगर केलेल्या AI सेवेला प्रवेश तपशील किंवा मॉडेल प्रवेश मान्य नाही. बॅकएंडमधील API की आणि उपलब्ध मॉडेल तपासून पुन्हा प्रयत्न करा.",
        "ai_rate_limited": "AI सेवेकडून तात्पुरती विनंती मर्यादा लागू झाली आहे. थोडा वेळ थांबून पुन्हा प्रयत्न करा.",
        "ai_quota_exceeded": "Gemini API प्रकल्पाची कोटा मर्यादा संपली आहे. पुन्हा प्रयत्न करण्यापूर्वी Google AI वापर आणि बिलिंग तपासा.",
        "ai_provider_quota_exceeded": "OpenAI API ची कोटा किंवा बिलिंग मर्यादा गाठली आहे. पुन्हा प्रयत्न करण्यापूर्वी OpenAI वापर आणि बिलिंग तपासा.",
        "ai_timeout": "AI सेवेकडून उत्तर येण्यास खूप वेळ लागला. पुन्हा प्रयत्न करा; समस्या कायम राहिल्यास सेवा स्थिती आणि बॅकएंड नेटवर्क तपासा.",
        "ai_dns_error": "बॅकएंडला AI सेवेचा पत्ता शोधता आला नाही. DNS आणि बॅकएंड नेटवर्क तपासा.",
        "ai_connection_error": "बॅकएंडला AI सेवेशी जोडता आले नाही. बाह्य नेटवर्क प्रवेश आणि सेवा स्थिती तपासा.",
        "ai_provider_error": "AI सेवेकडून सर्व्हर त्रुटी आली. कृपया नंतर पुन्हा प्रयत्न करा.",
        "ai_model_unavailable": "कॉन्फिगर केलेले AI मॉडेल या API कीसाठी उपलब्ध नाही. मॉडेलचे नाव आणि प्रवेश तपासा.",
        "invalid_message": "संदेश रिकामा असू शकत नाही.",
        "message_too_long": "कृपया ८,००० अक्षरांपेक्षा लहान संदेश लिहा.",
        "invalid_language": "ही भाषा समर्थित नाही. इंग्रजी, मराठी, हिंदी किंवा मल्याळम निवडा.",
        "invalid_image": "अपलोड केलेली प्रतिमा समर्थित नाही. कृपया JPG, PNG किंवा WebP प्रतिमा अपलोड करा.",
        "symptoms_unavailable": "दिलेल्या प्रतिमेवरून कोणतीही विशिष्ट लक्षणे खात्रीने सांगता आली नाहीत.",
        "image_too_large": "प्रतिमा १० MB मर्यादेपेक्षा मोठी आहे. कृपया लहान प्रतिमा निवडा.",
        "image_type_mismatch": "फाइलमधील मजकूर निवडलेल्या प्रतिमेच्या प्रकाराशी जुळत नाही. वैध JPG, PNG किंवा WebP प्रतिमा अपलोड करा.",
        "disease_server_error": "सर्व्हरमधील त्रुटीमुळे प्रतिमेचे विश्लेषण करता आले नाही. कृपया पुन्हा प्रयत्न करा.",
        "disease_analysis_failed": "सर्व्हर रोग विश्लेषण पूर्ण करू शकला नाही. कृपया पुन्हा प्रयत्न करा.",
        "disease_result_empty": "रोग विश्लेषणाचा निकाल मिळाला नाही. कृपया दुसरी प्रतिमा वापरून पुन्हा प्रयत्न करा.",
        "low_quality": "विश्वासार्ह निदानासाठी प्रतिमा पुरेशी स्पष्ट नाही. चांगल्या प्रकाशात एका पानाचा जवळून फोटो अपलोड करा.",
        "non_plant": "प्रतिमेत ओळखता येण्याजोगे रोप किंवा पीक दिसत नाही. रोपाचा स्पष्ट जवळून फोटो अपलोड करा.",
        "unsupported_crop": "सध्याच्या रोगनिदान मॉडेलमध्ये या पिकाचा समावेश नाही. त्याची भविष्यवाणी बदललेली नाही; सामान्य मार्गदर्शनासाठी AI सहाय्यकाला विचारा किंवा कृषी तज्ज्ञांचा सल्ला घ्या.",
        "disease_unavailable": "रोग विश्लेषण तात्पुरते उपलब्ध नाही. स्पष्ट, जवळून घेतलेल्या फोटोसह नंतर पुन्हा प्रयत्न करा.",
        "disease_auth_error": "Gemini ने कॉन्फिगर केलेली API की नाकारली आहे किंवा या कीला व्हिजन मॉडेल्सचा प्रवेश नाही. backend/.env मधील GEMINI_API_KEY आणि Gemini API/मॉडेल प्रवेश तपासा.",
        "disease_quota_error": "Gemini API प्रकल्पाची कोटा मर्यादा संपली आहे. पुन्हा प्रयत्न करण्यापूर्वी Google AI वापर आणि बिलिंग तपासा.",
        "disease_rate_limited": "Gemini कडून तात्पुरती विनंती मर्यादा लागू झाली आहे. कृपया थांबून पुन्हा प्रयत्न करा.",
        "disease_model_error": "कॉन्फिगर केलेली Gemini व्हिजन मॉडेल्स या API कीसाठी उपलब्ध नाहीत. मॉडेल प्रवेश आणि बॅकएंड कॉन्फिगरेशन तपासा.",
        "disease_model_unavailable": "प्रशिक्षित पीक रोग मॉडेल लोड करता आले नाही. बॅकएंडमधील TensorFlow/Keras स्थापना आणि मॉडेल फाइल्स तपासा.",
        "disease_provider_unavailable": "दृश्य विश्लेषण सेवा तात्पुरती उपलब्ध नाही. या प्रतिमेसाठी स्थानिक मॉडेल खात्रीशीर निकाल देऊ शकले नाही; नंतर पुन्हा प्रयत्न करा.",
        "disease_configuration_error": "या सर्व्हरवर रोग विश्लेषण कॉन्फिगर केलेले नाही. व्हिजन सेवा कॉन्फिगर करा किंवा प्रशिक्षित स्थानिक मॉडेल पुनर्स्थापित करा.",
        "disease_processing_error": "रोग विश्लेषण सेवेला प्रतिमा प्रक्रिया करता आली नाही. समर्थित प्रतिमेसह पुन्हा प्रयत्न करा.",
        "weather_unavailable": "हवामान सेवा उपलब्ध नाही. कृपया नंतर पुन्हा प्रयत्न करा.",
        "diagnosis_uncertain": "पीक किंवा रोगाची ओळख निश्चित नाही. प्रतिमेत पुरेसा विश्वासार्ह पुरावा नाही. एका पानाचा स्पष्ट, चांगल्या प्रकाशातील जवळून फोटो अपलोड करा किंवा स्थानिक कृषी तज्ज्ञांकडून खात्री करा.",
        "translation_unavailable": "या निदानाचा विश्वसनीय अनुवाद सध्या उपलब्ध नाही. अनुवादित निदान दाखवले जात नाही; कृपया नंतर पुन्हा प्रयत्न करा.",
        "translation_quota_unavailable": "कॉन्फिगर केलेल्या अनुवाद सेवेची API कोटा मर्यादा संपल्यामुळे रोगनिदानाचा अनुवाद उपलब्ध नाही. पुन्हा प्रयत्न करण्यापूर्वी सेवा वापर आणि बिलिंग तपासा.",
    },
    "hi": {
        "ai_unavailable": "AI सहायक अस्थायी रूप से उपलब्ध नहीं है। कोई उत्तर तैयार नहीं किया गया; कृपया थोड़ी देर बाद फिर प्रयास करें।",
        "ai_not_configured": "सर्वर पर AI चैट कॉन्फ़िगर नहीं है। बैकएंड वातावरण में GEMINI_API_KEY (या OPENAI_API_KEY) सेट करें।",
        "ai_auth_error": "कॉन्फ़िगर की गई AI सेवा ने अपनी जानकारी या मॉडल पहुँच अस्वीकार कर दी। बैकएंड API कुंजी और उपलब्ध मॉडल जांचकर फिर प्रयास करें।",
        "ai_rate_limited": "AI सेवा अस्थायी रूप से अनुरोध सीमित कर रही है। कृपया थोड़ी देर बाद पुनः प्रयास करें।",
        "ai_quota_exceeded": "Gemini API प्रोजेक्ट का कोटा समाप्त हो गया है। पुनः प्रयास करने से पहले Google AI उपयोग और बिलिंग जाँचें।",
        "ai_provider_quota_exceeded": "OpenAI API की कोटा या बिलिंग सीमा पूरी हो गई है। फिर से प्रयास करने से पहले OpenAI उपयोग और बिलिंग जांचें।",
        "ai_timeout": "AI सेवा से उत्तर आने में बहुत समय लगा। फिर प्रयास करें; समस्या बनी रहे तो सेवा की स्थिति और बैकएंड नेटवर्क जांचें।",
        "ai_dns_error": "बैकएंड AI सेवा का पता नहीं खोज सका। DNS और बैकएंड नेटवर्क जांचें।",
        "ai_connection_error": "बैकएंड AI सेवा से जुड़ नहीं सका। बाहरी नेटवर्क पहुँच और सेवा की स्थिति जांचें।",
        "ai_provider_error": "AI सेवा ने सर्वर त्रुटि लौटाई। कृपया बाद में फिर प्रयास करें।",
        "ai_model_unavailable": "कॉन्फ़िगर किया गया AI मॉडल इस API कुंजी के लिए उपलब्ध नहीं है। मॉडल का नाम और पहुँच जांचें।",
        "invalid_message": "संदेश खाली नहीं हो सकता।",
        "message_too_long": "कृपया अपना संदेश 8,000 अक्षरों से छोटा रखें।",
        "invalid_language": "यह भाषा समर्थित नहीं है। अंग्रेज़ी, मराठी, हिंदी या मलयालम चुनें।",
        "invalid_image": "अपलोड की गई छवि समर्थित नहीं है। कृपया JPG, PNG या WebP छवि अपलोड करें।",
        "symptoms_unavailable": "दी गई छवि से किसी विशिष्ट लक्षण की विश्वसनीय रूप से पहचान नहीं हो सकी।",
        "image_too_large": "छवि 10 MB की सीमा से बड़ी है। कृपया छोटी छवि चुनें।",
        "image_type_mismatch": "फ़ाइल की सामग्री चुने गए छवि प्रकार से मेल नहीं खाती। मान्य JPG, PNG या WebP छवि अपलोड करें।",
        "disease_server_error": "सर्वर की त्रुटि के कारण छवि का विश्लेषण नहीं हो सका। कृपया फिर प्रयास करें।",
        "disease_analysis_failed": "सर्वर रोग विश्लेषण पूरा नहीं कर सका। कृपया फिर प्रयास करें।",
        "disease_result_empty": "रोग विश्लेषण का कोई परिणाम नहीं मिला। दूसरी छवि के साथ फिर प्रयास करें।",
        "low_quality": "विश्वसनीय पहचान के लिए छवि पर्याप्त स्पष्ट नहीं है। अच्छी रोशनी में एक पत्ती का नज़दीकी फोटो अपलोड करें।",
        "non_plant": "छवि में पहचानने योग्य पौधा या फसल दिखाई नहीं देती। पौधे का स्पष्ट नज़दीकी फोटो अपलोड करें।",
        "unsupported_crop": "वर्तमान रोग पहचान मॉडल इस फसल का समर्थन नहीं करता। इसकी भविष्यवाणी नहीं बदली गई है; सामान्य मार्गदर्शन के लिए AI सहायक से पूछें या कृषि विशेषज्ञ से सलाह लें।",
        "disease_unavailable": "रोग विश्लेषण अस्थायी रूप से उपलब्ध नहीं है। स्पष्ट, नज़दीकी फोटो के साथ बाद में फिर प्रयास करें।",
        "disease_auth_error": "Gemini ने कॉन्फ़िगर की गई API कुंजी अस्वीकार कर दी है या इस कुंजी को विज़न मॉडल का एक्सेस नहीं है। backend/.env में GEMINI_API_KEY और Gemini API/मॉडल एक्सेस जांचें।",
        "disease_quota_error": "Gemini API प्रोजेक्ट का कोटा समाप्त हो गया है। पुनः प्रयास करने से पहले Google AI उपयोग और बिलिंग जाँचें।",
        "disease_rate_limited": "Gemini अस्थायी रूप से अनुरोध सीमित कर रहा है। कृपया प्रतीक्षा करके फिर प्रयास करें।",
        "disease_model_error": "कॉन्फ़िगर किए गए Gemini विज़न मॉडल इस API कुंजी के लिए उपलब्ध नहीं हैं। मॉडल एक्सेस और बैकएंड कॉन्फ़िगरेशन जांचें।",
        "disease_model_unavailable": "प्रशिक्षित फसल रोग मॉडल लोड नहीं हो सका। बैकएंड TensorFlow/Keras स्थापना और मॉडल फ़ाइलें जांचें।",
        "disease_provider_unavailable": "दृश्य विश्लेषण सेवा अस्थायी रूप से उपलब्ध नहीं है। इस छवि के लिए स्थानीय मॉडल विश्वसनीय परिणाम नहीं दे सका; बाद में फिर प्रयास करें।",
        "disease_configuration_error": "इस सर्वर पर रोग विश्लेषण कॉन्फ़िगर नहीं है। विज़न सेवा कॉन्फ़िगर करें या प्रशिक्षित स्थानीय मॉडल पुनर्स्थापित करें।",
        "disease_processing_error": "रोग विश्लेषण सेवा छवि को संसाधित नहीं कर सकी। कृपया समर्थित छवि के साथ फिर प्रयास करें।",
        "weather_unavailable": "मौसम सेवा उपलब्ध नहीं है। कृपया बाद में फिर प्रयास करें।",
        "diagnosis_uncertain": "फसल या रोग की पहचान निश्चित नहीं है। छवि में पर्याप्त विश्वसनीय प्रमाण नहीं हैं। एक पत्ती का स्पष्ट, अच्छी रोशनी वाला नज़दीकी फोटो अपलोड करें या स्थानीय कृषि विशेषज्ञ से पुष्टि करें।",
        "translation_unavailable": "इस रोग पहचान का विश्वसनीय अनुवाद अभी उपलब्ध नहीं है। अनूदित पहचान नहीं दिखाई जा रही है; कृपया बाद में फिर प्रयास करें।",
        "translation_quota_unavailable": "कॉन्फ़िगर की गई अनुवाद सेवा की API कोटा सीमा समाप्त होने के कारण निदान का अनुवाद उपलब्ध नहीं है। फिर से प्रयास करने से पहले सेवा उपयोग और बिलिंग जांचें।",
    },
    "ml": {
        "ai_unavailable": "AI സഹായി താൽക്കാലികമായി ലഭ്യമല്ല. മറുപടി തയ്യാറാക്കിയിട്ടില്ല; കുറച്ച് കഴിഞ്ഞ് വീണ്ടും ശ്രമിക്കുക.",
        "ai_not_configured": "സെർവറിൽ AI ചാറ്റ് ക്രമീകരിച്ചിട്ടില്ല. ബാക്ക്‌എൻഡ് പരിതസ്ഥിതിയിൽ GEMINI_API_KEY (അല്ലെങ്കിൽ OPENAI_API_KEY) സജ്ജമാക്കുക.",
        "ai_auth_error": "ക്രമീകരിച്ച AI സേവനം ക്രെഡൻഷ്യലുകളോ മോഡൽ പ്രവേശനമോ നിരസിച്ചു. ബാക്ക്‌എൻഡിലെ API കീയും ലഭ്യമായ മോഡലും പരിശോധിച്ച് വീണ്ടും ശ്രമിക്കുക.",
        "ai_rate_limited": "AI സേവനം താൽക്കാലികമായി അഭ്യർത്ഥനകൾ നിയന്ത്രിക്കുന്നു. കുറച്ച് കഴിഞ്ഞ് വീണ്ടും ശ്രമിക്കുക.",
        "ai_quota_exceeded": "Gemini API പ്രോജക്റ്റിന്റെ ക്വോട്ട തീർന്നു. വീണ്ടും ശ്രമിക്കുന്നതിന് മുമ്പ് Google AI ഉപയോഗവും ബില്ലിംഗും പരിശോധിക്കുക.",
        "ai_provider_quota_exceeded": "OpenAI API ക്വോട്ടയോ ബില്ലിംഗ് പരിധിയോ എത്തിയിരിക്കുന്നു. വീണ്ടും ശ്രമിക്കുന്നതിന് മുമ്പ് OpenAI ഉപയോഗവും ബില്ലിംഗും പരിശോധിക്കുക.",
        "ai_timeout": "AI സേവനത്തിൽ നിന്ന് മറുപടി ലഭിക്കാൻ ഏറെ സമയമെടുത്തു. വീണ്ടും ശ്രമിക്കുക; ഇത് തുടരുകയാണെങ്കിൽ സേവന നിലയും ബാക്ക്‌എൻഡ് നെറ്റ്‌വർക്കും പരിശോധിക്കുക.",
        "ai_dns_error": "AI സേവനത്തിന്റെ വിലാസം കണ്ടെത്താനായില്ല. DNS-യും ബാക്ക്‌എൻഡ് നെറ്റ്‌വർക്കും പരിശോധിക്കുക.",
        "ai_connection_error": "ബാക്ക്‌എൻഡിന് AI സേവനവുമായി ബന്ധപ്പെടാനായില്ല. നെറ്റ്‌വർക്ക് പ്രവേശനവും സേവന നിലയും പരിശോധിക്കുക.",
        "ai_provider_error": "AI സേവനം സെർവർ പിശക് നൽകി. പിന്നീട് വീണ്ടും ശ്രമിക്കുക.",
        "ai_model_unavailable": "ക്രമീകരിച്ച AI മോഡൽ ഈ API കീയ്ക്ക് ലഭ്യമല്ല. മോഡലിന്റെ പേരും പ്രവേശനവും പരിശോധിക്കുക.",
        "invalid_message": "സന്ദേശം ശൂന്യമായിരിക്കരുത്.",
        "message_too_long": "സന്ദേശം 8,000 അക്ഷരങ്ങളിൽ താഴെയാക്കുക.",
        "invalid_language": "ഈ ഭാഷ പിന്തുണയ്ക്കുന്നില്ല. ഇംഗ്ലീഷ്, മറാത്തി, ഹിന്ദി, അല്ലെങ്കിൽ മലയാളം തിരഞ്ഞെടുക്കുക.",
        "invalid_image": "അപ്‌ലോഡ് ചെയ്ത ചിത്രം പിന്തുണയ്ക്കുന്നില്ല. JPG, PNG, അല്ലെങ്കിൽ WebP ചിത്രം അപ്‌ലോഡ് ചെയ്യുക.",
        "symptoms_unavailable": "നൽകിയ ചിത്രത്തിൽ നിന്ന് പ്രത്യേക ലക്ഷണങ്ങൾ വിശ്വസനീയമായി വിവരിക്കാനായില്ല.",
        "image_too_large": "ചിത്രം 10 MB പരിധി കവിയുന്നു. ചെറിയ ചിത്രം തിരഞ്ഞെടുക്കുക.",
        "image_type_mismatch": "ഫയലിലെ ഉള്ളടക്കം തിരഞ്ഞെടുത്ത ചിത്രതരവുമായി പൊരുത്തപ്പെടുന്നില്ല. സാധുവായ JPG, PNG, WebP ചിത്രം അപ്‌ലോഡ് ചെയ്യുക.",
        "disease_server_error": "സെർവർ പിശകിനെ തുടർന്ന് ചിത്രം വിശകലനം ചെയ്യാനായില്ല. വീണ്ടും ശ്രമിക്കുക.",
        "disease_analysis_failed": "സെർവറിന് രോഗവിശകലനം പൂർത്തിയാക്കാനായില്ല. വീണ്ടും ശ്രമിക്കുക.",
        "disease_result_empty": "രോഗവിശകലന ഫലം ലഭിച്ചില്ല. മറ്റൊരു ചിത്രം ഉപയോഗിച്ച് വീണ്ടും ശ്രമിക്കുക.",
        "low_quality": "വിശ്വസനീയമായ രോഗനിർണയത്തിന് ചിത്രം വ്യക്തതയുള്ളതല്ല. നല്ല വെളിച്ചത്തിൽ ഒരിലയുടെ അടുത്തുനിന്നുള്ള ചിത്രം അപ്‌ലോഡ് ചെയ്യുക.",
        "non_plant": "ചിത്രത്തിൽ തിരിച്ചറിയാവുന്ന ചെടിയോ വിളയോ കാണുന്നില്ല. ചെടിയുടെ വ്യക്തമായ അടുത്തുനിന്നുള്ള ചിത്രം അപ്‌ലോഡ് ചെയ്യുക.",
        "unsupported_crop": "നിലവിലെ രോഗനിർണയ മോഡൽ ഈ വിളയെ പിന്തുണയ്ക്കുന്നില്ല. പ്രവചനം മാറ്റിയിട്ടില്ല; പൊതുവായ മാർഗനിർദേശത്തിന് AI സഹായിയോട് ചോദിക്കുകയോ കൃഷിവിദഗ്ധനെ സമീപിക്കുകയോ ചെയ്യുക.",
        "disease_unavailable": "രോഗവിശകലനം താൽക്കാലികമായി ലഭ്യമല്ല. വ്യക്തമായ അടുത്തുനിന്നുള്ള ചിത്രം ഉപയോഗിച്ച് പിന്നീട് വീണ്ടും ശ്രമിക്കുക.",
        "disease_auth_error": "ക്രമീകരിച്ച API കീ Gemini നിരസിച്ചു, അല്ലെങ്കിൽ ഈ കീക്ക് വിഷൻ മോഡലുകളിലേക്ക് പ്രവേശനമില്ല. backend/.env-ലെ GEMINI_API_KEY-യും Gemini API/മോഡൽ പ്രവേശനവും പരിശോധിക്കുക.",
        "disease_quota_error": "Gemini API പ്രോജക്റ്റിന്റെ ക്വോട്ട തീർന്നു. വീണ്ടും ശ്രമിക്കുന്നതിന് മുമ്പ് Google AI ഉപയോഗവും ബില്ലിംഗും പരിശോധിക്കുക.",
        "disease_rate_limited": "Gemini താൽക്കാലികമായി അഭ്യർത്ഥനകൾ നിയന്ത്രിക്കുന്നു. കാത്തிருந்து വീണ്ടും ശ്രമിക്കുക.",
        "disease_model_error": "ക്രമീകരിച്ച Gemini വിഷൻ മോഡലുകൾ ഈ API കീയ്ക്ക് ലഭ്യമല്ല. മോഡൽ പ്രവേശനവും ബാക്ക്‌എൻഡ് ക്രമീകരണവും പരിശോധിക്കുക.",
        "disease_model_unavailable": "പരിശീലിപ്പിച്ച വിളരോഗ മോഡൽ ലോഡ് ചെയ്യാനായില്ല. ബാക്ക്‌എൻഡിലെ TensorFlow/Keras ഇൻസ്റ്റാളേഷനും മോഡൽ ഫയലുകളും പരിശോധിക്കുക.",
        "disease_provider_unavailable": "ദൃശ്യ വിശകലന സേവനം താൽക്കാലികമായി ലഭ്യമല്ല. ഈ ചിത്രത്തിന് പ്രാദേശിക മോഡലിന് വിശ്വസനീയമായ ഫലം നൽകാനായില്ല; പിന്നീട് വീണ്ടും ശ്രമിക്കുക.",
        "disease_configuration_error": "ഈ സെർവറിൽ രോഗവിശകലനം ക്രമീകരിച്ചിട്ടില്ല. വിഷൻ സേവനം ക്രമീകരിക്കുകയോ പരിശീലിപ്പിച്ച പ്രാദേശിക മോഡൽ പുനഃസ്ഥാപിക്കുകയോ ചെയ്യുക.",
        "disease_processing_error": "രോഗവിശകലന സേവനത്തിന് ചിത്രം പ്രോസസ്സ് ചെയ്യാനായില്ല. പിന്തുണയ്ക്കുന്ന ചിത്രം ഉപയോഗിച്ച് വീണ്ടും ശ്രമിക്കുക.",
        "weather_unavailable": "കാലാവസ്ഥാ സേവനം ലഭ്യമല്ല. ദയവായി പിന്നീട് വീണ്ടും ശ്രമിക്കുക.",
        "diagnosis_uncertain": "വിളയെയോ രോഗത്തെയോ ഉറപ്പായി തിരിച്ചറിയാൻ കഴിയുന്നില്ല. ചിത്രത്തിൽ മതിയായ വിശ്വസനീയ തെളിവില്ല. നല്ല വെളിച്ചത്തിൽ ഒരിലയുടെ വ്യക്തമായ അടുത്തുനിന്നുള്ള ചിത്രം അപ്‌ലോഡ് ചെയ്യുക, അല്ലെങ്കിൽ പ്രാദേശിക കൃഷിവിദഗ്ധനോട് സ്ഥിരീകരിക്കുക.",
        "translation_unavailable": "ഈ രോഗനിർണയത്തിന്റെ വിശ്വസനീയമായ വിവർത്തനം ഇപ്പോൾ ലഭ്യമല്ല. വിവർത്തനം ചെയ്ത രോഗനിർണയം കാണിക്കുന്നില്ല; പിന്നീട് വീണ്ടും ശ്രമിക്കുക.",
        "translation_quota_unavailable": "ക്രമീകരിച്ച വിവർത്തന സേവനത്തിന്റെ API ക്വോട്ട തീർന്നതിനാൽ രോഗനിർണയം വിവർത്തനം ചെയ്യാനാകില്ല. വീണ്ടും ശ്രമിക്കുന്നതിന് മുമ്പ് സേവന ഉപയോഗവും ബില്ലിംഗും പരിശോധിക്കുക.",
    },
}


def resolve_language(language: str | None) -> str:
    """Return a supported language code, rejecting unknown values instead of silently changing language."""
    code = (language or "en").strip().lower()
    if code not in LANGUAGE_NAMES:
        raise ValueError(code)
    return code


def localized_message(language: str, message_key: str) -> str:
    code = resolve_language(language)
    messages = _MESSAGES[code]
    return messages.get(message_key, messages["disease_unavailable"])


def translate_known_message(message: str, language: str) -> str | None:
    """Translate a known fixed system message from the local verified dictionary."""
    code = resolve_language(language)
    for message_key, english_message in _MESSAGES["en"].items():
        if message == english_message or any(
            message == _MESSAGES[source_language].get(message_key)
            for source_language in LANGUAGE_NAMES
        ):
            return _MESSAGES[code].get(message_key)
    return None

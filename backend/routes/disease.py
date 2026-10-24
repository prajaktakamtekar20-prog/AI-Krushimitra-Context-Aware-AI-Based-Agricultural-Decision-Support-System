import logging
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, Depends, Header
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel
import shutil
import os
import hashlib
import uuid
import time
import math

from services.ai_service import (
    AIProviderUnavailable,
    _translate_model_diagnosis,
    detect_crop_disease,
)
from services.disease_result_localization import localize_disease_result
from services.disease_model_service import (
    predict_disease,
    analyze_prediction,
    build_crop_disease_key,
    normalize_crop_for_key,
    ERROR_DB_VALIDATION,
)
from services.image_quality import assess_image_quality
from auth_utils import get_current_user
from services.localization import localized_message, resolve_language

router = APIRouter()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
MAX_DISEASE_IMAGE_BYTES = 10 * 1024 * 1024
MAX_TRANSLATION_TEXT_CHARS = 20_000
SUPPORTED_IMAGE_TYPES = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


class DiseaseTranslationRequest(BaseModel):
    result: Dict[str, Any]


@router.post("/translate")
async def translate_disease_result(
    request: DiseaseTranslationRequest,
    x_language: Optional[str] = Header(default="en", alias="X-Language"),
):
    try:
        language = resolve_language(x_language)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=localized_message("en", "invalid_language"),
        )

    allowed_fields = {
        "crop", "disease", "severity", "symptoms", "possible_causes", "causes",
        "recommended_management", "treatment", "prevention", "safety_warnings", "warnings",
        "precautions", "diagnostic_note", "error", "crop_display", "disease_display",
        "confidence", "disease_confidence", "crop_confidence", "uncertain",
        "is_valid_plant_image", "ok", "symptoms_basis", "disease_key", "raw_class",
    }
    result = {
        key: value
        for key, value in request.result.items()
        if key in allowed_fields and value is not None
    }
    if (
        not isinstance(result.get("crop"), str)
        or not result.get("crop", "").strip()
        or not isinstance(result.get("disease"), str)
        or not result.get("disease", "").strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=localized_message(language, "translation_unavailable"),
        )

    numeric_fields = {"confidence", "disease_confidence", "crop_confidence"}
    boolean_fields = {"uncertain", "is_valid_plant_image", "ok"}
    identifier_fields = {"symptoms_basis", "disease_key", "raw_class"}
    text_size = 0
    for key, value in result.items():
        if key in numeric_fields:
            try:
                valid_number = (
                    not isinstance(value, bool)
                    and isinstance(value, (int, float))
                    and math.isfinite(value)
                )
            except OverflowError:
                valid_number = False
            if not valid_number:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=localized_message(language, "translation_unavailable"),
                )
            continue
        if key in boolean_fields:
            if not isinstance(value, bool):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=localized_message(language, "translation_unavailable"),
                )
            continue
        if key in identifier_fields:
            if not isinstance(value, str):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=localized_message(language, "translation_unavailable"),
                )
            continue
        if isinstance(value, str):
            text_size += len(value)
        elif isinstance(value, list):
            if len(value) > 20 or not all(isinstance(item, str) for item in value):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=localized_message(language, "translation_unavailable"),
                )
            text_size += sum(len(item) for item in value)
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=localized_message(language, "translation_unavailable"),
            )
    if text_size > MAX_TRANSLATION_TEXT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=localized_message(language, "translation_unavailable"),
        )

    started = time.perf_counter()
    translated = localize_disease_result(result, language)
    translation_source = "local_dictionary"
    if not isinstance(translated, dict) or not translated.get("_translation_complete"):
        translation_source = "ai_provider"
        try:
            translated = await _translate_model_diagnosis(result, language)
        except AIProviderUnavailable as exc:
            logger.warning(
                "Disease result translation unavailable language=%s reason=%s; using verified local translations",
                language,
                exc.reason,
            )
            translated = localize_disease_result(result, language)
            translation_source = "local_fallback"
        except Exception as exc:
            logger.warning(
                "Disease result translation failed language=%s error_type=%s; using verified local translations",
                language,
                type(exc).__name__,
            )
            translated = localize_disease_result(result, language)
            translation_source = "local_fallback"
    if not isinstance(translated, dict) or not translated.get("crop") or not translated.get("disease"):
        translated = localize_disease_result(result, language)
        translation_source = "local_fallback"
    if not isinstance(translated, dict) or not translated.get("crop") or not translated.get("disease"):
        logger.warning(
            "Disease result translation produced no usable diagnosis language=%s elapsed_ms=%.1f",
            language,
            (time.perf_counter() - started) * 1000,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "detail": localized_message(language, "translation_unavailable"),
                "code": "translation_unavailable",
            },
        )
    if (
        not translated.get("_translation_complete")
        and "_untranslated_fields" not in translated
    ):
        translated = localize_disease_result(result, language)
        translation_source = "local_fallback"
    translation_complete = bool(translated.pop("_translation_complete", False))
    untranslated_fields = translated.pop("_untranslated_fields", [])
    translated["translation_complete"] = translation_complete
    if untranslated_fields:
        translated["untranslated_fields"] = untranslated_fields
    logger.info(
        "Disease timing stage=language_translation language=%s source=%s elapsed_ms=%.1f",
        language,
        translation_source,
        (time.perf_counter() - started) * 1000,
    )
    return {"success": True, "result": translated}


DISEASE_DB = {
    "apple_apple_scab": {
        "disease": "Apple Scab",
        "severity": "Moderate to Severe",
        "crop": "Apple",
        "symptoms": [
            "Olive-green to brown velvety lesions on leaf undersides, later turning black and corky",
            "Similar lesions on fruit causing distortion, cracking, and premature drop",
            "Severe leaf infection leads to yellowing and early defoliation weakening tree",
            "Twig lesions on susceptible cultivars provide overwintering sites for fungus"
        ],
        "causes": [
            "Fungal pathogen Venturia inaequalis",
            "Overwinters in fallen infected leaves producing spores in early spring during green tip",
            "Primary infection occurs during wetting periods (leaf wetness duration ≥ 9 hrs at 15-20°C)",
            "Secondary (repeating) cycles every 10-14 days throughout growing season under favorable conditions"
        ],
        "treatment": [
            "Apply protective fungicides starting at green tip: Captan, Mancozeb, or Dodine",
            "Curative fungicides (post-infection): Myclobutanil, Penconazole within 72-96 hrs of infection event",
            "Spray interval 7-10 days, shorten during extended wet / high-humidity periods",
            "Remove and destroy fallen leaves in autumn (or shred/mulch in place with 5% urea spray)"
        ],
        "prevention": [
            "Plant scab-resistant apple cultivars: Liberty, Enterprise, Prima, GoldRush, Priscilla",
            "Rake, remove, or shred fallen leaves in autumn (reduces primary inoculum 70-90%)",
            "Apply 5% urea to fallen leaves just before leaf drop to accelerate decomposition",
            "Use disease warning systems (RIMpro, NEWA) to optimize spray timing and reduce applications"
        ]
    },
    "apple_black_rot": {
        "disease": "Black Rot (Apple)",
        "severity": "Severe",
        "crop": "Apple",
        "symptoms": [
            "Circular, slightly sunken tan to black lesions with concentric rings on fruit",
            "Frog-eye leaf spots: Small circular purple spots enlarging to tan centers with purple margins",
            "Cankers on branches and trunk causing bark cracking, girdling, and branch dieback",
            "Affected fruit shrivels and mummifies; remains attached to tree as overwintering site"
        ],
        "causes": [
            "Fungal pathogen Botryosphaeria obtusa (Physalospora obtusa)",
            "Overwinters in cankers, mummified fruit, and dead wood in orchard",
            "Spores spread by rain splash, wind, or pruning tools during wet spring/summer weather",
            "Weakened or stressed trees are most susceptible; wounds facilitate entry"
        ],
        "treatment": [
            "Prune out all cankers, dead wood, and mummified fruit during dormancy",
            "Sanitize pruning tools between cuts to prevent spread",
            "Apply protective fungicides: Captan or Mancozeb at bud break, bloom, and 2-3 post-bloom sprays",
            "Systemic fungicides (Tebuconazole, Myclobutanil) during early fruit development",
            "Remove severely infected trees that cannot be salvaged"
        ],
        "prevention": [
            "Plant disease-free nursery stock from certified sources",
            "Ensure adequate spacing and pruning for good air circulation and sunlight penetration",
            "Avoid injury to trunks and branches during cultivation; protect wounds with wound dressing",
            "Follow balanced fertilization to maintain tree vigor without excessive nitrogen",
            "Remove and destroy prunings, mummified fruit, and crop debris from orchard"
        ]
    },
    "apple_cedar_apple_rust": {
        "disease": "Cedar Apple Rust",
        "severity": "Moderate",
        "crop": "Apple",
        "symptoms": [
            "Apple leaves: Bright yellow-orange spots with red borders on upper surface",
            "Spots enlarge and develop raised, cup-like fungal structures (aecia) on underside",
            "Fruit: Similar spots near calyx end, may cause distortion and premature drop",
            "Cedar/Juniper alternate host: Greenish-brown galls producing orange gelatinous horns in spring rain"
        ],
        "causes": [
            "Fungal pathogen Gymnosporangium juniperi-virginianae",
            "Requires two alternate hosts: Apple/Malus and Juniperus (cedar) species to complete life cycle",
            "Spores released from cedar galls during spring rains infect young apple leaves/fruit",
            "Infection favored by cool, wet, windy conditions in early spring (10-24°C)"
        ],
        "treatment": [
            "Apply protective fungicides: Myclobutanil or Mancozeb on 7-10 day schedule starting at pink bud through petal fall + 30 days",
            "Remove cedar/juniper trees within 1 km radius of orchard where feasible",
            "Prune and remove cedar galls from junipers in late winter before spore release",
            "Rake and destroy fallen apple leaves in autumn to reduce overwintering inoculum"
        ],
        "prevention": [
            "Plant rust-resistant apple varieties (e.g., Red Delicious, Enterprise, GoldRush)",
            "Avoid planting susceptible Malus species within 1-2 km of cedar/juniper windbreaks",
            "Remove eastern red cedar (Juniperus virginiana) near orchards if practical",
            "Monitor weather forecasts and tighten spray intervals during prolonged wet spring periods"
        ]
    },
    "apple_healthy": {
        "disease": "Healthy Leaf / No Major Disease Detected",
        "severity": "Mild (None)",
        "crop": "Apple",
        "symptoms": [
            "Leaves uniformly green, vigorous, with no visible lesions or spots",
            "Good leaf turgor and structure; no abnormal curling or distortion",
            "Fruit clean and free of blemishes where present",
            "Tree shows healthy overall canopy development"
        ],
        "causes": [
            "Good orchard management and sanitation practices",
            "Favorable weather conditions for apple production",
            "Adequate balanced nutrition and irrigation",
            "Low disease inoculum pressure or effective preventive program"
        ],
        "treatment": [
            "Continue regular orchard scouting at least weekly during growing season",
            "Maintain balanced fertilization (NPK) and consistent irrigation schedule",
            "Follow good orchard sanitation: remove dropped fruit, prunings, and leaf litter",
            "Consider preventive Sulphur or Copper sprays if weather becomes conducive to disease"
        ],
        "prevention": [
            "Maintain orchard hygiene; remove weeds, mummified fruit, and pruning debris",
            "Prune annually for open canopy with good light and air penetration",
            "Use certified disease-free rootstock and grafting material",
            "Follow an apple disease warning system for optimized fungicide timing",
            "Ensure proper tree spacing to prevent canopy overcrowding"
        ]
    },
    "blueberry_healthy": {
        "disease": "Healthy Leaf / No Major Disease Detected",
        "severity": "Mild (None)",
        "crop": "Blueberry",
        "symptoms": [
            "Leaves uniformly blue-green with no spots, lesions, or abnormal discoloration",
            "Healthy leaf structure; no curling, wilting, or premature senescence",
            "Bush shows vigorous growth and good canopy density",
            "Fruit development normal where present"
        ],
        "causes": [
            "Good cultural management suited to acid-soil-loving blueberries",
            "Favorable weather and appropriate soil pH (4.0-5.5)",
            "Adequate mulching, irrigation, and balanced acidic nutrition",
            "Low disease pressure in the planting"
        ],
        "treatment": [
            "Continue weekly scouting for leaf spots, berry rots, and stem cankers",
            "Maintain acidic soil pH and consistent moisture via mulch and drip irrigation",
            "Remove any fallen fruit and pruning debris from planting area",
            "If weather turns warm/wet, consider preventive Copper-based sprays"
        ],
        "prevention": [
            "Use pine bark or sawdust mulch to conserve moisture and maintain acidity",
            "Avoid overhead irrigation; use drip to reduce leaf wetness and berry rot",
            "Prune out weak or crossing canes annually for open growth habit",
            "Choose disease-resistant blueberry cultivars adapted to your region",
            "Keep planting free from weeds that increase humidity around canopy"
        ]
    },
    "cherry_powdery_mildew": {
        "disease": "Powdery Mildew (Cherry)",
        "severity": "Mild to Moderate",
        "crop": "Cherry",
        "symptoms": [
            "White to grayish powdery fungal growth on upper leaf surfaces and young shoots",
            "Leaves may curl upward, become puckered, and turn pale or reddish",
            "Young fruit can develop powdery patches, russeting, and cracking",
            "Severe infection reduces photosynthesis, weakens tree, and reduces fruit quality"
        ],
        "causes": [
            "Fungal pathogen Podosphaera clandestina (cherry-specific powdery mildew)",
            "Overwinters as cleistothecia on bud scales and fallen leaves, or as mycelium in dormant buds",
            "High relative humidity (60-80%) without free water on leaves, moderate temps (18-25°C)",
            "Dense canopy, poor air movement, shade, and excessive nitrogen favor rapid spread"
        ],
        "treatment": [
            "Prune out and remove heavily infected shoots at first sign of symptoms",
            "Sulfur-based fungicides (Wettable Sulfur 0.3%) – do not use in high heat >30°C",
            "Systemic fungicides: Myclobutanil 10% WP or Tebuconazole for curative action",
            "Organic: Potassium bicarbonate 0.5% spray or wettable Sulfur below 30°C",
            "Apply every 7-10 days, rotate fungicide modes of action to avoid resistance"
        ],
        "prevention": [
            "Plant cherry trees in sunny locations with good air circulation",
            "Avoid excessive nitrogen; use balanced NPK fertilization",
            "Summer prune to open canopy to sunlight and improve air movement",
            "Remove weeds and alternate hosts around orchard perimeter",
            "Apply preventive Sulphur dust at popcorn / white bud stage before onset"
        ]
    },
    "cherry_healthy": {
        "disease": "Healthy Leaf / No Major Disease Detected",
        "severity": "Mild (None)",
        "crop": "Cherry",
        "symptoms": [
            "Leaves uniformly green, no powdery growth, leaf spots, or necrosis",
            "Good leaf structure, no curling, puckering, or deformation",
            "Tree shows healthy vegetative growth, buds well-formed",
            "Fruit where present is clean and free of blemishes or cracks"
        ],
        "causes": [
            "Effective orchard management and preventive spray program",
            "Weather conditions not favorable for cherry disease development",
            "Balanced nutrition and adequate irrigation",
            "Low overwintering inoculum from good previous-season sanitation"
        ],
        "treatment": [
            "Continue weekly orchard scouting during growing season",
            "Maintain balanced nutrition (avoid excess N) and regular irrigation",
            "Maintain good orchard floor and pruning sanitation",
            "Consider preventive Sulphur or Captan sprays during humid periods"
        ],
        "prevention": [
            "Prune annually for open canopy structure and good light penetration",
            "Remove and destroy pruning debris and mummified fruit from orchard",
            "Use certified virus-free cherry rootstocks and budwood",
            "Apply dormant-season lime-Sulphur to reduce overwintering inoculum",
            "Space trees properly to promote rapid drying of foliage after dew/rain"
        ]
    },
    "corn_leaf_spot": {
        "disease": "Gray Leaf Spot (Cercospora zeae-maydis)",
        "severity": "Moderate to Severe",
        "crop": "Corn (Maize)",
        "symptoms": [
            "Small, rectangular, necrotic lesions (1-4 mm) bounded by veins on lower leaves",
            "Lesions initially tan then turn gray-brown; expand into long narrow rectangular streaks parallel to veins",
            "Lesions coalesce to blight large portions of leaf; severe yield loss on susceptible hybrids",
            "Disease progresses from lower canopy upward; favored by no-till and continuous corn"
        ],
        "causes": [
            "Fungal pathogen Cercospora zeae-maydis / C. zeina",
            "Overwinters as mycelium and stromata in corn residue on soil surface",
            "Spores (conidia) dispersed by wind and rain splash; infection requires 12-24+ hours leaf wetness at 22-30°C",
            "Favored by humid, cloudy, dewy conditions, minimum tillage, and corn-after-corn rotation"
        ],
        "treatment": [
            "Foliar fungicides: Tebuconazole 250 EC, Propiconazole, or Pyraclostrobin (QoI) + Mancozeb combination",
            "Treat at VT/R1 (tassel/silking) stage when lesions first appear on ear leaf or below",
            "Repeat application after 14-21 days if disease pressure continues and weather favorable",
            "Apply protectant + systemic combination tank-mix in high-pressure fields"
        ],
        "prevention": [
            "Plant GLS-resistant or tolerant corn hybrids for your region (most effective)",
            "Crop rotation with non-host crops (soybean, legumes, cotton) for minimum 1-2 years",
            "Reduce / bury corn residue with tillage if GLS history is severe in field",
            "Balanced NPK fertilization; avoid excessive nitrogen that increases canopy humidity",
            "Optimum plant population and row spacing to improve air movement and lower RH in canopy"
        ]
    },
    "corn_rust": {
        "disease": "Common Rust of Maize (Puccinia sorghi)",
        "severity": "Moderate to Severe",
        "crop": "Corn (Maize)",
        "symptoms": [
            "Small oval to elongated orange-red pustules (uredinia) on both upper and lower leaf surfaces",
            "Pustules rupture releasing powdery rust-colored uredospores",
            "Heavy infection: large areas of leaf die, reducing photosynthetic area and yield",
            "Later in season, blackish-brown telial pustules develop in same lesions as overwintering stage"
        ],
        "causes": [
            "Obligate biotrophic fungus Puccinia sorghi (macrocyclic, heteroecious - alternate hosts Oxalis spp.)",
            "Wind-borne uredospores are blown long distances from southern areas into northern corn belts each season",
            "Favored by cool to moderate temps (15-25°C), high humidity, heavy dews, and frequent light rain",
            "Early planting and susceptible hybrids suffer most damage; late-season infections are less damaging"
        ],
        "treatment": [
            "Foliar spray: Propiconazole 25% EC (0.1%) or Tebuconazole 250 EC (0.1%) when 2-3 pustules/leaf observed",
            "Alternative: Mancozeb 75% WP (0.25%) as protective spray on a 10-day schedule",
            "Treat most aggressively at tasseling/silking (VT/R1) stage if rust is active on upper canopy",
            "Repeat spray at 10-15 day intervals if cool humid weather persists and pustules continue expanding"
        ],
        "prevention": [
            "Plant resistant / tolerant corn hybrids carrying Rp resistance genes adapted to your region",
            "Early sowing to allow plants to progress past critical growth stages before heavy spore arrival",
            "Balanced NPK fertilization; avoid excessive nitrogen that increases succulent susceptible growth",
            "Monitor crop weekly from knee-high to tassel stage for first pustule appearance",
            "Keep field borders mown; remove alternate weed hosts where feasible"
        ]
    },
    "corn_northern_leaf_blight": {
        "disease": "Northern Leaf Blight (Turcicum Leaf Blight)",
        "severity": "Moderate to Severe",
        "crop": "Corn (Maize)",
        "symptoms": [
            "Large, elongated (2-15 cm) cigar-shaped gray-green to tan necrotic lesions on lower leaves",
            "Lesions have a characteristic rectangular shape bounded by veins",
            "Heavy infection causes entire leaf blades to die, reducing photosynthetic area",
            "Disease progresses upwards from lower canopy during season; severe yield loss on susceptible hybrids"
        ],
        "causes": [
            "Fungal pathogen Exserohilum turcicum (Setosphaeria turcica)",
            "Overwinters on crop debris and infected corn residue on soil surface",
            "Spores spread by wind and rain splash; infection requires 6-18 hrs leaf wetness at 18-27°C",
            "Favored by moderate temps (20-25°C), high humidity (>90%), and frequent dews / light rains"
        ],
        "treatment": [
            "Foliar fungicides: Propiconazole, Tebuconazole, or Mancozeb at onset of symptoms",
            "Apply protectant + systemic combination if disease pressure is high or environment favorable",
            "Treat at tasseling / silking stage (most critical period for yield protection)",
            "Repeat after 14-21 days depending on disease pressure and weather"
        ],
        "prevention": [
            "Use resistant or tolerant hybrids adapted to your region (most effective)",
            "Crop rotation with non-host crops (soybean, cotton, legumes) for 1-2 years",
            "Conservation tillage should be avoided in fields with history of severe NLB",
            "Balanced NPK fertilization; avoid excessive nitrogen that promotes lush susceptible growth",
            "Optimum plant population to reduce canopy humidity and improve air circulation"
        ]
    },
    "corn_healthy": {
        "disease": "Healthy Leaf / No Major Disease Detected",
        "severity": "Mild (None)",
        "crop": "Corn (Maize)",
        "symptoms": [
            "Leaves uniformly green, no lesions, streaks, or rust pustules visible",
            "Good leaf turgor; no wilting, necrosis, or premature senescence",
            "Uniform healthy stand; plants reach expected height and tassel/silk timing",
            "Cobs fill properly with no visible ear rots where present"
        ],
        "causes": [
            "Good crop husbandry: proper rotation, seed quality, and fertility",
            "Weather conditions not favoring corn disease outbreaks",
            "Resistant hybrid planted in field",
            "Low inoculum due to good previous-season residue management"
        ],
        "treatment": [
            "Continue weekly scouting for leaf diseases, stalk rots, and ear rots through season",
            "Maintain balanced NPK fertility and adequate irrigation especially at critical stages",
            "Monitor weather for high-risk periods for rust, NLB, or blight outbreaks",
            "Keep field borders and perimeter clean from weeds and alternate hosts"
        ],
        "prevention": [
            "Always plant locally-adapted, disease-resistant hybrids from certified source",
            "Practice crop rotation (soybean/legumes minimum 1 year, preferably 2)",
            "Seed treatment with fungicide + insecticide (Carboxin + Thiram + Imidacloprid) recommended",
            "Manage plant population and row spacing to avoid excessively dense canopies",
            "Consider foliar fungicide at tassel/silking if weather becomes highly conducive to disease"
        ]
    },
    "grape_black_rot": {
        "disease": "Black Rot (Grape)",
        "severity": "Severe",
        "crop": "Grape",
        "symptoms": [
            "Leaves: Small circular tan spots with dark brown/black margins; tiny black pycnidia visible in centers",
            "Shoots/rachises: Elongated black sunken cankers girdling and killing young shoots",
            "Berries: At pea size or later: white circular spot with brown margin; rapidly expands into mummified shriveled black berry covered in pycnidia",
            "Fruit infection is most damaging phase; ripe rot can develop near harvest if conditions favorable"
        ],
        "causes": [
            "Fungal pathogen Guignardia bidwellii (anamorph Phyllosticta ampelicida)",
            "Overwinters as pseudothecia in mummified berries, infected canes, and tendrils from previous season",
            "Ascospores released during spring rains; infection requires 6-24 hrs leaf wetness at 20-27°C",
            "Favored by warm, wet, humid growing seasons; susceptible cultivars can be 100% destroyed without protection"
        ],
        "treatment": [
            "Remove and destroy all mummified berries and cankers during dormant pruning; do not compost",
            "Protective fungicides: Captan or Mancozeb starting at bud burst; repeat every 7-14 days",
            "Systemic fungicides (Difenoconazole, Myclobutanil, Tebuconazole) for curative kick-back after infection events",
            "Most critical protection period: immediate pre-bloom through 3-4 weeks post-bloom (berry set)",
            "Organic: Fixed Copper (Bordeaux mixture or Copper oxychloride) with good coverage every 7-10 days"
        ],
        "prevention": [
            "Plant black-rot-tolerant or resistant grape cultivars where available (e.g., many V. labrusca types)",
            "Dormant pruning: remove all infected canes, tendrils, clusters; thin vines for open canopy",
            "Canopy management: leaf removal around clusters, shoot positioning, hedging to improve air flow + spray penetration",
            "Avoid overhead irrigation; use drip/under-vine irrigation to minimize leaf and berry wetness",
            "Apply dormant lime-sulfur or Copper spray to reduce overwintering inoculum before buds break"
        ]
    },
    "grape_esca": {
        "disease": "Esca / Black Measles / Grapevine Trunk Disease",
        "severity": "Severe",
        "crop": "Grape",
        "symptoms": [
            "Leaves: Small chlorotic spots between veins coalescing into tiger-stripe pattern of red/yellow necrotic areas",
            "Berries: Tiny dark black spots (measles) surrounded by reddish halo; berries may crack and shrivel",
            "Wood: Dark streaks in xylem; white rot in center of trunk; cross-sections show characteristic black spots and streaks",
            "Whole vine: Sudden wilting and 'apoplexy' of shoots/vines mid-season; slow decline over years"
        ],
        "causes": [
            "Complex of fungi: Phaeomoniella chlamydospora, Phaeoacremonium species, Fomitiporia mediterranea",
            "Fungi enter primarily through pruning wounds; colonization of woody tissues disrupts xylem",
            "Favored by older vineyards, drought stress, heavy pruning, and poor wound protection",
            "Inoculum produced in old pruning wounds and cracks; dispersed by rain splash during winter/spring pruning period"
        ],
        "treatment": [
            "No curative treatment for vines with advanced internal wood rot - remove and replace heavily infected vines",
            "Protect all fresh pruning wounds with registered wound protectant (fungicide paste or paint) immediately after cutting",
            "Surgical removal (trenching) of infected wood cankers down to healthy tissue on slightly affected vines",
            "Reduce vine stress: Adequate irrigation, balanced fertilization, avoid excess vigor, cover crops for soil health",
            "Foliar sprays of fosetyl-Al or phosphonates may slow symptom development in early stages"
        ],
        "prevention": [
            "Always protect pruning wounds (within minutes/hours): thiophanate-methyl, copper pastes, or commercially available wound sealants",
            "Delay pruning to late dormant period (late winter/early spring) - reduces wound susceptibility period",
            "Sanitize pruning saws and shears between vines with 10% household bleach or commercial disinfectant",
            "Plant certified disease-free, trunk-disease-tested nursery stock obtained from reliable supplier",
            "Remove and destroy (burn, chip, or bury) infected prunings, dead wood, and uprooted vines away from vineyard"
        ]
    },
    "grape_leaf_blight_isariopsis": {
        "disease": "Leaf Blight (Isariopsis Leaf Spot)",
        "severity": "Moderate",
        "crop": "Grape",
        "symptoms": [
            "Irregular to angular, reddish-brown to dark brown necrotic spots on upper leaf surfaces",
            "Lesions 2-10 mm, often with yellow-green margin; centers may crack or fall out (shot-hole)",
            "Olive-brown to grayish sporulation visible on lower leaf surface under magnification",
            "Severe infection leads to premature defoliation, exposing fruit to sunburn and reducing sugar accumulation"
        ],
        "causes": [
            "Fungal pathogen Pseudocercospora vitis (formerly Isariopsis clavispora / Mycovellosiella vitis)",
            "Overwinters in fallen infected leaves and diseased canes as mycelium and spores",
            "Conidia spread by wind and rain splash; infection requires 12-24 hrs leaf wetness at 20-28°C",
            "Favored by warm, humid summers, dense canopy, high plantings, and overhead irrigation"
        ],
        "treatment": [
            "Apply protective fungicides: Copper oxychloride (0.3%), Captan, or Mancozeb at 10-14 day intervals",
            "Systemic fungicides: Tebuconazole, Difenoconazole, or Myclobutanil for curative action",
            "First spray at fruit set; repeat as required depending on canopy density and weather",
            "Organic alternatives: Wettable sulfur (below 30°C), Copper sulfate, or Bacillus amyloliquefaciens biofungicides"
        ],
        "prevention": [
            "Cultural practice: Maintain open canopy through timely pruning, leaf removal, and shoot positioning",
            "Remove basal leaves around fruit zone at veraison to improve air circulation and reduce humidity",
            "Rake and shred/destroy fallen leaves in autumn or incorporate into soil (reduces overwintering inoculum)",
            "Avoid overhead irrigation; use drip / under-vine irrigation to minimize leaf wetness",
            "Use disease-free planting material; select less susceptible grape cultivars where available"
        ]
    },
    "grape_healthy": {
        "disease": "Healthy Leaf / No Major Disease Detected",
        "severity": "Mild (None)",
        "crop": "Grape",
        "symptoms": [
            "Leaves uniformly green with no spots, necrosis, tiger-striping, or powdery growth",
            "Good leaf structure; no cupping, curling, or premature senescence",
            "Vine shows good vigor, balanced growth, and well-spaced internodes",
            "Clusters develop normally with clean, undamaged berries where present"
        ],
        "causes": [
            "Good vineyard management including canopy management and sanitation",
            "Weather conditions not favoring powdery mildew, black rot, or downy mildew",
            "Adequate balanced nutrition and irrigation scheduling",
            "Good previous-season dormant pruning reducing overwintering inoculum"
        ],
        "treatment": [
            "Continue weekly vineyard scouting during growing season especially pre-bloom through veraison",
            "Maintain balanced canopy: shoot thinning, leaf removal at cluster zone, hedging as needed",
            "Keep up good floor management: mow middles, remove suckers, control weeds",
            "Apply protective fungicides only if weather becomes highly conducive to disease"
        ],
        "prevention": [
            "Annual dormant pruning for balanced vine architecture; remove all infected/weak wood",
            "Apply dormant lime-sulfur or Copper spray to reduce overwintering powdery mildew/black rot inoculum",
            "Plant disease-resistant grape cultivars or certified disease-free nursery stock",
            "Use drip irrigation; avoid overhead watering to keep foliage and berries dry",
            "Protect pruning wounds immediately with fungicide pastes to reduce trunk disease risk"
        ]
    },
    "orange_haunglongbing": {
        "disease": "Citrus Greening / Huanglongbing (HLB)",
        "severity": "Severe",
        "crop": "Orange (Citrus)",
        "symptoms": [
            "Asymmetrical blotchy mottling of leaves; yellowing with irregular green patches (not uniform)",
            "Twig dieback progressing from canopy tips; overall stunting and decline vigor",
            "Fruit: Small, lopsided, with curved central column; bitter/off taste; poor color development (green at stylar end even at maturity)",
            "Aborted / dark seeds inside fruit; excessive fruit drop and premature flowering (off-season bloom)"
        ],
        "causes": [
            "Phloem-limited bacterium Candidatus Liberibacter asiaticus (CLas, most common)",
            "Transmitted by Asian citrus psyllid (Diaphorina citri) insect vector during feeding, or by grafting",
            "Once infected, all parts of tree (phloem) are permanently colonized; no cure for systemically infected tree",
            "Disease spread favored by presence of psyllid vector, nearby infected citrus trees, and movement of infected nursery stock"
        ],
        "treatment": [
            "No cure exists for HLB-infected trees - remove and destroy all confirmed infected trees to stop inoculum source",
            "Aggressive control of Asian citrus psyllid vector using foliar and soil-applied systemic insecticides (Imidacloprid, Thiamethoxam)",
            "Apply insecticides during dormancy, flush periods, and coordinated area-wide sprays to suppress psyllid populations",
            "Nutritional support: Regular foliar sprays of micronutrients (Zn, Mn, Fe, B) + cytokinins/seaweed extracts to temporarily extend productive life",
            "Establish new plantings with certified HLB-free nursery stock, protected by insect-proof screening"
        ],
        "prevention": [
            "Strict area-wide management: Remove all abandoned / neglected citrus trees within 5 km radius",
            "Use only certified, pathogen-tested nursery stock from accredited clean-stock program",
            "Protect young trees under 3 years with protective screen enclosures or regular psyllid monitoring + insecticide sprays",
            "Establish coordinated community / area-wide citrus health management program with shared scouting and vector control",
            "Monitor psyllid populations using yellow sticky traps; survey trees for HLB symptoms during every visit"
        ]
    },
    "peach_bacterial_spot": {
        "disease": "Bacterial Spot (Peach)",
        "severity": "Moderate to Severe",
        "crop": "Peach / Nectarine",
        "symptoms": [
            "Leaves: Small angular water-soaked spots turning purple/brown/black; centers may drop out giving shot-hole appearance",
            "Fruit: Small circular scabby brown to black spots, raised, cracking as fruit enlarges; secondary brown rot may follow",
            "Stems/twigs: Dark cankers and blighted tips developing during dormancy; may girdle and kill young branches",
            "Severe infection leads to heavy defoliation, sunburned fruit, and substantial quality/yield loss"
        ],
        "causes": [
            "Bacterial pathogen Xanthomonas arboricola pv. pruni (formerly X. pruni)",
            "Overwinters in twig cankers and in buds of infected peach/nectarine trees",
            "Bacteria spread by rain splash, wind-driven rain, overhead sprinklers, and contaminated pruning tools",
            "Infection favored by warm (20-28°C) wet weather; leaf stomates and fruit lenticels as entry points; sandy low-nutrient soils increase susceptibility"
        ],
        "treatment": [
            "Prune out and burn all infected twigs, cankers, and blighted branches during dormant period",
            "Copper-based sprays: Copper oxychloride 50% WP (0.3%) starting at dormant (delayed dormant / pink bud) stage",
            "Continue Copper every 7-10 days through petal fall and into early fruit development if wet weather persists",
            "Where permitted: Oxytetracycline or Streptomycin antibiotic sprays rotated with Copper during critical infection periods",
            "Avoid overhead irrigation; use drip irrigation to minimize leaf wetness and splash dispersal"
        ],
        "prevention": [
            "Plant bacterial-spot-resistant peach/nectarine cultivars (e.g., Redhaven derivatives, many modern releases)",
            "Use certified disease-free nursery stock; do not propagate from known infected trees",
            "Orchard site: select well-drained sunny location with good air flow; avoid frost pockets",
            "Balanced nutrition: proper soil pH and adequate calcium levels help reduce tree susceptibility",
            "Sanitize pruning tools between trees during dormant pruning; remove wild Prunus hosts nearby"
        ]
    },
    "peach_healthy": {
        "disease": "Healthy Leaf / No Major Disease Detected",
        "severity": "Mild (None)",
        "crop": "Peach",
        "symptoms": [
            "Leaves uniformly green, no spots, shot-holes, curling, or powdery growth",
            "Good leaf structure and turgor; no premature yellowing or defoliation",
            "Tree shows good vigor and healthy fruiting wood and buds",
            "Fruit where present is clean, free of spots, scabs, or deformities"
        ],
        "causes": [
            "Good orchard sanitation and dormant spray program",
            "Weather not highly favorable to brown rot, bacterial spot, or leaf curl",
            "Balanced fertilization and adequate soil moisture",
            "Healthy root system and properly trained open-vase tree structure"
        ],
        "treatment": [
            "Continue weekly orchard scouting from bud break through harvest",
            "Maintain balanced nutrition (avoid excess N) and regular irrigation schedule",
            "Keep orchard floor mown; remove dropped fruit and prunings promptly",
            "Consider preventive Copper/Sulphur sprays if weather becomes warm and wet"
        ],
        "prevention": [
            "Annual dormant pruning for open vase structure, good light + air penetration",
            "Apply dormant copper + lime-sulphur to control bacterial canker, leaf curl, and overwintering inoculum",
            "Plant disease-resistant peach cultivars and certified rootstock",
            "Thin fruit properly to avoid overcropping and maintain tree vigor",
            "Avoid wounding bark; prevent fruit skin damage from thinning and wind"
        ]
    },
    "orange_healthy": {
        "disease": "Healthy Leaf / No Major Disease Detected",
        "severity": "Mild (None)",
        "crop": "Orange (Citrus)",
        "symptoms": [
            "Leaves uniformly glossy dark green, no yellowing, blotches, lesions, or misshapen growth",
            "Healthy leaf structure; no premature abscission, cupping, or vein clearing",
            "Twigs clean with no cankers, gummosis, or dieback; tree canopy full and vigorous",
            "Fruit where present clean, uniform color, no rind blemishes, spots, or abnormal hardening"
        ],
        "causes": [
            "Good citrus orchard sanitation, balanced nutrition, and regular scouting",
            "Inoculum pressure low; no nearby HLB-infected or citrus-canker-positive groves",
            "Adequate soil drainage, proper pH, and well-managed irrigation",
            "Psyllid and leafminer vectors under effective control"
        ],
        "treatment": [
            "Continue weekly orchard scouting for HLB, citrus canker, greasy spot, and scab symptoms",
            "Maintain balanced citrus fertilization with micronutrients (Zn, Mn, Fe, B) and correct soil pH 6.0-6.5",
            "Keep orchard floor clean; remove dropped fruit, prunings, and leaf litter promptly",
            "Apply preventive Copper sprays before rainy periods if canker or greasy spot risk is elevated"
        ],
        "prevention": [
            "Use only certified disease-free citrus nursery stock from registered foundation blocks",
            "Control Asian citrus psyllid (Diaphorina citri) vector with dormant + foliar sprays; coordinate area-wide management",
            "Prune annually to open canopy; remove any suckers, water sprouts, and symptomatic branches immediately",
            "Avoid movement of citrus plant material, budwood, or fruit between orchards without certification",
            "Monitor local citrus disease advisory bulletins and follow regional HLB / canker mitigation protocols"
        ]
    },
    "bell_pepper_bacterial_spot": {
        "disease": "Bacterial Spot (Bell Pepper)",
        "severity": "Moderate to Severe",
        "crop": "Bell Pepper",
        "symptoms": [
            "Leaves: Small water-soaked spots turning dark brown / black with yellow halos; spots may coalesce and cause defoliation",
            "Fruit: Raised, scabby, wart-like brown to tan spots on green and ripe peppers; spots may crack open allowing secondary soft rot",
            "Stems: Elongated dark lesions and cankers; seedling infection causes damping off or stunting",
            "Heavy infection: severe defoliation exposing fruit to sunscald and direct yield loss"
        ],
        "causes": [
            "Bacterial pathogens: Xanthomonas euvesicatoria / X. vesicatoria (T1-T5 races)",
            "Primary source: Infested seed coat and embryo; also overwinters in pepper debris and solanaceous weeds",
            "Spread by rain splash, overhead irrigation, workers hands/clothing, and tools during cultivation/harvest",
            "Favored by warm (24-30°C), wet, windy conditions; 12+ hours leaf wetness; storms and hail cause wounds driving rapid epidemics"
        ],
        "treatment": [
            "Rogue out and destroy heavily infected plants; do not compost",
            "Copper-based bactericides: Copper oxychloride 50% WP (0.25-0.3%) + Mancozeb tank mix every 5-7 days during high pressure",
            "Rotate Copper sprays with fixed Copper / Ethylene-bis-dithiocarbamate combinations to reduce Copper phytotoxicity",
            "Use acibenzolar-S-methyl (ASM / Actigard) as systemic acquired resistance (SAR) inducer every 14 days where available",
            "Reduce leaf wetness duration by switching to drip irrigation; avoid working plants when foliage wet"
        ],
        "prevention": [
            "Use hot-water treated (52°C, 25 min.) or acid-extract-treated certified Xanthomonas-free pepper seed; use fresh seed lots",
            "Treat seed with Copper-based bactericide before planting; do not save seed from infected field",
            "Minimum 3-year crop rotation without pepper/tomato/solanaceous crops in same soil",
            "Raise transplants in clean, sterile media, new trays, insect-proof structures; do not handle transplants when wet",
            "Use plastic or straw mulch to prevent soil splash onto lower leaves; stake plants to keep foliage off ground"
        ]
    },
    "bell_pepper_healthy": {
        "disease": "Healthy Leaf / No Major Disease Detected",
        "severity": "Mild (None)",
        "crop": "Bell Pepper",
        "symptoms": [
            "Leaves uniformly green and glossy; no spots, wilting, or chlorosis",
            "Good leaf structure; no curling, distortion, or necrosis",
            "Plants show good vigor, bushy canopy, and uniform flowering",
            "Fruit development normal; clean blemish-free peppers where present"
        ],
        "causes": [
            "Good agricultural practices including use of clean seed and crop rotation",
            "Weather conditions not conducive to bacterial spot, anthracnose, or powdery mildew",
            "Adequate balanced nutrition and proper irrigation scheduling",
            "Low pathogen inoculum in field due to good previous-season sanitation"
        ],
        "treatment": [
            "Continue scouting 2-3 times weekly for bacterial spot, aphids, thrips, and powdery mildew",
            "Maintain calcium + balanced NPK fertility to prevent blossom-end rot and abiotic issues",
            "Use drip irrigation; avoid overhead sprinklers to keep foliage dry",
            "Keep field perimeter free of solanaceous weeds that may harbor pathogens/pests"
        ],
        "prevention": [
            "Always start with certified, disease-free pepper seed or commercially produced clean transplants",
            "Rotate pepper fields minimum 3 years; do not follow tomato, potato, or tobacco crops",
            "Apply straw or plastic mulch to prevent soil splash and maintain clean fruit",
            "Avoid field work when foliage is wet; sanitize hands/tools between blocks if bacterial spot history",
            "Provide good row spacing and proper staking/support to improve canopy air flow"
        ]
    },
    "potato_early_blight": {
        "disease": "Early Blight (Potato)",
        "severity": "Moderate",
        "crop": "Potato",
        "symptoms": [
            "Lower (older) leaves first: Dark brown to black concentric-ring target spots (2-10 mm)",
            "Yellow chlorotic halos surrounding leaf spots; spots coalesce to blight entire leaflets",
            "Severe cases: large areas of canopy turn brown and die back; premature defoliation and reduced tuber bulking",
            "Stem and tuber lesions rare but may cause dark sunken areas on tubers in storage"
        ],
        "causes": [
            "Fungal pathogen Alternaria solani (primary on potato) + Alternaria alternata",
            "Overwinters on infected potato crop debris, cull piles, infected volunteer potatoes, and solanaceous weeds",
            "Conidia spread by wind and rain splash; infection requires short leaf wetness period (≥3 hrs) at 20-29°C",
            "Favored by warm humid weather, overhead irrigation, soil-phosphorus/potassium deficiency, and plant stress (early season drought, heavy insect pressure)"
        ],
        "treatment": [
            "Remove and destroy infected plant debris after vine kill; deep plow any remaining potato trash",
            "Foliar fungicides: Mancozeb (0.2%) or Chlorothalonil (0.2%) protectant sprays every 7-10 days from canopy closure",
            "Systemic + protectant combinations: Azoxystrobin or Pyraclostrobin (QoI) tank-mixed with Mancozeb where labeled",
            "Begin spray schedule at first symptom appearance or at row closure (whichever is first) if field has EB history",
            "Organic: Copper oxychloride + 5% Neem seed kernel extract at 7-10 day intervals starting early"
        ],
        "prevention": [
            "Practice minimum 3-year crop rotation with non-solanaceous crops (cereals, legumes, mustard, maize)",
            "Use certified disease-free seed potatoes from high-health multiplication program",
            "Balanced NPK fertilization; ensure adequate P and K levels; avoid late-season excess N that delays maturity",
            "Mulch between rows with straw or crop residue to reduce soil splash to lower leaves",
            "Hill up potatoes properly to avoid tuber exposure; keep field free of volunteer potatoes and solanaceous weeds"
        ]
    },
    "potato_late_blight": {
        "disease": "Late Blight (Potato)",
        "severity": "Severe",
        "crop": "Potato",
        "symptoms": [
            "Water-soaked dark green to brownish-black lesions on leaves, rapidly enlarging under humid conditions",
            "White fuzzy sporulation visible on underside of lesions especially in early morning dew (key field diagnostic)",
            "Brown to black stem lesions girdling stems; entire stems and canopy collapse within days in epidemic",
            "Tuber infection: reddish-brown granular dry rot in outer tuber flesh; becomes foul-smelling secondary soft rot in storage"
        ],
        "causes": [
            "Oomycete pathogen Phytophthora infestans (A1 + A2 mating types increasing risk of sexual recombination)",
            "Primary source: Infected seed tubers, volunteer potatoes, cull piles, and nearby infected solanaceous crops",
            "Sporangia spread by wind up to 5-10 km; rain splash wash zoospores down into soil where tubers are infected",
            "Infection favored by cool (10-20°C), wet, windy, >90% RH, prolonged leaf wetness conditions"
        ],
        "treatment": [
            "Vine kill all infected plants with herbicide / flaming if 5%+ of canopy affected in hot-spot patches",
            "Protective fungicides: Mancozeb + Metalaxyl or Mancozeb + Mefenoxam combination products",
            "Curative fungicides: Cymoxanil 8% + Mancozeb 64% WP, or Fluopicolide + Propamocarb, at 2.0-2.5 g/L water; repeat every 5-7 days during conducive weather",
            "Treat seed tubers with fungicide dust (Mancozeb + Metalaxyl) at planting to reduce tuber-borne inoculum",
            "Do not harvest until at least 2-3 weeks after full vine kill to allow tuber skin set and reduce late-blight tuber infection risk"
        ],
        "prevention": [
            "Plant only CERTIFIED SEED POTATO — 100% disease-free stock from inspected multiplication fields; never use farm-saved seed for commercial production",
            "Completely destroy all potato cull piles, compost heaps, and volunteer potatoes around the farm well before planting",
            "Ridging / hilling up potatoes 2-3 times during season to keep tubers well-covered and avoid soil contact with foliage",
            "Use potato late blight forecast / warning systems (e.g., BLITECAST, NegFry) to schedule protectant sprays",
            "Choose late-blight-resistant potato cultivars where available (e.g., Defender, Jacqueline Lee, Bionica, Sarpo family)"
        ]
    },
    "potato_healthy": {
        "disease": "Healthy Leaf / No Major Disease Detected",
        "severity": "Mild (None)",
        "crop": "Potato",
        "symptoms": [
            "Plants uniform, vigorous; leaves uniformly green with no lesions, rings, or yellowing",
            "Good leaf turgor; no wilting, leaf rolling, or necrosis",
            "Even canopy closure; no signs of stem lesions or vascular discoloration",
            "Tubers under ground clean, uniform size, no discoloration or soft rots where inspected"
        ],
        "causes": [
            "Use of certified high-health seed potatoes + good crop rotation",
            "Weather conditions not favorable to late blight, early blight, or viral outbreaks",
            "Balanced NPK, adequate soil moisture, and proper hilling management",
            "Good farm biosecurity: no cull piles / volunteers, clean equipment between fields"
        ],
        "treatment": [
            "Continue regular field scouting 2-3 times weekly through canopy closure to vine senescence",
            "Maintain protective fungicide schedule if weather turns cool and humid",
            "Continue good irrigation scheduling; avoid overwatering in cool cloudy periods",
            "Keep field perimeter and headlands clear of solanaceous weeds and volunteers"
        ],
        "prevention": [
            "Minimum 3-year crop rotation between potato crops on same field; follow cereals or legumes",
            "Plant certified seed potatoes of known high-health status; grade and discard any suspect tubers at planting",
            "Hill up potatoes properly to ensure good tuber coverage and reduce tuber blight risk",
            "Destroy cull piles, volunteer potatoes, and on-farm compost containing potato waste well before planting",
            "Follow local late blight forecast service; apply protectant sprays on a schedule based on disease pressure"
        ]
    },
    "raspberry_healthy": {
        "disease": "Healthy Leaf / No Major Disease Detected",
        "severity": "Mild (None)",
        "crop": "Raspberry",
        "symptoms": [
            "Canes and leaves uniformly vigorous; no spots, blight, or yellow mosaic mottling",
            "Good leaf structure and turgor; no crumbly fruit symptoms where present",
            "Floricanes and primocanes show normal growth and healthy bud development",
            "No signs of cane blight, spur blight, or anthracnose lesions on canes"
        ],
        "causes": [
            "Good raspberry patch management: proper thinning, trellising, and pruning",
            "Weather not favorable to raspberry fungal/bacterial diseases",
            "Well-drained soil with balanced fertility and good irrigation management",
            "Virus-free planting stock maintained in isolated healthy block"
        ],
        "treatment": [
            "Continue weekly scouting for cane spots, yellow rust, Botrytis gray mold, and virus symptoms",
            "Maintain balanced nutrition (avoid excess N) and consistent soil moisture",
            "Remove old floricanes promptly after harvest to improve air flow",
            "If weather turns warm and humid, consider preventive Sulfur or Copper sprays"
        ],
        "prevention": [
            "Start with certified virus-free, tissue-cultured raspberry planting material",
            "Trellis rows to keep canes separated; thin to recommended plant density",
            "Remove and destroy wild brambles (blackberry/raspberry) within 100-300 m of planting",
            "Prune out and remove any canes showing lesions or virus symptoms immediately",
            "Use drip irrigation to keep foliage and fruit dry; avoid over-head watering"
        ]
    },
    "soybean_healthy": {
        "disease": "Healthy Leaf / No Major Disease Detected",
        "severity": "Mild (None)",
        "crop": "Soybean",
        "symptoms": [
            "Plants uniform, vigorous; leaves uniformly green with no spots, blight, or mosaic mottling",
            "Good canopy development; no sudden wilting, stem girdling, or vascular discoloration",
            "Normal flowering and pod development where present; no pod discoloration or shriveling",
            "No signs of frogeye leaf spot, Cercospora, brown spot, or soybean rust pustules"
        ],
        "causes": [
            "Good rotation, seed quality, and balanced fertility program",
            "Weather not favorable to soybean rust, frogeye, or bacterial pustule",
            "Soybean cyst nematode and root rots under control in field",
            "Low inoculum load in the field due to corn-soybean rotation practices"
        ],
        "treatment": [
            "Continue scouting weekly from V2 stage through R6 full seed; monitor for rust, SDS, white mold",
            "Maintain balanced NPK fertility, especially soil pH and Potassium levels",
            "Keep row middles and field borders clean from weed hosts",
            "Apply foliar fungicide only if weather turns highly conducive to disease at R3-R5 stages"
        ],
        "prevention": [
            "Rotate fields minimum 1 year out of soybean (preferably corn-soy rotation); longer if SDS or SCN present",
            "Plant locally-adapted soybean varieties with good disease-resistance package (SCN, SDS, Phytophthora, BSR)",
            "Use quality treated seed: fungicide + inoculant (Bradyrhizobium) + nematicide if field has SCN history",
            "Avoid planting back-to-back soybeans on same field to break residue-borne disease cycles",
            "Ensure proper drainage to avoid prolonged soil saturation and root rot issues"
        ]
    },
    "squash_healthy": {
        "disease": "Healthy Leaf / No Major Disease Detected",
        "severity": "Mild (None)",
        "crop": "Squash / Pumpkin / Cucurbits",
        "symptoms": [
            "Leaves uniformly green, vigorous; no powdery coating, spots, mosaic mottling, or yellowing",
            "Good leaf turgor and structure; no wilting, curling, or premature necrosis",
            "Vines healthy with strong growth; no stem lesions, girdling, or sudden vine collapse",
            "Fruit where present clean, uniform size, no rind spots, rot, or abnormal shape"
        ],
        "causes": [
            "Good rotation, spacing, and balanced nutrition suited to cucurbits",
            "Weather not highly favorable to powdery mildew, downy mildew, or viral mosaic outbreaks",
            "Adequate bee activity for fruit set; consistent moisture via drip irrigation",
            "Low inoculum pressure and effective weed/vector control"
        ],
        "treatment": [
            "Continue scouting 2-3 times weekly for powdery mildew, downy mildew, virus symptoms, and pickleworm",
            "Maintain balanced NPK with Calcium and Magnesium; avoid excess Nitrogen that causes lush susceptible growth",
            "Remove any fallen fruit, old senescent leaves, and crop debris from the plant base regularly",
            "Begin preventive Sulfur / Potassium bicarbonate sprays if weather turns warm, humid, and overcast for several days"
        ],
        "prevention": [
            "Rotate cucurbit crops minimum 2-3 years on same field; follow cereals or legumes, never cucurbit after cucurbit",
            "Use locally adapted disease-resistant/tolerant F1 hybrids; use certified disease-free seed or hot-water treat saved seed",
            "Plant on raised beds with plastic mulch and drip irrigation; avoid overhead sprinklers to keep foliage dry",
            "Space plants properly and trellis vining types to open canopy, improve air flow and spray penetration, and reduce humidity",
            "Destroy all cucurbit weeds and volunteer cucurbit plants within and around field to eliminate inoculum reservoirs"
        ]
    },
    "squash_powdery_mildew": {
        "disease": "Powdery Mildew (Squash / Cucurbits)",
        "severity": "Mild to Moderate",
        "crop": "Squash / Pumpkin / Cucurbits",
        "symptoms": [
            "White to grayish powdery fungal growth on upper (and lower) surfaces of older leaves first",
            "Affected leaves turn yellow, become brittle, and die prematurely; heavy infection causes defoliation exposing fruit to sunburn",
            "Stems and petioles can also develop powdery patches in severe cases",
            "Reduces photosynthesis, fruit size, total yield, and sugar/quality attributes"
        ],
        "causes": [
            "Fungal pathogens Podosphaera xanthii (most common on cucurbits) and Golovinomyces cichoracearum",
            "Obligate parasites; overwinter on alternate hosts and perennial weeds (e.g., pigweed, lambsquarters)",
            "Conidia blown by wind long distances; infection favored by 60-90% RH, moderate temps (20-28°C), dense foliage, and shade",
            "Unlike other fungal diseases, does NOT require free water on leaf surface for infection; 5-8 hours high humidity sufficient"
        ],
        "treatment": [
            "Remove and destroy heavily infected old leaves at base of plant immediately",
            "Sulfur-based products: Wettable Sulfur 0.3% or Dusting Sulfur – do not use when air temp >30°C to avoid phytotoxicity",
            "Systemic / localized systemic fungicides: Myclobutanil, Hexaconazole, or Trifloxystrobin (QoI) rotate with protectants",
            "Organic: Potassium bicarbonate 0.5% spray every 5-7 days or 1% Neem oil emulsion with soap as sticker",
            "Start first spray at earliest sign of mildew (usually lower canopy); repeat every 5-10 days; rotate MOA"
        ],
        "prevention": [
            "Plant PM-tolerant or resistant squash/pumpkin F1 hybrids where seed is available",
            "Avoid crowded plantings; ensure wide row spacing and thinning for good air circulation and light penetration",
            "Avoid excessive nitrogen fertilization that causes soft, lush susceptible vegetative growth",
            "Do not grow cucurbits in same area year after year; rotate with non-cucurbit crops minimum 2 years",
            "Keep field perimeter free of cucurbit weeds and volunteer cucurbits that serve as inoculum reservoirs"
        ]
    },
    "strawberry_leaf_scorch": {
        "disease": "Strawberry Leaf Scorch / Common Leaf Spot",
        "severity": "Mild to Moderate",
        "crop": "Strawberry",
        "symptoms": [
            "Numerous small, round to angular, purple to reddish-brown spots (2-5 mm) on upper leaf surfaces",
            "In advanced stages, spots coalesce and centers may turn gray-brown; entire leaves develop scorched appearance and die back from margins",
            "Unlike leaf spot (Mycosphaerella), scorch lesions usually do not have tan centers with purple borders - instead they are uniformly dark or reddish",
            "Severe defoliation weakens plants, reduces runner production and fruit size / total yield; increases winter injury risk"
        ],
        "causes": [
            "Fungal pathogen Diplocarpon earlianum (anamorph Marssonina fragariae)",
            "Overwinters on infected living and dead strawberry leaves, crowns, and runners in field",
            "Spores (conidia) produced during spring wet periods; spread by rain splash, overhead irrigation, wind, and insects",
            "Infection and disease development favored by warm (20-25°C), wet (>12 hrs leaf wetness), and humid conditions; repeated cycles all season"
        ],
        "treatment": [
            "Apply protective fungicides: Captan, Thiram, or Copper oxychloride starting at early bloom; repeat every 7-14 days through harvest",
            "Systemic fungicides: Tebuconazole, Myclobutanil, or Propiconazole if disease pressure is moderate-severe (rotate with protectants)",
            "Post-harvest sanitation mow-off / removal of all old foliage after renovation reduces overwintering inoculum",
            "Renovation: Narrow rows, remove weeds, subsoils between rows, top-dress with fertilizer after last harvest to renew planting vigor"
        ],
        "prevention": [
            "Plant certified, disease-free strawberry nursery stock in well-drained, sunny, weed-free location",
            "Allow adequate in-row and between-row spacing for air circulation; renovate annually after harvest",
            "Use straw or pine needle mulch between rows; reduces rain splash and keeps fruit cleaner + lower foliage drier",
            "Avoid overhead irrigation; use trickle / drip irrigation to minimize leaf wetness period",
            "Remove all runner plants that root between rows (thickens canopy, increases humidity) unless needed for new plants"
        ]
    },
    "strawberry_healthy": {
        "disease": "Healthy Leaf / No Major Disease Detected",
        "severity": "Mild (None)",
        "crop": "Strawberry",
        "symptoms": [
            "Leaves uniformly green, no leaf scorch spots, powdery growth, or purple lesions",
            "Good leaf turgor and structure; no red stele, black root rot symptoms on crown/roots",
            "Plants vigorous, with well-developed crowns and good runner set where expected",
            "Fruit where present is clean, uniform, free of Botrytis gray mold or leather rot"
        ],
        "causes": [
            "Good strawberry production system: certified plants, mulch, rotation, and renovation",
            "Weather not favoring foliar/fruit disease and root-rotting organisms",
            "Balanced nutrition, proper soil pH, and consistent moisture via drip/mulch",
            "Good field sanitation from previous season renovation"
        ],
        "treatment": [
            "Continue scouting twice weekly during fruiting season for fruit rots, leaf spots, and two-spotted mites",
            "Maintain good irrigation scheduling; avoid overly wet ground especially under plastic mulch",
            "Remove over-ripe and rotting berries promptly from field",
            "If hot humid weather develops, consider preventive Captan/Copper sprays on 7-day schedule"
        ],
        "prevention": [
            "Plant certified, virus-indexed strawberry plants every 1-2 seasons; do not perpetuate plantings indefinitely",
            "Use annual plasticulture or renovate matted-row plantings promptly after last harvest",
            "Maintain straw / pine needle mulch between rows to reduce soil splash onto fruit and leaves",
            "Do not plant strawberry in same soil within 2-3 years; rotate with brassicas, cereals, or sweet corn",
            "Use drip irrigation only; avoid any form of overhead watering where possible"
        ]
    },
    "tomato_bacterial_spot": {
        "disease": "Bacterial Spot (Tomato)",
        "severity": "Moderate to Severe",
        "crop": "Tomato",
        "symptoms": [
            "Leaves: Small water-soaked spots turning dark brown / black with yellow halos; spots coalesce causing defoliation starting from lower canopy",
            "Fruit: Small, raised, dark scabby spots (1-3 mm) on green and ripe tomatoes; spots may crack open allowing Alternaria or soft-rot secondary invasion",
            "Stems: Elongated dark lesions; seedling infection causes leaf necrosis and stunting",
            "Heavy infection causes near total defoliation, exposing fruit to sunscald; severe yield and quality loss"
        ],
        "causes": [
            "Bacterial pathogen Xanthomonas perforans / X. vesicatoria complexes (multiple T-races identified)",
            "Primary source: Infested tomato seed (on seed coat and within endosperm); overwinters on crop debris, solanaceous weeds, volunteer tomatoes",
            "Spread by rain splash, wind-driven rain, overhead sprinklers, worker hands, clothing, and farm equipment",
            "Infection favored by warm (24-30°C), wet, windy weather; hail storms and mechanical damage increase severity"
        ],
        "treatment": [
            "Rogue out heavily infected transplant blocks; do not plant infected seedlings",
            "Copper oxychloride 50% WP (0.25%) + Mancozeb 75% WP (0.2%) tank mix every 5-7 days during periods of high disease pressure",
            "Acibenzolar-S-methyl (Actigard) SAR inducer applied at transplant and every 14 days during early season helps reduce severity",
            "Where registered: Kasugamycin + Copper or Streptomycin + Copper antibiotic-combination sprays rotated to reduce resistance risk",
            "Switch immediately to drip irrigation if currently using overhead sprinklers; stop working field when foliage is wet"
        ],
        "prevention": [
            "Use hot-water treated (50°C, 25 min.) and acid-extract-tested CERTIFIED Xanthomonas-FREE tomato seed from reputable source",
            "Do not save seed from an infected tomato crop; seed-borne inoculum persists for years",
            "Minimum 3-year crop rotation without tomato / pepper / potato / tobacco or any solanaceous crop",
            "Use plastic (preferably reflective silver/aluminum) or straw mulch to prevent soil splash onto lower leaves; stake/cage plants",
            "Sanitize transplant trays, stakes, ties, and equipment between seasons/lots; do not smoke/tobacco while working plants"
        ]
    },
    "tomato_early_blight": {
        "disease": "Early Blight (Tomato)",
        "severity": "Moderate",
        "crop": "Tomato",
        "symptoms": [
            "Dark brown to black spots with concentric bullseye / target rings starting on OLDER (lower) leaves first",
            "Yellow chlorotic halos surround spots; spots often coalesce to form large irregular blighted areas",
            "Stem lesions: Dark, sunken, oval to elongated spots at soil line (collar rot) or on branches leading to breakage",
            "Fruit: Dark leathery sunken spots with concentric rings on stem end; causes fruit drop and rot in storage"
        ],
        "causes": [
            "Fungal pathogen Alternaria solani (primary) + Alternaria alternata (secondary)",
            "Overwinters on infected tomato debris, crop residue, solanaceous weeds (nightshade, horsenettle, Jimsonweed), and volunteer tomatoes",
            "Conidia spread by wind and rain splash; infection requires ≥3 hours leaf wetness at 24-29°C",
            "Favored by overhead irrigation, warm humid nights, plant stress (nutrient deficiency, heavy insect damage, drought), and dense canopies"
        ],
        "treatment": [
            "Remove and destroy all infected lower leaves, crop debris, and volunteer tomato plants immediately",
            "Protective fungicides: Mancozeb 75% WP (0.2%) or Chlorothalonil 75% WP (0.2%) every 7-10 days on a schedule",
            "Systemic + protectant combinations: Azoxystrobin, Pyraclostrobin, or Difenoconazole + Mancozeb tank-mix for high-pressure fields",
            "Start protective spray at fruit-set stage (first green pea-size fruit) or at first symptom (whichever is first)",
            "Organic: 5% Neem seed kernel extract + fixed Copper (0.3%) at 7-10 day schedule starting early"
        ],
        "prevention": [
            "Practice minimum 3-year crop rotation with non-solanaceous crops (cereals, legumes, mustard, corn, cotton)",
            "Use certified disease-free tomato seed and commercial transplants raised under clean conditions",
            "Stake/cage/trellis tomato plants; prune lower suckers to keep foliage off ground and improve air flow",
            "Apply straw mulch or black plastic mulch to prevent soil splash onto lower leaves from rain/irrigation",
            "Balanced NPK fertilization; maintain adequate potassium and calcium; avoid excessive late-season nitrogen application"
        ]
    },
    "tomato_late_blight": {
        "disease": "Late Blight (Tomato)",
        "severity": "Severe",
        "crop": "Tomato",
        "symptoms": [
            "Water-soaked dark green to brown lesions on leaves; rapidly expanding into irregular necrotic patches",
            "White fuzzy sporulation (sporangiophores) visible on UNDERSIDE of fresh lesions during high-humidity dewy mornings",
            "Brown to black stem lesions; entire plant canopy collapses within days during favorable weather",
            "Fruit: Greasy-brown, firm, slightly sunken patches on green and ripe tomatoes; lesions may extend deep into flesh; later invaded by soft-rot bacteria"
        ],
        "causes": [
            "Oomycete pathogen Phytophthora infestans (A1 + A2 mating types present globally, increasing aggressiveness)",
            "Primary inoculum sources: overwintered solanaceous host refuse, contaminated commercial transplants, and susceptible nightshade-family weeds",
            "Sporangia spread by wind up to 5-15 km overnight; zoospores infect leaves/stems/fruit via rain splash and overhead irrigation",
            "Epidemic favored by cool (10-20°C), wet, windy conditions, RH >90%, prolonged leaf wetness, and unprotected canopy"
        ],
        "treatment": [
            "Remove and destroy (bury/burn) all infected plant parts immediately; do not compost infected tomato debris",
            "Protective contact fungicides: Mancozeb (2.0-2.5 g/L) + Chlorothalonil combination every 5-7 days during high risk",
            "Curative systemic fungicides (treat within 24-48 hrs of infection event): Cymoxanil 8% + Mancozeb 64% WP, Fluopicolide + Propamocarb, or Dimethomorph 50% WP",
            "Repeat sprays every 5-7 days during cool wet conducive weather; ensure complete canopy coverage including undersides of leaves",
            "Organic production: Copper oxychloride 50% WP (0.3%) on strict 5-7 day protectant schedule; begin before first symptoms if forecast risky"
        ],
        "prevention": [
            "Use DISEASE-FREE tomato transplants from reputable commercial grower; inspect transplants thoroughly before planting",
            "Grow tomato at maximum possible distance (minimum 1 km) from all other solanaceous field-crop production areas, overwintered crop refuse heaps, and feral regrowth of related host plants",
            "Use wide row spacing, stake/cage plants, prune out extra suckers, and remove lower leaves to improve canopy air flow + spray penetration",
            "Use plastic or straw mulch to prevent soil splash; use ONLY drip irrigation – avoid overhead sprinklers entirely on tomatoes",
            "Follow tomato late blight forecast / advisory services; begin protective Mancozeb sprays BEFORE forecast high-risk infection periods"
        ]
    },
    "tomato_leaf_mold": {
        "disease": "Leaf Mold (Tomato Leaf Mold)",
        "severity": "Moderate",
        "crop": "Tomato",
        "symptoms": [
            "Upper leaf surface: Pale green or yellowish, diffuse, irregularly shaped blotches without distinct borders",
            "Lower leaf surface: Olive-green to brown velvety fungal growth (conidiophores and conidia) beneath the yellow blotches",
            "Spots may coalesce to cover large portions of leaf; severely affected leaves curl, wither, and die",
            "In high humidity: May also infect stems, flowers, and green fruit (rare); reduces fruit size and yield quality"
        ],
        "causes": [
            "Fungal pathogen Fulvia fulva (syn. Cladosporium fulvum / Passalora fulva)",
            "Overwinters on crop debris, seeds, volunteer tomatoes, and greenhouse structures",
            "Spores (conidia) disseminated by air currents, rain splash, workers, tools, and insects",
            "High relative humidity (>85%) inside canopy + moderate temperatures (18-26°C) + leaf wetness drive rapid epidemic development; severe in greenhouse / high tunnels"
        ],
        "treatment": [
            "Remove and destroy all infected leaves, crop debris, and volunteer tomato plants at end of season",
            "Apply fungicides at symptom onset: Chlorothalonil (protectant), Mancozeb, or Copper oxychloride at 7-10 day interval",
            "Systemic fungicides (Difenoconazole or Myclobutanil) for curative / kick-back action where available",
            "Reduce humidity: Increase ventilation, use fans, avoid overwatering late in day; apply to drip if possible",
            "Plant spacing + pruning + leaf removal around fruit trusses to improve air flow and lower canopy RH"
        ],
        "prevention": [
            "Use resistant tomato varieties (many available with Cf resistance genes: Cf-2, Cf-4, Cf-5, Cf-9 etc.)",
            "Hot-water seed treatment (50°C for 25 min.) or fungicide seed treatment to eliminate seed-borne inoculum",
            "Crop rotation 2-3 years between solanaceous crops; avoid planting after tomatoes / potatoes in same soil",
            "In greenhouse: Decontaminate all surfaces with bleach or commercial disinfectant between crops",
            "Maintain RH below 85% in canopy; heat + ventilate in early morning to remove dew from leaves"
        ]
    },
    "tomato_septoria_leaf_spot": {
        "disease": "Septoria Leaf Spot (Septoria Blight)",
        "severity": "Moderate",
        "crop": "Tomato",
        "symptoms": [
            "Small, numerous (1-3 mm) circular spots with dark brown borders and grayish-tan centers on lower leaves",
            "Tiny black fruiting bodies (pycnidia) visible with hand lens in centers of mature spots",
            "Yellowing (chlorosis) of leaf tissue surrounding spots; affected leaflets wither, curl, turn brown, and drop",
            "Defoliation progresses from bottom of plant upward; exposes fruit to sunburn; reduces yield and quality substantially"
        ],
        "causes": [
            "Fungal pathogen Septoria lycopersici",
            "Overwinters on infected tomato debris, crop residue, solanaceous weeds (nightshade, jimsonweed, horsenettle), and infected seed",
            "Spores splash from soil / debris to lower leaves; spread by rain, overhead irrigation, workers, and equipment",
            "Infection favored by warm (20-25°C), wet, and humid conditions; 48+ hours of leaf wetness needed; 5 to 10 day latent period"
        ],
        "treatment": [
            "Remove and burn / bury affected lower leaves and infected crop debris at end of season",
            "Apply protective fungicides: Chlorothalonil, Mancozeb, or Copper oxychloride every 7-10 days",
            "Start spraying when first spots appear (usually on lowest leaves) or after fruit set; continue through harvest",
            "Rotate fungicide modes of action to avoid resistance development",
            "Organic options: Fixed Copper products (Bordeaux, COC), Bacillus subtilis biofungicides, or 5% Neem seed kernel extract"
        ],
        "prevention": [
            "Use pathogen-free seed; hot water seed treatment: 50°C for 25-30 minutes",
            "Practice 2-3 year crop rotation with non-host (non-solanaceous) crops",
            "Plastic or organic straw mulch to prevent soil splash onto lower leaves from rain/irrigation",
            "Stake or cage tomatoes; prune basal suckers to keep foliage off soil and improve air circulation",
            "Avoid overhead watering and working in field when foliage is wet; remove solanaceous weeds"
        ]
    },
    "tomato_spider_mites": {
        "disease": "Spider Mite Damage (Two-Spotted Spider Mite)",
        "severity": "Moderate to Severe",
        "crop": "Tomato",
        "symptoms": [
            "Leaves: Small yellow to white stippled (speckled) appearance on upper surface from mite feeding on leaf sap",
            "Heavy infestation: Leaves turn pale yellow or bronze, wilt, and may dry up; fine silk webbing visible on undersides and between leaflets",
            "Eggs: Tiny round translucent spheres on lower leaf surfaces near veins; cast skins (white) accumulate",
            "Fruit: Exposed fruit may develop sunscald due to premature defoliation; reduced size, poor color, and lower sugars"
        ],
        "causes": [
            "Two-spotted spider mite - Tetranychus urticae (Acari: Tetranychidae) - tiny arachnid, not an insect",
            "Overwinters as adults in soil debris, crop residues, weeds, field margins; reproduce extremely rapidly (>10 generations/season)",
            "Favored by hot, dry, dusty conditions (28-32°C, <60% RH); populations build explosively during drought stress",
            "Often flare up after broad-spectrum insecticides kill natural enemies (predatory mites, ladybugs, lacewing larvae)"
        ],
        "treatment": [
            "Miticides (acaricides): Abamectin, Spiromesifen, Fenpyroximate, Propargite, or Wettable Sulfur dust (below 30°C)",
            "Rotate miticide chemical groups (MOA) strictly to prevent rapid resistance; target all life stages (eggs, larvae, adults)",
            "High-volume, high-pressure spray coverage is essential - ensure undersides of all leaves thoroughly wet; include surfactant",
            "Release commercially available predatory mites (Phytoseiulus persimilis, Neoseiulus californicus) early for bio-control in low-moderate pressure",
            "Organic options: 1-2% Neem oil emulsion, insecticidal soap (potassium salts of fatty acids), or horticultural oil (dormant/summer)"
        ],
        "prevention": [
            "Conserve natural enemies: Avoid / reduce broad-spectrum insecticides (Pyrethroids, Organophosphates) that kill beneficials",
            "Overhead irrigation or sprinkling of water increases humidity and disrupts mite reproduction and webbing",
            "Clean cultivation: Remove weeds (especially pigweed, morning glory, lambsquarters) around field edges that serve as alternate hosts",
            "Monitor weekly by inspecting lower leaf surfaces with 10-20x magnifier; take action when 3-5 mites/leaf average",
            "Avoid excessive nitrogen fertilization - promotes soft lush growth favorable to mites; maintain adequate irrigation to reduce drought stress"
        ]
    },
    "tomato_target_spot": {
        "disease": "Target Spot / Corynespora Leaf Spot",
        "severity": "Moderate",
        "crop": "Tomato",
        "symptoms": [
            "Circular to slightly irregular brown lesions (2-15 mm) with distinct concentric (target-like) rings on leaves",
            "Yellow halos often surround spots; older lesions may crack, tear, or drop out giving shot-hole appearance",
            "Stem lesions: Elongated, slightly sunken; can cause girdling and breakage in severe cases",
            "Fruit: Sunken dark spots with concentric rings on green and ripe fruit; secondary rot (soft) may follow, rendering fruit unmarketable"
        ],
        "causes": [
            "Fungal pathogen Corynespora cassiicola",
            "Overwinters as mycelium, chlamydospores, or conidia in crop debris, weeds, and on seed coat",
            "Infection occurs through stomata or direct penetration; 24-72 hours high humidity / leaf wetness at 22-28°C required",
            "Favored by warm, humid, rainy periods; dense plantings, poor air movement, excessive nitrogen, and stressed plants"
        ],
        "treatment": [
            "Remove and destroy all infected leaves, dropped fruit, and plant debris after harvest",
            "Apply protective fungicides: Mancozeb, Chlorothalonil, or Copper oxychloride (0.3%) every 7-10 days",
            "Systemic fungicides with good efficacy: Difenoconazole, Tebuconazole, or Pyraclostrobin (QoI) tank-mixed with protectant",
            "Begin spray at fruit set or first symptom appearance; continue on schedule if warm wet conditions persist",
            "Ensure thorough coverage with sufficient water volume and appropriate nozzle pressure"
        ],
        "prevention": [
            "Use clean seed or treat seed with fungicide (Thiram + Carbendazim combination) before sowing",
            "Implement 3-year crop rotation with non-host crops like cereals, grasses, or mustard family crops",
            "Optimize plant density and use staking/caging for tomatoes to reduce humidity within canopy",
            "Avoid overhead irrigation late in day; apply through drip; allow morning dew to evaporate quickly",
            "Control weeds; maintain balanced fertilization; maintain general field sanitation"
        ]
    },
    "tomato_tomato_yellow_leaf_curl": {
        "disease": "Tomato Yellow Leaf Curl Virus (TYLCV)",
        "severity": "Severe",
        "crop": "Tomato",
        "symptoms": [
            "Newly emerging leaves: Strong upward cupping/curling, bright yellowing along margins, and reduced leaflet size",
            "Leaves develop thick, leathery texture; interveinal chlorosis with deep green veins remaining prominent",
            "Plants severely stunted; excessive branching and erect bushy appearance; flowering is drastically reduced and fruit set poor",
            "Fruit that does set is small, ripens unevenly, and is of low market value; yield losses 70-100% if infected early"
        ],
        "causes": [
            "Single-stranded circular DNA Geminivirus: Tomato yellow leaf curl virus (Begomovirus, family Geminiviridae)",
            "Transmitted exclusively by sweet potato / silverleaf whitefly (Bemisia tabaci biotype B) in persistent-circulative manner; NOT by seed or mechanical contact",
            "Acquisition: 15-30 min. feeding by adult whitefly on infected plant; latent period 6-20 hrs; then transmits for remainder of life (20-30 days)",
            "Favored by high whitefly populations, warm weather (25-32°C), proximity to virus reservoirs (weeds, old tomato fields, greenhouse crops, ornamentals)"
        ],
        "treatment": [
            "No cure for virus-infected plants - UPROOT AND BURY all visibly infected plants immediately to eliminate virus source",
            "Strict WHITEFLY VECTOR MANAGEMENT is critical: apply Insecticides (Imidacloprid, Thiamethoxam, Spiromesifen, Pyriproxyfen) rotating modes of action",
            "Reflective (silver/aluminum) mulch at transplanting REPELS whiteflies (reduces early infections by 70-85%); remove when plants cover >80% ground",
            "Install fine-mesh (40-50 mesh) insect-proof netting/row covers over seedbeds and young plants during first 4-6 weeks after transplant",
            "Remove all weeds and alternate host plants (nightshade, Jimsonweed, Datura, Malva, Amaranthus) within and around tomato fields / greenhouse"
        ],
        "prevention": [
            "PLANT TYLCV-RESISTANT / TOLERANT TOMATO HYBRIDS (most effective single control strategy): Many available with Ty-1, Ty-2, Ty-3 resistance genes",
            "Area-wide / community coordinated whitefly management program; all farmers in area must participate",
            "Transplant only whitefly-free, TYLCV-free seedlings raised in insect-proof nurseries with netting + sticky yellow traps inside",
            "Respect crop-free periods of at least 2-3 months; remove all tomato debris, volunteers, and solanaceous weeds",
            "Monitor weekly: Yellow sticky traps (30 cm x 30 cm, 10/ha) positioned just above canopy; inspect undersides of newest leaves for whitefly adults/nymphs"
        ]
    },
    "tomato_tomato_mosaic_virus": {
        "disease": "Tomato Mosaic Virus (ToMV) / Tobacco Mosaic (TMV) on Tomato",
        "severity": "Moderate to Severe",
        "crop": "Tomato",
        "symptoms": [
            "Leaves: Alternating light and dark green mosaic/mottling pattern; leaflet narrowing (fernleaf), puckering, and downward curling",
            "Severe strains: Necrotic streaks on stems and petioles ('brown streak'); brown internal browning of fruit",
            "Fruit: Uneven ripening, yellow blotches, internal browning, reduced size, and deformities; sunburn can occur due to poor foliage cover",
            "Overall plant: Stunting, reduced vigor, poor fruit set; yield loss depends on time of infection (earlier = more severe)"
        ],
        "causes": [
            "Positive-sense single-stranded RNA virus: Tobacco mosaic virus (TMV) and Tomato mosaic virus (ToMV), genus Tobamovirus",
            "Easily spread MECHANICALLY by hands, tools, clothing, pruning / tying equipment during normal farm operations (virus is very stable outside host)",
            "Also transmitted by contaminated SEED (external on seed coat); can survive many years in dried plant debris and tobacco products (cigarettes, etc.)",
            "Favored by dense plantings, repeated handling of plants, contaminated tools; no insect vector required for transmission"
        ],
        "treatment": [
            "NO CURE for infected plants. Uproot, bag, and remove/incinerate ALL infected plants as soon as symptoms appear",
            "DISINFECT ALL TOOLS, HANDS, CLOTHING, STAKES, STRING, EQUIPMENT thoroughly between rows and especially after touching infected plants: use 20% Non-fat dry milk solution, 10% household bleach, or commercial disinfectant",
            "Work infected rows LAST; after completing healthy rows. Do not smoke / use tobacco products while working in tomato field; wash hands with soap and milk before entering",
            "Remove and destroy all infected crop debris; do NOT compost; solanaceous weeds around perimeter must be removed",
            "Maintain balanced nutrition and irrigation to maximize plant vigor and tolerance; avoid excessive nitrogen"
        ],
        "prevention": [
            "Use VIRUS-TESTED, CERTIFIED DISEASE-FREE SEED from reliable source; Tm-2^2 resistant varieties are available",
            "Seed disinfestation: 10% Trisodium phosphate (Na3PO4) soak for 15-30 minutes followed by thorough rinsing, or hot-water 50°C for 30 min. to inactivate virus on seed coat",
            "Crop rotation minimum 2 years, preferably 3-4 years between solanaceous crops in same field",
            "Minimum 2 years before re-using stakes, string, and other tomato field infrastructure (or decontaminate thoroughly)",
            "Do NOT plant solanaceous crops (eggplant, pepper, tobacco, potato) in rotation before tomatoes if ToMV/TMV history exists"
        ]
    },
    "tomato_healthy": {
        "disease": "Healthy Leaf / No Major Disease Detected",
        "severity": "Mild (None)",
        "crop": "Tomato",
        "symptoms": [
            "Leaves uniformly green, no spots, rings, wilting, curling, or mosaic mottling",
            "Good leaf turgor and structure; no yellowing, necrosis, or premature senescence",
            "Vigorous healthy growth, strong stems, good fruit set where present",
            "Fruit clean, uniform, free of blossom-end rot, sunscald, or spots"
        ],
        "causes": [
            "Good tomato IPM program, crop rotation, and resistant variety selection",
            "Weather conditions not favoring late/early blight, bacterial spot, or virus spread",
            "Balanced nutrition (NPK + Ca + Mg) and proper moisture via drip irrigation",
            "Low disease inoculum, clean seed/transplants, and good field sanitation"
        ],
        "treatment": [
            "Continue scouting 2-3 times weekly throughout fruiting season for foliar diseases, insects, and virus symptoms",
            "Maintain balanced fertilization; monitor calcium levels to prevent blossom-end rot on fruit",
            "Keep field free from weeds around row middles and perimeter",
            "If weather turns cool and humid, begin protective Mancozeb/Copper sprays on 7-day schedule"
        ],
        "prevention": [
            "Start with CERTIFIED DISEASE-FREE tomato seed or commercial transplants; do not save seed from problem fields",
            "Follow minimum 3-year crop rotation with non-solanaceous crops (cereals, legumes, brassicas, corn)",
            "Stake/cage/trellis all tomatoes; keep canopy off ground; prune suckers for good air flow",
            "Use reflective silver aluminum mulch or straw mulch to reduce soil splash and repel whiteflies/aphids",
            "DRIP IRRIGATION ONLY; avoid any overhead sprinkler irrigation that wets tomato foliage"
        ]
    },
    "healthy": {
        "disease": "Healthy Leaf / No Major Disease Detected",
        "severity": "Mild (None)",
        "crop": "General",
        "symptoms": [
            "Leaf appears green and vigorous",
            "No major lesions, spots, or abnormal discoloration observed",
            "Good leaf turgor and structure",
            "Plant appears healthy overall"
        ],
        "causes": [
            "Good agronomic management",
            "Favorable weather conditions",
            "Adequate nutrition and irrigation",
            "No disease pressure currently"
        ],
        "treatment": [
            "Continue regular crop monitoring at least twice a week",
            "Maintain balanced fertilization and irrigation schedule",
            "Good field sanitation practices",
            "Consider preventive organic sprays (Neem-based) if disease risk exists"
        ],
        "prevention": [
            "Maintain field hygiene; remove weeds and debris",
            "Follow recommended crop rotation schedule",
            "Use certified disease-free seeds",
            "Monitor weather and apply prophylactic measures if conducive conditions expected",
            "Ensure proper plant spacing for air circulation"
        ]
    }
}


def _get_current_user_optional():
    async def _getter(current_user: dict | None = Depends(lambda token = Depends(router.dependency_overrides_provider.get("oauth2_scheme")): (decode_access_token(token) and get_user_collection().find_one(ObjectId(decode_access_token(token).get("user_id")))) if token else None)):
        return current_user
    return _getter


async def _optional_auth(token: Optional[str] = Depends(__import__("auth_utils", fromlist=["oauth2_scheme"]).oauth2_scheme)):
    if not token:
        return None
    from auth_utils import decode_access_token
    payload = decode_access_token(token)
    if payload is None:
        return None
    user_id = payload.get("user_id")
    if not user_id:
        return None
    try:
        from bson import ObjectId
        from database import get_user_collection
        oid = ObjectId(user_id)
        database_started = time.perf_counter()
        user = await get_user_collection().find_one({"_id": oid})
        logger.info(
            "Disease timing stage=optional_auth_database elapsed_ms=%.1f",
            (time.perf_counter() - database_started) * 1000,
        )
        if user:
            user["_id"] = str(user["_id"])
            if "password" in user:
                del user["password"]
        return user
    except Exception:
        logger.exception("Disease optional-auth lookup failed.")
        return None


@router.post("/detect")
async def detect_disease(
    image: UploadFile = File(...),
    crop: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    x_language: Optional[str] = Header(default="en", alias="X-Language"),
    _current_user: dict | None = Depends(_optional_auth),
):
    request_started = time.perf_counter()
    try:
        response_language = resolve_language(language or x_language)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=localized_message("en", "invalid_language"),
        )

    content_type = (image.content_type or "").split(";", 1)[0].strip().lower()
    if content_type not in SUPPORTED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=localized_message(response_language, "invalid_image"),
        )

    try:
        image_read_started = time.perf_counter()
        contents = await image.read(MAX_DISEASE_IMAGE_BYTES + 1)
        image_read_elapsed_ms = round((time.perf_counter() - image_read_started) * 1000, 1)
        if len(contents) > MAX_DISEASE_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=localized_message(response_language, "image_too_large"),
            )
        if not contents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=localized_message(response_language, "invalid_image"),
            )
        image_size_kb = len(contents) / 1024

        analysis_id = uuid.uuid4().hex
        fingerprint_started = time.perf_counter()
        image_fingerprint = hashlib.sha256(contents).hexdigest()
        fingerprint_elapsed_ms = round((time.perf_counter() - fingerprint_started) * 1000, 1)
        timestamp_utc = datetime.utcnow().isoformat() + "Z"

        quality_started = time.perf_counter()
        quality = assess_image_quality(contents, include_decoded_rgb=True)
        quality_elapsed_ms = round((time.perf_counter() - quality_started) * 1000, 1)
        if not quality.get("ok"):
            err_type = quality.get("error_type", "low_quality")
            error_key = "invalid_image" if "invalid" in str(err_type).lower() else "low_quality"
            err_msg = localized_message(response_language, error_key)
            return JSONResponse(status_code=422, content={
                "success": False,
                "error": err_msg,
                "error_type": err_type,
                "image_info": {
                    "filename": image.filename,
                    "content_type": image.content_type,
                    "size_kb": round(image_size_kb, 2),
                    "width": quality.get("width"),
                    "height": quality.get("height"),
                    "sha256": image_fingerprint,
                },
                "analysis_id": analysis_id,
                "image_fingerprint": image_fingerprint,
                "performance": {
                    "quality_ms": quality_elapsed_ms,
                    "inference_ms": 0.0,
                    "total_ms": round((time.perf_counter() - request_started) * 1000, 1),
                },
                "analyzed_at": timestamp_utc,
            })

        expected_format = SUPPORTED_IMAGE_TYPES[content_type]
        if quality.get("format") != expected_format:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=localized_message(response_language, "image_type_mismatch"),
            )

        inference_started = time.perf_counter()
        ai_result = None
        try:
            decoded_rgb = quality.get("_decoded_rgb")
            if decoded_rgb is None:
                ai_result = await detect_crop_disease(
                    contents, crop or "", response_language, content_type
                )
            else:
                ai_result = await detect_crop_disease(
                    contents,
                    crop or "",
                    response_language,
                    content_type,
                    decoded_rgb=decoded_rgb,
                )
        except Exception:
            logger.exception("Disease analysis service call failed")
            ai_result = {
                "ok": False,
                "error": localized_message(response_language, "disease_analysis_failed"),
                "error_type": "service_error",
            }
        inference_elapsed_ms = round((time.perf_counter() - inference_started) * 1000, 1)
        analysis_timing = (
            ai_result.pop("_timing_ms", {})
            if isinstance(ai_result, dict)
            else {}
        )

        # Local model results are accepted only for supported, confident classes
        # with an exact crop-specific knowledge entry. Ambiguous predictions are
        # returned as uncertainty; no mock or cross-crop recommendation is used.
        if isinstance(ai_result, dict) and not ai_result.get("ok"):
            reuse_hint = ai_result.get("_model_prediction_fallback_hint")
            extra_note = ""
            if isinstance(reuse_hint, dict):
                hint_crop = reuse_hint.get("crop") or "Unknown crop"
                hint_disease = reuse_hint.get("disease") or "Unknown disease"
                extra_note = (
                    " (Note: a local image model produced a preliminary, unverified reference hint — "
                    f"{hint_crop} potentially showing {hint_disease} — but this was NOT independently confirmed "
                    "by the primary visual analysis engine. Please retry with a clearer photo or consult an expert.)"
                )
            original_error = ai_result.get("error") or "Visual analysis could not be completed."
            if extra_note and "unable to determine disease" in original_error.lower():
                ai_result["error"] = original_error.rstrip() + extra_note

        if not ai_result or not isinstance(ai_result, dict):
            return JSONResponse(status_code=503, content={
                "success": False,
                "error": localized_message(response_language, "disease_result_empty"),
                "error_type": "service_unavailable",
                "image_info": {
                    "filename": image.filename,
                    "content_type": image.content_type,
                    "size_kb": round(image_size_kb, 2),
                    "sha256": image_fingerprint,
                },
                "analysis_id": analysis_id,
                "image_fingerprint": image_fingerprint,
                "analyzed_at": timestamp_utc,
            })

        if not ai_result.get("ok"):
            fallback_hint = ai_result.get("_model_prediction_fallback_hint")
            extra_note = ""
            if isinstance(fallback_hint, dict):
                hint_crop = fallback_hint.get("crop") or "Unknown crop"
                hint_disease = fallback_hint.get("disease") or "Unknown disease"
                hint_cc = round(float(fallback_hint.get("crop_confidence") or 0.0), 1)
                hint_dc = round(float(fallback_hint.get("disease_confidence") or 0.0), 1)
                extra_note = (
                    f" [Local image-model reference: {hint_crop} ({hint_cc}% crop confidence) → {hint_disease} "
                    f"({hint_dc}% disease confidence). No locally curated crop/disease combination could be fully verified; "
                    f"please try a clearer close-up or consult an extension officer.]"
                )
            error_type = str(ai_result.get("error_type") or "")
            message_key = {
                "gemini_auth_error": "disease_auth_error",
                "gemini_invalid_key": "disease_auth_error",
                "gemini_permission_denied": "disease_auth_error",
                "gemini_quota_exceeded": "disease_quota_error",
                "gemini_rate_limited": "disease_rate_limited",
                "gemini_model_unavailable": "disease_model_error",
                "gemini_model_not_found": "disease_model_error",
                "gemini_sdk_incompatible": "disease_configuration_error",
                "gemini_timeout": "ai_timeout",
                "gemini_request_rejected": "disease_processing_error",
                "gemini_provider_unavailable": "disease_provider_unavailable",
                "gemini_provider_error": "disease_provider_unavailable",
                "gemini_provider_busy": "disease_provider_unavailable",
                "gemini_api_key_missing": "disease_configuration_error",
                "model_unavailable": "disease_model_unavailable",
                "class_mapping_mismatch": "disease_model_unavailable",
                "service_error": "disease_processing_error",
                "service_failure": "disease_processing_error",
            }.get(error_type)
            if not message_key:
                message_key = (
                    "unsupported_crop" if "unsupported" in error_type
                    else "low_quality" if "quality" in error_type or "blur" in error_type
                    else "non_plant" if "non_plant" in error_type
                    else "invalid_image" if "image_invalid" in error_type
                    else "disease_unavailable"
                )
            base_error = localized_message(response_language, message_key)
            local_model_status = ai_result.pop("_local_model_status", None)
            if local_model_status == "unavailable":
                base_error = (
                    f"{base_error} "
                    f"{localized_message(response_language, 'disease_model_unavailable')}"
                )
            http_status = (
                status.HTTP_503_SERVICE_UNAVAILABLE
                if error_type.startswith(("gemini_", "model_", "service_"))
                or error_type in {"class_mapping_mismatch", "service_unavailable"}
                else status.HTTP_422_UNPROCESSABLE_ENTITY
            )
            error_response = {
                "success": False,
                "error": base_error,
                "error_type": ai_result.get("error_type"),
                "image_info": {
                    "filename": image.filename,
                    "content_type": image.content_type,
                    "size_kb": round(image_size_kb, 2),
                },
                "performance": {
                    "image_read_ms": image_read_elapsed_ms,
                    "fingerprint_ms": fingerprint_elapsed_ms,
                    "quality_ms": quality_elapsed_ms,
                    "inference_ms": inference_elapsed_ms,
                    "disease_analysis_ms": analysis_timing.get("disease_analysis_ms"),
                    "model_initialization_ms": analysis_timing.get("model_initialization_ms"),
                    "image_preprocessing_ms": analysis_timing.get("image_preprocessing_ms"),
                    "model_inference_ms": analysis_timing.get("model_inference_ms"),
                    "external_ai_ms": analysis_timing.get("external_ai_ms"),
                    "explanation_ms": analysis_timing.get("explanation_ms"),
                    "translation_ms": analysis_timing.get("translation_ms"),
                    "total_ms": round((time.perf_counter() - request_started) * 1000, 1),
                },
                "analyzed_at": datetime.utcnow().isoformat() + "Z",
            }
            if local_model_status == "unavailable":
                error_response["local_model_status"] = local_model_status
            return JSONResponse(status_code=http_status, content=error_response)

        chosen = ai_result

        if isinstance(chosen, dict):
            symptoms = chosen.get("symptoms")
            if not isinstance(symptoms, list) or len(symptoms) == 0:
                chosen["symptoms"] = [
                    localized_message(response_language, "symptoms_unavailable")
                ]
            mgmt = chosen.get("treatment") or chosen.get("recommended_management")
            if not isinstance(mgmt, list) or len(mgmt) == 0:
                generic = (
                        localized_message(response_language, "disease_unavailable")
                    )
                chosen["recommended_management"] = [generic]
                chosen["treatment"] = [generic]
            if not chosen.get("possible_causes") and chosen.get("causes"):
                chosen["possible_causes"] = list(chosen["causes"])
            if not chosen.get("recommended_management") and chosen.get("treatment"):
                chosen["recommended_management"] = list(chosen["treatment"])

        return {
            "success": True,
            "result": chosen,
            "image_info": {
                "filename": image.filename,
                "content_type": image.content_type,
                "size_kb": round(image_size_kb, 2),
            },
            "performance": {
                "image_read_ms": image_read_elapsed_ms,
                "fingerprint_ms": fingerprint_elapsed_ms,
                "quality_ms": quality_elapsed_ms,
                "inference_ms": inference_elapsed_ms,
                "disease_analysis_ms": analysis_timing.get("disease_analysis_ms"),
                "model_initialization_ms": analysis_timing.get("model_initialization_ms"),
                "image_preprocessing_ms": analysis_timing.get("image_preprocessing_ms"),
                "model_inference_ms": analysis_timing.get("model_inference_ms"),
                "external_ai_ms": analysis_timing.get("external_ai_ms"),
                "explanation_ms": analysis_timing.get("explanation_ms"),
                "translation_ms": analysis_timing.get("translation_ms"),
                "total_ms": round((time.perf_counter() - request_started) * 1000, 1),
            },
            "analyzed_at": datetime.utcnow().isoformat() + "Z",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected crop-disease route failure")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": localized_message(response_language, "disease_server_error"),
                "error_type": "server_error",
            },
        )
    finally:
        logger.info(
            "Disease timing stage=request language=%s image_read_ms=%.1f fingerprint_ms=%.1f "
            "quality_ms=%.1f analysis_ms=%.1f total_ms=%.1f",
            response_language,
            locals().get("image_read_elapsed_ms", 0.0),
            locals().get("fingerprint_elapsed_ms", 0.0),
            locals().get("quality_elapsed_ms", 0.0),
            locals().get("inference_elapsed_ms", 0.0),
            (time.perf_counter() - request_started) * 1000,
        )

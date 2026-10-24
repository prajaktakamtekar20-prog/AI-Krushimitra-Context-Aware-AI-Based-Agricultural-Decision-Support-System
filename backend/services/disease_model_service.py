import os
import json
import io
import logging
import math
import threading
import time
from typing import Dict, List, Set, Tuple, Any, Optional

try:
    import numpy as np  # type: ignore
    _NUMPY_AVAILABLE = True
except Exception:
    _NUMPY_AVAILABLE = False

try:
    from PIL import Image  # noqa: F401  # type: ignore
    _PIL_AVAILABLE = True
except Exception:
    _PIL_AVAILABLE = False

try:
    import tensorflow as tf  # type: ignore  # noqa: F401
    _TF_AVAILABLE = True
    _TF_IMPORT_ERROR: Optional[str] = None
except Exception as exc:
    _TF_AVAILABLE = False
    _TF_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "plant_disease_mobilenetv2.keras")
CLASS_NAMES_PATH = os.path.join(MODEL_DIR, "class_names.json")
INFERENCE_CONFIG_PATH = os.path.join(MODEL_DIR, "inference_config.json")

_model = None
_class_names = None
_model_initialization_lock = threading.Lock()
_model_inference_lock = threading.Lock()
_crop_name_map: Optional[Dict[str, str]] = None
_valid_crop_diseases: Optional[Dict[str, Set[str]]] = None
_class_crop_raw_map: Optional[List[str]] = None
_class_disease_raw_map: Optional[List[str]] = None
_use_mock_predictor: bool = False
_inference_config: Optional[Dict[str, Any]] = None
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Model input: RGB 224x224 in the 0-255 range. The saved graph contains the
# MobileNetV2 preprocessing operations, so inference must not normalize twice.
IMG_SIZE = (224, 224)

CROP_NAME_MAP: Dict[str, str] = {
    "Corn (maize)": "Corn (Maize)",
    "Pepper, bell ": "Bell Pepper",
    "Pepper, bell": "Bell Pepper",
    "Cherry (including sour)": "Cherry",
    "Soybean": "Soybean",
    "Squash": "Squash",
    "Raspberry": "Raspberry",
    "Blueberry": "Blueberry",
    "Apple": "Apple",
    "Grape": "Grape",
    "Orange": "Orange (Citrus)",
    "Peach": "Peach",
    "Potato": "Potato",
    "Strawberry": "Strawberry",
    "Tomato": "Tomato",
}

ERROR_NON_PLANT = "Please upload a clear image of a crop or plant leaf."
ERROR_LOW_CROP_CONF = "Crop could not be identified confidently. Please upload a clearer crop or leaf image."
ERROR_LOW_DISEASE_CONF = "Disease could not be detected confidently. Please upload a clearer image of the affected leaf."
ERROR_UNSUPPORTED_CROP = (
    "This crop is not supported by the current PlantVillage MobileNetV2 model. "
    "A compatible model and labeled training images are required for this crop."
)
ERROR_INVALID_COMBO = "Crop and disease combination could not be validated. Please try a clearer image."
ERROR_DB_VALIDATION = "Crop and disease information could not be validated. Please upload a clearer image."
ERROR_UNCERTAIN = (
    "The model is not confident enough to name a disease. A high score on an unsupported "
    "crop is not a diagnosis. Please use a supported crop, a clearer photo, or consult local extension."
)
ERROR_MODEL_UNAVAILABLE = (
    "The on-device disease model is not available on this server (TensorFlow/Keras failed to load). "
    "Predictions will not be fabricated."
)

CROP_KEY_MAP: Dict[str, str] = {
    "Apple": "apple",
    "Blueberry": "blueberry",
    "Cherry": "cherry",
    "Corn (Maize)": "corn",
    "Grape": "grape",
    "Orange (Citrus)": "orange",
    "Peach": "peach",
    "Bell Pepper": "bell_pepper",
    "Potato": "potato",
    "Raspberry": "raspberry",
    "Soybean": "soybean",
    "Squash": "squash",
    "Strawberry": "strawberry",
    "Tomato": "tomato",
}

# Farmer-profile / UI aliases mapped onto model display names.
DECLARED_CROP_ALIASES: Dict[str, str] = {
    "apple": "Apple",
    "blueberry": "Blueberry",
    "cherry": "Cherry",
    "corn": "Corn (Maize)",
    "maize": "Corn (Maize)",
    "corn (maize)": "Corn (Maize)",
    "grape": "Grape",
    "grapes": "Grape",
    "orange": "Orange (Citrus)",
    "citrus": "Orange (Citrus)",
    "orange (citrus)": "Orange (Citrus)",
    "peach": "Peach",
    "pepper": "Bell Pepper",
    "bell pepper": "Bell Pepper",
    "bell_pepper": "Bell Pepper",
    "potato": "Potato",
    "raspberry": "Raspberry",
    "soybean": "Soybean",
    "squash": "Squash",
    "strawberry": "Strawberry",
    "tomato": "Tomato",
}


def load_inference_config() -> Dict[str, Any]:
    global _inference_config
    if _inference_config is not None:
        return _inference_config
    defaults = {
        "min_top1_confidence": 55.0,
        "min_margin_pp": 18.0,
        "min_crop_mass": 60.0,
        "max_softmax_entropy": 2.2,
        "uncertain_top1_confidence": 70.0,
        "non_plant_max_conf": 22.0,
        "min_image_side": 64,
        "min_laplacian_variance": 12.0,
        "min_mean_brightness": 12.0,
        "max_mean_brightness": 245.0,
    }
    try:
        with open(INFERENCE_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        thresholds = raw.get("thresholds") or {}
        defaults.update({k: thresholds[k] for k in defaults if k in thresholds})
    except Exception:
        pass
    _inference_config = defaults
    return _inference_config


def _normalize_name_component(name: str) -> str:
    cleaned = name.strip().lower()
    cleaned = cleaned.replace("(", " ").replace(")", " ")
    cleaned = cleaned.replace(",", " ")
    cleaned = cleaned.replace("-", "_")
    cleaned = cleaned.replace(" ", "_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("_")
    keep = ""
    for ch in cleaned:
        if ch.isalnum() or ch == "_":
            keep += ch
    return keep


def normalize_crop_for_key(crop_display: str) -> str:
    if crop_display in CROP_KEY_MAP:
        return CROP_KEY_MAP[crop_display]
    return _normalize_name_component(crop_display)


def build_crop_disease_key(crop_display: str, disease_key: str) -> str:
    crop_key = normalize_crop_for_key(crop_display)
    dis_key = _normalize_name_component(disease_key)
    combined = f"{crop_key}_{dis_key}"
    while "__" in combined:
        combined = combined.replace("__", "_")
    return combined.strip("_")


def _load_model_from_dir(model_dir: str):
    import tensorflow as tf

    tf.get_logger().setLevel("ERROR")

    cfg_path = os.path.join(model_dir, "config.json")
    weights_path = os.path.join(model_dir, "model.weights.h5")

    if not os.path.isfile(cfg_path):
        raise FileNotFoundError(
            f"Disease model config file is missing: {cfg_path}"
        )

    if not os.path.isfile(weights_path):
        raise FileNotFoundError(
            f"Disease model weights file is missing: {weights_path}"
        )

    with open(cfg_path, "r", encoding="utf-8") as f:
        config = json.load(f)

        
    def fix_keras_config(value):
        if isinstance(value, dict):
            class_name = value.get("class_name")
            layer_config = value.get("config")

            if isinstance(layer_config, dict):
                if class_name == "InputLayer":
                    if "batch_shape" in layer_config:
                        batch_shape = layer_config.pop("batch_shape")
                        layer_config.setdefault(
                            "batch_input_shape", batch_shape
                        )
                    layer_config.pop("optional", None)

                
                dtype = layer_config.get("dtype")
                if isinstance(dtype, dict):
                    dtype_config = dtype.get("config", {})
                    if isinstance(dtype_config, dict):
                        dtype_name = dtype_config.get("name")
                        if dtype_name:
                            layer_config["dtype"] = dtype_name

                if class_name in (
                    "RandomFlip",
                    "RandomRotation",
                    "RandomZoom",
                    "RandomTranslation",
                    "RandomContrast",
                ):
                    layer_config.pop("data_format", None)

                if class_name == "RandomContrast":
                    layer_config.pop("value_range", None)

                

            for child in value.values():
                fix_keras_config(child)

        elif isinstance(value, list):
            for child in value:
                fix_keras_config(child)

    fix_keras_config(config)

    try:
        model = tf.keras.models.model_from_json(json.dumps(config))
    except (AttributeError, TypeError, ValueError) as first_error:
        try:
            model = tf.keras.models.model_from_config(config)
        except Exception as second_error:
            raise RuntimeError(
                "Could not reconstruct the disease model architecture. "
                f"JSON loader error: {first_error}; "
                f"config loader error: {second_error}"
            ) from second_error

    model.load_weights(weights_path)
    return model

    def remove_noop_quantization_config(value):
        if isinstance(value, dict):
            if (
                "quantization_config" in value
                and value["quantization_config"] is None
            ):
                value.pop("quantization_config")
            for child in value.values():
                remove_noop_quantization_config(child)
        elif isinstance(value, list):
            for child in value:
                remove_noop_quantization_config(child)

    remove_noop_quantization_config(config)
    cfg_json = json.dumps(config)
    try:
        model = tf.keras.models.model_from_json(cfg_json)
    except (AttributeError, TypeError, ValueError):
        try:
            model = tf.keras.models.model_from_config(config)
        except AttributeError:
            model_cls_name = config.get("class_name", "Functional")
            inner_cfg = config.get("config", config)
            if model_cls_name in ("Functional", "Sequential"):
                model = tf.keras.models.Model.from_config(inner_cfg)
            else:
                raise
    model.load_weights(weights_path)
    return model


def _validate_model_contract(model):
    expected_input = (None, IMG_SIZE[0], IMG_SIZE[1], 3)
    actual_input = tuple(model.input_shape)
    if actual_input != expected_input:
        raise ValueError(
            f"Disease model input shape {actual_input} does not match {expected_input}."
        )

    output_shape = tuple(model.output_shape)
    if len(output_shape) != 2 or output_shape[-1] != len(_class_names):
        raise ValueError(
            "Disease model output dimensions do not match the configured class labels."
        )


def _ensure_loaded():
    global _model, _class_names, _use_mock_predictor
    with _model_initialization_lock:
        if _class_names is None:
            with open(CLASS_NAMES_PATH, "r") as f:
                _class_names = json.load(f)
        if _model is None and not _use_mock_predictor:
            if not _TF_AVAILABLE:
                _use_mock_predictor = True
                logger.error(
                    "Disease model unavailable error_type=tensorflow_import_failed "
                    "model_artifact=%s detail=%s",
                    os.path.basename(MODEL_PATH),
                    _TF_IMPORT_ERROR or "unknown import error",
                )
                return
            try:
                import tensorflow as tf
                tf.get_logger().setLevel("ERROR")
                if os.path.isdir(MODEL_PATH) and os.path.isfile(
                    os.path.join(MODEL_PATH, "config.json")
                ):
                    loaded_model = _load_model_from_dir(MODEL_PATH)
                else:
                    loaded_model = tf.keras.models.load_model(MODEL_PATH)
                _validate_model_contract(loaded_model)
                _model = loaded_model
                _use_mock_predictor = False
            except Exception as e:
                logger.exception(
                    "Disease model initialization failed error_type=%s "
                    "model_artifact=%s tensorflow_available=%s",
                    type(e).__name__,
                    os.path.basename(MODEL_PATH),
                    _TF_AVAILABLE,
                )
                print(
                    "Warning: Disease model initialization failed "
                    f"({type(e).__name__}); local diagnoses are unavailable."
                )
                _use_mock_predictor = True


def is_real_model_available() -> bool:
    _ensure_loaded()
    return bool(_model is not None and not _use_mock_predictor)


def warmup_model() -> None:
    """Run one non-mutating inference at startup so first-user latency is stable."""
    _ensure_loaded()
    if _model is None or _use_mock_predictor:
        return
    started = time.perf_counter()
    try:
        batch = np.zeros((1, IMG_SIZE[0], IMG_SIZE[1], 3), dtype=np.float32)
        with _model_inference_lock:
            _model.predict(batch, verbose=0)
    except Exception:
        logger.exception("Disease model warmup inference failed.")
        return
    logger.info(
        "Disease model startup warmup elapsed_ms=%.1f",
        (time.perf_counter() - started) * 1000,
    )


def _ensure_class_names_loaded():
    global _class_names
    if _class_names is None:
        with open(CLASS_NAMES_PATH, "r") as f:
            _class_names = json.load(f)


def _ensure_static_data_built():
    global _crop_name_map, _valid_crop_diseases, _class_crop_raw_map, _class_disease_raw_map
    if _valid_crop_diseases is not None and _class_crop_raw_map is not None and _class_disease_raw_map is not None:
        return
    _ensure_class_names_loaded()
    _class_crop_raw_map = []
    _class_disease_raw_map = []
    mapping: Dict[str, Set[str]] = {}
    for raw in _class_names:
        c_raw, d_raw = split_class_name_raw(raw)
        c_display = _pretty_crop_name(c_raw)
        _class_crop_raw_map.append(c_display)
        _class_disease_raw_map.append(d_raw)
        if c_display not in mapping:
            mapping[c_display] = set()
        mapping[c_display].add(d_raw.lower())
    _valid_crop_diseases = mapping


def get_supported_crops() -> List[str]:
    _ensure_static_data_built()
    return sorted(_valid_crop_diseases.keys())


def get_supported_classes() -> List[str]:
    _ensure_class_names_loaded()
    return list(_class_names)


def match_declared_crop(hint: Optional[str]) -> Tuple[Optional[str], bool, str]:
    """Return (matched_display_name, is_supported, original_hint).

    is_supported is True only when the hint maps onto a crop in class_names.json.
    An empty hint means auto-detect (supported=True, matched=None).
    """
    if hint is None:
        return None, True, ""
    raw = str(hint).strip()
    if not raw:
        return None, True, ""
    _ensure_static_data_built()
    key = raw.lower().replace("_", " ").strip()
    if key in DECLARED_CROP_ALIASES:
        display = DECLARED_CROP_ALIASES[key]
        if display in _valid_crop_diseases:
            return display, True, raw
        return display, False, raw
    for display in _valid_crop_diseases.keys():
        if display.lower() == key:
            return display, True, raw
        if normalize_crop_for_key(display) == _normalize_name_component(raw):
            return display, True, raw
    return None, False, raw


def _preprocess_image(image_bytes: bytes, decoded_rgb=None):
    """Resize to 224x224 RGB and preserve the model's expected 0-255 input."""
    if not _NUMPY_AVAILABLE or not _PIL_AVAILABLE:
        return None
    from PIL import Image
    import numpy as _np
    img = decoded_rgb
    if img is None:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")
    img = img.resize(IMG_SIZE, Image.BILINEAR)
    arr = _np.array(img, dtype=_np.float32)
    arr = _np.expand_dims(arr, axis=0)
    return arr


def _model_unavailable_prediction() -> dict:
    return {
        "class_name": "",
        "class_index": -1,
        "confidence": 0.0,
        "top5": [],
        "probabilities": [],
        "mock_predictor": True,
        "error_type": "model_unavailable",
        "error_message": ERROR_MODEL_UNAVAILABLE,
    }


def _prediction_error(error_type: str, message: str) -> dict:
    return {
        "class_name": "",
        "class_index": -1,
        "confidence": 0.0,
        "top5": [],
        "probabilities": [],
        "mock_predictor": False,
        "error_type": error_type,
        "error_message": message,
    }


def predict_disease(image_bytes: bytes, decoded_rgb=None) -> dict:
    model_load_started = time.perf_counter()
    _ensure_loaded()
    model_load_ms = (time.perf_counter() - model_load_started) * 1000
    _ensure_class_names_loaded()
    global _class_names
    if _use_mock_predictor or _model is None:
        logger.info(
            "Disease timing stage=model_initialization elapsed_ms=%.1f available=false",
            model_load_ms,
        )
        prediction = _model_unavailable_prediction()
        prediction["_timing_ms"] = {
            "model_initialization_ms": round(model_load_ms, 1),
            "image_preprocessing_ms": 0.0,
            "model_inference_ms": 0.0,
        }
        return prediction
    import numpy as _np
    preprocess_started = time.perf_counter()
    try:
        x = _preprocess_image(image_bytes, decoded_rgb)
    except (OSError, ValueError):
        preprocess_ms = (time.perf_counter() - preprocess_started) * 1000
        logger.info(
            "Disease timing stage=image_preprocessing elapsed_ms=%.1f result=invalid_image",
            preprocess_ms,
        )
        prediction = _prediction_error(
            "invalid_image",
            "The uploaded file could not be decoded as a supported crop image.",
        )
        prediction["_timing_ms"] = {
            "model_initialization_ms": round(model_load_ms, 1),
            "image_preprocessing_ms": round(preprocess_ms, 1),
            "model_inference_ms": 0.0,
        }
        return prediction
    preprocess_ms = (time.perf_counter() - preprocess_started) * 1000
    if x is None:
        logger.info(
            "Disease timing stage=image_preprocessing elapsed_ms=%.1f result=unavailable",
            preprocess_ms,
        )
        prediction = _prediction_error(
            "image_preprocessing_unavailable",
            "Image preprocessing dependencies are unavailable.",
        )
        prediction["_timing_ms"] = {
            "model_initialization_ms": round(model_load_ms, 1),
            "image_preprocessing_ms": round(preprocess_ms, 1),
            "model_inference_ms": 0.0,
        }
        return prediction
    inference_started = time.perf_counter()
    try:
        with _model_inference_lock:
            output = _model.predict(x, verbose=0)
        probs = _np.asarray(output, dtype="float64")
        if probs.ndim != 2 or probs.shape[0] != 1:
            raise ValueError("Model returned an invalid prediction tensor shape.")
        probs = probs[0]
        if (
            not _np.isfinite(probs).all()
            or (probs < 0).any()
            or (probs > 1).any()
            or not _np.isclose(float(probs.sum()), 1.0, atol=1e-3)
        ):
            raise ValueError("Model output is not a valid probability distribution.")
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Disease model inference failed.")
        logger.info(
            "Disease timing stages model_initialization_ms=%.1f image_preprocessing_ms=%.1f "
            "model_inference_ms=%.1f result=failed",
            model_load_ms,
            preprocess_ms,
            (time.perf_counter() - inference_started) * 1000,
        )
        prediction = _prediction_error(
            "model_inference_failed",
            "The crop disease model could not analyze this image. Please try again.",
        )
        prediction["_timing_ms"] = {
            "model_initialization_ms": round(model_load_ms, 1),
            "image_preprocessing_ms": round(preprocess_ms, 1),
            "model_inference_ms": round((time.perf_counter() - inference_started) * 1000, 1),
        }
        return prediction
    inference_ms = (time.perf_counter() - inference_started) * 1000
    n_model = int(probs.shape[0])
    n_labels = len(_class_names)
    if n_model != n_labels:
        logger.error(
            "Disease model output size mismatch model_classes=%d configured_classes=%d",
            n_model,
            n_labels,
        )
        prediction = _prediction_error(
            "class_mapping_mismatch",
            (
                f"Model output size ({n_model}) does not match class_names.json ({n_labels}). "
                "Refusing to map indices."
            ),
        )
        prediction["_timing_ms"] = {
            "model_initialization_ms": round(model_load_ms, 1),
            "image_preprocessing_ms": round(preprocess_ms, 1),
            "model_inference_ms": round(inference_ms, 1),
        }
        return prediction
    idx = int(_np.argmax(probs))
    conf = float(probs[idx]) * 100.0
    cls = _class_names[idx]
    top5_indices = _np.argsort(probs)[-5:][::-1]
    top5 = [
        {
            "class_name": _class_names[int(i)],
            "confidence": float(probs[int(i)]) * 100.0,
        }
        for i in top5_indices
    ]
    logger.info(
        "Disease timing stages model_initialization_ms=%.1f image_preprocessing_ms=%.1f "
        "model_inference_ms=%.1f",
        model_load_ms,
        preprocess_ms,
        inference_ms,
    )
    return {
        "class_name": cls,
        "class_index": idx,
        "confidence": conf,
        "top5": top5,
        "probabilities": [float(p) * 100.0 for p in probs.tolist()],
        "mock_predictor": False,
        "_timing_ms": {
            "model_initialization_ms": round(model_load_ms, 1),
            "image_preprocessing_ms": round(preprocess_ms, 1),
            "model_inference_ms": round(inference_ms, 1),
        },
    }


def split_class_name_raw(class_name: str) -> Tuple[str, str]:
    parts = class_name.split("___", 1)
    crop_raw = parts[0]
    disease_raw = parts[1] if len(parts) > 1 else ""
    return crop_raw, disease_raw


def _pretty_crop_name(crop_raw: str) -> str:
    rough = crop_raw.replace("_", " ")
    if rough in CROP_NAME_MAP:
        return CROP_NAME_MAP[rough]
    cleaned = rough.strip().rstrip(",")
    if cleaned in CROP_NAME_MAP:
        return CROP_NAME_MAP[cleaned]
    if cleaned.endswith(" "):
        cleaned = cleaned.rstrip()
    if cleaned.startswith(","):
        cleaned = cleaned.lstrip(",").strip()
    return cleaned.title() if cleaned else cleaned


def split_class_name(class_name: str) -> tuple:
    c_raw, d_raw = split_class_name_raw(class_name)
    crop = _pretty_crop_name(c_raw)
    disease = d_raw.replace("_", " ").strip()
    return crop, disease


def map_class_to_disease_key(class_name: str) -> str:
    cn = class_name.lower()
    if "healthy" in cn:
        return "healthy"
    if "apple_scab" in cn:
        return "apple_scab"
    if "cedar_apple_rust" in cn:
        return "cedar_apple_rust"
    if "black_rot" in cn:
        return "black_rot"
    if "northern_leaf_blight" in cn:
        return "northern_leaf_blight"
    if "esca" in cn or "black_measles" in cn:
        return "esca"
    if "isariopsis" in cn or "leaf_blight" in cn:
        if "grape" in cn:
            return "leaf_blight_isariopsis"
    if "haunglongbing" in cn or "citrus_greening" in cn:
        return "haunglongbing"
    if "bacterial_spot" in cn:
        return "bacterial_spot"
    if "leaf_mold" in cn:
        return "leaf_mold"
    if "septoria" in cn:
        return "septoria_leaf_spot"
    if "spider_mites" in cn or "two-spotted" in cn:
        return "spider_mites"
    if "target_spot" in cn:
        return "target_spot"
    if "yellow_leaf_curl" in cn:
        return "tomato_yellow_leaf_curl"
    if "mosaic_virus" in cn:
        return "tomato_mosaic_virus"
    if "leaf_scorch" in cn:
        return "leaf_scorch"
    if "powdery_mildew" in cn or "powdery" in cn:
        return "powdery_mildew"
    if "late_blight" in cn:
        return "late_blight"
    if "early_blight" in cn:
        return "early_blight"
    if "rust" in cn or "common_rust" in cn:
        return "rust"
    if "cercospora" in cn or "gray_leaf_spot" in cn:
        return "leaf_spot"
    return "unknown"


def _softmax_entropy_from_percent(pcts: List[float]) -> float:
    probs = [max(p, 0.0) / 100.0 for p in pcts]
    total = sum(probs)
    if total <= 0:
        return float("inf")
    probs = [p / total for p in probs]
    ent = 0.0
    for p in probs:
        if p > 0:
            ent -= p * math.log(p)
    return ent


def analyze_prediction(
    pred: Dict[str, Any],
    crop_threshold: float = None,
    disease_threshold: float = None,
    non_plant_max_conf: float = None,
    non_plant_other_below: float = 20.0,
    declared_crop: Optional[str] = None,
) -> Dict[str, Any]:
    """Interpret model output; declared_crop is retained as an advisory hint only."""
    _ensure_static_data_built()
    cfg = load_inference_config()
    if crop_threshold is None:
        crop_threshold = cfg["min_crop_mass"]
    if disease_threshold is None:
        disease_threshold = cfg["min_top1_confidence"]
    if non_plant_max_conf is None:
        non_plant_max_conf = cfg["non_plant_max_conf"]
    min_margin = cfg["min_margin_pp"]
    max_entropy = cfg["max_softmax_entropy"]
    uncertain_cut = cfg["uncertain_top1_confidence"]

    if pred.get("error_type") in {
        "class_mapping_mismatch",
        "invalid_image",
        "image_preprocessing_unavailable",
        "model_inference_failed",
    }:
        return {
            "ok": False,
            "error_type": pred["error_type"],
            "error_message": pred.get("error_message") or ERROR_INVALID_COMBO,
        }

    if pred.get("mock_predictor"):
        return {
            "ok": False,
            "error_type": "model_unavailable",
            "error_message": pred.get("error_message") or ERROR_MODEL_UNAVAILABLE,
        }

    probabilities = pred.get("probabilities")
    top5 = list(pred.get("top5") or [])
    if probabilities and len(probabilities) == len(_class_names):
        indexed = sorted(enumerate(probabilities), key=lambda kv: kv[1], reverse=True)
        top5 = [
            {"class_name": _class_names[i], "confidence": float(p), "class_index": i}
            for i, p in indexed[:5]
        ]
        crop_scores: Dict[str, float] = {}
        for i, p in enumerate(probabilities):
            crop_display = _class_crop_raw_map[i]
            crop_scores[crop_display] = crop_scores.get(crop_display, 0.0) + float(p)
        entropy = _softmax_entropy_from_percent(list(probabilities))
    else:
        crop_scores = {}
        entropy = _softmax_entropy_from_percent([e.get("confidence", 0.0) for e in top5]) if top5 else float("inf")
        for entry in top5:
            cname = entry.get("class_name", "")
            try:
                cidx = _class_names.index(cname)
            except ValueError:
                cidx = -1
            c_display = _class_crop_raw_map[cidx] if 0 <= cidx < len(_class_crop_raw_map) else split_class_name(cname)[0]
            crop_scores[c_display] = crop_scores.get(c_display, 0.0) + float(entry.get("confidence", 0.0))

    if not top5:
        return {"ok": False, "error_type": "non_plant", "error_message": ERROR_NON_PLANT}

    top1 = top5[0]
    top1_conf = float(top1.get("confidence", 0.0))
    top2_conf = float(top5[1].get("confidence", 0.0)) if len(top5) > 1 else 0.0
    margin = top1_conf - top2_conf

    if top1_conf < non_plant_max_conf:
        others_low = all(float(e.get("confidence", 0.0)) < non_plant_other_below for e in top5[1:]) if len(top5) > 1 else True
        if others_low:
            return {"ok": False, "error_type": "non_plant", "error_message": ERROR_NON_PLANT}

    sorted_crops = sorted(crop_scores.items(), key=lambda kv: kv[1], reverse=True)
    if not sorted_crops:
        return {"ok": False, "error_type": "low_crop_conf", "error_message": ERROR_LOW_CROP_CONF}

    crop_display, crop_confidence = sorted_crops[0]
    if crop_confidence < crop_threshold:
        return {
            "ok": False,
            "error_type": "low_crop_conf",
            "error_message": ERROR_LOW_CROP_CONF,
            "crop": crop_display,
            "crop_confidence": round(crop_confidence, 1),
        }

    if crop_display not in _valid_crop_diseases:
        return {
            "ok": False,
            "error_type": "unsupported_crop",
            "error_message": ERROR_UNSUPPORTED_CROP,
            "crop": crop_display,
            "supported_crops": get_supported_crops(),
        }

    crop_class_indices = [
        index for index, class_crop in enumerate(_class_crop_raw_map)
        if class_crop == crop_display
    ]
    crop_disease_labels = [
        _class_disease_raw_map[index].strip().lower()
        for index in crop_class_indices
    ]
    if len(crop_disease_labels) == 1 and crop_disease_labels[0] == "healthy":
        return {
            "ok": False,
            "error_type": "disease_identification_unsupported",
            "error_message": (
                f"The PlantVillage model has only healthy-leaf examples for {crop_display}; "
                "it cannot determine whether this crop has a disease. Please consult a local "
                "agricultural expert or use a disease-validated model for this crop."
            ),
            "crop": crop_display,
            "crop_confidence": round(crop_confidence, 1),
            "disease_confidence": round(top1_conf, 1),
            "supported_crops": get_supported_crops(),
        }

    if entropy > max_entropy or margin < min_margin or top1_conf < disease_threshold:
        return {
            "ok": False,
            "error_type": "uncertain",
            "error_message": ERROR_UNCERTAIN,
            "crop": crop_display,
            "crop_confidence": round(crop_confidence, 1),
            "disease_confidence": round(top1_conf, 1),
            "margin_pp": round(margin, 1),
            "entropy": round(entropy, 3),
            "top5": top5,
        }

    cname = top1.get("class_name", "")
    try:
        class_idx = int(top1.get("class_index", _class_names.index(cname)))
    except (ValueError, TypeError):
        class_idx = -1
        try:
            class_idx = _class_names.index(cname)
        except ValueError:
            class_idx = -1
    if class_idx < 0:
        return {"ok": False, "error_type": "class_mapping_mismatch", "error_message": ERROR_INVALID_COMBO}

    raw_class = _class_names[class_idx]
    mapped_crop = _class_crop_raw_map[class_idx]
    if mapped_crop != crop_display:
        return {"ok": False, "error_type": "invalid_combo", "error_message": ERROR_INVALID_COMBO}

    top_d_raw = _class_disease_raw_map[class_idx]
    generic_d_key = map_class_to_disease_key(raw_class)
    if generic_d_key == "unknown":
        return {"ok": False, "error_type": "invalid_combo", "error_message": ERROR_INVALID_COMBO}
    d_display = split_class_name(raw_class)[1] or top_d_raw.replace("_", " ").strip()
    d_raw_lower = top_d_raw.lower()
    if d_raw_lower not in _valid_crop_diseases.get(crop_display, set()) and "healthy" not in d_raw_lower:
        return {"ok": False, "error_type": "invalid_combo", "error_message": ERROR_INVALID_COMBO}

    is_healthy = "healthy" in top_d_raw.lower() or "healthy" in d_display.lower()
    crop_specific_d_key = build_crop_disease_key(crop_display, generic_d_key)
    uncertain_flag = top1_conf < uncertain_cut

    return {
        "ok": True,
        "crop": crop_display,
        "crop_confidence": round(crop_confidence, 1),
        "disease": d_display if not is_healthy else "Healthy Leaf / No Major Disease Detected",
        "disease_key": crop_specific_d_key,
        "generic_disease_key": generic_d_key,
        "disease_confidence": round(top1_conf, 1),
        "is_healthy": is_healthy,
        "raw_class": raw_class,
        "class_index": class_idx,
        "top5": top5,
        "margin_pp": round(margin, 1),
        "entropy": round(entropy, 3),
        "uncertain": uncertain_flag,
        "limitations": [
            "This classifier only covers PlantVillage crops/diseases listed in class_names.json.",
            "Softmax confidence is not proof of correctness, especially on crops the model never saw.",
            "Blueberry, Raspberry, and Soybean have healthy-only classes; disease detection is not supported for those crops.",
            "Confirm with a local agricultural extension officer before applying chemical treatments.",
        ],
    }

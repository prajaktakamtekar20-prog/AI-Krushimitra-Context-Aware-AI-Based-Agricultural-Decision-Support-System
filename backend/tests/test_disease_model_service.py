import contextlib
import io
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from services import disease_model_service as disease


def _jpeg_bytes():
    image = Image.new("RGB", (128, 128), color=(50, 150, 50))
    output = io.BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


class TestDiseaseModelService(unittest.TestCase):
    def test_concurrent_initialization_loads_the_model_once(self):
        model = SimpleNamespace(input_shape=(None, 224, 224, 3), output_shape=(None, 1))

        def load_model(_model_dir):
            time.sleep(0.02)
            return model

        with (
            patch.object(disease, "_model", None),
            patch.object(disease, "_class_names", ["Tomato___Early_blight"]),
            patch.object(disease, "_use_mock_predictor", False),
            patch.object(disease, "_TF_AVAILABLE", True),
            patch.object(disease.os.path, "isdir", return_value=True),
            patch.object(disease.os.path, "isfile", return_value=True),
            patch.object(disease, "_load_model_from_dir", side_effect=load_model) as load,
            patch.object(disease, "_validate_model_contract"),
        ):
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(disease._ensure_loaded) for _ in range(4)]
                for future in futures:
                    future.result()

        load.assert_called_once()

    def test_concurrent_predictions_are_serialized(self):
        state_lock = threading.Lock()
        active_predictions = 0
        max_active_predictions = 0

        def predict(_batch, verbose=0):
            nonlocal active_predictions, max_active_predictions
            with state_lock:
                active_predictions += 1
                max_active_predictions = max(max_active_predictions, active_predictions)
            time.sleep(0.02)
            with state_lock:
                active_predictions -= 1
            return [[1.0]]

        model = SimpleNamespace(predict=predict)
        with (
            patch.object(disease, "_ensure_loaded"),
            patch.object(disease, "_ensure_class_names_loaded"),
            patch.object(disease, "_use_mock_predictor", False),
            patch.object(disease, "_model", model),
            patch.object(disease, "_class_names", ["Tomato___Early_blight"]),
        ):
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(disease.predict_disease, _jpeg_bytes())
                    for _ in range(4)
                ]
                results = [future.result() for future in futures]

        self.assertEqual(max_active_predictions, 1)
        self.assertTrue(all(result["class_index"] == 0 for result in results))

    def test_startup_warmup_uses_one_zero_image_batch_without_a_mock_prediction(self):
        model = SimpleNamespace(predict=Mock(return_value=[[1.0]]))
        with (
            patch.object(disease, "_ensure_loaded"),
            patch.object(disease, "_use_mock_predictor", False),
            patch.object(disease, "_model", model),
        ):
            disease.warmup_model()

        model.predict.assert_called_once()
        batch = model.predict.call_args.args[0]
        self.assertEqual(batch.shape, (1, 224, 224, 3))

    def test_model_directory_without_weights_is_rejected(self):
        with tempfile.TemporaryDirectory() as model_dir:
            with self.assertRaisesRegex(FileNotFoundError, "weights file is missing"):
                disease._load_model_from_dir(model_dir)

    def test_model_load_failure_is_logged_and_never_marked_available(self):
        with (
            patch.object(disease, "_model", None),
            patch.object(disease, "_class_names", []),
            patch.object(disease, "_use_mock_predictor", False),
            patch.object(disease, "_TF_AVAILABLE", True),
            patch.object(disease.os.path, "isdir", return_value=True),
            patch.object(disease.os.path, "isfile", return_value=True),
            patch.object(
                disease,
                "_load_model_from_dir",
                side_effect=TypeError("incompatible Keras input config"),
            ),
            patch.object(disease.logger, "exception") as log_exception,
            patch("builtins.print"),
        ):
            disease._ensure_loaded()
            log_exception.assert_called_once()
            self.assertEqual(log_exception.call_args.args[1], "TypeError")
            self.assertIsNone(disease._model)
            self.assertTrue(disease._use_mock_predictor)

    def test_invalid_image_returns_error_instead_of_a_prediction(self):
        with (
            patch.object(disease, "_ensure_loaded"),
            patch.object(disease, "_ensure_class_names_loaded"),
            patch.object(disease, "_use_mock_predictor", False),
            patch.object(disease, "_model", SimpleNamespace()),
            patch.object(disease, "_class_names", ["Tomato___Early_blight"]),
        ):
            result = disease.predict_disease(b"not an image")

        self.assertEqual(result["error_type"], "invalid_image")
        self.assertEqual(result["class_name"], "")
        self.assertEqual(result["probabilities"], [])

    def test_missing_model_returns_unavailable_without_diagnosis(self):
        with (
            patch.object(disease, "_ensure_loaded"),
            patch.object(disease, "_ensure_class_names_loaded"),
            patch.object(disease, "_use_mock_predictor", True),
            patch.object(disease, "_model", None),
            patch.object(disease, "_class_names", ["Tomato___Early_blight"]),
        ):
            result = disease.predict_disease(_jpeg_bytes())

        self.assertEqual(result["error_type"], "model_unavailable")
        self.assertTrue(result["mock_predictor"])
        self.assertEqual(result["class_name"], "")
        self.assertEqual(result["probabilities"], [])

    def test_inference_exception_returns_error_without_prediction(self):
        model = SimpleNamespace(predict=Mock(side_effect=RuntimeError("test failure")))
        with (
            patch.object(disease, "_ensure_loaded"),
            patch.object(disease, "_ensure_class_names_loaded"),
            patch.object(disease, "_use_mock_predictor", False),
            patch.object(disease, "_model", model),
            patch.object(disease, "_class_names", ["Tomato___Early_blight"]),
        ):
            result = disease.predict_disease(_jpeg_bytes())

        self.assertEqual(result["error_type"], "model_inference_failed")
        self.assertEqual(result["class_name"], "")
        self.assertEqual(result["probabilities"], [])

    def test_model_contract_rejects_output_label_count_mismatch(self):
        with patch.object(disease, "_class_names", ["Tomato___Early_blight"]):
            with self.assertRaisesRegex(ValueError, "output dimensions"):
                disease._validate_model_contract(
                    SimpleNamespace(
                        input_shape=(None, 224, 224, 3),
                        output_shape=(None, 38),
                    )
                )

    def test_loaded_model_contract_matches_image_input_and_class_labels(self):
        class_names = disease.get_supported_classes()
        disease._validate_model_contract(
            SimpleNamespace(
                input_shape=(None, 224, 224, 3),
                output_shape=(None, len(class_names)),
            )
        )

    def test_invalid_image_error_is_preserved_by_prediction_analysis(self):
        with patch.object(disease, "_ensure_static_data_built"):
            result = disease.analyze_prediction(
                {
                    "error_type": "invalid_image",
                    "error_message": "Invalid image.",
                    "mock_predictor": False,
                }
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "invalid_image")
        self.assertEqual(result["error_message"], "Invalid image.")

    def test_startup_does_not_claim_real_model_when_loader_failed(self):
        import main

        output = io.StringIO()
        with (
            patch.object(disease, "_ensure_loaded"),
            patch.object(disease, "_model", None),
            patch.object(disease, "_use_mock_predictor", True),
            contextlib.redirect_stdout(output),
        ):
            main._preload_disease_model()

        self.assertIn("unavailable", output.getvalue())
        self.assertNotIn("loaded successfully", output.getvalue())


if __name__ == "__main__":
    unittest.main()

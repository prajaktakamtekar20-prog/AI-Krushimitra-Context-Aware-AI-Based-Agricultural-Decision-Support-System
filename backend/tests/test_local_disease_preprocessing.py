import io
import unittest

import numpy as np
from PIL import Image

from services.disease_model_service import _preprocess_image
from services.image_quality import assess_image_quality


class LocalDiseasePreprocessingTests(unittest.TestCase):
    def test_preprocessing_preserves_raw_rgb_pixels_for_saved_graph(self):
        image = Image.new("RGB", (32, 32), (12, 34, 56))
        image_bytes = io.BytesIO()
        image.save(image_bytes, format="PNG")

        batch = _preprocess_image(image_bytes.getvalue())

        self.assertEqual(batch.shape, (1, 224, 224, 3))
        np.testing.assert_allclose(batch[0, 112, 112], [12.0, 34.0, 56.0])

    def test_preprocessing_reuses_quality_check_decode_without_changing_pixels(self):
        image = Image.new("RGB", (128, 128), (50, 150, 50))
        image_bytes = io.BytesIO()
        image.save(image_bytes, format="JPEG")
        contents = image_bytes.getvalue()

        quality = assess_image_quality(contents, include_decoded_rgb=True)

        self.assertTrue(quality["ok"])
        original_batch = _preprocess_image(contents)
        reused_batch = _preprocess_image(contents, quality["_decoded_rgb"])
        np.testing.assert_array_equal(reused_batch, original_batch)


if __name__ == "__main__":
    unittest.main()

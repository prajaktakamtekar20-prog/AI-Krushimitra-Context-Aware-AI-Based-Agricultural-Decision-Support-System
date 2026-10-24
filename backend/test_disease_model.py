import json
import keras

config_path = "models/plant_disease_mobilenetv2.keras/config.json"
weights_path = "models/plant_disease_mobilenetv2.keras/model.weights.h5"

with open(config_path, encoding="utf-8") as f:
    config = json.load(f)

try:
    model = keras.Model.from_config(config["config"])
    model.load_weights(weights_path)
    print("MODEL LOADED SUCCESSFULLY")
    print("Input:", model.input_shape)
    print("Output:", model.output_shape)
except Exception as e:
    print(type(e).__name__ + ":", e)

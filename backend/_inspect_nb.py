import json, os, sys
root = os.path.dirname(__file__)
nb_path = os.path.join(root, "Untitled43.ipynb")
if not os.path.exists(nb_path):
    print("No notebook")
    sys.exit(0)
nb = json.load(open(nb_path, encoding="utf-8"))
src = []
for c in nb.get("cells", []):
    if c.get("cell_type") == "code":
        src.extend(c.get("source", []))
text = "\n".join(src)
for kw in ["preprocess_input", "Rescaling", "rescale", "127.5", "/255",
           "ImageDataGenerator", "flow_from_directory", "image_dataset_from_directory",
           "mobilenet_v2", "MobileNetV2", "include_top"]:
    idx = text.lower().find(kw.lower())
    if idx >= 0:
        print(f"--- {kw} ---")
        print(text[max(0, idx-200):idx+300].replace("\n", " "))
        print()

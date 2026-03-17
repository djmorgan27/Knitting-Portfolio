import os
from PIL import Image
import pillow_heif

pillow_heif.register_heif_opener()

folder = r"C:\Users\djmor\Desktop\Knitting_Portfolio"

for file in os.listdir(folder):
    if file.lower().endswith(".heic"):
        input_path = os.path.join(folder, file)
        output_path = os.path.join(folder, file.rsplit(".", 1)[0] + ".jpg")

        try:
            with Image.open(input_path) as img:
                img.convert("RGB").save(output_path, "JPEG", quality=95)

            os.remove(input_path)  # delete original after successful conversion
            print(f"Converted and replaced: {file}")

        except Exception as e:
            print(f"Failed on {file}: {e}")

print("Done.")
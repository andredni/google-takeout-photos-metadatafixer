import os
import re
import json
import zipfile
import piexif
import piexif.helper
from PIL import Image
from glob import glob
from datetime import datetime
from tqdm import tqdm

def extract_zip_files(zip_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    zip_files = glob(os.path.join(zip_folder, "*.zip"))

    for zip_file in tqdm(zip_files, desc="Unpack ZIP files"):
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(output_folder)

def find_matching_json(image, metadata_files):
    pattern = r"^.*" + image + "\.supplemental-metadata\.json"
    matches = [item for item in metadata_files if re.fullmatch(pattern, item)]

    if len(matches) > 0:
        return matches[0]
    
    return None

def update_exif_from_json(image_path, json_path):

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        img = Image.open(image_path)
        exif_dict = piexif.load(img.info.get("exif", b""))

        if "photoTakenTime" in metadata:
            timestamp = int(metadata["photoTakenTime"]["timestamp"])
            dt = datetime.utcfromtimestamp(timestamp).strftime("%Y:%m:%d %H:%M:%S")
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt.encode("ascii")
            exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = dt.encode("ascii")

        if "geoData" in metadata and metadata["geoData"].get("latitude"):
            lat = metadata["geoData"]["latitude"]
            lon = metadata["geoData"]["longitude"]
            lat_ref = "N" if lat >= 0 else "S"
            lon_ref = "E" if lon >= 0 else "W"

            def to_deg(value):
                d = int(value)
                m = int((value - d) * 60)
                s = round((value - d - m / 60) * 3600, 6)
                return [(d, 1), (m, 1), (int(s * 100), 100)]

            gps_data = {
                piexif.GPSIFD.GPSLatitudeRef: lat_ref.encode(),
                piexif.GPSIFD.GPSLatitude: to_deg(abs(lat)),
                piexif.GPSIFD.GPSLongitudeRef: lon_ref.encode(),
                piexif.GPSIFD.GPSLongitude: to_deg(abs(lon)),
            }
            exif_dict["GPS"] = gps_data

        if "description" in metadata:
            user_comment = metadata["description"]
            exif_dict["Exif"][piexif.ExifIFD.UserComment] = piexif.helper.UserComment.dump(user_comment, encoding="unicode")

        exif_bytes = piexif.dump(exif_dict)
        img.save(image_path, "jpeg", exif=exif_bytes)

    except Exception as e:
        print(f"\t Image update error: Image File: {image_path} | Metadata File: {json_path} | Error: {e}")


def find_images(directory, extensions=("jpg", "jpeg", "png", "JPG", "PNG", "JPEG")):
    image_files = []
    for ext in extensions:
        image_files.extend(glob(f"{directory}/**/*.{ext}", recursive=True))
    return image_files


def process_images(image_folder):
    images = find_images(image_folder)
    metadata_files = list(set(glob(f"{output_folder}/**/*.supplemental-metadata.json", recursive=True)))
    
    for img_path in tqdm(images, desc="Edit images"):
        image_path = img_path.rsplit('/', 1)[0]
        image = img_path.rsplit('/',1)[1]

        json_path = find_matching_json(image, metadata_files)

        if json_path:
            update_exif_from_json(img_path, json_path)


if __name__ == "__main__":
    zip_folder = input("Enter the path to the folder with the ZIP files: ")
    output_folder = os.path.join(zip_folder, "takeout_unpacked")

    if not os.path.exists(output_folder):
        extract_zip_files(zip_folder, output_folder)

    process_images(output_folder)
    print("All images have been successfully edited and contain their metadata again!")

from PIL import Image
import pytesseract
import numpy as np
import cv2

def extract_text_from_image(image_file):
    image = Image.open(image_file)
    image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    return pytesseract.image_to_string(gray)

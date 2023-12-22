# -*- coding: utf-8 -*-
# import ast
# import cv2
# import datetime
# import easyocr
import fitz
# import json
# import langid
import os
# import numpy as np
# import re
import requests, uuid
import streamlit as st
import string
import time
import traceback

# from googletrans import Translator
from pdf2image import convert_from_path
from PIL import Image, ImageDraw

# translator = Translator()

################# config #########################################
st.set_page_config(layout="wide")

################# CONSTANTS ########################################
INPUT_PATH = "./doctrans/INPUT/"
JPEG_PATH = "./doctrans/JPEG/"
OCRS_PATH = "./doctrans/OCRS/"
OUTPUT_PATH = "./doctrans/OUTPUT/"
FACTOR = 3
# POPPLER_PATH = r'C:\Program Files\poppler-0.68.0\bin'
LANG_LIST = ["English"]#,"Spanish","French"
OUTPUT_FORMAT = ["PDF","PNG","JPG"]
TYPE = False


EXCLUDE = string.punctuation+"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
key = "ddbffd58a93442d4a7f3414cb31d4765"
endpoint = "https://api.cognitive.microsofttranslator.com"
location = "eastus"
path = "/translate"
################# Sidebar ########################################
def save_uploadedfile(uploadedfile):
     with open(os.path.join(INPUT_PATH,uploadedfile.name),"wb") as f:
         f.write(uploadedfile.getbuffer())
     return st.success("Saved File:{}".format(uploadedfile.name))


st.sidebar.header("TOTALS")
# st.sidebar.markdown("**_Document Translator_**")
st.sidebar.markdown("( digi**T**al fact**O**ry smar**T** l**A**nguage trans**L**ation **S**olution)")
st.sidebar.image(Image.open("./doctrans/LOGO/logo2.jpg"),width=200)

exp = st.sidebar.expander("File Upload", expanded= False)
uploaded_file = exp.file_uploader("Upload a file",accept_multiple_files=False)
if uploaded_file is not None:
    bytes_data = uploaded_file.getvalue()
    if round(len(bytes_data)/1024,1) > 1.0:
        st.error("**_File upload is currently disabled!_**")
    else:
        try:
            save_uploadedfile(uploaded_file)
        except Exception as e:
            print(e)
            st.write(e)
            st.error("File upload failed. Error Message: "+str(e)+"\nPlease reach-out to support team with the error message.")

FILE_NAME = st.sidebar.selectbox("Choose a File:",os.listdir(INPUT_PATH))
FROM_LANG = st.sidebar.selectbox("Source Language:",["Thai"])
TO_LANG = st.sidebar.selectbox("Translate To:",LANG_LIST)
TRANSLATION_ENGINE = "Azure"#st.sidebar.selectbox("Translation Engine:",["Azure","Google"])
TARGET_DPI = st.sidebar.selectbox("Target DPI:",["500","150","300","600","1000"])

################ Functions ####################################
def check_type(file_name,th):
    doc = fitz.open(file_name)
    text_pages = 0
    for page in doc:
        text_pages = len(page.get_text("words"))
        break
    doc.close()
    if text_pages == 0:
        return "scanned"
    else:
        return "nonscanned"


def draw_boxes(image, bounds, color='red', width=3):
    draw = ImageDraw.Draw(image)
    for bound in bounds:
        p0,p1,p2,p3 = bound[0]
        if bound[2] > 0.2:
            # print(bound[2], bound[1])
            draw.line([*p0,*p1,*p2, *p3, *p0], fill=color, width=width)
    return image

constructed_url = endpoint + path
headers = {
    'Ocp-Apim-Subscription-Key': key,
    'Ocp-Apim-Subscription-Region': location,
    'Content-type': 'application/json',
    'X-ClientTraceId': str(uuid.uuid4())
}
def azure_translator(text,dest='en'):
    params = {'api-version': '3.0','from': 'th','to': [dest]}
    body = [{'text': str(text) }]
    request = requests.post(constructed_url, params=params, headers=headers, json=body)
    response = request.json()
    return response[0]["translations"][0]["text"]


def get_pdf_text(PDF_FILENAME):
    print("FILE NAME:",PDF_FILENAME)
    start_time = datetime.datetime.now()
    print("open pdf file...")
    doc = fitz.open(INPUT_PATH+PDF_FILENAME)
    images = []
    for idx, page in enumerate(doc):
        print("page of pdf file...")
        wrds = []
        wrds_tmp = page.get_text("words")
        mat = fitz.Matrix(FACTOR, FACTOR)
        pix = page.get_pixmap(matrix=mat)

        image_copy = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        draw = ImageDraw.Draw(image_copy)

        ocr_text_list = []
        trans_text_list = []

        print("fetching words from pdf...")
        for ele in reversed(wrds_tmp):
            ocr_text = str(ele[4])
            if langid.classify(ocr_text)[0] !='en':
                ocr_text_list.append(ocr_text.replace(","," "))
                wrds.append(ele)

        # TRANSLATE
        print("Translating non-scanned pdf...",datetime.datetime.now())
        print("Translating ",len(ocr_text_list), "identified text. Please wait...")
        tmp_lst = translator.translate(ocr_text_list, dest='en')
        print("Translation completed...",datetime.datetime.now())
        for ele in tmp_lst:
            trans_text_list.append(ele.text)
        print("Beautifying your output pdf file...")

        for w,txt in zip(wrds,trans_text_list):
            top_left_x = int(w[0]*FACTOR)
            top_left_y = int(w[1]*FACTOR)
            bottom_right_x = int(w[2]*FACTOR)
            bottom_right_y = int(w[3]*FACTOR)
            shape = [(top_left_x,top_left_y),(bottom_right_x,top_left_y),(bottom_right_x,bottom_right_y),(top_left_x,bottom_right_y),(top_left_x,top_left_y)]

            draw.line(shape, fill="red", width=1)
            x, y, width, height = top_left_x, top_left_y, (bottom_right_x - top_left_x), (bottom_right_y - top_left_y)

            image_copy = np.array(image_copy)
            image_copy[y:y + height, x:x + width] = (255, 255, 230)

            #draw patch
            org = (x , y + int(height*0.7)) #0.6
            font = cv2.FONT_HERSHEY_SIMPLEX
            thickness = 1

            try:
                fontScale = get_optimal_font_scale(txt,width, height)
            except Exception as e:
                print(e)
                fontScale = 1
            image_copy = cv2.putText(image_copy, txt, org, font,fontScale,(0.7, 0, 0 ,255), thickness)

        img = Image.fromarray(image_copy, 'RGB')
        images.append(img)
        try:
            img.save(OUTPUT_PATH+"Translated_"+PDF_FILENAME.replace(".pdf","")+"_"+str(idx)+".JPG")
        except Exception as e:
            print(str(e), OUTPUT_PATH+"Translated_"+PDF_FILENAME.replace(".pdf","")+"_"+str(idx)+".JPG")
            traceback.print_exc()
    st.info("File Translated Successfully..")
    end_time = datetime.datetime.now()
    print("UNSCANNED PDF took :",str((end_time-start_time).seconds),"seconds")
    doc.close()

    pdf_path = OUTPUT_PATH+"Translated_"+PDF_FILENAME
    if len(images)>=1:
        images[0].save(pdf_path, "PDF" ,resolution=100.0, save_all=True, append_images=images[1:])
    else:
        images[0].save(pdf_path, "PDF" ,resolution=100.0)

def ocr(image):
    image_tmp = image.copy()
    reader = easyocr.Reader(['th'], gpu=True)
    st.spinner(text="In progress...")
    print("Custom-CV Reading ... Please wait.")
    start_time = datetime.datetime.now()
    res = reader.readtext(np.array(image_tmp))
    end_time = datetime.datetime.now()
    print("Scanned PDF[Custom-CV] took :",str((end_time-start_time).seconds),"seconds")
    with open(OCRS_PATH+image_name.replace(".jpg","")+".json","w") as f:
        json.dump(str(res),f) 
    end_time = datetime.datetime.now()
    #save file
    try:
        draw_boxes(image_tmp,res).save(OCRS_PATH+"OCR_"+image_name.replace(".pdf",""))
    except Exception as e:
        print(e)
    print("OCR done")


def get_optimal_font_scale(text, width, height):
    for scale in reversed(list(np.arange(0.25, 5, 0.1))):
        textSize = cv2.getTextSize(text, fontFace=cv2.FONT_HERSHEY_DUPLEX, fontScale=scale, thickness=1)
        new_width = textSize[0][0]
        new_height = textSize[0][1]
        if (new_width <= width):
            if (new_height) <= height:
                # print(text, "Initial Width:", width, ", Initial Height: ", height, "Final Width:" ,new_width, "Final Height: ",new_height, "Scale:",round(scale,2))
                return round(scale,2)
    return 0.7

def translate(image_name,font_scale=1.5,thickness=2):
    with open(OCRS_PATH+image_name.replace(".jpg","")+".json", 'r') as openfile:
        res = ast.literal_eval(json.load(openfile))
    image_copy = Image.open(JPEG_PATH+ image_name).copy()
    p0,p1,p2,p3=0,0,0,0
    ocr_text_list = []
    trans_text_list = []

    for ele in res:
        ocr_text = str(ele[1])
        ocr_text_list.append(ocr_text.replace(","," "))
    # TRANSLATE
    tmp_lst = translator.translate(ocr_text_list, dest='en')
    for ele in tmp_lst:
        trans_text_list.append(ele.text)

    for bound,text in zip(res,trans_text_list):
        conf_score = bound[2]
        if conf_score > 0.2:
            p0,p1,p2,p3 = bound[0]
            top_left_x = int(p0[0])
            top_left_y = int(p0[1])
            bottom_right_x = int(p2[0])
            bottom_right_y = int(p2[1])

            x, y, width, height = top_left_x, top_left_y, (bottom_right_x - top_left_x), (bottom_right_y - top_left_y)

            image_copy = np.array(image_copy)
            image_copy[y:y + height, x:x + width] = (255, 255, 230)

            org = (x , y + int(height*0.8))
            font = cv2.FONT_HERSHEY_SIMPLEX
            
            try:
                fontScale = get_optimal_font_scale(text,width,height)
            except Exception as e:
                print(e)
                fontScale = font_scale #0.5
            image_copy = cv2.putText(image_copy, text, org, font,fontScale,(0.1, 0, 0 ,255), thickness)
    
    #save
    image_1 = Image.fromarray(np.array(image_copy), 'RGB')
    try:
        print(OUTPUT_PATH+"Translated_"+FILE_NAME.replace(".pdf","")+"_0.JPG")
        image_1.save(OUTPUT_PATH+"Translated_"+FILE_NAME.replace(".pdf","")+"_0.JPG","JPEG")
    except Exception as e:
        print(">>>>>:::",str(e))
    image_1.convert('RGB').save(OUTPUT_PATH+"Translated_"+FILE_NAME+".PDF","PDF")
################# Main ########################################
try:
    image_name = "Page_1_"+ FILE_NAME.replace(".pdf","") + ".jpg"
    #IF FILE NOT IN INPUT CONVERT FILE TO IMAGE
    # print("Page_1_"+FILE_NAME.replace(".pdf","")+".jpg")
    if "Page_1_"+FILE_NAME.replace(".pdf","")+".jpg" not in os.listdir(JPEG_PATH):
        pdfs = INPUT_PATH+FILE_NAME
        pages = convert_from_path(pdfs, TARGET_DPI)#, poppler_path=POPPLER_PATH)
        i = 1
        for page in pages:
            image_name = "Page_"+ str(i)+"_"+ FILE_NAME.replace(".pdf","") + ".jpg"
            page.save(JPEG_PATH+ image_name, "JPEG")
            i = i+1

    jpg_image = Image.open(JPEG_PATH+ image_name)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Source Document")
        expander = st.expander("Show Image", expanded= True)
        expander.image(Image.open(JPEG_PATH+ "Page_1_"+ FILE_NAME.replace(".pdf","") + ".jpg"))
        expander2= st.expander("Custom Computer Vision results", expanded= False)
        if "OCR_"+image_name in os.listdir(OCRS_PATH):
            # expander2.image(Image.open(OCRS_PATH+ "OCR_"+image_name))
            # print(">>>:","OCR_"+image_name)
            font_scale = 2
            thickness = 2
            if st.button("Translate"):
                with st.spinner("Translating the file, please wait."):
                    # translate(image_name,font_scale,thickness)
                    pass
        else:
            expander2.write("File not processed...")
            expander2.button("IDENTIFY TEXT")
            with st.spinner("Scanning the file..."):
                time.sleep(2)
                TYPE = check_type(INPUT_PATH+FILE_NAME,0.2)
            if "Translated_"+FILE_NAME not in os.listdir(OUTPUT_PATH): ###here
                if TYPE=="scanned":
                    st.info("Uploaded file is Scanned")
                    pass
                    # ocr(jpg_image)
                elif(TYPE=="nonscanned"):
                    st.info("Uploaded file is Non-Scanned")
                    if st.button("Translate"):
                        with st.spinner("Translating the file, please wait."):
                            try:
                                TYPE = get_pdf_text(FILE_NAME)
                            except Exception as e:
                                print(e)
                else:
                    print("cant decide if scanned or not")
            expander2.write("File processed.")

    with col2:
        st.subheader("Translated Document")
        expander3 = st.expander("Show Image", expanded= True)
        try:
            if TYPE=="nonscanned":
                expander3.image(Image.open(OUTPUT_PATH+"Translated_"+FILE_NAME.replace(".pdf","")+"_0.JPG"))
            else:
                expander3.image(Image.open(OUTPUT_PATH+"Translated_"+FILE_NAME.replace(".pdf","")+"_0.JPG"))
                with open(OUTPUT_PATH+"Translated_"+FILE_NAME.replace(".pdf","")+"_0.JPG", 'rb') as f:
                    st.download_button('Download', f, file_name=FILE_NAME+"_translated_save.jpg")
        except Exception as e:
            print(str(e))
            st.write("File not translated or Cant open the file.")

except Exception as e:
    st.error("**No File to translate.**")
    traceback.print_exc()




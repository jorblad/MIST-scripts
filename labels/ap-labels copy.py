from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

import pprint as pp
import sys
import argparse
import zipfile
from collections import Counter
import json


def extract_esx_data(input_file):
    project = {}
    access_points = {}
    try:
        with zipfile.ZipFile(input_file, "r") as z:
            if "project.json" in z.namelist():
                with z.open("project.json") as f:
                   data = f.read()
                   project = json.loads(data.decode("utf-8"))
            if "accessPoints.json" in z.namelist():
                print("found accessPoints.json")
                with z.open("accessPoints.json") as f:
                   data = f.read()
                   access_points = json.loads(data.decode("utf-8"))
    except Exception as e:
       print(e)
    return project, access_points


styles = getSampleStyleSheet()
style = styles["BodyText"]

#Getting the imported AP-modles to create packinglist
project, access_points = extract_esx_data('Eklandaskolan_ver2.esx')

access_points = access_points['accessPoints']

ap_models = Counter(access_point['model'] for access_point in access_points if access_point.get('model'))
ap_models = dict(ap_models)
print(ap_models)
label_file_url = "packlist.pdf"
label_title = str("Eklandaskolan")
#Creating packinglist
styles = getSampleStyleSheet()
style = styles["BodyText"]
header = Paragraph(
    "<bold><font size=15>{}</font></bold>".format(label_title), style)
canvas = Canvas(label_file_url, pagesize=(6.2 * cm, 4 * cm))
#canvas.drawString(0.1 * cm, 8.2 * cm, label_title)
aW = 6 * cm
aH = 3 * cm
w, h = header.wrap(aW, aH)
header.drawOn(canvas, 5, aH)
for ap_model in ap_models:
    aH = aH - h
    ap_model_str = str("{}: {}st".format(ap_model, ap_models[ap_model]))
    ap_model_text = Paragraph(
    "<font size=15>{}</font>".format(ap_model_str), style)
    ap_model_text.wrap(aW, aH)
    ap_model_text.drawOn(canvas, 5, aH)
    aH = aH - h
    #canvas.drawString(0.1 * cm, 0.2 * cm, ap_model_str)
    print(ap_model_str)
#canvas.showPage()
canvas.save()

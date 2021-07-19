from __future__ import division, print_function, absolute_import, unicode_literals
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import cm

import re
import subprocess
import sys
import os

printer_name = "Brother QL-700"
label_file = "ap-labels.pdf"

def inputMAC():
    while True:
        print("Enter mac-address:")
        inp = input()  # raw_input in Python 2.x
        if re.match(r'[a-fA-F0-9]{12}$', inp):
            return inp
        print('Invalid MAC, please enter again:')

canvas = Canvas(label_file, pagesize=(6.2 * cm, 1 * cm))
for i in range(8):
    mac = inputMAC()
    canvas.setFont("Courier", 24)
    canvas.drawString(0.1 * cm, 0.2 * cm, mac)
    canvas.showPage()
canvas.save()

# acroread = r'C:\Program Files (x86)\Adobe\Reader 11.0\Reader\AcroRd32.exe'
acrobat = r'C:\Program Files (x86)\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe'

# '"%s"'is to wrap double quotes around paths
# as subprocess will use list2cmdline internally if we pass it a list
# which escapes double quotes and Adobe Reader doesn't like that

cmd = '"{}" /N /T "{}" "{}"'.format(acrobat, label_file, printer_name)

proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE)
stdout, stderr = proc.communicate()
exit_code = proc.wait()
if os.path.exists(label_file):
  os.remove(label_file)
else:
  print("The file does not exist")

# coding: utf8
import requests
import json
import csv
import time
import yaml
import pandas
import os

from datetime import datetime
from re import search

# import the corresponding modules for email
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='/opt/scripts/logs/ApPerAdress.log', level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')

with open('/opt/scripts/ap/config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

base_url = config['mist']['base_url']
org_id = config['mist']['org_id']

mist_token = config['mist']['mist_token']
authorization = "Token {}".format(mist_token)

headers = {
    'Content-Type': 'application/json',
    'Authorization': authorization
}

#Regex for filtering out so that we only show sites that have a shortname
# which is how we decide if a site is just for lab or a actual site
regex_sitename = config['report']['regex_sitename']
#Regex for empty json to hide sites without any accesspoints.
regex_empty = "^\[\]$"

report_file = '{}/{}{}.xlsx'.format(config['report']['file_path'], config['report']
                                    ['filename'], str(datetime.now().strftime('%Y_%m_%d_%H_%M_%S')))
report_file_name = os.path.basename(report_file)

sites_url = "{}/orgs/{}/sites".format(base_url, org_id)

resultssites = requests.get(sites_url, headers=headers)
sites = json.loads(resultssites.text)

#email settings
smtp_port = config['email']['smtp_port']
smtp_server = config['email']['smtp_server']
smtp_login = config['email']['smtp_username']
smtp_password = config['email']['smtp_password']
sender_email = config['email']['sender_email']
receiver_email = config['report']['receiver_email']
message = MIMEMultipart("alternative")
message["Subject"] = "Netscript AP-rapport"
message["From"] = sender_email
message["To"] = receiver_email


dict_data = []
dict_sites = {}

for site in sites:
    if search(regex_sitename, site['name']):
        #print(site)
        for sitegroup in site['sitegroup_ids']:
            #print(sitegroup)
            sitegroup_url = "{}/orgs/{}/sitegroups/{}".format(base_url, org_id, sitegroup)
            resultsitegroup = requests.get(sitegroup_url, headers=headers)
            sitegroups = json.loads(resultsitegroup.text)
            sitegroup_name = sitegroups['name']


        #Log name and ID to file
        logging.info(site['name'])
        logging.info('Site-ID:')
        logging.info(site['id'])
        #Get devices on site
        device_url = "{}/sites/{}/devices".format(base_url, site["id"])
        resultsdevices = requests.get(device_url, headers=headers)
        devices = json.loads(resultsdevices.text)
        if not search(regex_empty, str(devices)):
            site_name = site['name'] + "\n"
            dict_site = {
                "site_name": site['name'],
                "site_tags": [],
            }

            dict_sites[site['name']] = {}


        #Get tags on site
        tags_url = "{}/sites/{}/wxtags".format(base_url, site["id"])
        resultstags = requests.get(tags_url, headers=headers)
        tags = json.loads(resultstags.text)

        device_lookup = {}
        device_lookup_mac = {}

        for device in devices:

            device_id = device['id']
            device_name = device['name']
            device_mac = device['mac']

            device_lookup[device_id] = device_name
            device_lookup_mac[device_id] = device_mac
        try:
            for tag in tags:
                #Logs ID and name
                logging.info(tag['name'])
                logging.info('Tag-ID:')
                logging.info(tag['id'])
                for ap in tag['values']:
                    #Logs AP ID
                    logging.info('AP-ID:')
                    logging.info(ap)
                    if tag['name'] in dict_sites[site['name']]:
                        dict_sites[site['name']][tag['name']] += 1
                    else:
                        dict_sites[site['name']][tag['name']] = 1

                    dict = {
                        "device_name": device_lookup[ap],
                        "device_tag": tag['name'],
                        "device_adress": site['name'],
                        "device_mac": device_lookup_mac[ap],
                    }
                    dict_data.append(dict)
                    device_lookup.pop(ap, None)
            for ap in device_lookup:
                    #Logs AP ID
                    logging.info('AP-ID:')
                    logging.info(ap)
                    if sitegroup_name in dict_sites[site['name']]:
                        dict_sites[site['name']][sitegroup_name] += 1
                    else:
                        dict_sites[site['name']][sitegroup_name] = 1
                    dict = {
                        "device_name": device_lookup[ap],
                        "device_tag": sitegroup_name,
                        "device_adress": site['name'],
                        "device_mac": device_lookup_mac[ap],
                    }

            if numberaps != 0:
                forvaltning_ap = tag['name'] + " " + str(numberaps) + "\n"
                #dict_sites[site['name']][tag['name']] = int(numberaps)

        except:
            pass



column_headers = ["device_name", "device_tag", "device_adress", "device_mac"]

df_aps = pandas.DataFrame(dict_data)

df_sites = pandas.DataFrame(dict_sites)
df_sites['Totalt'] = df_sites.sum(axis=1)
df_sites_t = df_sites.transpose()
# append sums to the data frame

try:
    with pandas.ExcelWriter(report_file) as writer:
        df_sites_t.to_excel(writer, sheet_name='Sites', freeze_panes=(1,0), engine='xlsxwriter', index_label='Adress')
        df_aps.to_excel(
            writer, sheet_name='APs', index=False, freeze_panes=(1,0), engine='xlsxwriter')
        worksheet_sites = writer.sheets['Sites']
        worksheet_aps = writer.sheets['APs']
        worksheet_sites.set_column('A:A', 40)
        worksheet_sites.set_column('B:V', 5)
        worksheet_aps.set_column('A:A', 40)
        worksheet_aps.set_column('B:B', 12)
        worksheet_aps.set_column('C:C', 40)
        worksheet_aps.set_column('D:D', 14)

except Exception as e:
    print(e)

#Mail the result
# write the plain text part
text = """\
Godmorgon
Här kommer månadens rapport med MIST-accesspunkter
"""
# write the HTML part
html = """\
<html>
  <body>
    <p>Godmorgon!<br>
    <p> Här kommer månadens rapport med MIST-accesspunkter</p>
  </body>
</html>
"""
# convert both parts to MIMEText objects and add them to the MIMEMultipart message
part1 = MIMEText(text, "plain")
part2 = MIMEText(html, "html")

# We assume that the file is in the directory where you run your Python script from
with open(report_file, "rb") as attachment:
    # The content type "application/octet-stream" means that a MIME attachment is a binary file
    part = MIMEBase("application", "octet-stream")
    part.set_payload(attachment.read())

# Encode to base64
encoders.encode_base64(part)

# Add header
part.add_header(
    "Content-Disposition",
    f"attachment; filename= {report_file_name}",
)

message.attach(part1)
message.attach(part2)

message.attach(part)
text = message.as_string()

# send your email
#with smtplib.SMTP(smtp_server, smtp_port) as server:
#    server.sendmail(
#        sender_email, receiver_email.split(','), message.as_string()
#    )





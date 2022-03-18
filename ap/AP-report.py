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

#Log to a specified file
import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='/opt/scripts/logs/ApPerAdress.log', level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')

#open configuration file for use in the script
with open('/opt/scripts/ap/config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

#set variables for easy access to settings
base_url = config['mist']['base_url']
org_id = config['mist']['org_id']

mist_token = config['mist']['mist_token']
authorization = "Token {}".format(mist_token)
#Set authorization header for Mist api
headers = {
    'Content-Type': 'application/json',
    'Authorization': authorization
}

#Regex for filtering out so that we only show sites that have a shortname
# which is how we decide if a site is just for lab or a actual site
regex_sitename = config['report']['regex_sitename']

#Regex to group address to be able to just pick the address itself without shortname
regex_adress = "(.*)\((....)\)"
#Regex for empty json to hide sites without any accesspoints.
regex_empty = "^\[\]$"
#Where to put the summary excelfile
report_file = '{}/{}{}.xlsx'.format(config['report']['file_path'], config['report']
                                    ['filename'], str(datetime.now().strftime('%Y_%m_%d_%H_%M_%S')))
#Where to put the csv file for importing to other
report_file_csv = '{}/{}{}.csv'.format(config['report']['file_path'], config['report']
                                    ['filename'], str(datetime.now().strftime('%Y_%m_%d_%H_%M')))
#What are the report files name
report_file_name = os.path.basename(report_file)

#API-url for sites in mist api
sites_url = "{}/orgs/{}/sites".format(base_url, org_id)

#Get sites from Mist api
resultssites = requests.get(sites_url, headers=headers)
#convert sites to dict from json
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

#Create empty dicts for ap:s and sites
dict_data = []
dict_sites = {}


#Go through all sites
for site in sites:
    #Check if the site is a normal sitesite according to our namestandard
    if search(regex_sitename, site['name']):
        #Check what sitegroup the site is part of
        for sitegroup in site['sitegroup_ids']:
            #Mist API url to sitegroups
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
        #check if devices is empty or not
        if not search(regex_empty, str(devices)):
            site_name = site['name'] + "\n"
            #create dict with data of site
            dict_site = {
                "site_name": site['name'],
                "site_tags": [],
            }
            #add dict to site list
            dict_sites[site['name']] = {}


        #Get tags on site
        tags_url = "{}/sites/{}/wxtags".format(base_url, site["id"])
        resultstags = requests.get(tags_url, headers=headers)
        tags = json.loads(resultstags.text)

        device_lookup = {}
        device_lookup_mac = {}
        #loop through devices on site
        for device in devices:

            device_id = device['id']
            device_name = device['name']
            device_mac = device['mac']
            #Add devicename and AP to separate lists
            device_lookup[device_id] = device_name
            device_lookup_mac[device_id] = device_mac
        #Look for AP tag
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
                    #Add number of AP if site tag and ap tag matches
                    if tag['name'] in dict_sites[site['name']]:
                        dict_sites[site['name']][tag['name']] += 1
                    else:
                        dict_sites[site['name']][tag['name']] = 1
                    #Add device to dict for csv and excel export
                    dict = {
                        "device_name": device_lookup[ap],
                        "device_tag": tag['name'],
                        "device_adress": search(regex_adress, site['name']).group(1),
                        "device_mac": device_lookup_mac[ap],
                    }
                    #Add to list
                    dict_data.append(dict)
                    #Delete ap from device lookup
                    device_lookup.pop(ap, None)
            #go through ap that has no tag
            for ap in device_lookup:
                #Logs AP ID
                logging.info('AP-ID:')
                logging.info(ap)
                #Add to site ap number
                if sitegroup_name in dict_sites[site['name']]:
                    dict_sites[site['name']][sitegroup_name] += 1
                else:
                    dict_sites[site['name']][sitegroup_name] = 1
                #Add ap to dict
                dict = {
                    "device_name": device_lookup[ap],
                    "device_tag": sitegroup_name,
                    "device_adress": search(regex_adress, site['name']).group(1),
                    "device_mac": device_lookup_mac[ap],
                }
                #Add to dict
                dict_data.append(dict)
                #Add tag from site to tag without tag
                for tag in tags:
                    if tag['name'] == sitegroup_name:

                        tag['values'].append(ap)
                        #API url for adding ap to tag
                        add_ap_url = "{}/sites/{}/wxtags/{}".format(
                            base_url, site['id'], tag['id'])
                        #API-call to add ap to tag
                        result_add_ap = requests.put(
                            add_ap_url, data=json.dumps(tag), headers=headers)
                        logging.debug(json.dumps(result_add_ap.text))

        except:
            pass

#Column headers for the csv_file
column_headers = ["device_name", "device_tag", "device_adress", "device_mac"]


#Export data as csv for combination with Cisco for invoicing purposes
with open(report_file_csv, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=column_headers)
    writer.writeheader()
    writer.writerows(dict_data)


#Create a pandas.dataframe to export as excel
df_aps = pandas.DataFrame(dict_data)

df_sites = pandas.DataFrame(dict_sites)
#Summarize number of APs per tag
df_sites['Totalt'] = df_sites.sum(axis=1)
#transpose dataframe so that one site is one row
df_sites_t = df_sites.transpose()
# append sums to the data frame

#Create empty list for tags
forvaltningar = []

#Loop through ap:s and set json per tag
for ap in dict_data:
    forvaltning_json = {
        'forkortning': ap['device_tag'],
        'antal_aps': '',
        'kostnad': ''
    }
    if forvaltning_json not in forvaltningar:
        forvaltningar.append(forvaltning_json)

#set path to tag, reports
report_date_path = os.path.join(
    config['report']['file_path'], datetime.today().strftime('%Y-%m-%d'))
#create folder for todays date
try:
    os.mkdir(report_date_path)
except Exception as e:
    print(e)

#Loop through tags
for forvaltning in forvaltningar:
    #Empty tag_ap list
    forvaltning_aps = []
    #Add ap with right tag to list
    for ap in dict_data:
        if ap['device_tag'] == forvaltning['forkortning']:
            forvaltning_aps.append(ap)
    #Empty tag_sites list
    forvaltning_sites = []
    #Add site on tag
    for site in dict_sites:
        try:
            site_json = {
                'Adress': site,
                'Antal aps': dict_sites[site][forvaltning['forkortning']]
            }
            forvaltning_sites.append(site_json)
        except:
            pass
    #Filepath for report per tag
    report_file_forvaltning = '{}/{}_{}_AP.xlsx'.format(report_date_path, forvaltning['forkortning'], str(datetime.now().strftime('%Y_%m')))
    #Create dataframe with AP:s per tag
    df_aps_forvaltning = pandas.DataFrame(forvaltning_aps)
    #Create dataframe with sites per tag
    df_sites_forvaltning = pandas.DataFrame.from_records(forvaltning_sites)
    #Create total per tag
    df_sites_forvaltning_total = {
        'Adress': 'Totalt',
        'Antal aps': sum(df_sites_forvaltning['Antal aps']),
        'Kostnad': "{} kr".format(sum(df_sites_forvaltning['Antal aps'])*config['report']['monthly_cost_per_ap'])
    }
    #Calculate sum per tag
    forvaltning_json = {
        'forkortning': forvaltning['forkortning'],
        'antal_aps': sum(df_sites_forvaltning['Antal aps']),
        'kostnad': "{} kr".format(sum(df_sites_forvaltning['Antal aps'])*config['report']['monthly_cost_per_ap'])
    }
    #Update dict
    forvaltning.update(forvaltning_json)
    #Add tag data to tag_sites
    forvaltning_sites.append(df_sites_forvaltning_total)
    #Convert to dataframe
    df_sites_forvaltning = pandas.DataFrame.from_records(forvaltning_sites)

    try:
        #Create excel-file per tag
        with pandas.ExcelWriter(report_file_forvaltning) as writer:
            #Write to sheet Sites and freeze first row
            df_sites_forvaltning.to_excel(writer, sheet_name='Sites', freeze_panes=(
                1, 0), engine='xlsxwriter', index=False)
            #Write to sheet APs and freeze first row
            df_aps_forvaltning.to_excel(
                writer, sheet_name='APs', index=False, freeze_panes=(1, 0), engine='xlsxwriter')
            worksheet_sites = writer.sheets['Sites']
            worksheet_aps = writer.sheets['APs']
            #Set column widths for Sites
            worksheet_sites.set_column('A:A', 40)
            worksheet_sites.set_column('B:V', 12)
            #Set column widths for APs
            worksheet_aps.set_column('A:A', 40)
            worksheet_aps.set_column('B:B', 12)
            worksheet_aps.set_column('C:C', 40)
            worksheet_aps.set_column('D:D', 14)

    except Exception as e:
        print(e)

#Convert forvatlningar/tags to dataframe
df_forvaltningar = pandas.DataFrame(forvaltningar)

try:
    #Create excel-file
    with pandas.ExcelWriter(report_file) as writer:
        #Write to sheet Sites, freeze first row and label the index as Adress
        df_sites_t.to_excel(writer, sheet_name='Sites', freeze_panes=(
            1, 0), engine='xlsxwriter', index_label='Adress')
        #Write to sheet Förvaltningar/tags, freeze first row and add headers as "Förvaltning", "Antal aps", "Kostnad"
        df_forvaltningar.to_excel(writer, sheet_name='Förvaltningar', freeze_panes=(
            1, 0), engine='xlsxwriter', index=False, header=("Förvaltning", "Antal aps", "Kostnad"))
        #Write to sheet APs and freeze first row
        df_aps.to_excel(
            writer, sheet_name='APs', index=False, freeze_panes=(1, 0), engine='xlsxwriter')
        worksheet_sites = writer.sheets['Sites']
        worksheet_aps = writer.sheets['APs']
        worksheet_forvaltningar = writer.sheets['Förvaltningar']
        #Set column witdhts for sites
        worksheet_sites.set_column('A:A', 40)
        worksheet_sites.set_column('B:V', 5)
        #Set column witdhts for tags
        worksheet_forvaltningar.set_column('A:A', 10)
        worksheet_forvaltningar.set_column('B:V', 10)
        #Set column witdhts for aps
        worksheet_aps.set_column('A:A', 40)
        worksheet_aps.set_column('B:B', 12)
        worksheet_aps.set_column('C:C', 40)
        worksheet_aps.set_column('D:D', 14)

except Exception as e:
    print(e)

#Mail the result
# write the plain text part
#Using \\ to escape so that it shows in the email
text = """\
Godmorgon
Här kommer månadens rapport med MIST-accesspunkter, resten av rapporterna finns på G:\IT-avdelningen special\mist\\reports\{}
""".format(datetime.today().strftime('%Y-%m-%d'))
# write the HTML part
html = """\
<html>
  <body>
    <p>Godmorgon!<br>
    <p> Här kommer månadens rapport med MIST-accesspunkter, resten av rapporterna finns på G:\IT-avdelningen special\mist\\reports\{}</p>
  </body>
</html>
""".format(datetime.today().strftime('%Y-%m-%d'))
# convert both parts to MIMEText objects and add them to the MIMEMultipart message
part1 = MIMEText(text, "plain")
part2 = MIMEText(html, "html")

# Open the report_file to add as a attachment
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
#Put the message together
message.attach(part1)
message.attach(part2)

message.attach(part)
text = message.as_string()
#A hardcoded if so that its easy to turn off email when testing the script
if True:
    # send your email
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.sendmail(
            sender_email, receiver_email.split(','), message.as_string()
        )





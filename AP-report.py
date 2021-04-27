# coding: utf8
import requests
import json
import csv
import time
import yaml
import pandas

from datetime import datetime
from re import search


import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', filename='ApPerAdress.log',
                    encoding='utf-8', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')

with open('config.yaml') as f:
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

sites_url = "{}/orgs/{}/sites".format(base_url, org_id)

resultssites = requests.get(sites_url, headers=headers)
sites = json.loads(resultssites.text)


dict_data = []
dict_sites = {}

for site in sites:
    if search(regex_sitename, site['name']):

        #Log name and ID to file
        logging.info(site['name'])
        logging.info('Site-ID:')
        logging.info(site['id'])
        #Get devices on site
        device_url = "{}/sites/{}/devices".format(base_url, site["id"])
        resultsdevices = requests.get(device_url, headers=headers)
        devices = json.loads(resultsdevices.text)
        if not search(regex_empty, str(devices)):
            print(site['name'])
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

        for tag in tags:
            #Logs ID and name
            logging.info(tag['name'])
            logging.info('Tag-ID:')
            logging.info(tag['id'])
            numberaps = 0
            for ap in tag['values']:
                #Logs AP ID
                logging.info('AP-ID:')
                logging.info(ap)

                numberaps += 1

                dict = {
                    "device_name": device_lookup[ap],
                    "device_tag": tag['name'],
                    "device_adress": site['name'],
                    "device_mac": device_lookup_mac[ap],
                }
                dict_data.append(dict)
            if numberaps != 0:
                print(tag['name'], " ", numberaps)
                forvaltning_ap = tag['name'] + " " + str(numberaps) + "\n"
                dict_sites[site['name']][tag['name']] = int(numberaps)


column_headers = ["device_name", "device_tag", "device_adress", "device_mac"]

df_aps = pandas.DataFrame(dict_data)

df_sites = pandas.DataFrame(dict_sites)
df_sites_t = df_sites.transpose()
print(df_sites_t)
try:
    with pandas.ExcelWriter(report_file) as writer:
                            df_sites_t.to_excel(writer, sheet_name='Sites', freeze_panes=(1,0), engine='xlsxwriter', index_label='Adress')
                            df_aps.to_excel(
                                writer, sheet_name='APs', index=False, freeze_panes=(1, 0), engine='xlsxwriter')
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



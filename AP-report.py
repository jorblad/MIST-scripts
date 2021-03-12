import requests
import json
import csv
import time

from datetime import datetime

import logging
logging.basicConfig(filename='logg.log', encoding='utf-8', level=logging.DEBUG)
#Edit base-url if you are not using the EU-environment
base_url = 'https://api.eu.mist.com/api/v1/'
#The organisation-ID for your organisation
org_id = '...'
#Your MIST API token
mist_token = '...'


authorization = "Token {}".format(mist_token)

headers = {
    'Content-Type': 'application/json',
    'Authorization': authorization
}

report_file = 'reports/AP_Inventory_Org_' + \
    str(datetime.now().strftime('%Y_%m_%d_%H_%M_%S')) + '.csv'

sites_url = "{}/orgs/{}/sites".format(base_url, org_id)

resultssites = requests.get(sites_url, headers=headers)
sites = json.loads(resultssites.text)

dict_data = []

for site in sites:
    print(site['name'])
    #Log name and ID to file
    logging.info(site['name'])
    logging.info('Site-ID:')
    logging.info(site['id'])
    #Get devices on site
    device_url = "{}/sites/{}/devices".format(base_url, site["id"])
    resultsdevices = requests.get(device_url, headers=headers)
    devices = json.loads(resultsdevices.text)
    #Get tags on site
    tags_url = "{}/sites/{}/wxtags".format(base_url, site["id"])
    resultstags = requests.get(tags_url, headers=headers)
    tags = json.loads(resultstags.text)

    device_lookup = {}

    for device in devices:

        device_id = device['id']
        device_name = device['name']

        device_lookup[device_id] = device_name

    #print (device_lookup)



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
            #print(device_lookup[ap])
            numberaps += 1

            dict = {
                "device_name": device_lookup[ap],
                "device_tag": tag['name'],
                "device_adress": site['name'],
            }
            dict_data.append(dict)

        print(tag['name'], " ", numberaps)
#print(dict_data)

column_headers = ["device_name", "device_tag", "device_adress"]

try:
    with open(report_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=column_headers)
        writer.writeheader()

        for dict in dict_data:
            writer.writerow(dict)

except IOError as err:
    logging.error("CSV I/O error: {}".format(err))
        #print(tag['name'], " ",numberaps)
    #for device in devices:
        #print(device['name'], ">", device["id"], ">", )

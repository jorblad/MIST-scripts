import requests
import json
import yaml
import orionsdk
import xmltodict

from re import search
from scrapli import Scrapli

import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='Mist-api.log', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')


with open('../django-script/netscripts/mist_import_sites/config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

#base_url = config['mist']['base_url']

import_file = config['import']['import_file']

import_file_sheet = config['import']['import_sheet']

import_path_ekahau = config['import']['import_ekahau_path']

regex_sitename = config['report']['regex_sitename']

# Configure True/False to enable/disable additional logging of the API response objects
show_more_details = config['import']['show_more_details']

# Your Google API key goes here. Documentation: https://cloud.google.com/docs/authentication/api-keys
google_api_key = config['google']['google_api_key']

# Your Mist API token goes here. Documentation: https://api.mist.com/api/v1/docs/Auth#api-token
mist_api_token = config['mist']['mist_token']

org_id = config['mist']['org_id']  # Your Organization ID goes here

base_url = config['mist']['base_url']

printer_name = config['printing']['label_printer']
label_file = config['printing']['file_name']

authorization = "Token {}".format(mist_api_token)

headers = {
    'Content-Type': 'application/json',
    'Authorization': authorization
}

regex_shortname = ".*\((....)\)"

##Switch variables
switch_username = config['switch']['username']
switch_password = config['switch']['password']
solarwinds_username = config['solarwinds']['username']
solarwinds_password = config['solarwinds']['password']
solarwinds_certificate = config['solarwinds']['certificate_file']

def addVlansToSwitch(switch):
    device = {
        "host": switch['IPAddress'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch['Caption'], switch['IPAddress']))
    conn = Scrapli(**device)
    conn.open()
    response = conn.send_command("show chassis hardware | display xml")
    response_dict = xmltodict.parse(response.result)
    response_json = json.dumps(response_dict)
    switch_hardware = json.loads(response_json)[
        'rpc-reply']['chassis-inventory']['chassis']
    switch_model = switch_hardware['description']
    print(switch_model)
    if "EX2300" in switch_model:
        response = conn.send_command(
            "show configuration interfaces interface-range uplink")
        if "unit 0" in response.result:
            response = conn.send_config(
                "set interfaces interface-range uplink unit 0 family ethernet-switching vlan members chromebook")
        response = conn.send_config(
            "set interfaces interface-range downlink unit 0 family ethernet-switching vlan members chromebook")
        response = conn.send_config(
            "set interfaces interface-range ap unit 0 family ethernet-switching vlan members chromebook")
        response = conn.send_config(
            "set vlans chromebook vlan-id 40")
        response = conn.send_config(
            'commit confirmed 5 comment "MIST preparation"')
        response = conn.send_config(
            'commit')
    elif "EX2200" in switch_model:
        response = conn.send_command(
            "show configuration interfaces interface-range uplink")
        if "unit 0" in response.result:
            response = conn.send_config(
                "set vlans chromebook interface uplink")
        response = conn.send_config(
            "set vlans chromebook interface downlink")
        response = conn.send_config(
            "set vlans chromebook interface ap")
        response = conn.send_config(
            "set vlans chromebook vlan-id 40")
        response = conn.send_config(
            'commit confirmed 5 comment "Chromebook-vlan preparation"')
        response = conn.send_config(
            'commit')


    logging.info(response.elapsed_time)
    logging.info(response.result)
    print(response.result)
    conn.close()

def findSwitches(shortname):

    print('\n\n==========\n\n')
    print("Adding Vlans byod and guest to switches on site")
    session = requests.Session()
    session.timeout = 30  # Set your timeout in seconds
    logging.info("Connecting to Solarwinds")
    swis = orionsdk.SwisClient("SolarWinds-Orion", solarwinds_username,
                                solarwinds_password, verify=False, session=session)
    logging.info("Getting switches that belong to the site")
    nodes = swis.query(
        "SELECT NodeID, Caption, IPAddress, Status FROM Orion.Nodes WHERE Caption LIKE 'swa-%-{}' AND Status LIKE 1".format(shortname))
    switch_number = 0
    switches = nodes['results']
    for switch in switches:
        print(switch)
        addVlansToSwitch(switch)
        switch_number += 1

    print("Updated settings on {} switches".format(switch_number))
try:
    sites_url = "{}/orgs/{}/sites".format(base_url, org_id)

    resultssites = requests.get(sites_url, headers=headers)
    sites = json.loads(resultssites.text)

    for site in sites:
        if search(regex_sitename, site['name']):
            print(site['name'])
            shortname = search(regex_shortname, site['name']).group(1)
            findSwitches(shortname)
            print('Vlan tillagda till site {}'.format(site['name']))

except:
    print("Kan inte lista siter")

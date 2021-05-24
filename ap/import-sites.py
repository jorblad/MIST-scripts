#!/usr/bin/python
#
# main.py
#
# Update the script with the necessary information to create sites from a CSV file.

import sys
import time
import requests
import csv
import json
import yaml
import pandas
import re
import os
import orionsdk
import xmltodict
import glob


from scrapli import Scrapli

import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', filename='../logs/SiteImport.log', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')


with open('config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

#base_url = config['mist']['base_url']

import_file = config['import']['import_file']

import_file_sheet = config['import']['import_sheet']

import_path_ekahau = config['import']['import_ekahau_path']

# Configure True/False to enable/disable additional logging of the API response objects
show_more_details = config['import']['show_more_details']

# Your Google API key goes here. Documentation: https://cloud.google.com/docs/authentication/api-keys
google_api_key = config['google']['google_api_key']

# Your Mist API token goes here. Documentation: https://api.mist.com/api/v1/docs/Auth#api-token
mist_api_token = config['mist']['mist_token']

org_id = config['mist']['org_id']  # Your Organization ID goes here

base_url = config['mist']['base_url']

authorization = "Token {}".format(mist_api_token)

headers = {
    'Content-Type': 'application/json',
    'Authorization': authorization
}

##Switch variables
switch_username = config['switch']['username']
switch_password = config['switch']['password']
solarwinds_username = config['solarwinds']['username']
solarwinds_password = config['solarwinds']['password']
solarwinds_certificate = config['solarwinds']['certificate_file']

# Google geocode the site address.
# Note: The Google Maps Web Services Client Libraries could also be used, rather than directly calling the REST APIs.
# Documentation: https://developers.google.com/maps/documentation/geocoding/client-library
def geocode(address):
    if address is None or address == '':
        return (False, 'Missing site address')

    try:
        # Establish Google session
        google = Google(google_api_key)

        # Call the Google Geocoding API: https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={google_api_key}
        # Documentation: https://developers.google.com/maps/documentation/geocoding/intro
        print('Calling the Google Geocoding API...')
        logging.info('Calling the Google Geocoding API...')
        url = 'https://maps.googleapis.com/maps/api/geocode/json?address={}'.format(address.replace(' ', '+'))
        result = google.get(url)
        if result == False:
            return (False, 'Failed to get Geocoding')

        if show_more_details:
            print('\nRetrieving the JSON response object...')
            logging.info('\nRetrieving the JSON response object...')
            #print(json.dumps(result, sort_keys=True, indent=4))
            logging.debug(json.dumps(result, sort_keys=True, indent=4))

        gaddr = result['results'][0]
        if show_more_details:
            print('\nRetrieving the results[0] object...')
            logging.info('\nRetrieving the results[0] object...')
            #print(json.dumps(gaddr, sort_keys=True, indent=4))
            logging.debug(json.dumps(gaddr, sort_keys=True, indent=4))

        location = gaddr['geometry']['location']
        if show_more_details:
            print('\nRetrieving the geometry.location object...')
            logging.info('\nRetrieving the geometry.location object...')
            #print(json.dumps(location, sort_keys=True, indent=4))
            logging.debug(json.dumps(location, sort_keys=True, indent=4))
            print('\nUsing lat and lng in the Google Time Zone API request')
            logging.info(
                '\nUsing lat and lng in the Google Time Zone API request')

        print()

        # Call the Google Time Zone API: https://maps.googleapis.com/maps/api/timezone/json?location={lat},{lng}&timestamp={timestamp}&key={google_api_key}
        # Documentation: https://developers.google.com/maps/documentation/timezone/start
        print('Calling the Google Time Zone API...')
        logging.info('Calling the Google Time Zone API...')
        url = 'https://maps.googleapis.com/maps/api/timezone/json?location={},{}&timestamp={}'.format(location['lat'], location['lng'], int(time.time()))
        result = google.get(url)
        if result == False:
            return (False, 'Failed to get Time Zone')

        gtz = result
        if show_more_details:
            print('\nRetrieving the JSON response object...')
            logging.info('\nRetrieving the JSON response object...')
            #print(json.dumps(result, sort_keys=True, indent=4))
            logging.debug(json.dumps(result, sort_keys=True, indent=4))

        print()
    except Exception as e:
        return (False, str(e))

    results = {
        'address':
        gaddr['formatted_address'],
        'latlng': {
            'lat': location['lat'],
            'lng': location['lng'],
        },
        'country_code': [ x['short_name'] for x in gaddr['address_components'] if 'country' in x['types'] ][0],
        'timezone':
        gtz['timeZoneId']
    }

    return (True, results)


#Defining postalcode cleanup for swedish postalcodes

def postalcode_cleanup(postalcode):
    site_postalcode_org = str(postalcode).strip()
    site_postalcode = "{} {}".format(
        site_postalcode_org[:3], site_postalcode_org[-2:])
    return site_postalcode

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
    switch_hardware = json.loads(response_json)['rpc-reply']['chassis-inventory']['chassis']
    switch_model = switch_hardware['description']
    print(switch_model)
    if "EX2300" in switch_model:
        response = conn.send_command(
            "show configuration interfaces interface-range uplink")
        if "unit 0" in response.result:
            response = conn.send_config(
                "set interfaces interface-range uplink unit 0 family ethernet-switching vlan members byod")
            response = conn.send_config(
                "set interfaces interface-range uplink unit 0 family ethernet-switching vlan members guest")
        response = conn.send_config(
            "set interfaces interface-range downlink unit 0 family ethernet-switching vlan members byod")
        response = conn.send_config(
            "set interfaces interface-range downlink unit 0 family ethernet-switching vlan members guest")
        response = conn.send_config(
            "set interfaces interface-range ap unit 0 family ethernet-switching vlan members byod")
        response = conn.send_config(
            "set interfaces interface-range ap unit 0 family ethernet-switching vlan members guest")
        response = conn.send_config(
            "set vlans byod vlan-id 39")
        response = conn.send_config(
            "set vlans guest vlan-id 38")
        response = conn.send_config(
            'commit comment "MIST preparation"')
    elif "EX2200" in switch_model:
        response = conn.send_command(
            "show configuration interfaces interface-range uplink")
        if "unit 0" in response.result:
            response = conn.send_config(
                "set vlans byod interface uplink")
            response = conn.send_config(
                "set vlans guest interface uplink")
        response = conn.send_config(
            "set vlans byod interface downlink")
        response = conn.send_config(
            "set vlans guest interface downlink")
        response = conn.send_config(
            "set vlans byod interface ap")
        response = conn.send_config(
            "set vlans guest interface ap")
        response = conn.send_config(
            "set vlans byod vlan-id 39")
        response = conn.send_config(
            "set vlans guest vlan-id 38")
        response = conn.send_config(
            'commit comment "MIST preparation"')

    #poe_interface_power = interface_poe['rpc-reply']['poe']['interface-information-detail']['interface-power-detail']
    #response = conn.send_config("commit confirmed 2")
    logging.info(response.elapsed_time)
    logging.info(response.result)
    print(response.result)
    conn.close()
# Google CRUD operations
class Google(object):
    def __init__(self, key=''):
        self.session = requests.Session()
        self.key = key

    def get(self, url):
        url += '&key={}'.format(self.key)
        session = self.session

        print('GET {}'.format(url))
        logging.info('GET {}'.format(url))
        response = session.get(url)

        if response.status_code != 200:
            print('Failed to GET')
            logging.warning('Failed to GET')
            print('\tURL: {}'.format(url))
            logging.warning('\tURL: {}'.format(url))
            print('\tResponse: {} ({})'.format(response.text, response.status_code))
            logging.warning('\tResponse: {} ({})'.format(
                response.text, response.status_code))

            return False

        return json.loads(response.text)


# Mist CRUD operations
class Admin(object):
    def __init__(self, token=''):
        self.session = requests.Session()
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Token ' + token
        }

    def post(self, url, payload, timeout=60):
        url = '{}{}'.format(config['mist']['base_url'], url)
        session = self.session
        headers = self.headers

        print('POST {}'.format(url))
        logging.info('POST {}'.format(url))
        response = session.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            print('Failed to POST')
            logging.warning('Failed to POST')
            print('\tURL: {}'.format(url))
            logging.warning('\tURL: {}'.format(url))
            print('\tPayload: {}'.format(payload))
            logging.warning('\tPayload: {}'.format(payload))
            print('\tResponse: {} ({})'.format(response.text, response.status_code))
            logging.warning('\tResponse: {} ({})'.format(response.text, response.status_code))

            return False

        return json.loads(response.text)

    def put(self, url, payload):
        url = '{}{}'.format(
            config['mist']['base_url'], url)
        session = self.session
        headers = self.headers

        print('PUT {}'.format(url))
        logging.info('PUT {}'.format(url))
        response = session.put(url, headers=headers, json=payload)

        if response.status_code != 200:
            print('Failed to PUT')
            logging.warning('Failed to PUT')
            print('\tURL: {}'.format(url))
            logging.warning('\tURL: {}'.format(url))
            print('\tPayload: {}'.format(payload))
            logging.warning('\tPayload: {}'.format(payload))
            print('\tResponse: {} ({})'.format(response.text, response.status_code))
            logging.warning('\tResponse: {} ({})'.format(
                response.text, response.status_code))

            return False

        return json.loads(response.text)




# Main function
if __name__ == '__main__':
    # Check for required variables
    if google_api_key == '':
        print('Please provide your Google API key as google_api_key')
        logging.error('Please provide your Google API key as google_api_key')
        sys.exit(1)
    elif mist_api_token == '':
        print('Please provide your Mist API token as mist_api_token')
        logging.error('Please provide your Mist API token as mist_api_token')
        sys.exit(1)
    elif org_id == '':
        print('Please provide your Mist Organization UUID as org_id')
        logging.error('Please provide your Mist Organization UUID as org_id')
        sys.exit(1)

    # Establish Mist session
    admin = Admin(mist_api_token)

    # Convert excel to valid JSON
    excel_data_df = pandas.read_excel(import_file, sheet_name=import_file_sheet)

    data = excel_data_df.to_dict(orient='records')

    if data == None or data == []:
        print('Failed to convert Excel file to JSON. Exiting script.')
        logging.error('Failed to convert Excel file to JSON. Exiting script.')
        sys.exit(2)

    number_sites = 0

    sitegroup_lookup = {}
    # Create each site from the CSV file
    for d in data:

        #Kolla verksamheter
        sitegroups_url = "{}/orgs/{}/sitegroups".format(base_url, org_id)
        sitegroups_result = requests.get(sitegroups_url, headers=headers)
        sitegroups = json.loads(sitegroups_result.text)

        #Kolla sites for dubletter
        sites_url = "{}/orgs/{}/sites".format(base_url, org_id)
        sites_result = requests.get(sites_url, headers=headers)
        sites = json.loads(sites_result.text)

        # Variables
        site_id = None
        site_address = "{}, {}, {}".format(d.get('Gatuadress'), postalcode_cleanup(d.get('Postnummer')), config['mist']['config']['country'])
        site_verksamhet = ''
        site_exists = False
        for site in sites:
            if site['name'] == "{} ({})".format(d.get('Gatuadress'), d.get('Forkortning')):
                print("Site {} ({}) already exists".format(
                    d.get('Gatuadress'), d.get('Forkortning')))
                logging.info("Site {} ({}) already exists".format(
                    d.get('Gatuadress'), d.get('Forkortning')))
                print('\n\n==========\n\n')
                site_exists = True

        if site_exists:
            continue


        sitegroup_json = {
            'name': "{}".format(d.get('Verksamhet'))
        }

        #Check if site group name is existing
        for sitegroup in sitegroups:
            if sitegroup['name'] == d.get('Verksamhet'):
                site_verksamhet = sitegroup['id']
        if not site_verksamhet:
            print('Calling the Mist Create Sitegroup API...')
            logging.info('Calling the Mist Create Sitegroup API...')
            result = admin.post('/orgs/' + org_id + '/sitegroups', sitegroup_json)
            if result == False:
                print('Failed to create sitegroup {}'.format(d.get('Verksamhet')))
                logging.warning(
                    'Failed to create sitegroup {}'.format(d.get('Verksamhet')))
                print('\n\n==========\n\n')
            site_verksamhet = result['id']
            print('\n\n==========\n\n')
        #Takes the field from the excel-file and create the site from that
        site = {
            'name': "{} ({})".format(d.get('Gatuadress'), d.get('Forkortning')),
            "sitegroup_ids": [
                "{}".format(site_verksamhet)
            ],
            "notes": "{}, {}".format(d.get('Popularnamn', ''), d.get('Forkortning')),
            "rftemplate_id": "{}".format(config['mist']['config']['rftemplate_id'])
            }

        # Provide your Site Setting.
        #Modify if anything you need is missing otherwise change in config.yaml will work best
        # Example can be found here: https://api.mist.com/api/v1/docs/Site#site-setting
        '''
        ie:
        {
          'rtsa': { 'enabled': True },			    # Enable vBLE Engagement
          'auto_upgrade': { 'enabled': False },	# Disable Auto Upgrade
          'rogue': {
            'honeypot_enabled': True		      	# Enable Honeypot APs
            'enabled': True,					          # Enable Rogue and Neighbor APs
            'min_rssi': -80,					          # Minimum Neighbor RSSI Threshold -80
          }
        }
        '''
        site_setting = {
            "auto_upgrade": {
                "enabled": config['mist']['config']['auto_upgrade']['enabled'],
                "version": config['mist']['config']['auto_upgrade']['version'],
                "time_of_day": config['mist']['config']['auto_upgrade']['time_of_day'],
                "custom_versions": {
                    "AP33": config['mist']['config']['auto_upgrade']['custom_versions']['AP33'],
                    "AP43": config['mist']['config']['auto_upgrade']['custom_versions']['AP43']
                },
                "day_of_week": config['mist']['config']['auto_upgrade']['day_of_week']
            },
            "rtsa": {
                "enabled": config['mist']['config']['rtsa']['enabled'],
                "track_asset": config['mist']['config']['rtsa']['track_asset'],
                "app_waking": config['mist']['config']['rtsa']['app_waking']
            },
            "led": {
                "enabled": config['mist']['config']['led']['enabled'],
                "brightness": config['mist']['config']['led']['brightness']
            },
            "wifi": {
                "enabled": config['mist']['config']['wifi']['enabled'],
                "locate_unconnected": config['mist']['config']['wifi']['locate_unconnected'],
                "mesh_enabled": config['mist']['config']['wifi']['mesh_enabled'],
                "detect_interference": config['mist']['config']['wifi']['detect_interference']
            },
            "wootcloud": config['mist']['config']['wootcloud'],
            "skyatp": {
                "enabled": config['mist']['config']['skyatp']['enabled'],
                "send_ip_mac_mapping": config['mist']['config']['skyatp']['send_ip_mac_mapping']
            },
            "persist_config_on_device": config['mist']['config']['persist_config_on_device'],
            "engagement": {
                "dwell_tags": {
                    "passerby": config['mist']['config']['engagement']['dwell_tags']['passerby'],
                    "bounce": config['mist']['config']['engagement']['dwell_tags']['bounce'],
                    "engaged": config['mist']['config']['engagement']['dwell_tags']['engaged'],
                    "stationed": config['mist']['config']['engagement']['dwell_tags']['stationed']
                },
                "dwell_tag_names": {
                    "passerby": config['mist']['config']['engagement']['dwell_tag_names']['passerby'],
                    "bounce": config['mist']['config']['engagement']['dwell_tag_names']['bounce'],
                    "engaged": config['mist']['config']['engagement']['dwell_tag_names']['engaged'],
                    "stationed": config['mist']['config']['engagement']['dwell_tag_names']['stationed']
                },
                "hours": {
                    "sun": config['mist']['config']['engagement']['hours']['sun'],
                    "mon": config['mist']['config']['engagement']['hours']['mon'],
                    "tue": config['mist']['config']['engagement']['hours']['tue'],
                    "wed": config['mist']['config']['engagement']['hours']['wed'],
                    "thu": config['mist']['config']['engagement']['hours']['thu'],
                    "fri": config['mist']['config']['engagement']['hours']['fri'],
                    "sat": config['mist']['config']['engagement']['hours']['sat']
                }
            },
            "analytic": {
                "enabled": config['mist']['config']['analytic']['enabled']
            },
            "rogue": {
                "min_rssi": config['mist']['config']['rogue']['min_rssi'],
                "min_duration": config['mist']['config']['rogue']['min_duration'],
                "enabled": config['mist']['config']['rogue']['enabled'],
                "honeypot_enabled": config['mist']['config']['rogue']['honeypot_enabled'],
                "whitelisted_bssids": config['mist']['config']['rogue']['whitelisted_bssids'],
                "whitelisted_ssids": config['mist']['config']['rogue']['whitelisted_ssids']
            },
            "analytic": {
                "enabled": config['mist']['config']['rogue']['enabled']
            },
            "ssh_keys": config['mist']['config']['ssh_keys'],
            "vars": config['mist']['config']['vars'],
            "wids": config['mist']['config']['wids'],
            "mxtunnel": {
                "enabled": config['mist']['config']['mxtunnel']['enabled'],
                "vlan_ids": config['mist']['config']['mxtunnel']['vlan_ids'],
                "ap_subnets": config['mist']['config']['mxtunnel']['ap_subnets'],
                "mtu": config['mist']['config']['mxtunnel']['mtu'],
                "protocol": config['mist']['config']['mxtunnel']['protocol'],
                "clusters": config['mist']['config']['mxtunnel']['clusters']
            },
            "occupancy": {
                "min_duration": config['mist']['config']['occupancy']['min_duration'],
                "clients_enabled": config['mist']['config']['occupancy']['clients_enabled'],
                "sdkclients_enabled": config['mist']['config']['occupancy']['sdkclients_enabled'],
                "assets_enabled": config['mist']['config']['occupancy']['assets_enabled'],
                "unconnected_clients_enabled": config['mist']['config']['occupancy']['unconnected_clients_enabled']
            },
            "gateway_mgmt": {
                "app_usage": config['mist']['config']['gateway_mgmt']['app_usage']
            }
        }


        # Create Site
        (geocoded, geocoding) = geocode(site_address)
        if geocoded == True:
            site.update(geocoding)
        else:
            print('Failed to geocode...')
            logging.warning('Failed to geocode...')
            print(geocoding)
            logging.warning(geocoding)
            print()

        print('Calling the Mist Create Site API...')
        logging.info('Calling the Mist Create Site API...')
        result = admin.post('/orgs/' + org_id + '/sites', site)
        if result == False:
            print('Failed to create site {}'.format(site['name']))
            logging.warning('Failed to create site {}'.format(site['name']))
            print('Skipping remaining operations for this site...')
            logging.warning('Skipping remaining operations for this site...')
            print('\n\n==========\n\n')

            continue
        else:
            site_id = result['id']
            print('Created site {} ({})'.format(site['name'], site_id))
            logging.info('Created site {} ({})'.format(site['name'], site_id))
            number_sites += 1

            if show_more_details:
                print('\nRetrieving the JSON response object...')
                logging.info('\nRetrieving the JSON response object...')
                #print(json.dumps(result, sort_keys=True, indent=4))
                logging.debug(json.dumps(result, sort_keys=True, indent=4))
                print('\nUsing id in the Mist Update Setting API request')
                logging.info(
                    '\nUsing id in the Mist Update Setting API request')

        print()

        # Update Site Setting
        print('Calling the Mist Update Setting API...')
        logging.info('Calling the Mist Update Setting API...')
        result = admin.put('/sites/' + site_id + '/setting',
                           site_setting)
        if result == False:
            print('Failed to update site setting {} ({})'.format(site['name'], site_id))
            logging.warning('Failed to update site setting {} ({})'.format(
                site['name'], site_id))
        else:
            print('Updated site setting {} ({})'.format(site['name'], site_id))
            logging.info('Updated site setting {} ({})'.format(
                site['name'], site_id))

            if show_more_details:
                print('\nRetrieving the JSON response object...')
                logging.info('\nRetrieving the JSON response object...')
                #print(json.dumps(result, sort_keys=True, indent=4))
                logging.debug(json.dumps(result, sort_keys=True, indent=4))

        print('\n\n==========\n\n')
        # Import map
        try:
            map_url = "{}/{}/*.esx".format(import_path_ekahau,
                                        d.get('Gatuadress'))
            print(map_url)
            list_of_files = glob.glob(map_url)
            map_file_url = max(list_of_files, key=os.path.getctime)
            print(map_file_url)
            map_import_url = "{}/sites/{}/maps/import".format(base_url, site_id)
            map_import_headers = {
                'Authorization': f'token {mist_api_token}'
            }
            print('Calling the Mist import map API...')
            logging.info('Calling the Mist import map API...')
            map_import_payload = {"vendor_name": "ekahau", "import_all_floorplans": True, "import_height": True, "import_orientation": True}
            files = {
                'file': (os.path.basename(map_file_url), open(map_file_url, 'rb'), 'application/octet-stream'),
                'json': (None, json.dumps(map_import_payload), 'application/json')
            }

            response = requests.post(map_import_url, files=files, headers=map_import_headers)

            print(response.text)

            print(response)
            if response == False:
                print('Failed to import map for {} ({})'.format(
                    site['name'], site_id))
                logging.warning('Failed to import map for {} ({})'.format(
                    site['name'], site_id))
            else:
                print('Imported map for {} ({})'.format(site['name'], site_id))
                logging.info('Imported map for {} ({})'.format(
                    site['name'], site_id))

                if show_more_details:
                    print('\nRetrieving the JSON response object...')
                    logging.info('\nRetrieving the JSON response object...')
                    #print(json.dumps(result, sort_keys=True, indent=4))
                    logging.debug(json.dumps(result, sort_keys=True, indent=4))

            print('\n\n==========\n\n')
        except:
            print("Couldn't find a ekahau file")

        #Add Vlan to switches
        print('\n\n==========\n\n')
        print("Adding Vlans byod and guest to switches on site")
        session = requests.Session()
        session.timeout = 30  # Set your timeout in seconds
        logging.info("Connecting to Solarwinds")
        swis = orionsdk.SwisClient("SolarWinds-Orion", solarwinds_username,
                                solarwinds_password, verify=False, session=session)
        logging.info("Getting switches that belong to the site")
        nodes = swis.query(
            "SELECT NodeID, Caption, IPAddress, Status FROM Orion.Nodes WHERE Caption LIKE 'swa-%-{}' AND Status LIKE 1".format(d.get('Forkortning')))
        switch_number = 0
        switches = nodes['results']
        for switch in switches:
            print(switch)
            addVlansToSwitch(switch)
            switch_number += 1

        print("Updated settings on {} switches".format(switch_number))


    print('Created {} sites'.format(number_sites))

#Django libraries
from __future__ import division, print_function, absolute_import, unicode_literals
from django.contrib.messages.api import info
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.template import loader
from django.contrib import messages
from django.views.generic import TemplateView
from django.core.files.storage import FileSystemStorage

#Include forms used in these views
from .forms import SiteForm, UpdateMistForm

#Import for label creation
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

#Other imports
import sys
import time
import requests
import json
import yaml
import pandas
import re
import os
#Import solarwinds api
import orionsdk
import xmltodict
import glob
import sys
import argparse
#Used by ekahau import
import zipfile
from collections import Counter
#For regex
from re import search
#For connecting to switches
from scrapli import Scrapli

#Logging to a speciefied file
import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='../logs/Mist-api.log', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')

#Open configuration file
with open('mist_import_sites/config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

#Add variables for easy access to configuration
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
#Mist API authorization header
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

#Upload ekahau file handler
def handle_uploaded_file(f, file_path):
    with open(file_path, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)


# Google geocode the site address.
# Note: The Google Maps Web Services Client Libraries could also be used, rather than directly calling the REST APIs.
# Documentation: https://developers.google.com/maps/documentation/geocoding/client-library

#Function for getting geocode from Google, function coming from Mist class API example of using API to import sites
def geocode(request, address):
    if address is None or address == '':
        messages.warning(request, 'Mising site address')
        return (False, 'Missing site address')

    try:
        # Establish Google session
        google = Google(google_api_key)

        # Call the Google Geocoding API: https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={google_api_key}
        # Documentation: https://developers.google.com/maps/documentation/geocoding/intro
        print('Calling the Google Geocoding API...')
        logging.info('Calling the Google Geocoding API...')
        url = 'https://maps.googleapis.com/maps/api/geocode/json?address={}'.format(
            address.replace(' ', '+'))
        result = google.get(url)
        if result == False:
            messages.warning(request, 'Failed to get Geocoding')
            return (False, 'Failed to get Geocoding')

        if show_more_details:
            print('\nRetrieving the JSON response object...')
            logging.info('\nRetrieving the JSON response object...')

            logging.debug(json.dumps(result, sort_keys=True, indent=4))

        gaddr = result['results'][0]
        if show_more_details:
            print('\nRetrieving the results[0] object...')
            logging.info('\nRetrieving the results[0] object...')

            logging.debug(json.dumps(gaddr, sort_keys=True, indent=4))

        location = gaddr['geometry']['location']
        if show_more_details:
            print('\nRetrieving the geometry.location object...')
            logging.info('\nRetrieving the geometry.location object...')
            logging.debug(json.dumps(location, sort_keys=True, indent=4))
            print('\nUsing lat and lng in the Google Time Zone API request')
            logging.info(
                '\nUsing lat and lng in the Google Time Zone API request')

        print()

        # Call the Google Time Zone API: https://maps.googleapis.com/maps/api/timezone/json?location={lat},{lng}&timestamp={timestamp}&key={google_api_key}
        # Documentation: https://developers.google.com/maps/documentation/timezone/start
        print('Calling the Google Time Zone API...')
        logging.info('Calling the Google Time Zone API...')
        url = 'https://maps.googleapis.com/maps/api/timezone/json?location={},{}&timestamp={}'.format(
            location['lat'], location['lng'], int(time.time()))
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
        'country_code': [x['short_name'] for x in gaddr['address_components'] if 'country' in x['types']][0],
        'timezone':
        gtz['timeZoneId']
    }

    return (True, results)


#Defining postalcode cleanup for swedish postalcodes
def postalcode_cleanup(postalcode):
    #Strip whitespaces
    site_postalcode_org = str(postalcode).strip()
    #format as the first three numbers, whitespace and the last two numbers
    #Used so that it works aslong as the numbers are correct no mather where there are whitespaces
    site_postalcode = "{} {}".format(
        site_postalcode_org[:3], site_postalcode_org[-2:])
    return site_postalcode

#Script for adding vlans to a switch
def addVlansToSwitch(switch):
    #Device object for scrapli
    device = {
        "host": switch['IPAddress'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch['Caption'], switch['IPAddress']))
    #Connecting to switch
    conn = Scrapli(**device)
    conn.open()
    #Get switch model
    response = conn.send_command("show chassis hardware | display xml")
    response_dict = xmltodict.parse(response.result)
    response_json = json.dumps(response_dict)
    switch_hardware = json.loads(response_json)[
        'rpc-reply']['chassis-inventory']['chassis']
    switch_model = switch_hardware['description']
    #Configuration based on switch model
    #Add new VLANS here that needs to be added to all mist sites
    if "EX2300" in switch_model:
        response = conn.send_command(
            "show configuration interfaces interface-range uplink")
        if "unit 0" in response.result:
            response = conn.send_config(
                "set interfaces interface-range uplink unit 0 family ethernet-switching vlan members byod")
            response = conn.send_config(
                "set interfaces interface-range uplink unit 0 family ethernet-switching vlan members guest")
            response = conn.send_config(
                "set interfaces interface-range uplink unit 0 family ethernet-switching vlan members chromebook")
        response = conn.send_config(
            "set interfaces interface-range downlink unit 0 family ethernet-switching vlan members byod")
        response = conn.send_config(
            "set interfaces interface-range downlink unit 0 family ethernet-switching vlan members guest")
        response = conn.send_config(
            "set interfaces interface-range downlink unit 0 family ethernet-switching vlan members chromebook")
        response = conn.send_config(
            "set interfaces interface-range ap unit 0 family ethernet-switching vlan members byod")
        response = conn.send_config(
            "set interfaces interface-range ap unit 0 family ethernet-switching vlan members guest")
        response = conn.send_config(
            "set interfaces interface-range ap unit 0 family ethernet-switching vlan members chromebook")
        response = conn.send_config(
            "set vlans byod vlan-id 39")
        response = conn.send_config(
            "set vlans guest vlan-id 38")
        response = conn.send_config(
            "set vlans chromebook vlan-id 40")
        #Commit confirmed to not mess up to bad, and comment to know what the commit does to the switch
        response = conn.send_config(
            'commit confirmed 5 comment "MIST preparation"')
        #If the switch is still in reach after commit confirmed, commit to save new config
        response = conn.send_config(
            'commit')

    elif "EX2200" in switch_model:
        response = conn.send_command(
            "show configuration interfaces interface-range uplink")
        if "unit 0" in response.result:
            response = conn.send_config(
                "set vlans byod interface uplink")
            response = conn.send_config(
                "set vlans guest interface uplink")
            response = conn.send_config(
                "set vlans chromebook interface uplink")
        response = conn.send_config(
            "set vlans byod interface downlink")
        response = conn.send_config(
            "set vlans guest interface downlink")
        response = conn.send_config(
            "set vlans chromebook interface downlink")
        response = conn.send_config(
            "set vlans byod interface ap")
        response = conn.send_config(
            "set vlans guest interface ap")
        response = conn.send_config(
            "set vlans chromebook interface ap")
        response = conn.send_config(
            "set vlans byod vlan-id 39")
        response = conn.send_config(
            "set vlans guest vlan-id 38")
        response = conn.send_config(
            "set vlans chromebook vlan-id 40")
        #Commit confirmed to not mess up to bad, and comment to know what the commit does to the switch
        response = conn.send_config(
            'commit confirmed 5 comment "MIST preparation"')
        #If the switch is still in reach after commit confirmed, commit to save new config
        response = conn.send_config(
            'commit')


    logging.info(response.elapsed_time)
    logging.info(response.result)
    #Disconnect from switch
    conn.close()


# Google CRUD operations, function coming from Mist class API example of using API to import sites
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
            print('\tResponse: {} ({})'.format(
                response.text, response.status_code))
            logging.warning('\tResponse: {} ({})'.format(
                response.text, response.status_code))

            return False

        return json.loads(response.text)

#Extract Ekahau data to create packinglist
def extract_esx_data(input_file):
    #Initialize project and access_points
    project = {}
    access_points = {}
    try:
        #extract the inner files of the esx-file
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
    #Return the dict with project info and access_points
    return project, access_points


# Mist CRUD operations, function coming from Mist class API example of using API to import sites
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
            print('\tResponse: {} ({})'.format(
                response.text, response.status_code))
            logging.warning('\tResponse: {} ({})'.format(
                response.text, response.status_code))

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
            print('\tResponse: {} ({})'.format(
                response.text, response.status_code))
            logging.warning('\tResponse: {} ({})'.format(
                response.text, response.status_code))

            return False

        return json.loads(response.text)


# Main function - create new Mist address is a modified version of the import sites example from Mist Class
def new_adress(request, gatuadress, shortname, popularnamn, verksamhet, postnummer, ekahau_file = None):
    logging.info('Create new adress: {}'.format(gatuadress))

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

    sitegroup_lookup = {}

    #Check sitegroups/Förvaltningar
    sitegroups_url = "{}/orgs/{}/sitegroups".format(base_url, org_id)
    sitegroups_result = requests.get(sitegroups_url, headers=headers)
    sitegroups = json.loads(sitegroups_result.text)

    #Check sites for duplicates
    sites_url = "{}/orgs/{}/sites".format(base_url, org_id)
    sites_result = requests.get(sites_url, headers=headers)
    sites = json.loads(sites_result.text)

    # Variables
    #Set siteid to none since that will be generated by Mist
    site_id = None
    #Defining Site-adress for google geocode as Gatuadress, postalcode, Country (from the config file)
    site_address = "{}, {}, {}".format(gatuadress, postalcode_cleanup(
        postnummer), config['mist']['config']['country'])

    #Initialize Site_group/Förvaltning
    site_verksamhet = ''
    #Set that site does not exist unless found in sites
    site_exists = False
    for site in sites:
        if site['name'] == "{} ({})".format(gatuadress, shortname):
            print("Site {} ({}) already exists".format(
                gatuadress, shortname))
            logging.info("Site {} ({}) already exists".format(
                gatuadress, shortname))
            print('\n\n==========\n\n')
            site_exists = True
    #Give a error message that the address already exists in mist
    if site_exists:
        messages.error(request, 'Adressen finns redan!')
        return False
    #Json for defining sitegroup
    sitegroup_json = {
        'name': "{}".format(verksamhet)
    }

    #Check if site group name is existing
    for sitegroup in sitegroups:
        if sitegroup['name'] == verksamhet:
            site_verksamhet = sitegroup['id']
    #If not existing create new sitegroup
    if not site_verksamhet:

        logging.info('Calling the Mist Create Sitegroup API...')
        #Add sitgroup through the mist API
        result = admin.post('/orgs/' + org_id + '/sitegroups', sitegroup_json)
        if result == False:

            logging.warning(
                'Failed to create sitegroup {}'.format(verksamhet))

        site_verksamhet = result['id']

    #Takes the field from the form and include that in the creation
    site = {
        'name': "{} ({})".format(gatuadress, shortname),
        "sitegroup_ids": [
            "{}".format(site_verksamhet)
        ],
        "notes": "{}, {}".format(popularnamn, shortname),
        "rftemplate_id": "{}".format(config['mist']['config']['rftemplate_id'])
    }

    # Provide your Site Setting.
    # Modify if anything you need is missing otherwise change in config.yaml will work best
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
                "AP32": config['mist']['config']['auto_upgrade']['custom_versions']['AP32'],
                "AP32E": config['mist']['config']['auto_upgrade']['custom_versions']['AP32E'],
                "AP33": config['mist']['config']['auto_upgrade']['custom_versions']['AP33'],
                "AP43": config['mist']['config']['auto_upgrade']['custom_versions']['AP43'],
                "AP43E": config['mist']['config']['auto_upgrade']['custom_versions']['AP43E']
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
    #Get coordinates for site to add on map in mist
    (geocoded, geocoding) = geocode(request, site_address)
    if geocoded == True:
        site.update(geocoding)
    else:
        print('Failed to geocode...')
        logging.warning('Failed to geocode...')
        messages.warning(request, 'Failed to geocode...')

        logging.warning(geocoding)

    #Creating site through mist API
    logging.info('Calling the Mist Create Site API...')
    result = admin.post('/orgs/' + org_id + '/sites', site)
    if result == False:
        logging.warning('Failed to create site {}'.format(site['name']))
        logging.warning('Skipping remaining operations for this site...')
    else:
        site_id = result['id']
        logging.info('Created site {} ({})'.format(site['name'], site_id))

        if show_more_details:
            logging.info('\nRetrieving the JSON response object...')
            logging.debug(json.dumps(result, sort_keys=True, indent=4))
            logging.info(
                '\nUsing id in the Mist Update Setting API request')


    # Update Site Setting to add site configuration according to config.yaml
    logging.info('Calling the Mist Update Setting API...')
    result = admin.put('/sites/' + site_id + '/setting',
                       site_setting)
    if result == False:
        logging.warning('Failed to update site setting {} ({})'.format(
            site['name'], site_id))
    else:
        logging.info('Updated site setting {} ({})'.format(
            site['name'], site_id))

        if show_more_details:
            logging.info('\nRetrieving the JSON response object...')

            logging.debug(json.dumps(result, sort_keys=True, indent=4))

    # Import map
    try:
        map_url = "{}/{}/*.esx".format(import_path_ekahau,
                                       gatuadress)

        #Get the newest file
        list_of_files = glob.glob(map_url)
        map_file_url = max(list_of_files, key=os.path.getctime)
        print(map_file_url)
        map_import_url = "{}/sites/{}/maps/import".format(base_url, site_id)
        map_import_headers = {
            'Authorization': f'token {mist_api_token}'
        }


        logging.info('Calling the Mist import map API...')
        map_import_payload = {"vendor_name": "ekahau", "import_all_floorplans": True,
                              "import_height": True, "import_orientation": True}
        files = {
            'file': (os.path.basename(map_file_url), open(map_file_url, 'rb'), 'application/octet-stream'),
            'json': (None, json.dumps(map_import_payload), 'application/json')
        }

        response = requests.post(
            map_import_url, files=files, headers=map_import_headers)
        messages.success(request, 'Ritning laddades upp')

        imported_aps = response.text
        #Getting the imported AP-models to create packinglist
        project, access_points = extract_esx_data(map_file_url)

        access_points = access_points['accessPoints']

        #Count how many accesspoint there is of a certain model
        ap_models = Counter(
            access_point['model'] for access_point in access_points if access_point.get('model'))
        ap_models = dict(ap_models)
        label_file_url = "{}/{}/{}".format(import_path_ekahau,
                                           gatuadress, label_file)
        label_title = str("{} - {}".format(gatuadress, popularnamn))
        #Creating packinglist
        styles = getSampleStyleSheet()
        style = styles["BodyText"]
        header = Paragraph(
            "<bold><font size=15>{}</font></bold>".format(label_title), style)
        #Set canvas to label size
        canvas = Canvas(label_file_url, pagesize=(6.2 * cm, 4 * cm))
        canvas.drawString(0.1 * cm, 8.2 * cm, label_title)
        aW = 6 * cm
        aH = 3 * cm
        w, h = header.wrap(aW, aH)
        header.drawOn(canvas, 5, aH)
        #Print AP models on packinglist
        for ap_model in ap_models:
            aH = aH - h
            ap_model_str = str("{}: {}st".format(
                ap_model, ap_models[ap_model]))
            ap_model_text = Paragraph(
                "<font size=15>{}</font>".format(ap_model_str), style)
            ap_model_text.wrap(aW, aH)
            ap_model_text.drawOn(canvas, 5, aH)
            aH = aH - h
        canvas.showPage()
        canvas.save()

        if response == False:

            logging.warning('Failed to import map for {} ({})'.format(
                site['name'], site_id))
        else:
            logging.info('Imported map for {} ({})'.format(
                site['name'], site_id))

            if show_more_details:
                logging.info('\nRetrieving the JSON response object...')

                logging.debug(json.dumps(result, sort_keys=True, indent=4))

    except:
        logging.warning("Something is not working with ekahau import")

    #Add Vlan to switches
    logging.info("Adding Vlans byod and guest to switches on site")
    #Connect to Solarwinds
    session = requests.Session()
    session.timeout = 30  # Set your timeout in seconds
    logging.info("Connecting to Solarwinds")
    swis = orionsdk.SwisClient("SolarWinds-Orion", solarwinds_username,
                               solarwinds_password, verify=False, session=session)
    logging.info("Getting switches that belong to the site")
    #Get access-switches on site
    nodes = swis.query(
        "SELECT NodeID, Caption, IPAddress, Status FROM Orion.Nodes WHERE Caption LIKE 'swa-%-{}' AND Status LIKE 1".format(shortname))
    #Reset switch number
    switch_number = 0
    switches = nodes['results']
    for switch in switches:
        addVlansToSwitch(switch)
        switch_number += 1

    messages.success(request, 'Lagt till VLAN på {} switchar'.format(switch_number))
    return True

def update_mist(request, mist_version):
    try:
        #Get mist sites
        sites_url = "{}/orgs/{}/sites".format(base_url, org_id)

        resultssites = requests.get(sites_url, headers=headers)
        sites = json.loads(resultssites.text)
        #Set the new configuration to update sites with, add new AP-models here

        json_update = json.dumps({
            "auto_upgrade": {
                "enabled": True,
                "version": "custom",
                "time_of_day": "02:00",
                "custom_versions": {
                    "AP32": mist_version,
                    "AP32E": mist_version,
                    "AP33": mist_version,
                    "AP43": mist_version,
                    "AP43E": mist_version
                },
                "day_of_week": ""
            }
        })
        #Open config.yaml to be able to change so that new sites are created with the new firmware from the start
        with open('mist_import_sites/config.yaml') as f:
            config = yaml.safe_load(f)
        #Change the firmware versions for the different AP-models, add new AP-models here
        config['mist']['config']['auto_upgrade']['custom_versions']['AP32'] = mist_version
        config['mist']['config']['auto_upgrade']['custom_versions']['AP32E'] = mist_version
        config['mist']['config']['auto_upgrade']['custom_versions']['AP33'] = mist_version
        config['mist']['config']['auto_upgrade']['custom_versions']['AP43'] = mist_version
        config['mist']['config']['auto_upgrade']['custom_versions']['AP43E'] = mist_version
        #Save config.yaml with new configuration
        with open('mist_import_sites/config.yaml', 'w') as f:
            config = yaml.dump(config, f,
                            default_flow_style=False, sort_keys=False)

        logging.debug(json.dumps(json_update))
        #Loop through Mist sites and update them
        for site in sites:
            #If site is according to our namestandard
            if search(regex_sitename, site['name']):

                logging.info('Updating site {}'.format(site['name']))
                update_settings_url = "{}/sites/{}/setting".format(base_url, site['id'])
                #Send new settings to mist site api
                result_update = requests.put(update_settings_url, data=json_update, headers=headers)
                logging.debug(json.dumps(result_update.text))
        messages.success(request, 'Mist version updateras till {} nästkommande natt'.format(
            mist_version))
    except:
        messages.error(request, 'Misslyckades med att uppdatera Mist version')






######################################################################################################
#####                                         GUI                                                 ####
######################################################################################################


#Function for defining the GUI for update Mist-gui, see django documentation for more info on how they work
def update_mist_gui(request):
    #Connected to forms.py
    form = UpdateMistForm()
    #If there is a POST-request
    if request.method == 'POST':
        form = UpdateMistForm(request.POST)
        #Check if orm is valid
        if form.is_valid():
            cd = form.cleaned_data
            #update Mist with the form data
            update_mist(request, cd.get('mist_version'))
            #Update the page
            return render(request, 'mist_import_sites/mist_update.html', {'form': form})
        else:
            #If the form data is corupt it will show a message but since the form is only a optinon list and the options are always valid it shouldn´t happen
            messages.error(request, 'Det här borde inte kunna uppstå så kolla kodningen...')
    #Before any POST-action render the page from this template
    return render(request, 'mist_import_sites/mist_update.html', {'form': form})


#Function for defining GUI for new site
def new_site(request):
    form = SiteForm()
    logging.info('Loading form')
    if request.method=='POST':
        #Include uploaded files in form data
        form = SiteForm(request.POST, request.FILES)
        logging.debug(form)
        if form.is_valid():
            #If there is a ekahau file include it otherwise make the object None
            request_file = request.FILES['ekahau_file'] if 'ekahau_file' in request.FILES else None
            cd = form.cleaned_data
            if request_file:
                #Add the uploaded file to file storage
                fs = FileSystemStorage()
                #Where should the file be stored
                map_url = "{}/{}/{}".format(import_path_ekahau,
                                                cd.get('gatuadress'),request.FILES['ekahau_file'].name)
                #If the folder for this adress dosen´t exist create it
                try:
                    os.mkdir(os.path.join(import_path_ekahau, cd.get('gatuadress')))
                except:
                    pass
                #Upload the file
                handle_uploaded_file(request.FILES['ekahau_file'], map_url)
            #Create new adress using the new_adress function
            if new_adress(request, cd.get('gatuadress'), cd.get('shortname'), cd.get('popularnamn'), cd.get('verksamhet'), cd.get('postnummer'), cd.get('ekahau_file')):
                messages.success(request, 'Ny adress {} ({}) tillagd'.format(
                    cd.get('gatuadress'), cd.get('shortname')))
                #Based on what type of new site is created send to different places
                if cd.get('creation_type') == "existing":
                    #For existing sites that are only new on mist return to previous page with a message how the creation went
                    return render(request, 'mist_import_sites/new_site.html', {'form': form})
                else:
                    #For new sites go to page for creating a new cobined switch
                    return redirect('/switches/new_swc_switch?gatuadress={}&popularnamn={}'.format(cd.get('gatuadress'), cd.get('popularnamn')))
        else:
            messages.error(request, 'Kunde inte lägga till den nya adressen')
    return render(request, 'mist_import_sites/new_site.html', {'form': form})
#Define what happens att index
def index(request):

    #Render mist import sites
    return render(request, 'mist_import_sites/index.html')



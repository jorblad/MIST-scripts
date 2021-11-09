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

from .forms import SiteForm, UpdateMistForm

from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

import sys
import time
import requests
import json
import yaml
import pandas
import re
import os
import orionsdk
import xmltodict
import glob
import sys
import argparse
import zipfile
from collections import Counter

from re import search



from scrapli import Scrapli

import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='../logs/Mist-api.log', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')


with open('mist_import_sites/config.yaml') as f:
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

##Switch variables
switch_username = config['switch']['username']
switch_password = config['switch']['password']
solarwinds_username = config['solarwinds']['username']
solarwinds_password = config['solarwinds']['password']
solarwinds_certificate = config['solarwinds']['certificate_file']


def handle_uploaded_file(f, file_path):
    with open(file_path, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)


# Google geocode the site address.
# Note: The Google Maps Web Services Client Libraries could also be used, rather than directly calling the REST APIs.
# Documentation: https://developers.google.com/maps/documentation/geocoding/client-library


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
    switch_hardware = json.loads(response_json)[
        'rpc-reply']['chassis-inventory']['chassis']
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
            'commit confirmed 5 comment "MIST preparation"')
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
            'commit confirmed 5 comment "MIST preparation"')
        response = conn.send_config(
            'commit')

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
            print('\tResponse: {} ({})'.format(
                response.text, response.status_code))
            logging.warning('\tResponse: {} ({})'.format(
                response.text, response.status_code))

            return False

        return json.loads(response.text)


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


# Main function
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
    site_address = "{}, {}, {}".format(gatuadress, postalcode_cleanup(
        postnummer), config['mist']['config']['country'])

    site_verksamhet = ''
    site_exists = False
    for site in sites:
        if site['name'] == "{} ({})".format(gatuadress, shortname):
            print("Site {} ({}) already exists".format(
                gatuadress, shortname))
            logging.info("Site {} ({}) already exists".format(
                gatuadress, shortname))
            print('\n\n==========\n\n')
            site_exists = True

    if site_exists:
        messages.error(request, 'Adressen finns redan!')
        return False

    sitegroup_json = {
        'name': "{}".format(verksamhet)
    }

    #Check if site group name is existing
    for sitegroup in sitegroups:
        if sitegroup['name'] == verksamhet:
            site_verksamhet = sitegroup['id']
    if not site_verksamhet:
        print('Calling the Mist Create Sitegroup API...')
        logging.info('Calling the Mist Create Sitegroup API...')
        result = admin.post('/orgs/' + org_id + '/sitegroups', sitegroup_json)
        if result == False:
            print('Failed to create sitegroup {}'.format(verksamhet))
            logging.warning(
                'Failed to create sitegroup {}'.format(verksamhet))
            print('\n\n==========\n\n')
        site_verksamhet = result['id']
        print('\n\n==========\n\n')
    #Takes the field from the excel-file and create the site from that
    site = {
        'name': "{} ({})".format(gatuadress, shortname),
        "sitegroup_ids": [
            "{}".format(site_verksamhet)
        ],
        "notes": "{}, {}".format(popularnamn, shortname),
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
    (geocoded, geocoding) = geocode(request, site_address)
    if geocoded == True:
        site.update(geocoding)
    else:
        print('Failed to geocode...')
        logging.warning('Failed to geocode...')
        messages.warning(request, 'Failed to geocode...')
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
    else:
        site_id = result['id']
        print('Created site {} ({})'.format(site['name'], site_id))
        logging.info('Created site {} ({})'.format(site['name'], site_id))

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
        print('Failed to update site setting {} ({})'.format(
            site['name'], site_id))
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
                                       gatuadress)


        list_of_files = glob.glob(map_url)
        map_file_url = max(list_of_files, key=os.path.getctime)
        print(map_file_url)
        map_import_url = "{}/sites/{}/maps/import".format(base_url, site_id)
        map_import_headers = {
            'Authorization': f'token {mist_api_token}'
        }

        print('Calling the Mist import map API...')
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
        print(imported_aps)
        #Getting the imported AP-modles to create packinglist
        project, access_points = extract_esx_data(map_file_url)

        access_points = access_points['accessPoints']

        ap_models = Counter(
            access_point['model'] for access_point in access_points if access_point.get('model'))
        ap_models = dict(ap_models)
        print(ap_models)
        label_file_url = "{}/{}/{}".format(import_path_ekahau,
                                           gatuadress, label_file)
        label_title = str("{} - {}".format(gatuadress, popularnamn))
        #Creating packinglist
        styles = getSampleStyleSheet()
        style = styles["BodyText"]
        header = Paragraph(
            "<bold><font size=15>{}</font></bold>".format(label_title), style)
        canvas = Canvas(label_file_url, pagesize=(6.2 * cm, 4 * cm))
        canvas.drawString(0.1 * cm, 8.2 * cm, label_title)
        aW = 6 * cm
        aH = 3 * cm
        w, h = header.wrap(aW, aH)
        header.drawOn(canvas, 5, aH)
        for ap_model in ap_models:
            aH = aH - h
            ap_model_str = str("{}: {}st".format(
                ap_model, ap_models[ap_model]))
            ap_model_text = Paragraph(
                "<font size=15>{}</font>".format(ap_model_str), style)
            ap_model_text.wrap(aW, aH)
            ap_model_text.drawOn(canvas, 5, aH)
            aH = aH - h
            #canvas.drawString(0.1 * cm, 0.2 * cm, ap_model_str)
            print(ap_model_str)
        canvas.showPage()
        canvas.save()

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
        print("Something is not working with ekahau import")

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
        "SELECT NodeID, Caption, IPAddress, Status FROM Orion.Nodes WHERE Caption LIKE 'swa-%-{}' AND Status LIKE 1".format(shortname))
    switch_number = 0
    switches = nodes['results']
    for switch in switches:
        print(switch)
        addVlansToSwitch(switch)
        switch_number += 1

    print("Updated settings on {} switches".format(switch_number))
    messages.success(request, 'Lagt till VLAN på {} switchar'.format(switch_number))
    return True

def update_mist(request, mist_version):
    try:
        sites_url = "{}/orgs/{}/sites".format(base_url, org_id)

        resultssites = requests.get(sites_url, headers=headers)
        sites = json.loads(resultssites.text)

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

        with open('mist_import_sites/config.yaml') as f:
            config = yaml.safe_load(f)

        config['mist']['config']['auto_upgrade']['custom_versions']['AP32'] = mist_version
        config['mist']['config']['auto_upgrade']['custom_versions']['AP32E'] = mist_version
        config['mist']['config']['auto_upgrade']['custom_versions']['AP33'] = mist_version
        config['mist']['config']['auto_upgrade']['custom_versions']['AP43'] = mist_version
        config['mist']['config']['auto_upgrade']['custom_versions']['AP43E'] = mist_version

        with open('mist_import_sites/config.yaml', 'w') as f:
            config = yaml.dump(config, f,
                            default_flow_style=False, sort_keys=False)

        logging.debug(json.dumps(json_update))

        for site in sites:
            if search(regex_sitename, site['name']):
                print(site['name'])
                logging.info('Updating site {}'.format(site['name']))
                update_settings_url = "{}/sites/{}/setting".format(base_url, site['id'])
                result_update = requests.put(update_settings_url, data=json_update, headers=headers)
                logging.debug(json.dumps(result_update.text))
        messages.success(request, 'Mist version updateras till {}'.format(mist_version))
    except:
        messages.error(request, 'Misslyckades med att uppdatera Mist version')






######################################################################################################
#####                                         GUI                                                 ####
######################################################################################################



def update_mist_gui(request):
    form = UpdateMistForm()
    if request.method == 'POST':
        form = UpdateMistForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            update_mist(request, cd.get('mist_version'))
            return render(request, 'mist_import_sites/mist_update.html', {'form': form})
        else:
            messages.error(request, 'Det här borde inte kunna uppstå så kolla kodningen...')
    return render(request, 'mist_import_sites/mist_update.html', {'form': form})



def new_site(request):
    form = SiteForm()
    logging.info('Loading form')
    if request.method=='POST':
        form = SiteForm(request.POST, request.FILES)
        logging.debug(form)
        if form.is_valid():
            #ekahau_file = request.FILES['file']
            request_file = request.FILES['ekahau_file'] if 'ekahau_file' in request.FILES else None
            cd = form.cleaned_data
            if request_file:
                fs = FileSystemStorage()
                map_url = "{}/{}/{}".format(import_path_ekahau,
                                                cd.get('gatuadress'),request.FILES['ekahau_file'].name)
                print(map_url)
                try:
                    os.mkdir(os.path.join(import_path_ekahau, cd.get('gatuadress')))
                except:
                    pass

                handle_uploaded_file(request.FILES['ekahau_file'], map_url)
            if new_adress(request, cd.get('gatuadress'), cd.get('shortname'), cd.get('popularnamn'), cd.get('verksamhet'), cd.get('postnummer'), cd.get('ekahau_file')):
                messages.success(request, 'Ny adress {} ({}) tillagd'.format(
                    cd.get('gatuadress'), cd.get('shortname')))
                if cd.get('creation_type') == "existing":
                    return render(request, 'mist_import_sites/new_site.html', {'form': form})
                else:
                    return redirect('/switches/new_swc_switch?gatuadress={}&popularnamn={}'.format(cd.get('gatuadress'), cd.get('popularnamn')))
        else:
            messages.error(request, 'Kunde inte lägga till den nya adressen')
    return render(request, 'mist_import_sites/new_site.html', {'form': form})

def index(request):
    template = loader.get_template('mist_import_sites/index.html')

    return render(request, 'mist_import_sites/index.html')



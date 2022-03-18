import requests
import json
import yaml
#Used to get the switches from solarwinds
import orionsdk
#Used to work with xml from the switches
import xmltodict

from re import search
#Used for communicating with the switches
from scrapli import Scrapli

#Log to a specified file
import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='Mist-api.log', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')

#open configuration file for use in the script
with open('../django-script/netscripts/mist_import_sites/config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)


#set variables for easy access to settings
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


authorization = "Token {}".format(mist_api_token)

headers = {
    'Content-Type': 'application/json',
    'Authorization': authorization
}
#Get shortname from sitename
regex_shortname = ".*\((....)\)"

##Switch variables
switch_username = config['switch']['username']
switch_password = config['switch']['password']
solarwinds_username = config['solarwinds']['username']
solarwinds_password = config['solarwinds']['password']
solarwinds_certificate = config['solarwinds']['certificate_file']

#Function that takes a switch object and add Vlan to that switch
def addVlansToSwitch(switch):
    #create device object for scrapli
    device = {
        "host": switch['IPAddress'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch['Caption'], switch['IPAddress']))
    #Connecting to the switch
    conn = Scrapli(**device)
    conn.open()
    #Check what kind of switch it is
    response = conn.send_command("show chassis hardware | display xml")
    response_dict = xmltodict.parse(response.result)
    response_json = json.dumps(response_dict)
    switch_hardware = json.loads(response_json)[
        'rpc-reply']['chassis-inventory']['chassis']
    #Get the model from the hardware section in the switch
    switch_model = switch_hardware['description']
    print(switch_model)
    #Based on switchmodel use different commands for adding a vlan
    #### Here is where you change what VLAN you want to add
    #### Make sure to change it on both EX2300 and EX2200
    if "EX2300" in switch_model:
        #Check if there is a uplink interface-range and if so add the vlan to it
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
        #Use commit confirmed so that if i cut my leg off the switch will come back up in 5 minutes
        # and add a comment so that its easy to see in the switch that it the config was scripted
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
        #Use commit confirmed so that if i cut my leg off the switch will come back up in 5 minutes
        # and add a comment so that its easy to see in the switch that it the config was scripted
        response = conn.send_config(
            'commit confirmed 5 comment "Chromebook-vlan preparation"')
        response = conn.send_config(
            'commit')

    #Looging and output the response from the commit and the time
    logging.info(response.elapsed_time)
    logging.info(response.result)
    print(response.result)
    #Disconnect from the switch
    conn.close()

#Function that finds switches in solarwinds based on a shortname
def findSwitches(shortname):

    print('\n\n==========\n\n')
    print("Adding Vlans byod and guest to switches on site")
    #Connect to Solarwinds
    session = requests.Session()
    session.timeout = 30  # Set your timeout in seconds
    logging.info("Connecting to Solarwinds")
    swis = orionsdk.SwisClient("SolarWinds-Orion", solarwinds_username,
                                solarwinds_password, verify=False, session=session)
    logging.info("Getting switches that belong to the site")
    #Solarwinds Query to get access-switches that belongs to that shortname and are online according to solarwinds
    nodes = swis.query(
        "SELECT NodeID, Caption, IPAddress, Status FROM Orion.Nodes WHERE Caption LIKE 'swa-%-{}' AND Status LIKE 1".format(shortname))
    #Reset switch number to zero
    switch_number = 0
    #Convert result to a list of switches
    switches = nodes['results']
    #Use the function to addVlanToSwitch
    for switch in switches:
        print(switch)
        addVlansToSwitch(switch)
        #add number to switches to keep track of how many is updated
        switch_number += 1

    print("Updated settings on {} switches".format(switch_number))
#Get the sites from Mist
try:
    #Mist API URL to get sites
    sites_url = "{}/orgs/{}/sites".format(base_url, org_id)

    resultssites = requests.get(sites_url, headers=headers)
    #Convert the result into a list of sites
    sites = json.loads(resultssites.text)

    #Go through sites and run the findSwitches functions with the shortname
    for site in sites:
        if search(regex_sitename, site['name']):
            print(site['name'])
            #get the shortname of the site
            shortname = search(regex_shortname, site['name']).group(1)
            findSwitches(shortname)
            print('Vlan tillagda till site {}'.format(site['name']))

except:
    #If it dosen´t work to list the sites active in Mist
    print("Kan inte lista siter")

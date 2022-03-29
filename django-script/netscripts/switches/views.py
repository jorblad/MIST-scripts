#Django libraries
from django.contrib.messages.api import info
from django.core.exceptions import AppRegistryNotReady
from django.shortcuts import render
from django.template import loader
from django.contrib import messages
from django.http import HttpResponse
from django.core.files.storage import FileSystemStorage
from django.template.loader import render_to_string

#Other imports
import re #Import regex
import orionsdk #Solarwinds API
import requests #For use with rest-api
import yaml
import os
import pdfkit #for creation of PDF:s
import ipaddress #Functions to work with IP-adresses in a easy way
import json
import xmltodict
#For working with switches
from scrapli import Scrapli

#import forms from the project
from .forms import NewSwitch, SearchSwitch, ReplaceSwitch, ConfigureSwitch, NewSwcSwitch, ReplaceSwcSwitch

#Logging
import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='../logs/switches.log', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')

#Get configuration from mist_import_sites config.yaml
with open('mist_import_sites/config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

import_path_ekahau = config['import']['import_ekahau_path']

##Switch variables
switch_username = config['switch']['username']
switch_password = config['switch']['password']
solarwinds_username = config['solarwinds']['username']
solarwinds_password = config['solarwinds']['password']
solarwinds_certificate = config['solarwinds']['certificate_file']

#Unicode to make config snmp usable
unicode_table = {
    ord('å'): 'a',
    ord('ä'): 'a',
    ord('ö'): 'o',
}

#Function to get available access-switch IP-adresses
def get_next_access_ip():
    #Connect to Solarwinds
    session = requests.Session()
    session.timeout = 30  # Set your timeout in seconds
    logging.info("Connecting to Solarwinds")
    swis = orionsdk.SwisClient("SolarWinds-Orion", solarwinds_username,
                               solarwinds_password, verify=False, session=session)
    logging.info("Getting free IP-adresses")
    #Queery to get free IP-adresses
    nodes = swis.query(
        "SELECT TOP 65025 IPAddress FROM IPAM.IPNode WHERE Status=2 AND SubnetId LIKE '149'")
    return nodes['results']

#Function to get available edge-switch IP-adresses
def get_next_edge_ip():
    #Connect to Solarwinds
    session = requests.Session()
    session.timeout = 30  # Set your timeout in seconds
    logging.info("Connecting to Solarwinds")
    swis = orionsdk.SwisClient("SolarWinds-Orion", solarwinds_username,
                               solarwinds_password, verify=False, session=session)
    logging.info("Getting free IP-adresses")
    #Queery to get free IP-adresses
    nodes = swis.query(
        "SELECT TOP 1022 IPAddress FROM IPAM.IPNode WHERE Status=2 AND SubnetId LIKE '2701'")
    return nodes['results']

#Check if input is a valid IP-adress
def valid_ip(address):
    try:
        #Try to print cause if it isn´t a valid IP it throws an exception
        print(ipaddress.ip_address(address))
        return True
    except:
        return False

#Function for creating a new access-switch configuration
def create_switch_conf(request, cd, source):
    #Count total amount of copper interfaces needed
    antal_interfaces = int(cd['interface_ap']) + \
        int(cd['interface_device']) + \
        int(cd['interface_pub']) + \
        int(cd['interface_klientklass1']) + \
            int(cd['interface_klientklass2']) + \
                int(cd['interface_cu_downlink'])
    #If smaller than a certain size add all available interfaces as klientklass2 interfaces
    if antal_interfaces <= 12:
        switchmodell = 'ex2300-c-12p'
        if cd['interface_uplink'] == 'sfp':
            if antal_interfaces != 12:
                cd['interface_klientklass2'] = 12 - \
                    int(cd['interface_ap']) - int(cd['interface_device']) - int(cd['interface_pub']
                                                                                ) - int(cd['interface_klientklass1']) - int(cd['interface_cu_downlink'])
        else:
            if antal_interfaces != 11:
                cd['interface_klientklass2'] = 11 - \
                    int(cd['interface_ap']) - int(cd['interface_device']) - int(cd['interface_pub']
                                                                                ) - int(cd['interface_klientklass1']) - int(cd['interface_cu_downlink'])
    elif antal_interfaces <= 24:
        switchmodell = 'ex2300-24p'
        if cd['interface_uplink'] == 'sfp':
            if antal_interfaces != 24:
                cd['interface_klientklass2'] = 24 - \
                    int(cd['interface_ap']) - int(cd['interface_device']) - int(cd['interface_pub']
                                                                                ) - int(cd['interface_klientklass1']) - int(cd['interface_cu_downlink'])
        else:
            if antal_interfaces != 23:
                cd['interface_klientklass2'] = 23 - \
                    int(cd['interface_ap']) - int(cd['interface_device']) - int(cd['interface_pub']
                                                                                ) - int(cd['interface_klientklass1']) - int(cd['interface_cu_downlink'])

    elif antal_interfaces <= 48:
        switchmodell = 'ex2300-48p'
        if cd['interface_uplink'] == 'sfp':
            if antal_interfaces != 48:
                cd['interface_klientklass2'] = 48 - \
                    int(cd['interface_ap']) - int(cd['interface_device']) - int(cd['interface_pub']
                                                                                ) - int(cd['interface_klientklass1']) - int(cd['interface_cu_downlink'])
        else:
            if antal_interfaces != 47:
                cd['interface_klientklass2'] = 47 - \
                    int(cd['interface_ap']) - int(cd['interface_device']) - int(cd['interface_pub']
                                                                                ) - int(cd['interface_klientklass1']) - int(cd['interface_cu_downlink'])

    else:
        #If more than 48 ports are needed say that it isnt´t possible
        messages.error(request, 'Vi har inte så stora switchar')
        return render(request, 'switches/new_switch.html', {'form': form})

    #Check the switchmodel and set what interfaces are uplink and downlink based on that
    if switchmodell == 'ex2300-c-12p':
        if cd['interface_uplink'] == 'sfp':

            interfaces = {
                "AP": [],
                "device": [],
                "pub": [],
                "klientklass1": [],
                "klientklass2": [],
                "downlink": ['ge-0/1/0'],
                "uplink": ['ge-0/1/1'],
                "access_ports": [],
            }
        else:
            interfaces = {
                "AP": [],
                "device": [],
                "pub": [],
                "klientklass1": [],
                "klientklass2": [],
                "downlink": ['ge-0/1/0', 'ge-0/1/1'],
                "uplink": ['ge-0/0/11'],
                "access_ports": [],
            }
    else:
        if cd['interface_uplink'] == 'sfp':

            interfaces = {
                "AP": [],
                "device": [],
                "pub": [],
                "klientklass1": [],
                "klientklass2": [],
                "downlink": ['ge-0/1/0', 'ge-0/1/1', 'ge-0/1/2'],
                "uplink": ['ge-0/1/3'],
                "access_ports": [],
            }
        else:
            if switchmodell == 'ex2300-24p':
                interfaces = {
                    "AP": [],
                    "device": [],
                    "pub": [],
                    "klientklass1": [],
                    "klientklass2": [],
                    "downlink": ['ge-0/1/0', 'ge-0/1/1', 'ge-0/1/2', 'ge-0/1/3'],
                    "uplink": ['ge-0/0/23'],
                    "access_ports": [],
                }
            else:
                interfaces = {
                    "AP": [],
                    "device": [],
                    "pub": [],
                    "klientklass1": [],
                    "klientklass2": [],
                    "downlink": ['ge-0/1/0', 'ge-0/1/1', 'ge-0/1/2', 'ge-0/1/3'],
                    "uplink": ['ge-0/0/47'],
                    "access_ports": [],
                }
    #Reset last interface number
    last_interface_number = 0
    #Go through all interfaces and add them to the correct interface ranges
    for i in range(0, int(cd['interface_ap'])):
        interface_number = i + last_interface_number
        interface_name = "ge-0/0/{}".format(interface_number)
        interfaces['AP'].append(interface_name)
        interfaces['access_ports'].append(interface_name)
    try:
        last_interface = interfaces['access_ports'][-1]
        last_interface_number = 1 + \
            int(re.search('ge-0/0/(\d*)', last_interface).group(1))
    except:
        last_interface_number = 0

    for i in range(0, int(cd['interface_device'])):
        interface_number = i + last_interface_number
        interface_name = "ge-0/0/{}".format(interface_number)
        interfaces['device'].append(interface_name)
        interfaces['access_ports'].append(interface_name)

    try:
        last_interface = interfaces['access_ports'][-1]
        last_interface_number = 1 + \
            int(re.search('ge-0/0/(\d*)', last_interface).group(1))
    except:
        last_interface_number = 0

    for i in range(0, int(cd['interface_pub'])):
        interface_number = i + last_interface_number
        interface_name = "ge-0/0/{}".format(interface_number)
        interfaces['pub'].append(interface_name)
        interfaces['access_ports'].append(interface_name)

    try:
        last_interface = interfaces['access_ports'][-1]
        last_interface_number = 1 + \
            int(re.search('ge-0/0/(\d*)', last_interface).group(1))
    except:
        last_interface_number = 0

    for i in range(0, int(cd['interface_klientklass1'])):
        interface_number = i + last_interface_number
        interface_name = "ge-0/0/{}".format(interface_number)
        interfaces['klientklass1'].append(interface_name)
        interfaces['access_ports'].append(interface_name)

    try:
        last_interface = interfaces['access_ports'][-1]
        last_interface_number = 1 + \
            int(re.search('ge-0/0/(\d*)', last_interface).group(1))
    except:
        last_interface_number = 0

    for i in range(0, int(cd['interface_klientklass2'])):
        interface_number = i + last_interface_number
        interface_name = "ge-0/0/{}".format(interface_number)
        interfaces['klientklass2'].append(interface_name)
        interfaces['access_ports'].append(interface_name)

    try:
        last_interface = interfaces['access_ports'][-1]
        last_interface_number = 1 + \
            int(re.search('ge-0/0/(\d*)', last_interface).group(1))
    except:
        last_interface_number = 0

    for i in range(0, int(cd['interface_cu_downlink'])):
        interface_number = i + last_interface_number
        interface_name = "ge-0/0/{}".format(interface_number)
        interfaces['downlink'].append(interface_name)

    #Convert to snmp usable names
    cd['gatuadress_uni'] = cd['gatuadress'].translate(unicode_table)
    cd['popularnamn_uni'] = cd['popularnamn'].translate(unicode_table)
    cd['plan_uni'] = cd['plan'].translate(unicode_table)
    cd['rum_nummer_uni'] = cd['rum_nummer'].translate(unicode_table)
    cd['rum_beskrivning_uni'] = cd['rum_beskrivning'].translate(
        unicode_table)
    #Put together context for creating configuration based on a template
    context = {
            "conf": cd,
            "interfaces": interfaces,
            "switch_model": switchmodell
        }

    #Decide which report should be used on wheter it is a new switch or a replacement of a existing switch
    if source == "new_switch":
        template_table = loader.get_template(
            'switches/switch_interfaces.html')

    elif source == "replace_switch":
        template_table = loader.get_template(
            'switches/switch_interfaces_replacement.html')

    else:
        template_table = loader.get_template(
            'switches/switch_interfaces.html')

    #Configuation template
    template_ex2300 = loader.get_template('switches/swa-ex2300.conf')

    #Template for switch-label
    template_label = loader.get_template('switches/switch_label.html')

    fs = FileSystemStorage()
    #Find where the config and report file should go
    conf_file_url = "{}/{}/{}.conf".format(import_path_ekahau,
                                            cd.get('gatuadress'), cd['switchnamn'])
    interfaces_file_url = "{}/{}/{}".format(import_path_ekahau,
                                            cd.get('gatuadress'), cd['switchnamn'])

    #If folder for adress dosen´t exist create it
    try:
        os.mkdir(os.path.join(
            import_path_ekahau, cd.get('gatuadress')))
    except:
        pass

    #Create configuration file from template
    f = open(conf_file_url, "w")
    f.write(template_ex2300.render(context))
    f.close()

    #Create interface report from template
    f_interfaces = open("{}.html".format(interfaces_file_url), "w")
    f_interfaces.write(template_table.render(context))
    f_interfaces.close()

    #Create PDF-file from html report
    pdfkit.from_file("{}.html".format(interfaces_file_url),
                        "{}.pdf".format(interfaces_file_url))

    #Create switchlabel from template
    f_switch_label = open(
        "{}-label.html".format(interfaces_file_url), "w")
    f_switch_label.write(template_label.render(cd))
    f_switch_label.close()

    #Options for creation of PDF-label
    label_options = {
        'page-height': '12mm',
        'page-width': '62mm',
        'margin-top': '0',
        'margin-bottom': '0',
    }
    #Create PDF switchlabel from html-file
    pdfkit.from_file("{}-label.html".format(interfaces_file_url),
                        "{}-label.pdf".format(interfaces_file_url), options=label_options)

    ## I have inactivated deletion of html files since those actually often behave better than the pdf conversion
    #os.remove("{}.html".format(interfaces_file_url))
    #os.remove("{}-label.html".format(interfaces_file_url))
    #return switchmodell for message and to end function
    return switchmodell

#Function for creating a new combined switch configuration
def create_swc_switch_conf(request, cd, source):
    antal_interfaces = int(cd['interface_ap']) + \
        int(cd['interface_device']) + \
        int(cd['interface_pub']) + \
        int(cd['interface_klientklass1']) + \
        int(cd['interface_klientklass2']) + \
        int(cd['interface_cu_downlink'])
    #If smaller than a certain size add all available interfaces as klientklass2 interfaces
    if antal_interfaces <= 10:
        switchmodell = 'ex2300-c-12p'
        if antal_interfaces != 10:
            cd['interface_klientklass2'] = 10 - \
                int(cd['interface_ap']) - int(cd['interface_device']) - int(cd['interface_pub']
                                                                            ) - int(cd['interface_klientklass1']) - int(cd['interface_cu_downlink'])

    elif antal_interfaces <= 22:
        switchmodell = 'ex2300-24p'
        if antal_interfaces != 22:
            cd['interface_klientklass2'] = 22 - \
                int(cd['interface_ap']) - int(cd['interface_device']) - int(cd['interface_pub']
                                                                            ) - int(cd['interface_klientklass1']) - int(cd['interface_cu_downlink'])

    elif antal_interfaces <= 46:
        switchmodell = 'ex2300-48p'
        if antal_interfaces != 46:
            cd['interface_klientklass2'] = 46 - \
                int(cd['interface_ap']) - int(cd['interface_device']) - int(cd['interface_pub']
                                                                            ) - int(cd['interface_klientklass1']) - int(cd['interface_cu_downlink'])

    else:
        #If more than 48 ports are needed say that it isnt´t possible
        messages.error(request, 'Vi har inte så stora switchar')
        return render(request, 'switches/new_switch.html', {'form': form})

    #Check the switchmodel and set what interfaces are uplink and downlink based on that
    if switchmodell == 'ex2300-c-12p':
        interfaces = {
            "AP": [],
            "device": [],
            "pub": [],
            "klientklass1": [],
            "klientklass2": [],
            "downlink": [],
            "uplink": ['ge-0/1/0', 'ge-0/1/1'],
            "EP_convert": ['ge-0/0/10'],
            "SP_convert": ['ge-0/0/11'],
            "access_ports": [],
        }
    elif switchmodell == 'ex2300-24p':
        interfaces = {
            "AP": [],
            "device": [],
            "pub": [],
            "klientklass1": [],
            "klientklass2": [],
            "downlink": ['ge-0/1/0', 'ge-0/1/1'],
            "uplink": ['ge-0/1/2', 'ge-0/1/3'],
            "EP_convert": ['ge-0/0/22'],
            "SP_convert": ['ge-0/0/23'],
            "access_ports": [],
        }
    else:
        interfaces = {
            "AP": [],
            "device": [],
            "pub": [],
            "klientklass1": [],
            "klientklass2": [],
            "downlink": ['ge-0/1/0', 'ge-0/1/1'],
            "uplink": ['ge-0/1/2', 'ge-0/1/3'],
            "EP_convert": ['ge-0/0/46'],
            "SP_convert": ['ge-0/0/47'],
            "access_ports": [],
        }

    #Reset last interface_number
    last_interface_number = 0

    #Go through all interfaces and add them to the correct interface ranges
    for i in range(0, int(cd['interface_ap'])):
        interface_number = i + last_interface_number
        interface_name = "ge-0/0/{}".format(interface_number)
        interfaces['AP'].append(interface_name)
        interfaces['access_ports'].append(interface_name)
    try:
        last_interface = interfaces['access_ports'][-1]
        last_interface_number = 1 + \
            int(re.search('ge-0/0/(\d*)', last_interface).group(1))
    except:
        last_interface_number = 0

    for i in range(0, int(cd['interface_device'])):
        interface_number = i + last_interface_number
        interface_name = "ge-0/0/{}".format(interface_number)
        interfaces['device'].append(interface_name)
        interfaces['access_ports'].append(interface_name)

    try:
        last_interface = interfaces['access_ports'][-1]
        last_interface_number = 1 + \
            int(re.search('ge-0/0/(\d*)', last_interface).group(1))
    except:
        last_interface_number = 0

    for i in range(0, int(cd['interface_pub'])):
        interface_number = i + last_interface_number
        interface_name = "ge-0/0/{}".format(interface_number)
        interfaces['pub'].append(interface_name)
        interfaces['access_ports'].append(interface_name)

    try:
        last_interface = interfaces['access_ports'][-1]
        last_interface_number = 1 + \
            int(re.search('ge-0/0/(\d*)', last_interface).group(1))
    except:
        last_interface_number = 0

    for i in range(0, int(cd['interface_klientklass1'])):
        interface_number = i + last_interface_number
        interface_name = "ge-0/0/{}".format(interface_number)
        interfaces['klientklass1'].append(interface_name)
        interfaces['access_ports'].append(interface_name)

    try:
        last_interface = interfaces['access_ports'][-1]
        last_interface_number = 1 + \
            int(re.search('ge-0/0/(\d*)', last_interface).group(1))
    except:
        last_interface_number = 0

    for i in range(0, int(cd['interface_klientklass2'])):
        interface_number = i + last_interface_number
        interface_name = "ge-0/0/{}".format(interface_number)
        interfaces['klientklass2'].append(interface_name)
        interfaces['access_ports'].append(interface_name)

    try:
        last_interface = interfaces['access_ports'][-1]
        last_interface_number = 1 + \
            int(re.search('ge-0/0/(\d*)', last_interface).group(1))
    except:
        last_interface_number = 0

    for i in range(0, int(cd['interface_cu_downlink'])):
        interface_number = i + last_interface_number
        interface_name = "ge-0/0/{}".format(interface_number)
        interfaces['downlink'].append(interface_name)

    #Convert input to snmp friendly version
    cd['gatuadress_uni'] = cd['gatuadress'].translate(unicode_table)
    cd['popularnamn_uni'] = cd['popularnamn'].translate(unicode_table)
    cd['plan_uni'] = cd['plan'].translate(unicode_table)
    cd['rum_nummer_uni'] = cd['rum_nummer'].translate(unicode_table)
    cd['rum_beskrivning_uni'] = cd['rum_beskrivning'].translate(
        unicode_table)
    cd['s_vlan_name'] = "s-{}".format(cd['switchnamn'][-4:])
    context = {
        "conf": cd,
        "interfaces": interfaces,
        "switch_model": switchmodell
    }

    #Set different report based on whether it is a new switch or a replacement
    if source == "new_switch":
        template_table = loader.get_template(
            'switches/switch_interfaces.html')

    elif source == "replace_switch":
        template_table = loader.get_template(
            'switches/switch_interfaces_replacement.html')

    else:
        template_table = loader.get_template(
            'switches/switch_interfaces.html')

    #Set template for switch-configuration
    template_ex2300 = loader.get_template('switches/swc-ex2300.conf')

    #Set template for switch-label
    template_label = loader.get_template('switches/switch_label.html')

    #Set file paths
    fs = FileSystemStorage()
    conf_file_url = "{}/{}/{}.conf".format(import_path_ekahau,
                                           cd.get('gatuadress'), cd['switchnamn'])
    interfaces_file_url = "{}/{}/{}".format(import_path_ekahau,
                                            cd.get('gatuadress'), cd['switchnamn'])

    #Create folder if it dosen´t exist
    try:
        os.mkdir(os.path.join(
            import_path_ekahau, cd.get('gatuadress')))
    except:
        pass

    #Create configuration file from template
    f = open(conf_file_url, "w")
    f.write(template_ex2300.render(context))
    f.close()

    #Create interface report from template
    f_interfaces = open("{}.html".format(interfaces_file_url), "w")
    f_interfaces.write(template_table.render(context))
    f_interfaces.close()

    #Create PDF-file from html report
    pdfkit.from_file("{}.html".format(interfaces_file_url),
                     "{}.pdf".format(interfaces_file_url))

    #Create switchlabel from template
    f_switch_label = open(
        "{}-label.html".format(interfaces_file_url), "w")
    f_switch_label.write(template_label.render(cd))
    f_switch_label.close()

    #Options for creation of PDF-label
    label_options = {
        'page-height': '12mm',
        'page-width': '62mm',
        'margin-top': '0',
        'margin-bottom': '0',
    }
    #Create PDF switchlabel from html-file
    pdfkit.from_file("{}-label.html".format(interfaces_file_url),
                     "{}-label.pdf".format(interfaces_file_url), options=label_options)

    ## I have inactivated deletion of html files since those actually often behave better than the pdf conversion
    #os.remove("{}.html".format(interfaces_file_url))
    #os.remove("{}-label.html".format(interfaces_file_url))

    return switchmodell

#Function for getting switch configuration from existing switch
def get_switch_conf(request, switch_ip, switch_name):
    #Set switch information for scrapli
    device = {
        "host": switch_ip,
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch_name, switch_ip))
    #Connecting to the switch
    conn = Scrapli(**device)
    conn.open()
    #Get switchmodel from the switch with ssh
    response = conn.send_command("show chassis hardware | display xml")
    response_dict = xmltodict.parse(response.result)
    response_json = json.dumps(response_dict)
    switch_hardware = json.loads(response_json)[
        'rpc-reply']['chassis-inventory']['chassis']

    #######################################################################
    ##########                 Get Location                      ##########
    #######################################################################
    try:
        response = conn.send_command(
            "show configuration snmp location | match location | trim 10")
        switch_location = response.result
    except:
        switch_location =', , , ";'

    if switch_location == '':
        switch_location = ', , , ";'
    #Using regex to get just the location from the response
    regex_location = '(.*)";'
    try:
        switch_location = re.search(
            regex_location, switch_location).groups()
        switch_location = str(switch_location[0])
    except:
        switch_location = ''

    #Split location field into our different fields
    switch_location_list = switch_location.split(', ')
    #Create a dict from the different parts of the location
    dict_switch_location = dict(enumerate(switch_location_list))

    #######################################################################
    ##########                 Get interfaces                    ##########
    #######################################################################
    #Reset interfaces
    switch_interfaces = {}
    try:
        #Ask the switch for interfaces in configuration
        response = conn.send_command(
            "show configuration interfaces | display xml")
        switch_interfaces_dict = json.dumps(xmltodict.parse(response.result))
        switch_interfaces = json.loads(switch_interfaces_dict)
        #Get interface-ranges
        switch_interfaces = switch_interfaces['rpc-reply']['configuration']['interfaces']['interface-range']

    except:
        switch_interfaces = ''

    #Set uplink to fiber if nothing else i configured
    uplink_interfaces = 'sfp'
    #Check Uplink interfaces
    for switch_interface_range in switch_interfaces:
        if switch_interface_range['name'] == 'uplink':
            try:
                #Check if there are any copper interface in uplink
                if re.match('ge-0/0/\d*', str(switch_interface_range['member']['name'])):
                    uplink_interfaces = 'ge'
            except:
                #If the switch has multiple interfaces in the interface-range it throws an exception
                if "swa" in switch_name:
                    messages.warning(request, "Flera uplink-portar, en access-switch ska bara ha en")

        if switch_interface_range['name'] == 'downlink':
            #Reset number of downlink copper interfaces
            downlink_interfaces = 0

            try:
                switch_interface_range['member-range']
                #For member-range find start and end interface
                start_interface = re.search(
                    "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['name']).group(2)
                end_interface = re.search(
                    "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['end-range']).group(2)

                #Create separate member statement for every part of the member-range
                response = conn.send_config(
                    "wildcard range set interfaces interface-range downlink member ge-0/0/[{}-{}]".format(start_interface, end_interface))

                #Delete the member-range
                response = conn.send_config(
                    "delete interfaces interface-range downlink member-range ge-0/0/{}".format(start_interface))
                downlink_interfaces = len(
                    switch_interface_range['member']) + (1 + int(end_interface) - int(start_interface))
            except:
                try:
                    for donwlink_interface in switch_interface_range['member']:
                        if re.match('ge-0/0/\d*', str(donwlink_interface['name'])):
                            downlink_interfaces += 1
                except:
                    pass


        if switch_interface_range['name'] == 'ap':
            try:
                switch_interface_range['@inactive']
                ap_interfaces = 0
            except:
                try:
                    #For member-range find start and end interface
                    switch_interface_range['member-range']
                    start_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['name']).group(2)
                    end_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['end-range']).group(2)

                    #Create separate member statement for every part of the member-range
                    response = conn.send_config(
                        "wildcard range set interfaces interface-range ap member ge-0/0/[{}-{}]".format(start_interface, end_interface))

                    #Delete the member-range
                    response = conn.send_config(
                        "delete interfaces interface-range ap member-range ge-0/0/{}".format(start_interface))
                    ap_interfaces = len(switch_interface_range['member']) + (1 + int(end_interface) - int(start_interface))
                except:
                    ap_interfaces = len(switch_interface_range['member'])


        if switch_interface_range['name'] == 'device':
            try:
                switch_interface_range['@inactive']
                device_interfaces = 0
            except:
                try:
                    #For member-range find start and end interface
                    switch_interface_range['member-range']
                    start_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['name']).group(2)
                    end_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['end-range']).group(2)

                    #Create separate member statement for every part of the member-range
                    response = conn.send_config(
                        "wildcard range set interfaces interface-range device member ge-0/0/[{}-{}]".format(start_interface, end_interface))

                    #Delete the member-range
                    response = conn.send_config(
                        "delete interfaces interface-range device member-range ge-0/0/{}".format(start_interface))
                    device_interfaces = len(switch_interface_range['member']) + (1 + int(end_interface) - int(start_interface))
                except:
                    device_interfaces = len(switch_interface_range['member'])


        if switch_interface_range['name'] == 'pub':

            try:
                switch_interface_range['@inactive']
                pub_interfaces = 0
            except:
                try:
                    #For member-range find start and end interface
                    switch_interface_range['member-range']
                    start_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['name']).group(2)
                    end_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['end-range']).group(2)

                    #Create separate member statement for every part of the member-range
                    response = conn.send_config(
                        "wildcard range set interfaces interface-range pub member ge-0/0/[{}-{}]".format(start_interface, end_interface))

                    #Delete the member-range
                    response = conn.send_config(
                        "delete interfaces interface-range pub member-range ge-0/0/{}".format(start_interface))
                    pub_interfaces = len(switch_interface_range['member']) + (1 + int(end_interface) - int(start_interface))

                except:
                    pub_interfaces = len(switch_interface_range['member'])


        if switch_interface_range['name'] == 'klientklass1':
            try:
                switch_interface_range['@inactive']
                klientklass1_interfaces = 0
            except:
                try:
                    #For member-range find start and end interface
                    switch_interface_range['member-range']
                    start_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['name']).group(2)
                    end_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['end-range']).group(2)

                    #Create separate member statement for every part of the member-range
                    response = conn.send_config(
                        "wildcard range set interfaces interface-range klientklass1 member ge-0/0/[{}-{}]".format(start_interface, end_interface))

                    #Delete the member-range
                    response = conn.send_config(
                        "delete interfaces interface-range klientklass1 member-range ge-0/0/{}".format(start_interface))
                    device_interfaces = len(
                        switch_interface_range['member']) + (1 + int(end_interface) - int(start_interface))
                except:
                    klientklass1_interfaces = len(switch_interface_range['member'])


        if switch_interface_range['name'] == 'klientklass2':
            try:
                switch_interface_range['@inactive']
                klientklass2_interfaces = 0
            except:
                try:
                    #For member-range find start and end interface
                    switch_interface_range['member-range']
                    start_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['name']).group(2)
                    end_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['end-range']).group(2)

                    #Create separate member statement for every part of the member-range
                    response = conn.send_config(
                        "wildcard range set interfaces interface-range klientklass2 member ge-0/0/[{}-{}]".format(start_interface, end_interface))

                    #Delete the member-range
                    response = conn.send_config(
                        "delete interfaces interface-range klientklass2 member-range ge-0/0/{}".format(start_interface))
                    device_interfaces = len(
                        switch_interface_range['member']) + (1 + int(end_interface) - int(start_interface))
                except:
                    klientklass2_interfaces = len(switch_interface_range['member'])
    #If there isn´t any interfaces set interfaces to 0
    try:
        ap_interfaces
    except:
        ap_interfaces = 0

    try:
        device_interfaces
    except:
        device_interfaces = 0

    try:
        pub_interfaces
    except:
        pub_interfaces = 0

    try:
        klientklass1_interfaces
    except:
        klientklass1_interfaces = 0

    try:
        klientklass2_interfaces
    except:
        klientklass2_interfaces = 0

    #Get interfaces in interface range again to load after member-ranges are fixed
    response = conn.send_config(
        "show interfaces | display xml")
    switch_interfaces_dict = json.dumps(xmltodict.parse(response.result))
    switch_interfaces = json.loads(switch_interfaces_dict)
    switch_interfaces = switch_interfaces['rpc-reply']['configuration']['interfaces']['interface-range']

    #Get link status for interfaces
    response = conn.send_command(
        "show interfaces terse | display xml")
    switch_interfaces_terse_dict = json.dumps(xmltodict.parse(response.result))
    switch_interfaces_terse = json.loads(switch_interfaces_terse_dict)
    switch_interfaces_terse = switch_interfaces_terse[
        'rpc-reply']['interface-information']['physical-interface']

    #Reset switch interfaces_terse_encoded
    switch_interfaces_terse_encoded = []
    for interface_terse in switch_interfaces_terse:
        #Add interface dict to every interface
        switch_interfaces_terse_encoded.append(
            {
                'name': interface_terse['name'],
                'admin_status': interface_terse['admin-status'],
                'oper_status': interface_terse['oper-status'],
            }
        )

    # Get unused ports
    session = requests.Session()
    session.timeout = 30  # Set your timeout in seconds
    logging.info("Connecting to Solarwinds")
    #Connect to solarwinds
    swis = orionsdk.SwisClient("SolarWinds-Orion", solarwinds_username,
                               solarwinds_password, verify=False, session=session)
    logging.info("Getting unused ports")
    #Query to get unused Ports for a certain switch
    switch_interfaces_unused = swis.query(
        "SELECT TOP 100 Caption, DNS, IpAddress, Name, PortDescription, DaysUnused FROM Orion.UDT.UnusedPorts WHERE Caption LIKE '{}'".format(switch_name))['results']



    #Set switch_conf dict to gathered config
    switch_conf = {
        'switch_name': switch_name,
        'switch_ip': switch_ip,
        'switch_gatuadress': dict_switch_location.get(0, ''),
        'switch_popularadress': dict_switch_location.get(1, ''),
        'switch_plan': dict_switch_location.get(2, ''),
        'switch_rumsnummer': dict_switch_location.get(3, ''),
        'switch_rumsbeskrivning': dict_switch_location.get(4, ''),
        'switch_interfaces': switch_interfaces,
        'uplink_interface': uplink_interfaces,
        'downlink_interfaces': downlink_interfaces,
        'ap_interfaces': ap_interfaces,
        'device_interfaces': device_interfaces,
        'pub_interfaces': pub_interfaces,
        'klientklass1_interfaces': klientklass1_interfaces,
        'klientklass2_interfaces': klientklass2_interfaces,
        'interfaces_terse': switch_interfaces_terse_encoded,
        'interfaces_unused': switch_interfaces_unused,

    }
    return switch_conf

#Load idex page
def index(request):
    template = loader.get_template('switches/index.html')

    return render(request, 'switches/index.html')

#GUI for replace switch
def replace_switch(request):
    template = loader.get_template('switches/replace_switch.html')
    form = ReplaceSwitch()

    #Uses get to send ip and switchname from list
    switch_ip = request.GET.get('ip', '')
    switch_name = request.GET.get('name', '')
    #Using the function to get the switch configuration
    switch_conf = get_switch_conf(request, switch_ip, switch_name)

    #If form is filled create new switch
    if request.method == 'POST':
        form = ReplaceSwitch(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            cd['old_interfaces'] = switch_conf['switch_interfaces']

            switchmodell = create_switch_conf(request, cd, 'replace_switch')
            messages.success(
                request, "Switchmodell: {}, filer finns på G:\IT-avdelningen special\mist\imports\ekahau\{}".format(switchmodell, cd.get('gatuadress')))

            return render(request, 'switches/replace_switch.html', {'form': form, 'switch_conf': switch_conf})

        else:
            messages.error(
                request, 'Kontrollera att du har fyllt i alla fält')


    return render(request, 'switches/replace_switch.html', {'form': form, 'switch_conf': switch_conf})

#GUI-for replacing switch with swc
def replace_swc_switch(request):
    template = loader.get_template('switches/replace_swc_switch.html')
    form = ReplaceSwcSwitch()

    #GUI for replace switch with swc
    switch_ip = request.GET.get('ip', '')
    #Base the new name on the old but change name from swa- to swc-
    switch_name = request.GET.get('name', '').replace("swa-", "swc-", 1)
    #Get lists of free edge IP-adresses
    ny_ip_adress = get_next_edge_ip()
    #Get configuration of current switch
    switch_conf = get_switch_conf(request, switch_ip, switch_name)

    #If form is posted create new switch
    if request.method == 'POST':
        form = ReplaceSwcSwitch(request.POST)
        #Check if form is valid
        if form.is_valid():
            cd = form.cleaned_data
            #Set old interfaces to switch_interfaces for later report
            cd['old_interfaces'] = switch_conf['switch_interfaces']
            
            #Create switch and return model of switch to the user
            switchmodell = create_swc_switch_conf(request, cd, 'replace_switch')
            messages.success(
                request, "Switchmodell: {}, filer finns på G:\IT-avdelningen special\mist\imports\ekahau\{}".format(switchmodell, cd.get('gatuadress')))
            
            #Render the page
            return render(request, 'switches/replace_swc_switch.html', {'form': form, 'switch_conf': switch_conf, 'IPadress': ny_ip_adress})

        else:
            messages.error(
                request, 'Kontrollera att du har fyllt i alla fält')
    #Render the replace switch page
    return render(request, 'switches/replace_swc_switch.html', {'form': form, 'switch_conf': switch_conf, 'IPadress': ny_ip_adress})

#GUI for searching switch
def search_switch(request):
    template = loader.get_template('switches/search_switch.html')
    form = SearchSwitch()

    if request.method == 'POST':
        form = SearchSwitch(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            #Connect to Solarwinds
            session = requests.Session()
            session.timeout = 30  # Set your timeout in seconds
            logging.info("Connecting to Solarwinds")
            swis = orionsdk.SwisClient("SolarWinds-Orion", solarwinds_username,
                                    solarwinds_password, verify=False, session=session)
            logging.info("Getting switches according to search")
            #Check if entered string is a IP or a switchname
            if valid_ip(cd['switchnamn']):
                #Query to get switch by IP
                nodes = swis.query(
                    "SELECT TOP 500  IPAddress, IPAddressType, Caption, NodeDescription, Description, Location, Status FROM Orion.Nodes WHERE IPAddress LIKE '{}'".format(cd['switchnamn']))['results']
            else:
                #Delete swc or swa to use only the rest of the name in the query
                cd['switchnamn'] = cd['switchnamn'].replace("swa-", "", 1).replace("swc-", "", 1)
                #Query to get access and combined switches that match the string
                nodes = swis.query(
                    "SELECT TOP 500  IPAddress, IPAddressType, Caption, NodeDescription, Description, Location, Status FROM Orion.Nodes WHERE Caption LIKE 'swa-%{}%' OR Caption LIKE 'swc-%{}%'".format(cd['switchnamn'], cd['switchnamn']))['results']

            
            #Render the result
            return render(request, 'switches/search_switch.html', {'form': form, 'nodes': nodes})

    #Render the page when nothing is searched on
    return render(request, 'switches/search_switch.html', {'form': form})

#GUI for configuring switch
def configure_switch(request):
    template = loader.get_template('switches/switch_configuration.html')
    form = ConfigureSwitch()

    #Set variables from the get string
    switch_ip = request.GET.get('ip', '')
    switch_name = request.GET.get('name', '')
    #Get existing switch configure
    switch_conf = get_switch_conf(request, switch_ip, switch_name)
    #Reset swithch interfaces
    switch_interface_conf = []

    
    #Go through interface ranges
    for interface_range in switch_conf['switch_interfaces']:
        #Don't list interface-ranges access-ports and dante since interfaces in those ranges are also in other interface-ranges
        if interface_range['name'] != 'access-ports' and interface_range['name'] != 'dante':
            try:
                #Interfaces look different if it is one interface or multiple in one range so need to convert to list if there is only one interface
                if not isinstance(interface_range['member'], list):
                    interface_range['member'] = [interface_range['member']]
                #Create a dict per interface
                for interface_conf in interface_range['member']:
                    
                    interface_conf_dict = {
                        "interface": interface_conf['name'],
                        "interface_range": interface_range['name']
                    }
                    #Add interface dict to list of interfaces_conf
                    switch_interface_conf.append(interface_conf_dict)
            except:
                pass
    #Include switch_interface_conf in switch_conf
    switch_conf['interface_dict'] = switch_interface_conf
    #If a change is made, make the changes
    if request.method == 'POST':
        form = ConfigureSwitch(request.POST)
        switch_ip = request.GET.get('ip', '')

        if form.is_valid():
            cd = form.cleaned_data
            #Reset interfaces
            interfaces = []
            for conf_item in request.POST.dict():
                #Group interfaces to get just the interface number
                if re.search("(interface_)(\w\w-\d/\d/\d*)", conf_item):
                    interface = re.search(
                        "(interface_)(\w\w-\d/\d/\d*)", conf_item).group(2)
                    #Add he new settings
                    interfaces.append({
                        'interface': interface,
                        'interface_range': request.POST.dict()[conf_item]
                        })
            
            #Reset interface_changes
            interface_changes = []
            #Check the differences between the new and the old interface-configurations
            for interface_old in switch_interface_conf:
                for interface_new in interfaces:
                    #For one interface check if it is still the same interface_range
                    if interface_old['interface'] == interface_new['interface']:
                        if interface_old['interface_range'] != interface_new['interface_range']:
                            #Create dict for changing interfaces
                            interface_change = {
                                'interface': interface_old['interface'],
                                'interface_range_old': interface_old['interface_range'],
                                'interface_range_new': interface_new['interface_range']
                            }
                            #Handle empty or inactive interface-ranges
                            for interface_range in switch_conf['switch_interfaces']:
                                if interface_range['name'] == interface_new['interface_range']:
                                    if '@inactive' in interface_range:
                                        interface_change['interface_range_active'] = False

                                    else:
                                        interface_change['interface_range_active'] = True
                            interface_changes.append(interface_change)
            #Connection info for the switch
            device = {
                "host": switch_ip,
                "auth_username": switch_username,
                "auth_password": switch_password,
                "auth_strict_key": False,
                "platform": "juniper_junos"
            }
            #Logging in to the switch
            logging.info("Logging in to switch {} with IP {}".format(
                switch_name, switch_ip))
            conn = Scrapli(**device)
            conn.open()
            #Set Snmp location according to our standard
            snmp_location = "{}, {}, {}, {}, {}".format(cd['gatuadress'], cd['popularnamn'], cd['plan'], cd['rum_nummer'], cd['rum_beskrivning'])
            #Set hostname to switchname
            response = conn.send_config("set system host-name {}".format(cd['switchnamn']))
            #Update snmp location on switch
            response = conn.send_config(
                'set snmp location "{}"'.format(snmp_location))
            #Make interface-ranges changes
            for interface_change in interface_changes:
                try:
                    ##Set new interface range
                    response = conn.send_config(
                        "set interfaces interface-range {} member {}".format(interface_change['interface_range_new'], interface_change['interface']))
                    #Delete from old interface-range
                    response = conn.send_config(
                        "delete interfaces interface-range {} member {}".format(interface_change['interface_range_old'], interface_change['interface']))
                    #If interface-range is inactive, activate it
                    if not interface_change['interface_range_active']:
                        response = conn.send_config(
                            "activate interfaces interface-range {}".format(interface_change['interface_range_new']))

                except:
                    messages.error(request, "Kunde inte uppdatera interface-range")
            #Do a commit confirmed for not chopping of my leg and comment to know when looking in a switch what made the change
            response = conn.send_config('commit confirmed comment "Netscript Config changes"')
            #As long as the switch still is reachable confirm the commit
            response = conn.send_config('commit')
            #If commit worked show message that it worked
            if "commit complete" in response.result:
                try:
                    messages.success(request, interface_change)
                except:
                    messages.success(request, "Ändringar sparade")
            #If there is a empty interface range deactivate it
            elif "has no member" in response.result:
                #Get which interface-range is the empty one
                empty_interface_range = re.search(
                    "(error: interface-range \')(\w*)(\' has no member)", response.result).group(2)
                #deactivate the interface-range
                response = conn.send_config(
                    "deactivate interfaces interface-range {}".format(empty_interface_range))
                #Do a commit confirmed for not chopping of my leg and comment to know when looking in a switch what made the change
                response = conn.send_config(
                    'commit confirmed comment "Netscript Config changes"')
                    #If commit worked show message that it worked
                response = conn.send_config('commit')
                #If it then worked show message that it worked, if possible show what interface changed otherwise just show a message
                if "commit complete" in response.result:
                    try:
                        messages.success(request, interface_change)
                    except:
                        messages.success(request, "Ändringar sparade")
                else:
                    #If it this commit dosen't work
                    messages.error(request, response.result)
            else:
                #If the first commit didn't work send error message to the user
                messages.error(request, response.result)
            
            #Close connection th the switch
            conn.close()

            #Get new configuration and reload page
            switch_ip = request.GET.get('ip', '')
            switch_name = request.GET.get('name', '')
            switch_conf = get_switch_conf(request, switch_ip, switch_name)
            switch_interface_conf = []

            #Go through interface ranges
            for interface_range in switch_conf['switch_interfaces']:
                #Don't list interface-ranges access-ports and dante since interfaces in those ranges are also in other interface-ranges
                if interface_range['name'] != 'access-ports' and interface_range['name'] != 'dante':
                    try:
                        #Interfaces look different if it is one interface or multiple in one range so need to convert to list if there is only one interface
                        if not isinstance(interface_range['member'], list):
                            interface_range['member'] = [interface_range['member']]

                        #Create a dict per interface
                        for interface_conf in interface_range['member']:
                            
                            interface_conf_dict = {
                                "interface": interface_conf['name'],
                                "interface_range": interface_range['name']
                            }
                            #Add interface dict to list of interfaces_conf
                            switch_interface_conf.append(interface_conf_dict)
                    except:
                        pass

            #Include switch_interface_conf in switch_conf
            switch_conf['interface_dict'] = switch_interface_conf

            #Return page loaded with switchconfiguation
            return render(request, 'switches/switch_configuration.html', {'form': form, 'switch_conf': switch_conf})

        else:
            #If not all required fields are populated ask the user to fix that
            messages.error(
                request, 'Kontrollera att du har fyllt i alla nödvändiga fält (Gatuadress)')
    #Return page witch configuration
    return render(request, 'switches/switch_configuration.html', {'form': form, 'switch_conf': switch_conf})

#GUI for creating new access-switch
def new_switch(request):
    form = NewSwitch()
    template = loader.get_template('switches/new_switch.html')
    #Get all available IP-adresses
    ny_ip_adress = get_next_access_ip()
    


    if request.method == 'POST':
        form = NewSwitch(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                #Create new switch-configuration based on the form and populate switchmodel
                switchmodell = create_switch_conf(request, cd, 'new_switch')
                #Show message of what switchmodel will be used and where all the files are stored
                messages.success(
                request, "Switchmodell: {}, filer finns på G:\IT-avdelningen special\mist\imports\ekahau\{}".format(switchmodell, cd.get('gatuadress')))
            except:
                messages.error(request, "Ngt gick fel")

            #Load page
            return render(request, 'switches/new_switch.html', {'form': form, 'IPadress': ny_ip_adress})

        else:
            #If not all fields are poulated ask the user to correct that
            messages.error(
                request, 'Kontrollera att du har fyllt i alla fält')

    #Load page
    return render(request, 'switches/new_switch.html', {'form': form, 'IPadress': ny_ip_adress})

#GUI for creating new swc-switch
def new_swc_switch(request):
    form = NewSwcSwitch()
    template = loader.get_template('switches/new_swc_switch.html')
    #Get the nex available IP-adress for a edge switch
    ny_ip_adress = get_next_edge_ip()

    #Populate variables from GET if created with new site
    gatuadress = request.GET.get('gatuadress', '')
    popularnamn = request.GET.get('popularnamn', '')


    if request.method == 'POST':
        form = NewSwcSwitch(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                #Create new switch-configuration based on the form and populate switchmodel
                switchmodell = create_swc_switch_conf(
                    request, cd, 'new_switch')
                #Show message of what switchmodel will be used and where all the files are stored
                messages.success(
                    request, "Switchmodell: {}, filer finns på G:\IT-avdelningen special\mist\imports\ekahau\{}".format(switchmodell, cd.get('gatuadress')))
            except:
                messages.error(request, "Något gick fel")
            #Return page
            return render(request, 'switches/new_swc_switch.html', {'form': form, 'IPadress': ny_ip_adress, 'gatuadress': gatuadress, 'popularnamn': popularnamn})

        else:
            #If not all fields are poulated ask the user to correct that
            messages.error(
                request, 'Kontrollera att du har fyllt i alla fält')
    #Return page
    return render(request, 'switches/new_swc_switch.html', {'form': form, 'IPadress': ny_ip_adress, 'gatuadress': gatuadress, 'popularnamn': popularnamn})

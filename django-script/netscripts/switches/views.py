from django.contrib.messages.api import info
from django.core.exceptions import AppRegistryNotReady
from django.shortcuts import render
from django.template import loader
from django.contrib import messages
from django.http import HttpResponse
from django.core.files.storage import FileSystemStorage

from django.template.loader import render_to_string
import re #Import regex
import orionsdk
import requests
import yaml
import os
import pdfkit
import ipaddress
import json
import xmltodict

from scrapli import Scrapli


from .forms import NewSwitch, SearchSwitch, ReplaceSwitch, ConfigureSwitch

import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='../logs/switches.log', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')


with open('mist_import_sites/config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

import_path_ekahau = config['import']['import_ekahau_path']

##Switch variables
switch_username = config['switch']['username']
switch_password = config['switch']['password']
solarwinds_username = config['solarwinds']['username']
solarwinds_password = config['solarwinds']['password']
solarwinds_certificate = config['solarwinds']['certificate_file']

#Unicode to make config snmp
unicode_table = {
    ord('å'): 'a',
    ord('ä'): 'a',
    ord('ö'): 'o',
}

def get_next_access_ip():
    session = requests.Session()
    session.timeout = 30  # Set your timeout in seconds
    logging.info("Connecting to Solarwinds")
    swis = orionsdk.SwisClient("SolarWinds-Orion", solarwinds_username,
                               solarwinds_password, verify=False, session=session)
    logging.info("Getting free IP-adresses")
    nodes = swis.query(
        "SELECT TOP 65025 IPAddress FROM IPAM.IPNode WHERE Status=2 AND SubnetId LIKE '149'")
    return nodes['results']

def valid_ip(address):
    try:
        print(ipaddress.ip_address(address))
        return True
    except:
        return False

def create_switch_conf(request, cd, source):
    antal_interfaces = int(cd['interface_ap']) + \
        int(cd['interface_device']) + \
        int(cd['interface_pub']) + \
        int(cd['interface_klientklass1']) + \
            int(cd['interface_klientklass2']) + \
                int(cd['interface_cu_downlink'])

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
        messages.error(request, 'Vi har inte så stora switchar')
        return render(request, 'switches/new_switch.html', {'form': form})

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

    last_interface_number = 0

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

    cd['gatuadress_uni'] = cd['gatuadress'].translate(unicode_table)
    cd['popularnamn_uni'] = cd['popularnamn'].translate(unicode_table)
    cd['plan_uni'] = cd['plan'].translate(unicode_table)
    cd['rum_nummer_uni'] = cd['rum_nummer'].translate(unicode_table)
    cd['rum_beskrivning_uni'] = cd['rum_beskrivning'].translate(
        unicode_table)
    context = {
            "conf": cd,
            "interfaces": interfaces,
            "switch_model": switchmodell
        }

    if source == "new_switch":
        template_table = loader.get_template(
            'switches/switch_interfaces.html')

    elif source == "replace_switch":
        template_table = loader.get_template(
            'switches/switch_interfaces_replacement.html')

    else:
        template_table = loader.get_template(
            'switches/switch_interfaces.html')

    template_ex2300 = loader.get_template('switches/swa-ex2300.conf')

    template_label = loader.get_template('switches/switch_label.html')

    fs = FileSystemStorage()
    conf_file_url = "{}/{}/{}.conf".format(import_path_ekahau,
                                            cd.get('gatuadress'), cd['switchnamn'])
    interfaces_file_url = "{}/{}/{}".format(import_path_ekahau,
                                            cd.get('gatuadress'), cd['switchnamn'])
    try:
        os.mkdir(os.path.join(
            import_path_ekahau, cd.get('gatuadress')))
    except:
        pass

    f = open(conf_file_url, "w")
    f.write(template_ex2300.render(context))
    f.close()

    f_interfaces = open("{}.html".format(interfaces_file_url), "w")
    f_interfaces.write(template_table.render(context))
    f_interfaces.close()

    pdfkit.from_file("{}.html".format(interfaces_file_url),
                        "{}.pdf".format(interfaces_file_url))

    f_switch_label = open(
        "{}-label.html".format(interfaces_file_url), "w")
    f_switch_label.write(template_label.render(cd))
    f_switch_label.close()

    label_options = {
        'page-height': '12mm',
        'page-width': '62mm',
        'margin-top': '0',
        'margin-bottom': '0',
    }

    pdfkit.from_file("{}-label.html".format(interfaces_file_url),
                        "{}-label.pdf".format(interfaces_file_url), options=label_options)

    #os.remove("{}.html".format(interfaces_file_url))
    #os.remove("{}-label.html".format(interfaces_file_url))

    return switchmodell



def get_switch_conf(request, switch_ip, switch_name):
    device = {
        "host": switch_ip,
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch_name, switch_ip))
    conn = Scrapli(**device)
    conn.open()
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

    regex_location = '(.*)";'
    try:
        switch_location = re.search(
            regex_location, switch_location).groups()
        switch_location = str(switch_location[0])
    except:
        switch_location = ''

    switch_location_list = switch_location.split(', ')
    dict_switch_location = dict(enumerate(switch_location_list))

    #######################################################################
    ##########                 Get interfaces                    ##########
    #######################################################################
    switch_interfaces = {}
    try:
        response = conn.send_command(
            "show configuration interfaces | display xml")
        switch_interfaces_dict = json.dumps(xmltodict.parse(response.result))
        switch_interfaces = json.loads(switch_interfaces_dict)
        switch_interfaces = switch_interfaces['rpc-reply']['configuration']['interfaces']['interface-range']

    except:
        switch_interfaces = ''

    uplink_interfaces = 'sfp'
    for switch_interface_range in switch_interfaces:
        if switch_interface_range['name'] == 'uplink':
            try:
                if re.match('ge-0/0/\d*', str(switch_interface_range['member']['name'])):
                    uplink_interfaces = 'ge'
            except:
                messages.warning(request, "Flera uplink-portar, en access-switch ska bara ha en")

        if switch_interface_range['name'] == 'downlink':
            downlink_interfaces = 0
            for donwlink_interface in switch_interface_range['member']:
                if re.match('ge-0/0/\d*', str(donwlink_interface['name'])):
                    downlink_interfaces += 1
            try:
                switch_interface_range['member-range']
                start_interface = re.search(
                    "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['name']).group(2)
                end_interface = re.search(
                    "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['end-range']).group(2)
                response = conn.send_config(
                    "wildcard range set interfaces interface-range downlink member ge-0/0/[{}-{}]".format(start_interface, end_interface))
                response = conn.send_config(
                    "delete interfaces interface-range downlink member-range ge-0/0/{}".format(start_interface))
                device_interfaces = len(
                    switch_interface_range['member']) + (1 + int(end_interface) - int(start_interface))
            except:
                downlink_interfaces = len(switch_interface_range['member'])


        if switch_interface_range['name'] == 'ap':
            try:
                switch_interface_range['@inactive']
                ap_interfaces = 0
            except:
                try:
                    switch_interface_range['member-range']
                    start_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['name']).group(2)
                    end_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['end-range']).group(2)
                    response = conn.send_config(
                        "wildcard range set interfaces interface-range ap member ge-0/0/[{}-{}]".format(start_interface, end_interface))
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
                    switch_interface_range['member-range']
                    start_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['name']).group(2)
                    end_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['end-range']).group(2)
                    response = conn.send_config(
                        "wildcard range set interfaces interface-range device member ge-0/0/[{}-{}]".format(start_interface, end_interface))
                    response = conn.send_config(
                        "delete interfaces interface-range device member-range ge-0/0/{}".format(start_interface))
                    device_interfaces = len(switch_interface_range['member']) + (1 + int(end_interface) - int(start_interface))
                except:
                    device_interfaces = len(switch_interface_range['member'])


        if switch_interface_range['name'] == 'pub':
            #messages.info(request, switch_interface_range['member-range'])
            #messages.info(request, switch_interfaces)
            try:
                switch_interface_range['@inactive']
                pub_interfaces = 0
            except:
                try:
                    switch_interface_range['member-range']
                    start_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['name']).group(2)
                    end_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['end-range']).group(2)
                    response = conn.send_config(
                        "wildcard range set interfaces interface-range pub member ge-0/0/[{}-{}]".format(start_interface, end_interface))
                    response = conn.send_config(
                        "delete interfaces interface-range pub member-range ge-0/0/{}".format(start_interface))
                    pub_interfaces = len(switch_interface_range['member']) + (1 + int(end_interface) - int(start_interface))
                    #switch_interface_range['member'] = list(switch_interface_range['member'])
                    #messages.info(request, type(
                        #switch_interface_range['member']).__name__)
                    #for interface in range(int(start_interface), (int(end_interface)+1)):

                        #switch_interface_range['member'].append({
                        #    'name': 'ge-0/0/{}'.format(interface)
                        #})
                    #messages.info(
                            #request, switch_interface_range['member'])


                        #switch_interface_range['member']
                except:
                    pub_interfaces = len(switch_interface_range['member'])
                #pass


        if switch_interface_range['name'] == 'klientklass1':
            try:
                switch_interface_range['@inactive']
                klientklass1_interfaces = 0
            except:
                try:
                    switch_interface_range['member-range']
                    start_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['name']).group(2)
                    end_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['end-range']).group(2)
                    response = conn.send_config(
                        "wildcard range set interfaces interface-range klientklass1 member ge-0/0/[{}-{}]".format(start_interface, end_interface))
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
                    switch_interface_range['member-range']
                    start_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['name']).group(2)
                    end_interface = re.search(
                        "(\w\w-\d/\d/)(\d*)", switch_interface_range['member-range']['end-range']).group(2)
                    response = conn.send_config(
                        "wildcard range set interfaces interface-range klientklass2 member ge-0/0/[{}-{}]".format(start_interface, end_interface))
                    response = conn.send_config(
                        "delete interfaces interface-range klientklass2 member-range ge-0/0/{}".format(start_interface))
                    device_interfaces = len(
                        switch_interface_range['member']) + (1 + int(end_interface) - int(start_interface))
                except:
                    klientklass2_interfaces = len(switch_interface_range['member'])

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

    switch_interfaces_terse_encoded = []
    for interface_terse in switch_interfaces_terse:
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
    swis = orionsdk.SwisClient("SolarWinds-Orion", solarwinds_username,
                               solarwinds_password, verify=False, session=session)
    logging.info("Getting unused ports")
    switch_interfaces_unused = swis.query(
        "SELECT TOP 100 Caption, DNS, IpAddress, Name, PortDescription, DaysUnused FROM Orion.UDT.UnusedPorts WHERE Caption LIKE '{}'".format(switch_name))['results']




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


def index(request):
    template = loader.get_template('switches/index.html')

    return render(request, 'switches/index.html')


def replace_switch(request):
    template = loader.get_template('switches/replace_switch.html')
    form = ReplaceSwitch()

    switch_ip = request.GET.get('ip', '')
    switch_name = request.GET.get('name', '')
    switch_conf = get_switch_conf(request, switch_ip, switch_name)

    if request.method == 'POST':
        form = ReplaceSwitch(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            #try:
            cd['old_interfaces'] = switch_conf['switch_interfaces']
            #messages.success(request, cd['old_interfaces'])
            switchmodell = create_switch_conf(request, cd, 'replace_switch')
            messages.success(
                request, "Switchmodell: {}, filer finns på G:\IT-avdelningen special\mist\imports\ekahau\{}".format(switchmodell, cd.get('gatuadress')))
            #except:
                #messages.error(request, "Ngt gick fel")

            return render(request, 'switches/replace_switch.html', {'form': form, 'switch_conf': switch_conf})

        else:
            messages.error(
                request, 'Kontrollera att du har fyllt i alla fält')


    return render(request, 'switches/replace_switch.html', {'form': form, 'switch_conf': switch_conf})


def search_switch(request):
    template = loader.get_template('switches/search_switch.html')
    form = SearchSwitch()

    if request.method == 'POST':
        form = SearchSwitch(request.POST)
        if form.is_valid():
            cd = form.cleaned_data

            session = requests.Session()
            session.timeout = 30  # Set your timeout in seconds
            logging.info("Connecting to Solarwinds")
            swis = orionsdk.SwisClient("SolarWinds-Orion", solarwinds_username,
                                    solarwinds_password, verify=False, session=session)
            logging.info("Getting switches according to search")

            if valid_ip(cd['switchnamn']):
                nodes = swis.query(
                    "SELECT TOP 500  IPAddress, IPAddressType, Caption, NodeDescription, Description, Location, Status FROM Orion.Nodes WHERE IPAddress LIKE '{}'".format(cd['switchnamn']))['results']
            else:
                nodes = swis.query(
                    "SELECT TOP 500  IPAddress, IPAddressType, Caption, NodeDescription, Description, Location, Status FROM Orion.Nodes WHERE Caption LIKE 'swa-%{}%'".format(cd['switchnamn']))['results']

            #messages.success(request, nodes)

            return render(request, 'switches/search_switch.html', {'form': form, 'nodes': nodes})


    return render(request, 'switches/search_switch.html', {'form': form})


def configure_switch(request):
    template = loader.get_template('switches/switch_configuration.html')
    form = ConfigureSwitch()

    switch_ip = request.GET.get('ip', '')
    switch_name = request.GET.get('name', '')
    switch_conf = get_switch_conf(request, switch_ip, switch_name)
    switch_interface_conf = []

    #messages.success(request, switch_conf)

    for interface_range in switch_conf['switch_interfaces']:
        if interface_range['name'] != 'access-ports':
            try:
                if not isinstance(interface_range['member'], list):
                    interface_range['member'] = [interface_range['member']]
                for interface_conf in interface_range['member']:
                    #messages.success(request, "Interface: {} Interface-range: {}".format(interface_conf['name'], interface_range['name']))
                    interface_conf_dict = {
                        "interface": interface_conf['name'],
                        "interface_range": interface_range['name']
                    }
                    switch_interface_conf.append(interface_conf_dict)
            except:
                pass
    switch_conf['interface_dict'] = switch_interface_conf

    if request.method == 'POST':
        form = ConfigureSwitch(request.POST)
        switch_ip = request.GET.get('ip', '')

        if form.is_valid():
            cd = form.cleaned_data
            interfaces = []
            for conf_item in request.POST.dict():

                if re.search("(interface_)(\w\w-\d/\d/\d*)", conf_item):
                    interface = re.search(
                        "(interface_)(\w\w-\d/\d/\d*)", conf_item).group(2)

                    interfaces.append({
                        'interface': interface,
                        'interface_range': request.POST.dict()[conf_item]
                        })
            #messages.success(request, interfaces)
            #messages.success(request, switch_interface_conf)

            interface_changes = []

            for interface_old in switch_interface_conf:
                for interface_new in interfaces:
                    if interface_old['interface'] == interface_new['interface']:
                        if interface_old['interface_range'] != interface_new['interface_range']:
                            interface_change = {
                                'interface': interface_old['interface'],
                                'interface_range_old': interface_old['interface_range'],
                                'interface_range_new': interface_new['interface_range']
                            }
                            for interface_range in switch_conf['switch_interfaces']:
                                if interface_range['name'] == interface_new['interface_range']:
                                    if '@inactive' in interface_range:
                                        interface_change['interface_range_active'] = False

                                    else:
                                        interface_change['interface_range_active'] = True
                            interface_changes.append(interface_change)

            device = {
                "host": switch_ip,
                "auth_username": switch_username,
                "auth_password": switch_password,
                "auth_strict_key": False,
                "platform": "juniper_junos"
            }
            logging.info("Logging in to switch {} with IP {}".format(
                switch_name, switch_ip))
            conn = Scrapli(**device)
            conn.open()
            #messages.success(request, cd)
            snmp_location = "{}, {}, {}, {}, {}".format(cd['gatuadress'], cd['popularnamn'], cd['plan'], cd['rum_nummer'], cd['rum_beskrivning'])
            response = conn.send_config("set system host-name {}".format(cd['switchnamn']))
            response = conn.send_config(
                "set snmp location {}".format(snmp_location))
            for interface_change in interface_changes:
                try:
                    response = conn.send_config(
                        "set interfaces interface-range {} member {}".format(interface_change['interface_range_new'], interface_change['interface']))
                    response = conn.send_config(
                        "delete interfaces interface-range {} member {}".format(interface_change['interface_range_old'], interface_change['interface']))
                    if not interface_change['interface_range_active']:
                        response = conn.send_config(
                            "activate interfaces interface-range {}".format(interface_change['interface_range_new']))

                except:
                    messages.error(request, "Kunde inte uppdatera interface-range")
            response = conn.send_config('commit confirmed comment "Netscript Config changes"')
            response = conn.send_config('commit')
            if "commit complete" in response.result:
                try:
                    messages.success(request, interface_change)
                except:
                    messages.success(request, "Ändringar sparade")
            elif "has no member" in response.result:
                empty_interface_range = re.search(
                    "(error: interface-range \')(\w*)(\' has no member)", response.result).group(2)
                response = conn.send_config(
                    "deactivate interfaces interface-range {}".format(empty_interface_range))
                response = conn.send_config(
                    'commit confirmed comment "Netscript Config changes"')
                response = conn.send_config('commit')
                if "commit complete" in response.result:
                    try:
                        messages.success(request, interface_change)
                    except:
                        messages.success(request, "Ändringar sparade")
                else:
                    messages.error(request, response.result)
            else:
                messages.error(request, response.result)



            #try:
            #cd['old_interfaces'] = switch_conf['switch_interfaces']
            #messages.success(request, cd['old_interfaces'])
            #messages.success(
            #    request, "Switch: {}, Uppdaterad".format(switchmodell))
            #except:
            #messages.error(request, "Ngt gick fel")

            conn.close()

            switch_ip = request.GET.get('ip', '')
            switch_name = request.GET.get('name', '')
            switch_conf = get_switch_conf(request, switch_ip, switch_name)
            switch_interface_conf = []

            #messages.success(request, switch_conf)

            for interface_range in switch_conf['switch_interfaces']:
                if interface_range['name'] != 'access-ports':
                    try:
                        if not isinstance(interface_range['member'], list):
                            interface_range['member'] = [interface_range['member']]
                        for interface_conf in interface_range['member']:
                            #messages.success(request, "Interface: {} Interface-range: {}".format(interface_conf['name'], interface_range['name']))
                            interface_conf_dict = {
                                "interface": interface_conf['name'],
                                "interface_range": interface_range['name']
                            }
                            switch_interface_conf.append(interface_conf_dict)
                    except:
                        pass
            switch_conf['interface_dict'] = switch_interface_conf

            return render(request, 'switches/switch_configuration.html', {'form': form, 'switch_conf': switch_conf})

        else:
            messages.error(
                request, 'Kontrollera att du har fyllt i alla fält')

    return render(request, 'switches/switch_configuration.html', {'form': form, 'switch_conf': switch_conf})


def new_switch(request):
    form = NewSwitch()
    template = loader.get_template('switches/new_switch.html')
    ny_ip_adress = get_next_access_ip()
    #messages.info(request, ny_ip_adress)


    if request.method == 'POST':
        form = NewSwitch(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                switchmodell = create_switch_conf(request, cd, 'new_switch')
                messages.success(
                request, "Switchmodell: {}, filer finns på G:\IT-avdelningen special\mist\imports\ekahau\{}".format(switchmodell, cd.get('gatuadress')))
            except:
                messages.error(request, "Ngt gick fel")

            return render(request, 'switches/new_switch.html', {'form': form, 'IPadress': ny_ip_adress})

        else:
            messages.error(
                request, 'Kontrollera att du har fyllt i alla fält')


    return render(request, 'switches/new_switch.html', {'form': form, 'IPadress': ny_ip_adress})

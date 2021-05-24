import requests
import orionsdk
import yaml
import json
import pandas
import re
import time
import xmltodict

#Email imports
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from scrapli import Scrapli

with open('/opt/scripts/switches/config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='/opt/scripts/logs/APTroubleshoot.log', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')

switch_username = config['switch']['username']
switch_password = config['switch']['password']
solarwinds_username = config['solarwinds']['username']
solarwinds_password = config['solarwinds']['password']
solarwinds_certificate = config['solarwinds']['certificate_file']

#Regex
regex_interface_status = 'ge-\d+\/\d+\/(?P<interface>\d+|\d+.\d)\s+(?P<admin>up|down) \s+(?P<link>up|down)'
regex_interface_short = '(?P<interface_short>ge-\d+\/\d+\/\d+)'

#email settings
smtp_port = config['email']['smtp_port']
smtp_server = config['email']['smtp_server']
smtp_login = config['email']['smtp_username']
smtp_password = config['email']['smtp_password']
sender_email = config['email']['sender_email']
receiver_email = config['email']['receiver_email']
message = MIMEMultipart("alternative")
message["Subject"] = "Netscript Accesspunkts-fel"
message["From"] = sender_email
message["To"] = receiver_email


def interfaceShort(switch_interface_name):
    switch_interface_name_short = (
        re.search(regex_interface_short, switch_interface_name).group('interface_short'))
    return switch_interface_name_short


def bouncePOE(switch_interface):
    device = {
        "host": switch_interface['SwitchIP'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch_interface['SwitchName'], switch_interface['SwitchIP']))
    conn = Scrapli(**device)
    conn.open()
    response = conn.send_config("set poe interface {} disable".format(
        switch_interface['PortName']))
    response = conn.send_config("commit confirmed 2 comment netscripts01")
    logging.info(response.elapsed_time)
    logging.info(response.result)
    conn.close()

def checkPOEPort(switch_interface):
    device = {
        "host": switch_interface['SwitchIP'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch_interface['SwitchName'], switch_interface['SwitchIP']))
    conn = Scrapli(**device)
    conn.open()
    response = conn.send_command(
        "show poe interface {}".format(switch_interface['PortName']))
    if '0.5W' in response.result:
        print('AP-needs {} reboot'.format(ap['Caption']))
        logging.info('AP-needs {} reboot'.format(ap['Caption']))
        return True
    else:
        logging.info("Another fault troubleshoot {} connected to {} on {} with IP {}".format(
            ap['Caption'], switch_interface['PortName'], switch_interface['SwitchName'], switch_interface['SwitchIP']))
        print("Another fault troubleshoot {} connected to {} on {} with IP {}".format(
            ap['Caption'], switch_interface['PortName'], switch_interface['SwitchName'], switch_interface['SwitchIP']))
        return False


def checkPOEPower(switch_interface):
    device = {
        "host": switch_interface['SwitchIP'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch_interface['SwitchName'], switch_interface['SwitchIP']))
    conn = Scrapli(**device)
    conn.open()
    try:
        response = conn.send_command(
            "show poe interface {} | display xml".format(switch_interface['PortName']))
        response_dict = xmltodict.parse(response.result)
        response_json = json.dumps(response_dict)
        interface_poe = json.loads(response_json)
        poe_interface_power = interface_poe['rpc-reply']['poe']['interface-information-detail']
        ['interface-power-detail']
        return poe_interface_power['interface-power-detail']
    except:
        return 'Non POE-switch'


def checkLink(switch_interface):
    device = {
        "host": switch_interface['SwitchIP'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch_interface['SwitchName'], switch_interface['SwitchIP']))
    conn = Scrapli(**device)
    conn.open()
    response = conn.send_command(
        "show interfaces terse {}".format(switch_interface['PortName']))
    interface_status = re.search(regex_interface_status, response.result)
    if 'up' in interface_status.group('link'):
        try:
            logging.info("AP {} has ethernet link{} connected to {} on {} with IP {}".format(
                ap['Caption'], switch_interface['PortName'], switch_interface['SwitchName'], switch_interface['SwitchIP']))
            print("AP interface status admin: {} link: {}".format(interface_status.group(
                'admin'), interface_status.group('link')))
            return True
        except:
            logging.info("AP has link but is down")
            return True
    else:
        logging.info("AP has no ethernet link {} connected to {} on {} with IP {}".format(
            ap['Caption'], switch_interface['PortName'], switch_interface['SwitchName'], switch_interface['SwitchIP']))
        print("AP interface status admin: {} link: {}".format(interface_status.group(
            'admin'), interface_status.group('link')))
        return False


def checkCable(switch_interface):
    device = {
        "host": switch_interface['SwitchIP'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch_interface['SwitchName'], switch_interface['SwitchIP']))
    conn = Scrapli(**device)
    conn.open()
    interface_test_status = 'Started'
    response = conn.send_command(
        "request diagnostics tdr start interface {}".format(switch_interface['PortName']))
    response = conn.send_command("show chassis hardware | display xml")
    response_dict = xmltodict.parse(response.result)
    response_json = json.dumps(response_dict)
    switch_hardware = json.loads(response_json)[
        'rpc-reply']['chassis-inventory']['chassis']
    switch_model = switch_hardware['description']
    print(switch_model)
    if "EX2300" in switch_model:
        while interface_test_status == 'Started':
            response = conn.send_command(
                "show diagnostics tdr interface {} | display xml".format(switch_interface['PortName']))
            response_dict = xmltodict.parse(response.result)
            response_json = json.dumps(response_dict)
            interface_tdr = json.loads(response_json)
            interface_test_status = interface_tdr[
                'rpc-reply']['vct']['vct-interface-information-detail']['vct-interface-test-status']
    elif "EX2200" in switch_model:
        while interface_test_status == 'Started':
            response = conn.send_command(
                "show diagnostics tdr interface {} | display xml".format(switch_interface['PortName']))
            response_dict = xmltodict.parse(response.result)
            response_json = json.dumps(response_dict)
            interface_tdr = json.loads(response_json)
            interface_test_status = interface_tdr[
                'rpc-reply']['tdr']['interface-information-detail']['interface-test-status']
    response = conn.send_command(
        "show diagnostics tdr interface {}".format(switch_interface['PortName']))
    return response.result


def checkVlanAPmgm(switch_interface):
    device = {
        "host": switch_interface['SwitchIP'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch_interface['SwitchName'], switch_interface['SwitchIP']))
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
            "show ethernet-switching interface {} | display xml".format(switch_interface['PortName']))
        response_dict = xmltodict.parse(response.result)
        response_json = json.dumps(response_dict)
        interface_vlans = json.loads(response_json)
        interface_vlan_apmgm = interface_vlans['rpc-reply']['l2ng-l2ald-iff-interface-information'][
            'l2ng-l2ald-iff-interface-entry']['l2ng-l2ald-iff-interface-entry']
        #print(interface_vlan_apmgm)
        for interface_vlan in interface_vlan_apmgm:
            if interface_vlan['l2iff-interface-vlan-name'] == 'apmgm' and interface_vlan['l2iff-interface-vlan-member-tagness'] == 'untagged':
                return True
        return False
    elif "EX2200" in switch_model:
        response = conn.send_command(
            "show ethernet-switching interface {} | display xml".format(switch_interface['PortName']))
        response_dict = xmltodict.parse(response.result)
        response_json = json.dumps(response_dict)
        interface_vlans = json.loads(response_json)
        interface_vlan_apmgm = interface_vlans['rpc-reply']['switching-interface-information'][
            'interface']['interface-vlan-member-list']
        print(interface_vlan_apmgm['interface-vlan-member'])
        if isinstance(interface_vlan_apmgm, list):
            for interface_vlan_member in interface_vlan_apmgm:
                if interface_vlan_member['interface-vlan-member']['interface-vlan-name'] == 'apmgm' and interface_vlan_member['interface-vlan-member']['interface-vlan-member-tagness'] == 'untagged':
                    return True
        else:
            if interface_vlan_apmgm['interface-vlan-member']['interface-vlan-name'] == 'apmgm' and interface_vlan_apmgm['interface-vlan-member']['interface-vlan-member-tagness'] == 'untagged':
                return True
        #print(interface_vlan_apmgm)
        #for interface_vlan in interface_vlan_apmgm['interface-vlan-member']:
            #if interface_vlan['interface-vlan-name'] == 'apmgm' and interface_vlan#['interface-vlan-member-tagness'] == 'untagged':
            #    return True
        return False


def fixVlanAPmgm(switch_interface):
    device = {
        "host": switch_interface['SwitchIP'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch_interface['SwitchName'], switch_interface['SwitchIP']))
    conn = Scrapli(**device)
    conn.open()
    response = conn.send_command("show chassis hardware | display xml")
    response_dict = xmltodict.parse(response.result)
    response_json = json.dumps(response_dict)
    switch_hardware = json.loads(response_json)[
        'rpc-reply']['chassis-inventory']['chassis']
    switch_model = switch_hardware['description']
    print(switch_model)
    if 'EX2300' in switch_model:
        response = conn.send_command(
            "show ethernet-switching interface {} | display xml".format(switch_interface['PortName']))
        response_dict = xmltodict.parse(response.result)
        response_json = json.dumps(response_dict)
        interface_vlans = json.loads(response_json)
        interface_vlan_apmgm = interface_vlans['rpc-reply']['l2ng-l2ald-iff-interface-information'][
            'l2ng-l2ald-iff-interface-entry']['l2ng-l2ald-iff-interface-entry']
        switch_interface_vlan = 'downlink'
        #print(interface_vlan_apmgm)
        for interface_vlan in interface_vlan_apmgm:
            if interface_vlan['l2iff-interface-vlan-member-tagness'] == 'untagged':
                switch_interface_vlan = interface_vlan['l2iff-interface-vlan-name']
    elif 'EX2200' in switch_model:
        response = conn.send_command(
            "show ethernet-switching interface {} | display xml".format(switch_interface['PortName']))
        response_dict = xmltodict.parse(response.result)
        response_json = json.dumps(response_dict)
        interface_vlans = json.loads(response_json)
        interface_vlan_apmgm = interface_vlans['rpc-reply']['switching-interface-information'][
            'interface']['interface-vlan-member-list']['interface-vlan-member']
        try:
            switch_interface_vlan = interface_vlan_apmgm['interface-vlan-name']
        except:
            switch_interface_vlan = 'downlink'
        print(interface_vlan_apmgm)

        #for interface_vlan in interface_vlan_apmgm:
        #    if interface_vlan['interface-vlan-member-tagness'] == 'untagged':
        #        switch_interface_vlan = interface_vlan['interface-vlan-name']

    response = conn.send_config(
        "set interfaces interface-range ap member {}".format(
            switch_interface['PortName']))
    response = conn.send_config(
        "delete interfaces interface-range {} member {}".format(
            switch_interface_vlan, switch_interface['PortName']))
    response = conn.send_config(
        'commit comment "fel vlan till ap"')


session = requests.Session()
session.timeout = 30  # Set your timeout in seconds
logging.info("Connecting to Solarwinds")
swis = orionsdk.SwisClient("SolarWinds-Orion", solarwinds_username,
                           solarwinds_password, verify=False, session=session)
logging.info("Getting switches that need to reboot")
nodes = swis.query(
    "SELECT NodeID, Caption, IPAddress, Status FROM Orion.Nodes WHERE Caption LIKE 'ap-%' AND Status LIKE 2")

aps = nodes['results']

print(aps)

dict_aps = []

for ap in aps:
    print(ap['Caption'])
    port_nodes = ''
    port_nodes = swis.query(
        "SELECT DISTINCT TOP 100 Port.Name AS PortName, Nodes.Caption AS SwitchName, Nodes.IPAddress AS SwitchIP, Nodes.Status AS SwitchStatus, PortToEndpointHistory.ConnectionType FROM Orion.UDT.IPAddressHistory INNER JOIN Orion.UDT.PortToEndpointHistory ON IPAddressHistory.EndpointID=PortToEndpointHistory.EndpointID INNER JOIN Orion.UDT.Port ON PortToEndpointHistory.PortID=Port.PortID INNER JOIN Orion.Nodes ON Port.NodeID=Nodes.NodeID WHERE IPAddressHistory.IPAddress LIKE '{}' AND SwitchName LIKE 'swa-%' AND PortName LIKE 'ge-%/0/%' AND PortToEndpointHistory.ConnectionType LIKE '1'".format(ap['IPAddress']))
    switch_interfaces = port_nodes['results']
    if not switch_interfaces:
        print("Can't find switch-interface for {}".format(ap['Caption']))
        logging.info(
            "Can't find switch-interface for {}".format(ap['Caption']))

        dict_ap = {
            "apName": ap['Caption'],
            "apIPAddress": ap['IPAddress'],
            "switchPort": '',
            "switchName": '',
            "switchIPAddress": '',
            "problem": "Can't find switchport",
            "solution": ""
        }
    else:
        for switch_interface in switch_interfaces:
            switch_interface['PortName'] = interfaceShort(
                switch_interface['PortName'])
            dict_ap = {
                "apName": ap['Caption'],
                "apIPAddress": ap['IPAddress'],
                "switchPort": switch_interface['PortName'],
                "switchName": switch_interface['SwitchName'],
                "switchIPAddress": switch_interface['SwitchIP'],
                "poe": "",
                "problem": "Can't find a switchport that isn't a uplink",
                "solution": ""
            }
            print(switch_interface)

            if checkPOEPort(switch_interface):
                bouncePOE(switch_interface)
                dict_ap = {
                    "apName": ap['Caption'],
                    "apIPAddress": ap['IPAddress'],
                    "switchPort": switch_interface['PortName'],
                    "switchName": switch_interface['SwitchName'],
                    "switchIPAddress": switch_interface['SwitchIP'],
                    "problem": "POE-0.5W",
                    "solution": "POE-port bounced"
                }

            elif checkLink(switch_interface):
                if checkVlanAPmgm(switch_interface):
                    logging.warning("Ethernet link but AP unreachable {} at the switch {} with IP {}".format(
                        switch_interface['PortName'], switch_interface['SwitchName'], switch_interface['SwitchIP']))
                    dict_ap = {
                        "apName": ap['Caption'],
                        "apIPAddress": ap['IPAddress'],
                        "switchPort": switch_interface['PortName'],
                        "switchName": switch_interface['SwitchName'],
                        "switchIPAddress": switch_interface['SwitchIP'],
                        "problem": "AP unreachable but ethernet link up, vlan correct",
                        "solution": ""
                    }
                else:
                    fixVlanAPmgm(switch_interface)
                    logging.warning("Wrong VLAN {} at the switch {} with IP {}".format(
                        switch_interface['PortName'], switch_interface['SwitchName'], switch_interface['SwitchIP']))
                    dict_ap = {
                        "apName": ap['Caption'],
                        "apIPAddress": ap['IPAddress'],
                        "switchPort": switch_interface['PortName'],
                        "switchName": switch_interface['SwitchName'],
                        "switchIPAddress": switch_interface['SwitchIP'],
                        "problem": "Wrong VLAN",
                        "solution": "Moved interface to correct interface range"
                    }
            elif '0.0W' in checkPOEPower(switch_interface):
                logging.warning("No POE draw and no ethernet link but AP was connected to {} at the switch {} with IP {}".format(
                    switch_interface['PortName'], switch_interface['SwitchName'], switch_interface['SwitchIP']))

                dict_ap = {
                    "apName": ap['Caption'],
                    "apIPAddress": ap['IPAddress'],
                    "switchPort": switch_interface['PortName'],
                    "switchName": switch_interface['SwitchName'],
                    "switchIPAddress": switch_interface['SwitchIP'],
                    "poe": checkPOEPower(switch_interface),
                    "problem": "Ethernet link down and no POE",
                    "solution": "{}".format(checkCable(switch_interface))
                }
            else:
                logging.warning("Ethernet link down but POE power draw on AP connected to {} at the switch {} with IP {}".format(
                    switch_interface['PortName'], switch_interface['SwitchName'], switch_interface['SwitchIP']))
                bouncePOE(switch_interface)

                dict_ap = {
                    "apName": ap['Caption'],
                    "apIPAddress": ap['IPAddress'],
                    "switchPort": switch_interface['PortName'],
                    "switchName": switch_interface['SwitchName'],
                    "switchIPAddress": switch_interface['SwitchIP'],
                    "poe": checkPOEPower(switch_interface),
                    "problem": "Ethernet link down but POE power draw",
                    "solution": "{}".format(checkCable(switch_interface))
                }

    dict_aps.append(dict_ap)

logging.info(json.dumps(dict_aps, indent=2, default=str))

df_aps = pandas.DataFrame(data=dict_aps)
print(df_aps)

#Mail the result
# write the plain text part
text = """\
Hej
Följande accesspunkter är nere
"""
# write the HTML part
html = """\
<html>
  <body>
    <p>Hej!<br>
    <p> Följande accesspunkter är nere, en del av dem har jag löst men vissa behöver ni kolla på</p>
    <p> {} </p>
    <p> Mvh Netscripts </p>
  </body>
</html>
""".format(df_aps.to_html(index=False))
# convert both parts to MIMEText objects and add them to the MIMEMultipart message
part1 = MIMEText(text, "plain")
part2 = MIMEText(html, "html")
message.attach(part1)
message.attach(part2)
# send your email
if True:
    if dict_aps:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.sendmail(
                sender_email, receiver_email.split(','), message.as_string()
            )
    else:
        logging.info("No aps found")
else:
    pass
    #if dict_aps:
    #with smtplib.SMTP(smtp_server, smtp_port) as server:
    #server.sendmail(
    #sender_email, 'samuel.sjobergsson@molndal.se', message.as_string()
    #)
    #else:
    #logging.info("No aps found")

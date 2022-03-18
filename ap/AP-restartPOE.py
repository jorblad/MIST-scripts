import requests
#Used to get data from solarwinds
import orionsdk
import yaml
import json
import pandas
import re
import time
#Used to work with xml from the switches
import xmltodict

#Email imports
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

#Used for communicating with the switches
from scrapli import Scrapli

#open configuration file for use in the script
with open('/opt/scripts/ap/config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

#Log to a specified file
import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='/opt/scripts/logs/APTroubleshoot.log', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')

#set variables for easy access to settings
switch_username = config['switch']['username']
switch_password = config['switch']['password']
solarwinds_username = config['solarwinds']['username']
solarwinds_password = config['solarwinds']['password']
solarwinds_certificate = config['solarwinds']['certificate_file']

#Regex
#Regex to get only interface and interface status in different groups
regex_interface_status = 'ge-\d+\/\d+\/(?P<interface>\d+|\d+.\d)\s+(?P<admin>up|down) \s+(?P<link>up|down)'
#Regex to get short interface name
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

#Function to convert long interface name to short
def interfaceShort(switch_interface_name):
    switch_interface_name_short = (
        re.search(regex_interface_short, switch_interface_name).group('interface_short'))
    return switch_interface_name_short

#Function to bounce POE on a switchport
def bouncePOE(switch_interface):
    #create device object for scrapli
    device = {
        "host": switch_interface['SwitchIP'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch_interface['SwitchName'], switch_interface['SwitchIP']))
    #Connect to the switch
    conn = Scrapli(**device)
    conn.open()
    #Disable POE on the interface
    response = conn.send_config("set poe interface {} disable".format(
        switch_interface['PortName']))
    #Commit conirmed to roll back to activated POE interface again
    response = conn.send_config("commit confirmed 2 comment netscripts01")
    logging.info(response.elapsed_time)
    logging.info(response.result)
    #Disconnect from switch
    conn.close()

#Function to check whether switchport is POE 0.5W or not
#This is because we have a few Cisco AP:s that spontanealsy dies and then uses only 0.5W of POE-power
def checkPOEPort(switch_interface):
    #create device object for scrapli
    device = {
        "host": switch_interface['SwitchIP'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch_interface['SwitchName'], switch_interface['SwitchIP']))
    #Connecting to switch
    conn = Scrapli(**device)
    conn.open()
    #Get POE status for the interface
    response = conn.send_command(
        "show poe interface {}".format(switch_interface['PortName']))
    if '0.5W' in response.result:
        logging.info('AP-needs {} reboot'.format(ap['Caption']))
        return True
    else:
        logging.info("Another fault troubleshoot {} connected to {} on {} with IP {}".format(
            ap['Caption'], switch_interface['PortName'], switch_interface['SwitchName'], switch_interface['SwitchIP']))
        return False

#Check if there is any POE power and if so how much
def checkPOEPower(switch_interface):
    #create device object for scrapli
    device = {
        "host": switch_interface['SwitchIP'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch_interface['SwitchName'], switch_interface['SwitchIP']))
    #Connecting to switch
    conn = Scrapli(**device)
    conn.open()

    #If the switch supports POE it wil get a result if not it won´t work and throw a exception
    try:
        #Get POE Power of the interface
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

#Check if there is linkon the interface
def checkLink(switch_interface):
    #create device object for scrapli
    device = {
        "host": switch_interface['SwitchIP'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch_interface['SwitchName'], switch_interface['SwitchIP']))
    #Connecting to switch
    conn = Scrapli(**device)
    conn.open()
    #Get interface status
    response = conn.send_command(
        "show interfaces terse {}".format(switch_interface['PortName']))
    #Get interface status from the result
    interface_status = re.search(regex_interface_status, response.result)
    if 'up' in interface_status.group('link'):
        try:
            logging.info("AP {} has ethernet link {} connected to {} on {} with IP {}".format(
                ap['Caption'], switch_interface['PortName'], switch_interface['SwitchName'], switch_interface['SwitchIP']))

            return True
        except:
            logging.info("AP has link but is down")
            return True
    else:
        logging.info("AP has no ethernet link {} connected to {} on {} with IP {}".format(
            ap['Caption'], switch_interface['PortName'], switch_interface['SwitchName'], switch_interface['SwitchIP']))

        return False

#Do a TDR-check of the cable
def checkCable(switch_interface):
    #create device object for scrapli
    device = {
        "host": switch_interface['SwitchIP'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    try:
        logging.info("Logging in to switch {} with IP {}".format(
            switch_interface['SwitchName'], switch_interface['SwitchIP']))
        #Connect to the switch
        conn = Scrapli(**device)
        conn.open()
        #Initialize interface test-status
        interface_test_status = 'Started'
        #Start interface test
        response = conn.send_command(
            "request diagnostics tdr start interface {}".format(switch_interface['PortName']))
        #Get switch hardware
        response = conn.send_command("show chassis hardware | display xml")
        switch_hardware_xml = str(response.result)
        #Convert switch xml to dict
        response_dict = xmltodict.parse(switch_hardware_xml)
        #convert dict to json to sanitize
        response_json = json.dumps(response_dict)
        #Get switch_hardware
        switch_hardware = json.loads(response_json)[
            'rpc-reply']['chassis-inventory']['chassis']
        switch_model = switch_hardware['description']
        #Base commands on switch model
        if "EX2300" in switch_model:
            #As long as the status is Started check for status
            while interface_test_status == 'Started':
                response = conn.send_command(
                    "show diagnostics tdr interface {} | display xml".format(switch_interface['PortName']))
                response_dict = xmltodict.parse(response.result)
                response_json = json.dumps(response_dict)
                interface_tdr = json.loads(response_json)
                interface_test_status = interface_tdr[
                    'rpc-reply']['vct']['vct-interface-information-detail']['vct-interface-test-status']
        elif "EX2200" in switch_model:
            #As long as the status is Started check for status
            while interface_test_status == 'Started':
                response = conn.send_command(
                    "show diagnostics tdr interface {} | display xml".format(switch_interface['PortName']))
                response_dict = xmltodict.parse(response.result)
                response_json = json.dumps(response_dict)
                interface_tdr = json.loads(response_json)
                interface_test_status = interface_tdr[
                    'rpc-reply']['tdr']['interface-information-detail']['interface-test-status']
        #Get the result from the test
        response = conn.send_command(
            "show diagnostics tdr interface {}".format(switch_interface['PortName']))
        return response.result
    except:
        return response.result


#Check if the interface is on the correct vlan
def checkVlanAPmgm(switch_interface):
    #create device object for scrapli
    device = {
        "host": switch_interface['SwitchIP'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch_interface['SwitchName'], switch_interface['SwitchIP']))
    #Connec to the switch
    conn = Scrapli(**device)
    conn.open()
    #Get switch model
    response = conn.send_command("show chassis hardware | display xml")
    response_dict = xmltodict.parse(response.result)
    response_json = json.dumps(response_dict)
    switch_hardware = json.loads(response_json)[
        'rpc-reply']['chassis-inventory']['chassis']
    switch_model = switch_hardware['description']

    try:
        #Base commands on switch model
        if "EX2300" in switch_model:
            #Get interface vlans
            response = conn.send_command(
                "show ethernet-switching interface {} | display xml".format(switch_interface['PortName']))
            response_dict = xmltodict.parse(response.result)
            response_json = json.dumps(response_dict)
            interface_vlans = json.loads(response_json)
            interface_vlan_apmgm = interface_vlans['rpc-reply']['l2ng-l2ald-iff-interface-information'][
                'l2ng-l2ald-iff-interface-entry']['l2ng-l2ald-iff-interface-entry']
            #Go through  interface_vlan and look for apmgm untagged
            for interface_vlan in interface_vlan_apmgm:
                if interface_vlan['l2iff-interface-vlan-name'] == 'apmgm' and interface_vlan['l2iff-interface-vlan-member-tagness'] == 'untagged':
                    return True
            #If there is no apmgm-vlan untagged then the port is wrongly configured
            return False
        elif "EX2200" in switch_model:
            #Get interface vlans
            response = conn.send_command(
                "show ethernet-switching interface {} | display xml".format(switch_interface['PortName']))
            response_dict = xmltodict.parse(response.result)
            response_json = json.dumps(response_dict)
            interface_vlans = json.loads(response_json)
            interface_vlan_apmgm = interface_vlans['rpc-reply']['switching-interface-information'][
                'interface']['interface-vlan-member-list']
            #Go through  interface_vlan and look for apmgm untagged
            if isinstance(interface_vlan_apmgm, list):
                for interface_vlan_member in interface_vlan_apmgm:
                    if interface_vlan_member['interface-vlan-member']['interface-vlan-name'] == 'apmgm' and interface_vlan_member['interface-vlan-member']['interface-vlan-member-tagness'] == 'untagged':
                        return True
            else:
                if interface_vlan_apmgm['interface-vlan-member']['interface-vlan-name'] == 'apmgm' and interface_vlan_apmgm['interface-vlan-member']['interface-vlan-member-tagness'] == 'untagged':
                    return True
    except:
        #If there is no apmgm-vlan untagged then the port is wrongly configured
        return False

#Move interface to correct vlan
def fixVlanAPmgm(switch_interface):
    #create device object for scrapli
    device = {
        "host": switch_interface['SwitchIP'],
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {} with IP {}".format(
        switch_interface['SwitchName'], switch_interface['SwitchIP']))
    #Connecting to the switch
    conn = Scrapli(**device)
    conn.open()
    #Get switch model
    response = conn.send_command("show chassis hardware | display xml")
    response_dict = xmltodict.parse(response.result)
    response_json = json.dumps(response_dict)
    switch_hardware = json.loads(response_json)[
        'rpc-reply']['chassis-inventory']['chassis']
    switch_model = switch_hardware['description']
    #Base commands of switch model
    if 'EX2300' in switch_model:
        #Show interface vlan
        response = conn.send_command(
            "show ethernet-switching interface {} | display xml".format(switch_interface['PortName']))
        response_dict = xmltodict.parse(response.result)
        response_json = json.dumps(response_dict)
        interface_vlans = json.loads(response_json)
        interface_vlan_apmgm = interface_vlans['rpc-reply']['l2ng-l2ald-iff-interface-information'][
            'l2ng-l2ald-iff-interface-entry']['l2ng-l2ald-iff-interface-entry']
        #If nothing else guess the interface is downlink
        switch_interface_vlan = 'downlink'
        #See what vlan is untagged
        for interface_vlan in interface_vlan_apmgm:
            if interface_vlan['l2iff-interface-vlan-member-tagness'] == 'untagged':
                switch_interface_vlan = interface_vlan['l2iff-interface-vlan-name']
    elif 'EX2200' in switch_model:
        #Show interface vlan
        response = conn.send_command(
            "show ethernet-switching interface {} | display xml".format(switch_interface['PortName']))
        response_dict = xmltodict.parse(response.result)
        response_json = json.dumps(response_dict)
        interface_vlans = json.loads(response_json)
        interface_vlan_apmgm = interface_vlans['rpc-reply']['switching-interface-information'][
            'interface']['interface-vlan-member-list']['interface-vlan-member']
        try:
            #If it works it means there is only one vlan on the port
            switch_interface_vlan = interface_vlan_apmgm['interface-vlan-name']
        except:
            #otherwise it is a downlink
            switch_interface_vlan = 'downlink'
    #Set interface as member in ap interface-range
    response = conn.send_config(
        "set interfaces interface-range ap member {}".format(
            switch_interface['PortName']))
    #Delete interface as member from the former interface-range
    response = conn.send_config(
        "delete interfaces interface-range {} member {}".format(
            switch_interface_vlan, switch_interface['PortName']))
    #Commit the change with a describing comment
    response = conn.send_config(
        'commit comment "fel vlan till ap"')

#Connect to Solarwinds
session = requests.Session()
session.timeout = 30  # Set your timeout in seconds
logging.info("Connecting to Solarwinds")
swis = orionsdk.SwisClient("SolarWinds-Orion", solarwinds_username,
                           solarwinds_password, verify=False, session=session)
logging.info("Getting accesspoints that don´t work")
#Query for finding accesspoint that has the satus offline
nodes = swis.query(
    "SELECT NodeID, Caption, IPAddress, Status FROM Orion.Nodes WHERE Caption LIKE 'ap-%' AND Status LIKE 2")
#Convert result to a list
aps = nodes['results']
#Create a empty list for the accesspoints
dict_aps = []
#Go through all accesspoints in the list and find where they have been connected
for ap in aps:
    #Initializing port_nodes
    port_nodes = ''
    #Query for getting the interfaces that have been connected to the accesspoint
    port_nodes = swis.query(
        "SELECT DISTINCT TOP 100 Port.Name AS PortName, Nodes.Caption AS SwitchName, Nodes.IPAddress AS SwitchIP, Nodes.Status AS SwitchStatus, PortToEndpointHistory.ConnectionType FROM Orion.UDT.IPAddressHistory INNER JOIN Orion.UDT.PortToEndpointHistory ON IPAddressHistory.EndpointID=PortToEndpointHistory.EndpointID INNER JOIN Orion.UDT.Port ON PortToEndpointHistory.PortID=Port.PortID INNER JOIN Orion.Nodes ON Port.NodeID=Nodes.NodeID WHERE IPAddressHistory.IPAddress LIKE '{}' AND SwitchName LIKE 'swa-%' AND PortName LIKE 'ge-%/0/%' AND PortToEndpointHistory.ConnectionType LIKE '1'".format(ap['IPAddress']))
    switch_interfaces = port_nodes['results']
    #If we dont find a switchport add that to the summary
    if not switch_interfaces:

        logging.info(
            "Can't find switch-interface for {}".format(ap['Caption']))
        #Dict for the ap with information
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
        #Check which port is most likely tha closest to the ap
        for switch_interface in switch_interfaces:
            #Set portname to the short interface name so that all are the same
            switch_interface['PortName'] = interfaceShort(
                switch_interface['PortName'])
            #initialize dict ap
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

            #Check POE 0.5W and if that is the problem bounce POE on the port
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
            #Check if the port is linking
            elif checkLink(switch_interface):
                #If port is linking check if it is on correct vlan
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
                    #If vlan isn´t correct fix it
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
            #AP port with no link and no powerdraw
            elif '0.0W' in checkPOEPower(switch_interface):
                logging.warning("No POE draw and no ethernet link but AP was connected to {} at the switch {} with IP {}".format(
                    switch_interface['PortName'], switch_interface['SwitchName'], switch_interface['SwitchIP']))
                #Check cable and add to the report
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
                #Do a cablecheck and bounce POE to see if that gives more information
                cable_check = checkCable(switch_interface)
                bouncePOE(switch_interface)

                dict_ap = {
                    "apName": ap['Caption'],
                    "apIPAddress": ap['IPAddress'],
                    "switchPort": switch_interface['PortName'],
                    "switchName": switch_interface['SwitchName'],
                    "switchIPAddress": switch_interface['SwitchIP'],
                    "poe": checkPOEPower(switch_interface),
                    "problem": "Ethernet link down but POE power draw",
                    "solution": "{}".format(cable_check)
                }
    #Add dict about AP to list
    dict_aps.append(dict_ap)

logging.info(json.dumps(dict_aps, indent=2, default=str))

#Turn dict of AP:s to dataframe for readability in email
df_aps = pandas.DataFrame(data=dict_aps)


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
#Hardcoded if for simply disabling email for testing
if True:
    #if there are any AP:s down send email
    if dict_aps:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.sendmail(
                sender_email, receiver_email.split(','), message.as_string()
            )
    else:
        logging.info("No aps found")


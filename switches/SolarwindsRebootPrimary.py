import requests
import orionsdk
import yaml

from scrapli import Scrapli

with open('/opt/scripts/switches/config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', filename='/opt/scripts/logs/rebootPrimary.log', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')

switch_username = config['switch']['username']
switch_password = config['switch']['password']
solarwinds_username = config['solarwinds']['username']
solarwinds_password = config['solarwinds']['password']
solarwinds_certificate = config['solarwinds']['certificate_file']


def rebootPrimary(switch_ip):
    device = {
        "host": switch_ip,
        "auth_username": switch_username,
        "auth_password": switch_password,
        "auth_strict_key": False,
        "platform": "juniper_junos"
    }
    logging.info("Logging in to switch {}".format(switch_ip))
    conn = Scrapli(**device)
    conn.open()
    response = conn.send_command("request system configuration rescue save")
    response = conn.send_interactive(
        [
            ("request system reboot slice alternate media internal at 22",
             "Reboot the system ", False),
            ("yes", "", False)
        ]
    )
    logging.info(response.elapsed_time)
    logging.info(response.result)
    if 'Shutdown at' in response.result:
        return True
    else:
        return False
    conn.close()



session = requests.Session()
session.timeout = 30  # Set your timeout in seconds
logging.info("Connecting to Solarwinds")
swis = orionsdk.SwisClient("SolarWinds-Orion", solarwinds_username,
                           solarwinds_password, verify=False, session=session)
logging.info("Getting switches that need to reboot")
nodes = swis.query("SELECT NodeID, Caption, IPAddress, Status, Nodes.CustomProperties.jun_bootpart FROM Orion.Nodes WHERE Caption LIKE 'swa%' AND Nodes.CustomProperties.jun_bootpart LIKE 'backup%'")

switches = nodes['results']
logging.debug(switches)

dict_switches = {}

for switch in switches:
    if rebootPrimary(switch['IPAddress']):
        dict_switches = {
            "Switchname": switch['Caption'],
            "IP-address": switch['IPAddress'],
            "Status": "Scheduled reboot at 22:00"
        }
    else:
        dict_switches = {
            "Switchname": switch['Caption'],
            "IP-address": switch['IPAddress'],
            "Status": "Failed"
        }
logging.info(dict_switches)



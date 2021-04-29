import requests
import orionsdk
import paramiko
import yaml

with open('config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', filename='rebootPrimary.log', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')

switch_username = config['switch']['username']
switch_password = config['switch']['password']
solarwinds_username = config['solarwinds']['username']
solarwinds_password = config['solarwinds']['password']
solarwinds_certificate = config['solarwinds']['certificate_file']

def rebootPrimary(switch_ip):
    ssh = paramiko.SSHClient()

     # Load SSH host keys.
    ssh.load_system_host_keys()
    # Add SSH host key automatically if needed.
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    logging.info("Logging in to switch {}".format(switch_ip))
    try:
        ssh.connect(switch_ip, username=switch_username,
                    password=switch_password, look_for_keys=False)
    except:
        print("[!] Cannot connect to the SSH Server")
        logging.warning("[!] Cannot connect to the SSH Server {}".format(switch_ip))
        exit()

    stdin, stdout, stderr = ssh.exec_command(
        'request system configuration rescue save\n')
    print(stdout.read())
    logging.info(stdout.read())
    stdin, stdout, stderr = ssh.exec_command(
        'request system reboot slice alternate media internal at 22\n')
    print(stdout.read())
    logging.info(stdout.read())
    logging.info("Closes SSH session")
    ssh.close()


session = requests.Session()
session.timeout = 30  # Set your timeout in seconds
logging.info("Connecting to Solarwinds")
swis = orionsdk.SwisClient("SolarWinds-Orion", solarwinds_username,
                           solarwinds_password, verify=False, session=session)
logging.info("Getting switches that need to reboot")
nodes = swis.query("SELECT NodeID, Caption, IPAddress, Status, Nodes.CustomProperties.jun_bootpart FROM Orion.Nodes WHERE Caption LIKE 'swa%' AND Nodes.CustomProperties.jun_bootpart LIKE 'backup%'")

switches = nodes['results']
logging.debug(switches)
for switch in switches:
    rebootPrimary(switch['IPAddress'])




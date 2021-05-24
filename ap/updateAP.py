import requests
import json
import yaml

from datetime import datetime
from re import search

import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='/opt/scripts/logs/updateAP.log', level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')

with open('/opt/scripts/ap/config.yaml') as f:
    config = yaml.safe_load(f)

#Regex for filtering out so that we only show sites that have a shortname
# which is how we decide if a site is just for lab or a actual site
regex_sitename = config['report']['regex_sitename']
#Regex for empty json to hide sites without any accesspoints.
regex_empty = "^\[\]$"

base_url = config['mist']['base_url']
org_id = config['mist']['org_id']

mist_token = config['mist']['mist_token']
authorization = "Token {}".format(mist_token)

headers = {
    'Content-Type': 'application/json',
    'Authorization': authorization
}

sites_url = "{}/orgs/{}/sites".format(base_url, org_id)

resultssites = requests.get(sites_url, headers=headers)
sites = json.loads(resultssites.text)

software_version = input('Vilken version ska vi uppdatera till?\n')

json_update = json.dumps({
    "auto_upgrade": {
        "enabled": True,
        "version": "custom",
        "time_of_day": "02:00",
        "custom_versions": {
            "AP32": software_version,
            "AP33": software_version,
            "AP43": software_version,
            "AP43E": software_version
        },
        "day_of_week": ""
    }
})

print(json.dumps(json_update))

for site in sites:
    if search(regex_sitename, site['name']):
        print(site['name'])
        logging.info('Updating site {}'.format(site['name']))
        update_settings_url = "{}/sites/{}/setting".format(base_url, site['id'])
        result_update = requests.put(update_settings_url, data=json_update, headers=headers)
        print(json.dumps(result_update.text))


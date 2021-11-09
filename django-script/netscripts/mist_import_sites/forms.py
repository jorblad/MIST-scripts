from __future__ import nested_scopes
from sys import version
from django import forms
from django.contrib import messages
import yaml
import json
import requests
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit

import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='../logs/Mist-api.log', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')

with open('mist_import_sites/config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

# Your Mist API token goes here. Documentation: https://api.mist.com/api/v1/docs/Auth#api-token
mist_api_token = config['mist']['mist_token']

org_id = config['mist']['org_id']  # Your Organization ID goes here

base_url = config['mist']['base_url']

authorization = "Token {}".format(mist_api_token)

headers = {
    'Content-Type': 'application/json',
    'Authorization': authorization
}

class SiteForm(forms.Form):
    gatuadress = forms.CharField(label='Gatuadress', max_length=255)
    shortname = forms.CharField(label='Förkortning', max_length=4)
    popularnamn = forms.CharField(label='Populärnamn', max_length=255)
    verksamhet = forms.CharField(label='Verksamhet', max_length=4)
    postnummer = forms.CharField(label='postnummer', max_length=6)
    ekahau_file = forms.FileField(required=False)
    creation_type = forms.ChoiceField(choices=(
        ("new", "Ny site - skapa kombinerad edge och access-switch"),
        ("existing", "Förbered befintlig site för Mist"),
    ))

class UpdateMistForm(forms.Form):
    sites_url = "{}/orgs/{}/sites".format(base_url, org_id)

    resultssites = requests.get(sites_url, headers=headers)
    sites = json.loads(resultssites.text)
    site_id = sites[0]['id']
    MistFirmwareVersions = [
        'Rekomenderad', [],
        'Resterande', [],
    ]

    logging.debug(MistFirmwareVersions)
    firmware_url = "{}/sites/{}/devices/versions".format(base_url, site_id)

    result_firmwares = requests.get(firmware_url, headers=headers)
    firmwares = json.loads(result_firmwares.text)
    for firmware in firmwares:
        if firmware['model']=='AP32':
            if firmware['tag']:
                logging.debug(firmware)
                firmware_tuple = (firmware['version'], "{} {}".format(firmware['version'], firmware['tag']))
                MistFirmwareVersions[1].append(firmware_tuple)
            else:
                logging.debug(firmware)
                firmware_tuple = (firmware['version'], "{}".format(
                    firmware['version']))
                MistFirmwareVersions[3].append(firmware_tuple)

    MistFirmwareVersions = "[('Rekomenderade', {}), ('Resterande', {})]".format(MistFirmwareVersions[1], MistFirmwareVersions[3])

    MistFirmwareVersions = eval(MistFirmwareVersions)




    mist_version = forms.ChoiceField(choices=(
        MistFirmwareVersions), initial=config['mist']['config']['auto_upgrade']['custom_versions']['AP32'])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.fields['mist_version'].label = ""
        #self.helper.add_input(Submit('submit', 'Uppdatera', css_class='btn btn-primary'))
        #self.helper.use_custom_control = True




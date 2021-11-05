from __future__ import nested_scopes
from sys import version
from django import forms
from django.contrib import messages
from django.forms.forms import Form

class NewSwitch(forms.Form):
    switchnamn = forms.CharField(label='Switchnamn', max_length=255)
    gatuadress = forms.CharField(label='Gatuadress', max_length=255)
    popularnamn = forms.CharField(
        label='Populärnamn', max_length=255, required=False)
    plan = forms.CharField(label='Våningsplan', max_length=255, required=False)
    rum_nummer = forms.CharField(
        label='Rumsnummer', max_length=255, required=False)
    rum_beskrivning = forms.CharField(
        label='Rumsbeskrivning', max_length=255, required=False)
    ip_adress = forms.GenericIPAddressField(label='IP_adress')
    interface_ap = forms.CharField(max_length=255, required=False)
    interface_device = forms.CharField(max_length=255, required=False)
    interface_pub = forms.CharField(max_length=255, required=False)
    interface_klientklass1 = forms.CharField(max_length=255, required=False)
    interface_klientklass2 = forms.CharField(max_length=255, required=False)
    interface_cu_downlink = forms.CharField(max_length=255, required=False)
    interface_uplink = forms.ChoiceField(choices=(
        ("sfp", "Fiber"),
        ("ge", "Koppar"),
    ))


class NewSwcSwitch(forms.Form):
    switchnamn = forms.CharField(label='Switchnamn', max_length=255)
    gatuadress = forms.CharField(label='Gatuadress', max_length=255)
    popularnamn = forms.CharField(
        label='Populärnamn', max_length=255, required=False)
    plan = forms.CharField(label='Våningsplan', max_length=255, required=False)
    rum_nummer = forms.CharField(
        label='Rumsnummer', max_length=255, required=False)
    rum_beskrivning = forms.CharField(
        label='Rumsbeskrivning', max_length=255, required=False)
    ip_adress = forms.GenericIPAddressField(label='IP_adress')
    s_vlan = forms.CharField(max_length=255, required=False)
    interface_ap = forms.CharField(max_length=255, required=False)
    interface_device = forms.CharField(max_length=255, required=False)
    interface_pub = forms.CharField(max_length=255, required=False)
    interface_klientklass1 = forms.CharField(max_length=255, required=False)
    interface_klientklass2 = forms.CharField(max_length=255, required=False)
    interface_cu_downlink = forms.CharField(max_length=255, required=False)


class ReplaceSwitch(forms.Form):
    switchnamn = forms.CharField(label='Switchnamn', max_length=255)
    gatuadress = forms.CharField(label='Gatuadress', max_length=255)
    popularnamn = forms.CharField(
        label='Populärnamn', max_length=255, required=False)
    plan = forms.CharField(label='Våningsplan', max_length=255, required=False)
    rum_nummer = forms.CharField(
        label='Rumsnummer', max_length=255, required=False)
    rum_beskrivning = forms.CharField(
        label='Rumsbeskrivning', max_length=255, required=False)
    ip_adress = forms.GenericIPAddressField(label='IP_adress')
    interface_ap = forms.CharField(max_length=255, required=False)
    interface_device = forms.CharField(max_length=255, required=False)
    interface_pub = forms.CharField(max_length=255, required=False)
    interface_klientklass1 = forms.CharField(max_length=255, required=False)
    interface_klientklass2 = forms.CharField(max_length=255, required=False)
    interface_cu_downlink = forms.CharField(max_length=255, required=False)
    interface_uplink = forms.ChoiceField(choices=(
        ("sfp", "Fiber"),
        ("ge", "Koppar"),
    ))


class ReplaceSwcSwitch(forms.Form):
    switchnamn = forms.CharField(label='Switchnamn', max_length=255)
    gatuadress = forms.CharField(label='Gatuadress', max_length=255)
    popularnamn = forms.CharField(
        label='Populärnamn', max_length=255, required=False)
    plan = forms.CharField(label='Våningsplan', max_length=255, required=False)
    rum_nummer = forms.CharField(
        label='Rumsnummer', max_length=255, required=False)
    rum_beskrivning = forms.CharField(
        label='Rumsbeskrivning', max_length=255, required=False)
    ip_adress = forms.GenericIPAddressField(label='IP_adress')
    s_vlan = forms.CharField(max_length=255, required=False)
    interface_ap = forms.CharField(max_length=255, required=False)
    interface_device = forms.CharField(max_length=255, required=False)
    interface_pub = forms.CharField(max_length=255, required=False)
    interface_klientklass1 = forms.CharField(max_length=255, required=False)
    interface_klientklass2 = forms.CharField(max_length=255, required=False)
    interface_cu_downlink = forms.CharField(max_length=255, required=False)


class ConfigureSwitch(forms.Form):
    switchnamn = forms.CharField(label='Switchnamn', max_length=255)
    gatuadress = forms.CharField(label='Gatuadress', max_length=255)
    popularnamn = forms.CharField(
        label='Populärnamn', max_length=255, required=False)
    plan = forms.CharField(label='Våningsplan', max_length=255, required=False)
    rum_nummer = forms.CharField(
        label='Rumsnummer', max_length=255, required=False)
    rum_beskrivning = forms.CharField(
        label='Rumsbeskrivning', max_length=255, required=False)
    ip_adress = forms.GenericIPAddressField(label='IP_adress')


class SearchSwitch(forms.Form):
    switchnamn = forms.CharField(label='Switchnamn', max_length=255)


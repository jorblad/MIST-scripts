from django.contrib import admin

from .models import ShodanSettings, ShodanIPSubnet, ShodanEmailReceiver

admin.site.register(ShodanSettings)
admin.site.register(ShodanIPSubnet)
admin.site.register(ShodanEmailReceiver)

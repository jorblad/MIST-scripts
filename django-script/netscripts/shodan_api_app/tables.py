import django_tables2 as tables
from .models import ShodanResult

class ShodanTable(tables.Table):
    class Meta:
        model = ShodanResult
        template_name = "django_tables2/bootstrap4.html"
        fields = ("ip_adress", "port_number", "organisation", "hostname", "operating_system", "transport", "vulnerabilities", "last_changed", )
        attrs = {
            "class": "table table-striped",
            "thead" : {
                "class": "table-light",
            },
        }

    def render_vulnerabilities(self, value):
        if value == "['n']":
            return ""
        else:
            return "<%s>" % value

    def render_hostname(self, value):
        if value == "[]":
            return ""
        else:
            return "%s" % value

import django_tables2 as tables
from .models import ShodanResult

#Define the table for shodan data
class ShodanTable(tables.Table):
    class Meta:
        model = ShodanResult
        #Using djangotemplates bootstrap table
        template_name = "django_tables2/bootstrap4.html"
        #Include fields
        fields = ("ip_adress", "port_number", "organisation", "hostname", "operating_system", "transport", "vulnerabilities", "last_changed", )
        #How should the table behave
        attrs = {
            "class": "table table-striped",
            "thead" : {
                "class": "table-light",
            },
        }
    #How should vulnerabilities be shown
    def render_vulnerabilities(self, value):
        if value == "['n']":
            return ""
        else:
            return "<%s>" % value
    #How should hostnames be shown
    def render_hostname(self, value):
        if value == "[]":
            return ""
        else:
            return "%s" % value

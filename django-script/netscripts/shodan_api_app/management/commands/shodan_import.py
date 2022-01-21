from django.core.management.base import BaseCommand, CommandError

import sys
import shodan
import time
import ipaddress
import pandas
from shodan_api_app.models import ShodanResult, ShodanSettings, ShodanIPSubnet, ShodanEmailReceiver

from django.core.mail import send_mail

import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='../logs/ShodanImport.log', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')

class Command(BaseCommand):
    args = ''
    help = 'import results from shodan'

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            '--manual',
            action='store_true',
            help='Manually triggering shodan update',
        )




    def handle(self, *args, **options):
        settings = ShodanSettings.load()
        shodan_subnet = ShodanIPSubnet.objects.all().values_list('ip_subnet', flat=True)
        subnets = list(shodan_subnet)
        SHODAN_API_KEY = settings.shodan_api
        shodan_email_receivers = list(
            ShodanEmailReceiver.objects.all().values_list('email_adress', flat=True))

        ShodanResult.objects.all().delete()
        dict_vulns = []

        for subnet in subnets:

            query = "net:" + str(subnet)

            counter = 0
            limit = 1500

            try:
                api = shodan.Shodan(SHODAN_API_KEY)
                results = api.search(query)

                for host in api.search_cursor(query):
                    try:
                        host_to_db = ShodanResult()
                        host_to_db.ip_adress = host['ip_str']
                        host_to_db.port_number = host['port']
                        host_to_db.organisation = host.get('org', 'n')
                        host_to_db.hostname = list(host.get('hostnames', 'n'))
                        host_to_db.operating_system = host.get('os', 'n')
                        host_to_db.transport = host.get('transport', 'n')
                        host_to_db.vulnerabilities = list(host.get('vulns', 'n'))
                        host_to_db.save()

                        if list(host.get('vulns', '')):
                            dict_vuln = {
                                "ip_adress": host['ip_str'],
                                "port_number": host['port'],
                                "organisation": host.get('org', 'n'),
                                "hostname": list(host.get('hostnames', 'n')),
                                "operating_system": host.get('os', 'n'),
                                "transport": host.get('transport', 'n'),
                                "vulnerabilities": list(host.get('vulns', ''))
                            }

                            dict_vulns.append(dict_vuln)


                    except KeyError:
                        print("{};{}".format(host['ip_str'], host['port']))

                    counter += 1
                    if counter >= limit:
                        break

                print(dict_vulns)

            except:
                raise

        df_vulns = pandas.DataFrame(data=dict_vulns)
        text = """\
        Hej
        Följande sårbarheter är hittade
        """


        # write the HTML part
        html = """\
        <html>
        <body>
            <p>Hej!<br>
            <p> Följande sårbarheter är hittade vill du se alla öppna portar kan du kolla det på <a href="https://netscripts.mk.se/shodan/">netscripts.mk.se/shodan/</a></p>
            <p> {} </p>
            <p> Mvh Netscripts </p>
        </body>
        </html>
        """.format(df_vulns.to_html(index=False))
        if options['manual']:
            pass
        else:
            if dict_vulns:
                send_mail('Shodan sårbarheter', text, settings.from_mail,
                        shodan_email_receivers, html_message=html)


        time.sleep(1)

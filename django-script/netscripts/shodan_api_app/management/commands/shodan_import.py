#Django imports
from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail

#Other imports
import sys
import shodan # Shodan api import
import time
import ipaddress  # Functions to work with IP-adresses in a easy way
import pandas #Work with tables
#Include models for settings and data
from shodan_api_app.models import ShodanResult, ShodanSettings, ShodanIPSubnet, ShodanEmailReceiver


### This script is triggered either via cron or by pressing update on the page ###

#Logging
import logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='../logs/ShodanImport.log', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')

#Tha class for importing shodan data
class Command(BaseCommand):
    args = ''
    help = 'import results from shodan'
    #What arguments are possible
    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            '--manual',
            action='store_true',
            help='Manually triggering shodan update',
        )



    #The updating function
    def handle(self, *args, **options):
        settings = ShodanSettings.load()
        shodan_subnet = ShodanIPSubnet.objects.all().values_list('ip_subnet', flat=True)
        subnets = list(shodan_subnet)
        SHODAN_API_KEY = settings.shodan_api
        shodan_email_receivers = list(
            ShodanEmailReceiver.objects.all().values_list('email_adress', flat=True))
        #Clear the table holding previous results
        ShodanResult.objects.all().delete()
        dict_vulns = []
        #Loop through subnets defined in settings
        for subnet in subnets:

            query = "net:" + str(subnet)

            counter = 0
            limit = 1500
            #Connect to Shodan API
            try:
                api = shodan.Shodan(SHODAN_API_KEY)
                results = api.search(query)
                #Adding the new data to the table
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

                        #If there are any vulnerabilities save those to a separate dict for emailing purposes
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
        #Make a datframe of vulnerabilities for the email
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
        #Check argument to not send email if updated manually
        if options['manual']:
            pass
        else:
            if dict_vulns:
                send_mail('Shodan sårbarheter', text, settings.from_mail,
                        shodan_email_receivers, html_message=html)


        time.sleep(1)

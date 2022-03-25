import datetime

from django.db import models
from django.utils import timezone

#Singleton model for storing configuration i django
class SingletonModel(models.Model):

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super(SingletonModel, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

#The model that holds the shodan data
class ShodanResult(models.Model):
    ip_adress = models.GenericIPAddressField(verbose_name="IP-adress")
    port_number = models.SmallIntegerField(verbose_name="Port")
    organisation = models.CharField(max_length=200, blank=True, null=True, verbose_name="Organisation")
    hostname = models.CharField(max_length=400, blank=True, null=True, verbose_name="Hostname")
    operating_system = models.CharField(max_length=200, blank=True, null=True, verbose_name="OS")
    transport = models.CharField(max_length=10, blank=True, null=True, verbose_name="Transport")
    vulnerabilities = models.CharField(max_length=400, blank=True, null=True, verbose_name="Sårbarheter")
    last_changed = models.DateTimeField(auto_now=True, verbose_name="Senast uppdaterad")
    #How should the object present itself
    def __str__(self):
        return "{}:{} Vulnerabilities: {}".format(self.ip_adress, self.port_number, self.vulnerabilities)
    #How old is the data
    def was_published_recently(self):
        return self.pub_date >= timezone.now() - datetime.timedelta(days=1)

#Class for storing the settings in shodan
class ShodanSettings(SingletonModel):
    shodan_api = models.CharField(max_length=255, verbose_name='Shodan API nyckel')
    from_mail = models.EmailField(verbose_name='skicka epost från')
    smtp_server = models.CharField(max_length=255, verbose_name='SMTP-server')

    def __str__(self):
        return "Shodan Settings"
    class Meta:
        verbose_name = 'Inställningar'
#Controling how IP subnets should behave in shodan settings
class ShodanIPSubnet(models.Model):
    ip_subnet = models.CharField(max_length=50, verbose_name='IP-subnät')

    def __str__(self):
        return "{}".format(self.ip_subnet)

    class Meta:
        verbose_name = 'Shodan Subnät'
#Define how shodan email receivers should behave
class ShodanEmailReceiver(models.Model):
    email_adress  = models.EmailField(verbose_name='Epost-address')

    def __str__(self):
        return "{}".format(self.email_adress)

    class Meta:
        verbose_name = 'Epost-mottagare'


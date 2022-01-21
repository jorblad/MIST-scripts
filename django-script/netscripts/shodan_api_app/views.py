from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.views.generic.list import ListView
from django_tables2 import SingleTableView
from django.core.management import call_command
from .models import ShodanResult
from .tables import ShodanTable



class IndexView(SingleTableView):
    template_name = 'shodan_api_app/index.html'
    model = ShodanResult
    table_class = ShodanTable
    SingleTableView.table_pagination = False


def UpdateView(request):
    call_command('shodan_import', '--manual')
    return redirect('/shodan/')


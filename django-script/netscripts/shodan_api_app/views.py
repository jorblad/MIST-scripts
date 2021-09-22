from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import generic
from django.views.generic.list import ListView
from django_tables2 import SingleTableView
from .models import ShodanResult
from .tables import ShodanTable


class IndexView(SingleTableView):
    template_name = 'shodan_api_app/index.html'
    model = ShodanResult
    table_class = ShodanTable
    SingleTableView.table_pagination = False


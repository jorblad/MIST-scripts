from django.urls import path
from django.contrib import admin

from . import views


app_name = 'shodan_api_app'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index')
]


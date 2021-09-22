from django.urls import path
from django.contrib import admin


from . import views


app_name = 'switches'

urlpatterns = [
    path('', views.index, name='index'),
    path("new_switch/", views.new_switch, name='new_switch'),
    path("search_switch/", views.search_switch, name='search_switch'),
    path("replace_switch/", views.replace_switch, name='replace_switch'),
    path("configure_switch/", views.configure_switch, name='configure_switch'),
]

from django.urls import path
from django.contrib import admin


from . import views


app_name = 'mist_import_site'

urlpatterns = [
    path('', views.index, name='index'),
    path("new_site/", views.new_site, name='new_site'),
    path("update/", views.update_mist_gui, name='update'),
]

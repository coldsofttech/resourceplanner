from django.urls import path

from . import views

urlpatterns = [
    path('',        views.howto_index, name='howto-index'),
    path('ai/',     views.howto_ai,    name='howto-ai'),
    path('jira/',   views.howto_jira,  name='howto-jira'),
    path('sso/',    views.howto_sso,   name='howto-sso'),
    path('email/',  views.howto_email, name='howto-email'),
    path('jobs/',   views.howto_jobs,  name='howto-jobs'),
    path('api/',    views.howto_api,   name='howto-api'),
]

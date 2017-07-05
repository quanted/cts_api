#  https://docs.djangoproject.com/en/1.6/intro/tutorial03/
from django.conf.urls import url
# from django.contrib import admin
# admin.autodiscover()
from . import cts_rest
from . import views


# All view functions here must be in '/views/views.py'
# path: serverLocation/jchem/...

# todo: use cts_api.views for every endpoint, which calls cts_rest

urlpatterns = [
	url(r'^$', cts_rest.showSwaggerPage),
	url(r'^swag/?$', views.getSwaggerJsonContent),

	# chemical-based urls
	url(r'^molecule/?$', cts_rest.getChemicalEditorData),

	# calc-based urls
	url(r'^(?P<calc>.*?)/inputs/?$', views.getCalcInputs),
	url(r'^(?P<calc>.*?)/run/?$', views.runCalc),
	url(r'^(?P<endpoint>.*?)/?$', views.getCalcEndpoints),
]

# # 404 Error view (file not found)
# handler404 = 'views.misc.fileNotFound'
# # 500 Error view (server error)
# handler500 = 'views.misc.fileNotFound'
# # 403 Error view (forbidden)
# handler403 = 'views.misc.fileNotFound'


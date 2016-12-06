#  https://docs.djangoproject.com/en/1.6/intro/tutorial03/
from django.conf.urls import url
# from django.contrib import admin
# admin.autodiscover()
from cts_api import cts_rest
from cts_api import views


# All view functions here must be in '/views/views.py'
# path: serverLocation/jchem/...

# todo: use cts_api.views for every endpoint, which calls cts_rest

urlpatterns = [
	# (r'^/?$', 'views.getCTSEndpoints'),
	url(r'^$', cts_rest.showSwaggerPage),
	url(r'^swag/?$', views.getSwaggerJsonContent),
	# url(r'^docs/?$', cts_rest.showSwaggerPage),

	url(r'^molecule/?$', cts_rest.getChemicalEditorData),
	# url(r'^speciation/?$', cts_rest.getChemicalEditorData),

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


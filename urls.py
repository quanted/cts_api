#  https://docs.djangoproject.com/en/1.6/intro/tutorial03/
from django.urls import path
from . import cts_rest
from . import views

urlpatterns = [
	path('v2/', views.showSwaggerPageV2),
	path('v2/swag/', views.getSwaggerJsonContentV2),
	path('v2/<str:endpoint>/', views.getCalcEndpoints),
]

urlpatterns += [
	path('', views.showSwaggerPage),
	path('swag', views.getSwaggerJsonContent),
	path('molecule', cts_rest.getChemicalEditorData),
	path('<str:calc>/inputs', views.getCalcInputs),
	path('<str:calc>/run', views.runCalc),
	path('<str:endpoint>', views.getCalcEndpoints),
]

# # 404 Error view (file not found)
# handler404 = 'views.misc.fileNotFound'
# # 500 Error view (server error)
# handler500 = 'views.misc.fileNotFound'
# # 403 Error view (forbidden)
# handler403 = 'views.misc.fileNotFound'


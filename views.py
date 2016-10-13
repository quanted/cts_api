"""
Calls CTS REST classes, functions linked to
CTS REST URLs - Swagger UI
"""

from REST import cts_rest
from django.http import HttpRequest, HttpResponse
import json
from django.conf import settings
import logging
import os

root_path = os.path.abspath(os.path.dirname(__file__))

logging.warning("project root {}".format(root_path))

def getSwaggerJsonContent(request):
	"""
	Opens up swagger.json content
	"""
	swag = open(root_path + '/static/cts_api/swagger.json', 'r').read()
	swag_filtered = swag.replace('\n', '').strip()
	swag_obj = json.loads(swag_filtered)
	response = HttpResponse()
	response.write(json.dumps(swag_obj))
	return response


def getCTSEndpoints(request):
	"""
	CTS REST calculator endpoints
	"""
	cts_obj = cts_rest.CTS_REST()
	return cts_obj.getCTSREST()


def getCalcEndpoints(request, endpoint=None):

	cts_obj = cts_rest.CTS_REST()

	if not endpoint in cts_obj.endpoints:
		return HttpResponse(json.dumps({'error': "endpoint not recognized"}), content_type='application/json')		
	else:
		return cts_rest.CTS_REST().getCalcEndpoints(endpoint)


def getCalcInputs(request, calc=None):

	request_params = json.loads(request.body)

	prop, chemical = None, None

	if 'prop' in request_params:
		prop = request_params['prop']

	if 'chemical' in request_params:
		chemical = request_params['chemical']

	try:
		return cts_rest.CTS_REST().getCalcInputs(chemical, calc, prop)
	except Exception as e:
		return HttpResponse(json.dumps({'error': "{}".format(e)}), content_type='application/json')


def runCalc(request, calc=None):

	request_params = json.loads(request.body)
	calc_request = HttpRequest()
	calc_request.POST = request_params

	try:
		return cts_rest.CTS_REST().runCalc(calc, calc_request)
	except Exception as e:
		logging.warning("~~~ exception occurring at cts_api views runCalc!")
		return HttpResponse(json.dumps({'error': "{}".format(e)}), content_type='application/json')
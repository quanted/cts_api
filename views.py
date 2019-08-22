"""
Calls CTS REST classes, functions linked to
CTS REST URLs - Swagger UI
"""

from cts_app.cts_api import cts_rest
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string
from django.shortcuts import render_to_response
import json
from django.conf import settings
import logging
import os

root_path = os.path.abspath(os.path.dirname(__file__))



@csrf_exempt
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



@csrf_exempt
def showSwaggerPage(request):
	"""
	display swagger.json with swagger UI
	for CTS API docs/endpoints
	"""
	return render_to_response('cts_api/swagger_index.html')



@csrf_exempt
def showSwaggerPageV2(request):
	return render_to_response('cts_api/swagger_index_v2.html')



@csrf_exempt
def getSwaggerJsonContentV2(request):
	"""
	Opens up swagger.json content
	"""
	swag = open(root_path + '/static/cts_api/swagger-v2.json', 'r').read()
	swag_filtered = swag.replace('\n', '').strip()
	swag_obj = json.loads(swag_filtered)
	response = HttpResponse()
	response.write(json.dumps(swag_obj))
	return response



@csrf_exempt
def getCTSEndpoints(request):
	"""
	CTS REST calculator endpoints
	"""
	cts_obj = cts_rest.CTS_REST()
	return cts_obj.getCTSREST()



@csrf_exempt
def getCalcEndpoints(request, endpoint=None):

	cts_obj = cts_rest.CTS_REST()

	if not endpoint in cts_obj.endpoints:
		return HttpResponse(json.dumps({'error': "endpoint not recognized"}), content_type='application/json')		
	else:
		return cts_rest.CTS_REST().getCalcEndpoints(endpoint)



@csrf_exempt
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



@csrf_exempt
def runCalc(request, calc=None):
	request_params = smiles_backslash_fix_for_swagger(request)
	try:
		return cts_rest.CTS_REST().runCalc(calc, request_params)
	except Exception as e:
		logging.warning("~~~ exception occurring at cts_api views runCalc!")
		logging.warning("exception: {}".format(e))
		return HttpResponse(json.dumps({'error': "Error requesting data from {}".format(calc)}), content_type='application/json')



@csrf_exempt
def get_chem_info(request):

	request_post = {}
	if 'message' in request.POST:
		# accounts for request from nodejs (e.g., cts_stress)
		request_post = json.loads(request.POST.get('message'))
	else:
		request_post = request.POST

	# request_params = smiles_backslash_fix_for_swagger(request_post)
	try:
		return cts_rest.getChemicalEditorData(request_post)
	except Exception as e:
		logging.warning("cts rest exception: {}".format(e))
		return HttpResponse(json.dumps({'error": "Error getting chemical information'}))



@csrf_exempt
def cts_rest_proxy(request):
	"""
	CTS API v2 entry point.
	"""
	request_params = smiles_backslash_fix_for_swagger(request)

	if request.method == "GET":
		# handle get request (return calc info)
		try:
			return cts_rest.CTS_REST().getCalcInputs(request_params['chemical'], request_params['calc'], request_params['prop'])
		except Exception as e:
			return HttpResponse(json.dumps({'error': "{}".format(e)}), content_type='application/json')

	elif request.method == "POST":
		# run calc model
		try:
			return cts_rest.CTS_REST().runCalc(calc, request_params)
		except Exception as e:
			logging.warning("exception: {}".format(e))
			return HttpResponse(json.dumps({'error': "Error requesting data from {}".format(calc)}), content_type='application/json')



def smiles_backslash_fix_for_swagger(request):
	"""
	Workaround for backslash encoding issue that occurs when using
	Swagger API docs.
	"""
	try:
		request_body = request.body
		request_params = json.loads(request_body)
	except ValueError as ve:
		# swagger api issue with not encoding backslash in smiles properly
		logging.warning("trouble converting request body to json obj, checking for backslashes in smiles..")
		request_string = str(request_body, 'utf-8')
		if '\\' in request_string:
			logging.warning("backslash found, temporarily replacing with '_', parsing, then re-replacing..")
			request_string = request_string.replace('\\', '_')  # temp replace backslash for json parse
			request_params = json.loads(request_string)
			request_params['chemical'] = request_params['chemical'].replace('_', '\\')  # put backslash back
		else:
			request_params = request.POST

	return request_params
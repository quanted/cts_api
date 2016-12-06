"""
CTS workflow/module-oriented REST endpoints

For Chemical Editor, p-chem table, chemical speciation,
and reaction pathways.
"""

import logging
import requests
import json
import datetime
import pytz

from django.http import HttpResponse, HttpRequest
from django.template.loader import render_to_string
from django.shortcuts import render_to_response

# !!!! These are other CTS repos !!!!
# cts_calcs is a ubertool_cts submodule
# models is a part of ubertool_cts
from cts_calcs.chemaxon_cts import jchem_rest, jchem_calculator
from cts_calcs.chemaxon_cts import views as chemaxon_views
from cts_calcs.epi_cts import worker as epi_views
from cts_calcs.epi_cts import epi_calculator
from cts_calcs.measured_cts import views as measured_views
from cts_calcs.test_cts import views as test_views
from cts_calcs.sparc_cts import views as sparc_views
from smilesfilter import filterSMILES
from models.chemspec import chemspec_output
from models.gentrans import data_walks



# TODO: Consider putting these classes somewhere else, maybe even the *_models.py files!
class Molecule(object):
	"""
	Basic molecule object for CTS
	"""
	def __init__(self):

		# cts keys:
		self.chemical = ''  # initial structure from user (any chemaxon format)
		self.orig_smiles = ''  # before filtering, converted to smiles

		# chemaxon/jchem keys:
		self.smiles = ''  # post filtered smiles 
		self.formula = ''
		self.iupac = ''
		self.mass = ''
		self.structureData = ''
		self.exactMass = ''

	def createMolecule(self, chemical, orig_smiles, chem_details_response):
		"""
		Gets Molecule attributes from jchem_rest getChemDetails response
		"""
		try:
			# set attrs from jchem data:
			for key in self.__dict__.keys():
				if key != 'orig_smiles' and key != 'chemical':
					self.__setattr__(key, chem_details_response['data'][0][key])
			# set cts attrs:
			self.__setattr__('chemical', chemical)
			self.__setattr__('orig_smiles', orig_smiles)

			return self.__dict__
		except KeyError as err:
			raise err


class CTS_REST(object):
	"""
	CTS level endpoints for REST API.
	Will have subclasses for calculators and
	other CTS features, like metabolizer.
	"""
	def __init__(self):
		self.calcs = ['chemaxon', 'epi', 'test', 'sparc', 'measured']
		self.endpoints = ['cts', 'metabolizer'] + self.calcs
		self.meta_info = {
			'metaInfo': {
				'model': "cts",
				'collection': "qed",
				'modelVersion': "1.3.22",
				'description': "The Chemical Transformation System (CTS) was generated by researchers at the U.S. Enivornmental Protection Agency to provide access to a collection of physicochemical properties and reaction transformation pathways.",
				'status': '',
				'timestamp': gen_jid(),
				'url': {
					'type': "application/json",
					'href': "http://qedinternal.epa.gov/cts/rest"
				}
			},
		}
		self.links = [
			{
				'rel': "episuite",
				'type': "application/json",
				'href': "http://qedinternal.epa.gov/cts/rest/episuite"
			},
			{
				'rel': "chemaxon",
				'type': "application/json",
				'href': "http://qedinternal.epa.gov/cts/rest/chemaxon"
			},
			{
				'rel': "sparc",
				'type': "application/json",
				'href': "http://qedinternal.epa.gov/cts/rest/sparc"
			},
			{
				'rel': "test",
				'type': "application/json",
				'href': "http://qedinternal.epa.gov/cts/rest/test"
			},
			{
				'rel': "metabolizer",
				'type': "application/json",
				'href': "http://qedinternal.epa.gov/cts/rest/metabolizer"
			}
		]
		self.calc_links = [
			{
				'rel': "inputs",
				'type': "application/json",
				'href': "http://qedinternal.epa.gov/cts/rest/{}/inputs",
				'description': "ChemAxon input schema",
				'method': "POST",
			},
			{
				'rel': "outputs",
				'type': "application/json",
				'href': "http://qedinternal.epa.gov/cts/rest/{}/outputs",
				'description': "ChemAxon output schema",
				'method': "POST"
			},
			{
				'rel': "run",
				'type': "application/json",
				'href': "http://qedinternal.epa.gov/cts/rest/{}/run",
				'description': "ChemAxon estimated values",
				'method': "POST"
			}
		]
		self.pchem_inputs = ['chemical', 'calc', 'prop', 'run_type']
		self.metabolizer_inputs = ['structure', 'generationLimit', 'transformationLibraries']

	@classmethod
	def getCalcObject(self, calc):
		if calc == 'chemaxon':
			return Chemaxon_CTS_REST()
		elif calc == 'epi':
			return EPI_CTS_REST()
		elif calc == 'test':
			return TEST_CTS_REST()
		elif calc == 'sparc':
			return SPARC_CTS_REST()
		elif calc == 'measured':
			return Measured_CTS_REST()
		elif calc == 'metabolizer':
			return Metabolizer_CTS_REST()
		else:
			return None

	def getCalcLinks(self, calc):
		if calc in self.calcs:
			_links = self.calc_links
			for item in _links:
				if 'href' in item:
					item['href'] = item['href'].format(calc)  # insert calc name into href
			return _links
		else:
			return None

	def getCTSREST(self):
		_response = self.meta_info
		_response['links'] = self.links
		return HttpResponse(json.dumps(_response), content_type='application/json')

	def getCalcEndpoints(self, calc):
		_response = {}
		calc_obj = self.getCalcObject(calc)
		_response.update({
			'metaInfo': calc_obj.meta_info,
			'links': self.getCalcLinks(calc)
		})
		return HttpResponse(json.dumps(_response), content_type="application/json")

	def getCalcInputs(self, chemical, calc, prop=None):
		_response = {}
		calc_obj = self.getCalcObject(calc)
		
		_response.update({'metaInfo': calc_obj.meta_info})

		if calc in self.calcs:
			_response.update({
			'inputs': {
				'chemical': chemical,
				'prop': prop,
				'calc': calc,
				'run_type': "rest",
			}
		})
		elif calc == 'metabolizer':
			_response.update({
				'inputs': calc_obj.inputs
			})
		return HttpResponse(json.dumps(_response), content_type="application/json")

	def runCalc(self, calc, request):

		_response = {}
		_response = self.meta_info

		if calc == 'metabolizer':
			structure = request.POST.get('structure')
			gen_limit = request.POST.get('generationLimit')
			trans_libs = request.POST.get('transformationLibraries')
			metabolizer_request = {
	            'structure': structure,
	            'generationLimit': gen_limit,
	            'populationLimit': 0,
	            'likelyLimit': 0.001,
	            # 'transformationLibraries': trans_libs,
	            'excludeCondition': ""  # 'generateImages': False
	        }
			response = jchem_rest.getTransProducts(metabolizer_request)
			data_walks.j = 0
			data_walks.metID = 0
			_response.update({'data': json.loads(data_walks.recursive(response, int(gen_limit)))})
			_response.update({'request_post': request.POST})

		else:
			pchem_data = {}
			if calc == 'chemaxon':
				pchem_data = chemaxon_views.request_manager(request).content
			elif calc == 'epi':
				pchem_data = epi_views.request_manager(request).content
			elif calc == 'test':
				pchem_data = test_views.request_manager(request).content
			elif calc == 'sparc':
				pchem_data = sparc_views.request_manager(request).content
			elif calc == 'measured':
				pchem_data = measured_views.request_manager(request).content
			
			_response.update({'data': json.loads(pchem_data)})

		return HttpResponse(json.dumps(_response), content_type="application/json")



class Chemaxon_CTS_REST(CTS_REST):
	"""
	CTS REST endpoints, etc. for ChemAxon
	"""
	def __init__(self):
		self.meta_info = {
			'metaInfo': {
				'model': "chemaxon",
				'collection': "qed",
				'modelVersion': "Jchem Web Services 15.3.23.0",
				'description': "Cheminformatics software platforms, applications, and services to optimize the value of chemistry information in life science and other R&D.",
				'status': '',
				'timestamp': gen_jid(),
				'url': {
					'type': "application/json",
					'href': "http://qedinternal.epa.gov/cts/rest/chemaxon"
				},
				'props': ['water_sol', 'ion_con', 'kow_no_ph', 'kow_wph'],
				'availableProps': [
					{
						'prop': 'water_sol',
						'units': 'mg/L',
						'description': "water solubility"
					},
					{
						'prop': 'ion_con',
						'description': "pKa and pKa values"
					},
					{
						'prop': 'kow_no_ph',
						'units': "log",
						'description': "Octanol/water partition coefficient",
						'methods': ['KLOP', 'PHYS', 'VG']
					},
					{
						'prop': 'kow_wph',
						'units': "log",
						'description': "pH-dependent octanol/water partition coefficient",
						'methods': ['KLOP', 'PHYS', 'VG']
					}
				]
			}
		}

	def runChemaxon(self, request):

		# get molecular info and append to inputs object:
		# mol_info_response = json.loads(getChemicalEditorData(request).content)

		pchem_data = chemaxon_views.request_manager(request).content

		_response = self.meta_info
		_response.update({'data': json.loads(pchem_data)})

		return HttpResponse(json.dumps(_response), content_type="application/json")


class EPI_CTS_REST(CTS_REST):
	"""
	CTS REST endpoints, etc. for EPI Suite
	"""
	def __init__(self):
		self.meta_info = {
			'metaInfo': {
				'model': "epi",
				'collection': "qed",
				'modelVersion': "4.11",
				'description': "EPI Suite is a Windows-based suite of physical/chemical property and environmental fate estimation programs developed by EPA and Syracuse Research Corp. (SRC).",
				'status': '',
				'timestamp': gen_jid(),
				'url': {
					'type': "application/json",
					'href': "http://qedinternal.epa.gov/cts/rest/epi"
				},
				'availableProps': [
					{
						'prop': 'melting_point',
						'units': 'degC',
						'description': "melting point"
					},
					{
						'prop': 'boiling_point',
						'units': 'degC',
						'description': "boiling point"
					},
					{
						'prop': 'water_sol',
						'units': 'mg/L',
						'description': "water solubility"
					},
					{
						'prop': 'vapor_press',
						'units': 'mmHg',
						'description': "vapor pressure"
					},
					{
						'prop': 'henrys_law_con',
						'units': '(atm*m^3)/mol',
						'description': "henry's law constant"
					},
					{
						'prop': 'kow_no_ph',
						'units': "log",
						'description': "Octanol/water partition coefficient"
					},
					{
						'prop': 'koc',
						'units': "L/kg",
						'description': "organic carbon partition coefficient"
					}
				]
			}
		}

	def runEpi(self, request):
		chemical = request.POST.get('chemical')
		prop = request.POST.get('prop')
		ph = request.POST.get('ph')
		run_type = request.POST.get('run_type')

		# get molecular info and append to inputs object:
		# mol_info_response = json.loads(getChemicalEditorData(request).content)

		pchem_data = epi_views.request_manager(request).content

		_response = self.meta_info
		_response.update({'data': json.loads(pchem_data)})

		return HttpResponse(json.dumps(_response), content_type="application/json")


class TEST_CTS_REST(CTS_REST):
	"""
	CTS REST endpoints, etc. for EPI Suite
	"""
	def __init__(self):
		self.meta_info = {
			'metaInfo': {
				'model': "test",
				'collection': "qed",
				'modelVersion': "4.2.1",
				'description': "The Toxicity Estimation Software Tool (TEST) allows users to easily estimate the toxicity of chemicals using QSARs methodologies.",
				'status': '',
				'timestamp': gen_jid(),
				'url': {
					'type': "application/json",
					'href': "http://qedinternal.epa.gov/cts/rest/test"
				},
				'availableProps': [
					{
						'prop': 'melting_point',
						'units': 'degC',
						'description': "melting point",
						'method': "FDAMethod"
					},
					{
						'prop': 'boiling_point',
						'units': 'degC',
						'description': "boiling point",
						'method': "FDAMethod"
					},
					{
						'prop': 'water_sol',
						'units': 'mg/L',
						'description': "water solubility",
						'method': "FDAMethod"
					},
					{
						'prop': 'vapor_press',
						'units': 'mmHg',
						'description': "vapor pressure",
						'method': "FDAMethod"
					}
				]
			}
		}


class SPARC_CTS_REST(CTS_REST):
	"""
	CTS REST endpoints, etc. for EPI Suite
	"""
	def __init__(self):
		self.meta_info = {
			'metaInfo': {
				'model': "sparc",
				'collection': "qed",
				'modelVersion': "",
				'description': "SPARC Performs Automated Reasoning in Chemistry (SPARC) is a chemical property estimator developed by UGA and the US EPA",
				'status': '',
				'timestamp': gen_jid(),
				'url': {
					'type': "application/json",
					'href': "http://qedinternal.epa.gov/cts/rest/sparc"
				},
				'availableProps': [
					{
						'prop': 'boiling_point',
						'units': 'degC',
						'description': "boiling point"
					},
					{
						'prop': 'water_sol',
						'units': 'mg/L',
						'description': "water solubility"
					},
					{
						'prop': 'vapor_press',
						'units': 'mmHg',
						'description': "vapor pressure"
					},
					{
						'prop': 'mol_diss',
						'units': 'cm^2/s',
						'description': "molecular diffusivity"
					},
					{
						'prop': 'ion_con',
						'description': "pKa and pKa values"
					},
					{
						'prop': 'henrys_law_con',
						'units': '(atm*m^3)/mol',
						'description': "henry's law constant"
					},
					{
						'prop': 'kow_no_ph',
						'units': "log",
						'description': "octanol/water partition coefficient"
					},
					{
						'prop': 'kow_wph',
						'units': "log",
						'description': "pH-dependent octanol/water partition coefficient"
					}
				]
			}
		}

	def runSparc(self, request):
		chemical = request.POST.get('chemical')
		prop = request.POST.get('prop')
		ph = request.POST.get('ph')
		run_type = request.POST.get('run_type')

		# get molecular info and append to inputs object:
		# mol_info_response = json.loads(getChemicalEditorData(request).content)

		pchem_data = sparc_views.request_manager(request).content

		_response = self.meta_info
		_response.update({'data': json.loads(pchem_data)})

		return HttpResponse(json.dumps(_response), content_type="application/json")


class Measured_CTS_REST(CTS_REST):
	"""
	CTS REST endpoints, etc. for EPI Suite
	"""
	def __init__(self):
		self.meta_info = {
			'metaInfo': {
				'model': "measured",
				'collection': "qed",
				'modelVersion': "EPI Suite 4.11",
				'description': "Measured data from EPI Suite 4.11.",
				'status': '',
				'timestamp': gen_jid(),
				'url': {
					'type': "application/json",
					'href': "http://qedinternal.epa.gov/cts/rest/measured"
				},
				'availableProps': [
					{
						'prop': 'melting_point',
						'units': 'degC',
						'description': "melting point",
						'method': "FDAMethod"
					},
					{
						'prop': 'boiling_point',
						'units': 'degC',
						'description': "boiling point"
					},
					{
						'prop': 'water_sol',
						'units': 'mg/L',
						'description': "water solubility"
					},
					{
						'prop': 'vapor_press',
						'units': 'mmHg',
						'description': "vapor pressure"
					},
					{
						'prop': 'henrys_law_con',
						'units': '(atm*m^3)/mol',
						'description': "henry's law constant"
					},
					{
						'prop': 'kow_no_ph',
						'units': "log",
						'description': "octanol/water partition coefficient"
					},
					{
						'prop': 'koc',
						'units': "L/kg",
						'description': "organic carbon partition coefficient"
					}
				]
			}
		}

	def runMeasured(self, request):
		chemical = request.POST.get('chemical')
		prop = request.POST.get('prop')
		ph = request.POST.get('ph')
		run_type = request.POST.get('run_type')

		# get molecular info and append to inputs object:
		# mol_info_response = json.loads(getChemicalEditorData(request).content)

		pchem_data = measured_views.request_manager(request).content

		_response = self.meta_info
		_response.update({'data': json.loads(pchem_data)})

		return HttpResponse(json.dumps(_response), content_type="application/json")


class Metabolizer_CTS_REST(CTS_REST):
	"""
	CTS REST endpoints, etc. for EPI Suite
	"""
	def __init__(self):
		self.meta_info = {
			'metaInfo': {
				'model': "metabolizer",
				'collection': "qed",
				'modelVersion': "",
				'description': "",
				'status': '',
				'timestamp': gen_jid(),
				'url': {
					'type': "application/json",
					'href': "http://qedinternal.epa.gov/cts/rest/metabolizer"
				},

			}
		}
		self.inputs = {
			'structure': '',
			'generationLimit': 1,
			'transformationLibraries': ["hydrolysis", "abiotic_reduction", "human_biotransformation"]
		}

	def runMetabolizer(self, request):
		chemical = request.POST.get('chemical')
		prop = request.POST.get('prop')
		ph = request.POST.get('ph')
		run_type = request.POST.get('run_type')

		# get molecular info and append to inputs object:
		# mol_info_response = json.loads(getChemicalEditorData(request).content)

		pchem_data = measured_views.request_manager(request).content

		_response = self.meta_info
		_response.update({'data': json.loads(pchem_data)})

		return HttpResponse(json.dumps(_response), content_type="application/json")


def showSwaggerPage(request):
	"""
	display swagger.json with swagger UI
	for CTS API docs/endpoints
	"""
	return render_to_response('swagger_index.html')


def getChemicalEditorData(request):
	"""
	Makes call to jchem_rest for chemaxon
	data. Converts incoming structure to smiles,
	then filters smiles, and then retrieves data
	:param request:
	:return: chemical details response json
	"""
	try:

		if 'message' in request.POST:
			# receiving request from cts_stress node server..
			# todo: should generalize and not have conditional
			request_post = json.loads(request.POST.get('message'))
		else:
			request_post = request.POST


		# chemical = request.POST.get('chemical')
		chemical = request_post.get('chemical')

		response = jchem_rest.convertToSMILES({'chemical': chemical})

		logging.warning("Converted SMILES: {}".format(response))

		orig_smiles = response['structure']
		filtered_smiles = filterSMILES(orig_smiles)  # call CTS REST SMILES filter

		logging.warning("Filtered SMILES: {}".format(filtered_smiles))

		jchem_response = jchem_rest.getChemDetails({'chemical': filtered_smiles})  # get chemical details

		molecule_obj = Molecule().createMolecule(chemical, orig_smiles, jchem_response)

		wrapped_post = {
			'status': True,  # 'metadata': '',
			'data': molecule_obj,
			'request_post': request_post
		}
		json_data = json.dumps(wrapped_post)

		return HttpResponse(json_data, content_type='application/json')

	except KeyError as error:
		logging.warning(error)
		wrapped_post = {
			'status': False, 
			'error': 'Error validating chemical',
			'chemical': chemical
		}
		return HttpResponse(json.dumps(wrapped_post), content_type='application/json')
	except Exception as error:
		logging.warning(error)
		wrapped_post = {'status': False, 'error': error}
		return HttpResponse(json.dumps(wrapped_post), content_type='application/json')


# class Metabolite(Molecule):


def getChemicalSpeciationData(request):
	"""
	CTS web service endpoint for getting
	chemical speciation data through  the
	chemspec model/class
	:param request - chemspec_model
	:return: chemical speciation data response json
	"""

	try:

		chemspec_obj = chemspec_output.chemspecOutputPage(request)

		wrapped_post = {
			'status': True,  # 'metadata': '',
			'data': chemspec_obj.run_data
		}
		json_data = json.dumps(wrapped_post)

		return HttpResponse(json_data, content_type='application/json')

	except Exception as error:
		raise


def booleanize(value):
	"""
    django checkbox comes back as 'on' or 'off',
    or True/False depending on version, so this
    makes sure they're True/False
    """
	if value == 'on' or value == 'true':
		return True
	if value == 'off' or value == 'false':
		return False
	if isinstance(value, bool):
		return value


def gen_jid():
	ts = datetime.datetime.now(pytz.UTC)
	localDatetime = ts.astimezone(pytz.timezone('US/Eastern'))
	jid = localDatetime.strftime('%Y%m%d%H%M%S%f')
	return jid
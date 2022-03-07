"""
CTS workflow/module-oriented REST endpoints

For Chemical Editor, p-chem table, chemical speciation,
and reaction pathways.
"""

import logging
import json
import datetime
import pytz

from django.http import HttpResponse, HttpRequest
from django.template.loader import render_to_string

from ..cts_calcs.calculator_chemaxon import JchemCalc
from ..cts_calcs.calculator_epi import EpiCalc
from ..cts_calcs.calculator_measured import MeasuredCalc
from ..cts_calcs.calculator_test import TestWSCalc
from ..cts_calcs.calculator_sparc import SparcCalc
from ..cts_calcs.calculator_metabolizer import MetabolizerCalc
from ..cts_calcs.calculator_biotrans import BiotransCalc
from ..cts_calcs.calculator_opera import OperaCalc
from ..cts_calcs.calculator_envipath import EnvipathCalc
from ..models.chemspec import chemspec_output  # todo: have cts_calcs handle specation, sans chemspec output route
from ..cts_calcs.calculator import Calculator
from ..cts_calcs.smilesfilter import SMILESFilter
from ..cts_calcs.chemical_information import ChemInfo
from ..cts_calcs.mongodb_handler import MongoDBHandler



db_handler = MongoDBHandler()
chem_info_obj = ChemInfo()



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
		if calc == 'cts':
			return CTS_REST()
		elif calc == 'chemaxon':
			return Chemaxon_CTS_REST()
		elif calc == 'epi':
			return EPI_CTS_REST()
		elif calc == 'test':
			return TEST_CTS_REST()
		elif calc == 'testws':
			return TEST_CTS_REST()
		elif calc == 'sparc':
			return SPARC_CTS_REST()
		elif calc == 'measured':
			return Measured_CTS_REST()
		elif calc == 'metabolizer':
			return Metabolizer_CTS_REST()
		elif calc == 'opera':
			return OperaCalc()
		elif calc == 'biotrans':
			return BiotransCalc()
		elif calc == 'envipath':
			return EnvipathCalc()
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

	def runCalc(self, calc, request_dict):

		_response = {}
		calc_obj = self.getCalcObject(calc)
		_response = calc_obj.meta_info

		if calc == 'metabolizer':
			structure = request_dict.get('structure')
			gen_limit = request_dict.get('generationLimit')
			trans_libs = request_dict.get('transformationLibraries', [])

			# TODO: Add transformationLibraries key:val logic
			metabolizer_request = {
				'structure': structure,
				'generationLimit': gen_limit,
				'populationLimit': 0,
				'likelyLimit': 0.1,
				'transformationLibraries': trans_libs,
				'excludeCondition': ""  # 'generateImages': False
			}

			_request = {
				'metabolizer_post': metabolizer_request,
				'chemical': structure,
				'gen_limit': gen_limit
			}

			try:
				response = MetabolizerCalc().data_request_handler(_request)
			except Exception as e:
				logging.warning("error making data request: {}".format(e))
				raise
				
			_response.update({'data': response})

		elif calc == 'speciation':
			return getChemicalSpeciationData(request_dict)

		else:

			try:
				_orig_smiles = request_dict.get('chemical')
				_filtered_smiles = SMILESFilter().filterSMILES(_orig_smiles)
				request_dict.update({
					'orig_smiles': _orig_smiles,
					'chemical': _filtered_smiles,
				})
			except AttributeError as ae:
				# POST type is django QueryDict (most likely)
				request_dict = dict(request_dict)  # convert QueryDict to dict
				for key, val in request_dict.items():
					request_dict.update({key: val[0]})  # vals of QueryDict are lists of 1 item

				request_dict.update({
					'orig_smiles': _orig_smiles,
					'chemical': _filtered_smiles,
				})
			except Exception as e:
				logging.warning("exception in cts_rest.py runCalc: {}".format(e))
				logging.warning("skipping SMILES filter..")

			pchem_data = {}
			if calc == 'chemaxon':
				pchem_data = JchemCalc().data_request_handler(request_dict)
			elif calc == 'epi':
				_epi_calc = EpiCalc()
				pchem_data = _epi_calc.data_request_handler(request_dict)
				if not pchem_data.get('valid'):
					logging.warning("{} request error: {}".format(calc, pchem_data))
					_response_obj = {'error': pchem_data.get('data')}
					_response_obj.update(request_dict)
					return HttpResponse(json.dumps(_response_obj))
				# with updated epi, have to pick out desired prop:
				_methods_list = []
				for data_obj in pchem_data.get('data'):
					epi_prop_name = _epi_calc.propMap[request_dict['prop']]['result_key']
					if data_obj['prop'] == epi_prop_name:
						if data_obj.get('method'):
							_epi_methods = _epi_calc.propMap.get(request_dict['prop']).get('methods')
							data_obj['method'] = _epi_methods.get(data_obj['method'])  # use pchem table name for method
							_methods_list.append(data_obj)
						else:
							pchem_data['data'] = data_obj['data'] # only want request prop
						pchem_data['prop'] = request_dict['prop']  # use cts prop name
				if len(_methods_list) > 0:
					# epi water solubility has two data objects..
					pchem_data['data'] = _methods_list

			elif calc == 'testws':
				pchem_data = TestWSCalc().data_request_handler(request_dict)

			elif calc == 'sparc':
				pchem_data = SparcCalc().data_request_handler(request_dict)
				
			elif calc == 'measured':
				pchem_data = MeasuredCalc().data_request_handler(request_dict)
				if not pchem_data.get('valid'):
					logging.warning("{} request error: {}".format(calc, pchem_data))
					_response_obj = {'error': pchem_data.get('data')}
					_response_obj.update(request_dict)
					return HttpResponse(json.dumps(_response_obj))
				# with updated measured, have to pick out desired prop:
				for data_obj in pchem_data.get('data'):
					measured_prop_name = MeasuredCalc().propMap[request_dict['prop']]['result_key']
					if data_obj['prop'] == measured_prop_name:
						pchem_data['data'] = data_obj['data'] # only want request prop
						pchem_data['prop'] = request_dict['prop']  # use cts prop name

			elif calc == 'opera':

				opera_calc = OperaCalc()

				try:

					db_results = opera_calc.check_opera_db(request_dict)  # checks db for pchem data
					if not db_results:
						logging.info("Running OPERA model.")
						pchem_data = opera_calc.data_request_handler(request_dict)
					else:
						logging.info("Getting OPERA p-chem from database.")
						pchem_data = {'valid': True, 'request_post': request_dict, 'data': []}
						db_results = opera_calc.curate_logd(db_results, request_dict, request_dict.get('ph'))
						pchem_data['data'] = self.wrap_db_results(request_dict, db_results, request_dict.get('props'))
						pchem_data['data'] = opera_calc.remove_opera_db_duplicates(pchem_data['data'])
						logging.info("Getting p-chem data from DB.")
						del db_results['_id']
						pchem_data = {'status': True, 'request_post': request_dict, 'data': db_results}
						pchem_data['data'].update(request_dict)
						pchem_data['data'] = opera_calc.convert_units_for_cts(request_dict['prop'], pchem_data['data'])

				except Exception as e:
					logging.warning("Error requesting opera data: {}".format(e))
					db_handler.mongodb_conn.close()
					pchem_data = {'status': False, 'request_post': request_dict, 'data': "Cannot reach OPERA"}
			
			elif calc == 'biotrans':
				biotrans_calc = BiotransCalc()
				pchem_data = biotrans_calc.data_request_handler(request_dict)

			elif calc == 'envipath':
				envipath_calc = EnvipathCalc()
				pchem_data = envipath_calc.data_request_handler(request_dict)

			_response.update({'data': pchem_data})


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
						# 'units': "L/kg",
						'units': "log",
						'description': "organic carbon partition coefficient"
					}
				]
			}
		}


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
		


def getChemicalEditorData(request_post):
	"""
	Makes call to Calculator for chemaxon
	data. Converts incoming structure to smiles,
	then filters smiles, and then retrieves data
	:param request:
	:return: chemical details response json

	Note: Due to marvin sketch image data (<cml> image) being
	so large, a bool, "structureData", is used to determine
	whether or not to grab it. It's only needed in chem edit tab.
	"""
# 	try:
		# # chem_info database routine:
		# ########################################################################
		# dsstox_result = chem_info_obj.get_cheminfo(request_post, only_dsstox=True)
		# db_results = db_handler.find_chem_info_document({'dsstoxSubstanceId': dsstox_result.get('dsstoxSubstanceId')})
		# if db_results:
		# 	# Add response keys (like results below), then push with redis:
		# 	logging.info("Getting chem info from DB.")
		# 	del db_results['_id']
		# 	results = {'status': True, 'request_post': request_post, 'data': db_results}
		# else:
		# 	logging.info("Making request for chem info.")
		# 	results = chem_info_obj.get_cheminfo(request_post)  # get recults from calc server
		# 	db_handler.insert_chem_info_data(results['data'])
		# ########################################################################
	results = chem_info_obj.get_cheminfo(request_post)  # get recults from calc server
	json_data = json.dumps(results)
	return HttpResponse(json_data, content_type='application/json')
# 	except KeyError as error:
# 		logging.warning(error)
# 		wrapped_post = {
# 			'status': False, 
# 			'error': 'Error validating chemical',
# 			'chemical': request_post.get('chemical')
# 		}
# 		return HttpResponse(json.dumps(wrapped_post), content_type='application/json')
# 	except Exception as error:
# 		logging.warning(error)
# 		wrapped_post = {'status': False, 'error': "Cannot validate chemical"}
# 		return HttpResponse(json.dumps(wrapped_post), content_type='application/json')


def getChemicalSpeciationData(request_dict):
	"""
	CTS web service endpoint for getting
	chemical speciation data through  the
	chemspec model/class
	:param request - chemspec_model
	:return: chemical speciation data response json
	"""
	try:
		filtered_smiles = SMILESFilter().filterSMILES(request_dict.get('chemical'))
		request_dict['chemical'] = filtered_smiles
		# Calls chemaxon calculator to get speciation results:
		chemaxon_calc = JchemCalc()
		speciation_results = chemaxon_calc.data_request_handler(request_dict)
		wrapped_post = {
			'status': True,  # 'metadata': '',
			'data': speciation_results
		}
		json_data = json.dumps(wrapped_post)
		return HttpResponse(json_data, content_type='application/json')
	except Exception as error:
		logging.warning("Error in cts_rest, getChemicalSpecation(): {}".format(error))
		return HttpResponse("Error getting speciation data")


def gen_jid():
	ts = datetime.datetime.now(pytz.UTC)
	localDatetime = ts.astimezone(pytz.timezone('US/Eastern'))
	jid = localDatetime.strftime('%Y%m%d%H%M%S%f')
	return jid

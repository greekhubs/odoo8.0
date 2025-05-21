# -*- coding: utf-8 -*-
import openerp
import openerp.http as http
from openerp.http import request
import logging
import json
import urllib2 # Added for Ollama API call
import socket  # Added for socket.timeout

_logger = logging.getLogger(__name__)

class OllamaChatbotController(http.Controller):
    _name = 'ollama_chatbot.controller'

    @http.route('/ollama_chatbot/chat', type='json', auth='user', methods=['POST'])
    def chat(self, **kwargs):
        payload = request.jsonrequest
        user_query = payload.get('query')

        if not user_query:
            return {'error': 'Missing query parameter'}

        _logger.info("Received query: %s from user_id: %s", user_query, request.uid)

        history_model_pool = request.registry['ollama_chatbot.history']
        
        history_id = history_model_pool.create(request.cr, request.uid, {
            'user_query': user_query,
            'user_id': request.uid,
        }, context=request.context)
        _logger.info("Created history record with ID: %s", history_id)

        sales_data = history_model_pool.get_sales_data(request.cr, request.uid, user_query, context=request.context)
        attendance_data = history_model_pool.get_attendance_data(request.cr, request.uid, user_query, context=request.context)
        bank_statement_data = history_model_pool.get_bank_statement_data(request.cr, request.uid, user_query, context=request.context)

        _logger.info("Sales Data Raw: %s", str(sales_data))
        _logger.info("Attendance Data Raw: %s", str(attendance_data))
        _logger.info("Bank Statement Data Raw: %s", str(bank_statement_data))

        # Check for direct apology/error messages from data querying methods
        apology_phrases = [
            "sorry, i can only answer about", 
            "not found", 
            "no records found", 
            "invalid date format",
            "no sales orders found", # Specific to sales
            "no attendance records found", # Specific to attendance
            "no bank statements found", # Specific to bank
            "no transaction lines found" # Specific to bank
        ]
        direct_response = None
        
        # Order of checking might matter if multiple return apologies.
        # For now, first one found is taken.
        data_results_for_check = [sales_data, attendance_data, bank_statement_data]

        for idx, result in enumerate(data_results_for_check):
            if isinstance(result, basestring): # Check if the result is a string
                result_lower = result.lower()
                for phrase in apology_phrases:
                    if phrase in result_lower:
                        source_names = ["sales", "attendance", "bank_statement"]
                        _logger.info("Direct response identified from '%s' data query: %s", source_names[idx], result)
                        direct_response = result
                        break
            if direct_response:
                break
        
        if direct_response:
            _logger.info("Using direct response, bypassing Ollama: %s", direct_response)
            history_model_pool.write(request.cr, request.uid, [history_id], {
                'bot_response': direct_response
            }, context=request.context)
            _logger.info("Updated history record ID %s with direct response.", history_id)
            return {'response': direct_response}

        # Proceed to Ollama if no direct response was identified
        _logger.info("No direct response identified. Proceeding to Ollama API call.")

        prompt = """You are an Odoo assistant. Answer the user's query based on the following data from Odoo.
Original query: {user_query}

Contextual Data from Odoo:
Sales Data: {sales_data}
Attendance Data: {attendance_data}
Bank Statement Data: {bank_statement_data}
---
Answer the original query based *only* on the provided Odoo data. If the data is insufficient, say you cannot answer.
Be concise and informative.
Answer:""".format(
            user_query=user_query,
            sales_data=str(sales_data),
            attendance_data=str(attendance_data),
            bank_statement_data=str(bank_statement_data)
        )
        _logger.info("Constructed Prompt for Ollama:\n%s", prompt)

        config_param_model = request.registry['ir.config_parameter']
        endpoint_url = config_param_model.get_param(request.cr, request.uid, 'ollama_chatbot.api_endpoint', default='', context=request.context)
        _logger.info("Retrieved Ollama API Endpoint: %s", endpoint_url)

        actual_ollama_response = None
        if not endpoint_url or endpoint_url == 'http://localhost:11434/api/default_generate':
            _logger.error("Ollama API endpoint is not configured or is using the placeholder default.")
            actual_ollama_response = "Error: Ollama API endpoint is not configured. Please configure it in Odoo's system parameters (key: ollama_chatbot.api_endpoint)."
        else:
            ollama_payload = {
                'model': 'mistral',
                'prompt': prompt,
                'stream': False
            }
            data = json.dumps(ollama_payload)
            headers = {'Content-Type': 'application/json'}
            req = urllib2.Request(endpoint_url, data, headers)
            
            try:
                _logger.info("Sending request to Ollama API: %s with payload: %s", endpoint_url, data)
                api_response = urllib2.urlopen(req, timeout=60)
                response_body = api_response.read()
                response_json = json.loads(response_body)
                actual_ollama_response = response_json.get('response')
                if actual_ollama_response:
                    _logger.info("Successfully received response from Ollama: %s", actual_ollama_response)
                else:
                    _logger.error("Ollama API response did not contain 'response' key. Full response: %s", response_body)
                    actual_ollama_response = "Error: Received an unexpected response structure from Ollama."
            
            except urllib2.HTTPError as e:
                error_body = ""
                try: error_body = e.read()
                except: error_body = "Could not read error body."
                _logger.error("Ollama API HTTPError: %s - %s. Response body: %s", e.code, e.reason, error_body)
                actual_ollama_response = "Error: Ollama API request failed with status %s. Details: %s" % (e.code, error_body if error_body else e.reason)
            
            except urllib2.URLError as e:
                _logger.error("Ollama API URLError: %s", str(e.reason))
                actual_ollama_response = "Error: Could not connect to Ollama service. Reason: %s" % str(e.reason)
            
            except socket.timeout:
                _logger.error("Ollama API request timed out after 60 seconds.")
                actual_ollama_response = "Error: Ollama API request timed out."

            except ValueError as e: 
                _logger.error("Error decoding JSON response from Ollama: %s. Response body: %s", str(e), response_body if 'response_body' in locals() else "N/A")
                actual_ollama_response = "Error: Could not decode the response from Ollama."

            except Exception as e:
                _logger.error("An unexpected error occurred during Ollama call: %s", str(e))
                actual_ollama_response = "Error: An unexpected error occurred while contacting Ollama: %s" % str(e)

        _logger.info("Final Ollama Response/Error for history: %s", actual_ollama_response)
        history_model_pool.write(request.cr, request.uid, [history_id], {
            'bot_response': actual_ollama_response if actual_ollama_response else "No response processed."
        }, context=request.context)
        _logger.info("Updated history record ID %s with actual Ollama response.", history_id)

        return {'response': actual_ollama_response if actual_ollama_response else "Failed to get response from Ollama."}

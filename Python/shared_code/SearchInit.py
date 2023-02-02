# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import json
import os
import logging
import datetime
from json import JSONEncoder
import azure.functions as func
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential


service_endpoint = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")
key = os.getenv("AZURE_SEARCH_API_KEY")

class DateTimeEncoder(JSONEncoder):
        #Override the default method
        def default(self, obj):
            if isinstance(obj, (datetime.date, datetime.datetime)):
                return obj.isoformat()

def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    logging.info(f'{context.function_name} HTTP trigger function processed a request.')
    if hasattr(context, 'retry_context'):
        logging.info(f'Current retry count: {context.retry_context.retry_count}')
        
        if context.retry_context.retry_count == context.retry_context.max_retry_count:
            logging.info(
                f"Max retries of {context.retry_context.max_retry_count} for "
                f"function {context.function_name} has been reached")
    
    try:
        body = json.dumps(req.get_json())
        if body:
            logging.info(body)
            result = compose_response(body)
            return func.HttpResponse(result, mimetype="application/json")
        else:
            return func.HttpResponse(
                "Invalid body",
                status_code=400
            )
    except ValueError:
        return func.HttpResponse(
             "Invalid body",
             status_code=400
        )
    except KeyError:
        return func.HttpResponse(
             "Skill configuration error. Endpoint & Key required.",
             status_code=400
        )

def cogsearch_query(search_text_string, numberofresults):
    
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    search_client = SearchClient(service_endpoint, index_name, AzureKeyCredential(key))
    results = search_client.search(search_text=search_text_string, include_total_count =1, top=numberofresults)
    print("records containing the string")
    for result in results:
            print(json.dumps(result))
    return results




def compose_response(json_data):
    values = json.loads(json_data)['values']
    # Prepare the Output before the loop
    results = {}
    results["values"] = []
    
    for value in values:
        output_record = transform_value(value)
        if output_record != None:
            results["values"].append(output_record)
    
    return json.dumps(results, ensure_ascii=False, cls=DateTimeEncoder)


def transform_value(value):
      
    # Validate the inputs
    try:
        assert ('searchQuery' in value), "'searchQuery' field is required."
        searchQuery = value['searchquery']   
        print(searchQuery)
    except AssertionError  as error:
        return None

      # Validate the inputs
    try:
        assert ('seachItemNumbers' in value), "'seachItemNumbers' field is will be defaulted to 10."
        seachItemNumbers = value['seachItemNumbers']   
        print(seachItemNumbers)
    except AssertionError  as warning:
        seachItemNumbers = 10
    search_result = cogsearch_query(searchQuery, seachItemNumbers)
    return search_result
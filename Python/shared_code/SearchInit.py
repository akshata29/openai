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

searchEndPoint = os.environ["SearchEndPoint"]
searchIndex = os.environ["SearchIndex"]
searchKey = os.environ["SearchKey"]

class DateTimeEncoder(JSONEncoder):
        #Override the default method
        def default(self, obj):
            if isinstance(obj, (datetime.date, datetime.datetime)):
                return obj.isoformat()

def cogSearchQuery(search_text_string, numberofresults, contentField):
    
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    search_client = SearchClient(searchEndPoint, searchIndex, AzureKeyCredential(searchKey))
    results = search_client.search(search_text=search_text_string, include_total_count =1, top=numberofresults, select=contentField)
    print("records containing the string")
    response = []
    for result in results:
            searchResp = result[contentField]
            response.append(searchResp)
    return '\n'.join(response)

def openAiQuery(search_text_string, numberofresults):
    
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    search_client = SearchClient(searchEndPoint, searchIndex, AzureKeyCredential(searchKey))
    results = search_client.search(search_text=search_text_string, include_total_count =1, top=numberofresults)
    print("records containing the string")
    for result in results:
            print(json.dumps(result))
    return results

def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    logging.info(f'{context.function_name} HTTP trigger function processed a request.')
    if hasattr(context, 'retry_context'):
        logging.info(f'Current retry count: {context.retry_context.retry_count}')
        
        if context.retry_context.retry_count == context.retry_context.max_retry_count:
            logging.info(
                f"Max retries of {context.retry_context.max_retry_count} for "
                f"function {context.function_name} has been reached")
    
    try:
        userQuery = req.params.get('userQuery')
        totalDocs = req.params.get('totalDocs')
        modelName = req.params.get('modelName')
        modelType = req.params.get('modelType')
        contentField = req.params.get('contentField')
        result = transform_value(userQuery, totalDocs, modelName, modelType, contentField)

        return func.HttpResponse(result, mimetype="application/json")
        #return result
        # body = json.dumps(req.get_json())
        # if body:
        #     logging.info(body)
        #     result = compose_response(body)
        #     return func.HttpResponse(result, mimetype="application/json")
        # else:
        #     return func.HttpResponse(
        #         "Invalid body",
        #         status_code=400
        #     )
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

def transform_value(userQuery, totalDocs, modelName, modelType, contentField):
      
    # Validate the inputs
    try:
        assert (userQuery), "'searchQuery' field is required."
        print(userQuery)
    except AssertionError  as error:
        return None
    try:
        assert (totalDocs), "'seachItemNumbers' field is will be defaulted to 10."
        print(totalDocs)
    except AssertionError  as warning:
        totalDocs = 10
    
    try:
        assert (modelType), "'modelType' field is required."
        print(modelType)
    except AssertionError  as warning:
        return None

    if (modelType == "CognitiveSearch"):
        search_result = cogSearchQuery(userQuery, totalDocs, contentField)
    elif modelType == "OpenAI":
        search_result = openAiQuery(userQuery, totalDocs, modelName)
        
    # Prepare the Output before the loop
    results = {}
    results['values'] = []
    searchResp = ({
            "recordId": 0,
            "data": {
                "text": search_result
                    }
            })

    if search_result != None:
        results["values"].append(searchResp)
    return json.dumps(results, ensure_ascii=False) 

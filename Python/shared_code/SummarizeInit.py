# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import json
import azure.functions as func
import openai
import re
import requests
import sys
import os
import pandas as pd
import numpy as np
from openai.embeddings_utils import get_embedding, cosine_similarity

opanaiKey = os.environ['OpenAiKey']
openaiEndpoint = os.environ['OpenAiEndPoint']
openAiVersion = os.environ['OpenAiVersion']

#Splits text after sentences ending in a period. Combines n sentences per chunk.
def splitter(n, s):
    pieces = s.split(". ")
    list_out = [" ".join(pieces[i:i+n]) for i in range(0, len(pieces), n)]
    return list_out

# Perform light data cleaning (removing redudant whitespace and cleaning up punctuation)
def normalize_text(s, sep_token = " \n "):
    s = re.sub(r'\s+',  ' ', s).strip()
    s = re.sub(r". ,","",s)
    # remove all instances of multiple spaces
    s = s.replace("..",".")
    s = s.replace(". .",".")
    s = s.replace("\n", "")
    s = s.strip()
    
    return s

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
        logging.info("Input parameters : " + userQuery + " " + totalDocs + " " + modelName)
        body = json.dumps(req.get_json())
    except ValueError:
        return func.HttpResponse(
             "Invalid body",
             status_code=400
        )
    
    if body:
        result = compose_response(userQuery, totalDocs, modelName, body)
        return func.HttpResponse(result, mimetype="application/json")
    else:
        return func.HttpResponse(
             "Invalid body",
             status_code=400
        )

def compose_response(userQuery, totalDocs, modelName, json_data):
    values = json.loads(json_data)['values']
    
    # Prepare the Output before the loop
    results = {}
    results["values"] = []

    for value in values:
        output_record = transform_value(value, userQuery, totalDocs, modelName)
        if output_record != None:
            results["values"].append(output_record)
    return json.dumps(results, ensure_ascii=False)        

## Perform an operation on a record
def transform_value(record, userQuery, totalDocs, modelName):
    try:
        recordId = record['recordId']
    except AssertionError  as error:
        return None

    # Validate the inputs
    try:
        assert ('data' in record), "'data' field is required."
        data = record['data']        
        assert ('text' in data), "'text' field is required in 'data' object."   

    except KeyError as error:
        return (
            {
            "recordId": recordId,
            "errors": [ { "message": "KeyError:" + error.args[0] }   ]       
            })
    except AssertionError as error:
        return (
            {
            "recordId": recordId,
            "errors": [ { "message": "AssertionError:" + error.args[0] }   ]       
            })
    except SystemError as error:
        return (
            {
            "recordId": recordId,
            "errors": [ { "message": "SystemError:" + error.args[0] }   ]       
            })

    try:
        openai.api_type = "azure"
        openai.api_key = opanaiKey
        openai.api_base = openaiEndpoint
        openai.api_version = openAiVersion

        # Getting the items from the values/data/text
        myStringList = []
        myStringList = data['text']

        # Cleaning the list, removing duplicates
        myStringList = list(dict.fromkeys(myStringList))

        '''
        Designing a prompt that will show and tell GPT-3 how to proceed. 
        + Providing an instruction to summarize the text about the general topic (prefix)
        + Providing quality data for the chunks to summarize and specifically mentioning they are the text provided (context + context primer)
        + Providing a space for GPT-3 to fill in the summary to follow the format (suffix)
        '''

        #prompt_i = userQuery + '\n\n\Text:\n' + ' '.join([normalize_text(myStringList)])
        prompt_i = userQuery + '\m\nText:\n' + ' '.join(myStringList)
        #logging.info(prompt_i)

        # for item in myStringList:
        #     logging.info(prompt_i)
        #     logging.info(item)
        #     prompt_i = prompt_i + '\n\n\Text:\n' + " ".join([normalize_text(item)])

        prompt = "".join([prompt_i, '\n\n Summary:\n'])

        #logging.info("Prompt ", prompt)

        # Using a temperature a low temperature to limit the creativity in the response. 
        response = openai.Completion.create(
                engine= modelName,
                prompt = prompt,
                temperature = 0.4,
                max_tokens = 500,
                top_p = 1.0,
                frequency_penalty=0.5,
                presence_penalty = 0.5,
                best_of = 1
            )

        summaryResponse = response.choices[0].text
        return ({
            "recordId": recordId,
            "data": {
                "text": summaryResponse
                    }
            })

    except:
        return (
            {
            "recordId": recordId,
            "errors": [ { "message": "Could not complete operation for record." }   ]
            })
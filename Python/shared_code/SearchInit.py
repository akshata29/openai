# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import json
import re
import os
import logging
import openai
import datetime
from json import JSONEncoder
import azure.functions as func
import pandas as pd
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai.embeddings_utils import get_embedding, cosine_similarity
from transformers import GPT2TokenizerFast

searchEndPoint = os.environ["SearchEndPoint"]
searchIndex = os.environ["SearchIndex"]
searchKey = os.environ["SearchKey"]
opanaiKey = os.environ['OpenAiKey']
openaiEndpoint = os.environ['OpenAiEndPoint']
openAiVersion = os.environ['OpenAiVersion']

class DateTimeEncoder(JSONEncoder):
        #Override the default method
        def default(self, obj):
            if isinstance(obj, (datetime.date, datetime.datetime)):
                return obj.isoformat()

#Splits text after sentences ending in a period. Combines n sentences per chunk.
def splitter(n, s):
    pieces = s.split(". ")
    list_out = [" ".join(pieces[i:i+n]) for i in range(0, len(pieces), n)]
    return list_out

# Perform light data cleaning (removing redudant whitespace and cleaning up punctuation)
# s is input text
def normalize_text(s, sep_token = " \n "):
    s = re.sub(r'\s+',  ' ', s).strip()
    s = re.sub(r". ,","",s)
    # remove all instances of multiple spaces
    s = s.replace("..",".")
    s = s.replace(". .",".")
    s = s.replace("\n", "")
    s = s.strip()
    
    return s

def searchUsingEmbedding(response, contentField, userQuery, topN):
    allDocsDf = pd.DataFrame(response, columns=[contentField])
    tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
    # remove bills that are too long for the token limitation
    allDocsDf['n_tokens'] = allDocsDf[contentField].apply(lambda x: len(tokenizer.encode(x, truncation=True, max_length=1024)))
    allDocsDf = allDocsDf[allDocsDf.n_tokens<2000]
    allDocsDf['curieSearch'] = allDocsDf[contentField].apply(lambda x : get_embedding(x, engine = 'searchcuriedoc001'))
    embedding = get_embedding(userQuery,engine="searchcuriequery001")
    allDocsDf["similarities"] = allDocsDf.curieSearch.apply(lambda x: cosine_similarity(x, embedding))

    allDocsDf = allDocsDf.sort_values("similarities", ascending=False)
    response = []
    i = 0
    for idx, row in allDocsDf.iterrows():
        print(row[contentField])
        if i > int(topN):
            break
        i = i + 1
        response.append(row[contentField])
    return response

# search through the document for a text segment most similar to the query
# display top n most similar chunks based on cosine similarity
def documentZoneIn(response, contentField, userQuery, top_n=3):
    # Now that we got the Top 5 results, let's chunk those into 10 sentences to run Embedding GPT model and do Document segmentation
    searchedDf = pd.DataFrame(response, columns=[contentField])
    searchChunkDf = pd.DataFrame(columns=["og_row", contentField])
    for idx, row in searchedDf.iterrows():
        df_temp = pd.DataFrame(columns=["og_row", contentField])
        for elem in splitter(10,row[contentField]):
            df_temp.loc[len(df_temp.index)] = [idx, elem]
        searchChunkDf = searchChunkDf.append(df_temp)

    searchChunkDf['id'] = range(1, len(searchChunkDf.index)+1)
    searchChunkDf.set_index("id", inplace=True)
    searchChunkDf[contentField] = searchChunkDf[contentField].apply(lambda x : normalize_text(x))
    # Run through the doc search chucked content against doc embedding model
    openai.api_type = "azure"
    openai.api_key = opanaiKey
    openai.api_base = openaiEndpoint
    openai.api_version = openAiVersion

    searchChunkDf['curieSearch'] = searchChunkDf[contentField].apply(lambda x : get_embedding(x, engine = 'searchcuriedoc001'))

    # We embed the user query using the associated “query” model (text-serach-query-curie-001). We compare the user query embedding 
    # to the embedding for each chunk of the article, to find the chunk that is most like the user query based on cosine similarity
    # and can provide the answer.
    embedding = get_embedding(userQuery, engine="searchcuriequery001")
    searchChunkDf["similarities"] = searchChunkDf.curieSearch.apply(lambda x: cosine_similarity(x, embedding))
    searchChunkDf = searchChunkDf.sort_values("similarities", ascending=False)
    response = []
    i = 0
    for idx, row in searchChunkDf.iterrows():
        print(row[contentField])
        if i > int(top_n):
            break
        i = i + 1
        response.append(row[contentField])
    return response

def cogSearchQuery(search_text_string, numberofresults, contentField):
    
    search_client = SearchClient(searchEndPoint, searchIndex, AzureKeyCredential(searchKey))
    results = search_client.search(search_text=search_text_string, include_total_count =1, top=numberofresults, select=contentField)
    response = []
    for result in results:
            searchResp = result[contentField]
            response.append(searchResp)

    zonedDf = documentZoneIn(response, contentField, search_text_string, numberofresults)
    return '\n'.join(zonedDf)

def openAiQuery(search_text_string, numberofresults, modelName, contentField):
    
    search_client = SearchClient(searchEndPoint, searchIndex, AzureKeyCredential(searchKey))
    results = search_client.search(search_text='*', select=contentField)
    print("records containing the string")
    response = []
    for result in results:
            searchResp = result[contentField]
            response.append(searchResp)

    # Perform the search using OpenAI model instead of Cognitive search
    searchResponse = searchUsingEmbedding(response, contentField, search_text_string, numberofresults)
    zonedDf = documentZoneIn(searchResponse, contentField, search_text_string, numberofresults)
    return '\n'.join(zonedDf)


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
        logging.info("Input parameters : " + userQuery + " " + totalDocs + " " + modelName + " " + modelType + " " + contentField)

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
        logging.info ("Call Cognitive Search Query")
        search_result = cogSearchQuery(userQuery, totalDocs, contentField)
    elif modelType == "OpenAI":
        logging.info ("Call OpenAI Query")
        search_result = openAiQuery(userQuery, totalDocs, modelName, contentField)
        
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

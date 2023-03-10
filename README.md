# Search and Summarization Accelerator

## Introduction

Knowledge bases in enterprises are very common in the industry today and can have extensive number of documents in different categories. Retrieving relevant content based on a user query is a challenging task.  Given a query we were able to retrieve information accurately at the document level using methods such as Page Rank developed and made highly accurate especially by Google,  after this point the user has to delve into the document and search for the relevant information.  With recent advances in Foundation Transformer Models such as the one developed by Open AI the challenge is alleviated by using “Semantic Search” methods by using encoding information such as “Embeddings” to find the relevant information and then to summarize the content to present to the user in a concise and succinct manner.

This accelerator will introduce the relevant use cases and the end-to-end architecture.  We will take you through the step-by-step process of using Power Platform (Power Virtual Agent & Power Flow), Azure Cognitive Search and Azure OpenAI's GPT-3 models to perform the downstream task of summarization.

## Architecture 

The end user passes their query from the Bot that is surfaced through Power Virtual Agent.  The PVA invokes Power Automate which in-turn calls Azure Function API which internally filters all the document for our dataset (CNN/Dailymail) hosted in Cognitive Search Knowledge base index.  The Cognitive search will narrow the scope of documents to top 5  from the large indexed repository. Then once a document is filtered, the document needs to be segmented and then each segment can be embedded using GPT-3 embedding models. This allows each text chunk to have its semantic meaning captured through an embedding. Then the query is "zoned in" on a particular text segment or segements based using similarities between the query and embeddings for each text chunk. Once a section is "zoned-in", the relavant text is passed to the second API from Power Automate to the GPT-3 Completion endpoint for summarization. 

![Figure 1: End-to-end Architecture](/images/End-To-End-Architecture.png)
<figcaption align = "center"><b>Figure 1: End-to-end Architecture</b></figcaption>

### Document Search

Document Search is driven by an initial user query. The user provided query is sent to the search service, enabling users to find the top most relevant document from their knowledge base. Azure Cognitive Search leverages the state of the art search technology using indexers. Within large enteprises there are various documents in different formats that are congregated in a large knowledge base. Having the ability to quickly, effectively, and accurately find relevant documents is essential to this end-to-end scenario.

### Document Summarization

Document Summarization is performed by providing input quality text into the summarizaton engine. The key to successful document summarization is retrieving the most important points within a large document to feed into summarization, as the quality and focus of a summary is only as good as the input data. To ensure the most succinct and focused summary is returned, we utitlize Embeddings to search within a document for the most salient pieces. Document Summarization is essential in large enteprises to condense large documents into human consumable information that frees up humans to do more specialized and techincal work rather than focus on common tasks such as summmarization.

## Example Walk-Through

We will dive deep into each component of the architecture for a successful document summarization use case. 

Our guiding query that we will use for this playbook is **"Provide details on the Clinton democratic nomination"**

## Dataset

For this walkthrough, we will be using the **CNN/Daily Mail** dataset. This is a common dataset used for text summarization and question answering tasks. Human generated abstractive summary bullets were generated from news stories in CNN and Daily Mail websites. 

In all, the corpus has 286,817 training pairs, 13,368 validation pairs and 11,487 test pairs, as defined by their scripts. The source documents in the training set have 766 words spanning 29.74 sentences on an average while the summaries consist of 53 words and 3.72 sentences. We will use a subset of the corpus for this example that can be found in the /data folder. 

The relevant schema for our work today consists of:

+ id: a string containing the heximal formatted SHA1 hash of the URL where the story was retrieved from
+ article: a string containing the body of the news article
+ highlights: a string containing the highlight of the article as written by the article author

## Knowledge Base: __Azure Blob Storage__

Being able to store and access unstructured data at scale is imperative for enterprises. Azure Blob Storage provides storage capabilities with optimized costs with tieired storage for long-term data, and flexibiluty for high perofrmancing computer and ML workloads. The comprehensive data management Azure Blob Storage provides coupled with it's ease of use is why we chose to upload our knowledge base to Azure Blob Storage for this scenario.

Around 11.2K articles and their summaries are stored in the Azure cloud for quick aceess. To do this we created a blob services with the dataset uploaded as a CSV.

## Enterprise Search: __Azure Cognitive Search__

Azure Cognitive Search is a cloud search service that provides developers infrastructure, APIs, and tools for building a rich search experience. This service creates a search engine for full text search over a search index containing user-owned content. Azure Cognitive Search uses semantic search that brings relevance and language understanding to search results.

In this example, we will create a search service within the Azure portal with a customized index that enables us to search the CNN/Daily Mail knowledge base stored in Azure Blob storage.

In the image below, we have created an index to search against the 11.2K document stored in the Azure Blob Storage. We use the id, article, and highlights field to be retrievable during the search.

![Figure 2: Azure Cognitive Search Index](/images/CognitiveSearch.png)
<figcaption align = "center"><b>Figure 2: Azure Cognitive Search Index</b></figcaption>


Now that we have our our storage and search services set up through the Azure portal, you can query against the knowledge base. As a reminder from above, our **guiding initial query is "Provide details on the Clinton Democratic nomination"**

Lets place that query or a paragraphse of the query into the Azure Cognitive Search service, and see what the top results are.

![Figure 3: Azure Cognitive Search Results](/images/CognitiveSearchResult.png)
<figcaption align = "center"><b>Figure 3: Azure Cognitive Search Results</b></figcaption>

For our use-case because we are surfacing this as the query coming in from PVA, and Power Automate will be orchestrate the workflow, we will create our wrapper as Python code in Azure Function.  Following is the code segment that will perform search against the Cognitive Search Index that we created earlier.

```python
import azure.search.document

search_client = SearchClient(searchEndPoint, searchIndex, AzureKeyCredential(searchKey))
results = search_client.search(search_text=search_text_string, include_total_count =1, top=numberofresults, select=contentField)
response = []
for result in results:
        searchResp = result[contentField]
        response.append(searchResp)
```

At this point in the use case, the user can either select the top article or investigate which of the top results is providing the most relevant information for their use case. For now we will keep it simple and select the top 3-5 documents and focus on those to find the answer for the user's initial query. 

## Document Zone: __Azure OpenAI Embedding API__

Now that we have narrowed on a top documents from our knowledge base of 11.2K documents - we can dive deeper into the single document to refine our initial query to a more specific section or "zone" of the article.

To do this, we will utilize the Azure Open AI Embeddings API. 

### Embeddings Overview

An embedding is a special format of data representation that can be easily utilized by machine learning models and algorithms. The embedding
is an information dense representation of the semantic meaning of a piece of text. Each embedding is a vector of floating-point numbers,
such that the distance between two embeddings in the vector space is correlated with semantic similarity between two inputs in the original
format. For example, if two texts are similar, then their vector representations should also be similar.

Different Azure OpenAI embedding models are specifically created to be good at a particular task. Similarity embeddings are good at capturing
semantic similarity between two or more pieces of text. Text search embeddings help measure long documents are relevant to a short query.
Code search embeddings are useful for embedding code snippets and embedding nature language search queries.

Embeddings make it easier to do machine learning on large inputs representing words by capturing the semantic similarities in a vector
space. Therefore, we can use embeddings to if two text chunks are semantically related or similar, and inherently provide a score to
assess similarity.

### Cosine Similarity

A previously used approach to match similar documents was based on counting maximum number of common words between documents. This is
flawed since as the document size increases, the overlap of common words increases even if the topics differ. Therefore cosine similarity is a better approach by using the Euclidean distance.

Mathematically, cosine similarity measures the cosine of the angle between two vectors projected in a multi-dimensional space. This is
beneficial because if two documents are far apart by Euclidean distance because of size, they could still have a smaller angle between them and therefore higher cosine similarity.

The Azure OpenAI embeddings rely on cosine similarity to compute similarity between documents and a query.

### Text Segmentation or "Chunking"

The documents that we selected span a few pages. In order to produce a meaningful and a focused summary we must first chunk or segment the document. This is essential for long document summarization for two main reasons:

+ Going around the token limitation inherit in a transformer based model - due to the token limitation we cannot pass the entire document into a model 
+ Creating a mapping from topic to relevant chunks of text - for long documents topics can vary drastically and to produce a meaningful summary, most of the time you want to "zone" on a single area. This may be a page or just a section with the information you want to dive into. 


By chunking the document into logical segments, we can utilize the power of the Azure OpenAI Embeddings following these steps:

1. Chunk the document into logical segments that fit within the token limitation
2. Create an embedding vector for each chunk that will capture the semantic meaning and overall topic of that chunk
3. Upon receiving a query for the specific document, embed the query in the same vector space as the context chunks from Step 2.
4. Find the most relevant context chunks through cosine similarity and use it for your desired downstream tasks. 

In the code below, for the documents we received from the content field we are:
1. Chunking the document by creating a chunk every 10th sentence and creating a pandas DF
-  Splitting text after sentences ending in a period. Combines n sentences per chunk.
- Perform light data cleaning (removing redudant whitespace and cleaning up punctuation)
2. Create an embedding vector for each chunk that will capture the semantic meaning and overall topic of that chunk
3. Upon receiving a query for the specific document, embed the query in the same vector space as the context chunks
4. We embed the user query using the associated “query” model (text-serach-query-curie-001). We compare the user query embedding  to the embedding for each chunk of the article, to find the chunk that is most like the user query based on cosine similarity and can provide the answer.

```python
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
```

## Document Summarization: __Azure OpenAI Completion API__

Now that we have extracted the relevant context chunks using Azure OpenAI Embedding API, we can use these chunks to provide meaningful context for our prompt design. We will be using the **Completion endpoint** for summarization. 

### Prompt Design Refresher

GPT-3 models can perform many tasks. Therefore you must be explicit in describing what you want. 

The models try to guess what you want from the prompt. If you send the words "Give me a list of cat breeds," the model wouldn't automatically assume that you're asking for a list of cat breeds. You could just as easily be asking the model to continue a conversation where the first words are "Give me a list of cat breeds" and the next ones are "and I'll tell you which ones I like." If the model only assumed that you wanted a list of cats, it wouldn't be as good at content creation, classification, or other tasks.

There are three basic guidelines to creating prompts:

**Show and tell**. Make it clear what you want either through instructions, examples, or a combination of the two. If you want the model to rank a list of items in alphabetical order or to classify a paragraph by sentiment, show it that's what you want.

**Provide quality data**. If you're trying to build a classifier or get the model to follow a pattern, make sure that there are enough examples. Be sure to proofread your examples — the model is usually smart enough to see through basic spelling mistakes and give you a response, but it also might assume this is intentional and it can affect the response.

**Check your settings.** The temperature and top_p settings control how deterministic the model is in generating a response. If you're asking it for a response where there's only one right answer, then you'd want to set these lower. If you're looking for more diverse responses, then you might want to set them higher. The number one mistake people use with these settings is assuming that they're "cleverness" or "creativity" controls.

### Few-Shot Approach

The goal of this is to teach the GPT-3 model to learn a conversation style input. We use the “Completion” create OpenAI API and generate a prompt that would best provide us a summary of the conversation. It is important to generate prompts carefully to extract relevant information. To extract general summaries from customer-agent chats, we will be using the following format:

1. Prefix: What do you want it to do
2. Context primer : Describe what the context is
3. Context: # Essentially the information needed to answer the question. In the case of summary, the prose that needs to be summarized. 
4. Suffix: Describe what form the answer should take. Whether it is an answer, a completion, a summary, etc


```python
    '''
    Designing a prompt that will show and tell GPT-3 how to proceed. 
    + Providing an instruction to summarize the text about the general topic (prefix)
    + Providing quality data for the chunks to summarize and specifically mentioning they are the text provided (context + context primer)
    + Providing a space for GPT-3 to fill in the summary to follow the format (suffix)
    '''

    prompt_i = userQuery + '\m\nText:\n' + ' '.join(myStringList)
    prompt = "".join([prompt_i, '\n\n Summary:\n'])
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
```
As a result, we have a succinct, clear, and impactful summary generated by the Azure OpenAI Completion API.

### Power Virtual Agent

![Figure 4: Power Virtual Agent Topic](/images/OpenAI-Topic.png)
<figcaption align = "center"><b>Figure 4: Power Virtual Agent Topic</b></figcaption>

Power Virtual Agent topic code is available at /powerplatform/openai.topic

### Power Automate

![Figure 5: Power Automate](/images/PowerAutomate.png)
<figcaption align = "center"><b>Figure 4: Power Automate</b></figcaption>

PVA and Power Automate solution is exported and made available at powerplatform/openai.zip

Feel free to publish the PVA bot to the website (https://learn.microsoft.com/en-us/power-virtual-agents/publication-connect-bot-to-web-channels) and enable the Microsoft Teams channel (https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/add-power-virtual-agents-bot-to-teams) to test it out further

### TODO
Add additional dataset 
- Immediate Plan - Financial Dataset - Annual Reports, Contracts and Call Transcripts
- Fine-tuning enhancements
- Automated Deployment with default datasets
- Additional Parameters (using Abstractive Summarization, - OpenAI and other models)
- Business Process Automation: Search through structured & unstructured documentation, Generate Code to query data models, Content Generation

#### Code is enhanced from OpenAI Samples.  Thank you to Azure OpenAI Samples Team
https://github.com/Azure/openai-samples

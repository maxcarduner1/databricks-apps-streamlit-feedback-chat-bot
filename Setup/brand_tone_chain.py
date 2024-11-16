# Databricks notebook source
# MAGIC %pip install langchain-core==0.2.5 langchain-community==0.2.4

# COMMAND ----------

# MAGIC %pip install -U databricks-agents databricks-sdk mlflow-skinny[databricks]
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

catalog = 'users'
db = 'max_carduner'

# COMMAND ----------

import mlflow
import yaml 

chain_config = {
    "databricks_resources": {
        "llm_endpoint_name": "databricks-meta-llama-3-1-70b-instruct",
    },
    "input_example": {
        "messages": [
            {"role": "user", "content": "Databricks is cool"},
            {"role": "assistant", "content": "Databricks is a cutting-edge platform that has transformed the big data landscape, providing a unified and user-friendly environment for data engineering, data science, and analytics, and enabling organizations to extract actionable insights and drive strategic decision-making."},
            {"role": "user", "content": "Incorporate more information on Data Engineering capabilities"},
        ]
    },
    "llm_config": {
        "llm_parameters": {"max_tokens": 5000, "temperature": 0.01},
        "llm_prompt_template": '''You are a marketing professional trusted assistant that helps write rough draft copy into the approved tone and voice. Only focus on the content that is provided by the user, don't add any additional context, just focus on getting it into the approved tone. Do not repeat information, answer directly, do not repeat the question, do not start with something like: the answer to the question, do not add AI in front of your answer, do not say: here is the answer. See examples below: 
        
        copy:
        final copy:

        copy:
        final copy:

        copy:
        final copy:

        copy:
        final copy:
        
        copy: {question}''',
        "llm_prompt_template_variables": ["copy"], 
    },
}
try:
    with open('chain_config.yaml', 'w') as f:
        yaml.dump(chain_config, f)
except:
    print('pass to work on build job')
model_config = mlflow.models.ModelConfig(development_config='chain_config.yaml')

# COMMAND ----------

# MAGIC %%writefile chain.py
# MAGIC from operator import itemgetter
# MAGIC import mlflow
# MAGIC import os
# MAGIC
# MAGIC from langchain_community.chat_models import ChatDatabricks
# MAGIC
# MAGIC from langchain_core.runnables import RunnableLambda
# MAGIC from langchain_core.output_parsers import StrOutputParser
# MAGIC from langchain_core.prompts import (
# MAGIC     PromptTemplate,
# MAGIC     ChatPromptTemplate,
# MAGIC     MessagesPlaceholder,
# MAGIC )
# MAGIC from langchain_core.messages import HumanMessage, AIMessage
# MAGIC from langchain_core.runnables import RunnablePassthrough, RunnableBranch
# MAGIC
# MAGIC ## Enable MLflow Tracing
# MAGIC mlflow.langchain.autolog()
# MAGIC
# MAGIC # Return the string contents of the most recent message from the user
# MAGIC def extract_user_query_string(chat_messages_array):
# MAGIC     return chat_messages_array[-1]["content"]
# MAGIC
# MAGIC # Return the chat history, which is is everything before the last question
# MAGIC def extract_chat_history(chat_messages_array):
# MAGIC     return chat_messages_array[:-1]
# MAGIC
# MAGIC # Load the chain's configuration
# MAGIC model_config = mlflow.models.ModelConfig(development_config="chain_config.yaml")
# MAGIC
# MAGIC databricks_resources = model_config.get("databricks_resources")
# MAGIC # retriever_config = model_config.get("retriever_config")
# MAGIC llm_config = model_config.get("llm_config")
# MAGIC
# MAGIC
# MAGIC # Prompt Template for generation
# MAGIC prompt = ChatPromptTemplate.from_messages(
# MAGIC     [
# MAGIC         ("system", llm_config.get("llm_prompt_template")),
# MAGIC         # Note: This chain does not compress the history, so very long converastions can overflow the context window.
# MAGIC         MessagesPlaceholder(variable_name="formatted_chat_history"),
# MAGIC         # User's most current question
# MAGIC         ("user", "{question}"),
# MAGIC     ]
# MAGIC )
# MAGIC
# MAGIC
# MAGIC # Format the converastion history to fit into the prompt template above.
# MAGIC def format_chat_history_for_prompt(chat_messages_array):
# MAGIC     history = extract_chat_history(chat_messages_array)
# MAGIC     formatted_chat_history = []
# MAGIC     if len(history) > 0:
# MAGIC         for chat_message in history:
# MAGIC             if chat_message["role"] == "user":
# MAGIC                 formatted_chat_history.append(HumanMessage(content=chat_message["content"]))
# MAGIC             elif chat_message["role"] == "assistant":
# MAGIC                 formatted_chat_history.append(AIMessage(content=chat_message["content"]))
# MAGIC     return formatted_chat_history
# MAGIC
# MAGIC # Prompt Template for query rewriting to allow converastion history to work - this will translate a query such as "how does it work?" after a question such as "what is spark?" to "how does spark work?".
# MAGIC query_rewrite_template = """Based on the chat history below and the newest instruction, rewrite the rough draft of the copy. Focus on getting all of the context into the rough draft of the copy. Don't say "here is the rough draft" or any precluding messages or any notes about how you changed the output, just the displayed output. See example below:
# MAGIC
# MAGIC Chat history: 'Databricks is cool','Databricks is a cutting-edge platform that has transformed the big data landscape, providing a unified and user-friendly environment for data engineering, data science, and analytics, and enabling organizations to extract actionable insights and drive strategic decision-making.'
# MAGIC Newest instruction on copy: provide more information on Gen AI capabilities
# MAGIC revised rough draft: Databricks is a cutting-edge platform that has transformed the big data landscape, providing a unified and user-friendly environment for data engineering, data science, and analytics. With its innovative capabilities, Databricks enables organizations to extract actionable insights and drive strategic decision-making. Furthermore, Databricks is at the forefront of Generative AI (Gen AI) capabilities, empowering users to unlock new levels of productivity and innovation. By leveraging Gen AI, users can automate complex tasks, generate new insights, and create new data products, revolutionizing the way they work with data. With Databricks, organizations can harness the power of Gen AI to stay ahead of the curve and achieve their goals.
# MAGIC
# MAGIC
# MAGIC Chat history: {formatted_chat_history}
# MAGIC Newest instruction on copy: {question}
# MAGIC revised rough draft:"""
# MAGIC
# MAGIC query_rewrite_prompt = PromptTemplate(
# MAGIC     template=query_rewrite_template,
# MAGIC     input_variables=["formatted_chat_history", "question"],
# MAGIC )
# MAGIC
# MAGIC # # FM for generation
# MAGIC model = ChatDatabricks(
# MAGIC     endpoint=databricks_resources.get("llm_endpoint_name"),
# MAGIC     extra_params=llm_config.get("llm_parameters"),
# MAGIC )
# MAGIC
# MAGIC # Chain with history
# MAGIC chain = (
# MAGIC     {
# MAGIC         "question": itemgetter("messages") | RunnableLambda(extract_user_query_string),
# MAGIC         "chat_history": itemgetter("messages") | RunnableLambda(extract_chat_history),
# MAGIC         "formatted_chat_history": itemgetter("messages") | RunnableLambda(format_chat_history_for_prompt),
# MAGIC     }
# MAGIC     | RunnablePassthrough()
# MAGIC     | {
# MAGIC         "question": RunnableBranch(  # Only re-write the question if there is a chat history
# MAGIC             (
# MAGIC                 lambda x: len(x["chat_history"]) > 0,
# MAGIC                 {
# MAGIC                     "formatted_chat_history": itemgetter("formatted_chat_history"),
# MAGIC                     "question": itemgetter("question")
# MAGIC                 } | query_rewrite_prompt | model | StrOutputParser(),
# MAGIC             ),
# MAGIC             itemgetter("question"),
# MAGIC         ),
# MAGIC          "formatted_chat_history": itemgetter("formatted_chat_history")
# MAGIC     }
# MAGIC     | prompt
# MAGIC     | model
# MAGIC     | StrOutputParser()
# MAGIC )
# MAGIC
# MAGIC ## Tell MLflow logging where to find your chain.
# MAGIC mlflow.models.set_model(model=chain)

# COMMAND ----------

import os
# Log the model to MLflow
with mlflow.start_run(run_name="brand_tone_bot"):
  logged_chain_info = mlflow.langchain.log_model(
      lc_model=os.path.join(os.getcwd(), 'chain.py'),  #Chain code file e.g., /path/to/the/chain.py 
      model_config='chain_config.yaml',  # Chain configuration 
      artifact_path="chain",  # Required by MLflow
      input_example=model_config.get("input_example"),  # Save the chain's input schema.  MLflow will execute the chain before logging & capture it's output schema.
      example_no_conversion=True,  # Required by MLflow to use the input_example as the chain's schema
      pip_requirements="requirements.txt",
      
  )
# 
# Test the chain locally
chain = mlflow.langchain.load_model(logged_chain_info.model_uri)
chain.invoke(model_config.get("input_example"))

# COMMAND ----------

MODEL_NAME = "brand_tone_chain"
MODEL_NAME_FQN = f"{catalog}.{db}.{MODEL_NAME}"
# Register the chain to UC
uc_registered_model_info = mlflow.register_model(model_uri=logged_chain_info.model_uri, name=MODEL_NAME_FQN)
uc_registered_model_info

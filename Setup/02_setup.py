# Databricks notebook source
#DBR 14.3 LTS
%pip install -U databricks-sdk mlflow-skinny[databricks]
dbutils.library.restartPython()

# COMMAND ----------

# use ml runtime or install mlflow
# update params where appropriate, 
# in next cell also set to appropriate PAT, recommended to use Service Principals instead of personal PAT like we do in this demo
secret_scope_name = "feedback_app"
catalog = 'dbdemos'
schema =  'maxcarduner'
model_name = 'brand_tone_chain'
entity_name = f'{catalog}.{schema}.{model_name}'
entity_version = 5
host_url = ''
warehouse_id = ''

# COMMAND ----------

# secrets
from dbruntime.databricks_repl_context import get_context
from databricks.sdk import WorkspaceClient

# just an example on how to get your current PAT but may want to change expiration of it or use a service principal
context = get_context()
databricks_api_token = context.apiToken 

# Add secrets to desired secret scope and key in Databricks Secret Store
w = WorkspaceClient()
try:
  w.secrets.create_scope(scope=secret_scope_name)
except:
  pass #already created

w.secrets.put_secret(scope=secret_scope_name, key='api_token', string_value=databricks_api_token)

# COMMAND ----------

for i in ['host_url', 'full_host_url', 'warehouse_id']:
  print(i)

# COMMAND ----------

# from databricks.sdk import WorkspaceClient
# w = WorkspaceClient()
w.secrets.put_secret(scope=secret_scope_name, key='host_url', string_value=host_url)
w.secrets.put_secret(scope=secret_scope_name, key='full_host_url', string_value=f'https://{host_url}')
w.secrets.put_secret(scope=secret_scope_name, key='warehouse_id', string_value=warehouse_id)

# COMMAND ----------

# create feedback table
spark.sql(f'CREATE TABLE IF NOT EXISTS {catalog}.{schema}.feedback_log (timestamp timestamp, user_message string, assistant_message string, feedback string)')

# COMMAND ----------

w.secrets.put_secret(scope=secret_scope_name, key='feedback_table', string_value=f"{catalog}.{schema}.feedback_log")

# COMMAND ----------

import mlflow
from mlflow.deployments import get_deploy_client
mlflow.set_registry_uri("databricks-uc")
client = get_deploy_client("databricks")

endpoint = client.create_endpoint(
    name="voice-tone-chatbot",
    config={
        "served_entities": [
            {
                "name": "voice-tone-chatbot",
                "entity_name": entity_name,
                "entity_version": entity_version,
                "workload_size": "Small",
                "scale_to_zero_enabled": True,
                "environment_vars": {
                    "DATABRICKS_TOKEN": '{{secrets/'+secret_scope_name+'/api_token}}',
                    "DATABRICKS_HOST": '{{secrets/'+secret_scope_name+'/host_url}}'
                }
            }
        ],
        "traffic_config": {
            "routes": [
                {
                    "served_model_name": "voice-tone-chatbot",
                    "traffic_percentage": 100
                }
            ]
        },
        "auto_capture_config":{
                    "catalog_name": catalog,
                    "schema_name": schema
        }
    }
)

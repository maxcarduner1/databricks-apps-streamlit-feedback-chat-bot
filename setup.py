# Databricks notebook source
secret_scope_name = "review_app_demo"
catalog = 'users'
schema =  'max_carduner'
entity_name = f'{catalog}.{schema}.review_app_no_rag'
entity_version = 8

# COMMAND ----------

# secrets
from dbruntime.databricks_repl_context import get_context
from databricks.sdk import WorkspaceClient

secret_scope_name = "review_app_demo"

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


w.secrets.put_secret(scope=secret_scope_name, key='host_url', string_value='adb-2338896885246877.17.azuredatabricks.net')
w.secrets.put_secret(scope=secret_scope_name, key='full_host_url', string_value='https://adb-2338896885246877.17.azuredatabricks.net')
w.secrets.put_secret(scope=secret_scope_name, key='warehouse_id', string_value='fe3ded27521e7f40')

# COMMAND ----------

spark.sql(f'CREATE TABLE IF NOT EXISTS {catalog}.{schema}.feedback_log (timestamp timestamp, user_message string, assistant_message string, feedback string)')

# COMMAND ----------

w.secrets.put_secret(scope=secret_scope_name, key='feedback_table', string_value=f"{catalog}.{schema}.feedback_log")

# COMMAND ----------

# MAGIC %pip install mlflow
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import mlflow
from mlflow.deployments import get_deploy_client
mlflow.set_registry_uri("databricks-uc")
client = get_deploy_client("databricks")

endpoint = client.create_endpoint(
    name="brand-tone-bot",
    config={
        "served_entities": [
            {
                "name": "brand-tone-chatbot",
                "entity_name": entity_name,
                "entity_version": entity_version,
                "workload_size": "Small",
                "scale_to_zero_enabled": True,
                "environment_vars": {
                    "MY_ENV_VAR": "api_token", 
                    "MY_SECRET_VAR": f"{{secrets/{secret_scope_name}/api_token}}",
                    "MY_ENV_VAR": "host_url", 
                    "MY_SECRET_VAR": f"{{secrets/{secret_scope_name}/host_url}}",
                    "MY_ENV_VAR": "warehouse_id", 
                    "MY_SECRET_VAR": f"{{secrets/{secret_scope_name}/warehouse_id}}"
                }
            }
        ],
        "traffic_config": {
            "routes": [
                {
                    "served_model_name": "brand-tone-chatbot",
                    "traffic_percentage": 100
                }
            ]
        }
    }
)

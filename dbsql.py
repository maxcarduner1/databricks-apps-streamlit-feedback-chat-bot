import requests

def execute_sql_statement(databricks_host, databricks_token, warehouse_id, sql_statement):
    """
    Executes a SQL statement on a Databricks SQL warehouse.

    Parameters:
    - databricks_host (str): The Databricks host URL 
    - databricks_token (str): The Databricks token for authentication.
    - warehouse_id (str): The ID of the Databricks SQL warehouse.
    - sql_statement (str): The SQL statement to execute.
    
    Returns:
    - dict: The response containing the statement execution result.
    """

    
    # Define the headers
    headers = {
        "Authorization": f"Bearer {databricks_token}",
        "Content-Type": "application/json"
    }

    # Define the payload
    payload = {
        "warehouse_id": warehouse_id,
        "statement": sql_statement,
        "wait_timeout": "0s"
    }

    # Send the POST request to execute the SQL statement
    response = requests.post(
        f"{databricks_host}/api/2.0/sql/statements/",
        headers=headers,
        json=payload
    )

    # Check for errors in the response
    if response.status_code != 200:
        raise Exception(f"Error executing SQL statement: {response.text}")

    # Parse the response JSON
    response_data = response.json()

    # Extract and print statement_id and next_chunk_internal_link if available
    sql_statement_id = response_data.get('statement_id')
    try:
        next_chunk_internal_link = response_data.get('result', {}).get('next_chunk_internal_link')
        print(f"NEXT_CHUNK_INTERNAL_LINK={next_chunk_internal_link}")
    except:
        print("No Chunk")

    # Print extracted values
    print(f"SQL_STATEMENT_ID={sql_statement_id}")
    
    # Return the full response data for further processing
    return response_data


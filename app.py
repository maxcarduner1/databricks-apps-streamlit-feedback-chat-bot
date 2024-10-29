import logging
import os
from datetime import datetime
import streamlit as st
from streamlit_feedback import streamlit_feedback
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
from dotenv import load_dotenv
import dbsql
from supabase import create_client, Client

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the Databricks Workspace Client
if ".env" in os.listdir(os.curdir):
    # this is for local development
    w = WorkspaceClient(host=os.getenv("FULL_DATABRICKS_HOST"), token=os.getenv("DATABRICKS_TOKEN_VALUE"))
else:
    # this will be engaged when the app is running in Databricks
    w = WorkspaceClient()

# Ensure environment variable is set correctly
assert os.getenv('SERVING_ENDPOINT'), "SERVING_ENDPOINT must be set in app.yaml."

def handle_feedback(**response_dict):
    prompt = response_dict.get("prompt")
    assistant_response = response_dict.get("assistant_response")
    if 'fb_k' in st.session_state:
        # Only log feedback if it has been submitted
        feedback = st.session_state.fb_k
        current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print("LOGGING FEEDBACK!")
        try:
            if os.getenv("LOG_METHOD") == "dbsql":
                pat = os.getenv("DATABRICKS_TOKEN_VALUE")
                databricks_host = os.getenv("FULL_DATABRICKS_HOST")
                warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID_VALUE")
                table_name = os.getenv("CHAT_LOG_TABLE")
                sql_statement = f"""INSERT INTO {table_name} VALUES ("{current_timestamp}", "{prompt.replace('"', "'")}", "{assistant_response.replace('"', "'")}", "{feedback['text'].replace('"', "'")}")"""
                dbsql.execute_sql_statement(databricks_host=databricks_host, databricks_token=pat, warehouse_id=warehouse_id, sql_statement=sql_statement)
                st.toast("✔️ Feedback received!")
            else:
                url: str = os.getenv("SUPABASE_URL")
                key: str = os.getenv("SUPABASE_KEY")
                supabase: Client = create_client(url, key)
                chat_data = {
                    'user_message': prompt,
                    'assistant_response': assistant_response,
                    'feedback': feedback,
                    'timestamp': 'now()'
                }
                supabase.table(os.getenv("CHAT_LOG_TABLE")).insert(chat_data).execute()
                st.toast("✔️ Feedback received!")
        except Exception as e:
            st.toast(f"X Feedback not received, error with feedback mechanism {e}!")
            
            

# Streamlit app
if "visibility" not in st.session_state:
    st.session_state.visibility = "visible"
    st.session_state.disabled = False

st.title("🧱 Chatbot App")
st.write(f"A basic chatbot using the your own serving endpoint and allows users to log feedback on assistant responses.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("What is up?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    messages = [ChatMessage(role=ChatMessageRole.SYSTEM, content="You are a helpful assistant."),
                ChatMessage(role=ChatMessageRole.USER, content=prompt)]

    # Display assistant response in chat message container
    # Query the Databricks serving endpoint
    try:
        response = w.serving_endpoints.query(
            name=os.getenv("SERVING_ENDPOINT"),
            messages=messages,
            max_tokens=400,
        )
        assistant_response = response.choices[0].message.content

        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            st.markdown(assistant_response)
    except Exception as e:
        st.error(f"Error querying model: {e}")
        assistant_response = "Error retrieving response"

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": assistant_response})

    # Feedback form for thumbs feedback and optional explanation
    with st.form('form'):
        streamlit_feedback(
            feedback_type="thumbs",
            optional_text_label="[Optional] Please provide an explanation",
            align="flex-start", 
            key='fb_k'
        )

        st.form_submit_button('Save feedback', on_click=handle_feedback, kwargs={"prompt":prompt, "assistant_response": assistant_response})

import json
from typing import Optional

import httpx
import litellm
import redis
import requests
from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel

import env as config

router = APIRouter()

_headers = {
    'stsk': config.web_server_secret,
    'x-server-key': config.web_server_secret,
    'Content-Type': 'application/json',
}

class UnstructuredLiteLLMCompletionResponse(BaseModel):
    response: str
    completion_tokens: int
    prompt_tokens: int
    total_tokens: int
    tries: int

# Redis for session-based chat history
redis_client = redis.Redis(
    host='redis-15082.c56.east-us.azure.redns.redis-cloud.com',
    password='1wNZNp0FW09f7zhIkncOudeduHo3DF2k',
    port=15082,
    decode_responses=True,
)

# Data Model for Chat Requests
class ChatRequest(BaseModel):
    session_id: str
    model_name: str  # Choose from LLM_MODELS (e.g., "claude", "gpt-4")
    message: str

# Helper function to store chat history in Redis
def save_session(session_id, history):
    redis_client.set(session_id, json.dumps(history))

# Helper function to retrieve chat history
def get_session(session_id):
    data = redis_client.get(session_id)
    return json.loads(data) if data else []

# API Endpoint to Handle Chat
@router.post('/chat')
async def chat_with_llm(
    chat_request: ChatRequest,
) -> UnstructuredLiteLLMCompletionResponse:
    session_id = chat_request.session_id
    model_name = chat_request.model_name.lower() or 'azure/gpt-4o'
    message = chat_request.message

    # Retrieve previous chat history
    chat_history = get_session(session_id) or []

    # Append user message to chat history
    messages = chat_history if isinstance(chat_history, list) else []

    # Append the new user message
    messages.append(
        {'role': 'user', 'content': str(message)}
    )  # Ensure content is a string

    try:
        # Call LiteLLM directly
        response = await litellm.acompletion(
            api_key=config.litellm_proxy_api_key,
            base_url=config.litellm_proxy_api_base,
            model=model_name or 'azure/gpt-4o',
            messages=messages,
        )

        assistant_response = response['choices'][0]['message']['content']

        # Summarize response for shorter context retention
        summary_response = await litellm.acompletion(
            api_key=config.litellm_proxy_api_key,
            base_url=str(config.litellm_proxy_api_base),
            model=model_name or 'azure/gpt-4o',
            messages=[
                {
                    'role': 'system',
                    'content': 'Summarize the response while keeping key details.',
                },
                {'role': 'user', 'content': assistant_response},
            ],
        )

        summarized_content = summary_response['choices'][0]['message']['content']

        # Append assistant response to chat history
        chat_history.append({'role': 'assistant', 'content': summarized_content})

        # Save updated chat history
        save_session(session_id, chat_history)

        return UnstructuredLiteLLMCompletionResponse(
            response=response['choices'][0]['message']['content'],
            completion_tokens=response['usage']['completion_tokens'],
            prompt_tokens=response['usage']['prompt_tokens'],
            total_tokens=response['usage']['total_tokens'],
            tries=1,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class UserQueryDetails(BaseModel):
    user_query: str
@router.post('/chat/{connector_id}')
async def query_on_jira(connector_id: str, user_query_details: UserQueryDetails, session: Optional[str] = None):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url=f"{config.klot_data_service_url}/actions/jira/config/{connector_id}", headers={"x-server-key": config.web_server_secret})
            response.raise_for_status()
            configuration = response.json()
            jira_config_data = configuration.get("config", {}).get("config", {})
        headers = {
            "Accept": "application/json",
        }
        account_url = jira_config_data["account_url"]
        search_url = f"{account_url}/rest/api/3/users/search"

        email = jira_config_data["email"]
        token = jira_config_data["api_token"]

        response = requests.get(search_url, headers=headers, auth=(email, token))

        jira_response = response.json()
        temp_users_data = [user for user in jira_response if user.get("accountType") == "atlassian"]

        if user_query_details.user_query:
            message_check = f"""Convert the following user request into a valid Jira Query Language (JQL) query: {user_query_details.user_query}. Ensure the generated JQL query is syntactically correct and does not throw any errors. Use {temp_users_data} to match user details such as accountId, email, or name.

If the query involves a field that requires an operator, use only the valid JQL operators: =, !=, <, >, <=, >=, ~, !~, IN, NOT IN, IS, IS NOT.
If the query involves a field that should not be empty, use IS NOT NULL instead of IS NOT EMPTY.
Ensure field names are correct as per Jira's schema.
Return only the JQL query as a string and nothing else, do not include any additional information or metadata. do  not even mention jql , just return the JQL query generated as string"""
            chat_request = ChatRequest(
                session_id=session or None,
                model_name='azure/gpt-4o',
                message=message_check,
            )
            response = await chat_with_llm(chat_request=chat_request)
            jql_query = response.response

            print("jql_query", jql_query)

        account_url = jira_config_data["account_url"]

        email = jira_config_data["email"]
        token = jira_config_data["api_token"]

        url = f"{account_url}/rest/api/3/search"
        headers = {
            "Accept": "application/json"
        }
        auth = (email, token)
        params = {"jql": jql_query, "maxResults": 10}

        response = requests.get(url, headers=headers, params=params, auth=auth)

        if response.status_code == 200:
            return response.json()["issues"]
        else:
            return f"Error fetching Jira tickets: {response.text}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import datetime
from datetime import timedelta
import json
from typing import List, Literal, Optional

import httpx
import requests
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from temporalio.client import Client

import env
from server.common.database.mongodb import client as mongodb
from server.config.collections import collections
from server.config.llm_caller import LLMCaller
from server.connector_router import ProjectDetails

# from server.temporal.workflow import UserCallsWorkflow

users_collection = mongodb.db[collections.users]
summaries_collection = mongodb.db[collections.summaries]
project_details_collection = mongodb.db[collections.project_data]

router = APIRouter()


class TableDetails(BaseModel):
    table_name: str
    table_id: str

class AgentflowDetails(BaseModel):
    agentflow_name: str
    agentflow_id: str

class UserDetails(BaseModel):
    jira_connector_id: Optional[str]
    slack_connector_id: Optional[str]
    voice_connector_id: Optional[str]
    email_connector_id: Optional[str]
    master_connector_id: Optional[str]
    bland_connector_id: Optional[str]
    table_details: Optional[list[TableDetails]]
    agentflow_details: Optional[list[AgentflowDetails]]
    projectId: str
    user_id: str
    token: str

async def  send_email_to_master(email_id: str, content: str, email_connector_id: str):
    try:
        blocker_prompt = f"""
            based on the data provided {content}, generate a neat body of a email addressing as a AI project Manager named Mario, to send to {email_id} for the quick updates on the tickets and if the ticket require any update from the user, if the ticket has any blocker or not.
            make sure the body is well constructed to format the email as a professional email, visible with neat spacing looks good and easy to read,
            also have a clear structured crisp subject line to make it easy to read and understand the email.
            return the output as dict containing fields
            body - generated email body
            subject - generated subject line
            return the output as stringified json value of these fields in a dict, return only the stringified json value only, do not return anything else, do not mention anything, do not even mention json also, just return the stringified json value
            """
        payload = {
            "model": "azure/gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": blocker_prompt,
                },
            ],
        }
        llm_caller = LLMCaller(payload)
        response = await llm_caller.llm_unstructured_completion()
        content = response.response
        email = json.loads(content)
        body = email["body"]
        subject = email["subject"]

        async with httpx.AsyncClient(timeout=600) as client:

            json_data = {
                'subject' : subject,
                'recipient_emails' : [email_id],
                'body' : body
            }
            headers = {
                "x-server-key": env.web_server_secret
            }
            print("Request JSON:", json_data)
            print("Request Headers:", headers)
            response = await client.post(f"{env.klot_data_service_url}/actions/email/send/{email_connector_id}", json=json_data, headers=headers)
            print("Response Status Code:", response.status_code)
            print("Response Content:", response.text)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
async def make_call(phone_number: str, content: str, voice_connector_id: str):
    try:
        async with httpx.AsyncClient() as client:
            data = {
                "phone_number": phone_number,
                "initial_prompt": content,
                "message" : "Hello! This is Mario - your AI project Manager calling to understand the status of the tickets you are working on",
            }
            print("data", data)
            response = await client.post(f"{env.klot_data_service_url}/actions/voice/make_call/{voice_connector_id}",json=data,headers={"x-server-key": env.web_server_secret})
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def get_tickets_last_n_hours(account_url: str, email: str, token: str, user_id: str, n : str):
    """
    Fetch tickets updated in the last 'n' hours.
    """
    n = int(n)

    headers = {
        "Accept": "application/json",
    }
    time_n_hours_ago = (datetime.datetime.utcnow() - datetime.timedelta(hours=n)).strftime("%Y-%m-%d %H:%M")

    # Jira Query Language (JQL) to filter issues updated in the last 'n' hours
    jql_query = f'assignee = "{user_id}" AND updated >= "{time_n_hours_ago}" ORDER BY updated DESC'

    search_url = f"{account_url}/rest/api/2/search?jql={jql_query}"

    response = requests.get(search_url, headers=headers, auth=(email, token ))

    if response.status_code == 200:
        return response.json().get("issues", [])

    return []
async def manage_tickets(tickets: list, account_url: str, email: str, api_token: str):
    """
    Manage the tickets and return the concerns.
    """
    try:
        tickets_summary = {}
        if tickets:
            for ticket in tickets:

                print("ticket", ticket["key"])
                key = ticket["key"]
                url = f"{account_url}/rest/api/3/issue/{key}"

                # Prepare headers
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }

                # Make GET request to retrieve ticket details
                response = requests.get(
                    url, headers=headers, auth=(email, api_token)
                )
                content = f"""
                    you are a ai project manager, you have a ticket with the following details: {ticket},
                    your task is to find if the ticket is up to date , being updated by developer timely and if the ticket is being resolved in time also check the ticket status according to the comments made by the developer with considering the due date and the time of the ticket creation with time logs, if things are fine with ticket return None else return the concerns to be resolved as a string value"""
                payload = {
                    "model": "azure/gpt-4o",
                    "messages": [
                        {
                            "role": "user",
                            "content": content,
                        },
                    ],
                }
                llm_caller = LLMCaller(payload)
                response = await llm_caller.llm_unstructured_completion()
                summary_of_ticket = response.response
                if summary_of_ticket:
                    tickets_summary[ticket["key"]] = summary_of_ticket
        return tickets_summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def summarize_tickets(n: int ,email_id: str, phone_number: str,  jira_account_url: str, email: str, token: str,accountId: Optional[str] = None):
    try:
        if accountId is None:
            url = f"{jira_account_url}/rest/api/3/user/search"

            # Prepare headers
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }

            # Prepare query parameters
            params = {"query": email_id}

            # Make GET request to search users
            response = requests.get(
                url,
                headers=headers,
                auth=(email, token),
                params=params,
            )
            response.raise_for_status()

            # Parse the response
            response_data = response.json()
            accountId = response_data["accountId"]
            if n == 0:
                return None

            tickets = await get_tickets_last_n_hours(jira_account_url, email, token, accountId, n)
            return manage_tickets(tickets, jira_account_url, email, token)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save/user/details")
async def save_details(data: UserDetails):
    try:
        user_details = await users_collection.find_one({"user_id": data.user_id})
        if user_details is not None:
            await users_collection.update_one({"user_id": data.user_id}, {"$set": data.model_dump()})
        else:
            await users_collection.insert_one(data.model_dump())

        return {"message": "Data saved successfully"}
    except HTTPException as e:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update/jira/details/table/{user_id}")
async def update_jira_details_table(user_id: str):
    try:
        user = await mongodb.db.users.find_one({"user_id": user_id})
        users_tables = user["table_details"]
        projectID = user["projectId"]
        jira_connector_id = user["jira_connector_id"]
        async with httpx.AsyncClient() as client:
            response = await client.get(url=f"{env.klot_data_service_url}/actions/jira/config/{jira_connector_id}", headers={"x-server-key": env.web_server_secret})
            response.raise_for_status()
            configuration = response.json()
            jira_config_data = configuration.get("config", {}).get("config", {})
            account_url = jira_config_data["account_url"]
            email = jira_config_data["email"]
            api_token = jira_config_data["api_token"]
        for user_table in users_tables:
            if user_table["table_name"] == "Employee Details":
                table_id = user_table["table_id"]
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{env.klot_data_service_url}/storage/{projectID}/{table_id}?page=1&page_size=1000000", headers={"x-server-key": env.web_server_secret})
                    response.raise_for_status()
                    users = response.json()

                    for user in users:
                        async with httpx.AsyncClient() as inner_client:
                            url = f"{account_url}/rest/api/3/user/search"

                            # Prepare headers
                            headers = {
                                "Accept": "application/json",
                                "Content-Type": "application/json",
                            }

                            # Prepare query parameters
                            params = {"query": user["emailAddress"]}

                            # Make GET request to search users
                            inner_response = await inner_client.get(
                                url,
                                headers=headers,
                                auth=(email, api_token),
                                params=params,
                            )
                            if inner_response.status_code == 200:
                                user_detail = inner_response.json()
                                combined_user = {**user, **user_detail}
                                user.update(combined_user)
                                async with httpx.AsyncClient() as service_client:
                                    record_id = str(user["_id"])
                                    await service_client.put(url=f"{env.klot_data_service_url}/storage/{projectID}/{table_id}/{record_id}",json=user, headers={"x-server-key": env.web_server_secret})
    except HTTPException as e:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/insert/new/record/{user_id}/{inserted_id}")
async def new_record_insertion(user_id: str, inserted_id: str):
    try:
        users = await users_collection.find_one({"user_id": user_id})
        for table in users["table_details"]:
            if table["table_name"] == "Employee Details":
                table_id = table["table_id"]
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{env.klot_data_service_url}/storage/{users['projectId']}/{table_id}/{inserted_id}", headers={"x-server-key": env.web_server_secret})
                    response.raise_for_status()
                    user = response.json()
                    async with httpx.AsyncClient() as inner_client:
                        url = f"{users['account_url']}/rest/api/3/user/search"

                        # Prepare headers
                        headers = {
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                        }

                        # Prepare query parameters
                        params = {"query": user["emailAddress"]}

                        # Make GET request to search users
                        inner_response = await inner_client.get(
                            url,
                            headers=headers,
                            auth=(users['email'], users['api_token']),
                            params=params,
                        )
                        if inner_response.status_code == 200:
                            user_detail = inner_response.json()
                            combined_user = {**user, **user_detail}
                            user.update(combined_user)
                            async with httpx.AsyncClient() as service_client:
                                record_id = str(user["_id"])
                                await service_client.put(url=f"{env.klot_data_service_url}/storage/{users['projectId']}/{table_id}/{record_id}", json=user, headers={"x-server-key": env.web_server_secret})
    except HTTPException as e:
        raise e

async def make_call_using_bland(user_id: str, call_prompt: str, phone_number: str):
    try:
        user_details = await users_collection.find_one({"user_id": user_id})
        if user_details is None:
            raise HTTPException(status_code=404, detail="User Details not found")
        if user_details.get("bland_connector_id"):
            bland_connector_id = user_details["bland_connector_id"]
            async with httpx.AsyncClient() as client:
                response = await client.get(url=f"{env.klot_data_service_url}/actions/bland/config/{bland_connector_id}", headers={"x-server-key": env.web_server_secret})
                response.raise_for_status()
                bland_configuration = response.json()
                bland_api_key = bland_configuration.get("config", {}).get("config", {}).get("authorization_key", "")
        else:
            bland_api_key = env.bland_api_key

        print("hack service", f"{env.hack_service}/update/conversation/history")

        print("bland_api_key", bland_api_key)
        url = "https://api.bland.ai/v1/calls"

        payload = {
            "phone_number": f"+{phone_number}",
            "voice": "josh",
            "task" : f"{call_prompt}, also send the user id value after the call {user_id}",
            "first_sentence": "Hello There! This is Mario - your AI project Manager calling to understand the status of the task you are working on",
            "wait_for_greeting": False,
            "block_interruptions": True,
            "max_duration": 12,
            "temperature": 0.5,
            "model": "base",
            "language": "en",
            "retry": {},
            "timezone": "Asia/Kolkata",
            "record": True,
            "interruption_threshold": 100,
            "background_track": "none",
            "endpoint": "https://api.bland.ai",
            "voicemail_action": "hangup",
            "webhook": f"{env.hack_service}/update/conversation/history",
            "summary_prompt": f"After the Call, Summarize the conversation along with the user id value {user_id} value which has to be returned for sure in the response",
        }
        headers = {
            'Authorization': bland_api_key,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url=url, json=payload, headers=headers)
            print("response", response)
            response.raise_for_status()
            response_data = response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule/bland/calls/{user_id}")
async def schedule_bland_calls(user_id: str, n: Optional[int] = 0):
    try:
        user_details = await users_collection.find_one({"user_id": user_id})
        if user_details is None:
            raise HTTPException(status_code=404, detail="User Details not found")
        for table in user_details["table_details"]:
            if table["table_name"] == "Employee Details":
                employee_table_id = table["table_id"]
                token = user_details["token"]
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{env.klot_data_service_url}/storage/{user_details['projectId']}/{employee_table_id}?page=1&page_size=1000000", headers={"x-server-key": env.web_server_secret,"Authorization":f"Bearer {token}"})
                    response.raise_for_status()
                    users = response.json()
        for user in users["records"]:
            print("users", user)
            task_goal = user.get("task_goal") if user.get("task_goal") is not None else None
            task_status = user.get("task_status") if user.get("task_status") is not None else "to do"
            phone_number = user.get("phone_number") if user.get("phone_number") is not None else None
            last_call_summary  = user.get("last_call_summary") if user.get("last_call_summary") is not None else None
            employee_email = user["emailAddress"]
            employee_name = user["displayName"]
            email_connector_id = user_details.get("email_connector_id") if user_details.get("email_connector_id") is not None else None
            master_connector_id = user_details.get("master_connector_id") if user_details.get("master_connector_id") is not None else None
            if task_goal is None:
                jira_connector_id = user_details.get("jira_connector_id") if user_details.get("jira_connector_id") is not None else None
                if jira_connector_id is not None:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(url=f"{env.klot_data_service_url}/actions/jira/config/{jira_connector_id}", headers={"x-server-key": env.web_server_secret})
                        response.raise_for_status()
                        configuration = response.json()
                        jira_config_data = configuration.get("config", {}).get("config", {})
                    tickets_summary = await summarize_tickets(n=n, email_id=employee_email,tickets=last_call_summary, account_url=jira_config_data["account_url"], email=jira_config_data["email"], api_token=jira_config_data["api_token"])
                    if tickets_summary is not None:
                        call_prompt = f"""
                            you are a ai project manager, you have tickets of the user {employee_name} with the following details: {tickets_summary} along with the previous conversation data {last_call_summary},
                            your task is to ask the user for quick updates on the tickets mentioned, also find out if the user requires any assistance in any ticket, if there is any blocker, ask for the status of the tickets to the user, make sure to maintain soft tone while talking, talk like a friendly manager
                            """

                        if phone_number and task_status != "done":
                            # await make_call(phone_number=phone_number, content=call_prompt, voice_connector_id=voice_connector_id)
                            await make_call_using_bland(phone_number=phone_number, call_prompt=call_prompt, user_id=user_id)
                        elif email_connector_id and task_status != "done":
                            await send_email_to_master(email_id=employee_email, content=call_prompt, email_connector_id=email_connector_id)
                        else:
                            raise HTTPException(status_code=400, detail="No valid connector found for the user")
            else:
                call_prompt = f"""
                    you are a ai project manager, you have task of the user {employee_name} with the following details: {task_goal} along with the previous conversation data {last_call_summary},
                    your task is to ask the user for quick updates on the tickets mentioned, also find out if the user requires any assistance in any ticket, if there is any blocker, ask for the status of the tickets to the user, make sure to maintain soft tone while talking, talk like a friendly manager"""

                if phone_number and task_status != "done":
                    # await make_call(phone_number=phone_number, content=call_prompt, voice_connector_id=voice_connector_id)
                    await make_call_using_bland(phone_number=phone_number, call_prompt=call_prompt, user_id=user_id)
                elif email_connector_id and task_status != "done":
                    await send_email_to_master(email_id=employee_email, content=call_prompt, email_connector_id=email_connector_id)
                else:
                    raise HTTPException(status_code=400, detail="No valid connector found for the user")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule/the/calls/{user_id}/{n}")
async def schedule_calls(user_id: str, n: int):
    try:
        user_details = await users_collection.find_one({"user_id": user_id})
        if user_details is None:
            raise HTTPException(status_code=404, detail="User Details not found")
        for table in user_details["table_details"]:
            if table["table_name"] == "Employee Details":
                employee_table_id = table["table_id"]
                token = user_details["token"]
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{env.klot_data_service_url}/storage/{user_details['projectId']}/{employee_table_id}?page=1&page_size=1000000", headers={"x-server-key": env.web_server_secret,"Authorization":f"Bearer {token}"})
                    print("response", response)
                    response.raise_for_status()
                    users = response.json()
        for user in users["records"]:
            print("users", user)
            task_goal = user["task_goal"]
            phone_number = user["phone_number"]
            last_call_summary  = user["last_call_summary"]
            employee_email = user["emailAddress"]
            employee_name = user["displayName"]
            voice_connector_id = user_details["voice_connector_id"]
            email_connector_id = user_details["email_connector_id"]
            master_connector_id = user_details["master_connector_id"]
            if task_goal is None:
                jira_connector_id = user_details.get("jira_connector_id")
                if jira_connector_id is not None:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(url=f"{env.klot_data_service_url}/actions/jira/config/{jira_connector_id}", headers={"x-server-key": env.web_server_secret})
                        response.raise_for_status()
                        configuration = response.json()
                        jira_config_data = configuration.get("config", {}).get("config", {})
                    tickets_summary = await summarize_tickets(n=n, email_id=employee_email,tickets=last_call_summary, account_url=jira_config_data["account_url"], email=jira_config_data["email"], api_token=jira_config_data["api_token"])
                    # your task is to ask the user for quick updates on the tickets mentioned, also find out if the user requires any assistance in any ticket, if there is any blocker, ask for the status of the tickets to the user, make sure to make function call to master executor with {employee_email} also {employee_name} , these has to be passed to the executeFlow actionSelector executor as the goal for the execution with email , name of employee for sure without missing, also make sure to verify the user with name before conversation,
                    #     the goal to executeFlow function call is use the email id {employee_email} and name {employee_name} to identify the user then update the history of the user with the updates of the user about the task assigned"""
                    # based on the updates received from the user, update the history of the user with the updates of the user about the task assigned with the email id {employee_email} and name {employee_name}
                    call_prompt = f"""
                        you are a ai project manager, you have tickets of the user {employee_name} with the following details: {tickets_summary} along with the previous conversation data {last_call_summary},
                        your task is to ask the user for quick updates on the tickets mentioned, also find out if the user requires any assistance in any ticket, if there is any blocker, ask for the status of the tickets to the user, 
                        """

                    if voice_connector_id:
                        await make_call(phone_number=phone_number, content=call_prompt, voice_connector_id=voice_connector_id)
                    elif email_connector_id:
                        await send_email_to_master(email_id=employee_email, content=call_prompt, master_connector_id=master_connector_id)
                    else:
                        raise HTTPException(status_code=400, detail="No valid connector found for the user")
            else:
                call_prompt = f"""
                    you are a ai project manager, you have task of the user {employee_name} with the following details: {task_goal} along with the previous conversation data {last_call_summary},
                    your task is to ask the user for quick updates on the tickets mentioned, also find out if the user requires any assistance in any ticket, if there is any blocker, ask for the status of the task to the user, make sure to make function call to master executor with {employee_email} also {employee_name} , these has to be passed to the master executor as the goal for the execution with email , name of employee for sure without missing, also make sure to verify the user with name before conversation"""

                voice_connector_id = user_details["voice_connector_id"]
                if voice_connector_id:
                    await make_call(phone_number=phone_number, content=call_prompt, voice_connector_id=voice_connector_id)
                elif email_connector_id:
                    await send_email_to_master(email_id=employee_email, content=call_prompt, master_connector_id=master_connector_id)
                else:
                    raise HTTPException(status_code=400, detail="No valid connector found for the user")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ScheduleData(BaseModel):
    schedule_type: Literal["once", "recurring"]
    schedule: Optional[str]
    cron_expression: Optional[str]
# @router.post("/schedule/calls/{user_id}/{n}")
# async def start_schedule(user_id:str, n: int, schedule_data: ScheduleData):
#     try:
#         temporal_url = env.temporal_url
#         user_details = await users_collection.find_one({"user_id": user_id})
#         user_details = UserDetails(**user_details)
#         if user_details is None:
#             raise HTTPException(status_code=404, detail="User Details not found")
#         client = await Client.connect(temporal_url)
#         await client.schedule.create(
#             id=f"user_details_schedule_{user_id}",
#             workflow=UserCallsWorkflow.run,
#             workflow_args=[user_details],
#             schedule = schedule_data.schedule if schedule_data.schedule else None,
#             cron_expression=schedule_data.cron_expression if schedule_data.cron_expression else None,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop/calls/{user_id}")
async def stop_schedule(user_id:str):
    try:
        temporal_url = env.temporal_url
        client = await Client.connect(temporal_url)
        await client.get_schedule_handle(id=f"user_details_schedule_{user_id}").delete()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ConversationContent(BaseModel):
    conversation_content: str
    user_id: str
@router.post("/find/user")
async def find_user(conversation: ConversationContent):
    try:
        print(conversation)
        conversation_content = conversation.conversation_content
        user_id = conversation.user_id
        conv_content = f"""

        you are a ai project manager, you have a conversation with the following details: {conversation_content},
        your task is to find the name of the user with whom the AI is talking to, return the name of the user if found as a string value if not found return null,
        return the output with name as string only, nothing else except name should be returned, do not mention anything else except the name of the user"""
        payload = {
            "model": "azure/gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": conv_content,
                },
            ],
        }
        llm_caller = LLMCaller(payload)
        response = await llm_caller.llm_unstructured_completion()
        name = response.response

        user_details = await users_collection.find_one({"user_id": user_id})
        if user_details is None:
            raise HTTPException(status_code=404, detail="User Details not found")
        for table in user_details["table_details"]:
            if table["table_name"] == "Employee Details":
                table_id = table["table_id"]
                token = user_details["token"]
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{env.klot_data_service_url}/storage/{user_details['projectId']}/{table_id}?page=1&page_size=1000000", headers={"x-server-key": env.web_server_secret,"Authorization":f"Bearer {token}"})
                    response.raise_for_status()
                    users = response.json()
                    records = users["records"]
                    names = [user["displayName"] for user in records]
                    content = f"""

                        you are a ai project manager, you have a list of users with the following details: {names},
                        your task is to find if the user is present in the list or not, if the user is present return the name of the user else return None,
                        return the name of the user if any name matches with the {name} from the provided names
                        return the full name matched with the names provided, returned the name exactly how it is there in the names provided which matched the name to provided name
                        return the full name only as string value, nothing else except the name should be returned, do not mention anything else except the name of the user"""
                    payload = {
                        "model": "azure/gpt-4o",
                        "messages": [
                            {
                                "role": "user",
                                "content": content,
                            },
                        ],
                    }

                    llm_caller = LLMCaller(payload)

                    response = await llm_caller.llm_unstructured_completion()
                    name = response.response
                    if name is None:
                        raise HTTPException(status_code=404, detail="User not found")
                    return {"name": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update/conversation/history")
async def history_received(request: Request):
    try:
        data = await request.json()
        # print("data", data)
        content = f"""
        based on the data {data}, find the value of user_id from the data, return the user_id as a string value, do not return anything else except the user_id, do not mention anything, just return the user_id value only
        """
        payload = {
            "model": "azure/gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": content,
                },
            ],
        }

        llm_caller = LLMCaller(payload)

        llm_response = await llm_caller.llm_unstructured_completion()
        user_id = llm_response.response
        print("user_id", user_id)
        user_details = await users_collection.find_one({"user_id": user_id})
        master_connector_id = user_details.get("master_connector_id") if user_details is not None else None
        notify_through_email_connector_id = user_details.get("notify_through_email_connector_id") if user_details is not None else None
        token = user_details["token"]
        if user_details is None:
            raise HTTPException(status_code=404, detail="User Details not found")
        # for agentflow in user_details["agentflow_details"]:
        #     if agentflow["agentflow_name"] == "Follow Up":
        #         agentflow_id = agentflow["agentflow_id"]
        #         async with httpx.AsyncClient() as client:
        #             user_name = "follow_up_service"
        #             input_data = {"agentflow_id":agentflow_id,"goal" : f"with the data of the converasation history provided {data} perform the action"}
        #             response = await client.get(f"{env.klot_data_service_url}/execute_flow/common?user_id={user_id}&&user_name={user_name}", headers={"x-server-key": env.web_server_secret}, json=input_data)
        #             response.raise_for_status()
        #             configuration = response.json()
        projectID = user_details["projectId"]
        email_address_of_user = None
        history_table_id = None
        task_goal_of_user = None
        for table in user_details.get("table_details"):
            if table["table_name"] == "Employee Details":
                table_id = table.get("table_id")
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{env.klot_data_service_url}/storage/{projectID}/{table_id}?page=1&page_size=1000000", headers={"x-server-key": env.web_server_secret, "Authorization":f"Bearer {token}"})
                    response.raise_for_status()
                    users = response.json()
                    records = users.get("records")
                    for record in records:
                        phone_number = record["phone_number"]
                        if record["phone_number"] == f"+{phone_number}" or record["phone_number"] == f"{phone_number}":
                            print("record found", record["displayName"])
                            email_address_of_user = record["emailAddress"]
                            content = f"""
                            based on the data {data["summary"]}, find if the user has any update on the task, if the task is mentioned completed then return "done" else return "in progress" value as a string, return only "done" or "in progress" value only as per the summary of call provided, do not return anything else except the "done" or "in progress" value only
                            """
                            payload = {
                                "model": "azure/gpt-4o",
                                "messages": [
                                    {
                                        "role": "user",
                                        "content": content,
                                    },
                                ],
                            }

                            llm_caller = LLMCaller(payload)

                            inner_llm_response = await llm_caller.llm_unstructured_completion()
                            task_response = inner_llm_response.response
                            print("task_response", task_response)
                            record_id = record["_id"]
                            record["last_call_summary"] = data.get("summary")
                            record["task_status"] = task_response
                            task_goal_of_user = record["task_goal"]

                            async with httpx.AsyncClient() as inner_client:
                                inner_response = await inner_client.put(f"{env.klot_data_service_url}/storage/{projectID}/{table_id}/{record_id}", json=record, headers={"x-server-key": env.web_server_secret, "Authorization":f"Bearer {user_details['token']}"})
                                inner_response.raise_for_status()
                                inner_response.json()
            if table["table_name"] == "History":
                history_table_id = table["table_id"]
        if email_address_of_user is not None and history_table_id is not None:
            print("history_table_id", history_table_id)
            # record_to_insert = {
            #     "timestamp" : datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            #     "emailAddress" : email_address_of_user,
            #     "summary" : data.get("summary"),
            #     'call_id' : data.get("call_id"),
            #     "c_id" : data.get("c_id"),
            #     "call_length" : data.get("call_length"),
            #     "to" : data.get("to"),
            #     "from" : data.get("from"),
            #     "created_at" : data.get("created_at"),
            #     "queue_status" : data.get("queue_status"),
            #     "variables" : data.get("variables"),
            #     "recording_url" : data.get("recording_url"),
            #     "price" : data.get("price"),
            #     "started_at" : data.get("started_at"),
            #     "transcripts" : data.get("transcripts"),
            #     "corrected_duration" : data.get("corrected_duration"),
            #     "end_at" : data.get("end_at"),
            #     "disposition_tag" : data.get("disposition_tag"),
            # }
            # json_data_to_insert = {
            #     "records": [record_to_insert]
            # }
            data["timestamp"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            data["emailAddress"] = email_address_of_user
            data["task_goal"] = task_goal_of_user

            async with httpx.AsyncClient() as client:
                response = await client.post(f"{env.klot_data_service_url}/storage/{projectID}/{history_table_id}", json=[data], headers={"x-server-key": env.web_server_secret, "Authorization":f"Bearer {token}"})
                print("response", response)
                response.raise_for_status()
                response.json()
        blocker_prompt = f"""
        based on the data {data}, find if the user has any blocker, if the user has any blocker then return the full details of the blocker as a string value, else return None, do not return anything else except the detailed blocker constructed data value only, do not mention anything else except the detailed blocker constructed data value
        """
        payload = {
            "model": "azure/gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": blocker_prompt,
                },
            ],
        }
        llm_caller = LLMCaller(payload)

        blocker_llm_response = await llm_caller.llm_unstructured_completion()
        if blocker_llm_response.response not in ["None", "null", "", None]:
            async with httpx.AsyncClient() as client:
                prompt = f"""
                based on the data provided {blocker_llm_response.response}, generate a neat body of a email addressing as a AI project Manager named Mario, to send an email addressing the blocker to the user with detailed information of the blocker.
                make sure the body is well constructed to format the email as a professional email, visible with neat spacing looks good and easy to read,
                also have a clear structured crisp subject line to make it easy to read and understand the email.
                return the output as dict containing fields
                body - generated email body
                subject - generated subject line
                return the output as stringified json value of these fields in a dict, return only the stringified json value only, do not return anything else, do not mention anything, do not even mention json also, just return the stringified json value
                """
                payload = {
                    "model": "azure/gpt-4o",
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                }
                llm_caller = LLMCaller(payload)
                response = await llm_caller.llm_unstructured_completion()
                content = response.response
                email = json.loads(content)
                if email is not None:
                    body = email["body"]
                    subject = email["subject"]

                    async with httpx.AsyncClient(timeout=600) as blocker_client:

                        json_data = {
                            'subject' : subject,
                            'body' : body
                        }
                        headers = {
                            "x-server-key": env.web_server_secret
                        }
                        print("sending blocker mail to project manager")
                        response = await blocker_client.post(f"{env.klot_data_service_url}/actions/notify_through_email/send/{notify_through_email_connector_id}", json=json_data, headers=headers)
                        response.raise_for_status()
                    # prompt = f"send an email using notify through email send function with the data of the blocker {blocker_llm_response.response}"
                    # json_data = {"goal": prompt}
                    # response = await client.post(f"{env.klot_data_service_url}/actions/master/action_selector/{master_connector_id}", json=json_data, headers={"x-server-key": env.web_server_secret})
                    # response.raise_for_status()
                    # response_data = response.json()
                    # print("response_data", response_data)

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/retrieve/users")
async def find_users():
    #     response.raise_for_status()
    #     users = response.json()
    #     records = users["records"]
    #     print("records", records)


    # url = "http://localhost:4000/storage/67c8a029cc201eb6ba8261ba/67c9d83662ac2e39df1b7e1a?page=1&page_size=1000000"

    # payload = {}
    # headers = {
    # 'x-server-key': 'KlOtCoGnO',
    # 'Authorization': 'Bearer eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..2gaCuPQSM_N4QkRe.6tPpsB6oX5nOzkWhA6hMjFZEeI2gGCYMbVG5Vl5jQ9XLNFupOOXp7N2npN7fZkkktOb-UGzlg6RX_r9JZk0tvZxdRZ5fl2ehbOXoyOjKLtpmBlsOQTuHNLuMhctclec1x6csGdI4_41EFD_TjMNIK1bgwzs7jZ8DErB2lhCjuA_fEiS2QRiQ3PSSjFg1Pq0qIZ6aOzM2xqGMabYJM4txB4Bo5aPFOk2tFOjF8F1s4hP_rlkfFzjvUn--Mgi4pDmx8fObnHobCdTfvylN-EFJZFKrjgObWAGU9Yp5nowrrSpOAJPrsIAy6rCr1L9dJTSyKNYzO71gE5dFDh7P3vq-CYNb6MWtpmA-ZJrBIl1wpuAqwQUBQlviqM0seriwW_1uMaIamPnRfYsrwYI4cTz2bcyWNSmcLLtGMrncw_QSH1UYR9fHzGbD2pYShbLxSAGw4agln6a2qg6Q9_jtDNj_7jyWSoXjF-8nOYpIjklAxG5IDiJsFlGMidk41X5yfVxoOixjL7qNedVx-mArzYr0BLbmd9CS2-OesNRXZlNgchIYzz2XtJLp88iFXspXKcj7As35XWJZJYKGoFjKvpyApUPL8iQnJ2IHqGybprxR_L20yyfx6xBBLcZZ0-oewhGLFy81FMRlYiP1OMzG1lUU7h-xWikqA52jn1V0PTWKHbnPPrIdlJ2EAI83HT8I711IYAkSTCCXIzz5axzER3cMEKPG2_YIAgIBQ121u8WiDyd9byi6n34zCX9HcBaNti-X-aEB2CkHief02iCd4gUf4ohCU0ndWOuTM_4hSjVxke5mgeHfFPKCJ01V8VjK8l9B0dFhTgSs89nt1cKDx_9XxKj5W6ywPGPNhAYZX2gzENtAhmZKI-ExeuuP4RJF_8MAnLSp0Rcvmuy4Kr2TbrrMZqTZ39XJMD2EZXvMy5xB-kVa3gH9dCfkTg7yZ_uoEa-1BKOrkzziL6-RmdM0sj5Zzaby2Bk5wiex0c56Yz8ORKkAGBOiQmtjVXm_eM1D-i-xpu8TlHYIRUV6HKkOqgVPxs9pnuOgFxeBCBENr8XdO6VtOcza-T6ss_z90O_4hEbTfxWwyGnGRMcwxyNnptw88hC56-TFRPZLH8rAnZOtyZmvt4VrMphDKaneQeh4jClrke4eEdqNZDJKgGWud03_fjmGf4sT1bYVGM5VggjGJY3JVB3uIQIc_5WOfpdvZ4BEhpbG34ine_Pcm3c10kEBMOWI2x171WKNA6g.Qwpkwutajac-OUTqcX7Bow'
    # }

    # response = requests.request("GET", url, headers=headers, data=payload)

    # print(response.text)

    projectID = "67c8a029cc201eb6ba8261ba"
    user_id = "677d2aa2efbb447dd6f968a1"
    token = "eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..4XTb4ExmPFwpAQsf.4ycuFUYm0kjRDDtLBU8XG4l9o6epBSNKbzTcQEjsdpcUIrpWq0VQ0X4hcKMyvu9HfnZ_5z97yrVTjvnAOAPMcJjf7JQhfNOvpacMUUqIFpSdNuPsURkMxj-zaLzpzE95LR2nJdsd190z1QBzeOoVf2znU37rILzBDYG5CFe0083-ivPhOuV_yZOPOuo07Ruz1h6W3kv-AsRwarhwirKxwQARpe6o30UD9CHWVACCmzl8NEM8p9zSgrcbRfQcTZUidX2jwR7x1sAuSJPEn77-Cusgz6yCQuG5ieZrRb-Qc5Ie3jREom6jB9m-jdR9Wgk75AIMLnWTnsANAV7t5xLacvAbZPFPoYfUqn7UlZkDHQuF5CY2kN3Nl05ZcfgoywmCKVSqIc2VOJEEWzyoOHWhV3ESBpefj9ex-Wt06ei8GiT1q9X76xjVhI_U_TW_1A-IOqWyiz-UA7LC-0hRxHr2NZ9wIQ3Euvlab7MHtRiafl3wJOmJBJmeZXku6UVav6yJJEccE-rXqXKia99BaHQ63a1CY3_1HTqyZ4d2GcW24PdlvyPhOD6gnbh64bMtghenjWsfIHZMgjGV0yOrBsedn6pPXUBscHNTzh9J6U9qU22rRKfTI8nVeFOYXDUr7UkJvLuxjBMzDJgzPXS4q-UbOyLSDwS3dpGfFi3QzmWcPLIMQ4noMrjUwpSl0v4X-sAga_MVqTTPhM4K28BHnXRhEM92din5SNgklxrC93uqOOhro1lzOpRXizEux1j7A--O7tFtPW8drAW9kBUVGKNf6Hl9x0tvGGjNG9f_mI3vOU6UmUtDnfByfrt8LJikvu3UUMrtg_l2oXwjybpQU-OAL3-0xpUDcBGrE4tue28jnhPqCnBe08ZXOF3TXOE9ahhrMfFmr9aoAeEoAXbUMx08sU6r3HZzM4K1BqjXvwmxosq45W1dDTQu_DJjVEtOwhABq4Qbruf9GKdk15JTVD--Ll0ln9CSVnbmDm1ELbLVgoPKsI4XBz_nye8BnsKUJ_5fRFhsMuU6gAyGM8OFBzE1Zznxe58cG427EN5dPmuFgBhYlMAdlfHiUVo_Y5-D1aqtSP_4vTAa8WqtG6RMeDfdBoEE0vStVnoK1vmVnFTmTuHAmsL5QckJ8s5t65_G76SrW8w3wv78pqzE4d5EG9Rsp0o1npSvthtH76Hbztu-Ylqcv1xwCry4XIYjY9tNnz8t5VF9ZgwLFeSTGprnAdBy6ngGnyee73fFC8w.LFS_Kz6qyqsRuYY3yALW1w"
    table_id = "67c9d83662ac2e39df1b7e1a"
    record =  {'_id': '67ca742062ac2e39df1b7e55', 'emailAddress': 'akhil@wexa.ai', 'phone_number': '918247435669', 'user_followed_up': False, 'task_status': 'to do', 'task_goal': 'call akhil, ask him whether the upgrade coworker task assigned to him is completed or not', 'row_id': 1, 'coworker_user_id': '677d2aa2efbb447dd6f968a1', 'last_call_summary': '', 'displayName': 'Akhil'}
    record["last_call_summary"] = """The caller, Mario, AI project manager, spoke with Akhil to discuss the status of the "upgrade coworker" task assigned to him. Akhil confirmed that the task is completed and mentioned there are no other tickets he\'s working on or blockers that need assistance. The task will be marked as completed. """
    record["task_status"] = "done"
    record_id = "67ca742062ac2e39df1b7e55"
    email_id = "akhil@wexa.ai"
    content = "say hi"
    master_connector_id = "67c8a09a28bfa9f22a714d1c"
    email_connector_id = "67c8a0bc28bfa9f22a714d26"
    notify_through_email_connector_id = "67c93926636698b54462352d"
    prompt = f"""
    based on the data provided {content}, generate a neat body of a email addressing as a AI project Manager named Mario, to send an email addressing the blocker to the user with detailed information of the blocker.
    make sure the body is well constructed to format the email as a professional email, visible with neat spacing looks good and easy to read,
    also have a clear structured crisp subject line to make it easy to read and understand the email.
    return the output as dict containing fields
    body - generated email body
    subject - generated subject line
    return the output as stringified json value of these fields in a dict, return only the stringified json value only, do not return anything else, do not mention anything, do not even mention json also, just return the stringified json value
    """
    payload = {
        "model": "azure/gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": prompt,
            },
        ],
    }
    llm_caller = LLMCaller(payload)
    response = await llm_caller.llm_unstructured_completion()
    content = response.response
    email = json.loads(content)
    body = email["body"]
    subject = email["subject"]

    async with httpx.AsyncClient(timeout=600) as blocker_client:

        json_data = {
            'subject' : subject,
            'body' : body
        }
        headers = {
            "x-server-key": env.web_server_secret
        }
        response = await blocker_client.post(f"{env.klot_data_service_url}/actions/notify_through_email/send/{notify_through_email_connector_id}", json=json_data, headers=headers)
        response.raise_for_status()

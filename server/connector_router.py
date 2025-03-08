import asyncio
import datetime
import json
from typing import List, Optional

import httpx
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import env
from server.common.database.mongodb import client as mongodb
from server.config.collections import collections
from server.config.llm_caller import LLMCaller

router = APIRouter()

class UsersData(BaseModel):
    self: str
    accountId: str
    accountType: str
    avatarUrls: dict
    displayName: str
    active: bool
    locale: str

class FetchUserData(BaseModel):
    users: list[UsersData]
    accountIds: list[str]
    projectID: str
    tableID: str

users_collection = mongodb.db[collections.users]
summaries_collection = mongodb.db[collections.summaries]
project_details_collection = mongodb.db[collections.project_data]


class ProjectDetails(BaseModel):
    jira_connector_id: str
    slack_connector_id: str
    voice_connector_id: str
    email_connector_id: str
    master_connector_id: str
    bland_connector_id: str
    projectId: str
    hours: int
    user_id: str
    token: str




async def get_tickets_last_n_hours(config_data: dict, user_id: str, n : str):
    """
    Fetch tickets updated in the last 'n' hours.
    """
    n = int(n)
    # Headers for Authentication

    # async with httpx.AsyncClient() as client:
    #     response = await client.get(f"{env.klot_data_service_url}/actions/jira/config/{connector_id}", headers={"x-server-key": env.web_server_secret})
    #     response.raise_for_status()
    #     configuration = response.json()
    #     config_data = configuration.get("config", {})
    # Calculate the time N hours ago in Jira datetime format (YYYY-MM-DD HH:MM)
    headers = {
        "Accept": "application/json",
    }
    time_n_hours_ago = (datetime.datetime.utcnow() - datetime.timedelta(hours=n)).strftime("%Y-%m-%d %H:%M")

    # Jira Query Language (JQL) to filter issues updated in the last 'n' hours
    jql_query = f'assignee = "{user_id}" AND updated >= "{time_n_hours_ago}" ORDER BY updated DESC'

    account_url = config_data["account_url"]

    search_url = f"{account_url}/rest/api/2/search?jql={jql_query}"
    email = config_data["email"]
    token = config_data["api_token"]
    response = requests.get(search_url, headers=headers, auth=(email, token ))

    if response.status_code == 200:
        return response.json().get("issues", [])

    return []

async def send_email_to_master(email_id: str, content: str, master_connector_id: str):
    try:
        async with httpx.AsyncClient() as client:
            json = {
                "goal": f"send an email to {email_id} with content {content}, acting as the AI product Manager who is asking for the quick updates on the tickets and if the ticket require any update from the user, if the ticket has any blocker or not",
            }
            response = await client.post(f"{env.klot_data_service_url}/actions/master/action_selector/{master_connector_id}", json=json,headers={"x-server-key": env.web_server_secret})
            response.raise_for_status()
            response_data = response.json()
            return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def make_call_with_bland(phone_number: str, content: str, bland_connector_id):
    try:
        async with httpx.AsyncClient() as client:
            data = {
                "phone_number": phone_number,
                "task": content
            }
            response = await client.post(f"{env.klot_data_service_url}/actions/bland/send_call/{bland_connector_id}", json=data, headers={"x-server-key": env.web_server_secret})
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def validate_tickets(summaries: dict, input_details: ProjectDetails):
    """
    Validate the summaries of tickets and return the concerns.
    """
    concerns = []
    for accountId, tickets_summary in summaries.items():
        stringify_tickets = f""" from the content available {tickets_summary}, summarize content including key value pairs of the tickets and return the stringified format of the tickets, make sure to maintain every detail from the ticket summary and return the stringified format of the tickets"""
        payload = {
            "model": "azure/gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": stringify_tickets,
                },
                ],
            }
        llm_caller = LLMCaller(payload)
        response = await llm_caller.llm_unstructured_completion()
        summary_of_ticket = response.response
        if summary_of_ticket:
            content = f"""you are an AI product Manager, you have a ticket with the following details: {summary_of_ticket} which is stringified format of the ticket_id corresponding to the summary of the ticket the user worked on,
            you are calling the person who was assigned with the tickets for quick updates on the tickets, if the ticket require any update from the user, if the ticket has any blocker or not
            make sure to ask the user every required questions and get the answers from the user and return the concerns to be resolved as a string value describing things in detailed, make sure to pass the projectId to the master connector execution post call with value {input_details.projectId} along the conversation history, if there is a mention of blocker then create content through content creator in master executor if there is no blocker then use notify through email connector send action for sending email with summary of the conversation, make call to execute master execution at last with these details, the master call should have goal which describes what it has to do"""
            user = await users_collection.find_one({"accountId": accountId})
            if user:
                phone_number = user.get("phone_number")
                call_data = await make_call(phone_number, content, input_details.voice_connector_id)
                # if call_data:
                #     blocker_check = f"""from the content available {call_data}, decide based on the content if the user mentioned any blocker for his ticket, if yes return the concerns to be resolved as a string value"""
                #     users_names = await users_collection.find({"projectId": input_details.projectId},{"displayName":1}).to_list(None)
                #     user_names = users_names.get("displayName")
                #     name_finder = f"""from the content available {blocker_check}, find the name of the user who has been the blocker for the user matching with the names provided {user_names}, return only the name as it is provided matching with the content, return the complete name matched with the name as provided in the content"""
                #     payload = {
                #     "model": "azure/gpt-4o",
                #     "messages": [
                #         {
                #             "role": "user",
                #             "content": name_finder,
                #         },
                #         ],
                #     }
                #     llm_caller = LLMCaller(payload)
                #     response = await llm_caller.llm_unstructured_completion()
                #     name = response.response

                #     phone_number_of_blocker = users_collection.find_one({"displayName": name},{"phone_number":1}).get("phone_number")


                #     blocker_call = f"""you are an AI product Manager whose task is to call the person who has been the blocker for the user based on the content {blocker_check}, make sure to ask the user every required questions and get the answers from the user and return the concerns to be resolved as a string value describing things in detailed"""
                #     call_data = await make_call(phone_number_of_blocker, blocker_call, input_details.voice_connector_id)
                #     if call_data:
                #         send_email_to_master(email_id=user.get("emailAddress"), content=content, master_connector_id=input_details.email_connector_id)
            else:
                email = user.get("emailAddress")
                await send_email_to_master(
                    email_id=email,
                    content=content,
                    master_connector_id=input_details.email_connector_id
                )
    return concerns



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




@router.post("/project/manager/perform")
async def get_user_details(input_details: ProjectDetails):
    try:
        existing_record = await project_details_collection.find_one({"projectId": input_details.projectId})
        if existing_record:
            await project_details_collection.update_one(
                {"projectId": input_details.projectId},
                {"$set": input_details.model_dump()}
            )
        else:
            await project_details_collection.insert_one(input_details.model_dump())

        async with httpx.AsyncClient() as client:
            response = await client.get(url=f"{env.klot_data_service_url}/actions/jira/config/{input_details.jira_connector_id}", headers={"x-server-key": env.web_server_secret})
            response.raise_for_status()
            configuration = response.json()
            jira_config_data = configuration.get("config", {}).get("config", {})
        # Calculate the time N hours ago in Jira datetime format (YYYY-MM-DD HH:MM)
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{env.klot_data_service_url}/actions/slack/config/{input_details.slack_connector_id}", headers={"x-server-key": env.web_server_secret})
            response.raise_for_status()
            configuration = response.json()
            slack_config_data = configuration.get("config", {}).get("config", {})

        users_data = []
        temp_users_data = []
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
        accountIds = [user["accountId"] for user in temp_users_data]
        for account_id in accountIds:
            search_url = f"{account_url}/rest/api/3/user?accountId={account_id}"
            response = requests.get(search_url, headers=headers,auth=(email, token))
            user_data = response.json()
            users_data.append(user_data if user_data.get("active") else None)
        
        token = slack_config_data["user_token"] if slack_config_data["user_token"] else slack_config_data["bot_token"]
        slack_headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        for user in users_data:
            user["projectId"] = input_details.projectId
            user_email = user.get('emailAddress') if user.get('emailAddress') else None

            if user_email is not None:
                slack_url = f"https://slack.com/api/users.lookupByEmail?email={user_email}"
                response = requests.get(slack_url, headers=slack_headers)
                slack_user = response.json()

                if not slack_user["user"]["is_bot"] and slack_user["user"]["is_email_confirmed"] and not slack_user["user"]["deleted"] and not slack_user["user"]["is_app_user"]:
                    user["phone_number"] = slack_user.get("user").get("profile").get("phone") if slack_user.get("user").get("profile").get("phone") else None
        
        retrieved_users = await users_collection.find({"projectId": input_details.projectId}).to_list(None)
        if retrieved_users is None or len(retrieved_users) == 0:
            await users_collection.insert_many(users_data)
        else:
            retrieved_users_ids = [user["accountId"] for user in retrieved_users]
            users_to_insert = [user for user in users_data if user["accountId"] not in retrieved_users_ids]
            users_to_update = [user for user in users_data if user["accountId"] in retrieved_users_ids]
            for user in users_to_update:
                await users_collection.update_one(
                    {"accountId": user}["accountId"],
                    {"$set": user}
                )
            for user in users_to_insert:
                user["projectId"] = input_details.projectId
                await users_collection.insert_one(user)
        summary_details =  {}
        retrieved_users_data = await users_collection.find({"projectId": input_details.projectId, "emailAddress" : {"$ne": None}}).to_list(None)
        for user in retrieved_users_data:
            tickets = await get_tickets_last_n_hours(jira_config_data, user["accountId"], input_details.hours)
            print("tickets", tickets)
            if len(tickets) != 0:

                tickets_summary = await manage_tickets(tickets, account_url=account_url, email=email, api_token=token)
                summary_details[user["accountId"]] = tickets_summary
        day_summary = {datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"): summary_details}

        await summaries_collection.insert_one(day_summary)

        await validate_tickets(summaries=summary_details, input_details=input_details)

        return "completed"

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class BlockerData(BaseModel):
    context: str
    user_id: str

@router.post("/project/manager/blocker/call")
async def blocker_call(data: BlockerData):
    try:
        projectId_check = f"""from the content available {data}, find the projectId value which is sent by the agent, send the projectId value only as string value, do not return anything else"""
        payload = {
            "model": "azure/gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": projectId_check,
                },
            ],
        }
        llm_caller = LLMCaller(payload)
        response = await llm_caller.llm_unstructured_completion()
        projectId = response.response
        user_details = await project_details_collection.find_one({"user_id": data.user_id})
        if user_details is None:
            raise HTTPException(status_code=404, detail="User not found")
        jira_connector_id = user_details.get("jira_connector_id")

        async with httpx.AsyncClient() as client:
            response = await client.get(url=f"{env.klot_data_service_url}/actions/jira/config/{jira_connector_id}", headers={"x-server-key": env.web_server_secret})
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

        user_names = [user["displayName"] for user in response.json()]


        content = f"""from the content available {data}, find the name of the user who has been the blocker for the user matching with the names provided {user_names}, return only the name as it is provided matching with the content, return the complete name matched with the name as provided in the content"""
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
        phone_number_of_blocker = users_collection.find_one({"displayName": name},{"phone_number":1}).get("phone_number")
        blocker_call = f"""you are an AI product Manager whose task is to call the person who has been the blocker for the user based on the content {data}, make sure to ask the user every required questions and get the answers from the user and return the concerns to be resolved as a string value describing things in detailed, also send an email with the content using notify through email connector, make call to execute master execution at last with these details, the master call should have goal which describes what it has to do"""
        voice_connector_id = await project_details_collection.find_one({"projectId": projectId}, {"voice_connector_id":1, "_id":0}).get("voice_connector_id")
        call_data = await make_call(phone_number_of_blocker, blocker_call, voice_connector_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
class Worklog(BaseModel):
    startAt: Optional[int]
    maxResults: Optional[int]
    total: Optional[int]
    worklogs: List[dict]

class Ticket(BaseModel):
    id: Optional[str]
    summary: Optional[str]
    status: Optional[str]
    issue_type: Optional[str]
    created: Optional[str]
    updated: Optional[str]
    worklog: Worklog
    assignee_email: Optional[str]
    reporter_email: Optional[str]
    assignee_display_name: Optional[str]
    reporter_display_name: Optional[str]

class TicketsData(BaseModel):
    tickets: Optional[List[Ticket]]
    user_id: str

async def manage_ticket(tickets: dict):
    try:
        tickets_summary = {}
        if tickets:
            for ticket in tickets:

                print("ticket", ticket["key"])
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

@router.post("/tickets/summary/generator")
async def tickets_summary_generator(tickets: TicketsData):
    try:
        user = await users_collection.find_one({"user_id":tickets.user_id})
        if user is None:
            raise HTTPException(status_code=404, detail="User Details not found")
        jira_connector_id = user.get("jira_connector_id")
        async with httpx.AsyncClient() as client:
            response = await client.get(url=f"{env.klot_data_service_url}/actions/jira/config/{jira_connector_id}", headers={"x-server-key": env.web_server_secret})
            response.raise_for_status()
            configuration = response.json()
            jira_config_data = configuration.get("config", {}).get("config", {})
        for ticket in tickets.tickets:
            account_url = ticket["account_url"]
            email = jira_config_data["email"]
            api_token = jira_config_data["api_token"]
            summary_of_ticket = await manage_tickets(tickets=response.json(), account_url=account_url, email=email, api_token=api_token)
            return summary_of_ticket
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/retrieve/timestamp")
async def retrieve_timestamp():
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        return timestamp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
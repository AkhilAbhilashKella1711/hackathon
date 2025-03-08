import httpx

async def send_history_received():
    data = {
        'call_id': '6f76dd08-f92c-4661-9c3c-b65298075d66',
        'c_id': '6f76dd08-f92c-4661-9c3c-b65298075d66',
        'call_length': 0.983333333333333,
        'batch_id': None,
        'to': '+918247435669',
        'from': '+19592656197',
        'completed': True,
        'created_at': '2025-03-08T13:02:03.129+00:00',
        'inbound': False,
        'queue_status': 'complete',
        'max_duration': 12,
        'error_message': None,
        'variables': {
            'now': 'Saturday, March 8, 2025 6:32 PM',
            'now_utc': 'Saturday, March 8, 2025 1:02 PM',
            'short_from': '9592656197',
            'short_to': '8247435669',
            'from': '+19592656197',
            'to': '+918247435669',
            'call_id': '6f76dd08-f92c-4661-9c3c-b65298075d66',
            'phone_number': '+918247435669',
            'city': 'Mangalore',
            'country': 'IN',
            'state': 'Dakshin Kanada (Mangalore)',
            'language': 'English',
            'timestamp': '2025-03-08T18:32:11+05:30',
            'timezone': 'Asia/Kolkata'
        },
        'answered_by': None,
        'record': True,
        'recording_url': 'https://server.aws.dc5.bland.ai/v1/recordings/6f76dd08-f92c-4661-9c3c-b65298075d66:d7d6a1b1-fa4f-4ac0-8d20-47a7ca741af1',
        'metadata': {},
        'summary': "Summary: The conversation was between Mario, the AI project manager, and Akhil, regarding the status of tasks Akhil was working on. Akhil confirmed that the previous task, \"driver's card\", was completed and Mario marked the \"upgrade coworker task\" as completed. No new issues or concerns were raised, and the call ended with a positive note. User ID: 677d2aa2efbb447dd6f968a1.",
        'price': 0.089,
        'started_at': '2025-03-08T13:02:03.129Z',
        'local_dialing': False,
        'call_ended_by': 'USER',
        'pathway_logs': None,
        'analysis_schema': None,
        'analysis': None,
        'transferred_to': None,
        'pathway_tags': [],
        'recording_expiration': None,
        'status': 'completed',
        'pathway_id': None,
        'concatenated_transcript': "assistant: Hello There! This is Mario - your AI project Manager calling to understand the status of the task you are working on \n user: Hello, Mario. \n assistant: Hi Akhil, hope you're doing well, I just wanted to quickly touch base with you regarding the tickets you're working on, do you have any updates on those \n user: Yeah. I have completed the previous card, driver's card. \n assistant: That's great to hear, Akhil, so the upgrade coworker task is completed, are you working on any new tickets now or is there anything that's blocking you or needs my assistance \n user: Yes. <Cannot be interrupted, user message ignored> \n user: No. No. \n assistant: Alright, so everything looks good, I'll go ahead and mark the upgrade coworker task as completed, was there anything else you wanted to discuss or bring up, Akhil \n user: I'm completed. <Cannot be interrupted, user message ignored> \n user: What? Nothing. \n assistant: Okay, great, well in that case, I think we're all set, it was great catching up with you, Akhil, have a great rest of your day and I'll talk to you soon, bye for now \n ",
        'transcripts': [
            {'id': 105663612, 'user': 'assistant', 'text': 'Hello There! This is Mario - your AI project Manager calling to understand the status of the task you are working on', 'created_at': '2025-03-08T13:02:17.91428+00:00'},
            {'id': 105663653, 'user': 'user', 'text': 'Hello, Mario.', 'created_at': '2025-03-08T13:02:21.395858+00:00'},
            {'id': 105663676, 'user': 'assistant', 'text': "Hi Akhil, hope you're doing well, I just wanted to quickly touch base with you regarding the tickets you're working on, do you have any updates on those", 'created_at': '2025-03-08T13:02:22.899096+00:00'},
            {'id': 105663849, 'user': 'user', 'text': "Yeah. I have completed the previous card, driver's card.", 'created_at': '2025-03-08T13:02:36.513679+00:00'},
            {'id': 105663890, 'user': 'assistant', 'text': "That's great to hear, Akhil, so the upgrade coworker task is completed, are you working on any new tickets now or is there anything that's blocking you or needs my assistance", 'created_at': '2025-03-08T13:02:38.765401+00:00'},
            {'id': 105663962, 'user': 'user', 'text': 'Yes. <Cannot be interrupted, user message ignored>', 'created_at': '2025-03-08T13:02:42.896021+00:00'},
            {'id': 105664032, 'user': 'user', 'text': 'No. No.', 'created_at': '2025-03-08T13:02:47.759818+00:00'},
            {'id': 105664051, 'user': 'assistant', 'text': "Alright, so everything looks good, I'll go ahead and mark the upgrade coworker task as completed, was there anything else you wanted to discuss or bring up, Akhil", 'created_at': '2025-03-08T13:02:48.991352+00:00'},
            {'id': 105664061, 'user': 'user', 'text': "I'm completed. <Cannot be interrupted, user message ignored>", 'created_at': '2025-03-08T13:02:49.514652+00:00'},
            {'id': 105664191, 'user': 'user', 'text': 'What? Nothing.', 'created_at': '2025-03-08T13:02:58.804795+00:00'},
            {'id': 105664210, 'user': 'assistant', 'text': "Okay, great, well in that case, I think we're all set, it was great catching up with you, Akhil, have a great rest of your day and I'll talk to you soon, bye for now", 'created_at': '2025-03-08T13:03:00.005362+00:00'}
        ],
        'corrected_duration': '59',
        'end_at': '2025-03-08T13:03:09.000Z',
        'disposition_tag': 'COMPLETED_ACTION'
    }

    async with httpx.AsyncClient(timeout=600) as client:
        response = await client.post("http://localhost:5005/update/conversation/history", json=data)
        print("Response Status Code:", response.status_code)
        print("Response Content:", response.text)
        response.raise_for_status()

# Call the function to send the data
import asyncio
asyncio.run(send_history_received())
from datetime import timedelta

from temporalio import activity, workflow

from server.connector_router import ProjectDetails, get_user_details
from server.follow_up_router import UserDetails, schedule_calls


@activity.defn
async def get_user_details_activity(input_details: UserDetails):
    return await schedule_calls(input_details)

@workflow.defn
class UserCallsWorkflow:
    @workflow.run
    async def run(self, input_details: UserDetails):
        await workflow.execute_activity(
            schedule_calls,
            input_details,
            start_to_close_timeout=timedelta(minutes=10)
        )
from datetime import timedelta

from temporalio import activity, workflow

from server.follow_up_router import BlandCallInput, UserDetails, schedule_bland_calls


@activity.defn
async def get_user_details_activity(input_details: BlandCallInput):
    return await schedule_bland_calls(input_details)


@workflow.defn
class UserCallsWorkflow:
    @workflow.run
    async def run(self, input_details: UserDetails):
        await workflow.execute_activity(
            schedule_bland_calls,
            input_details,
            start_to_close_timeout=timedelta(minutes=10),
        )

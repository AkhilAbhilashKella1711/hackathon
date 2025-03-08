from fastapi import HTTPException
from pydantic import ValidationError

from server.common.database.mongodb import client as mongodb


class SessionManager:
    def __init__(self):
        self.session = None

    async def start_session(self):
        if self.session is None:
            print('Creating new session')
            self.session = await mongodb.client.start_session()
        else:
            print('Using existing session')

        return self.session

    async def end_session(self):
        if self.session:
            print('Ending session')
            await self.session.end_session()
            self.session = None


session_manager = SessionManager()


def with_transaction(func):
    async def wrapper(*args, **kwargs):
        session = await session_manager.start_session()
        try:
            if session.in_transaction is False:
                session.start_transaction()

            result = await func(*args, **kwargs, session=session)
            return result
        except ValidationError as e:
            print(e)
            if session.in_transaction:
                await session.abort_transaction()

            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException as e:
            print(e)
            if session.in_transaction:
                await session.abort_transaction()
            raise e
        except Exception as e:
            print(e)
            if session.in_transaction:
                await session.abort_transaction()
            raise HTTPException(status_code=500, detail=str(e))
        # finally:
        #     await session_manager.end_session()

    return wrapper

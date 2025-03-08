import uvicorn
from fastapi import FastAPI

import env

# from server.common.database.data_service_mongodb import client as data_service_mongodb
from server.common.database.mongodb import client as mongodb
from server.connector_router import router as connector_router
from server.conversation import router as conversation_router
from server.follow_up_router import router as follow_up_router

# from server.common.database.table_mongodb import client as table_mongodb

app = FastAPI()

app.add_event_handler('startup', mongodb.connect)
app.add_event_handler('shutdown', mongodb.disconnect)
# app.add_event_handler('startup', data_service_mongodb.connect)
# app.add_event_handler('shutdown', data_service_mongodb.disconnect)
# app.add_event_handler('startup', table_mongodb.connect)
# app.add_event_handler('shutdown', table_mongodb.disconnect)

app.include_router(connector_router)
app.include_router(conversation_router)
app.include_router(follow_up_router)

@app.get('/health_check')
async def health_check():
    return {'message': 'Hey Devops dude! I am alive!'}


if __name__ == '__main__':
    uvicorn.run(
        app='server.main:app',
        host='0.0.0.0',
        port=int(env.port),
        reload=True,
        limit_max_requests=None,
        workers=1,
        timeout_keep_alive=600,
    )
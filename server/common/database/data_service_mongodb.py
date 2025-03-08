import logging

from motor.motor_asyncio import AsyncIOMotorClient

import env


class MongoDB:
    """
    MongoDB class to manage connection to a MongoDB database.

    Attributes:
        client (AsyncIOMotorClient): The MongoDB client.
        db (Database): The database instance.
    """

    def __init__(self):
        """
        Initialize the MongoDB connection using environment variables.
        """
        print("env.mongodb_url", env.data_service_mongodb_url)
        print("env.mongodb_db", env.data_service_mongodb_name)
        self.client: AsyncIOMotorClient = AsyncIOMotorClient(
            env.mongodb_url
        )
        self.db = self.client.get_database(env.mongodb_db)
        print('Connected to MongoDB client')

    def connect(self):
        """
        Establish a connection to the MongoDB database.

        If a client connection already exists, it does nothing.
        """
        if self.client is not None:
            return
        self.client = AsyncIOMotorClient(env.mongodb_url)
        self.db = self.client.get_database(env.mongodb_db)
        logging.info('MongoDB connection established')

    def disconnect(self):
        """
        Close the connection to the MongoDB database.

        If no client connection exists, it logs a warning.
        """
        if self.client is None:
            logging.warning('Connection is None, nothing to close')
            return
        self.client.close()
        self.client = None  # type: ignore
        logging.info('MongoDB connection closed')

    def __del__(self):
        """
        Ensure the MongoDB connection is closed when the object is deleted.
        """
        self.disconnect()


# Create an instance of MongoDB client
client = MongoDB()

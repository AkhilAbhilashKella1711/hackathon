from pydantic import BaseModel, Field


class DatabaseCollections(BaseModel):
    users: str = Field(default='users', description='Collection name for users')
    summaries: str = Field(default='summaries', description='Collection name for summaries')
    project_data: str = Field(default='project_data', description='Collection name for project data')

collections = DatabaseCollections()

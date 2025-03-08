from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """
    User model representing the details of a user.

    Attributes:
        id (str): Unique identifier of the user.
        email (EmailStr): Email address of the user.
        username (str): Username of the user.
    """

    id: str = Field(..., description='User id', alias='_id')
    email: EmailStr = Field(..., description='User email')
    username: str = Field(..., description='User name')


class Project(BaseModel):
    """
    Project model representing the details of a project.

    Attributes:
        id (str): Unique identifier of the project.
        org (str): Organization ID associated with the project.
        projectName (str): Name of the project.
        role (Literal): Role of the user within the project.
            Allowed values: "OWNER", "ORG_ADMIN", "ORG_MEMBER", "PROJECT_ADMIN", "PROJECT_MEMBER".
    """

    id: str = Field(..., description='Project id', alias='_id')
    org: str = Field(..., description='Organization id')
    projectName: str = Field(..., description='Project name')
    role: Literal[
        'OWNER', 'ORG_ADMIN', 'ORG_MEMBER', 'PROJECT_ADMIN', 'PROJECT_MEMBER'
    ] = Field(..., description='Role')


class Organization(BaseModel):
    """
    Organization model representing the details of an organization.

    Attributes:
        id (str): Unique identifier of the organization.
        by (str): User ID of the creator of the organization.
        name (str): Name of the organization.
        role (Literal): Role of the user within the organization.
            Allowed values: "OWNER", "ORG_ADMIN", "ORG_MEMBER", "PROJECT_ADMIN".
    """

    id: str = Field(..., description='Organization id', alias='_id')
    by: str = Field(..., description='User id')
    name: str = Field(..., description='Organization name')
    role: Literal['OWNER', 'ORG_ADMIN', 'ORG_MEMBER', 'PROJECT_ADMIN'] = Field(
        ..., description='Role'
    )


class AuthenticatedUser(BaseModel):
    """
    AuthenticatedUser model representing the details of an authenticated user.

    Attributes:
        user (User): Details of the user.
        project (Optional[Project]): Details of the project the user is associated with.
        organization (Optional[Organization]): Details of the organization the user is associated with.
    """

    user: User = Field(..., description='User details')
    project: Optional[Project] = Field(..., description='Project details')
    organization: Optional[Organization] = Field(
        ..., description='Organization details'
    )

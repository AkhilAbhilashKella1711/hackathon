from fastapi import HTTPException, Request

import env
from server.common.authorization.model import AuthenticatedUser, User


async def system_call(request: Request) -> AuthenticatedUser:
    """
    Verifies if the request is a system call using a special server key.

    This function checks if an incoming request to the server is a system-level call
    by verifying a special 'x-server-key' in the request headers against a predefined server key.
    If the check passes, it returns an AuthenticatedUser object representing the system user.
    If the check fails, it raises an HTTPException to deny access.

    Args:
        request (Request): The incoming request object from a client.

    Returns:
        AuthenticatedUser: An object representing the authenticated system user if the request is verified as a system call.

    Raises:
        HTTPException: If the 'x-server-key' is missing or incorrect, it raises a 403 Forbidden error.
        HTTPException: If any other error occurs during the process, it raises a 500 Internal Server Error.
    """

    # Extract the 'x-server-key' from the request headers
    server_key = request.headers.get('x-server-key')

    # Check if the server key is present and matches the expected value
    if server_key and server_key == env.web_server_secret:
        # Return an AuthenticatedUser object representing the system user
        return AuthenticatedUser(
            user=User(
                _id='1',
                email='server@example.com',  # type: ignore
                username='Server',
            ),
            organization=None,  # Organization ID, keep as None if not applicable
            project=None,  # Project ID, keep as None if not applicable
        )

    # Raise a 403 Forbidden error if the server key is missing or incorrect
    raise HTTPException(
        detail='You are not allowed to access this resource', status_code=403
    )

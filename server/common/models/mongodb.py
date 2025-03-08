from typing import Annotated, Any

from bson.objectid import ObjectId
from pydantic import AfterValidator, PlainSerializer, WithJsonSchema


def validate_object_id(v: Any) -> ObjectId:
    """
    Validate and convert the input to a valid ObjectId.

    Args:
        v (Any): The value to validate and convert. Can be of any type.

    Returns:
        ObjectId: The validated and converted ObjectId.

    Raises:
        ValueError: If the input is not a valid ObjectId.
    """
    if isinstance(v, ObjectId):
        return v
    if ObjectId.is_valid(v):
        return ObjectId(v)
    raise ValueError("Invalid ObjectId")


# Define a type alias PyObjectId that ensures the value is a valid ObjectId
PyObjectId = Annotated[
    str | ObjectId,
    PlainSerializer(
        lambda x: str(x), return_type=str, when_used="json"
    ),  # Serialize ObjectId to string for JSON
    AfterValidator(validate_object_id),  # Validate the value to be a valid ObjectId
    WithJsonSchema(
        {"type": "string"}, mode="serialization"
    ),  # Define JSON schema for serialization
]


# <-- Implementation 2 --->

# from bson.objectid import ObjectId
# from pydantic.functional_validators import AfterValidator
# from typing_extensions import Annotated


# def validate_object_id(v: ObjectId | str) -> ObjectId | str:
#     assert ObjectId.is_valid(v), f"{v} is not a valid ObjectId"
#     if isinstance(v, str):
#         return ObjectId(v)
#     return str(v)


# PyObjectId = Annotated[ObjectId | str, AfterValidator(validate_object_id)]

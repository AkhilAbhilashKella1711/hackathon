from typing import Any, Dict, List, Literal, Optional, Union

from bson import ObjectId
from pydantic import BaseModel, Field, field_validator

from server.common.models.mongodb import PyObjectId

Status = Literal["success"]


class DeleteStorageModel(BaseModel):
    storage_ids: List[str] = Field(..., description="The IDs of the storage.")

# Model to represent an object field
class ObjectField(BaseModel):
    key: str = Field(..., description="The key of the object field.")
    keyType: str = Field(..., description="The type of the object field.")


# Main Column model with validation
class Column(BaseModel):
    column_name: str = Field(..., description="The name of the column.")
    column_type: str = Field(..., description="The type of the column.")
    column_id: str = Field(..., description="The ID of the column.")
    array_type: Optional[str] = Field(
        default=None,
        description="The type of elements in the array. Required if column_type is 'Array'.",
    )
    default_value: Optional[Union[Any, List, Dict[str, Any]]] = Field(
        default=None,
        description="The default value for the column, can be a string, int, bool, array, or dictionary.",
    )
    object_fields: Optional[List[ObjectField]] = Field(
        default=None,
        description="The fields for the object. Required if column_type is 'Object'.",
    )

    # Root validator to check conditions based on column_type
    @field_validator(pre=True)
    def validate_column(cls, values):
        column_type = values.get("column_type").lower()
        array_type = values.get("array_type")
        object_fields = values.get("object_fields")
        default_value = values.get("default_value")

        cls._validate_array_type(column_type, array_type)
        cls._validate_object_fields(column_type, object_fields)
        cls._validate_default_value(column_type, array_type, object_fields, default_value, values)

        return values

    @staticmethod
    def _validate_array_type(column_type, array_type):
        if column_type == "array" and not array_type:
            raise ValueError('array_type is required when column_type is "Array".')

    @staticmethod
    def _validate_object_fields(column_type, object_fields):
        if column_type == "object":
            if not object_fields or len(object_fields) == 0:
                raise ValueError('object_fields are required when column_type is "Object".')
            for field in object_fields:
                if not field.get("key") or not field.get("keyType"):
                    raise ValueError("Each object field must have a key and keyType.")

    @staticmethod
    def _validate_default_value(column_type, array_type, object_fields, default_value, values):
        if default_value is not None:
            if column_type == "array":
                Column._validate_array_default_value(array_type, default_value)
            elif column_type == "object":
                Column._validate_object_default_value(object_fields, default_value)
            else:
                Column._validate_simple_default_value(column_type, default_value, values)

    @staticmethod
    def _validate_array_default_value(array_type, default_value):
        if not isinstance(default_value, list):
            raise ValueError("default_value must be a list for array column_type.")
        if array_type:
            if array_type == "string" and not all(isinstance(item, str) for item in default_value):
                raise ValueError("All items in default_value must be strings.")
            elif array_type == "number" and not all(isinstance(item, (int, float)) for item in default_value):
                raise ValueError("All items in default_value must be numbers.")
            elif array_type == "boolean" and not all(isinstance(item, bool) for item in default_value):
                raise ValueError("All items in default_value must be booleans.")

    @staticmethod
    def _validate_object_default_value(object_fields, default_value):
        if not isinstance(default_value, dict):
            raise ValueError("default_value must be a dictionary for object column_type.")
        if default_value:
            for obj_field in object_fields:
                key = obj_field.get("key")
                key_type = obj_field.get("keyType").lower()
                if key in default_value:
                    value = default_value[key]
                    if key_type == "string" and not isinstance(value, str):
                        raise ValueError(f"The key '{key}' in default_value must be a string.")
                    elif key_type == "number" and not isinstance(value, (int, float)):
                        raise ValueError(f"The key '{key}' in default_value must be a number.")
                    elif key_type == "boolean" and not isinstance(value, bool):
                        raise ValueError(f"The key '{key}' in default_value must be a boolean.")
                else:
                    raise ValueError(f"The key '{key}' is missing in default_value.")

    @staticmethod
    def _validate_simple_default_value(column_type, default_value, values):
        if column_type == "string" and not isinstance(default_value, str):
            raise ValueError("default_value must be a string for string column_type.")
        elif column_type == "number" and not isinstance(default_value, int):
            try:
                values["default_value"] = int(default_value)
            except ValueError:
                raise ValueError("default_value must be an integer for integer column_type.")
        elif column_type == "boolean" and not isinstance(default_value, bool):
            if isinstance(default_value, str):
                if default_value.lower() in ["true", "false"]:
                    values["default_value"] = default_value.lower() == "true"
                else:
                    raise ValueError("default_value must be a boolean for boolean column_type.")
            else:
                raise ValueError("default_value must be a boolean for boolean column_type.")

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class Table(BaseModel):
    id: PyObjectId = Field(..., description="ID of the inbox item.", alias="_id")
    projectID: str = Field(..., description="The ID of the project.")
    table_name: str = Field(..., description="The name of the table.")
    columns: List[Column] = Field([], description="The columns of the table.")
    connector_id: str = Field(..., description="The ID of the connector.")
    last_row_id: Optional[int] = Field(
        0,
        description="The ID of the last row in the table. Used to generate unique row IDs.",
    )


class CreateTableInput(BaseModel):
    projectID: str = Field(..., description="The ID of the project.")
    user_id: str = Field(..., description="The ID of the user.")
    table_name: str = Field(..., description="The name of the table.")


class TableName(BaseModel):
    table_name: str = Field(..., description="The name of the table.")
    id: PyObjectId = Field(..., description="ID of the inbox item.", alias="_id")


class GetTableNamesResponse(BaseModel):
    total_count: int = Field(..., description="The total number of tables.")
    tables: List[TableName] = Field(
        [], description="The tables that are related to the workspace"
    )


class GetTablesResponse(BaseModel):
    total_count: int = Field(..., description="The total number of tables.")
    tables: List[Table] = Field(
        [], description="The tables that are related to the workspace"
    )


class DeleteTableResponse(BaseModel):
    status: Status = Field(..., description="The status of the deletion.")
    message: str = Field(..., description="The message of the deletion.")


class EditColumnsData(BaseModel):
    column_id: str = Field(..., description="Id of the column")
    column_name: str = Field(..., description="Name of the column")
    table_id: str = Field(..., description="Id of the table")


class DeleteColumn(BaseModel):
    table_id: str = Field(..., description="Id of the table")
    column_id: str = Field(..., description="Id of column")


class RenameTable(BaseModel):
    table_id: str = Field(..., description="Id of the table")
    table_name: str = Field(..., description="New name of the table")

class ExportRecordsResponse(BaseModel):
    metadata: Table = Field(..., description="The metadata of the table.")
    records: List[dict] = Field(..., description="The records of the table.")
    total_count: int = Field(..., description="The total number of records.")

class GetRecordsListResponse(BaseModel):
    meta_data: Table = Field(..., description="The metadata of the table.")
    total_count: int = Field(..., description="The total number of records.")
    records: List[dict] = Field(..., description="The records of the table.")


class BaseColumn(BaseModel):
    column_name: str = Field(..., description="The name of the column.")
    column_id: str = Field(..., description="The type of the column.")


class ColumnMapper(BaseModel):
    column_names: List[BaseColumn] = Field(..., description="The names of the columns.")
    csv_headers: List[str] = Field(..., description="The CSV headers of the columns.")


class ColumnMapperOutput(BaseModel):
    suggestions: Dict[str, str | None] = Field(..., description="Column Mapper output")

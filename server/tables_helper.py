
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pymongo
from bson import ObjectId
from fastapi import HTTPException
from motor.motor_asyncio import (
    AsyncIOMotorClientSession,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)

from server.common.database.mongodb import client as mongodb
from server.common.models.mongodb import PyObjectId
from server.table_models import (
    Column,
    CreateTableInput,
    GetTablesResponse,
    RenameTable,
    Table,
)

WEXA_TABLES = "mario_tables"


async def create_collection(
    tableId: str,
    projectID: str,
    table_name: str,
    session: AsyncIOMotorClientSession | None = None,
):
    try:
        db = mongodb.client.get_database(WEXA_TABLES)

        create_table = await db.create_collection(name=tableId)

        if create_table is None:
            raise HTTPException(status_code=500, detail="Could not create the Table")

        collection = db[tableId]

        if collection is None:
            raise HTTPException(status_code=500, detail="Could not find the table")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



async def create_table(
    table_data: CreateTableInput,
    session: AsyncIOMotorClientSession | None = None,
):
    tables_json_path = Path(__file__).parent / "tables.json"
    
    # Check if the file exists
    if not tables_json_path.exists():
        raise HTTPException(status_code=404, detail="tables.json file not found")
    
    # Read the content of the tables.json file
    with open(tables_json_path, "r") as file:
        tables_json = json.load(file)
    columns = tables_json[table_data.table_name]

    for column in columns:
        column = Column(**column)
    # Check if the table name already exists within the project
    table_exists = await mongodb.db.tables.find_one(
        {"user_id": table_data.user_id, "table_name": table_data.table_name},
        session=session,
    )
    print("table_exists", table_exists)

    if table_exists:
        raise HTTPException(
            status_code=400,
            detail=f"Table with name {table_data.table_name} already exists",
        )

    # Check if the table_data.columns already contains _id
    for column in columns:
        if column.column_id in ["_id", "row_id", "coworker_user_id"]:
            # delete the column with _id
            table_data.columns.remove(column)

    table_data.columns.insert(
        0,
        Column(
            column_name="_id",
            column_type="string",
            column_id="_id",
            default_value="",
            triggers=None,
        ),
    )
    table_data.columns.insert(
        1,
        Column(
            column_name="Row ID",
            column_type="number",
            column_id="row_id",
            default_value=1,
            triggers=None,
        ),
    )
    table_data.columns.insert(
        2,
        Column(
            column_name="User ID",
            column_type="string",
            column_id="coworker_user_id",
            default_value="",
            triggers=None,
        ),
    )
    table = table_data.model_dump(by_alias=True)

    inserted_record = await mongodb.db.tables.insert_one(
        # table_data.dict(by_alias=True),
        table,
        session=session,
    )

    print("inserted_record", inserted_record)

    if not inserted_record:
        raise HTTPException(status_code=500, detail="Failed to create a table")

    await create_collection(
        tableID=str(inserted_record.inserted_id),
        projectID=table_data.projectID,
        table_name=table_data.table_name,
        session=session,
    )

    # update the table with the connector id
    table = await mongodb.db.tables.find_one_and_update(
        {"_id": inserted_record.inserted_id},
        return_document=pymongo.ReturnDocument.AFTER,
        session=session,
    )

    if not table:
        raise HTTPException(status_code=500, detail="Failed to create a table")

    return Table(**table)

async def get_table_by_id(table_id: str):
    table = await mongodb.db.tables.find_one({"_id": ObjectId(table_id)})

    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    return Table(**table)

async def get_most_recent_record(database: str, collection_name: str):
    db = mongodb.client.get_database(WEXA_TABLES)

    record: dict | None = await db[collection_name].find_one({}, sort=[("_id", -1)])  # type: ignore

    if record is None:
        return None

    return record

async def get_table_details(table_id: PyObjectId):
    table_in_db = await mongodb.db.tables.find_one({"_id": table_id})

    if not table_in_db:
        raise HTTPException(
            status_code=404, detail=f"Table not found with id {table_id}"
        )

    table = Table(**table_in_db)

    # check if the  last row id exists in the collection
    if table.last_row_id is None:
        # Get the last row id and add that to the table
        last_record = await get_most_recent_record(WEXA_TABLES, str(table_id))

        if last_record is not None:
            last_record_id = last_record.get("row_id") or 0
            table.last_row_id = last_record_id

            await mongodb.db.tables.update_one(
                {"_id": table_id},
                {"$set": {"last_row_id": last_record_id}},
            )
        else:
            table.last_row_id = 0

            await mongodb.db.tables.update_one(
                {"_id": table_id},
                {"$set": {"last_row_id": 0}},
            )

    return table

async def update_table_name(data: RenameTable, user_id: str):
    try:
        # check if the name already exists in the projectID
        table_exists = await mongodb.db.tables.find_one(
            {"user_id": user_id, "table_name": data.table_name}
        )
        if table_exists and table_exists["_id"] != PyObjectId(data.table_id):
            raise HTTPException(
                status_code=400,
                detail=f"Table with name {data.table_name} already exists",
            )


        updated_table = await mongodb.db.tables.update_one(
            {"_id": ObjectId(data.table_id)},
            {"$set": {"table_name": data.table_name}},
        )
        if updated_table.modified_count > 0:
            return f"Successfully updated table name to {data.table_name}"
        raise HTTPException(status_code=500, detail="Failed to update table name")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to update table name")



async def get_table_view(table_id: str, fields: List[str]):
    result = await get_table_details(PyObjectId(table_id))
    db = mongodb.client.get_database(WEXA_TABLES)
    collection = db.get_collection(table_id)
    projection = {field: 1 for field in fields}
    records = await collection.find({}, projection).to_list(length=100)
    return {"records": records, "meta_data": result.dict(by_alias=True)}

async def fetch_latest_row_id(
    table_id: PyObjectId,
    session: AsyncIOMotorClientSession | None = None,
) -> int:
    await get_table_details(table_id)

    table_with_row_id = await mongodb.db.tables.find_one_and_update(
        {"_id": table_id},
        {"$inc": {"last_row_id": 1}},
        return_document=pymongo.ReturnDocument.AFTER,
        session=session,
    )

    return table_with_row_id["last_row_id"]

async def insert_records(
    collection_name: str,
    items: List[Dict[str, Any]],
    user_id: str,
    return_document: Optional[bool] = False,
    projectID: Optional[str] = None,
):
    try:
        db: AsyncIOMotorDatabase = mongodb.client.get_database(WEXA_TABLES)
        response = await mongodb.db.tables.find_one(
            {"_id": PyObjectId(collection_name)}
        )
        if response is None:
            raise HTTPException(
                status_code=404, detail=f"Table {collection_name} not found"
            )

        table_meta_data = Table(**response)

        column_defaults = {
            col.column_id: col.default_value
            for col in table_meta_data.columns
            if col.default_value is not None
        }

        for item in items:
            # Prepare the record for insertion
            item["_id"] = str(ObjectId())
            item["row_id"] = await fetch_latest_row_id(table_meta_data.id)
            item["coworker_user_id"] = user_id

            # Apply column defaults if missing
            for field, default_value in column_defaults.items():
                if field not in item or (
                    item.get(field) is None or item.get(field, "") == ""
                ):
                    item[field] = default_value

        # Insert the items into the database
        result = await db[collection_name].insert_many(items)
        if return_document:
            return result.inserted_ids


        return f"Inserted {len(result.inserted_ids)} records into {collection_name}."

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to insert the records with error code {str(e)}",
        )



async def update_record(
    collection_name: str, new_record: Dict, id: str, user_id: str, projectID: str
):
    try:
        db = mongodb.client.get_database(WEXA_TABLES)
        collection = db.get_collection(collection_name)

        if "row_id" in new_record or "coworker_user_id" in new_record:
            del new_record["row_id"]
            del new_record["coworker_user_id"]

        new_record["coworker_user_id"] = user_id

        # deleting the record columns for now, if required raise a exception

        table = await mongodb.db.tables.find_one({"_id": PyObjectId(collection_name)})
        if table is None:
            raise HTTPException(status_code=404, detail="Table not found")
        columns = table["columns"]
        print("new record", new_record)
        keys = new_record.keys()

        updated_record = await collection.find_one_and_update(
            {"_id": id},
            {"$set": new_record},
            upsert=False,
            return_document=pymongo.ReturnDocument.AFTER,
        )
        if not updated_record:
            raise HTTPException(status_code=404, detail="Failed to find the record")

        return updated_record

    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred")



async def delete_record(projectID: str, table_id: str, ids: List[str], user_id: str):
    try:
        db = mongodb.client.get_database(WEXA_TABLES)
        collection = db.get_collection(table_id)

        response = await mongodb.db.tables.find_one({"_id": PyObjectId(table_id)})
        if response is None:
            raise HTTPException(status_code=404, detail="Table not found")

        table_meta_data = Table(**response)
        items = await collection.find({"_id": {"$in": ids}}).to_list(length=None)
        result = await collection.delete_many({"_id": {"$in": ids}})
        return {"deleted_count": result.deleted_count}

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete the records")

async def get_records_count(collection_name: str) -> int:
    try:
        db = mongodb.client.get_database(WEXA_TABLES)

        collection = db.get_collection(collection_name)

        total_count = await collection.count_documents({"is_deleted": {"$ne": True}})

        return total_count
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to insert the records")

async def get_records(
    collection_name: str,
    page: int,
    sort: Optional[int],
    sort_key: Optional[str],
    page_size: int,
    query: Optional[str],
):
    try:
        db = mongodb.client.get_database(WEXA_TABLES)
        # sort_list = {sort_key: sort} if sort_key else {"_id": 1}
        sort_list = [(sort_key, sort)] if sort_key else [("row_id", 1)]
        skip = (page - 1) * page_size

        collection: AsyncIOMotorCollection = db.get_collection(collection_name)

        total_count = await collection.count_documents({"is_deleted": {"$ne": True}})

        # sort_list = [(sort_key, sort)] if sort_key else [("_id", 1)]
        sort_list = [(sort_key, sort)] if sort_key else [("row_id", 1)]
        records_cursor = (
            collection.find({query}).sort(sort_list).skip(skip).limit(page_size)  # type: ignore
        )
        records = await records_cursor.to_list(page_size)
        return {"total_count": total_count, "records": records}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Could not get the collections list"
        )


async def get_record(database: str, collection_name: str, id: str):
    try:
        db = mongodb.client.get_database(WEXA_TABLES)

        record: dict = await db[collection_name].find_one(
            {"_id": id, "is_deleted": {"$ne": True}}
        )  # type: ignore

        if record is None or record.get("is_deleted", False):
            raise HTTPException(status_code=404, detail="Failed to find the record")

        record["_id"] = str(record["_id"])

        return record
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get the record")

async def delete_record(projectID: str, table_id: str, ids: List[str], user_id: str):
    try:
        db = mongodb.client.get_database(WEXA_TABLES)
        collection = db.get_collection(table_id)

        response = await mongodb.db.tables.find_one({"_id": PyObjectId(table_id)})
        if response is None:
            raise HTTPException(status_code=404, detail="Table not found")

        table_meta_data = Table(**response)
        items = await collection.find({"_id": {"$in": ids}}).to_list(length=None)
        result = await collection.delete_many({"_id": {"$in": ids}})
        return {"deleted_count": result.deleted_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete the records")


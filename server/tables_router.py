
from typing import Any, Dict, List, Optional

import pymongo
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from motor.motor_asyncio import (
    AsyncIOMotorClientSession,
    AsyncIOMotorDatabase,
)

from server.common.database.mongodb import client as mongodb
from server.common.models.mongodb import PyObjectId
from server.table_models import (
    Column,
    CreateTableInput,
    DeleteStorageModel,
    GetRecordsListResponse,
    GetTablesResponse,
    RenameTable,
    Table,
)
from server.tables_helper import (
    delete_record,
    get_record,
    get_records,
    get_records_count,
    get_table_names,
    get_tables,
    insert_records,
    update_record,
    update_table_name,
)
from server.tables_helper import create_table as create_table_helper
router = APIRouter()

@router.get("/tables/{projectID}/{user_id}", response_model=GetTablesResponse)
async def get_tables(
    projectID: str,
    user_id: str,
    limit: int = 50,
    # after_id: Optional[str] = None,
    after_id: Optional[int] = None,
    search_key: Optional[str] = None,
):
    try:
        query: dict[str, Any] = {"projectID": projectID, "user_id": user_id}
        if after_id:
            # query["_id"] = {"$gt": ObjectId(after_id)}  # type: ignore
            query["row_id"] = {"$gt": after_id}  # type: ignore
        if search_key:
            query["$or"] = [
                {"table_name": {"$regex": search_key, "$options": "i"}},
            ]

        total_count = await mongodb.db.tables.count_documents(query)

        tables_in_db = await mongodb.db.tables.find(query).limit(limit).to_list(None)
        tables = [Table(**table) for table in tables_in_db]

        return GetTablesResponse(tables=tables, total_count=total_count)
    except HTTPException as e:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.put("/table/rename/{projectID}")
async def rename_table(projectID: str, data: RenameTable):
    try:
        return await update_table_name(data, projectID)
    except HTTPException as e:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/create/table", response_model=Table)
async def create_table(
    table_data: CreateTableInput,
):
    try:
        table = await create_table_helper(table_data=table_data)
        return table
    except HTTPException as e:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tables/{projectID}/{collection_name}")
async def create_records(
    projectID: str,
    collection_name: str,
    records: List[Dict],
    user_id: str
):
    try:
        existing_records_count = await get_records_count(collection_name)

        result = await insert_records(
            collection_name, records, user_id, projectID=projectID
        )

        return result

    except HTTPException as e:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tables/{projectID}/{table_id}")
async def get_records_list(
    projectID: str,
    table_id: str,
    page: int = Query(1, gt=0),
    page_size: int = Query(50, gt=0),
    sort: Optional[int] = None,
    sort_key: Optional[str] = None,
    query: Optional[str] = None,
):
    try:
        table_in_db = await mongodb.db.tables.find_one(
            {"_id": ObjectId(table_id), "projectID": projectID}
        )
        if not table_in_db:
            raise HTTPException(
                status_code=404, detail=f"The table with id {table_id} does not exist"
            )

        table_data = await get_records(
            query=query,
            collection_name=table_id,
            page=page,
            sort=sort,
            sort_key=sort_key,
            page_size=page_size,
        )
        return GetRecordsListResponse.model_validate(
            {**table_data, "meta_data": table_in_db}
        )
    except HTTPException as e:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/storage/{projectID}/{collection_name}/{record_id}")
async def get_record_data(
    projectID: str,
    collection_name: str,
    record_id: str,
):
    return await get_record(projectID, collection_name, record_id)

@router.put("/storage/{projectID}/{tableId}/{record_id}/{user_id}")
async def update_record_data(
    projectID: str,
    tableId: str,
    user_id: str,
    record_id: str,
    record: Dict,
    
):
    return await update_record(tableId, record, record_id, user_id, projectID)


@router.delete("/storage/{projectID}/{tableId}/{user_id}")
async def delete_record_in_db(
    projectID: str,
    tableId: str,
    user_id: str,
    record_ids: DeleteStorageModel,

):
    record_ids_dict = record_ids.model_dump()
    return await delete_record(
        projectID, tableId, record_ids_dict["storage_ids"], user_id
    )

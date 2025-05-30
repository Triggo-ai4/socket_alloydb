
from ..modules import ws_manager, chat_service, blob_service, database_service, search_service
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import JSONResponse
from ..models import schemas as schemas
from ..context import analysis
from ..context import legal
from typing import Optional, List
import json
import io

router = APIRouter()

@router.delete("/v1/folder/{folder_id}/analysis/{analysis_id}/file/{file_id}")
async def stop_chat_stream(request: Request, folder_id: str, file_id: str, analysis_id:str):
    authorization_header = request.headers.get('Authorization')
    if authorization_header and authorization_header.startswith('Bearer '):
        token = authorization_header.split('Bearer ')[1]
    else:
        token = authorization_header
        
    if token in ws_manager.active_connections:
        delete = analysis.delete_file_by_id(collection=database_service.collection_legal, folder_id=folder_id, file_id=file_id)
        if delete:
            search_service.delete_documents(index_name=folder_id, url=delete)
            return JSONResponse({"message": "File deleted successfully"})
        else:
            raise HTTPException(status_code=400, detail="Failed to upload file")
    else:
        raise HTTPException(status_code=401, detail="user not connected")
        
        
@router.delete("/v1/folder/{folder_id}/analysis/{analysis_id}/comment/{comment_id}")
async def stop_chat_stream(request: Request, folder_id: str, analysis_id:str, comment_id:str):
    authorization_header = request.headers.get('Authorization')
    if authorization_header and authorization_header.startswith('Bearer '):
        token = authorization_header.split('Bearer ')[1]
    else:
        token = authorization_header
        
    if token in ws_manager.active_connections:
        delete = legal.delete_message_with_feedback(collection=database_service.collection_legal, folder_id=folder_id, analysis_id=analysis_id, comment_id=comment_id)
        if delete:
            return JSONResponse({"message": "Comment deleted successfully"})
        else:
            raise HTTPException(status_code=400, detail="Failed to deleted comment")
    else:
        raise HTTPException(status_code=401, detail="user not connected")
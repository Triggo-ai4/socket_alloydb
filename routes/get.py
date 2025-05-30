from ..modules import ws_manager, chat_service, blob_service, database_service
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query, Request, UploadFile, File
from ..middleware.loginRequiredMiddleware import decode_jwt_token
from ..context import chat as chat_db
from ..context import legal
from ..context import user

router = APIRouter()

@router.get("/v1/chat/{chat_id}/message/{message_id}/origin/{id}/page/{page}")
async def return_origin(request: Request, chat_id: str, message_id: str, id: str, page: str):
    authorization_header = request.headers.get('Authorization')
    if authorization_header and authorization_header.startswith('Bearer '):
        token = authorization_header.split('Bearer ')[1]
    else:
        token = authorization_header
    if token in ws_manager.active_connections:
        origins = chat_db.get_origin(collection=database_service.collection, chat_id=chat_id, message_id=message_id, id=id, page=page)
        if origins:
            return origins
        else:
            return None
    else:
        raise HTTPException(status_code=401, detail="user not connected")

@router.get("/v1/folder/{folder_id}/analysis/{analysis_id}/message/{message_id}/origin/{id}/page/{page}")
async def return_origin(request: Request, folder_id: str, analysis_id:str, message_id: str, id: str, page: str):
    authorization_header = request.headers.get('Authorization')
    if authorization_header and authorization_header.startswith('Bearer '):
        token = authorization_header.split('Bearer ')[1]
    else:
        token = authorization_header
    if token in ws_manager.active_connections:
        origins = legal.get_origin(collection=database_service.collection_legal, folder_id=folder_id, analysis_id=analysis_id, message_id=message_id, id=id, page=page)
        if origins:
            return origins
        else:
            return None
    else:
        raise HTTPException(status_code=401, detail="user not connected")
    
@router.get("/v1/user")
async def return_origin(request: Request):
    authorization_header = request.headers.get('Authorization')
    if authorization_header and authorization_header.startswith('Bearer '):
        token = authorization_header.split('Bearer ')[1]
    else:
        token = authorization_header
        
    payload = await decode_jwt_token(token)   
    
    if payload:
        result = user.get_context(collection=database_service.collection_data_user, agent_id=payload['agent_id'])
        payload['context'] = result
        return payload
    else:
        raise HTTPException(status_code=401, detail="Invalid token or expired")
    
@router.get("/v1/folder/{folder_id}/analysis/{analysis_id}/file")
async def return_origin(request: Request, folder_id: str, analysis_id:str):
    authorization_header = request.headers.get('Authorization')
    if authorization_header and authorization_header.startswith('Bearer '):
        token = authorization_header.split('Bearer ')[1]
    else:
        token = authorization_header
        
    
    if token in ws_manager.active_connections:
        try:
            response = legal.get_files_folder(collection=database_service.collection_legal, folder_id=folder_id)
            filtered_response = [item for item in response if item['id'] == analysis_id]
            return filtered_response[0]
        except:
            raise HTTPException(status_code=404, detail="File not found")
    else:
        raise HTTPException(status_code=401, detail="Invalid token or expired")

from ..modules import ws_manager, chat_service, blob_service, database_service
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import JSONResponse
from ..models import schemas as schemas
from ..context import chat as chat_db
from ..context import feedback as feedback_db
from typing import Optional, List
from ..context import analysis
from ..context import legal
from datetime import datetime
import uuid
import json
import io

router = APIRouter()

@router.post("/v1/chat/upload/file")
async def stop_chat_stream(request: Request, file: UploadFile = File(...)):
    authorization_header = request.headers.get('Authorization')
    if authorization_header and authorization_header.startswith('Bearer '):
        token = authorization_header.split('Bearer ')[1]
    else:
        token = authorization_header
        
    if token in ws_manager.active_connections:
        contents = await file.read()
        arq = io.BytesIO(contents)
        filename = file.filename
        upload = await blob_service.upload_file(agent_id=request.state.user['agent_id'], user_id=request.state.user['user_id'], name=filename, arq_bytes=arq )
        if upload:
            return JSONResponse(upload)
        else:
            raise HTTPException(status_code=400, detail="Failed to upload file")
    else:
        raise HTTPException(status_code=401, detail="user not connected")
        
@router.post("/v1/ws/message")
async def stop_chat_stream(request: Request, message:schemas.ProcessingAnalysis):
    authorization_header = request.headers.get('Authorization')
    if authorization_header and authorization_header.startswith('Bearer '):
        token = authorization_header.split('Bearer ')[1]
    else:
        token = authorization_header
    if token in ws_manager.active_connections:
        if message:
            await ws_manager.send_personal_message(json.dumps(message.dict()), token)
            return {"status": "success", "message": "Message sent successfully"}
        else:
            raise HTTPException(status_code=400, detail="Error stopping stream")
    else:
        raise HTTPException(status_code=401, detail="user not connected")

@router.post("/v1/chat/stop")
async def stop_chat_stream(request: Request, chat_id: schemas.StopStreamRequest):
    chat_id = chat_id.chat_id
    authorization_header = request.headers.get('Authorization')
    if authorization_header and authorization_header.startswith('Bearer '):
        token = authorization_header.split('Bearer ')[1]
    else:
        token = authorization_header
    if token in ws_manager.active_connections:
        success = await chat_service.stop_stream_func(chat_id)
        
        if success:
            await ws_manager.send_personal_message(json.dumps({"stop": True}), token)
            return {"status": "success", "message": "Stream stopped successfully"}
        else:
            raise HTTPException(status_code=400, detail="Error stopping stream")
    else:
        raise HTTPException(status_code=401, detail="user not connected")
    
@router.post("/v1/chat/feedback")
async def stop_chat_stream(request: Request, data: schemas.FeedBackRequest):
    authorization_header = request.headers.get('Authorization')
    if authorization_header and authorization_header.startswith('Bearer '):
        token = authorization_header.split('Bearer ')[1]
    else:
        token = authorization_header
    if token in ws_manager.active_connections:
        data.agent_id = request.state.user['agent_id']
        data.user_id = request.state.user['user_id']
        data.email = request.state.user['email']
        if not data.message:
            data.message=""
        
        chat = analysis.get_analysis(collection=database_service.collection_legal, request=data)
        verf = False
        if chat:
            history = chat["history"]

            previous_message = None

            for message in history:
                message_id = message['message_id'] 
                owner = message['owner'] 
                msg_content = message['msg'] 
                timestamp = message['timestamp']  

                if message_id == data.message_id:
                    if previous_message:
                        feedback = schemas.FeedBackRequest(agent_id=data.agent_id,
                                            user_id=token,
                                            email=data.email,
                                            folder_id=data.folder_id,
                                            analysis_id=data.analysis_id,
                                            feedback=data.feedback,
                                            message=data.message,
                                            message_id_agent=message_id,
                                            message_id_user=previous_message['message_id'],
                                            body_agent=msg_content,
                                            body_user=previous_message['msg'],
                                            timestamp=timestamp)
                        verf = feedback_db.insert_feedback(collection=database_service.collection_feedback, request=feedback)
                        break
                previous_message = message
            if verf:
                return {"status": "success", "message": "Feedback sent successfully"}
            else:
                return {"status": "error", "message": "Error sending feedback"}
        else:
            raise HTTPException(status_code=404, detail="Chat not found")
    else:
        raise HTTPException(status_code=401, detail="user not connected")

@router.post("/v1/analysis/feedback")
async def stop_chat_stream(request: Request, data: schemas.FeedBackFolderRequest):
    authorization_header = request.headers.get('Authorization')
    if authorization_header and authorization_header.startswith('Bearer '):
        token = authorization_header.split('Bearer ')[1]
    else:
        token = authorization_header
        
    if token in ws_manager.active_connections:
        try:
            analysis_data = analysis.get_analysis(collection=database_service.collection_legal,
                                                request=schemas.ChatRequest(
                                                        action="get_analysis",
                                                        folder_id=data.folder_id,
                                                        analysis_id=data.analysis_id
                                                    )
            )
            message_id_to_find = data.message_id
            message_data = next((item for item in analysis_data["data"] if item['message_id'] == message_id_to_find), None)
            feedback = schemas.FeedBackAnalysis(
                folder_id=data.folder_id,
                analysis_id=data.analysis_id,
                email=request.state.user['email'],
                message_id=message_data["message_id"],
                data=message_data,
                feedback=data.feedback
            )
            result = feedback_db.insert_feedback_analysis(collection=database_service.collection_feedback, request=feedback)

            if result:
                return {"message": "Feedback sent successfully"}
            else:
                raise HTTPException(status_code=400, detail="Error sending feedback")
        except:
            raise HTTPException(status_code=400, detail="Folder or Analysis not found")
    else:
        raise HTTPException(status_code=401, detail="user not connected")

@router.post("/v1/chat/generic/feedback")
async def stop_chat_stream(request: Request, data: schemas.FeedBackRequestChat):
    authorization_header = request.headers.get('Authorization')
    if authorization_header and authorization_header.startswith('Bearer '):
        token = authorization_header.split('Bearer ')[1]
    else:
        token = authorization_header
    if token in ws_manager.active_connections:
        data.agent_id = request.state.user['agent_id']
        data.user_id = request.state.user['user_id']
        data.email = request.state.user['email']
        if not data.message:
            data.message=""
        
        chat = chat_db.find_chat(collection=database_service.collection, request=data)
        chat = chat.model_dump()
        verf = False
        if chat:
            history = chat["history"]

            previous_message = None

            for message in history:
                message_id = message['message_id'] 
                owner = message['owner'] 
                msg_content = message['msg'] 
                timestamp = message['timestamp']  

                if message_id == data.message_id:
                    if previous_message:
                        feedback = schemas.FeedBackChat(agent_id=data.agent_id,
                                            user_id=token,
                                            email=data.email,
                                            chat_id=data.chat_id,
                                            feedback=data.feedback,
                                            message=data.message,
                                            message_id_agent=message_id,
                                            message_id_user=previous_message['message_id'],
                                            body_agent=msg_content,
                                            body_user=previous_message['msg'],
                                            timestamp=timestamp)
                        verf = feedback_db.insert_feedback_chat(collection=database_service.collection_feedback, request=feedback)
                        break
                previous_message = message
            if verf:
                return {"status": "success", "message": "Feedback sent successfully"}
            else:
                return {"status": "error", "message": "Error sending feedback"}
        else:
            raise HTTPException(status_code=404, detail="Chat not found")
    else:
        raise HTTPException(status_code=401, detail="user not connected")
    
@router.post("/v1/folder/{folder_id}/analysis/{analysis_id}/comment")
async def stop_chat_stream(request: Request, folder_id:str, analysis_id:str, data: schemas.Message):
    authorization_header = request.headers.get('Authorization')
    if authorization_header and authorization_header.startswith('Bearer '):
        token = authorization_header.split('Bearer ')[1]
    else:
        token = authorization_header
        
    if token in ws_manager.active_connections:
        try:
            feedback = schemas.FeedbackAnalysisMessage(
                comment_id=str(uuid.uuid4()),
                email=request.state.user['email'],
                name=request.state.user['name'],
                user_id=request.state.user['user_id'],
                message=data.message,
                timestamp=datetime.utcnow().isoformat()
            )
            
            result = legal.insert_message_with_feedback(collection=database_service.collection_legal, folder_id=folder_id, analysis_id=analysis_id, feedback=feedback)
            feedback_dict = feedback.model_dump()
            feedback_dict['can_delete'] = True
            if result:
                return {"message": "Feedback sent successfully", "comment": feedback_dict}
            else:
                raise HTTPException(status_code=400, detail="Error sending feedback")
        except:
            raise HTTPException(status_code=400, detail="Folder or Analysis not found")
    else:
        raise HTTPException(status_code=401, detail="user not connected")
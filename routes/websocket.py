from ..modules import ws_manager, chat_service, search_service, prompt_service, database_service, agent_service 
from ..middleware.loginRequiredMiddleware import decode_jwt_token
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..models import schemas as schemas
from ..context import chat as chat_db
from ..context import legal as legal
from ..context import feedback as feedback_db
from ..utils import utils as utils
from datetime import datetime
from typing import Optional
import urllib.parse
import unicodedata
import json
import uuid
import re

router = APIRouter()

@router.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    await ws_manager.connect(websocket, token)
    await ws_manager.send_personal_message(
        json.dumps({"connection": "on"}), token)
    try:
        payload = await decode_jwt_token(token)
        
        if not payload:
            await ws_manager.send_personal_message(
                json.dumps({"error": "Invalid token or expired"}), token)
            raise Exception("Invalid token or expired")
        
        history = {}    
        
        while True:
            data = await websocket.receive_text()
            await ws_manager.send_personal_message(json.dumps({"message": "Message received."}), token)
            try:
                request = schemas.ChatRequest.parse_raw(data)
                #print("request", request)  
                request.agent_id = payload['agent_id']
                request.user_id = payload['user_id']
                request.email = payload['email']
                request.ia_search = payload['ia_search']
                request.agent_type = payload['agent_type']
                #request.context = ""
                
                
                diretrizes = legal.get_instructions(collection=database_service.collection_data_user, request=request)
                match request.action:
                    case "personal_data":
                        await ws_manager.send_personal_message(
                            json.dumps(payload), token)
                        
                    case "create_index":
                        await ws_manager.send_personal_message(
                            schemas.ProcessingResponse(processing=True).model_dump_json(), token)
                        analysis_folder = legal.insert_analysis(collection=database_service.collection_legal, request=request)
                        utils.run_pipeline(token=token, name=analysis_folder.ia_search, id=analysis_folder.folder_id, file_id=analysis_folder.urls[0]['id'], name_file=urllib.parse.unquote(analysis_folder.urls[0]["name"]))
                        await ws_manager.send_personal_message(json.dumps(analysis_folder.dict()), token)
                        await ws_manager.send_personal_message(
                            schemas.ProcessingResponse(processing=False).model_dump_json(), token)
                    
                    case "reset_analyze":
                        await ws_manager.send_personal_message(
                            schemas.ProcessingResponse(processing=True).model_dump_json(), token)
                        analysis_folder = legal.edit_folder(collection=database_service.collection_legal, request=request, pct=5, status=[{"message": 'Creating folder', "status": "sucess"}, {"message": 'Calculated index', "status": "processing"}])
                        utils.run_pipeline_reset_index(token=token, name=request.ia_search, id=request.folder_id, file_id=analysis_folder['urls'][-1]['id'], name_file=urllib.parse.unquote(analysis_folder['urls'][-1]["name"]))
                        await ws_manager.send_personal_message(json.dumps(analysis_folder), token)
                        await ws_manager.send_personal_message(
                            schemas.ProcessingResponse(processing=False).model_dump_json(), token)
                        
                    case "get_chats_v2":
                        response = chat_db.get_chats(collection=database_service.collection, request=request)
                        response = utils.categorize_chats_by_date(response)
                        await ws_manager.send_personal_message(json.dumps(response), token)
                        
                    case "get_chat_history":
                        response = chat_db.get_chat_history(collection=database_service.collection, request=request)
                        feedbacks = feedback_db.get_feedback_by_chat(collection=database_service.collection_feedback, chat_id=request.chat_id)
                        
                        if feedbacks:
                            for feedback in feedbacks:
                                for message in response:
                                    if feedback['message_id_agent'] == message['message_id']:
                                        message['feedback'] = feedback['feedback']
                                        message['feedback_message'] = feedback['message']
                        await ws_manager.send_personal_message(json.dumps(response), token)
                        
                    case "rename_chat":
                        response = chat_db.rename_chat(collection=database_service.collection, request=request)
                        if response:
                            await ws_manager.send_personal_message(
                                json.dumps({"status": "success", "message": "Chat renamed successfully"}), token)
                        else:
                            await ws_manager.send_personal_message(
                                json.dumps({"status": "error", "message": "Error renaming chat"}), token) 
                                
                    case "delete_chat":
                        response = chat_db.delete_chat(collection=database_service.collection, request=request)
                        if response:
                            await ws_manager.send_personal_message(
                                json.dumps({"status": "success", "message": "Chat deleted successfully"}), token)
                        else:
                            await ws_manager.send_personal_message(
                                json.dumps({"status": "error", "message": "Error deleting chat"}), token)  
                                    
                    case "check_index_creation":
                        analysis_folder = legal.search_analysis_by_folder(collection=database_service.collection_legal, request=request)
                        normalized_status = []
                        for entry in analysis_folder['status']:
                            normalized_entry = {
                                "message": unicodedata.normalize('NFKD', 
                                            urllib.parse.unquote(entry['message'])).encode('ascii', 'ignore').decode('utf-8'),
                                "status": entry['status']
                            }
                            normalized_status.append(normalized_entry)
                            
                            filtered_status = []
                            success_messages = set()

                            for msg in normalized_status:
                                if msg["message"] == "Creating folder":
                                    filtered_status.append(msg)
                                if msg["status"] == "success":
                                    success_messages.add(msg["message"])

                            for msg in normalized_status:
                                if msg["status"] == "success":
                                    filtered_status.append(msg)
                                elif msg["status"] == "processing" and msg["message"] not in success_messages:
                                    filtered_status.append(msg)

                        normalized_status = filtered_status
                        
                        if analysis_folder['pct'] == 100:
                            await ws_manager.send_personal_message(
                                schemas.ProcessingAnalysis(processing=False, pct=int(analysis_folder['pct']), message=normalized_status, folder_id=request.folder_id, analysis_id=analysis_folder['analysis'][-1]['analysis_id']).model_dump_json(), token) 
                        else:
                            await ws_manager.send_personal_message(
                                schemas.ProcessingAnalysis(processing=True, pct=int(analysis_folder['pct']), message=normalized_status, folder_id=request.folder_id, analysis_id=None).model_dump_json(), token)
                        
                    case "get_folders":
                        response = legal.get_folders(collection=database_service.collection_legal, request=request)
                        await ws_manager.send_personal_message(json.dumps(response), token)

                    case "get_analysis":
                        response = legal.get_analysis(collection=database_service.collection_legal, request=request)
                        await ws_manager.send_personal_message(json.dumps(response), token)

                    case "rename_folder":
                        response = legal.rename_analysis(collection=database_service.collection_legal, request=request)
                        if response:
                            await ws_manager.send_personal_message(
                                json.dumps({"status": "success", "message": "Chat renamed successfully"}), token)
                        else:
                            await ws_manager.send_personal_message(
                                json.dumps({"status": "error", "message": "Error renaming chat"}), token)

                    case "delete_folder":
                        response = legal.delete_folder(collection=database_service.collection_legal, request=request)
                        if response:
                            await ws_manager.send_personal_message(
                                json.dumps({"status": "success", "message": "Chat deleted successfully"}), token)
                        else:
                            await ws_manager.send_personal_message(
                                json.dumps({"status": "error", "message": "Error deleting chat"}), token)

                    case "delete_analysis":
                        delete = legal.delete_file_by_id(collection=database_service.collection_legal, folder_id=request.folder_id, file_id=request.analysis_id)
                        response = legal.delete_analysis(collection=database_service.collection_legal, request=request)
                        if response:
                            search_service.delete_documents(index_name=request.ia_search, url=delete)
                            await ws_manager.send_personal_message(
                                json.dumps({"status": "success", "message": "Chat deleted successfully"}), token)
                        else:
                            await ws_manager.send_personal_message(
                                json.dumps({"status": "error", "message": "Error deleting chat"}), token)

                    case "send_message":
                            try:
                                await ws_manager.send_personal_message(
                                    schemas.ProcessingResponse(processing=True).model_dump_json(), token)
                                
                                await ws_manager.send_personal_message(
                                    schemas.LoadResponse(load=True).model_dump_json(), token)
                                
                                message=schemas.ChatMessage(
                                            message_id=str(uuid.uuid4()),
                                            owner="user",
                                            msg=request.message,
                                            timestamp=datetime.utcnow().isoformat()
                                )
                            except Exception as e:
                                print("Erro ao processar a mensagem:", str(e))
                            
                            if request.folder_id != None and request.analysis_id != None:
                                data = legal.insert_message(
                                    collection=database_service.collection_legal, 
                                    request=request,
                                    message=message
                                )
                            else:
                                chat = chat_db.find_chat(collection=database_service.collection, request=request)
                                if not chat:
                                    chat = chat_db.insert_chat(collection=database_service.collection, request=request)
                                    chat_response = chat.model_dump()  
                                    chat_response['new_chat'] = True 
                                    await ws_manager.send_personal_message(json.dumps(chat_response), token) 
                                    
                                chat_db.insert_message(
                                    collection=database_service.collection, 
                                    chat_id=chat.chat_id,
                                    request=message
                                )
                        
                            responses_count = 0
                            message_id = str(uuid.uuid4())
                            timestamp = datetime.utcnow().isoformat()
                            ia_response = ""
                            
                            tokens_used_by_function = {}
                            generate_answer_tokens = 0
                            chat_history = []
                            user_msg = None

                            agent_service.memory.conversation_history = []
                            if token not in chat_service.chat_active:
                                chat_service.chat_active[token] = []
                            
                            if chat.chat_id not in chat_service.chat_active[token]:
                                chat_service.chat_active[token].append(chat.chat_id)
                            print(chat_service.chat_active[token])
                            
                            if request.folder_id != None and request.analysis_id != None:
                                try:
                                    for messages in data["history"][request.user_id]:
                                        if messages["owner"] == "user":
                                            user_msg = messages["msg"]
                                        elif messages["owner"] == "agent" and user_msg:
                                            agent_msg = messages["msg"]
                                            chat_history.append({"user": user_msg, "agent": agent_msg})
                                except: 
                                    print("Erro ao processar o histórico de mensagens:", str(e))
                                    chat_history = []
                            else:
                                try:
                                    if chat.history:
                                        for messages in chat.history:
                                            if str(messages.owner) == "OwnerEnum.user":
                                                user_msg = messages.msg
                                            elif str(messages.owner) == "OwnerEnum.agent" and user_msg is not None:
                                                agent_msg = messages.msg
                                                chat_history.append({"user": user_msg, "agent": agent_msg})   
                                    
                                except Exception as e:
                                    print("Erro ao processar o histórico de mensagens:", str(e))
                                    chat_history = []
                                    

                            agent_service.add_history(history=chat_history)
                            print("Adicionou histórico")
                            try:
                                #print("request", request)
                                messages, tokens_used_by_function = await agent_service.process_question(question = request.message, 
                                                                                                    index_name = request.ia_search,
                                                                                                    folder_id = request.folder_id,
                                                                                                    analysis_id = request.analysis_id,
                                                                                                    chat_id = chat.chat_id,
                                                                                                    message_id = message_id,
                                                                                                    diretrizes=diretrizes,
                                                                                                    reasoning_flag='low',
                                                                                                    context=request.context,
                                                                                                    agent_id=request.agent_id) 
                                
                                generate_answer_tokens = tokens_used_by_function["generate_answer"]
                                print("GENERATE ANSWER TOKENS: ", generate_answer_tokens)
                            except Exception as e:
                                print("Erro ao processar a pergunta:", str(e))                                                       
                            print("messages", messages)
                            
                            async for msg_ia, tokens in chat_service.create_chat_completion_stream(messages=messages, temperature=0.3):
                                if token in chat_service.chat_active and chat.chat_id in chat_service.chat_active[token]:
                                    responses_count += 1
                                    if responses_count == 1:
                                        await ws_manager.send_personal_message(
                                            schemas.LoadResponse(load=False).model_dump_json(), token)
                                    
                                    if request.analysis_id in chat_service.stop_stream:
                                        await ws_manager.send_personal_message(
                                            json.dumps({"stop": False}), token)
                                        await chat_service.clear_stop_signal(request.analysis_id )
                                        break
                                    
                                    response = schemas.ChatResponse(
                                        chat_id=request.analysis_id or chat.chat_id,
                                        message_id=message_id,
                                        owner="agent",
                                        msg=ia_response,
                                        timestamp=timestamp
                                    )
                                    
                                    ia_response += msg_ia
                                    ia_response = utils.apply_styles(ia_response)
                                    ia_response = re.sub(r'### (.*?)\n', r'***\1***\n', ia_response)
                                    ia_response = ia_response.replace("\n", "<br> ").replace("</a>", "</a><br>")
                                    ia_response = re.sub(r'(<[^>]+>)(<br\s*/?>)', r'\1', ia_response)
                                    
                                    tokens_used_by_function['generate_answer'] = {"prompt_tokens":generate_answer_tokens, "completion_tokens": tokens}
                                    await ws_manager.send_personal_message(response.model_dump_json(), token)
                                else: break
                            if token in chat_service.chat_active and chat.chat_id in chat_service.chat_active[token]:        
                                print("tokens_used_by_function: ", tokens_used_by_function)
                                message= schemas.ChatMessage(
                                    message_id=message_id,
                                    owner="agent",
                                    msg=ia_response,
                                    tokens=tokens_used_by_function,
                                    timestamp=timestamp
                                )  
                                if request.folder_id != None and request.analysis_id != None: 
                                    legal.insert_message(
                                        collection=database_service.collection_legal, 
                                        request=request,
                                        message= message
                                    )
                                else:
                                    chat_db.insert_message(
                                        collection=database_service.collection, 
                                        chat_id=chat.chat_id,
                                        request= message
                                    )
                                    
                                if request.folder_id != None and request.analysis_id != None:
                                    if request.analysis_id in search_service.previous_search_data:
                                        search_service.previous_search_data[request.analysis_id] += ia_response
                                    else:
                                        search_service.previous_search_data[request.analysis_id] = ia_response
                                else: search_service.previous_search_data[chat.chat_id] = ia_response
                                
                                await ws_manager.send_personal_message(
                                    schemas.ProcessingResponse(processing=False).model_dump_json(), token)
                            
                    case "suggested_questions":
                        await ws_manager.send_personal_message(
                            schemas.ProcessingResponse(processing=True).model_dump_json(), token)
                        
                        try:
                            if request.folder_id != None and request.analysis_id != None:
                                questions = await chat_service.generate_questions(search_service.previous_search_data[request.analysis_id])
                                del search_service.previous_search_data[request.analysis_id]
                            else:
                                questions = await chat_service.generate_questions(search_service.previous_search_data[request.chat_id])
                                del search_service.previous_search_data[request.chat_id]
                            
                            await ws_manager.send_personal_message(json.dumps(questions), token)
                            
                        except: await ws_manager.send_personal_message(json.dumps([]), token)
                        
                        await ws_manager.send_personal_message(
                            schemas.ProcessingResponse(processing=False).model_dump_json(), token)
                        
                    case _:
                        await ws_manager.send_personal_message(json.dumps({"error": "Invalid action"}), token)
            except Exception as e:
                print("Error processing request:", str(e))
                await ws_manager.send_personal_message(
                    json.dumps({"error": "Invalid request body.", "detail": str(e)}), token)
    except WebSocketDisconnect:
        print("Client disconnected")
        ws_manager.remove_agent_token(request.agent_id, token)
        ws_manager.disconnect(token)
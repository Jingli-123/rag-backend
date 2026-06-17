from fastapi import APIRouter, Request
from bson import ObjectId
from pymongo import UpdateOne
from db.mongodb import db
import json
from bson import json_util
from pydantic import BaseModel
from services.embedding import get_embedding
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from fastapi import Header, HTTPException
from services.middlewear import is_signed_in
from typing import List
import re
from fastapi.responses import StreamingResponse
from bson import ObjectId
from bson import json_util


MODEL = "gpt-4.1-nano"

client = ChatOpenAI(temperature=0,model_name=MODEL) 


router = APIRouter()

booksegments = db["booksegments"]



# create embedding by book id 
@router.post("/booksegments/embedding/{book_id}")
async def embed_book_by_clerkId(book_id: str, request: Request):
    if not is_signed_in(request):
        return{"error":"Unauthorized"}
    try:
        if not book_id:
            return {
                "message":"No Auth",
                "suceessfully_update":0
            }
        
        clean_id = book_id.strip()
        book_object_id = ObjectId(clean_id)
        
        raw_segments = list(
            db["booksegments"].find(
            {"bookId": book_object_id},
            {"_id": 1, "content": 1}
            )
        )
        
        bulk_operations = []
        for doc in raw_segments:
            segment_id = doc["_id"]
            content_text = doc.get("content")
            
            if not content_text:
                continue

            vector = get_embedding(content_text)

            bulk_operations.append(
                UpdateOne(
                    {"_id":segment_id},
                    {"$set":{"embedding":vector, "bookIdString":str(book_id)}}
                )
            )
        if bulk_operations:
            write_result = db["booksegments"].bulk_write(bulk_operations)
            modified_count += write_result.modified_count
        else:
            modified_count = 0

        return {
            "message": f"successfully embedding all chunks under {book_id}",
            "total_segments_found": len(raw_segments),
            "successfully_updated": modified_count
        }
    except Exception as e:
        return {
            "message":'Search failed', 
            "error":str(e)
        }


# create question embedding and return the answer
class QueryRequest(BaseModel):
    content: str    # user question
    clerkId: str    # Clerk ID
    bookId: str     # Book ID
    authorization: str = Header(None)
    
@router.post("/questions/embed")
async def embed_content(request_data: QueryRequest, request:Request): 
    if not is_signed_in(request):
        async def error_generator():
            yield json.dumps({"error": "Unauthorized"})
        return StreamingResponse(error_generator(), media_type="application/json")
    try:
        print("excute /questions/embed")
        # request_data 
        user_query = request_data.content.strip()
        clerk_id = request_data.clerkId.strip()
        book_id = request_data.bookId.strip()

        # 1. convert to 1536 vector
        query_vector = get_embedding(user_query)
        book_object_id = ObjectId(book_id)
        
        # 3. pipeline for search
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": 100,
                    "limit": 5,
                    "filter": {
                        "$and": [
                            {"clerkId": clerk_id},
                            {"bookId": book_object_id},
                        ]
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "content": 1,
                    "segmentIndex": 1,
                    "bookId":1,
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ]
        
        # 4. search
        search_results = []
        try:
            search_results = list(booksegments.aggregate(pipeline))
        except Exception as e:
            print("search failed",e)
        
        async def response_generator():
            if not search_results:
                yield json.dumps({
                    "event": "done",
                    "message": "Success",
                    "answer": "No answer could be found."
                })
                return

            context_text = "\n".join([
                f"Source {i+1} (Book {doc['bookId']}): {doc['content']}"
                for i, doc in enumerate(search_results)
            ])
            
            messages = [
            SystemMessage(
                content="""
                    You are a rigorous reading AI assistant.
                    Answer ONLY using the provided reference material.
                    Whenever information from a reference source is used, you MUST cite the source number inline.
                    Use the following format:
                    Example:
                    RAG improves accuracy [1].
                    RAG systems include a data layer and a model layer [2].
                    Managed RAG services are provided by cloud vendors [4].
                    Every factual statement must contain one or more citations.
                    Never omit citations.
                    The citation format MUST be:
                    [1]
                    [2]
                    [1][3]
                    Examples:
                    RAG improves accuracy [1].
                    Graph RAG uses graph structures [3].
                    Never use:
                    Source 1
                    Sources 1,2
                    【1】
                    (Source 1)
                    Do NOT provide a separate "Sources used" section.
                    """
            ),
            HumanMessage(
                content=(
                    f"[Reference Material]:\n{context_text}\n\n"
                    f"[User Question]:\n{user_query}\n\n"
                    f"Please combine the reference material above to provide a detailed, clear, and coherent answer:"
                )
            )
        ]
            final_answer = ""
            
            for chunk in client.stream(messages):
                if chunk.content:
                    final_answer += chunk.content

                    # 为了方便前端区分文本和最后的元数据，这里包一层结构（或者直接 yield chunk.content）
                    yield json.dumps({"event": "text", "data": chunk.content}) + "\n"
            
            # 当大模型流结束后，提取引用并组装你的元数据
            sources = re.findall(r"\[(\d+)\]", final_answer)
            source_numbers = sorted(set(int(s) for s in sources))
            citations = []

            for source_number in source_numbers:
                # 防止大模型胡说八道生成了越界的数字
                if 0 < source_number <= len(search_results):
                    doc = search_results[source_number - 1]
                    citations.append({
                        "source": source_number,
                        "bookId": str(doc["bookId"]),
                        "segmentIndex": doc["segmentIndex"],
                        "content": doc["content"]
                    })

            # 将最终的结构化元数据作为流的最后一行发送
            final_metadata = {
                "event": "done",
                "message": "Success",
                "source_segments": json.loads(json_util.dumps(search_results)),
                "citation": citations
            }
            yield json.dumps(final_metadata) + "\n"

        # 返回 StreamingResponse 供前端实时读取
        return StreamingResponse(response_generator(), media_type="application/x-ndjson")
        
        # if search_results:
        #     context_text = "\n".join(
        #         [
        #             f"Source {i+1} (Book {doc['bookId']}): {doc['content']}"
        #             for i, doc in enumerate(search_results)
        #         ]
        #     )
        # else:
        #     context_text = "No relevant reference document found."
    
       
        # get answer by using stream
        # final_answer=""
        # for chunk in client.stream(messages):
        #     if chunk.content:
        #         final_answer += chunk.content
        #         yield chunk.content
                
        # sources = re.findall(r"\[(\d+)\]", final_answer)
 
        # source_numbers = sorted(set(int(s) for s in sources))

        # citations = []

        # for source_number in source_numbers:
        #     doc = search_results[source_number - 1]
        #     citations.append({
        #         "source": source_number,
        #         "bookId": str(doc["bookId"]),
        #         # "title": doc["title"],
        #         "segmentIndex": doc["segmentIndex"],
        #         "content": doc["content"]
        #     })
        # return {
        #     "message": "Success",
        #     "answer": final_answer, # return to frontend
        #     "source_segments": json.loads(json_util.dumps(search_results)), #  resource content
        #     "citation":citations
        # }
    
    

    except Exception as e:
        return {"message": "Search failed", "error": str(e)}
    
    
 # create question embedding and return the answer cross multiple books
class QueryRequest(BaseModel):
    content: str    # user question
    clerkId: str    # Clerk ID
    bookIds:list[str]     # Book IDs
    authorization: str = Header(None)
    
@router.post("/questions/multiple-books/embed")
async def embed_content(request_data: QueryRequest, request:Request): 
    if not is_signed_in(request):
        return{"error":"Unauthorized"}
    try:
        print("excute multiple-books/embed")
        # request_data 
        user_query = request_data.content.strip()
        clerk_id = request_data.clerkId.strip()
        book_ids = request_data.bookIds

        # 1. convert to 1536 vector
        query_vector = get_embedding(user_query)
        
        # 3. pipeline for search
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": 100,
                    "limit": 5,
                    "filter": {
                        "clerkId": clerk_id,
                        "bookIdString": {
                            "$in":book_ids
                        }
                        }
                    # "filter": {
                    #    "clerkId":clerk_id,
                    #    "bookId":{
                    #        "$in":book_object_ids
                    #    }
                    # }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "bookId":1,
                    "content": 1,
                    "segmentIndex": 1,
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ]
        
        search_results = []
        try:
            search_results = list(booksegments.aggregate(pipeline))
        except Exception as e:
            print("search failed",e)
        async def response_generator():
            if not search_results:
                yield json.dumps({
                    "event": "done",
                    "message": "Success",
                    "answer": "No answer could be found."
                })
                return

            context_text = "\n".join([
                f"Source {i+1} (Book {doc['bookId']}): {doc['content']}"
                for i, doc in enumerate(search_results)
            ])
            
            messages = [
            SystemMessage(
                content="""
                    You are a rigorous reading AI assistant.
                    Answer ONLY using the provided reference material.
                    Whenever information from a reference source is used, you MUST cite the source number inline.
                    Use the following format:
                    Example:
                    RAG improves accuracy [1].
                    RAG systems include a data layer and a model layer [2].
                    Managed RAG services are provided by cloud vendors [4].
                    Every factual statement must contain one or more citations.
                    Never omit citations.
                    The citation format MUST be:
                    [1]
                    [2]
                    [1][3]
                    Examples:
                    RAG improves accuracy [1].
                    Graph RAG uses graph structures [3].
                    Never use:
                    Source 1
                    Sources 1,2
                    【1】
                    (Source 1)
                    Do NOT provide a separate "Sources used" section.
                    """
            ),
            HumanMessage(
                content=(
                    f"[Reference Material]:\n{context_text}\n\n"
                    f"[User Question]:\n{user_query}\n\n"
                    f"Please combine the reference material above to provide a detailed, clear, and coherent answer:"
                )
            )
        ]
            final_answer = ""
            
            for chunk in client.stream(messages):
                if chunk.content:
                    final_answer += chunk.content

                    # 为了方便前端区分文本和最后的元数据，这里包一层结构（或者直接 yield chunk.content）
                    yield json.dumps({"event": "text", "data": chunk.content}) + "\n"
            
            # 当大模型流结束后，提取引用并组装你的元数据
            sources = re.findall(r"[\[【](\d+)[\]】]", final_answer)
            source_numbers = sorted(set(int(s) for s in sources))
            citations = []

            for source_number in source_numbers:
                # 防止大模型胡说八道生成了越界的数字
                if 0 < source_number <= len(search_results):
                    doc = search_results[source_number - 1]
                    citations.append({
                        "source": source_number,
                        "bookId": str(doc["bookId"]),
                        "segmentIndex": doc["segmentIndex"],
                        "content": doc["content"]
                    })

            # 将最终的结构化元数据作为流的最后一行发送
            final_metadata = {
                "event": "done",
                "message": "Success",
                "source_segments": json.loads(json_util.dumps(search_results)),
                "citation": citations
            }
            yield json.dumps(final_metadata) + "\n"

        # 返回 StreamingResponse 供前端实时读取
        return StreamingResponse(response_generator(), media_type="application/x-ndjson")

    except Exception as e:
        return {"message": "Search failed", "error": str(e)}
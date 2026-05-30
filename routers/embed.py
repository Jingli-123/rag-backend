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



MODEL = "gpt-4.1-nano"

client = ChatOpenAI(temperature=0,model_name=MODEL) 


router = APIRouter()

booksegments = db["booksegments"]


@router.post("/booksegments/embedding/{book_id}")
async def embed_book_by_clerkId(book_id: str, request: Request):
    if not is_signed_in(request):
        return{"error":"Unauthorized"}
    try:
        # user_books = list(
        #     db["books"].find(
        #         {"clerkId": clerk_id.strip()},
        #         {"_id":1}
        #     )
        # )
        # if not user_books:
        #  return{
        #      "message":"No book found.",
        #      "suceessfully_update":0
        #  }
            
        # book_ids = [book["_id"] for book in user_books]
        # raw_segments = list(
        #     db["booksegments"].find(
        #         {"bookId":{"$in": book_ids}},
        #         {"_id":1, "content":1}
        #     )
        # )
        if not book_id:
            return {
                "message":"No Auth",
                "suceessfully_update":0
            }
        
        raw_segments = list(
            db["booksegments"].find(
                {"bookId":{"$in": book_id}},
                {"_id":1, "content":1}
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
                    {"$set":{"embedding":vector}}
                )
            )
            if bulk_operations:
                write_result = db["booksegments"].bulk_write(bulk_operations)
                modified_count = write_result.modified_count
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



@router.post("/booksegments/embed/{book_id}")
async def embed_book_by_bookId(book_id: str, request: Request):
    if not is_signed_in(request):
        return{"error":"Unauthorized"}
    try:
        clean_id = book_id.strip()
        book_object_id = ObjectId(clean_id)

        raw_segments = list(
            booksegments.find({"bookId": book_object_id})
        )

        sanitized_segments = json.loads(json_util.dumps(raw_segments))
        for doc in sanitized_segments:
            if "$oid" in doc.get("_id", {}):
                doc["_id"] = doc["_id"]["$oid"]
            if "$oid" in doc.get("bookId", {}):
                doc["bookId"] = doc["bookId"]["$oid"]


        return {
            "message": "Segments fetched",
            "count": len(sanitized_segments),
            "data": sanitized_segments
        }
    except Exception as e:
        return {
            "message":'Search failed', 
            "error":str(e)
        }
    
class QueryRequest(BaseModel):
    content: str    # user question
    clerkId: str    # Clerk ID
    bookId: str     # Book ID
    authorization: str = Header(None)
    
@router.post("/questions/embed")
async def embed_content(request_data: QueryRequest): 
    try:
        print("excute")
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
                            {"bookId": book_object_id}
                        ]
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "content": 1,
                    "segmentIndex": 1,
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ]
        
        # 4. search
        search_results = list(booksegments.aggregate(pipeline))
        if not search_results:
            return {
                "message":"Success",
                "answer":"No answer could be found."
            }
        if search_results:
            context_text = "\n".join([f"Source {i+1}: {doc['content']}" for i, doc in enumerate(search_results)])
        else:
            context_text = "No relevant reference document found."
    
        messages = [
            SystemMessage(
                content=(
                    "You are a rigorous reading AI assistant. Please strictly answer the user's question "
                    "based ON the provided [Reference Material]. If the provided material does not contain "
                    "the information needed to answer the question, please politely inform the user. "
                    "Do not make up facts or extrapolate beyond the text."
                )
            ),
            HumanMessage(
                content=(
                    f"[Reference Material]:\n{context_text}\n\n"
                    f"[User Question]:\n{user_query}\n\n"
                    f"Please combine the reference material above to provide a detailed, clear, and coherent answer:"
                )
            )
        ]

        # get answer
        response = client.invoke(messages)
        final_answer = response.content

        return {
            "message": "Success",
            "answer": final_answer, # return to frontend
            "source_segments": json.loads(json_util.dumps(search_results)) #  resource content
        }
    

    except Exception as e:
        return {"message": "Search failed", "error": str(e)}
from bson import ObjectId
from fastapi import APIRouter, Request
import json
from bson import json_util
from db.mongodb import db
from services.middlewear import is_signed_in

router = APIRouter()

books = db["books"]
booksegments = db["booksegments"]


@router.get("/books")
async def get_all_books(request:Request):
    if not is_signed_in(request):
        return{"error":"Unauthorized"}
    try:
        segments = list(
            books.find({}, {"_id": 0})
        )

        return{
            "message": "Segments fetched",
            "count": len(segments),
            "data":segments
        }
    except Exception as e:
        return {
            "message": "Error occurred",
            "error": str(e)
        }


@router.post("/book/{book_id}")
async def get_all_book_by_clerkId(book_id: str, request: Request):
    if not is_signed_in(request):
        return{"error":"Unauthorized"}
    try:
        book_object_id = ObjectId(book_id.strip())
  
        raw_segments = list(
            booksegments.find({"bookId": book_object_id})
        )
        
  
        sanitized_segments = json.loads(json_util.dumps(raw_segments))
        

        for doc in sanitized_segments:
            if "_id" in doc and "$oid" in doc["_id"]:
                doc["_id"] = doc["_id"]["$oid"]
            if "bookId" in doc and "$oid" in doc["bookId"]:
                doc["bookId"] = doc["bookId"]["$oid"]
            if "createdAt" in doc and "$date" in doc["createdAt"]:
                doc["createdAt"] = doc["createdAt"]["$date"]
            if "updatedAt" in doc and "$date" in doc["updatedAt"]:
                doc["updatedAt"] = doc["updatedAt"]["$date"]

        return {
            "message": "Success",
            "data": sanitized_segments  
        }

    except Exception as e:
        return {"message": "Error occurred", "error": str(e)}
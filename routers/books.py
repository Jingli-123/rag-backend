from bson import ObjectId
from fastapi import APIRouter
import json
from bson import json_util
from db.mongodb import db

router = APIRouter()

books = db["books"]
booksegments = db["booksegments"]

@router.get("/books")
async def get_all_books():
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
async def get_all_book_by_clerkId(book_id: str):
    try:
        book_object_id = ObjectId(book_id.strip())
        # 1. 去数据库查询（这里甚至不需要加 {"_id": 0} 了，因为下面会做完美转换）
        raw_segments = list(
            booksegments.find({"bookId": book_object_id})
        )
        
        # 2. 🔥 核心拯救步骤：把数据里所有的 Date、ObjectId 完美转成标准的 Python 基础类型
        sanitized_segments = json.loads(json_util.dumps(raw_segments))
        
        # 3. 可选的优雅优化：json_util 会把 _id 转成 {"$oid": "..."} 的嵌套格式。
        # 如果你想让前端拿到的数据干干净净，可以用下面这个小循环把它拍平：
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
            "data": sanitized_segments  # 现在绝对安全，100% 不会报 500 错误了
        }

    except Exception as e:
        return {"message": "Error occurred", "error": str(e)}
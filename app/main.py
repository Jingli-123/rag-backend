from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import embed
from routers import books

app = FastAPI()

origins = [
    "http://localhost:3000",    # Next.js 本地开发地址
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           # 允许这几个前端域名跨域访问
    allow_credentials=True,          # 允许前端请求携带 Cookie 或 认证凭证
    allow_methods=["*"],             # 允许所有的 HTTP 方法 (POST, GET, OPTIONS 等)
    allow_headers=["*"],             # 允许所有的 请求头 (Content-Type, Authorization 等)
)

app.include_router(embed.router)
app.include_router(books.router)
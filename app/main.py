from dotenv import load_dotenv

load_dotenv()
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import embed
from routers import books


app = FastAPI()

origins = [
    os.getenv("FRONT_END_URL")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          
    allow_credentials=True,         
    allow_methods=["*"],            
    allow_headers=["*"],             
)

app.include_router(embed.router)
app.include_router(books.router)
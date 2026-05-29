# Bookified RAG Backend

A FastAPI-based Retrieval-Augmented Generation (RAG) backend for Bookified, an AI-powered reading assistant.

## Features

* PDF document chunk processing
* OpenAI embedding generation
* MongoDB Atlas Vector Search
* Semantic document retrieval
* Retrieval-Augmented Question Answering (RAG)
* Clerk authentication integration (in progress)
* FastAPI REST API

## Tech Stack

* Python
* FastAPI
* MongoDB Atlas
* OpenAI API
* Pymongo
* Pydantic

## Architecture

User Question

↓

Embedding Generation

↓

MongoDB Atlas Vector Search

↓

Retrieve Relevant Chunks

↓

GPT Response Generation

↓

Answer

## API Endpoints

### Generate Answer

POST `/questions/embed`

Request:

```json
{
  "content": "What is RAG?",
  "bookId": "book_id"
}
```

Response:

```json
{
  "message": "Success",
  "answer": "...",
  "source_segments": []
}
```

## Local Development

Clone the repository:

```bash
git clone <repo-url>
cd rag-backend
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
OPENAI_API_KEY=your_key
MONGODB_URI=your_mongodb_uri
```

Run the application:

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://localhost:8000/docs
```

## Future Improvements

* JWT authentication validation
* Voice + RAG integration
* Streaming responses
* Evaluation pipeline
* Conversation history support

## Related Project

Bookified Frontend

Built with:

* Next.js
* TypeScript
* Clerk
* Vapi
* OpenAI
* MongoDB Atlas

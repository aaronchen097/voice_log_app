# API Documentation for the Voice Intelligent Log System

This document provides a detailed overview of the API endpoints available in the Voice Intelligent Log System. 

## Base URL

The base URL for all API endpoints is the root of the application.

## Endpoints

### 1. Upload Voice Log

- **Endpoint**: `/api/voice_log`
- **Method**: `POST`
- **Description**: Uploads an audio file, transcribes it, generates a summary, and saves it as a log file. The new log is then indexed for searching.
- **Request Body**:
  - `file`: The audio file to be uploaded (multipart/form-data).
- **Responses**:
  - `200 OK`: Returns a JSON object with the transcription, summary, and filename.
    ```json
    {
      "text": "The transcribed text...",
      "summary": "The AI-generated summary...",
      "filename": "log_20231027_103000.md"
    }
    ```
  - `400 Bad Request`: If the audio content cannot be recognized.
  - `500 Internal Server Error`: If an error occurs during the process.

### 2. Query Logs

- **Endpoint**: `/api/query`
- **Method**: `GET`
- **Description**: Searches the indexed logs for an answer to a given query.
- **Query Parameters**:
  - `query` (string, required): The question to search for.
- **Responses**:
  - `200 OK`: Returns a JSON object with the query and the answer.
    ```json
    {
      "query": "What was discussed yesterday?",
      "answer": "The answer to your query..."
    }
    ```
  - `404 Not Found`: If no log files are available to query.

### 3. Get Latest Summary

- **Endpoint**: `/api/latest_summary`
- **Method**: `GET`
- **Description**: Retrieves the summary of the most recent log file.
- **Responses**:
  - `200 OK`: Returns a JSON object with the latest summary information.
    ```json
    {
      "summary": "The latest summary...",
      "filename": "log_20231027_103000.md",
      "timestamp": "2023-10-27 10:30:00"
    }
    ```
  - `404 Not Found`: If no logs are found.

### 4. Generate AI Summary

- **Endpoint**: `/api/summary`
- **Method**: `POST`
- **Description**: Generates an AI-powered summary for a given text.
- **Request Body**:
  ```json
  {
    "text": "The text to be summarized...",
    "summary_type": "day_report",
    "model": "qwen-plus"
  }
  ```
  - `text` (string, required): The text to summarize.
  - `summary_type` (string, optional, default: `day_report`): The type of summary to generate. 
  - `model` (string, optional, default: `qwen-plus`): The AI model to use for summarization.
- **Responses**:
  - `200 OK`: Returns a JSON object with the generated summary.
    ```json
    {
      "summary": "The generated summary..."
    }
    ```
  - `500 Internal Server Error`: If an error occurs during summary generation.

### 5. Frontend

- **Endpoint**: `/`
- **Method**: `GET`
- **Description**: Serves the main `index.html` file for the frontend application.

- **Endpoint**: `/static/{file_path}`
- **Method**: `GET`
- **Description**: Serves static files (CSS, JavaScript, etc.) from the `frontend` directory.
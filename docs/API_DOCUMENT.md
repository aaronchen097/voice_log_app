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
  - `200 OK`: Returns a JSON object with the transcription, summary, capability assessment, and filename.
    ```json
    {
      "text": "The transcribed text...",
      "summary": "The AI-generated summary...",
      "capability_assessment": "The AI-generated personal capability assessment...",
      "filename": "log_20231027_103000.md"
    }
    ```
  - `400 Bad Request`: If the audio content cannot be recognized.
  - `500 Internal Server Error`: If an error occurs during the process.

### 2. Batch Upload Audio Segments

- **Endpoint**: `/api/batch_upload`
- **Method**: `POST`
- **Description**: Uploads multiple audio files as segments for batch processing. Each segment is stored temporarily and can be processed together.
- **Request Body**:
  - `file`: The audio file to be uploaded (multipart/form-data).
- **Responses**:
  - `200 OK`: Returns a JSON object with segment information.
    ```json
    {
      "success": true,
      "message": "音频片段上传成功",
      "segment_id": "unique_segment_id",
      "filename": "audio_segment.wav",
      "file_size": 1024000
    }
    ```
  - `400 Bad Request`: If no file is provided or file format is invalid.
  - `500 Internal Server Error`: If an error occurs during upload.

### 3. Process Batch Audio Segments

- **Endpoint**: `/api/batch_process`
- **Method**: `POST`
- **Description**: Processes all uploaded audio segments in batch. Transcribes each segment, concatenates the results in chronological order with file name markers (【filename】), and generates a unified AI summary using optimized prompts specifically designed for multi-segment content analysis. The AI prompt has been enhanced to understand cross-segment logical connections and temporal sequences.
- **Request Body**: No body required (processes all segments for current user).
- **Responses**:
  - `200 OK`: Returns a JSON object with combined transcription and summary.
    ```json
    {
      "success": true,
      "combined_text": "【segment1.wav】\nTranscription of first segment...\n\n【segment2.wav】\nTranscription of second segment...",
      "summary": "AI-generated summary of all segments using day_report mode...",
      "capability_assessment": "Personal capability assessment based on combined content...",
      "processed_segments": 3,
      "feishu_saved": true
    }
    ```
  - `400 Bad Request`: If no audio segments are available for processing.
  - `500 Internal Server Error`: If an error occurs during batch processing.

### 4. Clear Batch Audio Segments

- **Endpoint**: `/api/clear_batch`
- **Method**: `POST`
- **Description**: Clears all uploaded audio segments for the current user without processing them.
- **Request Body**: No body required.
- **Responses**:
  - `200 OK`: Returns a JSON object confirming successful clearing.
    ```json
    {
      "success": true,
      "message": "已清空当前批次的音频片段",
      "cleared_segments": 3
    }
    ```

### 5. Query Logs

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

### 6. Get Latest Summary

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

### 7. Generate AI Summary

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

### 8. Generate Personal Capability Assessment

- **Endpoint**: `/api/capability_assessment`
- **Method**: `POST`
- **Description**: Generates an AI-powered personal capability assessment based on the provided text content.
- **Request Body**:
  ```json
  {
    "text": "The text content to analyze for capability assessment..."
  }
  ```
  - `text` (string, required): The text content to analyze for personal capabilities.
- **Responses**:
  - `200 OK`: Returns a JSON object with the generated capability assessment.
    ```json
    {
      "success": true,
      "capability_assessment": "Based on the analysis of your speech content, here are the key capability insights..."
    }
    ```
  - `400 Bad Request`: If the text parameter is missing or empty.
  - `500 Internal Server Error`: If an error occurs during assessment generation.

### 9. Frontend

- **Endpoint**: `/`
- **Method**: `GET`
- **Description**: Serves the main `index.html` file for the frontend application.

- **Endpoint**: `/static/{file_path}`
- **Method**: `GET`
- **Description**: Serves static files (CSS, JavaScript, etc.) from the `static` directory. Falls back to the `frontend` directory for backward compatibility.

### 10. OAuth Authentication

#### 10.1 Initiate OAuth Login

- **Endpoint**: `/auth/login`
- **Method**: `GET`
- **Description**: Initiates the Feishu OAuth authentication process by redirecting the user to Feishu's authorization server.
- **Responses**:
  - `307 Temporary Redirect`: Redirects to Feishu OAuth authorization URL.
  - `500 Internal Server Error`: If OAuth configuration is missing or invalid.

#### 10.2 OAuth Callback

- **Endpoint**: `/auth/callback`
- **Method**: `GET`
- **Description**: Handles the OAuth callback from Feishu, exchanges the authorization code for access tokens.
- **Query Parameters**:
  - `code` (string, required): Authorization code from Feishu.
  - `state` (string, required): State parameter for CSRF protection.
- **Responses**:
  - `200 OK`: Returns a JSON object indicating successful authentication.
    ```json
    {
      "success": true,
      "message": "登录成功",
      "user_info": {
        "name": "User Name",
        "avatar_url": "https://...",
        "open_id": "ou_..."
      }
    }
    ```
  - `400 Bad Request`: If required parameters are missing or invalid.
  - `500 Internal Server Error`: If token exchange fails.

#### 7.3 Check Authentication Status

- **Endpoint**: `/auth/status`
- **Method**: `GET`
- **Description**: Checks the current authentication status of the user.
- **Responses**:
  - `200 OK`: Returns authentication status.
    ```json
    {
      "success": true,
      "is_authenticated": true,
      "user_info": {
        "name": "User Name",
        "avatar_url": "https://...",
        "open_id": "ou_..."
      }
    }
    ```
    Or if not authenticated:
    ```json
    {
      "success": true,
      "is_authenticated": false,
      "message": "未找到认证token"
    }
    ```

### 8. Traditional Login

- **Endpoint**: `/api/login`
- **Method**: `POST`
- **Description**: Traditional username/password login endpoint (for backward compatibility).
- **Request Body**:
  ```json
  {
    "username": "admin",
    "password": "password"
  }
  ```
- **Responses**:
  - `200 OK`: Returns login result.
    ```json
    {
      "success": false,
      "message": "账号或密码错误"
    }
    ```
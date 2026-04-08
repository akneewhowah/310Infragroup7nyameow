#pragma once
//Contains various functions that handle download file tasks
//Macros and dependences are imported in main.cpp and/or config.h (imported by main before this file)

// Downloads a specific file chunk from the server and "returns" the transfered data, next chunk id, and total via pointers
// Returns success/failure
int downloadChunk(std::string file_id, int chunk_id, std::string *out, int *next_chunk_id, int *total)
{
    /*
    HT: 8
    Client:
    {
        "file_id": "<file_id>",
        "chunk_id": ""
    }
    Server Response:
    {
        "message": "OK",
        "id": 0,
        "chunk": "",
        "next_chunk_id": 0,
        "total": 0
    }
    */

    // Create JSON
    json j;
    j["file_id"] = file_id;
    j["chunk_id"] = chunk_id;
    std::string sendStr = j.dump();
    std::string response = convert_and_send(sendStr, 8);

    json response_json = json::parse(response);
    //for (auto &p : response_json.items()) {
    //    COUT(p.key());
    //}
    // analysis suggests that the written spec is wrong and it does not contain the preliminary 'data' field
    /*
    if (!response_json.contains("data"))
    {
        COUT("downloadChunk error: received malformed response from server");
        return FALSE;
    }
    */

    // Parse server response for download specific data
    //Base64Decode(response_json["data"], &response); //see the big commented out block above
    //response_json = json::parse(response);  //see the big commented out block above
    if (response_json["message"] != "OK")
    {
        COUT("downloadChunk error: server indicated error when sending data");
        return FALSE;
    }

    // Return data
    std::string decodedChunk;
    Base64Decode(response_json["chunk"], &decodedChunk);
    *out = decodedChunk;
    *next_chunk_id = response_json["next_chunk_id"];
    *total = response_json["total"];
    return TRUE;
}

// Given a file_id, downloads the requested file from the server, including chunks
int downloadFile(std::string file_id, std::string task_id, std::string *out)
{
    /////////////////////
    // Send DownloadStart to the server
    /////////////////////
    *out = "";
    int next_chunk_id;
    int total;
    /*
    HT: 7
    Client:
    {
        "task_id": "<task_id>",
        "file_id": "<file_id>"
    }
    Server Response:
    {
        "message": "OK",
        "chunk": "",
        "next_chunk_id": 0,
        "total": 0
    }
    */
    // Create JSON
    json j;
    j["task_id"] = task_id;
    j["file_id"] = file_id;
    std::string sendStr = j.dump();
    std::string response = convert_and_send(sendStr, 7);

    json response_json = json::parse(response);
    if (!response_json.contains("chunk"))
    {
        COUT("downloadFile error: received malformed response from server when sending downloadStart");
        return FALSE;
    }

    // Parse server response for download specific data
    std::string decodedChunk;
    Base64Decode(response_json["chunk"], &decodedChunk);
    //response_json = json::parse(response);
    //if (response_json["message"] != "OK")
    //{
    //    COUT("downloadFile error: server indicated error when sending data");
    //    return FALSE;
    //}

    /////////////////////
    // Parse result to get next chunk
    /////////////////////

    *out += decodedChunk;
    next_chunk_id = response_json["next_chunk_id"];
    total = response_json["total"];

    /////////////////////
    // Loop downloadChunk until all data has been downloaded
    /////////////////////

    while (next_chunk_id != 0)
    {
        std::string outTemp;
        int totalTemp;
        BOOL bRet = downloadChunk(file_id, next_chunk_id, &outTemp, &next_chunk_id, &totalTemp);
        if (!bRet)
        {
            //COUT("downloadFile error: received malformed response from server"); //Print is handled downstream
            return FALSE;
        }
        total += totalTemp;
        out->append(outTemp);
    }

    /////////////////////
    // Send DownloadEnd
    /////////////////////
    /*
    HT: 9
    Client:
    {
        "task_id": "<task_id>",
        "agent_id": "<agent_id>",
        "status": 0
    }
    Server Response:
    {
        "message": "OK"
    }
    */
    j["task_id"] = task_id;
    j["agent_id"] = global_agent_id;
    j["status"] = 0;
    sendStr = j.dump();
    response = convert_and_send(sendStr, 9);

    response_json = json::parse(response);
    if (!response_json.contains("message"))
    {
        COUT("downloadFile error: received malformed response from server when sending downloadEnd");
        return FALSE;
    }

    // Parse server response for download specific data
    Base64Decode(response_json["message"], &response);
    if (response != "8")
    {
        COUT("downloadFile error: server indicated error when sending data for downloadEnd");
        return FALSE;
    }

    return TRUE;
}

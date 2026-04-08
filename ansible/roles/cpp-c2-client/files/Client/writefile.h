#pragma once
//Contains various functions that handle writing to file tasks
//Macros and dependences are imported in main.cpp and/or config.h (imported by main before this file)

BOOL WriteWholeFile(std::string& path, std::string& data)
{
    BOOL bRet = FALSE;
    HANDLE hFile = NULL;
    DWORD wSize = 0;

    // Expand environment variables
    char expanded[MAX_PATH] = { 0 };
    ExpandEnvironmentStringsA(path.c_str(), expanded, MAX_PATH);

    // use `OPEN_ALWAYS` instead of `CREATE_ALWAYS` for append if the file already exists.
    hFile = CreateFileA(expanded, GENERIC_WRITE, FILE_SHARE_WRITE, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile == INVALID_HANDLE_VALUE)
        goto Cleanup;

    if (WriteFile(hFile, data.data(), (DWORD)data.size(), &wSize, NULL) && wSize == data.size())
        bRet = TRUE;

Cleanup:
    if (hFile != INVALID_HANDLE_VALUE)
    {
        FlushFileBuffers(hFile);
        CloseHandle(hFile);
    }

    return bRet;
}


BOOL WriteWholeFile2(LPCSTR path, LPBYTE data, size_t dataSize)
{
    BOOL bRet = FALSE;
    HANDLE hFile = NULL;
    DWORD wSize = 0;

    // Expand environment variables
    char expanded[MAX_PATH] = { 0 };
    ExpandEnvironmentStringsA(path, expanded, MAX_PATH);

    hFile = CreateFileA(expanded, GENERIC_WRITE, FILE_SHARE_WRITE, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile == INVALID_HANDLE_VALUE)
        goto Cleanup;

    if (WriteFile(hFile, data, (DWORD)dataSize, &wSize, NULL) && wSize == (DWORD)dataSize)
        bRet = TRUE;

Cleanup:
    if (hFile != INVALID_HANDLE_VALUE)
    {
        FlushFileBuffers(hFile);
        CloseHandle(hFile);
    }


    return bRet;
}

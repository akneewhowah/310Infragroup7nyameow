#pragma once

// Referencing writeFile.h and labs
BOOL ReadWholeFile(std::string &path, std::string *out)
{
    BOOL bRet = FALSE;
    HANDLE hFile = NULL;
    DWORD fileSize = 0;
    DWORD bytesRead = 0;

    char expanded[MAX_PATH] = { 0 };
    ExpandEnvironmentStringsA(path.c_str(), expanded, MAX_PATH);

    // Open file for reading
    hFile = CreateFileA(expanded, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile == INVALID_HANDLE_VALUE)
        goto Cleanup;

    // Get file size
    fileSize = GetFileSize(hFile, NULL);
    if (fileSize == INVALID_FILE_SIZE || fileSize == 0)
        goto Cleanup;

    // Allocate buffer and read file contents
    out->resize(fileSize);
    if (!ReadFile(hFile, reinterpret_cast<LPVOID>(&(*out)[0]), fileSize, &bytesRead, NULL))
        goto Cleanup;

    if (bytesRead == fileSize)
        bRet = TRUE;

Cleanup:
    if (hFile != INVALID_HANDLE_VALUE)
        CloseHandle(hFile);

    if (!bRet)
        out->clear();

    return bRet;
}
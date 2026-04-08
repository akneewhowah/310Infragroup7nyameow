#include <windows.h>
#include <wincrypt.h>
#pragma comment(lib, "advapi32.lib")

bool Rc4Encrypt(const std::string &in, const std::string &key, std::string *out)
{
    HCRYPTPROV hProv = 0;
    HCRYPTHASH hHash = 0;
    HCRYPTKEY hKey = 0;
    DWORD len = 0;

    if (!CryptAcquireContext(&hProv, NULL, NULL, PROV_RSA_FULL, CRYPT_VERIFYCONTEXT))
        return false;

    if (!CryptCreateHash(hProv, CALG_MD5, 0, 0, &hHash))
        goto cleanup;

    CryptHashData(hHash, (BYTE *)key.data(), (DWORD)key.size(), 0);

    if (!CryptDeriveKey(hProv, CALG_RC4, hHash, 0, &hKey))
        goto cleanup;

    *out = in;                         // copy so we can modify in place
    len = (DWORD)out->size();
    if (!CryptEncrypt(hKey, 0, TRUE, 0, (BYTE *)&(*out)[0], &len, len))
        goto cleanup;

    CryptDestroyKey(hKey);
    CryptDestroyHash(hHash);
    CryptReleaseContext(hProv, 0);
    return true;

cleanup:
    if (hKey) CryptDestroyKey(hKey);
    if (hHash) CryptDestroyHash(hHash);
    if (hProv) CryptReleaseContext(hProv, 0);
    return false;
}

bool Rc4Decrypt(const std::string &in, const std::string &key, std::string *out)
{
    HCRYPTPROV hProv = 0;
    HCRYPTHASH hHash = 0;
    HCRYPTKEY hKey = 0;
    DWORD len = 0;

    if (!CryptAcquireContext(&hProv, NULL, NULL, PROV_RSA_FULL, CRYPT_VERIFYCONTEXT))
        return false;

    if (!CryptCreateHash(hProv, CALG_MD5, 0, 0, &hHash))
        goto cleanup;

    CryptHashData(hHash, (BYTE *)key.data(), (DWORD)key.size(), 0);

    if (!CryptDeriveKey(hProv, CALG_RC4, hHash, 0, &hKey))
        goto cleanup;

    *out = in;
    len = (DWORD)out->size();
    if (!CryptDecrypt(hKey, 0, TRUE, 0, (BYTE *)&(*out)[0], &len))
        goto cleanup;

    CryptDestroyKey(hKey);
    CryptDestroyHash(hHash);
    CryptReleaseContext(hProv, 0);
    return true;

cleanup:
    if (hKey) CryptDestroyKey(hKey);
    if (hHash) CryptDestroyHash(hHash);
    if (hProv) CryptReleaseContext(hProv, 0);
    return false;
}
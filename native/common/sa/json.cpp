#include "json.hpp"

#include <sys/stat.h>

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <ctime>

namespace sa {

bool readFile(const std::string& path, std::string& out) {
    FILE* file = std::fopen(path.c_str(), "rb");
    if (!file) return false;
    out.clear();
    char chunk[8192];
    size_t n;
    while ((n = std::fread(chunk, 1, sizeof(chunk), file)) > 0) out.append(chunk, n);
    const bool ok = !std::ferror(file);
    std::fclose(file);
    return ok;
}

std::string dirName(const std::string& path) {
    const size_t slash = path.rfind('/');
    return slash == std::string::npos ? "" : path.substr(0, slash);
}

bool makeDirs(const std::string& dir) {
    if (dir.empty()) return true;
    struct stat st;
    if (stat(dir.c_str(), &st) == 0) return S_ISDIR(st.st_mode);
    if (!makeDirs(dirName(dir))) return false;
    return mkdir(dir.c_str(), 0777) == 0 || errno == EEXIST;
}

bool writeFileAtomic(const std::string& path, const std::string& data) {
    if (!makeDirs(dirName(path))) return false;
    const std::string tmp = path + ".tmp";
    FILE* file = std::fopen(tmp.c_str(), "wb");
    if (!file) return false;
    const bool wrote = std::fwrite(data.data(), 1, data.size(), file) == data.size();
    const bool closed = std::fclose(file) == 0;
    if (!wrote || !closed) {
        std::remove(tmp.c_str());
        return false;
    }
    std::remove(path.c_str());
    return std::rename(tmp.c_str(), path.c_str()) == 0;
}

cJSON* parseFile(const std::string& path) {
    std::string text;
    if (!readFile(path, text)) return nullptr;
    return cJSON_Parse(text.c_str());
}

std::string jsonStr(const cJSON* obj, const char* key, const std::string& fallback) {
    const cJSON* item = cJSON_GetObjectItemCaseSensitive(obj, key);
    return cJSON_IsString(item) ? std::string(item->valuestring) : fallback;
}

bool jsonToInt(const cJSON* item, int64_t& out) {
    if (cJSON_IsBool(item)) {
        out = cJSON_IsTrue(item) ? 1 : 0;
        return true;
    }
    if (cJSON_IsNumber(item)) {
        out = static_cast<int64_t>(item->valuedouble);
        return true;
    }
    if (cJSON_IsString(item)) {
        char* end = nullptr;
        out = static_cast<int64_t>(std::strtoull(item->valuestring, &end, 0));
        return end && *end == '\0' && end != item->valuestring;
    }
    return false;
}

int64_t jsonInt(const cJSON* obj, const char* key, int64_t fallback) {
    int64_t value;
    return jsonToInt(cJSON_GetObjectItemCaseSensitive(obj, key), value) ? value : fallback;
}

bool jsonBool(const cJSON* obj, const char* key, bool fallback) {
    const cJSON* item = cJSON_GetObjectItemCaseSensitive(obj, key);
    return cJSON_IsBool(item) ? cJSON_IsTrue(item) : fallback;
}

std::string printJson(const cJSON* root) {
    char* raw = cJSON_PrintUnformatted(root);
    if (!raw) return "";
    std::string out(raw);
    cJSON_free(raw);
    return out;
}

std::string isoNowUtc() {
    const std::time_t now = std::time(nullptr);
    std::tm parts{};
    gmtime_r(&now, &parts);
    char buf[40];
    std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S+00:00", &parts);
    return buf;
}

}  // namespace sa

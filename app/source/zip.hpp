#pragma once

#include <cstdint>
#include <functional>
#include <string>
#include <vector>

namespace app {

struct ZipEntry {
    std::string name;
    uint16_t method = 0;
    uint32_t crc = 0;
    uint32_t compressed = 0;
    uint32_t size = 0;
    uint32_t localOffset = 0;
};

// Leitor de zip em memória: só "stored" (0) e "deflate" (8), sem zip64.
class ZipReader {
public:
    bool open(const std::vector<uint8_t>& data, std::string& error);
    const std::vector<ZipEntry>& entries() const { return m_entries; }
    bool extract(const ZipEntry& entry, std::vector<uint8_t>& out, std::string& error) const;

private:
    const std::vector<uint8_t>* m_data = nullptr;
    std::vector<ZipEntry> m_entries;
};

}  // namespace app

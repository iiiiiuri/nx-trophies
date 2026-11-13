#include "zip.hpp"

#include <zlib.h>

#include <cstring>

namespace app {

namespace {

uint16_t le16(const uint8_t* p) { return static_cast<uint16_t>(p[0] | (p[1] << 8)); }
uint32_t le32(const uint8_t* p) { return p[0] | (p[1] << 8) | (p[2] << 16) | (static_cast<uint32_t>(p[3]) << 24); }

}  // namespace

bool ZipReader::open(const std::vector<uint8_t>& data, std::string& error) {
    m_data = &data;
    m_entries.clear();
    if (data.size() < 22) {
        error = "zip curto demais";
        return false;
    }
    size_t eocd = std::string::npos;
    const size_t floor = data.size() > 0x10000 + 22 ? data.size() - 0x10000 - 22 : 0;
    for (size_t i = data.size() - 22 + 1; i-- > floor;) {
        if (le32(&data[i]) == 0x06054b50) {
            eocd = i;
            break;
        }
    }
    if (eocd == std::string::npos) {
        error = "fim do diretório do zip não encontrado";
        return false;
    }
    const uint16_t count = le16(&data[eocd + 10]);
    size_t p = le32(&data[eocd + 16]);
    for (uint16_t i = 0; i < count; ++i) {
        if (p + 46 > data.size() || le32(&data[p]) != 0x02014b50) {
            error = "diretório central inválido";
            return false;
        }
        ZipEntry e;
        e.method = le16(&data[p + 10]);
        e.crc = le32(&data[p + 16]);
        e.compressed = le32(&data[p + 20]);
        e.size = le32(&data[p + 24]);
        const uint16_t nameLen = le16(&data[p + 28]);
        const uint16_t extraLen = le16(&data[p + 30]);
        const uint16_t commentLen = le16(&data[p + 32]);
        e.localOffset = le32(&data[p + 42]);
        if (p + 46 + nameLen > data.size()) {
            error = "nome fora do zip";
            return false;
        }
        e.name.assign(reinterpret_cast<const char*>(&data[p + 46]), nameLen);
        m_entries.push_back(std::move(e));
        p += 46 + nameLen + extraLen + commentLen;
    }
    return true;
}

bool ZipReader::extract(const ZipEntry& e, std::vector<uint8_t>& out, std::string& error) const {
    const auto& data = *m_data;
    const size_t p = e.localOffset;
    if (p + 30 > data.size() || le32(&data[p]) != 0x04034b50) {
        error = "cabeçalho local inválido: " + e.name;
        return false;
    }
    const size_t start = p + 30 + le16(&data[p + 26]) + le16(&data[p + 28]);
    if (start + e.compressed > data.size()) {
        error = "dados fora do zip: " + e.name;
        return false;
    }
    out.resize(e.size);
    if (e.method == 0) {
        if (e.compressed != e.size) {
            error = "tamanho inconsistente: " + e.name;
            return false;
        }
        std::memcpy(out.data(), &data[start], e.size);
    } else if (e.method == 8) {
        z_stream zs{};
        if (inflateInit2(&zs, -MAX_WBITS) != Z_OK) {
            error = "zlib indisponível";
            return false;
        }
        zs.next_in = const_cast<Bytef*>(&data[start]);
        zs.avail_in = e.compressed;
        zs.next_out = out.data();
        zs.avail_out = e.size;
        const int rc = inflate(&zs, Z_FINISH);
        inflateEnd(&zs);
        if (rc != Z_STREAM_END || zs.total_out != e.size) {
            error = "falha ao descompactar: " + e.name;
            return false;
        }
    } else {
        error = "método de compressão não suportado: " + e.name;
        return false;
    }
    if (crc32(0, out.data(), static_cast<uInt>(out.size())) != e.crc) {
        error = "CRC inválido: " + e.name;
        return false;
    }
    return true;
}

}  // namespace app

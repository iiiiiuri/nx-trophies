// Roda o motor nativo no PC para comparar com o avaliador Python.
//   sa_host trace <pack.json> <trace.json>      um JSON por tick
//   sa_host saves <pack.json> <arquivo.sav>...  um tick com todos os saves
//   sa_host view  <pack.json> <arquivo.sav>...  visão do jogo após o tick

#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>

#include "sa/engine.hpp"
#include "sa/json.hpp"
#include "sa/publish.hpp"

namespace {

class FakeProcess : public sa::MemoryReader {
public:
    bool read(uint64_t address, void* out, size_t size) override {
        auto* bytes = static_cast<uint8_t*>(out);
        for (size_t i = 0; i < size; ++i) {
            const auto it = m_bytes.find(address + i);
            bytes[i] = it == m_bytes.end() ? 0 : it->second;
        }
        return true;
    }

    void write(uint64_t address, uint64_t value, size_t size) {
        for (size_t i = 0; i < size; ++i) m_bytes[address + i] = static_cast<uint8_t>(value >> (8 * i));
    }

    uint64_t address(const std::string& expr) const {
        const size_t plus = expr.find('+');
        if (plus == std::string::npos) return std::strtoull(expr.c_str(), nullptr, 0);
        return regions.at(expr.substr(0, plus)).base + std::strtoull(expr.c_str() + plus + 1, nullptr, 0);
    }

private:
    std::map<uint64_t, uint8_t> m_bytes;
};

size_t sizeOf(const std::string& type) {
    if (type == "u8" || type == "s8") return 1;
    if (type == "u16" || type == "s16") return 2;
    if (type == "u32" || type == "s32") return 4;
    return 8;
}

void applyWrites(FakeProcess& process, const cJSON* writes) {
    const cJSON* w = nullptr;
    cJSON_ArrayForEach(w, writes) {
        int64_t value = 0;
        sa::jsonToInt(cJSON_GetObjectItemCaseSensitive(w, "value"), value);
        process.write(process.address(sa::jsonStr(w, "addr")), static_cast<uint64_t>(value), sizeOf(sa::jsonStr(w, "type")));
    }
}

void printIds(const sa::Pack& pack, const std::vector<int>& ids) {
    std::printf("[");
    for (size_t i = 0; i < ids.size(); ++i) std::printf("%s\"%s\"", i ? "," : "", pack.achievements[ids[i]].id.c_str());
    std::printf("]");
}

int runTrace(const sa::Pack& pack, const char* tracePath) {
    sa::JsonDoc trace(sa::parseFile(tracePath));
    if (!trace.root) return 2;
    const int binding = pack.bindingForBuild(sa::jsonStr(trace.root, "build_id"));
    if (binding < 0) return 3;
    FakeProcess process;
    const cJSON* region = nullptr;
    cJSON_ArrayForEach(region, cJSON_GetObjectItemCaseSensitive(trace.root, "regions")) {
        int64_t base = 0, size = 0;
        sa::jsonToInt(cJSON_GetObjectItemCaseSensitive(region, "base"), base);
        sa::jsonToInt(cJSON_GetObjectItemCaseSensitive(region, "size"), size);
        process.regions[region->string] = {static_cast<uint64_t>(base), static_cast<uint64_t>(size)};
    }
    applyWrites(process, cJSON_GetObjectItemCaseSensitive(trace.root, "initial"));
    sa::UserState state;
    sa::Engine engine(pack, binding, state);
    const cJSON* tick = nullptr;
    cJSON_ArrayForEach(tick, cJSON_GetObjectItemCaseSensitive(trace.root, "ticks")) {
        applyWrites(process, cJSON_GetObjectItemCaseSensitive(tick, "writes"));
        const sa::Snapshot snap = sa::readMemory(pack, engine.binding(), process);
        const sa::TickResult result = engine.tick({snap}, "2026-01-01T00:00:00+00:00");
        std::printf("{\"unlocked\":");
        printIds(pack, result.unlocked);
        std::printf(",\"rehearsal\":");
        printIds(pack, result.rehearsal);
        std::printf(",\"events\":{");
        bool first = true;
        for (const auto& [id, n] : result.events) {
            std::printf("%s\"%s\":%d", first ? "" : ",", id.c_str(), n);
            first = false;
        }
        std::printf("}}\n");
    }
    return 0;
}

int runSaves(const sa::Pack& pack, int argc, char** argv, bool view) {
    int binding = -1;
    for (size_t i = 0; i < pack.bindings.size(); ++i) {
        if (!pack.bindings[i].memory) binding = static_cast<int>(i);
    }
    if (binding < 0) return 3;
    std::vector<sa::Snapshot> snaps;
    for (int i = 0; i < argc; ++i) {
        sa::Snapshot snap;
        if (sa::scanSaveFile(pack, pack.bindings[binding], argv[i], snap) == sa::ScanResult::Ok) snaps.push_back(std::move(snap));
    }
    sa::UserState state;
    sa::Engine engine(pack, binding, state);
    const sa::TickResult result = engine.tick(snaps, "2026-01-01T00:00:00+00:00");
    if (view) {
        sa::JsonDoc doc(sa::gameView(pack, engine, state, snaps, "pt-BR", "2026-01-01T00:00:00+00:00"));
        std::printf("%s\n", sa::printJson(doc.root).c_str());
        return 0;
    }
    std::printf("{\"unlocked\":");
    printIds(pack, result.unlocked);
    std::printf(",\"rehearsal\":");
    printIds(pack, result.rehearsal);
    std::printf("}\n");
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 4) {
        std::fprintf(stderr, "uso: sa_host trace|saves|view <pack.json> <arquivos>...\n");
        return 2;
    }
    sa::Pack pack;
    std::string error;
    if (!sa::loadPack(argv[2], pack, error)) {
        std::fprintf(stderr, "pacote: %s\n", error.c_str());
        return 2;
    }
    if (!std::strcmp(argv[1], "trace")) return runTrace(pack, argv[3]);
    if (!std::strcmp(argv[1], "saves")) return runSaves(pack, argc - 3, argv + 3, false);
    if (!std::strcmp(argv[1], "view")) return runSaves(pack, argc - 3, argv + 3, true);
    return 2;
}

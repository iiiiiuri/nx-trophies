// Sysmodule Switch Achievements: observa o jogo aberto e os saves, avalia as
// conquistas com o mesmo motor do PC (native/common) e publica no SD:
//   state.json, profile.json, progress/<jogo>.json, detected.json
// e um .notify do Ultrahand por desbloqueio.

#include <switch.h>

#include <dirent.h>
#include <sys/stat.h>

#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <map>
#include <memory>
#include <string>
#include <vector>

#include "dmntcht.h"
#include "sa/engine.hpp"
#include "sa/json.hpp"
#include "sa/publish.hpp"

extern "C" {
void __libnx_init_time(void);
u32 __nx_applet_type = AppletType_None;
u32 __nx_fs_num_sessions = 1;

#define INNER_HEAP_SIZE 0x300000
void __libnx_initheap(void) {
    static u8 inner_heap[INNER_HEAP_SIZE];
    extern void* fake_heap_start;
    extern void* fake_heap_end;
    fake_heap_start = inner_heap;
    fake_heap_end = inner_heap + sizeof(inner_heap);
}

void __appInit(void) {
    if (R_FAILED(smInitialize())) diagAbortWithResult(MAKERESULT(Module_Libnx, LibnxError_InitFail_SM));
    if (R_SUCCEEDED(setsysInitialize())) {
        SetSysFirmwareVersion fw;
        if (R_SUCCEEDED(setsysGetFirmwareVersion(&fw))) hosversionSet(MAKEHOSVERSION(fw.major, fw.minor, fw.micro));
        setsysExit();
    }
    if (R_FAILED(fsInitialize())) diagAbortWithResult(MAKERESULT(Module_Libnx, LibnxError_InitFail_FS));
    fsdevMountSdmc();
    pmdmntInitialize();
    pminfoInitialize();
    setInitialize();
    if (R_SUCCEEDED(timeInitialize())) __libnx_init_time();
    smExit();
}

void __appExit(void) {
    dmntchtExit();
    timeExit();
    setExit();
    pminfoExit();
    pmdmntExit();
    fsdevUnmountAll();
    fsExit();
}
}

namespace {

const sa::Layout kLayout;
constexpr u64 kTickNs = 250'000'000ull;
constexpr u64 kAppCheckMs = 1000;
constexpr u64 kViewEveryMs = 5000;

u64 nowMs() { return armTicksToNs(armGetSystemTick()) / 1'000'000ull; }

void logLine(const char* fmt, ...) {
    const std::string path = kLayout.log();
    struct stat st;
    const bool rotate = stat(path.c_str(), &st) == 0 && st.st_size > 64 * 1024;
    sa::makeDirs(kLayout.root());
    FILE* file = std::fopen(path.c_str(), rotate ? "w" : "a");
    if (!file) return;
    std::fprintf(file, "%s ", sa::isoNowUtc().c_str());
    va_list args;
    va_start(args, fmt);
    std::vfprintf(file, fmt, args);
    va_end(args);
    std::fputc('\n', file);
    std::fclose(file);
}

std::string hex16(u64 value) {
    char buf[17];
    std::snprintf(buf, sizeof(buf), "%016lX", value);
    return buf;
}

std::string systemLang() {
    u64 code = 0;
    SetLanguage lang = SetLanguage_ENUS;
    if (R_SUCCEEDED(setGetSystemLanguage(&code)) && R_SUCCEEDED(setMakeLanguage(code, &lang))) {
        if (lang == SetLanguage_PTBR || lang == SetLanguage_PT) return "pt-BR";
    }
    return "en";
}

class DmntReader : public sa::MemoryReader {
public:
    bool read(uint64_t address, void* out, size_t size) override {
        return R_SUCCEEDED(dmntchtReadCheatProcessMemory(address, out, size));
    }
};

struct FileWatch {
    time_t mtime = 0;
    off_t size = -1;
};

struct Game {
    sa::Pack pack;
    std::unique_ptr<sa::Engine> engine;
    std::vector<sa::Snapshot> snapshots;
    std::map<std::string, sa::Snapshot> saves;
    std::map<std::string, FileWatch> watches;
    int saveBinding = -1;
    u64 nextPoll = 0;
    bool dirty = true;
};

class Tracker {
public:
    void reload() {
        m_lang = systemLang();
        sa::JsonDoc settings(sa::parseFile(kLayout.settings()));
        if (settings.root) m_lang = sa::jsonStr(settings.root, "lang", m_lang);
        if (!m_state.load(kLayout.state())) m_state = sa::UserState();
        endSession();
        m_pid = ~0ull;
        m_games.clear();
        DIR* dir = opendir(kLayout.packs().c_str());
        if (dir) {
            while (dirent* entry = readdir(dir)) {
                const std::string name = entry->d_name;
                if (name.size() < 6 || name.compare(name.size() - 5, 5, ".json") != 0) continue;
                auto game = std::make_unique<Game>();
                std::string error;
                if (!sa::loadPack(kLayout.packs() + "/" + name, game->pack, error)) {
                    logLine("pacote %s ignorado: %s", name.c_str(), error.c_str());
                    continue;
                }
                for (size_t b = 0; b < game->pack.bindings.size(); ++b) {
                    if (!game->pack.bindings[b].memory && game->saveBinding < 0) game->saveBinding = static_cast<int>(b);
                }
                const int binding = game->saveBinding >= 0 ? game->saveBinding : 0;
                if (!game->pack.bindings.empty()) game->engine = std::make_unique<sa::Engine>(game->pack, binding, m_state);
                m_games.push_back(std::move(game));
            }
            closedir(dir);
        }
        logLine("%zu pacote(s), idioma %s", m_games.size(), m_lang.c_str());
        publishAll();
    }

    void step() {
        const u64 now = nowMs();
        if (now >= m_nextAppCheck) {
            m_nextAppCheck = now + kAppCheckMs;
            checkApplication();
            checkReloadFlag();
        }
        if (m_session && now >= m_session->nextPoll) {
            m_session->nextPoll = now + m_session->engine->binding().pollMs;
            pollMemory(*m_session);
        }
        for (auto& game : m_games) {
            if (game->saveBinding < 0 || !game->engine || now < game->nextPoll) continue;
            game->nextPoll = now + game->pack.bindings[game->saveBinding].pollMs;
            pollSaves(*game);
        }
        if (now >= m_nextViews) {
            m_nextViews = now + kViewEveryMs;
            bool any = false;
            for (auto& game : m_games) {
                if (!game->dirty) continue;
                writeView(*game);
                any = true;
            }
            if (any) {
                writeProfile();
                m_state.save(kLayout.state());
            }
        }
    }

private:
    void checkReloadFlag() {
        const std::string flag = kLayout.root() + "/reload";
        struct stat st;
        if (stat(flag.c_str(), &st) != 0) return;
        std::remove(flag.c_str());
        logLine("recarregando pacotes");
        reload();
    }

    void checkApplication() {
        u64 pid = 0;
        if (R_FAILED(pmdmntGetApplicationProcessId(&pid))) pid = 0;
        if (pid == m_pid) return;
        endSession();
        m_pid = pid;
        if (!pid) return;
        u64 programId = 0;
        if (R_FAILED(pminfoGetProgramId(&programId, pid))) return;
        const std::string titleId = hex16(programId);
        Game* game = nullptr;
        for (auto& g : m_games) {
            if (g->pack.hasTitle(titleId)) game = g.get();
        }
        std::string buildId;
        int binding = -1;
        if (game && openCheatProcess()) {
            DmntCheatProcessMetadata meta{};
            if (R_SUCCEEDED(dmntchtGetCheatProcessMetadata(&meta)) && meta.title_id == programId) {
                char buf[17];
                for (int i = 0; i < 8; ++i) std::snprintf(buf + 2 * i, 3, "%02X", meta.main_nso_build_id[i]);
                buildId = buf;
                binding = game->pack.bindingForBuild(buildId);
                if (binding >= 0 && game->pack.bindings[binding].memory) {
                    m_reader.regions = {
                        {"main", {meta.main_nso_extents.base, meta.main_nso_extents.size}},
                        {"heap", {meta.heap_extents.base, meta.heap_extents.size}},
                        {"alias", {meta.alias_extents.base, meta.alias_extents.size}},
                        {"aslr", {meta.address_space_extents.base, meta.address_space_extents.size}},
                    };
                    game->engine = std::make_unique<sa::Engine>(game->pack, binding, m_state);
                    game->snapshots.clear();
                    game->nextPoll = 0;
                    game->dirty = true;
                    m_session = game;
                }
            }
        }
        writeDetected(titleId, buildId, game, binding);
        logLine("app %s build %s: %s", titleId.c_str(), buildId.empty() ? "-" : buildId.c_str(),
                m_session ? m_session->engine->binding().id.c_str() : (game ? "versão sem binding" : "sem pacote"));
    }

    bool openCheatProcess() {
        if (R_FAILED(dmntchtInitialize())) return false;
        bool has = false;
        for (int attempt = 0; attempt < 10; ++attempt) {
            if (R_SUCCEEDED(dmntchtHasCheatProcess(&has)) && has) return true;
            dmntchtForceOpenCheatProcess();
            svcSleepThread(200'000'000ull);
        }
        return R_SUCCEEDED(dmntchtHasCheatProcess(&has)) && has;
    }

    void endSession() {
        if (!m_session) return;
        writeView(*m_session);
        writeProfile();
        m_state.save(kLayout.state());
        m_session = nullptr;
    }

    void pollMemory(Game& game) {
        bool has = false;
        if (R_FAILED(dmntchtHasCheatProcess(&has)) || !has) return;
        game.snapshots = {sa::readMemory(game.pack, game.engine->binding(), m_reader)};
        handle(game, game.engine->tick(game.snapshots, sa::isoNowUtc()));
    }

    void pollSaves(Game& game) {
        const sa::Binding& binding = game.pack.bindings[game.saveBinding];
        bool changed = false;
        for (const std::string& file : binding.files) {
            struct stat st;
            FileWatch& watch = game.watches[file];
            if (stat(file.c_str(), &st) != 0) {
                if (game.saves.erase(file)) changed = true;
                watch = FileWatch{};
                continue;
            }
            if (st.st_mtime == watch.mtime && st.st_size == watch.size) continue;
            sa::Snapshot snap;
            if (sa::scanSaveFile(game.pack, binding, file, snap) != sa::ScanResult::Ok) continue;
            watch = FileWatch{st.st_mtime, st.st_size};
            game.saves[file] = std::move(snap);
            changed = true;
        }
        if (!changed) return;
        game.snapshots.clear();
        for (const auto& [file, snap] : game.saves) game.snapshots.push_back(snap);
        handle(game, game.engine->tick(game.snapshots, sa::isoNowUtc()));
        game.dirty = true;
    }

    void handle(Game& game, const sa::TickResult& result) {
        if (!result.events.empty()) game.dirty = true;
        for (int index : result.rehearsal) logLine("ensaio: %s/%s", game.pack.game.c_str(), game.pack.achievements[index].id.c_str());
        if (result.unlocked.empty()) return;
        for (int index : result.unlocked) {
            const sa::Achievement& ach = game.pack.achievements[index];
            const std::string name = sa::notificationName(ach.icon, armGetSystemTick());
            sa::writeFileAtomic(kLayout.notifications() + "/" + name, sa::notificationJson(ach, m_lang));
            logLine("desbloqueada: %s/%s", game.pack.game.c_str(), ach.id.c_str());
        }
        m_state.save(kLayout.state());
        writeView(game);
        writeProfile();
    }

    void writeView(Game& game) {
        if (!game.engine) return;
        sa::JsonDoc view(sa::gameView(game.pack, *game.engine, m_state, game.snapshots, m_lang, sa::isoNowUtc()));
        sa::writeFileAtomic(kLayout.progress(game.pack.game), sa::printJson(view.root));
        game.dirty = false;
    }

    void writeProfile() {
        std::vector<const cJSON*> views;
        std::vector<std::unique_ptr<sa::JsonDoc>> owned;
        for (auto& game : m_games) {
            auto doc = std::make_unique<sa::JsonDoc>(sa::parseFile(kLayout.progress(game->pack.game)));
            if (doc->root) views.push_back(doc->root);
            owned.push_back(std::move(doc));
        }
        sa::JsonDoc profile(sa::profileView(m_state, views, sa::isoNowUtc()));
        sa::writeFileAtomic(kLayout.profile(), sa::printJson(profile.root));
    }

    void publishAll() {
        for (auto& game : m_games) writeView(*game);
        writeProfile();
    }

    void writeDetected(const std::string& titleId, const std::string& buildId, const Game* game, int binding) {
        sa::JsonDoc doc(cJSON_CreateObject());
        cJSON_AddStringToObject(doc.root, "title_id", titleId.c_str());
        if (!buildId.empty()) cJSON_AddStringToObject(doc.root, "build_id", buildId.c_str());
        else cJSON_AddNullToObject(doc.root, "build_id");
        if (game) cJSON_AddStringToObject(doc.root, "game", game->pack.game.c_str());
        else cJSON_AddNullToObject(doc.root, "game");
        if (game && binding >= 0) cJSON_AddStringToObject(doc.root, "binding", game->pack.bindings[binding].id.c_str());
        else cJSON_AddNullToObject(doc.root, "binding");
        cJSON_AddBoolToObject(doc.root, "supported", m_session != nullptr);
        cJSON_AddStringToObject(doc.root, "at", sa::isoNowUtc().c_str());
        sa::writeFileAtomic(kLayout.detected(), sa::printJson(doc.root));
    }

    std::string m_lang = "pt-BR";
    sa::UserState m_state;
    std::vector<std::unique_ptr<Game>> m_games;
    Game* m_session = nullptr;
    DmntReader m_reader;
    u64 m_pid = ~0ull;
    u64 m_nextAppCheck = 0;
    u64 m_nextViews = 0;
};

}  // namespace

int main(int argc, char* argv[]) {
    // espera o SD e os serviços do sistema assentarem depois do boot
    svcSleepThread(10'000'000'000ull);
    static Tracker tracker;
    logLine("iniciado");
    tracker.reload();
    while (true) {
        tracker.step();
        svcSleepThread(kTickNs);
    }
    return 0;
}

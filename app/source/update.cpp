#include <switch.h>

#include "update.hpp"

#include <curl/curl.h>
#include <sys/stat.h>

#include <cstdio>
#include <cstring>
#include <vector>

#include "sa/json.hpp"
#include "sa/publish.hpp"
#include "zip.hpp"

namespace app {

namespace {

const sa::Layout kLayout;
constexpr const char* kSysmoduleExefs = "atmosphere/contents/4200000000534143/exefs.nsp";
constexpr const char* kAppNro = "switch/switch-achievements/switch-achievements.nro";
constexpr const char* kUltrahandSound = "config/ultrahand/sounds/notification.wav";
constexpr const char* kSoundBackup = "config/switch-achievements/backup/ultrahand-notification.wav";
const std::string kCaBundle = kLayout.root() + "/cacert.pem";

struct Transfer {
    std::vector<uint8_t>* out;
    std::atomic<float>* progress;
};

size_t onData(char* data, size_t size, size_t count, void* user) {
    auto* t = static_cast<Transfer*>(user);
    t->out->insert(t->out->end(), data, data + size * count);
    return size * count;
}

int onProgress(void* user, curl_off_t total, curl_off_t now, curl_off_t, curl_off_t) {
    auto* t = static_cast<Transfer*>(user);
    if (t->progress && total > 0) t->progress->store(static_cast<float>(now) / static_cast<float>(total));
    return 0;
}

bool download(const std::string& url, std::vector<uint8_t>& out, std::atomic<float>* progress, std::string& error) {
    CURL* curl = curl_easy_init();
    if (!curl) {
        error = "curl indisponível";
        return false;
    }
    Transfer t{&out, progress};
    out.clear();
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "switch-achievements");
    curl_easy_setopt(curl, CURLOPT_CAINFO, kCaBundle.c_str());
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 15L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_LIMIT, 64L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, 30L);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, onData);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &t);
    curl_easy_setopt(curl, CURLOPT_XFERINFOFUNCTION, onProgress);
    curl_easy_setopt(curl, CURLOPT_XFERINFODATA, &t);
    curl_easy_setopt(curl, CURLOPT_NOPROGRESS, 0L);
    const CURLcode rc = curl_easy_perform(curl);
    long status = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &status);
    curl_easy_cleanup(curl);
    if (rc != CURLE_OK) {
        error = std::string("rede: ") + curl_easy_strerror(rc);
        return false;
    }
    if (status != 200) {
        error = "GitHub respondeu HTTP " + std::to_string(status);
        return false;
    }
    return true;
}

std::string hex(const u8* data, size_t size) {
    static const char digits[] = "0123456789abcdef";
    std::string out;
    for (size_t i = 0; i < size; ++i) {
        out.push_back(digits[data[i] >> 4]);
        out.push_back(digits[data[i] & 0xF]);
    }
    return out;
}

bool safeName(const std::string& name) {
    return !name.empty() && name[0] != '/' && name.find("..") == std::string::npos && name.find(':') == std::string::npos;
}

bool exists(const std::string& path) {
    struct stat st;
    return stat(path.c_str(), &st) == 0;
}

std::string coverFile(const std::string& gameId) { return kLayout.root() + "/covers/" + gameId + ".png"; }

const cJSON* findGame(const cJSON* games, const std::string& id) {
    const cJSON* game = nullptr;
    cJSON_ArrayForEach(game, games) {
        if (sa::jsonStr(game, "id") == id) return game;
    }
    return nullptr;
}

std::string achievementCount(int64_t count) {
    return std::to_string(count) + (count == 1 ? " conquista" : " conquistas");
}

// Sem `contents` local (instalação anterior à 0.2), tudo o que vier conta como novo ou atualizado.
std::vector<Change> diffContents(const cJSON* local, const cJSON* remote) {
    std::vector<Change> out;
    const cJSON* localGames = local ? cJSON_GetObjectItemCaseSensitive(local, "games") : nullptr;
    const cJSON* remoteGames = cJSON_GetObjectItemCaseSensitive(remote, "games");
    const cJSON* game = nullptr;
    cJSON_ArrayForEach(game, remoteGames) {
        const std::string id = sa::jsonStr(game, "id");
        const std::string name = sa::jsonStr(game, "name", id);
        const int64_t count = sa::jsonInt(game, "achievements");
        const cJSON* before = findGame(localGames, id);
        if (!before && !exists(kLayout.packs() + "/" + id + ".json")) {
            out.push_back({Change::Kind::NewGame, id, name, "Jogo novo · " + achievementCount(count)});
            continue;
        }
        if (before && sa::jsonStr(before, "rev") == sa::jsonStr(game, "rev")) continue;
        const int64_t previous = before ? sa::jsonInt(before, "achievements") : count;
        const std::string detail = previous != count
                                       ? std::to_string(previous) + " → " + achievementCount(count)
                                       : "Conquistas atualizadas";
        out.push_back({Change::Kind::GameUpdated, id, name, detail});
    }

    struct Component {
        const char* key;
        Change::Kind kind;
        const char* title;
        const char* detail;
    };
    static const Component components[] = {
        {"app", Change::Kind::App, "App Conquistas", "Nova versão do app"},
        {"sysmodule", Change::Kind::Service, "Serviço de conquistas", "Detecção dos jogos e notificações"},
        {"overlay", Change::Kind::Overlay, "Overlay do Ultrahand", "Lista de conquistas dentro do jogo"},
        {"art", Change::Kind::Art, "Ícones e capas", "Imagens das conquistas e dos jogos"},
        {"sound", Change::Kind::Sound, "Som da conquista", "Som tocado ao desbloquear"},
    };
    const cJSON* localParts = local ? cJSON_GetObjectItemCaseSensitive(local, "components") : nullptr;
    const cJSON* remoteParts = cJSON_GetObjectItemCaseSensitive(remote, "components");
    for (const Component& c : components) {
        const std::string next = sa::jsonStr(remoteParts, c.key);
        if (next.empty() || next == sa::jsonStr(localParts, c.key)) continue;
        out.push_back({c.kind, "", c.title, c.detail});
    }
    return out;
}

}  // namespace

std::string avatarPath() { return kLayout.root() + "/ui/avatar.png"; }

void prepareCertificates() {
    std::string bundled, current;
    if (!sa::readFile("romfs:/cacert.pem", bundled)) return;
    if (sa::readFile(kCaBundle, current) && current == bundled) return;
    sa::writeFileAtomic(kCaBundle, bundled);
}

std::string installedVersion() {
    sa::JsonDoc doc(sa::parseFile(kLayout.root() + "/version.json"));
    return doc.root ? sa::jsonStr(doc.root, "version", "?") : "?";
}

bool sysmoduleRunning() {
    u64 pid = 0;
    return R_SUCCEEDED(pmdmntGetProcessId(&pid, kSysmoduleId)) && pid != 0;
}

bool restartSysmodule() {
    if (R_FAILED(pmshellInitialize())) return false;
    pmshellTerminateProgram(kSysmoduleId);
    svcSleepThread(300'000'000ull);
    const NcmProgramLocation location{kSysmoduleId, NcmStorageId_None, {}};
    u64 pid = 0;
    const bool ok = R_SUCCEEDED(pmshellLaunchProgram(0, &location, &pid));
    pmshellExit();
    return ok;
}

Updater::~Updater() { join(); }

void Updater::join() {
    if (m_thread.joinable()) m_thread.join();
}

void Updater::check() {
    const Phase p = m_phase.load();
    if (p == Phase::Checking || p == Phase::Downloading || p == Phase::Installing) return;
    join();
    m_phase = Phase::Checking;
    setMessage("Procurando atualização...");
    m_thread = std::thread(&Updater::run, this, false);
}

void Updater::install() {
    if (m_phase.load() != Phase::Available) return;
    join();
    m_phase = Phase::Downloading;
    m_thread = std::thread(&Updater::run, this, true);
}

std::string Updater::message() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_message;
}

std::string Updater::remoteVersion() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_version;
}

std::string Updater::notes() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_notes;
}

std::vector<Change> Updater::changes() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_changes;
}

void Updater::setMessage(const std::string& text) {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_message = text;
}

void Updater::run(bool install) {
    std::string error;
    if (!install) {
        if (!doCheck(error)) {
            setMessage(error);
            m_phase = Phase::Failed;
        }
        return;
    }
    if (!doInstall(error)) {
        setMessage(error);
        m_phase = Phase::Failed;
    }
}

bool Updater::doCheck(std::string& error) {
    std::vector<uint8_t> avatar;
    std::string ignored;
    if (download(std::string("https://github.com/") + kAuthor + ".png?size=96", avatar, nullptr, ignored) &&
        sa::writeFileAtomic(avatarPath(), std::string(avatar.begin(), avatar.end()))) {
        ++m_avatarVersion;
    }

    std::vector<uint8_t> body;
    const std::string url = std::string("https://github.com/") + kRepo + "/releases/latest/download/manifest.json";
    if (!download(url, body, nullptr, error)) return false;
    body.push_back(0);
    sa::JsonDoc doc(cJSON_Parse(reinterpret_cast<const char*>(body.data())));
    if (!doc.root) {
        error = "manifesto inválido";
        return false;
    }
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_version = sa::jsonStr(doc.root, "version");
        m_asset = sa::jsonStr(doc.root, "asset");
        m_sha256 = sa::jsonStr(doc.root, "sha256");
        m_notes = sa::jsonStr(doc.root, "notes");
        m_size = static_cast<size_t>(sa::jsonInt(doc.root, "size"));
    }
    if (m_version.empty() || m_asset.empty() || m_sha256.size() != 64) {
        error = "manifesto incompleto";
        return false;
    }
    if (m_version == installedVersion()) {
        setMessage("Você já tem a versão mais recente.");
        m_phase = Phase::UpToDate;
        return true;
    }

    sa::JsonDoc local(sa::parseFile(kLayout.root() + "/version.json"));
    const cJSON* localContents = local.root ? cJSON_GetObjectItemCaseSensitive(local.root, "contents") : nullptr;
    const cJSON* remoteContents = cJSON_GetObjectItemCaseSensitive(doc.root, "contents");
    std::vector<Change> changes = remoteContents ? diffContents(localContents, remoteContents) : std::vector<Change>{};
    const std::string tag = "v" + m_version;
    for (const Change& c : changes) {
        if (c.kind != Change::Kind::NewGame || exists(coverFile(c.gameId))) continue;
        std::vector<uint8_t> cover;
        if (download(std::string("https://raw.githubusercontent.com/") + kRepo + "/" + tag + "/assets/covers/" + c.gameId + ".png",
                     cover, nullptr, ignored)) {
            sa::writeFileAtomic(coverFile(c.gameId), std::string(cover.begin(), cover.end()));
        }
    }
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_changes = std::move(changes);
    }
    setMessage("Versão " + m_version + " disponível.");
    m_phase = Phase::Available;
    return true;
}

bool Updater::doInstall(std::string& error) {
    setMessage("Baixando versão " + m_version + "...");
    std::vector<uint8_t> zip;
    zip.reserve(m_size);
    const std::string url = std::string("https://github.com/") + kRepo + "/releases/download/v" + m_version + "/" + m_asset;
    if (!download(url, zip, &m_progress, error)) return false;
    u8 digest[SHA256_HASH_SIZE];
    sha256CalculateHash(digest, zip.data(), zip.size());
    if (hex(digest, sizeof(digest)) != m_sha256) {
        error = "download corrompido (sha256 não confere)";
        return false;
    }

    m_phase = Phase::Installing;
    m_progress = 0;
    setMessage("Instalando...");
    ZipReader reader;
    if (!reader.open(zip, error)) return false;
    bool touchesSysmodule = false;
    for (const auto& e : reader.entries()) {
        if (!safeName(e.name)) {
            error = "caminho inválido no pacote: " + e.name;
            return false;
        }
        touchesSysmodule = touchesSysmodule || e.name == kSysmoduleExefs;
    }
    const std::string sd = kLayout.sd + "/";
    const bool wasRunning = sysmoduleRunning();
    if (touchesSysmodule) {
        std::vector<uint8_t> exefs;
        std::string current;
        for (const auto& e : reader.entries()) {
            if (e.name == kSysmoduleExefs && reader.extract(e, exefs, error) && sa::readFile(sd + e.name, current) &&
                current.size() == exefs.size() && std::memcmp(current.data(), exefs.data(), exefs.size()) == 0) {
                touchesSysmodule = false;
            }
        }
    }
    if (touchesSysmodule && wasRunning && R_SUCCEEDED(pmshellInitialize())) {
        pmshellTerminateProgram(kSysmoduleId);
        pmshellExit();
    }
    const auto finish = [&](bool ok) {
        if (touchesSysmodule) restartSysmodule();
        else sa::writeFileAtomic(kLayout.root() + "/reload", "1");
        return ok;
    };

    if (!exists(sd + kSoundBackup) && exists(sd + kUltrahandSound)) {
        std::string original;
        if (sa::readFile(sd + kUltrahandSound, original)) sa::writeFileAtomic(sd + kSoundBackup, original);
    }

    std::vector<uint8_t> data;
    std::string current;
    size_t done = 0;
    for (const auto& e : reader.entries()) {
        ++done;
        m_progress = static_cast<float>(done) / static_cast<float>(reader.entries().size());
        if (e.name.back() == '/') continue;
        if (!reader.extract(e, data, error)) return finish(false);
        const std::string target = sd + e.name;
        if (sa::readFile(target, current) && current.size() == data.size() &&
            std::memcmp(current.data(), data.data(), data.size()) == 0) {
            continue;
        }
        if (!sa::writeFileAtomic(target, std::string(data.begin(), data.end()))) {
            error = "não consegui gravar " + target;
            return finish(false);
        }
        m_appRestart = m_appRestart.load() || e.name == kAppNro;
    }

    finish(true);
    setMessage("Versão " + m_version + " instalada." + std::string(m_appRestart ? " Feche e abra o app para usar a nova versão." : ""));
    m_phase = Phase::Done;
    return true;
}

}  // namespace app

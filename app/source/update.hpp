#pragma once

#include <switch.h>

#include <atomic>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace app {

constexpr const char* kRepo = "iiiiiuri/nx-trophies";
constexpr const char* kAuthor = "iiiiiuri";
constexpr u64 kSysmoduleId = 0x4200000000534143ull;

// Uma linha do resumo da atualização: diferença entre o version.json instalado e o manifest.
struct Change {
    enum class Kind { NewGame, GameUpdated, App, Service, Overlay, Art, Sound };
    Kind kind;
    std::string gameId;
    std::string title;
    std::string detail;
};

std::string avatarPath();

// Copia o certificado do romfs para o SD; depois disso o romfs pode ser fechado,
// e o .nro deixa de ficar aberto (o Switch não substitui arquivo aberto).
void prepareCertificates();
std::string installedVersion();
bool sysmoduleRunning();
bool restartSysmodule();

// Verifica e instala a última release do GitHub numa thread separada.
class Updater {
public:
    enum class Phase { Idle, Checking, UpToDate, Available, Downloading, Installing, Done, Failed };

    ~Updater();
    void check();
    void install();
    Phase phase() const { return m_phase.load(); }
    float progress() const { return m_progress.load(); }
    std::string message() const;
    std::string remoteVersion() const;
    std::string notes() const;
    std::vector<Change> changes() const;
    int avatarVersion() const { return m_avatarVersion.load(); }
    bool needsAppRestart() const { return m_appRestart.load(); }

private:
    void join();
    void run(bool install);
    void setMessage(const std::string& text);
    bool doCheck(std::string& error);
    bool doInstall(std::string& error);

    std::thread m_thread;
    std::atomic<Phase> m_phase{Phase::Idle};
    std::atomic<float> m_progress{0};
    std::atomic<bool> m_appRestart{false};
    std::atomic<int> m_avatarVersion{0};
    mutable std::mutex m_mutex;
    std::string m_message, m_version, m_asset, m_sha256, m_notes;
    std::vector<Change> m_changes;
    size_t m_size = 0;
};

}  // namespace app

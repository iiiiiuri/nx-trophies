#pragma once

#include <switch.h>

#include <atomic>
#include <mutex>
#include <string>
#include <thread>

namespace app {

constexpr const char* kRepo = "iiiiiuri/nx-trophies";
constexpr u64 kSysmoduleId = 0x4200000000534143ull;

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
    mutable std::mutex m_mutex;
    std::string m_message, m_version, m_asset, m_sha256, m_notes;
    size_t m_size = 0;
};

}  // namespace app

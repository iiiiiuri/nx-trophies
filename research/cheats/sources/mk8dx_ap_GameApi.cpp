#include "GameApi.hpp"

#include "Structs.hpp"
#include "../sym/PatternResolver.hpp"
#include "../util/Log.hpp"

namespace mk8ap::game {

namespace {

using VoidPtrFn = void* (*)();
using IntFn = int (*)();
using TextFn = const char* (*)(int);

VoidPtrFn g_getRaceInfo = nullptr;
VoidPtrFn g_getNextRaceInfo = nullptr;
VoidPtrFn g_getPlayerManager = nullptr;
VoidPtrFn g_getCurrentGameScene = nullptr;
IntFn     g_getMyKartIndex = nullptr;
VoidPtrFn g_getCurrentUserSaveData = nullptr;
TextFn    g_driverText = nullptr;
TextFn    g_bodyText = nullptr;
TextFn    g_tireText = nullptr;
TextFn    g_wingText = nullptr;
bool      g_bound = false;

}  // namespace

void bindGameApi() {
    if (g_bound) return;
    g_bound = true;
    g_getRaceInfo = sym::fn<VoidPtrFn>("gear::GetRaceInfo");
    g_getNextRaceInfo = sym::fn<VoidPtrFn>("gear::GetNextRaceInfo");
    g_getPlayerManager = sym::fn<VoidPtrFn>("gear::GetPlayerManager");
    g_getCurrentGameScene = sym::fn<VoidPtrFn>("gear::FrameworkUtil::getCurrentGameScene");
    g_getMyKartIndex = sym::fn<IntFn>("gear::NetworkUtil::getMyKartIndex");
    g_getCurrentUserSaveData = sym::fn<VoidPtrFn>("gear::GetCurrentUserSaveData");
    g_driverText = sym::fn<TextFn>("mush::EDriverID::text_");
    g_bodyText = sym::fn<TextFn>("mush::EBodyID::text_");
    g_tireText = sym::fn<TextFn>("mush::ETireID::text_");
    g_wingText = sym::fn<TextFn>("mush::EWingID::text_");
    MK8AP_LOG_INFO("[game] api bound: raceInfo=%d nextRaceInfo=%d scene=%d kartIdx=%d "
                   "save=%d text(d/b/t/w)=%d%d%d%d",
                   g_getRaceInfo != nullptr, g_getNextRaceInfo != nullptr,
                   g_getCurrentGameScene != nullptr, g_getMyKartIndex != nullptr,
                   g_getCurrentUserSaveData != nullptr,
                   g_driverText != nullptr, g_bodyText != nullptr,
                   g_tireText != nullptr, g_wingText != nullptr);
}

void* getRaceInfo() { return g_getRaceInfo ? g_getRaceInfo() : nullptr; }
void* getNextRaceInfo() { return g_getNextRaceInfo ? g_getNextRaceInfo() : nullptr; }
void* getPlayerManager() { return g_getPlayerManager ? g_getPlayerManager() : nullptr; }
void* getCurrentGameScene() { return g_getCurrentGameScene ? g_getCurrentGameScene() : nullptr; }
int getMyKartIndex() { return g_getMyKartIndex ? g_getMyKartIndex() : -1; }
void* getCurrentUserSaveData() { return g_getCurrentUserSaveData ? g_getCurrentUserSaveData() : nullptr; }

int localKartIndex() {
    const int i = getMyKartIndex();
    return i < 0 ? 0 : i;
}

void* kartVehicle(int idx) {
    if (idx < 0 || idx >= race_info::kMaxKarts) return nullptr;
    void* sc = getCurrentGameScene();
    if (!sc) return nullptr;
    void* engine = rd<void*>(sc, scene::kObjectEngine);
    if (!engine) return nullptr;
    void* director = rd<void*>(engine, scene::kKartDirector);
    if (!director) return nullptr;
    void** holders = rd<void**>(director, scene::kKartUnitHolders);
    if (!holders) return nullptr;
    void* holder = holders[idx];
    if (!holder) return nullptr;
    return rd<void*>(holder, scene::kHolderKartVehicle);
}

void* kartVehicleMove(int idx) {
    void* v = kartVehicle(idx);
    return v ? rd<void*>(v, scene::kVehicleMove) : nullptr;
}

int kartRank(int idx) {
    if (idx < 0 || idx >= race_info::kMaxKarts) return -1;
    void* sc = getCurrentGameScene();
    if (!sc) return -1;
    void* engine = rd<void*>(sc, scene::kObjectEngine);
    if (!engine) return -1;
    void* raceDir = rd<void*>(engine, scene::kRaceDirector);
    if (!raceDir) return -1;
    void** checkers = rd<void**>(raceDir, scene::kRaceKartCheckers);
    if (!checkers) return -1;
    void* checker = checkers[idx];
    if (!checker) return -1;
    return rd<std::int32_t>(checker, scene::kCheckerRank);
}

const char* driverText(int id) { return g_driverText ? g_driverText(id) : nullptr; }
const char* bodyText(int id) { return g_bodyText ? g_bodyText(id) : nullptr; }
const char* tireText(int id) { return g_tireText ? g_tireText(id) : nullptr; }
const char* wingText(int id) { return g_wingText ? g_wingText(id) : nullptr; }

int currentRule() {
    void* ri = getRaceInfo();
    return ri ? rd<std::int32_t>(ri, race_info::kRule) : -1;
}
int currentEngineClass() {
    void* ri = getRaceInfo();
    return ri ? rd<std::int32_t>(ri, race_info::kEngineClass) : -1;
}
int currentCourseId() {
    void* ri = getRaceInfo();
    return ri ? static_cast<int>(rd<std::uint32_t>(ri, race_info::kCourseId)) : -1;
}
bool currentIsMirror() {
    void* ri = getRaceInfo();
    return ri ? rd<bool>(ri, race_info::kIsMirror) : false;
}

}  // namespace mk8ap::game

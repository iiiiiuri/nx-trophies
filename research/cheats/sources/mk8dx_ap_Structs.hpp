// Offset-based accessors for the handful of game structures we read or
// write, for MK8DX 4.0.x. Offsets come from fishguy6564/MK8DX-Headers
// (64-bit branch) and the RoGamer97 4.0.0 patch sources, which use every
// chain and offset below (checked 2026-09-27). The layout changes 4.0.0
// made (object::DriverKart members +8, UI page ids +1) are in structures
// this mod does not touch. 4.0.1 (the current target) changed none of
// them: Ro's 4.0.1 sources match 4.0.0 apart from addresses (2026-10-21).
//
// Deliberately NOT full struct mirrors: a wrong padding byte in a mirrored
// 0x600-byte class silently shifts every later field, whereas a named
// offset is either right or obviously wrong in the logs.

#pragma once

#include <cstddef>
#include <cstdint>

namespace mk8ap::game {

template <typename T>
inline T rd(const void* base, std::size_t off) {
    return *reinterpret_cast<const T*>(static_cast<const std::uint8_t*>(base) + off);
}
template <typename T>
inline void wr(void* base, std::size_t off, T v) {
    *reinterpret_cast<T*>(static_cast<std::uint8_t*>(base) + off) = v;
}

// ---- gear::RaceInfo (MK8DX-Headers gear/Race/RaceInfo.hpp) ----------------
namespace race_info {
inline constexpr std::size_t kRule        = 0x08;   // ERaceRule (s32)
inline constexpr std::size_t kBattleType  = 0x0C;
inline constexpr std::size_t kEngineClass = 0x10;   // EEngineLevelSlot (s32)
inline constexpr std::size_t kIsMirror    = 0x26;   // bool
inline constexpr std::size_t kKartInfos   = 0x30;   // RaceKartInfo[12]
inline constexpr std::size_t kPlayerAmount = 0x180; // u32
inline constexpr std::size_t kCourseId    = 0x1A0;  // u32 (mush::ECourseID)
inline constexpr int kMaxKarts = 12;
}  // namespace race_info

// ---- gear::RaceKartInfo (0x1C bytes) ---------------------------------------
namespace kart_info {
inline constexpr std::size_t kSize     = 0x1C;
inline constexpr std::size_t kBodyId   = 0x00;
inline constexpr std::size_t kTireId   = 0x04;
inline constexpr std::size_t kGliderId = 0x08;
inline constexpr std::size_t kDriverId = 0x0C;
inline constexpr std::size_t kDriverVariant = 0x10;  // u8
inline constexpr std::size_t kPlayerType = 0x14;     // s32 (gear::RacePlayerType)
inline constexpr std::size_t kTeam = 0x18;
}  // namespace kart_info

inline void* kartInfoAt(void* raceInfo, int idx) {
    return static_cast<std::uint8_t*>(raceInfo) + race_info::kKartInfos
           + static_cast<std::size_t>(idx) * kart_info::kSize;
}

// ---- ui::CourseInfo (MK8DX-Headers ui/Course/CourseInfo.hpp) --------------
namespace course_info {
inline constexpr std::size_t kCourseId   = 0x00;  // mush::ECourseID (s32)
inline constexpr std::size_t kPrefixMsbt = 0x04;
inline constexpr std::size_t kCourseMsbt = 0x08;
inline constexpr std::size_t kIsDLC      = 0x0C;  // bool
// The struct ends here (0x10 bytes). An earlier revision of the public
// header listed an icon-resource string after it; that was wrong, so course
// names are NOT read from CourseInfo. The PC learns course ids by pairing
// the hook's numeric id with the PlayReport course string of the same race.
}  // namespace course_info

// ---- Scene -> kart chain (RoGamer97 4.0.0 FINISH / Free Camera patches) ---
//   gear::FrameworkUtil::getCurrentGameScene()   -> FrameworkGameScene*
//   scene + 0x1B0                                -> object::ObjectEngine*
//   engine + 0x218                               -> object::RaceDirector*
//   engine + 0x238                               -> object::KartDirector*
//   kartDirector + 0xC8                          -> KartUnitHolder** (array)
//   holder[i] + 0x08                             -> object::KartVehicle*
//   vehicle + 0x28                               -> object::KartVehicleMove*
//   raceDirector + 0x68                          -> gear::RaceKartChecker** (array)
//   checker + 0x40                               -> s32 current rank (0-based)
// ui::RaceWindow: the first s32 is the window index (Ro's FINISH patch); the
// public header also lists mKartIdx at +0xF4. RaceFinishHook logs both.
namespace race_window {
inline constexpr std::size_t kWindowId = 0x00;
inline constexpr std::size_t kKartIdx  = 0xF4;
}  // namespace race_window

namespace scene {
inline constexpr std::size_t kObjectEngine = 0x1B0;
inline constexpr std::size_t kRaceDirector = 0x218;
inline constexpr std::size_t kKartDirector = 0x238;
inline constexpr std::size_t kKartUnitHolders = 0xC8;
inline constexpr std::size_t kHolderKartVehicle = 0x08;
inline constexpr std::size_t kVehicleMove = 0x28;
inline constexpr std::size_t kRaceKartCheckers = 0x68;
inline constexpr std::size_t kCheckerRank = 0x40;
}  // namespace scene

// ---- object::KartVehicle (MK8DX-Headers object/Kart/KartVehicle.hpp) ------
// gear::PlayerManager (MK8DX-Headers): sead::PtrArray<Player> at 0x50
// {s32 num; s32 max; Player** ptrs}, local player count at 0x178.
// gear::Player: RaceKartInfo mKartInfo at 0x210 (same layout as kart_info).
namespace player_manager {
inline constexpr std::size_t kPlayersNum  = 0x50;
inline constexpr std::size_t kPlayersPtrs = 0x58;
inline constexpr std::size_t kLocalPlayerAmount = 0x178;
inline constexpr int kMaxPlayers = 16;  // observed 16 slots on 4.0.0 (12 karts + spares)
}  // namespace player_manager
namespace player {
inline constexpr std::size_t kKartInfo = 0x210;
}  // namespace player

namespace vehicle {
inline constexpr std::size_t kPlayerId = 0xA8;
inline constexpr std::size_t kBodyId   = 0xB0;
inline constexpr std::size_t kDriverId = 0xB4;
inline constexpr std::size_t kIsMaster = 0xD0;  // bool: locally controlled
inline constexpr std::size_t kIsCpu    = 0xD2;
inline constexpr std::size_t kIsNetSend = 0xE6;
}  // namespace vehicle

// ---- object::KartVehicleMove (header warns: "still based off of 32-bit
// structure" - SpeedCapHook logs the raw values once so drift is visible) --
namespace vehicle_move {
inline constexpr std::size_t kSpeed     = 0x37C;  // float, current speed
inline constexpr std::size_t kTopSpeed1 = 0x424;  // float
inline constexpr std::size_t kTopSpeed2 = 0x428;
inline constexpr std::size_t kTopSpeed3 = 0x42C;
}  // namespace vehicle_move

// ---- gear::ItemOwner (MK8DX-Headers gear/Item/ItemOwner.hpp) -------------
namespace item_owner {
inline constexpr std::size_t kPlayerId = 0x40;
inline constexpr std::size_t kKartInfoProxy = 0x48;   // object::KartInfoProxy*
inline constexpr std::size_t kProxyKartVehicle = 0x48; // proxy + 0x48 -> KartVehicle* (4.0.0 Debug Item Cycler)
}  // namespace item_owner

// ---- gear::SaveData ---------------------------------------------------------
namespace save_data {
inline constexpr std::size_t kFlagAccessor = 0x190;
}

}  // namespace mk8ap::game

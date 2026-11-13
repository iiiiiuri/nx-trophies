// Enumerations mirrored from the public MK8DX headers (fishguy6564/
// MK8DX-Headers) and the RoGamer97 patch comments. Only values we actually
// branch on are listed; everything else is carried as a raw int on the wire.
//
// Course, cup (EGrandPrixID), driver and vehicle-part ids are NOT enumerated
// here on purpose: the public headers leave those enums empty. The mod
// learns them at runtime (mush::E*ID::text_() dumps, CourseInfo resource
// names) and ships them to the PC, which owns the id -> AP-name tables.

#pragma once

#include <cstdint>

namespace mk8ap::game {

// gear::ERaceRule
enum class RaceRule : std::int32_t {
    GrandPrix = 0,
    VS = 1,
    TimeAttack = 2,
    Battle = 3,
    TitleRace = 4,
    Menu = 5,
    TheaterMenu = 6,
    Customizer = 7,
};

// gear::EEngineLevelSlot
enum class EngineClass : std::int32_t {
    Invalid = -1,
    CC50 = 0,
    CC100 = 1,
    CC150 = 2,
    CC200 = 3,
    Mirror = 4,
};

// gear::EItemSlot (23 items; None = -1). Bit i of ApState::items_allowed
// corresponds to value i.
enum class ItemSlot : std::int32_t {
    None = -1,
    Banana = 0,
    KouraG = 1,      // Green Shell
    KouraR = 2,      // Red Shell
    Kinoko = 3,      // Mushroom
    Bomhei = 4,      // Bob-omb
    Gesso = 5,       // Blooper
    KouraB = 6,      // Spiny (Blue) Shell
    Kinoko3 = 7,     // Triple Mushrooms
    Star = 8,
    Killer = 9,      // Bullet Bill
    Thunder = 10,    // Lightning
    KinokoP = 11,    // Golden Mushroom
    Fireball = 12,   // Fire Flower
    Packun = 13,     // Piranha Plant
    Boomerang = 14,
    Coin = 15,
    SHorn = 16,      // Super Horn
    Banana3 = 17,
    KouraG3 = 18,
    KouraR3 = 19,
    Eight = 20,      // Crazy Eight
    Feather = 21,
    Teresa = 22,     // Boo
    Count = 23,
};

// ui::ECup (course-select cup buttons). CONFIRMED on 4.0.0 (boot log
// 2026-10-16): 0-based, Mushroom = 0 ... Spiny = 23, and identical to
// mush::EGrandPrixID (isOpen(gp=N) is always paired with setCup(ecup=N)).
// AP cup index == ECup == EGrandPrixID. Note these "enums" are class
// wrappers passed BY CONST REFERENCE in the game ABI (see CupGateHook.cpp).
inline constexpr int kCupCount = 24;

// mush::EDriverID / EBodyID / ETireID / EWingID counts on 4.0.1 (the text_
// tables enumerate 54 / 42 / 23 / 16 entries, index 0 = "Invalid"; the
// parts-list builder queries body 0..40, tire 0..21, glider 0..14).
// Drivers 44..52 are Booster Course Pass characters (client/tables.py).
inline constexpr int kBaseDriverCount = 44;
inline constexpr int kBodyCount = 41;
inline constexpr int kTireCount = 22;
inline constexpr int kWingCount = 15;

// ui::DLCState (Control_CupButton::setCup second argument)
enum class DLCState : std::int32_t {
    NotSale = 0,
    NotSaleReserve = 1,
    NotBuy = 2,
    NotBuyReserve = 3,
    Locked = 4,
    Unlocked = 5,
};

// ui::DLCStatus (DLCManager::getCupStatus return)
enum class DLCStatus : std::int32_t {
    Unlocked = 0,
    Locked = 3,
};

}  // namespace mk8ap::game

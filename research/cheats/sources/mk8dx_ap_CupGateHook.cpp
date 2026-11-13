// Cup gating (AP location gate).
//
// Three layers, mirroring the "catch it upstream of the visible state
// change" rule from smo_archipelago M7:
//   1. gear::FlagAccessor::isOpen(const EGrandPrixID&)      -> save-flag query
//   2. gear::DLCManager::getCupStatus(const EGrandPrixID&)  -> entitlement query
//   3. ui::Control_CupButton::setCup(const ECup&, const DLCState&) -> button state
//
// CALLING CONVENTION (confirmed on 4.0.0, 2026-10-16): the mush::E*ID /
// ui::ECup / ui::DLCState "enums" are class wrappers (they carry static
// text_() members), so they travel BY CONST REFERENCE: x1/x2 are pointers to
// a 32-bit value on the caller's stack, not the value itself. The first
// build declared them `int`, truncated the pointers on the way into orig()
// and faulted on the Prepare Thread at boot. Every hook here now forwards
// the registers as u64 and dereferences them only when they look like
// pointers; to override an argument it points orig() at a local copy.
//
// EGrandPrixID vs ECup: CONFIRMED on 4.0.0 (2026-10-16 boot log) that the
// two are the same 0-based index (Mushroom = 0 ... Spiny = 23): the title
// screen's cup grid calls isOpen(gp=N) immediately followed by setCup(ecup=N).

#include "Hooks.hpp"

#include <atomic>
#include <cstdint>

#include "hk/hook/Trampoline.h"

#include "../ap/ApState.hpp"
#include "../game/Ids.hpp"
#include "../game/Structs.hpp"
#include "../sym/PatternResolver.hpp"
#include "../util/Log.hpp"

namespace mk8ap::hooks {

namespace {

using u64 = std::uint64_t;

// The DLCState an AP-locked cup reports (see Page_CourseBase::isDLC below).
constexpr std::int32_t kGatedState = static_cast<std::int32_t>(game::DLCState::NotSale);

std::atomic<std::uint64_t> g_logged_gp{0};
std::atomic<std::uint64_t> g_logged_cup{0};
std::atomic<std::uint64_t> g_logged_status{0};

// Returns true the first time `slot` (0..63) is seen.
bool firstTime(std::atomic<std::uint64_t>& seen, int slot) {
    if (slot < 0) slot = 63;
    const std::uint64_t bitv = 1ULL << (slot & 63);
    return (seen.fetch_or(bitv) & bitv) == 0;
}

// Read the 32-bit enum value a by-reference argument points at. Returns
// -1 when the register does not look like a pointer (so callers never
// dereference a small immediate by mistake).
int derefEnum(u64 reg) {
    if (reg < 0x10000) return -1;
    return *reinterpret_cast<const std::int32_t*>(reg);
}

// --- 1. gear::FlagAccessor::isOpen(this, const EGrandPrixID&) const -> bool
HkTrampoline<u64, const void*, u64, u64, u64> g_isOpen = hk::hook::trampoline(
    [](const void* self, u64 x1, u64 x2, u64 x3) -> u64 {
        const u64 vanilla = g_isOpen.orig(self, x1, x2, x3);
        const int gpId = derefEnum(x1);
        if (firstTime(g_logged_gp, gpId)) {
            MK8AP_LOG_INFO("[cup] FlagAccessor::isOpen(gp=%d) [x1=0x%llx] vanilla=%d",
                           gpId, static_cast<unsigned long long>(x1), static_cast<int>(vanilla & 1));
        }
        // EXPERIMENT (2026-10-16): returning false here soft-locked the game
        // when a locked cup was selected (Deluxe never has closed cups, so the
        // UI has no path for it). Pass through and log; the button-state
        // layer (setCup -> Locked) carries the gate alone for this test.
        static int denials_logged = 0;
        if (gpId >= 0 && gpId < game::kCupCount &&
            !ap::ApState::instance().isCupAllowed(gpId) && denials_logged < 40) {
            ++denials_logged;
            MK8AP_LOG_INFO("[cup] isOpen(gp=%d) would deny (passing vanilla=%d)", gpId,
                           static_cast<int>(vanilla & 1));
        }
        return vanilla;
    });

// --- 2. gear::DLCManager::getCupStatus(this, const EGrandPrixID&) -> DLCStatus
HkTrampoline<u64, void*, u64, u64, u64> g_getCupStatus = hk::hook::trampoline(
    [](void* self, u64 x1, u64 x2, u64 x3) -> u64 {
        const u64 vanilla = g_getCupStatus.orig(self, x1, x2, x3);
        const int gpId = derefEnum(x1);
        if (firstTime(g_logged_status, gpId)) {
            MK8AP_LOG_INFO("[cup] DLCManager::getCupStatus(gp=%d) [x1=0x%llx] vanilla=%d",
                           gpId, static_cast<unsigned long long>(x1), static_cast<int>(vanilla));
        }
        if (gpId >= 0 && gpId < game::kCupCount &&
            !ap::ApState::instance().isCupAllowed(gpId)) {
            return static_cast<u64>(static_cast<int>(game::DLCStatus::Locked));
        }
        return vanilla;
    });

// --- 3. ui::Control_CupButton::setCup(this, const ECup&, const DLCState&) --
// To lock a cup we hand orig() a pointer to a local kGatedState instead of
// the caller's value; the caller's object is never written.
HkTrampoline<u64, void*, u64, u64, u64, u64, u64> g_setCup = hk::hook::trampoline(
    [](void* self, u64 x1, u64 x2, u64 x3, u64 x4, u64 x5) -> u64 {
        startNetworkingOnce("ui::Control_CupButton::setCup");
        const int ecup = derefEnum(x1);
        const int state = derefEnum(x2);
        if (firstTime(g_logged_cup, ecup)) {
            MK8AP_LOG_INFO("[cup] Control_CupButton::setCup(ecup=%d, state=%d) [x1=0x%llx x2=0x%llx x3=0x%llx]",
                           ecup, state, static_cast<unsigned long long>(x1),
                           static_cast<unsigned long long>(x2), static_cast<unsigned long long>(x3));
        }
        // 4.0.0 boot log: setCup(ecup=N) is always paired with isOpen(gp=N),
        // so ECup is 0-based (Mushroom == 0) and equals EGrandPrixID. The
        // upstream header's "Mushroom == 1" reading was wrong for this build.
        const int cupIdx = ecup;
        // setCup only picks the icon frames (4.0.1 disassembly: NotSale and
        // Locked draw alike, NotBuy and Unlocked alike); the press is gated by
        // Page_CourseBase::isDLC below, which also feeds this call on the cup
        // grid. Kept so a caller that skips isDLC never draws a locked cup as
        // purchasable or open.
        if (state >= 0 && cupIdx >= 0 && cupIdx < game::kCupCount &&
            !ap::ApState::instance().isCupAllowed(cupIdx)) {
            const std::int32_t gated = kGatedState;
            return g_setCup.orig(self, x1, reinterpret_cast<u64>(&gated), x3, x4, x5);
        }
        return g_setCup.orig(self, x1, x2, x3, x4, x5);
    });

// --- 4. static ui::DLCState Page_CourseBase::isDLC(ui::ECup) ----------------
// DLCState carries a user-declared destructor, so the AArch64 ABI returns it
// through memory at the hidden x8 pointer; a C++ lambda cannot see x8, so the
// hook entry is an asm stub that moves x8 into x1 (and the caller's return
// address, x30, into x2) and jumps to the C++ body. The original is invoked
// through another stub that reloads x8.
//
// AP-locked cups report NotSale(0). From the 4.0.1 disassembly (isDLC at
// +0x494E44 and its callers):
//   * the cup-grid setup (+0x494B..) disables the button (Control+0x3CB = 0,
//     the generic "enabled" flag that gates input and picks the greyed
//     animation) only for Locked(4). A disabled button cannot take the
//     cursor, so with Locked an open cup boxed in by locked ones (Mushroom
//     + Lightning, nothing between) was unreachable. That was 0.2.0's gate.
//   * the cup decide handler (+0x4980A0) re-queries isDLC at press time:
//     Unlocked(5) enters, NotBuy(2) may run the eShop purchase check and
//     then enter, NotSale(0) only plays the deny window (Page+0x370), and
//     1 / 3 / 4 do nothing.
//   * the focus preview (+0x494F08) shows "???" course names for 0, 1, 4.
// So NotSale keeps the cursor free and the press inert, and because the
// press re-reads isDLC, a cup received while the grid is open becomes
// enterable at once (setup-time Locked needed the page rebuilt).
// isDLC itself returns Locked for a base cup whose save flag is closed
// (FlagAccessor::isOpen), which is why gating isOpen soft-locked the grid.
//
// ONLY the cup page's own calls are gated. isDLC has 25 call sites on 4.0.1:
// 18 inside Page_CourseBase (+0x494BDC .. +0x4982E8), and 7 elsewhere. Five
// of those (+0x4B603C, +0x4B7648, +0x4B9880, +0x4B9CF8, +0x4BBE3C) are the
// driver / part availability checks: an id 30..35 (Tanooki Mario, Link,
// Villager, Isabelle, Cat Peach, Dry Bowser: the former Wii U DLC packs) is
// mapped to its pack's cup (Egg / Triforce / Crossing / Bell) and the
// character is available iff isDLC(that cup) says so. Gating every caller
// blanked those characters' icons and froze the select screen on a pick
// while the pack's cup was AP-locked (player report 2026-11). The remaining
// two (+0x4E6F44, +0x4E77A8) query a cup read from a global (+0x2084).
// Calls whose return address lies outside the Page_CourseBase window below
// get the vanilla answer.
constexpr std::intptr_t kCupPageCallersLo = -0x300;   // isDLC + this ..
constexpr std::intptr_t kCupPageCallersHi = 0x3500;   // .. isDLC + this
}  // namespace
extern "C" std::uint64_t mk8ap_isDlcEntry(std::uint64_t cup);
extern "C" std::uint64_t mk8ap_callSret(void* fn, std::uint64_t x0, std::uint64_t x8);
asm(R"(
    .section .text.mk8ap_isDlcEntry,"ax",%progbits
    .global mk8ap_isDlcEntry
    .type mk8ap_isDlcEntry,%function
mk8ap_isDlcEntry:
    mov x1, x8
    mov x2, x30
    b mk8ap_isDlcImpl
    .size mk8ap_isDlcEntry, .-mk8ap_isDlcEntry

    .section .text.mk8ap_callSret,"ax",%progbits
    .global mk8ap_callSret
    .type mk8ap_callSret,%function
mk8ap_callSret:
    mov x8, x2
    mov x16, x0
    mov x0, x1
    br x16
    .size mk8ap_callSret, .-mk8ap_callSret
)");
namespace {
HkTrampoline<std::uint64_t, std::uint64_t> g_isDlc{&mk8ap_isDlcEntry};
}  // namespace
extern "C" std::uint64_t mk8ap_isDlcImpl(std::uint64_t x0, std::uint64_t x8, std::uint64_t lr) {
    using namespace mk8ap;
    using namespace mk8ap::hooks;
    std::int32_t local = 0;
    const std::uint64_t ret = mk8ap_callSret(reinterpret_cast<void*>(g_isDlc.orig), x0,
                                             reinterpret_cast<std::uint64_t>(&local));
    const int ecup = derefEnum(x0);
    std::int32_t result = local;
    static const std::uintptr_t isDlcAddr = sym::addr("ui::Page_CourseBase::isDLC");
    const std::intptr_t rel = static_cast<std::intptr_t>(lr - isDlcAddr);
    const bool cupPage = isDlcAddr && rel >= kCupPageCallersLo && rel < kCupPageCallersHi;
    if (cupPage && ecup >= 0 && ecup < game::kCupCount &&
        !ap::ApState::instance().isCupAllowed(ecup)) {
        result = kGatedState;
    }
    if (!cupPage && ecup >= 0 && ecup < game::kCupCount &&
        !ap::ApState::instance().isCupAllowed(ecup)) {
        static int passLogs = 0;
        if (passLogs < 20) {
            ++passLogs;
            MK8AP_LOG_INFO("[cup] isDLC(ecup=%d) from +0x%llx (not the cup page): vanilla %d kept",
                           ecup, static_cast<unsigned long long>(sym::mainOffset("ui::Page_CourseBase::isDLC") + rel),
                           local);
        }
    }
    static std::atomic<std::uint64_t> logged{0};
    if (firstTime(logged, ecup) || result != local) {
        static int n = 0;
        if (n < 60) {
            ++n;
            MK8AP_LOG_INFO("[cup] Page_CourseBase::isDLC(ecup=%d) vanilla=%d -> %d [x8=0x%llx]",
                           ecup, local, result, static_cast<unsigned long long>(x8));
        }
    }
    if (x8 >= 0x10000) *reinterpret_cast<std::int32_t*>(x8) = result;
    return ret;
}
namespace {

template <typename H>
void install(H& hook, const char* name) {
    const auto off = sym::mainOffset(name);
    if (!off) { MK8AP_LOG_WARN("[cup] %s unresolved; skipped", name); return; }
    const auto rc = hook.installAtMainOffset(off);
    MK8AP_LOG_INFO("[cup] %s @+0x%llx: %s", name, static_cast<unsigned long long>(off),
                   rc.succeeded() ? "installed" : "FAILED");
}

}  // namespace

void installCupGateHooks() {
    install(g_isOpen, "gear::FlagAccessor::isOpen");
    install(g_getCupStatus, "gear::DLCManager::getCupStatus");
    install(g_setCup, "ui::Control_CupButton::setCup");
    install(g_isDlc, "ui::Page_CourseBase::isDLC");
}

}  // namespace mk8ap::hooks

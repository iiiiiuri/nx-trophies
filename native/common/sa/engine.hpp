#pragma once

#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include "pack.hpp"

namespace sa {

struct Snapshot {
    std::string label;
    std::vector<Val> values;
};

struct Context {
    const std::vector<Val>& values;
    const std::vector<int64_t>& counters;
};

Val evalValue(const ValueNode& node, const Context& ctx);
bool evalCond(const CondNode& cond, const Context& ctx);

struct Unlock {
    std::string game, achievement, unlockedAt;
    int xp = 0;
};

class UserState {
public:
    std::map<std::string, Unlock> unlocked;
    std::vector<Unlock> history;
    std::map<std::string, std::map<std::string, int64_t>> counters;

    bool isUnlocked(const std::string& game, const std::string& ach) const;
    const Unlock* record(const std::string& game, const std::string& ach) const;
    void unlock(const std::string& game, const std::string& ach, int xp, const std::string& when);
    int xpFor(const std::string& game = "") const;

    bool load(const std::string& path);
    bool save(const std::string& path) const;
};

int levelForXp(int xp);
int xpForLevel(int level);

struct TickResult {
    std::vector<int> unlocked;
    std::vector<int> rehearsal;
    std::map<std::string, int> events;
};

class Engine {
public:
    Engine(const Pack& pack, int binding, UserState& state);

    TickResult tick(const std::vector<Snapshot>& snapshots, const std::string& now);
    bool progress(int achievement, const std::vector<Snapshot>& snapshots, int64_t& current, int64_t& target) const;
    const Binding& binding() const { return m_pack.bindings[m_binding]; }
    int bindingIndex() const { return m_binding; }

private:
    std::vector<int64_t> counters() const;
    void storeCounters(const std::vector<int64_t>& counters);
    std::string modeOf(const Snapshot& snap, const std::vector<int64_t>& counters) const;
    bool active(const Snapshot& snap, const std::vector<int64_t>& counters) const;

    const Pack& m_pack;
    int m_binding;
    UserState& m_state;
    std::map<std::pair<std::string, int>, bool> m_previousEvents;
    std::vector<int> m_streaks;
    std::set<int> m_rehearsed;
};

struct Region {
    uint64_t base = 0, size = 0;
};

class MemoryReader {
public:
    virtual ~MemoryReader() = default;
    virtual bool read(uint64_t address, void* out, size_t size) = 0;
    std::map<std::string, Region> regions;
};

Snapshot readMemory(const Pack& pack, const Binding& binding, MemoryReader& reader);

enum class ScanResult { Ok, Missing, Invalid };
ScanResult scanSaveFile(const Pack& pack, const Binding& binding, const std::string& path, Snapshot& out);
ScanResult scanSaveText(const Pack& pack, const Binding& binding, const std::string& text, Snapshot& out);

}  // namespace sa

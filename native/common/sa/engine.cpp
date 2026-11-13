#include "engine.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>

#include "json.hpp"

namespace sa {

Val evalValue(const ValueNode& node, const Context& ctx) {
    switch (node.kind) {
        case ValueNode::Kind::Const:
            return node.constant;
        case ValueNode::Kind::Var:
            if (node.index < 0 || static_cast<size_t>(node.index) >= ctx.values.size()) return {};
            return ctx.values[node.index];
        case ValueNode::Kind::Count:
            if (node.index < 0 || static_cast<size_t>(node.index) >= ctx.counters.size()) return Val::num(0);
            return Val::num(ctx.counters[node.index]);
        case ValueNode::Kind::Truth:
            return Val::num(evalCond(*node.cond, ctx) ? 1 : 0);
        case ValueNode::Kind::Pop: {
            const Val v = evalValue(node.kids[0], ctx);
            if (!v.ok) return {};
            return Val::num(__builtin_popcountll(static_cast<uint64_t>(v.asInt()) & node.mask));
        }
        case ValueNode::Kind::Sum: {
            bool real = false;
            int64_t si = 0;
            double sf = 0;
            for (const auto& kid : node.kids) {
                const Val v = evalValue(kid, ctx);
                if (!v.ok) return {};
                real = real || v.real;
                si += v.asInt();
                sf += v.asDouble();
            }
            return real ? Val::dbl(sf) : Val::num(si);
        }
        case ValueNode::Kind::Div: {
            const Val a = evalValue(node.kids[0], ctx);
            const Val b = evalValue(node.kids[1], ctx);
            if (!a.ok || !b.ok || b.asDouble() == 0) return {};
            if (a.real || b.real) return Val::dbl(std::floor(a.asDouble() / b.asDouble()));
            int64_t q = a.i / b.i;
            if ((a.i % b.i != 0) && ((a.i < 0) != (b.i < 0))) --q;
            return Val::num(q);
        }
    }
    return {};
}

namespace {

bool compare(Op op, const Val& a, const Val& b) {
    if (op == Op::HasAll || op == Op::HasAny) {
        const uint64_t x = static_cast<uint64_t>(a.asInt());
        const uint64_t y = static_cast<uint64_t>(b.asInt());
        return op == Op::HasAll ? (x & y) == y : (x & y) != 0;
    }
    if (a.real || b.real) {
        const double x = a.asDouble(), y = b.asDouble();
        switch (op) {
            case Op::Eq: return x == y;
            case Op::Ne: return x != y;
            case Op::Lt: return x < y;
            case Op::Le: return x <= y;
            case Op::Gt: return x > y;
            case Op::Ge: return x >= y;
            case Op::HasAll: case Op::HasAny: break;
        }
        return false;
    }
    const int64_t x = a.i, y = b.i;
    switch (op) {
        case Op::Eq: return x == y;
        case Op::Ne: return x != y;
        case Op::Lt: return x < y;
        case Op::Le: return x <= y;
        case Op::Gt: return x > y;
        case Op::Ge: return x >= y;
        case Op::HasAll: case Op::HasAny: break;
    }
    return false;
}

}  // namespace

bool evalCond(const CondNode& cond, const Context& ctx) {
    switch (cond.kind) {
        case CondNode::Kind::All:
            for (const auto& kid : cond.kids) {
                if (!evalCond(*kid, ctx)) return false;
            }
            return true;
        case CondNode::Kind::Any:
            for (const auto& kid : cond.kids) {
                if (evalCond(*kid, ctx)) return true;
            }
            return false;
        case CondNode::Kind::Not:
            return !evalCond(*cond.kids[0], ctx);
        case CondNode::Kind::Exists:
            return cond.index >= 0 && static_cast<size_t>(cond.index) < ctx.values.size() && ctx.values[cond.index].ok;
        case CondNode::Kind::Cmp: {
            const Val l = evalValue(cond.left, ctx);
            const Val r = evalValue(cond.right, ctx);
            return l.ok && r.ok && compare(cond.op, l, r);
        }
    }
    return false;
}

// ---------------------------------------------------------------- estado

bool UserState::isUnlocked(const std::string& game, const std::string& ach) const {
    return unlocked.count(game + "/" + ach) != 0;
}

const Unlock* UserState::record(const std::string& game, const std::string& ach) const {
    const auto it = unlocked.find(game + "/" + ach);
    return it == unlocked.end() ? nullptr : &it->second;
}

void UserState::unlock(const std::string& game, const std::string& ach, int xp, const std::string& when) {
    Unlock u{game, ach, when, xp};
    unlocked[game + "/" + ach] = u;
    history.push_back(u);
}

int UserState::xpFor(const std::string& game) const {
    int total = 0;
    for (const auto& [key, u] : unlocked) {
        if (game.empty() || u.game == game) total += u.xp;
    }
    return total;
}

namespace {

Unlock parseUnlock(const cJSON* node) {
    return Unlock{jsonStr(node, "game"), jsonStr(node, "achievement"), jsonStr(node, "unlocked_at"),
                  static_cast<int>(jsonInt(node, "xp"))};
}

cJSON* unlockJson(const Unlock& u) {
    cJSON* obj = cJSON_CreateObject();
    cJSON_AddStringToObject(obj, "game", u.game.c_str());
    cJSON_AddStringToObject(obj, "achievement", u.achievement.c_str());
    cJSON_AddNumberToObject(obj, "xp", u.xp);
    cJSON_AddStringToObject(obj, "unlocked_at", u.unlockedAt.c_str());
    return obj;
}

}  // namespace

bool UserState::load(const std::string& path) {
    JsonDoc doc(parseFile(path));
    if (!doc.root) return false;
    unlocked.clear();
    history.clear();
    counters.clear();
    const cJSON* item = nullptr;
    cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(doc.root, "unlocked")) {
        unlocked[item->string] = parseUnlock(item);
    }
    cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(doc.root, "history")) {
        history.push_back(parseUnlock(item));
    }
    cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(doc.root, "counters")) {
        auto& game = counters[item->string];
        const cJSON* counter = nullptr;
        cJSON_ArrayForEach(counter, item) {
            int64_t value;
            if (jsonToInt(counter, value)) game[counter->string] = value;
        }
    }
    return true;
}

bool UserState::save(const std::string& path) const {
    JsonDoc doc(cJSON_CreateObject());
    cJSON_AddNumberToObject(doc.root, "version", 2);
    cJSON* unlockedObj = cJSON_AddObjectToObject(doc.root, "unlocked");
    for (const auto& [key, u] : unlocked) cJSON_AddItemToObject(unlockedObj, key.c_str(), unlockJson(u));
    cJSON* historyArr = cJSON_AddArrayToObject(doc.root, "history");
    for (const auto& u : history) cJSON_AddItemToArray(historyArr, unlockJson(u));
    cJSON* countersObj = cJSON_AddObjectToObject(doc.root, "counters");
    for (const auto& [game, values] : counters) {
        cJSON* gameObj = cJSON_AddObjectToObject(countersObj, game.c_str());
        for (const auto& [id, value] : values) cJSON_AddNumberToObject(gameObj, id.c_str(), static_cast<double>(value));
    }
    return writeFileAtomic(path, printJson(doc.root));
}

int levelForXp(int xp) {
    int level = 0;
    while (100.0 * std::pow(level + 1, 1.5) <= xp) ++level;
    return level;
}

int xpForLevel(int level) { return static_cast<int>(100.0 * std::pow(level, 1.5)); }

// ---------------------------------------------------------------- motor

Engine::Engine(const Pack& pack, int binding, UserState& state)
    : m_pack(pack), m_binding(binding), m_state(state), m_streaks(pack.achievements.size(), 0) {}

std::vector<int64_t> Engine::counters() const {
    std::vector<int64_t> out(m_pack.events.size(), 0);
    const auto game = m_state.counters.find(m_pack.game);
    if (game == m_state.counters.end()) return out;
    for (size_t i = 0; i < m_pack.events.size(); ++i) {
        const auto it = game->second.find(m_pack.events[i].id);
        if (it != game->second.end()) out[i] = it->second;
    }
    return out;
}

void Engine::storeCounters(const std::vector<int64_t>& values) {
    auto& game = m_state.counters[m_pack.game];
    for (size_t i = 0; i < m_pack.events.size(); ++i) {
        if (values[i] != 0 || game.count(m_pack.events[i].id)) game[m_pack.events[i].id] = values[i];
    }
}

std::string Engine::modeOf(const Snapshot& snap, const std::vector<int64_t>& counters) const {
    const Context ctx{snap.values, counters};
    for (const auto& [name, cond] : binding().modes) {
        if (evalCond(*cond, ctx)) return name;
    }
    return "default";
}

bool Engine::active(const Snapshot& snap, const std::vector<int64_t>& counters) const {
    const auto& guard = binding().activeWhen;
    return !guard || evalCond(*guard, Context{snap.values, counters});
}

TickResult Engine::tick(const std::vector<Snapshot>& snapshots, const std::string& now) {
    TickResult result;
    std::vector<int64_t> values = counters();
    std::vector<const Snapshot*> live;
    for (const auto& snap : snapshots) {
        if (active(snap, values)) live.push_back(&snap);
    }

    for (const Snapshot* snap : live) {
        const Context ctx{snap->values, values};
        for (size_t e = 0; e < m_pack.events.size(); ++e) {
            const auto key = std::make_pair(snap->label, static_cast<int>(e));
            const bool on = evalCond(*m_pack.events[e].when, ctx);
            if (on && !m_previousEvents[key]) {
                ++values[e];
                ++result.events[m_pack.events[e].id];
            }
            m_previousEvents[key] = on;
        }
    }
    storeCounters(values);

    for (size_t a = 0; a < m_pack.achievements.size(); ++a) {
        const Achievement& ach = m_pack.achievements[a];
        const Readiness ready = binding().ready[a];
        if (ready < Readiness::Rehearsal || m_state.isUnlocked(m_pack.game, ach.id)) continue;
        bool satisfied = false;
        for (const Snapshot* snap : live) {
            if (ach.modes) {
                const std::string mode = modeOf(*snap, values);
                if (std::find(ach.modes->begin(), ach.modes->end(), mode) == ach.modes->end()) continue;
            }
            if (evalCond(*ach.cond, Context{snap->values, values})) {
                satisfied = true;
                break;
            }
        }
        m_streaks[a] = satisfied ? m_streaks[a] + 1 : 0;
        if (m_streaks[a] < ach.confirm) continue;
        if (ready == Readiness::Live) {
            m_state.unlock(m_pack.game, ach.id, ach.xp, now);
            result.unlocked.push_back(static_cast<int>(a));
        } else if (m_rehearsed.insert(static_cast<int>(a)).second) {
            result.rehearsal.push_back(static_cast<int>(a));
        }
    }
    return result;
}

bool Engine::progress(int a, const std::vector<Snapshot>& snapshots, int64_t& current, int64_t& target) const {
    const Achievement& ach = m_pack.achievements[a];
    if (!ach.hasProgress) return false;
    target = ach.target;
    if (m_state.isUnlocked(m_pack.game, ach.id)) {
        current = target;
        return true;
    }
    const std::vector<int64_t> values = counters();
    static const Snapshot offline{"offline", {}};
    bool found = false;
    int64_t best = 0;
    auto consider = [&](const Snapshot& snap) {
        if (ach.modes) {
            const std::string mode = modeOf(snap, values);
            if (std::find(ach.modes->begin(), ach.modes->end(), mode) == ach.modes->end()) return;
        }
        const Val v = evalValue(ach.progress, Context{snap.values, values});
        if (!v.ok) return;
        best = std::max(best, std::min(v.asInt(), target));
        found = true;
    };
    if (snapshots.empty()) consider(offline);
    for (const auto& snap : snapshots) consider(snap);
    current = best;
    return found;
}

// ---------------------------------------------------------------- memória

namespace {

bool inRegions(const std::map<std::string, Region>& regions, uint64_t address, uint64_t size) {
    for (const auto& [name, r] : regions) {
        if (r.base <= address && address + size <= r.base + r.size) return true;
    }
    return false;
}

Val decode(VarType type, const uint8_t* p) {
    switch (type) {
        case VarType::U8: return Val::num(p[0]);
        case VarType::S8: return Val::num(static_cast<int8_t>(p[0]));
        case VarType::U16: { uint16_t v; std::memcpy(&v, p, 2); return Val::num(v); }
        case VarType::S16: { int16_t v; std::memcpy(&v, p, 2); return Val::num(v); }
        case VarType::U32: { uint32_t v; std::memcpy(&v, p, 4); return Val::num(v); }
        case VarType::S32: { int32_t v; std::memcpy(&v, p, 4); return Val::num(v); }
        case VarType::U64: { uint64_t v; std::memcpy(&v, p, 8); return Val::num(static_cast<int64_t>(v)); }
        case VarType::S64: { int64_t v; std::memcpy(&v, p, 8); return Val::num(v); }
        case VarType::F32: { float v; std::memcpy(&v, p, 4); return Val::dbl(v); }
        case VarType::F64: { double v; std::memcpy(&v, p, 8); return Val::dbl(v); }
    }
    return {};
}

}  // namespace

Snapshot readMemory(const Pack& pack, const Binding& binding, MemoryReader& reader) {
    Snapshot snap{"memória", std::vector<Val>(pack.vars.size())};
    std::vector<int64_t> anchors(binding.pointers.size(), -1);
    std::vector<bool> resolved(binding.pointers.size(), false);
    for (size_t p = 0; p < binding.pointers.size(); ++p) {
        const Pointer& ptr = binding.pointers[p];
        const auto region = reader.regions.find(ptr.region);
        if (region == reader.regions.end()) continue;
        uint64_t address = region->second.base;
        bool ok = true;
        for (uint64_t offset : ptr.chain) {
            const uint64_t slot = address + offset;
            uint64_t next = 0;
            if (!inRegions(reader.regions, slot, binding.pointerWidth) ||
                !reader.read(slot, &next, binding.pointerWidth) || next == 0) {
                ok = false;
                break;
            }
            address = next;
        }
        if (ok) {
            anchors[p] = static_cast<int64_t>(address);
            resolved[p] = true;
        }
    }

    std::vector<uint8_t> buffer;
    for (const Block& block : binding.blocks) {
        uint64_t base = 0;
        if (block.pointer >= 0) {
            if (static_cast<size_t>(block.pointer) >= resolved.size() || !resolved[block.pointer]) continue;
            base = static_cast<uint64_t>(anchors[block.pointer]);
        } else {
            const auto region = reader.regions.find(block.region);
            if (region == reader.regions.end()) continue;
            base = region->second.base;
        }
        const uint64_t address = base + block.offset;
        buffer.resize(block.size);
        if (!inRegions(reader.regions, address, block.size) || !reader.read(address, buffer.data(), block.size)) continue;
        for (const Field& f : block.fields) {
            if (f.var >= 0 && static_cast<size_t>(f.var) < snap.values.size()) {
                snap.values[f.var] = decode(f.type, buffer.data() + f.rel);
            }
        }
    }
    return snap;
}

// ---------------------------------------------------------------- save JSON

namespace {

struct PathNode {
    int leaf = -1;
    std::map<std::string, PathNode> keys;
    std::map<int64_t, PathNode> items;
};

class Scanner {
public:
    Scanner(const std::string& text, std::vector<Val>& values) : m_p(text.data()), m_end(text.data() + text.size()), m_values(values) {}

    bool run(const PathNode& root) {
        if (!value(&root, 0)) return false;
        ws();
        return m_p == m_end;
    }

private:
    void ws() {
        while (m_p < m_end && (*m_p == ' ' || *m_p == '\n' || *m_p == '\r' || *m_p == '\t')) ++m_p;
    }

    bool string(std::string* out) {
        if (m_p >= m_end || *m_p != '"') return false;
        ++m_p;
        while (m_p < m_end && *m_p != '"') {
            if (*m_p == '\\') {
                if (++m_p >= m_end) return false;
                if (out) {
                    switch (*m_p) {
                        case 'n': out->push_back('\n'); break;
                        case 't': out->push_back('\t'); break;
                        case 'r': out->push_back('\r'); break;
                        case 'b': out->push_back('\b'); break;
                        case 'f': out->push_back('\f'); break;
                        case 'u': out->push_back('?'); m_p += 4; break;
                        default: out->push_back(*m_p); break;
                    }
                } else if (*m_p == 'u') {
                    m_p += 4;
                }
                ++m_p;
                continue;
            }
            if (out) out->push_back(*m_p);
            ++m_p;
        }
        if (m_p >= m_end) return false;
        ++m_p;
        return true;
    }

    void set(const PathNode* node, Val v) {
        if (node && node->leaf >= 0 && static_cast<size_t>(node->leaf) < m_values.size()) m_values[node->leaf] = v;
    }

    bool value(const PathNode* node, int depth) {
        if (depth > 64) return false;
        ws();
        if (m_p >= m_end) return false;
        const char c = *m_p;
        if (c == '{') {
            ++m_p;
            ws();
            if (m_p < m_end && *m_p == '}') { ++m_p; return true; }
            while (true) {
                ws();
                std::string key;
                if (!string(node ? &key : nullptr)) return false;
                ws();
                if (m_p >= m_end || *m_p != ':') return false;
                ++m_p;
                const PathNode* child = nullptr;
                if (node) {
                    const auto it = node->keys.find(key);
                    if (it != node->keys.end()) child = &it->second;
                }
                if (!value(child, depth + 1)) return false;
                ws();
                if (m_p < m_end && *m_p == ',') { ++m_p; continue; }
                if (m_p < m_end && *m_p == '}') { ++m_p; return true; }
                return false;
            }
        }
        if (c == '[') {
            ++m_p;
            int64_t count = 0;
            ws();
            if (m_p < m_end && *m_p == ']') {
                ++m_p;
            } else {
                while (true) {
                    const PathNode* child = nullptr;
                    if (node) {
                        const auto it = node->items.find(count);
                        if (it != node->items.end()) child = &it->second;
                    }
                    if (!value(child, depth + 1)) return false;
                    ++count;
                    ws();
                    if (m_p < m_end && *m_p == ',') { ++m_p; continue; }
                    if (m_p < m_end && *m_p == ']') { ++m_p; break; }
                    return false;
                }
            }
            if (node) {
                const auto it = node->keys.find("length");
                if (it != node->keys.end()) set(&it->second, Val::num(count));
            }
            return true;
        }
        if (c == '"') return string(nullptr);
        if (m_end - m_p >= 4 && !std::strncmp(m_p, "true", 4)) { m_p += 4; set(node, Val::num(1)); return true; }
        if (m_end - m_p >= 5 && !std::strncmp(m_p, "false", 5)) { m_p += 5; set(node, Val::num(0)); return true; }
        if (m_end - m_p >= 4 && !std::strncmp(m_p, "null", 4)) { m_p += 4; return true; }
        const char* start = m_p;
        bool real = false;
        while (m_p < m_end && (std::strchr("+-0123456789.eE", *m_p) != nullptr)) {
            if (*m_p == '.' || *m_p == 'e' || *m_p == 'E') real = true;
            ++m_p;
        }
        if (m_p == start) return false;
        const std::string number(start, m_p);
        if (real) set(node, Val::dbl(std::strtod(number.c_str(), nullptr)));
        else set(node, Val::num(std::strtoll(number.c_str(), nullptr, 10)));
        return true;
    }

    const char* m_p;
    const char* m_end;
    std::vector<Val>& m_values;
};

PathNode buildTrie(const Binding& binding) {
    PathNode root;
    for (const PathVar& pv : binding.paths) {
        PathNode* node = &root;
        for (const PathToken& tok : pv.tokens) {
            node = tok.isIndex ? &node->items[tok.index] : &node->keys[tok.key];
        }
        node->leaf = pv.var;
    }
    return root;
}

}  // namespace

ScanResult scanSaveText(const Pack& pack, const Binding& binding, const std::string& text, Snapshot& out) {
    out.values.assign(pack.vars.size(), Val{});
    const PathNode root = buildTrie(binding);
    Scanner scanner(text, out.values);
    if (!scanner.run(root)) {
        out.values.assign(pack.vars.size(), Val{});
        return ScanResult::Invalid;
    }
    return ScanResult::Ok;
}

ScanResult scanSaveFile(const Pack& pack, const Binding& binding, const std::string& path, Snapshot& out) {
    std::string text;
    if (!readFile(path, text)) return ScanResult::Missing;
    const size_t slash = path.rfind('/');
    out.label = slash == std::string::npos ? path : path.substr(slash + 1);
    return scanSaveText(pack, binding, text, out);
}

}  // namespace sa

#pragma once

#include <cstdint>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace sa {

struct Val {
    bool ok = false;
    bool real = false;
    int64_t i = 0;
    double f = 0;

    static Val num(int64_t v) { Val x; x.ok = true; x.i = v; return x; }
    static Val dbl(double v) { Val x; x.ok = true; x.real = true; x.f = v; return x; }
    double asDouble() const { return real ? f : static_cast<double>(i); }
    int64_t asInt() const { return real ? static_cast<int64_t>(f) : i; }
};

struct CondNode;
using Cond = std::shared_ptr<const CondNode>;

struct ValueNode {
    enum class Kind { Const, Var, Count, Truth, Pop, Sum, Div };
    Kind kind = Kind::Const;
    Val constant;
    int index = -1;
    bool hasMask = false;
    uint64_t mask = ~0ull;
    std::vector<ValueNode> kids;
    Cond cond;
};

enum class Op { Eq, Ne, Lt, Le, Gt, Ge, HasAll, HasAny };

struct CondNode {
    enum class Kind { All, Any, Not, Exists, Cmp };
    Kind kind = Kind::Cmp;
    std::vector<Cond> kids;
    int index = -1;
    Op op = Op::Eq;
    ValueNode left, right;
};

enum class Readiness { Unsupported = 0, Pending = 1, Rehearsal = 2, Live = 3 };
enum class VarType { U8, S8, U16, S16, U32, S32, U64, S64, F32, F64 };

size_t typeSize(VarType t);
const char* readinessName(Readiness r);

using Localized = std::map<std::string, std::string>;
const std::string& localized(const Localized& text, const std::string& lang);

struct Field {
    int var;
    uint32_t rel;
    VarType type;
};

struct Block {
    int pointer = -1;
    std::string region;
    uint64_t offset = 0;
    uint32_t size = 0;
    std::vector<Field> fields;
};

struct Pointer {
    std::string region;
    std::vector<uint64_t> chain;
};

struct PathToken {
    bool isIndex = false;
    int64_t index = 0;
    std::string key;
};

struct PathVar {
    int var;
    std::vector<PathToken> tokens;
};

struct Binding {
    std::string id;
    bool memory = false;
    std::vector<std::string> buildIds;
    std::vector<std::string> files;
    uint32_t pollMs = 1000;
    Cond activeWhen;
    std::vector<std::pair<std::string, Cond>> modes;
    std::vector<Readiness> ready;
    std::vector<Pointer> pointers;
    uint32_t pointerWidth = 8;
    std::vector<Block> blocks;
    std::vector<PathVar> paths;
};

struct Event {
    std::string id;
    Cond when;
};

struct Achievement {
    std::string id;
    Localized name, desc;
    int xp = 0;
    std::string rarity;
    bool secret = false;
    std::string icon;
    std::optional<std::vector<std::string>> modes;
    int confirm = 1;
    bool hasProgress = false;
    ValueNode progress;
    int64_t target = 0;
    Cond cond;
};

struct Pack {
    std::string game, kind, rev;
    Localized name;
    std::vector<std::string> titleIds;
    std::vector<std::string> vars;
    std::vector<Event> events;
    std::vector<Binding> bindings;
    std::vector<Achievement> achievements;

    int bindingForBuild(const std::string& buildId) const;
    bool hasTitle(const std::string& titleId) const;
};

bool loadPack(const std::string& path, Pack& out, std::string& error);
bool parsePack(const char* text, Pack& out, std::string& error);

}  // namespace sa

#include "pack.hpp"

#include <cmath>
#include <cstring>

#include "json.hpp"

namespace sa {

size_t typeSize(VarType t) {
    switch (t) {
        case VarType::U8: case VarType::S8: return 1;
        case VarType::U16: case VarType::S16: return 2;
        case VarType::U32: case VarType::S32: case VarType::F32: return 4;
        case VarType::U64: case VarType::S64: case VarType::F64: return 8;
    }
    return 0;
}

const char* readinessName(Readiness r) {
    switch (r) {
        case Readiness::Live: return "live";
        case Readiness::Rehearsal: return "rehearsal";
        case Readiness::Pending: return "pending";
        case Readiness::Unsupported: return "unsupported";
    }
    return "unsupported";
}

const std::string& localized(const Localized& text, const std::string& lang) {
    static const std::string empty;
    auto it = text.find(lang);
    if (it != text.end() && !it->second.empty()) return it->second;
    it = text.find("en");
    if (it != text.end() && !it->second.empty()) return it->second;
    return text.empty() ? empty : text.begin()->second;
}

int Pack::bindingForBuild(const std::string& buildId) const {
    for (size_t i = 0; i < bindings.size(); ++i) {
        for (const auto& id : bindings[i].buildIds) {
            if (strcasecmp(id.c_str(), buildId.c_str()) == 0) return static_cast<int>(i);
        }
    }
    return -1;
}

bool Pack::hasTitle(const std::string& titleId) const {
    for (const auto& id : titleIds) {
        if (strcasecmp(id.c_str(), titleId.c_str()) == 0) return true;
    }
    return false;
}

namespace {

struct Fail {
    std::string message;
};

[[noreturn]] void fail(const std::string& message) { throw Fail{message}; }

const cJSON* need(const cJSON* obj, const char* key) {
    const cJSON* item = cJSON_GetObjectItemCaseSensitive(obj, key);
    if (!item) fail(std::string("campo ausente: ") + key);
    return item;
}

int64_t toInt(const cJSON* item) {
    int64_t value;
    if (!jsonToInt(item, value)) fail("inteiro inválido");
    return value;
}

Val toConst(const cJSON* item) {
    if (cJSON_IsNumber(item)) {
        const double d = item->valuedouble;
        if (std::floor(d) == d && std::fabs(d) < 9007199254740992.0) return Val::num(static_cast<int64_t>(d));
        return Val::dbl(d);
    }
    return Val::num(toInt(item));
}

Cond parseCond(const cJSON* node);

ValueNode parseValue(const cJSON* node) {
    ValueNode v;
    if (!cJSON_IsObject(node)) {
        v.kind = ValueNode::Kind::Const;
        v.constant = toConst(node);
        return v;
    }
    const cJSON* child = node->child;
    if (!child) fail("valor vazio");
    const char* key = child->string;
    if (!std::strcmp(key, "v")) {
        v.kind = ValueNode::Kind::Var;
        v.index = static_cast<int>(toInt(child));
    } else if (!std::strcmp(key, "c")) {
        v.kind = ValueNode::Kind::Count;
        v.index = static_cast<int>(toInt(child));
    } else if (!std::strcmp(key, "t")) {
        v.kind = ValueNode::Kind::Truth;
        v.cond = parseCond(child);
    } else if (!std::strcmp(key, "pop") || !std::strcmp(key, "mask")) {
        v.kind = ValueNode::Kind::Pop;
        v.kids.push_back(parseValue(need(node, "pop")));
        const cJSON* mask = cJSON_GetObjectItemCaseSensitive(node, "mask");
        if (mask) {
            v.hasMask = true;
            v.mask = static_cast<uint64_t>(toInt(mask));
        }
    } else if (!std::strcmp(key, "sum") || !std::strcmp(key, "div")) {
        v.kind = key[0] == 's' ? ValueNode::Kind::Sum : ValueNode::Kind::Div;
        const cJSON* item = nullptr;
        cJSON_ArrayForEach(item, child) v.kids.push_back(parseValue(item));
        if (v.kind == ValueNode::Kind::Div && v.kids.size() != 2) fail("div exige 2 valores");
    } else {
        fail(std::string("valor desconhecido: ") + key);
    }
    return v;
}

Op parseOp(const std::string& op) {
    if (op == "==") return Op::Eq;
    if (op == "!=") return Op::Ne;
    if (op == "<") return Op::Lt;
    if (op == "<=") return Op::Le;
    if (op == ">") return Op::Gt;
    if (op == ">=") return Op::Ge;
    if (op == "has_all") return Op::HasAll;
    if (op == "has_any") return Op::HasAny;
    fail("operador desconhecido: " + op);
}

Cond parseCond(const cJSON* node) {
    if (!cJSON_IsObject(node)) fail("condição inválida");
    auto c = std::make_shared<CondNode>();
    const cJSON* item = nullptr;
    if ((item = cJSON_GetObjectItemCaseSensitive(node, "all")) || (item = cJSON_GetObjectItemCaseSensitive(node, "any"))) {
        c->kind = item->string[1] == 'l' ? CondNode::Kind::All : CondNode::Kind::Any;
        const cJSON* kid = nullptr;
        cJSON_ArrayForEach(kid, item) c->kids.push_back(parseCond(kid));
    } else if ((item = cJSON_GetObjectItemCaseSensitive(node, "not"))) {
        c->kind = CondNode::Kind::Not;
        c->kids.push_back(parseCond(item));
    } else if ((item = cJSON_GetObjectItemCaseSensitive(node, "exists"))) {
        c->kind = CondNode::Kind::Exists;
        c->index = static_cast<int>(toInt(item));
    } else {
        c->kind = CondNode::Kind::Cmp;
        c->op = parseOp(jsonStr(node, "op"));
        c->left = parseValue(need(node, "l"));
        c->right = parseValue(need(node, "r"));
    }
    return c;
}

Localized parseLocalized(const cJSON* node) {
    Localized out;
    const cJSON* item = nullptr;
    cJSON_ArrayForEach(item, node) {
        if (cJSON_IsString(item)) out[item->string] = item->valuestring;
    }
    return out;
}

std::vector<std::string> parseStrings(const cJSON* node) {
    std::vector<std::string> out;
    const cJSON* item = nullptr;
    cJSON_ArrayForEach(item, node) {
        if (cJSON_IsString(item)) out.emplace_back(item->valuestring);
    }
    return out;
}

VarType parseType(const std::string& name) {
    static const std::pair<const char*, VarType> table[] = {
        {"u8", VarType::U8}, {"s8", VarType::S8}, {"u16", VarType::U16}, {"s16", VarType::S16},
        {"u32", VarType::U32}, {"s32", VarType::S32}, {"u64", VarType::U64}, {"s64", VarType::S64},
        {"f32", VarType::F32}, {"f64", VarType::F64},
    };
    for (const auto& [key, type] : table) {
        if (name == key) return type;
    }
    fail("tipo desconhecido: " + name);
}

Readiness parseReadiness(const std::string& name) {
    if (name == "live") return Readiness::Live;
    if (name == "rehearsal") return Readiness::Rehearsal;
    if (name == "pending") return Readiness::Pending;
    return Readiness::Unsupported;
}

Binding parseBinding(const cJSON* node) {
    Binding b;
    b.id = jsonStr(node, "id");
    b.memory = jsonStr(node, "source") == "memory";
    b.buildIds = parseStrings(cJSON_GetObjectItemCaseSensitive(node, "build_ids"));
    b.files = parseStrings(cJSON_GetObjectItemCaseSensitive(node, "files"));
    b.pollMs = static_cast<uint32_t>(jsonInt(node, "poll_ms", 1000));
    const cJSON* guard = cJSON_GetObjectItemCaseSensitive(node, "active_when");
    if (guard && !cJSON_IsNull(guard)) b.activeWhen = parseCond(guard);
    const cJSON* item = nullptr;
    cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(node, "modes")) {
        b.modes.emplace_back(jsonStr(item, "name"), parseCond(need(item, "cond")));
    }
    cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(node, "ready")) {
        b.ready.push_back(parseReadiness(cJSON_IsString(item) ? item->valuestring : ""));
    }
    cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(node, "pointers")) {
        Pointer p;
        p.region = jsonStr(item, "region");
        const cJSON* off = nullptr;
        cJSON_ArrayForEach(off, cJSON_GetObjectItemCaseSensitive(item, "chain")) p.chain.push_back(static_cast<uint64_t>(toInt(off)));
        b.pointers.push_back(std::move(p));
    }
    cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(node, "blocks")) {
        Block blk;
        const cJSON* anchor = need(item, "anchor");
        if (cJSON_IsString(anchor)) blk.region = anchor->valuestring;
        else blk.pointer = static_cast<int>(toInt(anchor));
        blk.offset = static_cast<uint64_t>(toInt(need(item, "offset")));
        blk.size = static_cast<uint32_t>(toInt(need(item, "size")));
        const cJSON* field = nullptr;
        cJSON_ArrayForEach(field, cJSON_GetObjectItemCaseSensitive(item, "vars")) {
            Field f;
            f.var = static_cast<int>(toInt(cJSON_GetArrayItem(field, 0)));
            f.rel = static_cast<uint32_t>(toInt(cJSON_GetArrayItem(field, 1)));
            const cJSON* type = cJSON_GetArrayItem(field, 2);
            f.type = parseType(cJSON_IsString(type) ? type->valuestring : "");
            if (f.rel + typeSize(f.type) > blk.size) fail("campo fora do bloco");
            blk.fields.push_back(f);
        }
        b.blocks.push_back(std::move(blk));
    }
    cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(node, "paths")) {
        PathVar pv;
        pv.var = static_cast<int>(toInt(cJSON_GetArrayItem(item, 0)));
        const cJSON* tok = nullptr;
        cJSON_ArrayForEach(tok, cJSON_GetArrayItem(item, 1)) {
            PathToken t;
            if (cJSON_IsNumber(tok)) {
                t.isIndex = true;
                t.index = static_cast<int64_t>(tok->valuedouble);
            } else if (cJSON_IsString(tok)) {
                t.key = tok->valuestring;
            }
            pv.tokens.push_back(std::move(t));
        }
        b.paths.push_back(std::move(pv));
    }
    return b;
}

Achievement parseAchievement(const cJSON* node) {
    Achievement a;
    a.id = jsonStr(node, "id");
    a.name = parseLocalized(cJSON_GetObjectItemCaseSensitive(node, "name"));
    a.desc = parseLocalized(cJSON_GetObjectItemCaseSensitive(node, "desc"));
    a.xp = static_cast<int>(jsonInt(node, "xp"));
    a.rarity = jsonStr(node, "rarity", "common");
    a.secret = jsonBool(node, "secret");
    a.icon = jsonStr(node, "icon", "common/trophy");
    const cJSON* modes = cJSON_GetObjectItemCaseSensitive(node, "modes");
    if (cJSON_IsArray(modes)) a.modes = parseStrings(modes);
    a.confirm = static_cast<int>(jsonInt(node, "confirm", 1));
    const cJSON* progress = cJSON_GetObjectItemCaseSensitive(node, "progress");
    if (cJSON_IsObject(progress)) {
        a.hasProgress = true;
        a.progress = parseValue(need(progress, "value"));
        a.target = toInt(need(progress, "target"));
    }
    a.cond = parseCond(need(node, "cond"));
    return a;
}

}  // namespace

bool parsePack(const char* text, Pack& out, std::string& error) {
    JsonDoc doc(cJSON_Parse(text));
    if (!doc.root) {
        error = "JSON inválido";
        return false;
    }
    try {
        Pack pack;
        if (jsonInt(doc.root, "format") != 1) fail("formato de pacote não suportado");
        pack.game = jsonStr(doc.root, "game");
        pack.kind = jsonStr(doc.root, "kind");
        pack.rev = jsonStr(doc.root, "rev");
        pack.name = parseLocalized(cJSON_GetObjectItemCaseSensitive(doc.root, "name"));
        pack.titleIds = parseStrings(cJSON_GetObjectItemCaseSensitive(doc.root, "title_ids"));
        pack.vars = parseStrings(cJSON_GetObjectItemCaseSensitive(doc.root, "vars"));
        const cJSON* item = nullptr;
        cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(doc.root, "events")) {
            pack.events.push_back({jsonStr(item, "id"), parseCond(need(item, "when"))});
        }
        cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(doc.root, "bindings")) {
            pack.bindings.push_back(parseBinding(item));
        }
        cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(doc.root, "achievements")) {
            pack.achievements.push_back(parseAchievement(item));
        }
        for (const auto& b : pack.bindings) {
            if (b.ready.size() != pack.achievements.size()) fail("binding " + b.id + ": prontidão incompleta");
        }
        out = std::move(pack);
        return true;
    } catch (const Fail& f) {
        error = f.message;
        return false;
    }
}

bool loadPack(const std::string& path, Pack& out, std::string& error) {
    std::string text;
    if (!readFile(path, text)) {
        error = "não foi possível ler " + path;
        return false;
    }
    return parsePack(text.c_str(), out, error);
}

}  // namespace sa

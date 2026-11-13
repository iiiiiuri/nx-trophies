#include "publish.hpp"

#include <algorithm>
#include <cstring>
#include <strings.h>

namespace sa {

namespace {

struct RarityText {
    const char* key;
    const char* pt;
    const char* en;
};

constexpr RarityText kRarities[] = {
    {"common", "Comum", "Common"},
    {"uncommon", "Incomum", "Uncommon"},
    {"rare", "Rara", "Rare"},
    {"epic", "Épica", "Epic"},
    {"legendary", "Lendária", "Legendary"},
};

bool portuguese(const std::string& lang) { return lang.rfind("pt", 0) == 0; }

}  // namespace

std::string rarityLabel(const std::string& rarity, const std::string& lang) {
    for (const auto& r : kRarities) {
        if (rarity == r.key) return portuguese(lang) ? r.pt : r.en;
    }
    return rarity;
}

cJSON* gameView(const Pack& pack, Engine& engine, const UserState& state, const std::vector<Snapshot>& snapshots,
                const std::string& lang, const std::string& now) {
    const bool pt = portuguese(lang);
    const char* secretName = pt ? "Conquista secreta" : "Secret achievement";
    const char* secretDesc = pt ? "Continue jogando para descobrir." : "Keep playing to find out.";
    const Binding& binding = engine.binding();

    cJSON* view = cJSON_CreateObject();
    cJSON_AddNumberToObject(view, "version", 1);
    cJSON_AddStringToObject(view, "game", pack.game.c_str());
    cJSON_AddStringToObject(view, "name", localized(pack.name, lang).c_str());
    cJSON_AddStringToObject(view, "updated_at", now.c_str());
    cJSON* items = cJSON_CreateArray();
    int done = 0, xpTotal = 0;
    for (size_t a = 0; a < pack.achievements.size(); ++a) {
        const Achievement& ach = pack.achievements[a];
        const Unlock* record = state.record(pack.game, ach.id);
        const bool unlocked = record != nullptr;
        const bool hidden = ach.secret && !unlocked;
        done += unlocked ? 1 : 0;
        xpTotal += ach.xp;

        cJSON* item = cJSON_CreateObject();
        cJSON_AddStringToObject(item, "id", ach.id.c_str());
        cJSON_AddStringToObject(item, "name", hidden ? secretName : localized(ach.name, lang).c_str());
        cJSON_AddStringToObject(item, "description", hidden ? secretDesc : localized(ach.desc, lang).c_str());
        cJSON_AddStringToObject(item, "icon", hidden ? kSecretIcon : ach.icon.c_str());
        cJSON_AddNumberToObject(item, "xp", ach.xp);
        cJSON_AddStringToObject(item, "rarity", rarityLabel(ach.rarity, lang).c_str());
        cJSON_AddBoolToObject(item, "secret", ach.secret);
        cJSON_AddBoolToObject(item, "unlocked", unlocked);
        if (record) cJSON_AddStringToObject(item, "unlocked_at", record->unlockedAt.c_str());
        else cJSON_AddNullToObject(item, "unlocked_at");
        int64_t current = 0, target = 0;
        if (!hidden && engine.progress(static_cast<int>(a), snapshots, current, target)) {
            cJSON* progress = cJSON_AddArrayToObject(item, "progress");
            cJSON_AddItemToArray(progress, cJSON_CreateNumber(static_cast<double>(current)));
            cJSON_AddItemToArray(progress, cJSON_CreateNumber(static_cast<double>(target)));
        } else {
            cJSON_AddNullToObject(item, "progress");
        }
        cJSON_AddStringToObject(item, "status", readinessName(binding.ready[a]));
        cJSON_AddItemToArray(items, item);
    }
    cJSON_AddNumberToObject(view, "unlocked", done);
    cJSON_AddNumberToObject(view, "total", static_cast<double>(pack.achievements.size()));
    cJSON_AddNumberToObject(view, "xp", state.xpFor(pack.game));
    cJSON_AddNumberToObject(view, "xp_total", xpTotal);
    cJSON_AddItemToObject(view, "achievements", items);
    return view;
}

cJSON* profileView(const UserState& state, const std::vector<const cJSON*>& games, const std::string& now) {
    struct Summary {
        std::string id, name;
        int unlocked, total, xp;
    };
    std::vector<Summary> summary;
    for (const cJSON* g : games) {
        summary.push_back({jsonStr(g, "game"), jsonStr(g, "name"), static_cast<int>(jsonInt(g, "unlocked")),
                           static_cast<int>(jsonInt(g, "total")), static_cast<int>(jsonInt(g, "xp"))});
    }
    std::sort(summary.begin(), summary.end(), [](const Summary& a, const Summary& b) {
        if (a.unlocked != b.unlocked) return a.unlocked > b.unlocked;
        return strcasecmp(a.name.c_str(), b.name.c_str()) < 0;
    });
    const int xp = state.xpFor();
    const int level = levelForXp(xp);
    int unlocked = 0, total = 0;
    cJSON* view = cJSON_CreateObject();
    cJSON_AddNumberToObject(view, "version", 1);
    cJSON_AddStringToObject(view, "updated_at", now.c_str());
    cJSON_AddNumberToObject(view, "xp", xp);
    cJSON_AddNumberToObject(view, "level", level);
    cJSON_AddNumberToObject(view, "next_level_xp", xpForLevel(level + 1));
    cJSON* list = cJSON_CreateArray();
    for (const auto& s : summary) {
        unlocked += s.unlocked;
        total += s.total;
        cJSON* g = cJSON_CreateObject();
        cJSON_AddStringToObject(g, "id", s.id.c_str());
        cJSON_AddStringToObject(g, "name", s.name.c_str());
        cJSON_AddNumberToObject(g, "unlocked", s.unlocked);
        cJSON_AddNumberToObject(g, "total", s.total);
        cJSON_AddNumberToObject(g, "xp", s.xp);
        cJSON_AddItemToArray(list, g);
    }
    cJSON_AddNumberToObject(view, "unlocked", unlocked);
    cJSON_AddNumberToObject(view, "total", total);
    cJSON_AddItemToObject(view, "games", list);
    return view;
}

std::string notificationName(const std::string& iconKey, uint64_t unique) {
    std::string app = "SwitchAchievements-" + iconKey;
    std::replace(app.begin(), app.end(), '/', '.');
    return app + "-" + std::to_string(unique) + ".notify";
}

std::string notificationJson(const Achievement& ach, const std::string& lang) {
    JsonDoc doc(cJSON_CreateObject());
    const bool pt = portuguese(lang);
    const std::string text = localized(ach.name, lang) + "\n" + localized(ach.desc, lang) + "\n+" +
                             std::to_string(ach.xp) + " XP · " + rarityLabel(ach.rarity, lang);
    cJSON_AddStringToObject(doc.root, "title", pt ? "Conquista desbloqueada" : "Achievement unlocked");
    cJSON_AddStringToObject(doc.root, "text", text.c_str());
    cJSON_AddNumberToObject(doc.root, "font_size", 20);
    cJSON_AddStringToObject(doc.root, "alignment", "left");
    cJSON_AddNumberToObject(doc.root, "duration", 5000);
    cJSON_AddStringToObject(doc.root, "show_time", "false");
    return printJson(doc.root);
}

}  // namespace sa

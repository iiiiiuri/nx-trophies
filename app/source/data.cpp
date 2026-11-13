#include <switch.h>

#include "data.hpp"

#include <dirent.h>

#include <algorithm>
#include <cstdio>
#include <strings.h>

#include "sa/json.hpp"
#include "sa/publish.hpp"

namespace app {

namespace {

const sa::Layout kLayout;

GameData loadGame(const std::string& id) {
    GameData game;
    game.id = id;
    sa::JsonDoc pack(sa::parseFile(kLayout.packs() + "/" + id + ".json"));
    if (pack.root) {
        game.name = sa::jsonStr(cJSON_GetObjectItemCaseSensitive(pack.root, "name"), "pt-BR", id);
        const cJSON* titles = cJSON_GetObjectItemCaseSensitive(pack.root, "title_ids");
        if (cJSON_GetArraySize(titles) > 0) game.titleId = cJSON_GetArrayItem(titles, 0)->valuestring;
        game.total = cJSON_GetArraySize(cJSON_GetObjectItemCaseSensitive(pack.root, "achievements"));
    }
    sa::JsonDoc view(sa::parseFile(kLayout.progress(id)));
    if (!view.root) return game;
    game.name = sa::jsonStr(view.root, "name", game.name);
    game.updatedAt = sa::jsonStr(view.root, "updated_at");
    game.unlocked = static_cast<int>(sa::jsonInt(view.root, "unlocked"));
    game.total = static_cast<int>(sa::jsonInt(view.root, "total", game.total));
    game.xp = static_cast<int>(sa::jsonInt(view.root, "xp"));
    game.xpTotal = static_cast<int>(sa::jsonInt(view.root, "xp_total"));
    const cJSON* item = nullptr;
    cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(view.root, "achievements")) {
        AchievementRow row;
        row.id = sa::jsonStr(item, "id");
        row.name = sa::jsonStr(item, "name");
        row.description = sa::jsonStr(item, "description");
        row.icon = sa::jsonStr(item, "icon", "common/trophy");
        row.rarity = sa::jsonStr(item, "rarity");
        row.status = sa::jsonStr(item, "status");
        row.unlockedAt = sa::jsonStr(item, "unlocked_at");
        row.xp = static_cast<int>(sa::jsonInt(item, "xp"));
        row.secret = sa::jsonBool(item, "secret");
        row.unlocked = sa::jsonBool(item, "unlocked");
        const cJSON* progress = cJSON_GetObjectItemCaseSensitive(item, "progress");
        if (cJSON_GetArraySize(progress) == 2) {
            row.hasProgress = true;
            row.current = static_cast<long long>(cJSON_GetArrayItem(progress, 0)->valuedouble);
            row.target = static_cast<long long>(cJSON_GetArrayItem(progress, 1)->valuedouble);
        }
        game.rows.push_back(std::move(row));
    }
    return game;
}

}  // namespace

Library loadLibrary() {
    Library lib;
    std::vector<std::string> ids;
    if (DIR* dir = opendir(kLayout.packs().c_str())) {
        while (dirent* entry = readdir(dir)) {
            const std::string name = entry->d_name;
            if (name.size() > 5 && name.compare(name.size() - 5, 5, ".json") == 0) ids.push_back(name.substr(0, name.size() - 5));
        }
        closedir(dir);
    }
    for (const auto& id : ids) lib.games.push_back(loadGame(id));
    std::sort(lib.games.begin(), lib.games.end(), [](const GameData& a, const GameData& b) {
        if (a.unlocked != b.unlocked) return a.unlocked > b.unlocked;
        return strcasecmp(a.name.c_str(), b.name.c_str()) < 0;
    });

    sa::JsonDoc profile(sa::parseFile(kLayout.profile()));
    if (profile.root) {
        lib.synced = true;
        lib.level = static_cast<int>(sa::jsonInt(profile.root, "level"));
        lib.xp = static_cast<int>(sa::jsonInt(profile.root, "xp"));
        lib.nextLevelXp = static_cast<int>(sa::jsonInt(profile.root, "next_level_xp", 100));
        lib.updatedAt = sa::jsonStr(profile.root, "updated_at");
    }
    for (const auto& g : lib.games) {
        lib.unlocked += g.unlocked;
        lib.total += g.total;
    }

    sa::JsonDoc detected(sa::parseFile(kLayout.detected()));
    if (detected.root) {
        lib.detected.present = true;
        lib.detected.supported = sa::jsonBool(detected.root, "supported");
        lib.detected.titleId = sa::jsonStr(detected.root, "title_id");
        lib.detected.buildId = sa::jsonStr(detected.root, "build_id");
        lib.detected.game = sa::jsonStr(detected.root, "game");
    }
    return lib;
}

std::string iconPath(const std::string& key) { return kLayout.root() + "/icons/" + key + ".png"; }

std::string coverPath(const std::string& gameId) { return kLayout.root() + "/covers/" + gameId + ".png"; }

std::string formatDate(const std::string& iso) {
    int y, mo, d, h, mi, s;
    if (std::sscanf(iso.c_str(), "%d-%d-%dT%d:%d:%d", &y, &mo, &d, &h, &mi, &s) != 6) return iso;
    // dias desde 1970-01-01 (algoritmo civil de Howard Hinnant), para converter UTC no fuso do console
    const int yy = y - (mo <= 2);
    const int era = (yy >= 0 ? yy : yy - 399) / 400;
    const int yoe = yy - era * 400;
    const int doy = (153 * (mo + (mo > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    const int doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    const u64 epoch = (static_cast<u64>(era) * 146097 + doe - 719468) * 86400ull + h * 3600 + mi * 60 + s;
    TimeCalendarTime cal;
    TimeCalendarAdditionalInfo info;
    if (R_FAILED(timeToCalendarTimeWithMyRule(epoch, &cal, &info))) {
        cal = TimeCalendarTime{static_cast<u16>(y), static_cast<u8>(mo), static_cast<u8>(d), static_cast<u8>(h), static_cast<u8>(mi), static_cast<u8>(s), 0};
    }
    char buf[32];
    std::snprintf(buf, sizeof(buf), "%02u/%02u/%04u %02u:%02u", cal.day, cal.month, cal.year, cal.hour, cal.minute);
    return buf;
}

}  // namespace app

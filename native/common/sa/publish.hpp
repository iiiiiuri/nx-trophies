#pragma once

#include <string>
#include <vector>

#include "engine.hpp"
#include "json.hpp"

namespace sa {

// Raiz do SD: "sdmc:" no console; nos testes, uma pasta temporária.
struct Layout {
    std::string sd = "sdmc:";

    std::string root() const { return sd + "/config/switch-achievements"; }
    std::string packs() const { return root() + "/packs"; }
    std::string state() const { return root() + "/state.json"; }
    std::string profile() const { return root() + "/profile.json"; }
    std::string detected() const { return root() + "/detected.json"; }
    std::string settings() const { return root() + "/settings.json"; }
    std::string log() const { return root() + "/sysmodule.log"; }
    std::string progress(const std::string& game) const { return root() + "/progress/" + game + ".json"; }
    std::string notifications() const { return sd + "/config/ultrahand/notifications"; }
};

constexpr const char* kSecretIcon = "common/secret";

std::string rarityLabel(const std::string& rarity, const std::string& lang);

cJSON* gameView(const Pack& pack, Engine& engine, const UserState& state, const std::vector<Snapshot>& snapshots,
                const std::string& lang, const std::string& now);
cJSON* profileView(const UserState& state, const std::vector<const cJSON*>& games, const std::string& now);

std::string notificationName(const std::string& iconKey, uint64_t unique);
std::string notificationJson(const Achievement& ach, const std::string& lang);

}  // namespace sa

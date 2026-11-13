#pragma once

#include <string>
#include <vector>

namespace app {

struct AchievementRow {
    std::string id, name, description, icon, rarity, status, unlockedAt;
    int xp = 0;
    bool secret = false, unlocked = false, hasProgress = false;
    long long current = 0, target = 0;
};

struct GameData {
    std::string id, name, titleId, updatedAt;
    int unlocked = 0, total = 0, xp = 0, xpTotal = 0;
    std::vector<AchievementRow> rows;
};

struct Detected {
    bool present = false, supported = false;
    std::string titleId, buildId, game;
};

struct Library {
    bool synced = false;
    int level = 0, xp = 0, nextLevelXp = 100, unlocked = 0, total = 0;
    std::string updatedAt;
    std::vector<GameData> games;
    Detected detected;
};

Library loadLibrary();
std::string iconPath(const std::string& key);
std::string coverPath(const std::string& gameId);
std::string formatDate(const std::string& iso);

}  // namespace app

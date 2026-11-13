#define TESLA_INIT_IMPL
#include <exception_wrap.hpp>
#include <ultra.hpp>
#include <tesla.hpp>

#include <cJSON.h>

#include <cstdio>
#include <memory>
#include <string>
#include <vector>

namespace {

constexpr const char* kRoot = "sdmc:/config/switch-achievements";
constexpr s32 kIconSize = 50;
constexpr u16 kItemHeight = 96;

const tsl::Color kMuted(0x9, 0x9, 0x9, 0xF);
const tsl::Color kUnlocked(0x5, 0xD, 0x7, 0xF);
const tsl::Color kGold(0xF, 0xC, 0x3, 0xF);
const tsl::Color kTrack(0x3, 0x3, 0x3, 0xF);
const tsl::Color kFill(0x2, 0x9, 0xF, 0xF);

struct JsonDoc {
    cJSON* root = nullptr;
    explicit JsonDoc(const std::string& path) {
        FILE* file = std::fopen(path.c_str(), "rb");
        if (!file) return;
        std::string text;
        char chunk[4096];
        size_t n;
        while ((n = std::fread(chunk, 1, sizeof(chunk), file)) > 0) text.append(chunk, n);
        std::fclose(file);
        root = cJSON_Parse(text.c_str());
    }
    ~JsonDoc() { cJSON_Delete(root); }
    JsonDoc(const JsonDoc&) = delete;
    JsonDoc& operator=(const JsonDoc&) = delete;
};

std::string str(const cJSON* obj, const char* key) {
    const cJSON* item = cJSON_GetObjectItemCaseSensitive(obj, key);
    return cJSON_IsString(item) ? item->valuestring : "";
}

int num(const cJSON* obj, const char* key) {
    const cJSON* item = cJSON_GetObjectItemCaseSensitive(obj, key);
    return cJSON_IsNumber(item) ? item->valueint : 0;
}

bool flag(const cJSON* obj, const char* key) {
    return cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(obj, key));
}

std::vector<u8> loadIcon(const std::string& key, bool locked) {
    std::vector<u8> pixels(kIconSize * kIconSize * 4);
    FILE* file = std::fopen((std::string(kRoot) + "/icons/" + key + ".rgba").c_str(), "rb");
    if (!file) return {};
    const size_t got = std::fread(pixels.data(), 1, pixels.size(), file);
    std::fclose(file);
    if (got != pixels.size()) return {};
    if (locked) {
        for (size_t i = 0; i < pixels.size(); i += 4) {
            const u8 gray = static_cast<u8>((pixels[i] * 30 + pixels[i + 1] * 59 + pixels[i + 2] * 11) / 250);
            pixels[i] = pixels[i + 1] = pixels[i + 2] = gray;
        }
    }
    return pixels;
}

struct Achievement {
    std::string name, description, icon, rarity;
    int xp = 0;
    bool unlocked = false;
    int current = 0, target = 0;
};

Achievement parseAchievement(const cJSON* obj) {
    Achievement ach;
    ach.name = str(obj, "name");
    ach.description = str(obj, "description");
    ach.icon = str(obj, "icon");
    ach.rarity = str(obj, "rarity");
    ach.xp = num(obj, "xp");
    ach.unlocked = flag(obj, "unlocked");
    const cJSON* progress = cJSON_GetObjectItemCaseSensitive(obj, "progress");
    if (cJSON_IsArray(progress) && cJSON_GetArraySize(progress) == 2) {
        ach.current = cJSON_GetArrayItem(progress, 0)->valueint;
        ach.target = cJSON_GetArrayItem(progress, 1)->valueint;
    }
    return ach;
}

class AchievementItem : public tsl::elm::ListItem {
public:
    explicit AchievementItem(Achievement ach)
        : ListItem(ach.name), m_ach(std::move(ach)), m_icon(loadIcon(m_ach.icon, !m_ach.unlocked)) {}

    void draw(tsl::gfx::Renderer* renderer) override {
        const s32 x = getX();
        const s32 y = getY();
        const s32 w = getWidth();
        const s32 textX = x + 20 + kIconSize + 16;
        const s32 right = x + w - 16;

        if (!m_icon.empty()) {
            renderer->drawBitmap(x + 20, y + (kItemHeight - kIconSize) / 2, kIconSize, kIconSize, m_icon.data());
        }

        const std::string value = m_ach.unlocked ? "+" + std::to_string(m_ach.xp) + " XP"
                                                 : std::to_string(m_ach.xp) + " XP";
        const s32 valueW = renderer->getTextDimensions(value, false, 18).first;
        renderer->drawString(value, false, right - valueW, y + 32, 18, m_ach.unlocked ? kGold : kMuted);

        renderer->drawString(m_ach.name, false, textX, y + 32, 21,
                             m_ach.unlocked ? tsl::defaultTextColor : kMuted, right - valueW - 12 - textX);
        renderer->drawString(m_ach.description, false, textX, y + 58, 15, kMuted, right - textX);

        if (m_ach.unlocked) {
            renderer->drawString(m_ach.rarity, false, textX, y + 82, 14, kUnlocked);
        } else if (m_ach.target > 0) {
            const std::string count = std::to_string(m_ach.current) + "/" + std::to_string(m_ach.target);
            const s32 countW = renderer->getTextDimensions(count, false, 14).first;
            const s32 barW = right - textX - countW - 10;
            const s32 filled = barW * std::min(m_ach.current, m_ach.target) / m_ach.target;
            renderer->drawRect(textX, y + 74, barW, 6, kTrack);
            renderer->drawRect(textX, y + 74, filled, 6, kFill);
            renderer->drawString(count, false, right - countW, y + 82, 14, kMuted);
        } else {
            renderer->drawString(m_ach.rarity, false, textX, y + 82, 14, kMuted);
        }
    }

    void layout(u16 parentX, u16 parentY, u16 parentWidth, u16 parentHeight) override {
        setBoundaries(getX() + 3, getY(), getWidth() + 9, kItemHeight);
    }

private:
    Achievement m_ach;
    std::vector<u8> m_icon;
};

class GuiGame : public tsl::Gui {
public:
    explicit GuiGame(std::string gameId) : m_gameId(std::move(gameId)) {}

    tsl::elm::Element* createUI() override {
        JsonDoc doc(std::string(kRoot) + "/progress/" + m_gameId + ".json");
        auto* list = new tsl::elm::List();
        if (!doc.root) {
            list->addItem(new tsl::elm::ListItem("Sem progresso salvo para este jogo"));
            auto* frame = new tsl::elm::OverlayFrame(m_gameId, "Switch Achievements");
            frame->setContent(list);
            return frame;
        }

        std::vector<Achievement> done, locked;
        const cJSON* items = cJSON_GetObjectItemCaseSensitive(doc.root, "achievements");
        const cJSON* item = nullptr;
        cJSON_ArrayForEach(item, items) {
            Achievement ach = parseAchievement(item);
            (ach.unlocked ? done : locked).push_back(std::move(ach));
        }

        const int unlocked = num(doc.root, "unlocked");
        const int total = num(doc.root, "total");
        list->addItem(new tsl::elm::ListItem("Progresso",
            std::to_string(unlocked) + "/" + std::to_string(total) + "  " +
            std::to_string(num(doc.root, "xp")) + "/" + std::to_string(num(doc.root, "xp_total")) + " XP"));

        if (!done.empty()) {
            list->addItem(new tsl::elm::CategoryHeader("Concluídas (" + std::to_string(done.size()) + ")"));
            for (auto& ach : done) list->addItem(new AchievementItem(std::move(ach)), kItemHeight);
        }
        if (!locked.empty()) {
            list->addItem(new tsl::elm::CategoryHeader("Bloqueadas (" + std::to_string(locked.size()) + ")"));
            for (auto& ach : locked) list->addItem(new AchievementItem(std::move(ach)), kItemHeight);
        }

        auto* frame = new tsl::elm::OverlayFrame(str(doc.root, "name"), "Atualizado em " + str(doc.root, "updated_at").substr(0, 10));
        frame->setContent(list);
        return frame;
    }

private:
    std::string m_gameId;
};

class GuiGames : public tsl::Gui {
public:
    tsl::elm::Element* createUI() override {
        JsonDoc doc(std::string(kRoot) + "/profile.json");
        auto* list = new tsl::elm::List();

        if (!doc.root) {
            list->addItem(new tsl::elm::CategoryHeader("Nada sincronizado ainda"));
            list->addItem(new tsl::elm::ListItem("No PC: sa.py device sync"));
            auto* frame = new tsl::elm::OverlayFrame("Switch Achievements", APP_VERSION);
            frame->setContent(list);
            return frame;
        }

        const std::string subtitle = "Nível " + std::to_string(num(doc.root, "level")) + "  " +
            std::to_string(num(doc.root, "xp")) + "/" + std::to_string(num(doc.root, "next_level_xp")) + " XP";
        list->addItem(new tsl::elm::ListItem("Conquistas",
            std::to_string(num(doc.root, "unlocked")) + "/" + std::to_string(num(doc.root, "total"))));

        list->addItem(new tsl::elm::CategoryHeader("Jogos"));
        const cJSON* games = cJSON_GetObjectItemCaseSensitive(doc.root, "games");
        const cJSON* game = nullptr;
        cJSON_ArrayForEach(game, games) {
            const std::string id = str(game, "id");
            auto* row = new tsl::elm::ListItem(str(game, "name"),
                std::to_string(num(game, "unlocked")) + "/" + std::to_string(num(game, "total")));
            row->setClickListener([id](u64 keys) {
                if (keys & KEY_A) {
                    tsl::changeTo<GuiGame>(id);
                    return true;
                }
                return false;
            });
            list->addItem(row);
        }

        auto* frame = new tsl::elm::OverlayFrame("Switch Achievements", subtitle);
        frame->setContent(list);
        return frame;
    }
};

class AchievementsOverlay : public tsl::Overlay {
public:
    std::unique_ptr<tsl::Gui> loadInitialGui() override {
        return std::make_unique<GuiGames>();
    }
};

}  // namespace

int main(int argc, char* argv[]) {
    return tsl::loop<AchievementsOverlay, tsl::impl::LaunchFlags::None>(argc, argv);
}

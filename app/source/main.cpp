// App Conquistas: biblioteca de jogos e conquistas, no estilo da tela inicial.
// Só lê o que o sysmodule publica em sdmc:/config/switch-achievements/ e
// atualiza tudo (app, sysmodule, overlay, pacotes, ícones) pelo GitHub.

#include <switch.h>

#include <SDL2/SDL.h>
#include <curl/curl.h>

#include <algorithm>
#include <cmath>
#include <map>
#include <memory>
#include <string>
#include <vector>

#include "data.hpp"
#include "ui.hpp"
#include "update.hpp"

namespace {

using namespace app;

constexpr int kTop = 88;
constexpr int kBottom = 648;
constexpr int kCardW = 200;
constexpr int kCardGap = 28;
constexpr int kColumns = 5;
constexpr int kCardH = 266;
constexpr int kGridTop = 140;
constexpr int kRowH = 104;
constexpr int kListTop = 212;
constexpr u64 kReloadMs = 3000;

u64 nowMs() { return armTicksToNs(armGetSystemTick()) / 1'000'000ull; }

enum class Screen { Library, Game };
enum class Tab { All, Done, Locked };

class App {
public:
    bool init() {
        if (!m_ui.init()) return false;
        padConfigureInput(1, HidNpadStyleSet_NpadStandard);
        padInitializeDefault(&m_pad);
        hidInitializeTouchScreen();
        reload();
        return true;
    }

    void shutdown() { m_ui.shutdown(); }

    bool frame() {
        padUpdate(&m_pad);
        const u64 down = padGetButtonsDown(&m_pad);
        const u64 held = padGetButtons(&m_pad);
        if (down & HidNpadButton_Plus) return false;
        if (nowMs() - m_lastReload > kReloadMs) reload();
        const u64 nav = repeat(down, held);
        handleTouch();
        if (m_updateOpen) handleUpdate(down);
        else if (m_screen == Screen::Library) handleLibrary(down, nav);
        else handleGame(down, nav);

        m_ui.clear(theme::bg);
        if (m_screen == Screen::Library) drawLibrary();
        else drawGame();
        if (m_updateOpen) drawUpdate();
        m_ui.present();
        return true;
    }

private:
    // ------------------------------------------------------------ dados

    void reload() {
        const std::string selectedId = selectedGame() ? selectedGame()->id : "";
        m_lib = loadLibrary();
        m_running = sysmoduleRunning();
        m_lastReload = nowMs();
        for (size_t i = 0; i < m_lib.games.size(); ++i) {
            if (m_lib.games[i].id == selectedId) m_sel = static_cast<int>(i);
        }
        m_sel = std::clamp(m_sel, 0, std::max(0, static_cast<int>(m_lib.games.size()) - 1));
        clampRow();
    }

    GameData* selectedGame() {
        if (m_sel < 0 || m_sel >= static_cast<int>(m_lib.games.size())) return nullptr;
        return &m_lib.games[m_sel];
    }

    std::vector<const AchievementRow*> visibleRows() {
        std::vector<const AchievementRow*> rows;
        GameData* game = selectedGame();
        if (!game) return rows;
        for (const auto& r : game->rows) {
            if (m_tab == Tab::Done && !r.unlocked) continue;
            if (m_tab == Tab::Locked && r.unlocked) continue;
            rows.push_back(&r);
        }
        if (m_tab == Tab::All) {
            std::stable_sort(rows.begin(), rows.end(), [](const AchievementRow* a, const AchievementRow* b) {
                return a->unlocked > b->unlocked;
            });
        }
        return rows;
    }

    void clampRow() {
        const int count = static_cast<int>(visibleRows().size());
        m_row = std::clamp(m_row, 0, std::max(0, count - 1));
    }

    SDL_Texture* cover(const GameData& game) {
        if (!game.titleId.empty()) {
            const auto it = m_nsTried.find(game.titleId);
            if (it == m_nsTried.end()) {
                m_nsTried[game.titleId] = true;
                auto data = std::make_unique<NsApplicationControlData>();
                u64 size = 0;
                const u64 id = std::strtoull(game.titleId.c_str(), nullptr, 16);
                if (R_SUCCEEDED(nsGetApplicationControlData(NsApplicationControlSource_Storage, id, data.get(), sizeof(*data), &size)) &&
                    size > sizeof(data->nacp)) {
                    m_ui.imageFromMemory("ns:" + game.titleId, data->icon, size - sizeof(data->nacp));
                }
            }
            if (SDL_Texture* tex = m_ui.imageFromMemory("ns:" + game.titleId, nullptr, 0)) return tex;
        }
        if (SDL_Texture* tex = m_ui.image(coverPath(game.id))) return tex;
        return m_ui.image(iconPath("common/trophy"));
    }

    // ------------------------------------------------------------ entrada

    u64 repeat(u64 down, u64 held) {
        constexpr u64 dirs = HidNpadButton_AnyUp | HidNpadButton_AnyDown | HidNpadButton_AnyLeft | HidNpadButton_AnyRight;
        const u64 now = nowMs();
        if (down & dirs) {
            m_repeatAt = now + 400;
            return down;
        }
        if ((held & dirs) && now >= m_repeatAt) {
            m_repeatAt = now + 90;
            return held & dirs;
        }
        return down;
    }

    void handleTouch() {
        HidTouchScreenState state{};
        hidGetTouchScreenStates(&state, 1);
        if (state.count > 0) {
            if (!m_touching) {
                m_touching = true;
                m_touchStartX = m_touchX = static_cast<int>(state.touches[0].x);
                m_touchStartY = m_touchY = static_cast<int>(state.touches[0].y);
            } else {
                m_touchX = static_cast<int>(state.touches[0].x);
                m_touchY = static_cast<int>(state.touches[0].y);
            }
            return;
        }
        if (!m_touching) return;
        m_touching = false;
        if (std::abs(m_touchX - m_touchStartX) > 20 || std::abs(m_touchY - m_touchStartY) > 20) return;
        tap(m_touchX, m_touchY);
    }

    void tap(int x, int y) {
        if (m_updateOpen) return;
        if (m_screen == Screen::Library) {
            for (size_t i = 0; i < m_lib.games.size(); ++i) {
                const SDL_Rect r = cardRect(static_cast<int>(i));
                if (x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h) {
                    if (m_sel == static_cast<int>(i)) openGame();
                    m_sel = static_cast<int>(i);
                }
            }
            return;
        }
        const int count = static_cast<int>(visibleRows().size());
        for (int i = 0; i < count; ++i) {
            const int top = kListTop + i * kRowH - m_listScroll;
            if (y >= top && y < top + kRowH - 8 && y >= kListTop && y < kBottom) m_row = i;
        }
    }

    void openGame() {
        if (!selectedGame()) return;
        m_screen = Screen::Game;
        m_tab = Tab::All;
        m_row = 0;
        m_listScroll = 0;
    }

    void handleLibrary(u64 down, u64 nav) {
        const int count = static_cast<int>(m_lib.games.size());
        if (count > 0) {
            if (nav & HidNpadButton_AnyRight) m_sel = std::min(count - 1, m_sel + 1);
            if (nav & HidNpadButton_AnyLeft) m_sel = std::max(0, m_sel - 1);
            if (nav & HidNpadButton_AnyDown) m_sel = std::min(count - 1, m_sel + kColumns);
            if (nav & HidNpadButton_AnyUp) m_sel = std::max(0, m_sel - kColumns);
        }
        if (down & HidNpadButton_A) openGame();
        if (down & HidNpadButton_Y) {
            m_updateOpen = true;
            m_updater.check();
        }
        if ((down & HidNpadButton_X) && !m_running) {
            restartSysmodule();
            svcSleepThread(500'000'000ull);
            reload();
        }
    }

    void handleGame(u64 down, u64 nav) {
        if (down & HidNpadButton_B) {
            m_screen = Screen::Library;
            return;
        }
        if (down & (HidNpadButton_R | HidNpadButton_ZR)) m_tab = static_cast<Tab>((static_cast<int>(m_tab) + 1) % 3);
        if (down & (HidNpadButton_L | HidNpadButton_ZL)) m_tab = static_cast<Tab>((static_cast<int>(m_tab) + 2) % 3);
        if (down & (HidNpadButton_L | HidNpadButton_R | HidNpadButton_ZL | HidNpadButton_ZR)) {
            m_row = 0;
            m_listScroll = 0;
        }
        if (nav & HidNpadButton_AnyDown) ++m_row;
        if (nav & HidNpadButton_AnyUp) --m_row;
        if (nav & HidNpadButton_AnyRight) m_row += 4;
        if (nav & HidNpadButton_AnyLeft) m_row -= 4;
        clampRow();
    }

    void handleUpdate(u64 down) {
        const Updater::Phase phase = m_updater.phase();
        const bool busy = phase == Updater::Phase::Checking || phase == Updater::Phase::Downloading || phase == Updater::Phase::Installing;
        if ((down & HidNpadButton_A) && phase == Updater::Phase::Available) m_updater.install();
        if ((down & HidNpadButton_B) && !busy) {
            m_updateOpen = false;
            reload();
        }
    }

    // ------------------------------------------------------------ desenho

    SDL_Rect cardRect(int i) const {
        const int x0 = (1280 - (kColumns * kCardW + (kColumns - 1) * kCardGap)) / 2;
        const int col = i % kColumns, row = i / kColumns;
        return SDL_Rect{x0 + col * (kCardW + kCardGap), kGridTop + row * (kCardH + 26) - m_gridScroll, kCardW, kCardH};
    }

    void drawBottom(bool library) {
        m_ui.rect(30, kBottom, 1220, 1, theme::line);
        int x = 1220;
        if (library) {
            m_ui.button("+", "Sair", x, 670);
            m_ui.button("Y", "Atualizar", x, 670);
            if (!m_running) m_ui.button("X", "Iniciar serviço", x, 670);
            m_ui.button("A", "Abrir", x, 670);
            m_ui.circle(70, 684, 8, m_running ? theme::green : Rgba{230, 80, 80});
            m_ui.text(m_running ? "Serviço ativo" : "Serviço parado", 88, 670, 20, theme::muted);
        } else {
            m_ui.button("B", "Voltar", x, 670);
            m_ui.button("R", "Filtro", x, 670);
            m_ui.button("L", "", x, 670);
        }
    }

    void drawLibrary() {
        m_ui.text("Conquistas", 60, 24, 34, theme::text);
        if (m_lib.synced) {
            const std::string level = "Nível " + std::to_string(m_lib.level);
            m_ui.text(level, 1220, 18, 24, theme::text, Align::Right);
            const int prev = m_lib.level > 0 ? static_cast<int>(100 * std::pow(m_lib.level, 1.5)) : 0;
            const float fraction = m_lib.nextLevelXp > prev ? float(m_lib.xp - prev) / float(m_lib.nextLevelXp - prev) : 0.f;
            m_ui.bar(1020, 56, 200, 8, fraction, theme::accent);
            m_ui.text(std::to_string(m_lib.xp) + " / " + std::to_string(m_lib.nextLevelXp) + " XP", 1005, 48, 18, theme::muted, Align::Right);
        }
        m_ui.rect(30, kTop, 1220, 1, theme::line);
        std::string summary = std::to_string(m_lib.unlocked) + " de " + std::to_string(m_lib.total) + " conquistas";
        if (!m_lib.updatedAt.empty()) summary += "  ·  atualizado " + formatDate(m_lib.updatedAt);
        m_ui.text(summary, 60, 100, 20, theme::muted);

        if (m_lib.games.empty()) {
            m_ui.text("Nenhum jogo instalado. Aperte Y para baixar do GitHub.", 640, 340, 26, theme::muted, Align::Center);
            drawBottom(true);
            return;
        }
        const SDL_Rect sel = cardRect(m_sel);
        if (sel.y < kGridTop) m_gridScroll -= kGridTop - sel.y;
        if (sel.y + sel.h > kBottom - 10) m_gridScroll += sel.y + sel.h - (kBottom - 10);
        const SDL_Rect clip{0, kTop + 40, 1280, kBottom - kTop - 40};
        SDL_RenderSetClipRect(m_ui.renderer(), &clip);
        const float pulse = 0.5f + 0.5f * std::sin(nowMs() / 250.0f);
        for (size_t i = 0; i < m_lib.games.size(); ++i) {
            const GameData& g = m_lib.games[i];
            const SDL_Rect r = cardRect(static_cast<int>(i));
            m_ui.rounded(r.x, r.y, r.w, r.h, 8, theme::panel);
            m_ui.draw(cover(g), r.x, r.y, kCardW, kCardW);
            m_ui.text(g.name, r.x + 10, r.y + kCardW + 8, 19, theme::text, Align::Left, kCardW - 20);
            const float fraction = g.total ? float(g.unlocked) / float(g.total) : 0.f;
            m_ui.bar(r.x + 10, r.y + kCardW + 44, kCardW - 80, 8, fraction, g.unlocked == g.total && g.total ? theme::gold : theme::accent);
            m_ui.text(std::to_string(g.unlocked) + "/" + std::to_string(g.total), r.x + kCardW - 10, r.y + kCardW + 36, 18, theme::muted, Align::Right);
            if (static_cast<int>(i) == m_sel) {
                const Rgba glow{theme::accent.r, theme::accent.g, theme::accent.b, static_cast<uint8_t>(160 + 95 * pulse)};
                m_ui.frame(r.x - 2, r.y - 2, r.w + 4, r.h + 4, 10, 4, glow);
            }
        }
        SDL_RenderSetClipRect(m_ui.renderer(), nullptr);
        drawBottom(true);
    }

    void drawGame() {
        GameData* game = selectedGame();
        if (!game) {
            m_screen = Screen::Library;
            return;
        }
        m_ui.draw(cover(*game), 60, 14, 60, 60);
        m_ui.text(game->name, 136, 24, 30, theme::text, Align::Left, 760);
        m_ui.text(std::to_string(game->unlocked) + "/" + std::to_string(game->total) + "  ·  " + std::to_string(game->xp) + "/" +
                      std::to_string(game->xpTotal) + " XP",
                  1220, 30, 22, theme::muted, Align::Right);
        m_ui.rect(30, kTop, 1220, 1, theme::line);
        const float fraction = game->total ? float(game->unlocked) / float(game->total) : 0.f;
        m_ui.bar(60, 108, 1160, 10, fraction, theme::accent);

        const int done = game->unlocked;
        const char* labels[] = {"Todas", "Concluídas", "Bloqueadas"};
        const int counts[] = {game->total, done, game->total - done};
        int x = 60;
        for (int t = 0; t < 3; ++t) {
            const std::string label = std::string(labels[t]) + " (" + std::to_string(counts[t]) + ")";
            const bool active = static_cast<int>(m_tab) == t;
            const int w = m_ui.text(label, x, 140, 24, active ? theme::text : theme::muted);
            if (active) m_ui.rect(x, 176, w, 4, theme::accent);
            x += w + 48;
        }
        if (m_lib.detected.present && m_lib.detected.game == game->id && !m_lib.detected.supported && !m_lib.detected.buildId.empty()) {
            m_ui.text("Versão do jogo (build " + m_lib.detected.buildId + ") ainda sem suporte", 1220, 146, 18, theme::gold, Align::Right);
        }

        const auto rows = visibleRows();
        const int selTop = kListTop + m_row * kRowH;
        if (selTop - m_listScroll < kListTop) m_listScroll = selTop - kListTop;
        if (selTop + kRowH - m_listScroll > kBottom - 4) m_listScroll = selTop + kRowH - (kBottom - 4);
        const SDL_Rect clip{0, kListTop - 6, 1280, kBottom - kListTop + 2};
        SDL_RenderSetClipRect(m_ui.renderer(), &clip);
        for (int i = 0; i < static_cast<int>(rows.size()); ++i) {
            const int y = kListTop + i * kRowH - m_listScroll;
            if (y + kRowH < kListTop - 6 || y > kBottom) continue;
            drawRow(*rows[i], y, i == m_row);
        }
        if (rows.empty()) m_ui.text("Nada aqui ainda.", 640, 380, 24, theme::muted, Align::Center);
        SDL_RenderSetClipRect(m_ui.renderer(), nullptr);
        drawBottom(false);
    }

    void drawRow(const AchievementRow& r, int y, bool selected) {
        m_ui.rounded(60, y, 1160, kRowH - 8, 8, selected ? theme::panelHi : theme::panel);
        m_ui.draw(m_ui.image(iconPath(r.icon), !r.unlocked), 76, y + 12, 72, 72, r.unlocked ? 255 : 150);
        const Rgba nameColor = r.unlocked ? theme::text : theme::muted;
        m_ui.text(r.name, 168, y + 12, 24, nameColor, Align::Left, 780);
        m_ui.text(r.description, 168, y + 44, 18, theme::muted, Align::Left, 840);
        m_ui.text((r.unlocked ? "+" : "") + std::to_string(r.xp) + " XP", 1196, y + 12, 22, r.unlocked ? theme::gold : theme::muted, Align::Right);
        m_ui.text(r.rarity, 1196, y + 44, 18, theme::muted, Align::Right);
        if (r.unlocked) {
            m_ui.text("Desbloqueada em " + formatDate(r.unlockedAt), 168, y + 70, 16, theme::green);
        } else if (r.status == "pending" || r.status == "unsupported") {
            m_ui.text("Ainda não rastreada nesta versão", 168, y + 70, 16, theme::muted);
        } else if (r.hasProgress && r.target > 0) {
            m_ui.bar(168, y + 76, 680, 8, float(r.current) / float(r.target), theme::accent);
            m_ui.text(std::to_string(r.current) + "/" + std::to_string(r.target), 864, y + 68, 16, theme::muted);
        } else if (r.status == "rehearsal") {
            m_ui.text("Em teste: ainda não desbloqueia", 168, y + 70, 16, theme::muted);
        }
        if (selected) m_ui.frame(58, y - 2, 1164, kRowH - 4, 10, 3, theme::accent);
    }

    void drawUpdate() {
        m_ui.rect(0, 0, 1280, 720, Rgba{0, 0, 0, 170});
        m_ui.rounded(290, 200, 700, 320, 12, theme::panel);
        m_ui.text("Atualização", 330, 230, 30, theme::text);
        m_ui.text("Instalada: " + installedVersion(), 950, 238, 20, theme::muted, Align::Right);
        m_ui.text(m_updater.message(), 330, 300, 22, theme::text, Align::Left, 620);
        const Updater::Phase phase = m_updater.phase();
        if (phase == Updater::Phase::Downloading || phase == Updater::Phase::Installing) {
            m_ui.bar(330, 360, 620, 12, m_updater.progress(), theme::accent);
        }
        int x = 950;
        if (phase != Updater::Phase::Checking && phase != Updater::Phase::Downloading && phase != Updater::Phase::Installing) {
            m_ui.button("B", "Fechar", x, 460);
        }
        if (phase == Updater::Phase::Available) m_ui.button("A", "Instalar", x, 460);
    }

    Ui m_ui;
    PadState m_pad{};
    Library m_lib;
    Updater m_updater;
    Screen m_screen = Screen::Library;
    Tab m_tab = Tab::All;
    std::map<std::string, bool> m_nsTried;
    int m_sel = 0, m_row = 0, m_gridScroll = 0, m_listScroll = 0;
    bool m_running = false, m_updateOpen = false, m_touching = false;
    int m_touchStartX = 0, m_touchStartY = 0, m_touchX = 0, m_touchY = 0;
    u64 m_lastReload = 0, m_repeatAt = 0;
};

}  // namespace

int main(int argc, char* argv[]) {
    romfsInit();
    socketInitializeDefault();
    curl_global_init(CURL_GLOBAL_DEFAULT);
    plInitialize(PlServiceType_User);
    nsInitialize();
    pmdmntInitialize();
    {
        App app;
        if (app.init()) {
            while (appletMainLoop() && app.frame()) {}
        }
        app.shutdown();
    }
    pmdmntExit();
    nsExit();
    plExit();
    curl_global_cleanup();
    socketExit();
    romfsExit();
    return 0;
}

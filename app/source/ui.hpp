#pragma once

#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>

#include <cstdint>
#include <map>
#include <string>
#include <tuple>
#include <vector>

namespace app {

struct Rgba {
    uint8_t r, g, b, a = 255;
};

namespace theme {
constexpr Rgba bg{45, 45, 45};
constexpr Rgba panel{60, 60, 60};
constexpr Rgba panelHi{72, 72, 72};
constexpr Rgba line{90, 90, 90};
constexpr Rgba text{255, 255, 255};
constexpr Rgba muted{170, 170, 170};
constexpr Rgba accent{0, 195, 227};
constexpr Rgba gold{255, 196, 54};
constexpr Rgba green{90, 214, 120};
constexpr Rgba track{30, 30, 30};
}  // namespace theme

enum class Align { Left, Center, Right };

class Ui {
public:
    bool init();
    void shutdown();
    SDL_Renderer* renderer() const { return m_renderer; }

    void clear(Rgba c);
    void present();
    void rect(int x, int y, int w, int h, Rgba c);
    void rounded(int x, int y, int w, int h, int radius, Rgba c);
    void frame(int x, int y, int w, int h, int radius, int thickness, Rgba c);
    void circle(int cx, int cy, int r, Rgba c);
    int text(const std::string& s, int x, int y, int size, Rgba c, Align align = Align::Left, int maxWidth = 0);
    int textWidth(const std::string& s, int size);
    void bar(int x, int y, int w, int h, float fraction, Rgba fill);
    void button(const char* letter, const std::string& label, int& x, int y);

    // Imagens: arquivo no SD ou JPEG em memória (ícone de jogo do sistema).
    SDL_Texture* image(const std::string& path, bool gray = false);
    SDL_Texture* imageFromMemory(const std::string& key, const void* data, size_t size);
    void draw(SDL_Texture* tex, int x, int y, int w, int h, uint8_t alpha = 255);

private:
    TTF_Font* font(int size);
    SDL_Texture* textTexture(const std::string& s, int size, Rgba c, int& w, int& h);

    SDL_Window* m_window = nullptr;
    SDL_Renderer* m_renderer = nullptr;
    std::vector<uint8_t> m_fontData;
    std::map<int, TTF_Font*> m_fonts;
    struct TextEntry {
        SDL_Texture* tex;
        int w, h;
    };
    std::map<std::tuple<std::string, int, uint32_t>, TextEntry> m_textCache;
    std::map<std::string, SDL_Texture*> m_images;
};

}  // namespace app

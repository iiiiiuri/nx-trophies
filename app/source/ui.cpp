#include "ui.hpp"

#include <switch.h>

#include <SDL2/SDL2_gfxPrimitives.h>
#include <SDL2/SDL_image.h>

#include <cstring>

namespace app {

bool Ui::init() {
    if (SDL_Init(SDL_INIT_VIDEO) != 0) return false;
    m_window = SDL_CreateWindow("Conquistas", 0, 0, 1280, 720, 0);
    if (!m_window) return false;
    m_renderer = SDL_CreateRenderer(m_window, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
    if (!m_renderer) return false;
    SDL_SetRenderDrawBlendMode(m_renderer, SDL_BLENDMODE_BLEND);
    IMG_Init(IMG_INIT_PNG | IMG_INIT_JPG);
    if (TTF_Init() != 0) return false;
    PlFontData standard;
    if (R_FAILED(plGetSharedFontByType(&standard, PlSharedFontType_Standard))) return false;
    m_fontData.assign(static_cast<const uint8_t*>(standard.address), static_cast<const uint8_t*>(standard.address) + standard.size);
    return true;
}

void Ui::shutdown() {
    for (auto& [key, entry] : m_textCache) SDL_DestroyTexture(entry.tex);
    for (auto& [key, tex] : m_images) {
        if (tex) SDL_DestroyTexture(tex);
    }
    for (auto& [size, f] : m_fonts) TTF_CloseFont(f);
    TTF_Quit();
    IMG_Quit();
    if (m_renderer) SDL_DestroyRenderer(m_renderer);
    if (m_window) SDL_DestroyWindow(m_window);
    SDL_Quit();
}

void Ui::clear(Rgba c) {
    SDL_SetRenderDrawColor(m_renderer, c.r, c.g, c.b, c.a);
    SDL_RenderClear(m_renderer);
}

void Ui::present() {
    SDL_RenderPresent(m_renderer);
    if (m_textCache.size() > 600) {
        for (auto& [key, entry] : m_textCache) SDL_DestroyTexture(entry.tex);
        m_textCache.clear();
    }
}

void Ui::rect(int x, int y, int w, int h, Rgba c) {
    SDL_SetRenderDrawColor(m_renderer, c.r, c.g, c.b, c.a);
    const SDL_Rect r{x, y, w, h};
    SDL_RenderFillRect(m_renderer, &r);
}

void Ui::rounded(int x, int y, int w, int h, int radius, Rgba c) {
    roundedBoxRGBA(m_renderer, x, y, x + w - 1, y + h - 1, radius, c.r, c.g, c.b, c.a);
}

void Ui::frame(int x, int y, int w, int h, int radius, int thickness, Rgba c) {
    for (int i = 0; i < thickness; ++i) {
        roundedRectangleRGBA(m_renderer, x - i, y - i, x + w - 1 + i, y + h - 1 + i, radius + i, c.r, c.g, c.b, c.a);
    }
}

void Ui::circle(int cx, int cy, int r, Rgba c) { filledCircleRGBA(m_renderer, cx, cy, r, c.r, c.g, c.b, c.a); }

TTF_Font* Ui::font(int size) {
    auto it = m_fonts.find(size);
    if (it != m_fonts.end()) return it->second;
    SDL_RWops* rw = SDL_RWFromConstMem(m_fontData.data(), static_cast<int>(m_fontData.size()));
    TTF_Font* f = TTF_OpenFontRW(rw, 1, size);
    m_fonts[size] = f;
    return f;
}

int Ui::textWidth(const std::string& s, int size) {
    int w = 0, h = 0;
    if (TTF_Font* f = font(size)) TTF_SizeUTF8(f, s.c_str(), &w, &h);
    return w;
}

SDL_Texture* Ui::textTexture(const std::string& s, int size, Rgba c, int& w, int& h) {
    const uint32_t color = (c.r << 24) | (c.g << 16) | (c.b << 8) | c.a;
    const auto key = std::make_tuple(s, size, color);
    const auto it = m_textCache.find(key);
    if (it != m_textCache.end()) {
        w = it->second.w;
        h = it->second.h;
        return it->second.tex;
    }
    TTF_Font* f = font(size);
    if (!f) return nullptr;
    SDL_Surface* surface = TTF_RenderUTF8_Blended(f, s.c_str(), SDL_Color{c.r, c.g, c.b, c.a});
    if (!surface) return nullptr;
    SDL_Texture* tex = SDL_CreateTextureFromSurface(m_renderer, surface);
    w = surface->w;
    h = surface->h;
    SDL_FreeSurface(surface);
    m_textCache[key] = {tex, w, h};
    return tex;
}

namespace {

// corta no limite de um caractere UTF-8
std::string utf8Prefix(const std::string& s, size_t bytes) {
    while (bytes > 0 && bytes < s.size() && (static_cast<uint8_t>(s[bytes]) & 0xC0) == 0x80) --bytes;
    return s.substr(0, bytes);
}

}  // namespace

int Ui::text(const std::string& s, int x, int y, int size, Rgba c, Align align, int maxWidth) {
    if (s.empty()) return 0;
    std::string shown = s;
    if (maxWidth > 0 && textWidth(shown, size) > maxWidth) {
        size_t lo = 0, hi = s.size();
        while (lo < hi) {
            const size_t mid = (lo + hi + 1) / 2;
            if (textWidth(utf8Prefix(s, mid) + "…", size) <= maxWidth) lo = mid;
            else hi = mid - 1;
        }
        shown = utf8Prefix(s, lo) + "…";
    }
    int w = 0, h = 0;
    SDL_Texture* tex = textTexture(shown, size, c, w, h);
    if (!tex) return 0;
    const int left = align == Align::Left ? x : align == Align::Center ? x - w / 2 : x - w;
    const SDL_Rect dst{left, y, w, h};
    SDL_RenderCopy(m_renderer, tex, nullptr, &dst);
    return w;
}

void Ui::bar(int x, int y, int w, int h, float fraction, Rgba fill) {
    rounded(x, y, w, h, h / 2, theme::track);
    const int filled = static_cast<int>(w * (fraction < 0 ? 0 : fraction > 1 ? 1 : fraction));
    if (filled >= h) rounded(x, y, filled, h, h / 2, fill);
    else if (filled > 0) rect(x, y, filled, h, fill);
}

void Ui::button(const char* letter, const std::string& label, int& x, int y) {
    const int w = textWidth(label, 22);
    x -= w;
    text(label, x, y, 22, theme::text);
    x -= 22;
    circle(x, y + 14, 15, theme::text);
    text(letter, x, y + 2, 20, theme::bg, Align::Center);
    x -= 40;
}

SDL_Texture* Ui::image(const std::string& path, bool gray) {
    const std::string key = path + (gray ? "#gray" : "");
    const auto it = m_images.find(key);
    if (it != m_images.end()) return it->second;
    SDL_Texture* tex = nullptr;
    if (SDL_Surface* loaded = IMG_Load(path.c_str())) {
        SDL_Surface* rgba = SDL_ConvertSurfaceFormat(loaded, SDL_PIXELFORMAT_ABGR8888, 0);
        SDL_FreeSurface(loaded);
        if (rgba) {
            if (gray) {
                SDL_LockSurface(rgba);
                for (int y = 0; y < rgba->h; ++y) {
                    auto* row = static_cast<uint8_t*>(rgba->pixels) + y * rgba->pitch;
                    for (int x = 0; x < rgba->w; ++x) {
                        uint8_t* p = row + 4 * x;
                        const uint8_t l = static_cast<uint8_t>((p[0] * 30 + p[1] * 59 + p[2] * 11) / 140);
                        p[0] = p[1] = p[2] = l;
                    }
                }
                SDL_UnlockSurface(rgba);
            }
            tex = SDL_CreateTextureFromSurface(m_renderer, rgba);
            SDL_FreeSurface(rgba);
        }
    }
    m_images[key] = tex;
    return tex;
}

SDL_Texture* Ui::imageFromMemory(const std::string& key, const void* data, size_t size) {
    const auto it = m_images.find(key);
    if (it != m_images.end()) return it->second;
    SDL_Texture* tex = nullptr;
    if (SDL_Surface* loaded = IMG_Load_RW(SDL_RWFromConstMem(data, static_cast<int>(size)), 1)) {
        tex = SDL_CreateTextureFromSurface(m_renderer, loaded);
        SDL_FreeSurface(loaded);
    }
    m_images[key] = tex;
    return tex;
}

void Ui::draw(SDL_Texture* tex, int x, int y, int w, int h, uint8_t alpha) {
    if (!tex) return;
    SDL_SetTextureAlphaMod(tex, alpha);
    const SDL_Rect dst{x, y, w, h};
    SDL_RenderCopy(m_renderer, tex, nullptr, &dst);
}

}  // namespace app

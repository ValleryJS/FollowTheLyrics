#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>

#include <reshade.hpp>

#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <thread>

#pragma comment(lib, "ws2_32.lib")

namespace {
constexpr unsigned short kInputPort = 48790;
constexpr unsigned short kAckPort = 48791;
constexpr size_t kCharCount = 64;
constexpr size_t kPacketSize = 12 + kCharCount * 4;

SOCKET g_socket = INVALID_SOCKET;
std::atomic<bool> g_running{false};
std::thread g_receiver;
std::mutex g_mutex;
std::array<int32_t, kCharCount> g_glyphs{};
int32_t g_count = 0;
std::chrono::steady_clock::time_point g_lastPacket{};
std::chrono::steady_clock::time_point g_lastAck{};

void receive_frames() {
    std::array<uint8_t, kPacketSize> bytes{};
    while (g_running) {
        sockaddr_in peer{};
        int peerSize = sizeof(peer);
        const int received = recvfrom(g_socket, reinterpret_cast<char *>(bytes.data()),
            static_cast<int>(bytes.size()), 0, reinterpret_cast<sockaddr *>(&peer), &peerSize);
        if (received != static_cast<int>(kPacketSize) ||
            ntohl(peer.sin_addr.s_addr) != INADDR_LOOPBACK ||
            std::memcmp(bytes.data(), "FTL1", 4) != 0)
            continue;

        uint32_t count = 0;
        std::memcpy(&count, bytes.data() + 8, sizeof(count));
        if (count > kCharCount)
            continue;
        std::array<int32_t, kCharCount> codes{};
        std::memcpy(codes.data(), bytes.data() + 12, sizeof(codes));
        std::lock_guard<std::mutex> lock(g_mutex);
        g_glyphs = codes;
        g_count = static_cast<int32_t>(count);
        g_lastPacket = std::chrono::steady_clock::now();
    }
}

void on_begin_effects(reshade::api::effect_runtime *runtime,
    reshade::api::command_list *, reshade::api::resource_view,
    reshade::api::resource_view) {
    const auto technique = runtime->find_technique("FTL_Live.fx", "FTL_Live");
    if (technique.handle == 0 || !runtime->get_technique_state(technique))
        return;
    const auto codes = runtime->find_uniform_variable("FTL_Live.fx", "FTL_Codes");
    const auto count = runtime->find_uniform_variable("FTL_Live.fx", "FTL_Count");
    if (codes.handle == 0 || count.handle == 0)
        return;

    std::array<int32_t, kCharCount> snapshot{};
    int32_t length = 0;
    bool fresh = false;
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        fresh = std::chrono::steady_clock::now() - g_lastPacket <= std::chrono::seconds(1);
        if (fresh) {
            snapshot = g_glyphs;
            length = g_count;
        }
    }

    runtime->set_uniform_value_int(codes, snapshot.data(), snapshot.size());
    runtime->set_uniform_value_int(count, &length, 1);

    const auto now = std::chrono::steady_clock::now();
    if (fresh && now - g_lastAck >= std::chrono::milliseconds(400) && g_socket != INVALID_SOCKET) {
        sockaddr_in ack{};
        ack.sin_family = AF_INET;
        ack.sin_port = htons(kAckPort);
        ack.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        const char message[] = "FTL_READY";
        sendto(g_socket, message, sizeof(message) - 1, 0,
            reinterpret_cast<const sockaddr *>(&ack), sizeof(ack));
        g_lastAck = now;
    }
}
}

extern "C" __declspec(dllexport) bool AddonInit(HMODULE, HMODULE) {
    WSADATA state{};
    if (WSAStartup(MAKEWORD(2, 2), &state) != 0)
        return false;
    g_socket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (g_socket == INVALID_SOCKET) {
        WSACleanup();
        return false;
    }
    DWORD timeoutMs = 200;
    setsockopt(g_socket, SOL_SOCKET, SO_RCVTIMEO,
        reinterpret_cast<const char *>(&timeoutMs), sizeof(timeoutMs));
    sockaddr_in local{};
    local.sin_family = AF_INET;
    local.sin_port = htons(kInputPort);
    local.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (bind(g_socket, reinterpret_cast<const sockaddr *>(&local), sizeof(local)) != 0) {
        closesocket(g_socket);
        g_socket = INVALID_SOCKET;
        WSACleanup();
        return false;
    }
    g_running = true;
    g_receiver = std::thread(receive_frames);
    return true;
}

extern "C" __declspec(dllexport) void AddonUninit(HMODULE, HMODULE) {
    g_running = false;
    if (g_receiver.joinable())
        g_receiver.join();
    if (g_socket != INVALID_SOCKET)
        closesocket(g_socket);
    g_socket = INVALID_SOCKET;
    WSACleanup();
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        if (!reshade::register_addon(instance))
            return FALSE;
        reshade::register_event<reshade::addon_event::reshade_begin_effects>(&on_begin_effects);
    } else if (reason == DLL_PROCESS_DETACH) {
        reshade::unregister_event<reshade::addon_event::reshade_begin_effects>(&on_begin_effects);
        reshade::unregister_addon(instance);
    }
    return TRUE;
}

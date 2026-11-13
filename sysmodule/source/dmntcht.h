// Cliente mínimo do serviço dmnt:cht do Atmosphère (só leitura).
// Comandos e estruturas: stratosphere/dmnt/source/cheat/dmnt_cheat_service.hpp.
#pragma once

#include <switch.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    u64 base;
    u64 size;
} DmntMemoryRegionExtents;

typedef struct {
    u64 process_id;
    u64 title_id;
    DmntMemoryRegionExtents main_nso_extents;
    DmntMemoryRegionExtents heap_extents;
    DmntMemoryRegionExtents alias_extents;
    DmntMemoryRegionExtents address_space_extents;
    u8 main_nso_build_id[0x20];
} DmntCheatProcessMetadata;

Result dmntchtInitialize(void);
void dmntchtExit(void);
Result dmntchtHasCheatProcess(bool* out);
Result dmntchtForceOpenCheatProcess(void);
Result dmntchtGetCheatProcessMetadata(DmntCheatProcessMetadata* out);
Result dmntchtReadCheatProcessMemory(u64 address, void* buffer, size_t size);

#ifdef __cplusplus
}
#endif

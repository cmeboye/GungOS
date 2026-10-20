/*
 * Host tests for the FAT32 driver: fat32.c runs against an SD card held in
 * memory, formatted here, and every test ends with a structural check of the
 * card (the parts of fsck the driver can break). Block traffic is counted, so
 * the tests also hold the driver to its read budgets.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "sdcard.h"
#include "fat32.h"

static int failures = 0, checks = 0;

#define CHECK(cond)                                                    \
    do                                                                 \
    {                                                                  \
        checks++;                                                      \
        if (!(cond))                                                   \
        {                                                              \
            failures++;                                                \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);     \
        }                                                              \
    } while (0)

/* ---- the card ------------------------------------------------------------ */

static uint8_t *card;
static uint32_t card_blocks;
static unsigned long block_reads, block_writes;

sd_error_t sd_card_init(void) { return card ? SD_OK : SD_ERROR_NO_CARD; }
bool sd_card_present(void) { return card != NULL; }
void sd_init(void) {}
bool sd_is_sdhc(void) { return true; }

sd_error_t sd_read_blocks(uint32_t start, uint32_t count, uint8_t *buffer)
{
    if (!card || start + count > card_blocks)
        return SD_ERROR_READ_FAILED;
    memcpy(buffer, card + (size_t)start * SD_BLOCK_SIZE, (size_t)count * SD_BLOCK_SIZE);
    block_reads += count;
    return SD_OK;
}

sd_error_t sd_read_block(uint32_t block, uint8_t *buffer) { return sd_read_blocks(block, 1, buffer); }

sd_error_t sd_write_blocks(uint32_t start, uint32_t count, const uint8_t *buffer)
{
    if (!card || start + count > card_blocks)
        return SD_ERROR_WRITE_FAILED;
    memcpy(card + (size_t)start * SD_BLOCK_SIZE, buffer, (size_t)count * SD_BLOCK_SIZE);
    block_writes += count;
    return SD_OK;
}

sd_error_t sd_write_block(uint32_t block, const uint8_t *buffer) { return sd_write_blocks(block, 1, buffer); }

static uint8_t *sector(uint32_t n) { return card + (size_t)n * SD_BLOCK_SIZE; }

static uint32_t le32(const uint8_t *p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }

static void put32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)v, p[1] = (uint8_t)(v >> 8), p[2] = (uint8_t)(v >> 16), p[3] = (uint8_t)(v >> 24);
}

/* A fresh FAT32 volume (no partition table) on a new card. */
static uint8_t *format_card(uint32_t blocks, uint8_t sectors_per_cluster)
{
    uint8_t *image = calloc(blocks, SD_BLOCK_SIZE);
    const uint32_t reserved = 32;
    uint32_t fat_size = 1, clusters = 0;
    for (int pass = 0; pass < 4; pass++)
    {
        clusters = (blocks - reserved - 2 * fat_size) / sectors_per_cluster;
        fat_size = ((clusters + 2) * 4 + SD_BLOCK_SIZE - 1) / SD_BLOCK_SIZE;
    }
    fat32_boot_sector_t bs = {{0xEB, 0x58, 0x90}, {0}, SD_BLOCK_SIZE, sectors_per_cluster,
                              reserved, 2, 0, 0, 0xF8, 0, 32, 64, 0, blocks, fat_size, 0, 0, 2, 1, 6,
                              {0}, 0x80, 0, 0x29, 0x1234, {0}, {0}};
    memcpy(bs.oem_name, "GUNGTEST", 8);
    memcpy(bs.volume_label, "GUNGTEST   ", 11);
    memcpy(bs.file_system_type, "FAT32   ", 8);
    memcpy(image, &bs, sizeof(bs));
    image[510] = 0x55, image[511] = 0xAA;
    uint8_t *info = image + SD_BLOCK_SIZE;
    put32(info, 0x41615252);
    put32(info + 484, 0x61417272);
    put32(info + 488, clusters - 1); /* the root directory holds cluster 2 */
    put32(info + 492, 3);
    put32(info + 508, 0xAA550000);
    for (int fat = 0; fat < 2; fat++)
    {
        uint8_t *entries = image + (size_t)(reserved + fat * fat_size) * SD_BLOCK_SIZE;
        put32(entries, 0x0FFFFFF8);
        put32(entries + 4, 0x0FFFFFFF);
        put32(entries + 8, 0x0FFFFFFF);
    }
    return image;
}

static void insert_card(uint8_t *image, uint32_t blocks)
{
    card = image;
    card_blocks = blocks;
}

/* ---- structural check ---------------------------------------------------- */

static struct
{
    uint32_t reserved, fat_size, first_data, clusters, spc, bpc;
    uint8_t *used;
    int problems;
} vol;

static uint32_t fat_entry(uint32_t cluster)
{
    return le32(sector(vol.reserved) + cluster * 4) & 0x0FFFFFFF;
}

static void problem(const char *what, const char *where)
{
    if (vol.problems++ < 10)
        printf("  card problem: %s (%s)\n", what, where);
}

/* Follow a chain, claiming each cluster once; returns its length. */
static uint32_t claim_chain(uint32_t cluster, const char *where)
{
    uint32_t length = 0;
    while (cluster >= 2 && cluster < 0x0FFFFFF8)
    {
        if (cluster >= vol.clusters + 2 || vol.used[cluster])
        {
            problem("cross-linked or out-of-range cluster", where);
            return length;
        }
        vol.used[cluster] = 1;
        length++;
        const uint32_t next = fat_entry(cluster);
        if (next == 0)
        {
            problem("chain runs into a free cluster", where);
            return length;
        }
        cluster = next;
    }
    return length;
}

static uint8_t short_checksum(const uint8_t *name)
{
    uint8_t sum = 0;
    for (int i = 0; i < 11; i++)
        sum = (uint8_t)(((sum & 1) << 7) + (sum >> 1) + name[i]);
    return sum;
}

static void check_directory(uint32_t start, uint32_t parent, const char *path)
{
    uint32_t chain[4096], length = 0;
    for (uint32_t c = start; c >= 2 && c < 0x0FFFFFF8 && length < 4096; c = fat_entry(c))
        chain[length++] = c;
    if (claim_chain(start, path) != length)
        return;
    int lfn_left = 0, slot = 0; /* parts still due; a complete name waits in lfn_done */
    bool lfn_done = false;
    uint8_t lfn_sum = 0;
    for (uint32_t i = 0; i < length; i++)
        for (uint32_t s = 0; s < vol.spc; s++)
            for (int off = 0; off < SD_BLOCK_SIZE; off += 32, slot++)
            {
                const uint8_t *e = sector(vol.first_data + (chain[i] - 2) * vol.spc + s) + off;
                if (e[0] == 0x00)
                {
                    if (lfn_left || lfn_done)
                        problem("long name without its entry", path);
                    return;
                }
                if (e[0] == 0xE5)
                {
                    if (lfn_left || lfn_done)
                        problem("long name broken by a free slot", path);
                    lfn_left = 0, lfn_done = false;
                    continue;
                }
                if (e[11] == 0x0F)
                {
                    if (e[0] & 0x40)
                    {
                        if (lfn_left || lfn_done)
                            problem("long name restarted", path);
                        lfn_left = e[0] & 0x3F;
                        lfn_sum = e[13];
                    }
                    else if (!lfn_left || e[0] != lfn_left || e[13] != lfn_sum)
                        problem("long name parts out of order", path);
                    lfn_left--;
                    lfn_done = lfn_left == 0;
                    continue;
                }
                if (lfn_left || (lfn_done && short_checksum(e) != lfn_sum))
                    problem("long name does not match its entry", path);
                lfn_left = 0, lfn_done = false;
                const uint32_t cluster = (uint32_t)(e[20] | e[21] << 8) << 16 | (e[26] | e[27] << 8);
                if (start != 2 && slot == 0)
                {
                    if (memcmp(e, ".          ", 11) != 0 || cluster != start)
                        problem("'.' entry lost", path);
                    continue;
                }
                if (start != 2 && slot == 1)
                {
                    if (memcmp(e, "..         ", 11) != 0 || cluster != (parent == 2 ? 0 : parent))
                        problem("'..' entry lost", path);
                    continue;
                }
                if (e[11] & 0x08)
                    continue; /* volume label */
                char name[16];
                snprintf(name, sizeof(name), "%.11s", (const char *)e);
                if (e[11] & 0x10)
                    check_directory(cluster, start, name);
                else
                {
                    /* The driver gives every new file one cluster. */
                    const uint32_t size = le32(e + 28);
                    const uint32_t needed = size ? (size + vol.bpc - 1) / vol.bpc : 1;
                    if (claim_chain(cluster, name) != needed)
                        problem("file size and cluster chain disagree", name);
                }
            }
}

/* The checks fsck makes that the driver can affect. Returns the problems. */
static int check_card(void)
{
    const fat32_boot_sector_t *bs = (const fat32_boot_sector_t *)card;
    vol.reserved = bs->reserved_sectors;
    vol.fat_size = bs->fat_size_32;
    vol.spc = bs->sectors_per_cluster;
    vol.bpc = vol.spc * SD_BLOCK_SIZE;
    vol.first_data = vol.reserved + bs->num_fats * vol.fat_size;
    vol.clusters = (bs->total_sectors_32 - vol.first_data) / vol.spc;
    vol.used = calloc(vol.clusters + 2, 1);
    vol.problems = 0;
    check_directory(bs->root_cluster, 0, "/");
    uint32_t free_count = 0;
    for (uint32_t c = 2; c < vol.clusters + 2; c++)
    {
        const uint32_t entry = fat_entry(c);
        free_count += entry == 0;
        if (entry != 0 && !vol.used[c])
            problem("lost cluster", "FAT");
    }
    if (le32(sector(bs->fat32_info) + 488) != free_count)
        problem("FSInfo free count is wrong", "FSInfo");
    free(vol.used);
    return vol.problems;
}

/* ---- helpers ------------------------------------------------------------- */

/* Content of file `id` at byte `pos`, so every read can be verified. */
static uint8_t byte_at(int id, uint32_t pos)
{
    uint32_t x = (uint32_t)id * 2654435761u ^ pos * 40503u;
    x ^= x >> 13;
    x *= 0x5bd1e995u;
    return (uint8_t)(x ^ (x >> 15));
}

static bool write_file(const char *path, int id, uint32_t size, uint32_t chunk)
{
    fat32_file_t f;
    if (fat32_create(&f, path) != FAT32_OK)
        return false;
    uint8_t *buf = malloc(chunk);
    bool ok = true;
    for (uint32_t pos = 0; pos < size && ok;)
    {
        const uint32_t n = size - pos < chunk ? size - pos : chunk;
        for (uint32_t i = 0; i < n; i++)
            buf[i] = byte_at(id, pos + i);
        size_t done = 0;
        ok = fat32_write(&f, buf, n, &done) == FAT32_OK && done == n;
        pos += n;
    }
    fat32_close(&f);
    free(buf);
    return ok;
}

/* Read `len` bytes from `from` in `chunk` pieces; the number of bytes wrong,
 * or -1 if the file did not give exactly the bytes it holds. */
static long read_check(const char *path, int id, uint32_t from, uint32_t len, uint32_t chunk)
{
    fat32_file_t f;
    if (fat32_open(&f, path) != FAT32_OK)
        return -1;
    const uint32_t size = fat32_size(&f);
    const uint32_t expect = from >= size ? 0 : (size - from < len ? size - from : len);
    fat32_seek(&f, from);
    uint8_t *buf = malloc(chunk);
    long bad = 0;
    uint32_t got_total = 0;
    while (got_total < len)
    {
        size_t got = 0;
        const uint32_t want = len - got_total < chunk ? len - got_total : chunk;
        if (fat32_read(&f, buf, want, &got) != FAT32_OK || got == 0)
            break;
        for (size_t i = 0; i < got; i++)
            bad += buf[i] != byte_at(id, from + got_total + (uint32_t)i);
        got_total += (uint32_t)got;
    }
    fat32_close(&f);
    free(buf);
    return got_total == expect ? bad : -1;
}

static int count_entries(const char *path, size_t *longest)
{
    fat32_file_t d;
    if (fat32_open(&d, path) != FAT32_OK)
        return -1;
    fat32_entry_t e;
    int n = 0;
    while (fat32_dir_read(&d, &e) == FAT32_OK && e.filename[0])
    {
        if (strcmp(e.filename, ".") != 0 && strcmp(e.filename, "..") != 0)
            n++;
        if (longest && strlen(e.filename) > *longest)
            *longest = strlen(e.filename);
    }
    fat32_close(&d);
    return n;
}

static void mkdir_path(const char *path)
{
    fat32_file_t d;
    CHECK(fat32_dir_create(&d, path) == FAT32_OK);
    fat32_close(&d);
}

/* ---- tests --------------------------------------------------------------- */

/* Entries whose slots cross a cluster boundary used to wrap to the start of
 * the cluster, overwriting '.', '..' or other files. */
static void test_entries_across_clusters(void)
{
    mkdir_path("/apps");
    char path[64];
    for (int i = 0; i < 60; i++)
    {
        snprintf(path, sizeof(path), "/apps/Application Number %03d.mpy", i);
        CHECK(write_file(path, i, (uint32_t)(i * 997 % 3000), 512));
    }
    int bad = 0;
    for (int i = 0; i < 60; i++)
    {
        snprintf(path, sizeof(path), "/apps/Application Number %03d.mpy", i);
        bad += read_check(path, i, 0, 4000, 700) != 0;
    }
    CHECK(bad == 0);
    CHECK(count_entries("/apps", NULL) == 60);
    /* Removing every third file frees runs that cross boundaries too. */
    for (int i = 0; i < 60; i += 3)
    {
        snprintf(path, sizeof(path), "/apps/Application Number %03d.mpy", i);
        CHECK(fat32_delete(path) == FAT32_OK);
    }
    for (int i = 0; i < 20; i++)
    {
        snprintf(path, sizeof(path), "/apps/Refilled slot %02d.dat", i);
        CHECK(write_file(path, 100 + i, 1000, 1000));
    }
    CHECK(count_entries("/apps", NULL) == 60);
    CHECK(check_card() == 0);
}

static void test_long_names(void)
{
    mkdir_path("/long");
    char path[400];
    static const int lengths[] = {200, 247, 248, 250, 253};
    for (size_t k = 0; k < sizeof(lengths) / sizeof(lengths[0]); k++)
    {
        int n = snprintf(path, sizeof(path), "/long/");
        for (int i = 0; i < lengths[k]; i++)
            path[n + i] = (char)('a' + (i + (int)k) % 26);
        path[n + lengths[k]] = '\0';
        CHECK(write_file(path, 300 + (int)k, 10, 10));
        CHECK(read_check(path, 300 + (int)k, 0, 10, 10) == 0);
    }
    size_t longest = 0;
    CHECK(count_entries("/long", &longest) == 5 && longest == 253);
    /* The longest name FAT allows, 255 characters, fits only near the root. */
    memset(path, 'c', 256);
    path[0] = '/';
    path[256] = '\0';
    CHECK(write_file(path, 310, 10, 10));
    CHECK(read_check(path, 310, 0, 10, 10) == 0);
    longest = 0;
    CHECK(count_entries("/", &longest) >= 1 && longest == 255);
    CHECK(fat32_delete(path) == FAT32_OK);
    /* Paths or names that do not fit are refused, not cut to another name. */
    memset(path, 'b', 300);
    path[0] = '/';
    path[300] = '\0';
    fat32_file_t f;
    CHECK(fat32_create(&f, path) == FAT32_ERROR_INVALID_PATH);
    path[257] = '\0'; /* one 256-character name */
    CHECK(fat32_create(&f, path) == FAT32_ERROR_INVALID_PATH);
    CHECK(fat32_open(&f, path) == FAT32_ERROR_FILE_NOT_FOUND);
    /* Deleting names of 16 to 20 parts leaves no stray parts. */
    fat32_file_t d;
    fat32_entry_t e;
    char names[5][300];
    int count = 0;
    CHECK(fat32_open(&d, "/long") == FAT32_OK);
    while (fat32_dir_read(&d, &e) == FAT32_OK && e.filename[0] && count < 5)
        if (e.filename[0] != '.')
            snprintf(names[count++], sizeof(names[0]), "/long/%s", e.filename);
    fat32_close(&d);
    for (int i = 0; i < count; i++)
        CHECK(fat32_delete(names[i]) == FAT32_OK);
    CHECK(count_entries("/long", NULL) == 0);
    CHECK(check_card() == 0);
}

/* Names sharing a short-name stem get the lowest free ~n, past ~255 too. */
static void test_numeric_tails(void)
{
    mkdir_path("/many");
    char path[64];
    const unsigned long reads = block_reads;
    for (int i = 0; i < 270; i++)
    {
        snprintf(path, sizeof(path), "/many/Collision Test File %03d.txt", i);
        CHECK(write_file(path, 400 + i, 10, 10));
    }
    const unsigned long create_reads = block_reads - reads;
    fat32_file_t d;
    fat32_entry_t e;
    char seen[300][12];
    int n = 0, duplicates = 0, high_tail = 0;
    CHECK(fat32_open(&d, "/many") == FAT32_OK);
    while (fat32_dir_read(&d, &e) == FAT32_OK && e.filename[0] && n < 300)
    {
        if (e.filename[0] == '.')
            continue;
        for (int j = 0; j < n; j++)
            duplicates += memcmp(seen[j], e.short83, 11) == 0;
        memcpy(seen[n++], e.short83, 12);
        high_tail += memcmp(e.short83, "COLL~270TXT", 11) == 0;
    }
    fat32_close(&d);
    CHECK(n == 270 && duplicates == 0 && high_tail == 1);
    /* A freed tail is used again. */
    CHECK(fat32_delete("/many/Collision Test File 006.txt") == FAT32_OK);
    CHECK(write_file("/many/Collision Test File again.txt", 700, 10, 10));
    CHECK(fat32_open(&d, "/many") == FAT32_OK);
    bool reused = false;
    while (fat32_dir_read(&d, &e) == FAT32_OK && e.filename[0])
        reused |= strcmp(e.filename, "Collision Test File again.txt") == 0 &&
                  memcmp(e.short83, "COLLIS~7TXT", 11) == 0;
    fat32_close(&d);
    CHECK(reused);
    /* One directory pass per name, not one per tail tried (5.2 million
     * reads on 512-byte clusters before the tail search and the sector
     * buffer, about 100 thousand now). */
    printf("270 colliding names: %lu block reads\n", create_reads);
    CHECK(create_reads < 250000);
    CHECK(check_card() == 0);
}

static void test_sizes_and_seeks(void)
{
    mkdir_path("/sizes");
    static const uint32_t sizes[] = {0, 1, 511, 512, 513, 1024, 1025, 4097, 30000};
    static const uint32_t chunks[] = {37, 512, 1000, 65536};
    char path[64];
    int bad = 0;
    for (size_t s = 0; s < sizeof(sizes) / sizeof(sizes[0]); s++)
        for (size_t c = 0; c < sizeof(chunks) / sizeof(chunks[0]); c++)
        {
            const int id = 500 + (int)(s * 10 + c);
            snprintf(path, sizeof(path), "/sizes/s%u_c%u.bin", sizes[s], chunks[c]);
            CHECK(write_file(path, id, sizes[s], chunks[c]));
            bad += read_check(path, id, 0, sizes[s] + 5, 13) != 0;
            bad += read_check(path, id, 0, sizes[s], 512) != 0;
            bad += read_check(path, id, sizes[s] / 3, sizes[s], 777) != 0;
        }
    CHECK(bad == 0);

    /* Seeks forwards and backwards on one open file. */
    fat32_file_t f;
    CHECK(fat32_open(&f, "/sizes/s30000_c1000.bin") == FAT32_OK);
    static const uint32_t at[] = {0, 21000, 90, 29990, 15360, 1, 7500, 30000, 18000, 3000, 0};
    uint8_t buf[600];
    int wrong = 0;
    for (size_t k = 0; k < sizeof(at) / sizeof(at[0]); k++)
    {
        fat32_seek(&f, at[k]);
        for (int part = 0; part < 2; part++)
        {
            const uint32_t pos = fat32_tell(&f);
            size_t got = 0;
            fat32_read(&f, buf, sizeof(buf), &got);
            wrong += got != (pos >= 30000 ? 0 : (30000 - pos < 600 ? 30000 - pos : 600));
            for (size_t i = 0; i < got; i++)
                wrong += buf[i] != byte_at(500 + 8 * 10 + 2, pos + (uint32_t)i);
        }
    }
    fat32_close(&f);
    CHECK(wrong == 0);

    /* Overwriting part of a file, and writing past its end. */
    CHECK(fat32_open(&f, "/sizes/s4097_c37.bin") == FAT32_OK);
    fat32_seek(&f, 1000);
    uint8_t patch[3500];
    for (uint32_t i = 0; i < sizeof(patch); i++)
        patch[i] = byte_at(999, 1000 + i);
    size_t done = 0;
    CHECK(fat32_write(&f, patch, sizeof(patch), &done) == FAT32_OK && done == sizeof(patch));
    CHECK(fat32_size(&f) == 4500);
    fat32_close(&f);
    CHECK(fat32_open(&f, "/sizes/s4097_c37.bin") == FAT32_OK);
    uint8_t all[4500];
    done = 0;
    CHECK(fat32_read(&f, all, sizeof(all), &done) == FAT32_OK && done == sizeof(all));
    fat32_close(&f);
    wrong = 0;
    for (uint32_t i = 0; i < sizeof(all); i++)
        wrong += all[i] != (i >= 1000 ? byte_at(999, i) : byte_at(500 + 7 * 10, i));
    CHECK(wrong == 0);

    /* Small reads come from the buffered sector: a 4 KB file read one byte
     * at a time costs its sectors, not a sector per byte. */
    const unsigned long reads = block_reads;
    CHECK(read_check("/sizes/s4097_c512.bin", 500 + 7 * 10 + 1, 0, 4097, 1) == 0);
    CHECK(block_reads - reads < 64);
    CHECK(check_card() == 0);
}

/* Nothing buffered may survive a remount, or another card. */
static void test_remount_and_card_swap(uint8_t *first, uint8_t *second, uint32_t blocks)
{
    fat32_unmount();
    CHECK(fat32_mount() == FAT32_OK);
    CHECK(count_entries("/apps", NULL) == 60);
    fat32_unmount();
    insert_card(second, blocks);
    CHECK(fat32_mount() == FAT32_OK);
    CHECK(count_entries("/", NULL) == 0);
    fat32_file_t f;
    CHECK(fat32_open(&f, "/apps") == FAT32_ERROR_FILE_NOT_FOUND);
    CHECK(write_file("/after swap.txt", 800, 5000, 333));
    CHECK(read_check("/after swap.txt", 800, 0, 5000, 512) == 0);
    CHECK(count_entries("/", NULL) == 1);
    CHECK(check_card() == 0);
    fat32_unmount();
    insert_card(first, blocks);
    CHECK(fat32_mount() == FAT32_OK);
    CHECK(count_entries("/apps", NULL) == 60);
    CHECK(fat32_open(&f, "/after swap.txt") == FAT32_ERROR_FILE_NOT_FOUND);
}

/* The two FAT copies differ in this many sectors (a computer's disk check
 * compares them). */
static uint32_t fat_copies_differ(void)
{
    const fat32_boot_sector_t *bs = (const fat32_boot_sector_t *)card;
    uint32_t differ = 0;
    for (uint32_t s = 0; s < bs->fat_size_32; s++)
        differ += memcmp(sector(bs->reserved_sectors + s),
                         sector(bs->reserved_sectors + bs->fat_size_32 + s), SD_BLOCK_SIZE) != 0;
    return differ;
}

static bool exists(const char *path)
{
    fat32_file_t f;
    if (fat32_open(&f, path) != FAT32_OK)
        return false;
    fat32_close(&f);
    return true;
}

/* sd_mp.write(path, data, overwrite), call for call. */
static bool sd_mp_write(const char *path, int id, uint32_t size, bool overwrite)
{
    fat32_file_t f;
    if (fat32_open(&f, path) != FAT32_OK)
    {
        if (fat32_create(&f, path) != FAT32_OK)
            return false;
    }
    else if (overwrite)
    {
        fat32_close(&f);
        for (int i = 0; i < 32 && exists(path); i++)
            if (fat32_delete(path) != FAT32_OK)
                return false;
        if (fat32_create(&f, path) != FAT32_OK || fat32_open(&f, path) != FAT32_OK)
            return false;
    }
    else if (fat32_seek(&f, fat32_size(&f)) != FAT32_OK)
        return false;
    uint8_t *buf = malloc(size);
    const uint32_t start = fat32_size(&f);
    for (uint32_t i = 0; i < size; i++)
        buf[i] = byte_at(id, start + i);
    size_t done = 0;
    const bool ok = fat32_write(&f, buf, size, &done) == FAT32_OK && done == size;
    fat32_close(&f);
    free(buf);
    return ok;
}

/* sd_mp.remove: a directory's entries first, then the path itself. */
static bool sd_mp_remove(const char *path)
{
    fat32_file_t f;
    if (fat32_open(&f, path) != FAT32_OK)
        return true;
    if (f.attributes & FAT32_ATTR_DIRECTORY)
    {
        fat32_entry_t e;
        char child[300];
        while (fat32_dir_read(&f, &e) == FAT32_OK && e.filename[0])
        {
            if (strcmp(e.filename, ".") == 0 || strcmp(e.filename, "..") == 0)
                continue;
            snprintf(child, sizeof(child), "%s/%s", path, e.filename);
            sd_mp_remove(child);
        }
    }
    fat32_close(&f);
    return fat32_delete(path) == FAT32_OK;
}

/* The core benchmark's SD step (engtools/bench/core.py, _stage_sd), the same
 * driver calls in the same order, run three times as on the device. */
static void test_core_benchmark_sd_step(void)
{
    const char *scratch = "/picoware/core-benchmark-tmp", *data = "/picoware/core-benchmark-tmp/data.bin";
    mkdir_path("/picoware");
    CHECK(write_file("/picoware/apps.mpy", 900, 20000, 4096));
    char names[16][96], path[128];
    for (int round = 0; round < 3; round++)
    {
        /* _clear_scratch, then storage.mkdir */
        if (exists(scratch))
            CHECK(sd_mp_remove(scratch));
        mkdir_path(scratch);
        for (int i = 0; i < 3; i++) /* SD write 64 KB file in one call */
            CHECK(sd_mp_write(data, 1, 65536, true));
        for (int r = 0; r < 2; r++) /* SD append 512 bytes */
        {
            CHECK(sd_mp_write(data, 2, 512, true));
            for (int i = 0; i < 31; i++)
                CHECK(sd_mp_write(data, 2, 512, false));
        }
        CHECK(read_check(data, 2, 0, 16384, 4096) == 0);
        CHECK(sd_mp_write(data, 1, 65536, true));
        CHECK(read_check(data, 1, 0, 65536, 4096) == 0);
        for (int i = 0; i < 2; i++) /* open(path, 'wb'), 128 writes of 512 */
        {
            fat32_delete(data);
            CHECK(write_file(data, 3, 65536, 512));
        }
        CHECK(read_check(data, 3, 0, 65536, 4096) == 0);
        for (int i = 0; i < 16; i++)
        {
            snprintf(names[i], sizeof(names[i]), "%s/file-with-a-long-name-%02d.txt", scratch, i);
            CHECK(sd_mp_write(names[i], 10 + i, 20, true));
        }
        CHECK(count_entries(scratch, NULL) == 17);
        snprintf(path, sizeof(path), "%s/renamed-file-with-a-long-name.txt", scratch);
        for (int i = 0; i < 3; i++)
        {
            CHECK(fat32_rename(names[0], path) == FAT32_OK);
            CHECK(fat32_rename(path, names[0]) == FAT32_OK);
        }
        snprintf(path, sizeof(path), "%s/settings.json", scratch);
        for (int i = 0; i < 3; i++)
            CHECK(sd_mp_write(path, 40, 120, true));
        for (int i = 0; i < 16; i++)
            CHECK(sd_mp_remove(names[i]));
        CHECK(count_entries(scratch, NULL) == 2);
        /* _clear_scratch in the finally block */
        CHECK(sd_mp_remove(data));
        CHECK(sd_mp_remove(path));
        CHECK(sd_mp_remove(scratch));
        CHECK(!exists(scratch));
        CHECK(read_check("/picoware/apps.mpy", 900, 0, 20000, 4096) == 0);
        const int problems = check_card();
        if (problems)
            printf("  after round %d: %d card problems\n", round + 1, problems);
        CHECK(problems == 0);
    }
    printf("  FAT copies differ in %u sectors after the benchmark step\n", fat_copies_differ());
    /* FAT32_TEST_IMAGE=path keeps the card (sparse) for a disk checker. */
    const char *image = getenv("FAT32_TEST_IMAGE");
    if (image)
    {
        const fat32_boot_sector_t *bs = (const fat32_boot_sector_t *)card;
        FILE *out = fopen(image, "wb");
        static const uint8_t zero[SD_BLOCK_SIZE];
        for (uint32_t b = 0; out && b < bs->total_sectors_32; b++)
            if (memcmp(sector(b), zero, SD_BLOCK_SIZE) != 0)
            {
                fseek(out, (long)b * SD_BLOCK_SIZE, SEEK_SET);
                fwrite(sector(b), SD_BLOCK_SIZE, 1, out);
            }
        if (out)
        {
            fseek(out, (long)bs->total_sectors_32 * SD_BLOCK_SIZE - 1, SEEK_SET);
            fputc(0, out);
            fclose(out);
        }
    }
}

int main(void)
{
    static const uint8_t cluster_sizes[] = {1, 2, 64};
    fat32_init();
    for (size_t k = 0; k < sizeof(cluster_sizes) / sizeof(cluster_sizes[0]); k++)
    {
        const uint8_t spc = cluster_sizes[k];
        const uint32_t blocks = 70000u * spc; /* just over FAT32's 65525 clusters */
        uint8_t *first = format_card(blocks, spc), *second = format_card(blocks, spc);
        insert_card(first, blocks);
        CHECK(fat32_mount() == FAT32_OK);
        printf("%u-sector clusters\n", spc);
        test_entries_across_clusters();
        test_long_names();
        test_numeric_tails();
        test_sizes_and_seeks();
        test_core_benchmark_sd_step();
        test_remount_and_card_swap(first, second, blocks);
        printf("  block reads %lu, writes %lu\n", block_reads, block_writes);
        fat32_unmount();
        free(first);
        free(second);
        card = NULL;
    }
    printf("%s: %d checks, %d failures\n", failures ? "FAIL" : "PASS", checks, failures);
    return failures != 0;
}

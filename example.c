// Wokwi ILI9341 Display - Runs program.c from SD Card
// Single-purpose C program runner

#include "wokwi-api.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

// Simple C interpreter structures
typedef struct {
    char name[16];
    int16_t value;
} variable_t;

typedef struct {
    // Display pins
    pin_t VCC;
    pin_t GND;
    pin_t CS;
    pin_t RST;
    pin_t DC;
    pin_t MOSI;
    pin_t SCK;
    pin_t LED;
    pin_t MISO;
    
    // SD Card pins (SPI interface)
    pin_t SD_CS;
    pin_t SD_MOSI;
    pin_t SD_MISO;
    pin_t SD_SCK;
    pin_t SD_CD;  // Card detect
    
    // Control pin
    pin_t RUN_BTN;
    
    // Button state tracking
    uint8_t btn_pressed;
    uint8_t btn_debounce;
    
    // Program state
    uint8_t running;
    uint8_t error;
    char error_msg[64];
    int16_t output_value;
    
    // Interpreter state
    variable_t variables[32];
    uint8_t var_count;
    char program_buffer[4096];
    uint8_t program_loaded;
    
    // Output display
    char program_outputs[10][32];
    uint8_t output_count;
    
    // SD card state
    uint8_t sd_initialized;
    uint8_t sd_card_present;
    
    timer_t timer;
    timer_t display_timer;
    timer_t btn_debounce_timer;
    timer_t program_timer;
} chip_state_t;

// Colors
#define COLOR_BLACK   0x0000
#define COLOR_BLUE    0x001F
#define COLOR_RED     0xF800
#define COLOR_GREEN   0x07E0
#define COLOR_YELLOW  0xFFE0
#define COLOR_WHITE   0xFFFF
#define COLOR_CYAN    0x07FF
#define COLOR_MAGENTA 0xF81F
#define COLOR_GRAY    0x8410
#define COLOR_ORANGE  0xFD20

// Font definitions
#define FONT_WIDTH 5
#define FONT_HEIGHT 7
#define FONT_SPACING 1

// 5x7 Font Array - Generated Code
// ASCII Characters: 32(' '), 33('!'), 35('#'), 48('0'), 49('1'), 50('2'), 51('3'), 52('4'), 53('5'), 54('6'), 55('7'), 56('8'), 57('9'), 64('@'), 65('A'), 66('B'), 67('C'), 68('D'), 69('E'), 70('F'), 71('G'), 72('H'), 73('I'), 74('J'), 75('K'), 76('L'), 77('M'), 78('N'), 79('O'), 80('P'), 81('Q'), 82('R'), 83('S'), 84('T'), 85('U'), 86('V'), 87('W'), 88('X'), 89('Y'), 90('Z'), 97('a'), 98('b'), 99('c'), 100('d'), 101('e'), 102('f'), 103('g'), 104('h'), 105('i'), 106('j'), 107('k'), 108('l'), 109('m'), 110('n'), 111('o'), 112('p'), 113('q'), 114('r'), 115('s'), 116('t'), 117('u'), 118('v'), 119('w'), 120('x'), 121('y'), 122('z')

static const uint8_t font_5x7[][7] = {
    // 32 ' '
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 33 '!'
    { 0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04 },
    // 34 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 35 '#'
    { 0x00, 0x00, 0x00, 0x05, 0x0F, 0x0F, 0x0A },
    // 36 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 37 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 38 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 39 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 40 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 41 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 42 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 43 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 44 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 45 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 46 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 47 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 48 '0'
    { 0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E },
    // 49 '1'
    { 0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E },
    // 50 '2'
    { 0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F },
    // 51 '3'
    { 0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E },
    // 52 '4'
    { 0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02 },
    // 53 '5'
    { 0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E },
    // 54 '6'
    { 0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E },
    // 55 '7'
    { 0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08 },
    // 56 '8'
    { 0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E },
    // 57 '9'
    { 0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C },
    // 58 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 59 - ';'
    { 0x00, 0x00, 0x02, 0x00, 0x04, 0x08, 0x00 },
    // 60 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 61 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 62 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 63 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 64 '@'
    { 0x00, 0x0F, 0x01, 0x0F, 0x0B, 0x0F, 0x0F },
    // 65 'A'
    { 0x04, 0x0A, 0x11, 0x11, 0x1F, 0x11, 0x11 },
    // 66 'B'
    { 0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E },
    // 67 'C'
    { 0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E },
    // 68 'D'
    { 0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E },
    // 69 'E'
    { 0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F },
    // 70 'F'
    { 0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10 },
    // 71 'G'
    { 0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F },
    // 72 'H'
    { 0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11 },
    // 73 'I'
    { 0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E },
    // 74 'J'
    { 0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C },
    // 75 'K'
    { 0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11 },
    // 76 'L'
    { 0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F },
    // 77 'M'
    { 0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11 },
    // 78 'N'
    { 0x11, 0x11, 0x19, 0x15, 0x13, 0x11, 0x11 },
    // 79 'O'
    { 0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E },
    // 80 'P'
    { 0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10 },
    // 81 'Q'
    { 0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D },
    // 82 'R'
    { 0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11 },
    // 83 'S'
    { 0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E },
    // 84 'T'
    { 0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04 },
    // 85 'U'
    { 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E },
    // 86 'V'
    { 0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04 },
    // 87 'W'
    { 0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A },
    // 88 'X'
    { 0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11 },
    // 89 'Y'
    { 0x11, 0x11, 0x11, 0x0A, 0x04, 0x04, 0x04 },
    // 90 'Z'
    { 0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F },
    // 91 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 92 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 93 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 94 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 95 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 96 - Not defined
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
    // 97 'a'
    { 0x00, 0x00, 0x0E, 0x12, 0x12, 0x0F, 0x00 },
    // 98 'b'
    { 0x10, 0x10, 0x10, 0x10, 0x1C, 0x12, 0x1C },
    // 99 'c'
    { 0x00, 0x00, 0x0E, 0x10, 0x10, 0x10, 0x0E },
    // 100 'd'
    { 0x02, 0x02, 0x02, 0x0E, 0x12, 0x12, 0x0E },
    // 101 'e'
    { 0x00, 0x00, 0x0E, 0x11, 0x1E, 0x10, 0x0E },
    // 102 'f'
    { 0x00, 0x08, 0x0E, 0x08, 0x1C, 0x08, 0x08 },
    // 103 'g'
    { 0x00, 0x0F, 0x12, 0x12, 0x0E, 0x02, 0x1C },
    // 104 'h'
    { 0x08, 0x08, 0x08, 0x08, 0x0E, 0x0A, 0x0A },
    // 105 'i'
    { 0x00, 0x00, 0x04, 0x00, 0x04, 0x04, 0x04 },
    // 106 'j'
    { 0x00, 0x00, 0x04, 0x00, 0x04, 0x04, 0x18 },
    // 107 'k'
    { 0x08, 0x08, 0x0A, 0x0C, 0x0C, 0x0A, 0x09 },
    // 108 'l'
    { 0x00, 0x00, 0x04, 0x04, 0x04, 0x04, 0x04 },
    // 109 'm'
    { 0x00, 0x00, 0x00, 0x00, 0x1B, 0x15, 0x15 },
    // 110 'n'
    { 0x00, 0x00, 0x00, 0x0E, 0x09, 0x09, 0x09 },
    // 111 'o'
    { 0x00, 0x00, 0x0E, 0x11, 0x11, 0x11, 0x0E },
    // 112 'p'
    { 0x00, 0x08, 0x0E, 0x0A, 0x0E, 0x08, 0x08 },
    // 113 'q'
    { 0x00, 0x0E, 0x12, 0x12, 0x0E, 0x02, 0x02 },
    // 114 'r'
    { 0x00, 0x00, 0x08, 0x0E, 0x0A, 0x08, 0x08 },
    // 115 's'
    { 0x00, 0x00, 0x0F, 0x10, 0x0E, 0x01, 0x1E },
    // 116 't'
    { 0x00, 0x00, 0x1F, 0x04, 0x04, 0x04, 0x04 },
    // 117 'u'
    { 0x00, 0x00, 0x00, 0x11, 0x11, 0x11, 0x0E },
    // 118 'v'
    { 0x00, 0x00, 0x00, 0x11, 0x11, 0x0A, 0x04 },
    // 119 'w'
    { 0x00, 0x00, 0x00, 0x11, 0x15, 0x15, 0x0A },
    // 120 'x'
    { 0x00, 0x00, 0x11, 0x0A, 0x04, 0x0A, 0x11 },
    // 121 'y'
    { 0x00, 0x00, 0x09, 0x09, 0x07, 0x01, 0x0F },
    // 122 'z'
    { 0x00, 0x00, 0x1F, 0x02, 0x04, 0x08, 0x1F },
};


// ===========================================
// DISPLAY FUNCTIONS
// ===========================================

static void spi_write(pin_t mosi, pin_t sck, uint8_t data) {
    for (int i = 7; i >= 0; i--) {
        pin_write(mosi, (data >> i) & 1);
        pin_write(sck, 1);
        pin_write(sck, 0);
    }
}

static uint8_t spi_read(pin_t miso, pin_t sck) {
    uint8_t data = 0;
    for (int i = 7; i >= 0; i--) {
        pin_write(sck, 1);
        data |= (pin_read(miso) << i);
        pin_write(sck, 0);
    }
    return data;
}

static void send_cmd(chip_state_t *chip, uint8_t cmd) {
    pin_write(chip->DC, 0);
    pin_write(chip->CS, 0);
    spi_write(chip->MOSI, chip->SCK, cmd);
    pin_write(chip->CS, 1);
}

static void send_data(chip_state_t *chip, uint8_t data) {
    pin_write(chip->DC, 1);
    pin_write(chip->CS, 0);
    spi_write(chip->MOSI, chip->SCK, data);
    pin_write(chip->CS, 1);
}

static void send_data16(chip_state_t *chip, uint16_t data) {
    send_data(chip, data >> 8);
    send_data(chip, data & 0xFF);
}

static void set_window(chip_state_t *chip, uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1) {
    send_cmd(chip, 0x2A);
    send_data16(chip, x0);
    send_data16(chip, x1);
    send_cmd(chip, 0x2B);
    send_data16(chip, y0);
    send_data16(chip, y1);
}

static void fill_rect(chip_state_t *chip, uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t color) {
    if (x >= 240 || y >= 320) return;
    if (x + w > 240) w = 240 - x;
    if (y + h > 320) h = 320 - y;
    
    set_window(chip, x, y, x + w - 1, y + h - 1);
    send_cmd(chip, 0x2C);
    
    for (int i = 0; i < w * h; i++) {
        send_data16(chip, color);
    }
}

static void draw_char(chip_state_t *chip, char c, uint16_t x, uint16_t y, uint16_t color) {
    if (c < 32 || c > 126) return;
    
    int idx = c - 32;
    for (int row = 0; row < FONT_HEIGHT; row++) {
        uint8_t bits = font_5x7[idx][row];
        for (int col = 0; col < FONT_WIDTH; col++) {
            if (bits & (1 << (4 - col))) {
                set_window(chip, x + col, y + row, x + col, y + row);
                send_cmd(chip, 0x2C);
                send_data16(chip, color);
            }
        }
    }
}

static void draw_string(chip_state_t *chip, const char *str, uint16_t x, uint16_t y, uint16_t color) {
    uint16_t cx = x;
    while (*str) {
        draw_char(chip, *str, cx, y, color);
        cx += FONT_WIDTH + 1;
        if (cx + FONT_WIDTH > 240) {
            cx = x;
            y += FONT_HEIGHT + 2;
        }
        str++;
    }
}

// ===========================================
// SD CARD FUNCTIONS (REAL IMPLEMENTATION)
// ===========================================

// SD Card SPI functions
static void sd_spi_write(chip_state_t *chip, uint8_t data) {
    pin_write(chip->SD_CS, 0);
    spi_write(chip->SD_MOSI, chip->SD_SCK, data);
    pin_write(chip->SD_CS, 1);
}

static uint8_t sd_spi_read(chip_state_t *chip) {
    pin_write(chip->SD_CS, 0);
    uint8_t data = spi_read(chip->SD_MISO, chip->SD_SCK);
    pin_write(chip->SD_CS, 1);
    return data;
}

// Send command to SD card
static uint8_t sd_send_command(chip_state_t *chip, uint8_t cmd, uint32_t arg) {
    uint8_t response;
    int retry = 0;
    
    // Send command
    sd_spi_write(chip, 0x40 | cmd);
    sd_spi_write(chip, (arg >> 24) & 0xFF);
    sd_spi_write(chip, (arg >> 16) & 0xFF);
    sd_spi_write(chip, (arg >> 8) & 0xFF);
    sd_spi_write(chip, arg & 0xFF);
    
    // CRC (dummy for most commands)
    if (cmd == 0) sd_spi_write(chip, 0x95);
    else if (cmd == 8) sd_spi_write(chip, 0x87);
    else sd_spi_write(chip, 0x01);
    
    // Wait for response (up to 8 bytes)
    while ((response = sd_spi_read(chip)) == 0xFF && retry < 10) {
        retry++;
    }
    
    return response;
}

// Initialize SD card
static uint8_t sd_init(chip_state_t *chip) {
    printf("Initializing SD card...\n");
    
    // Set SPI mode (slow speed for initialization)
    pin_write(chip->SD_CS, 1);
    pin_write(chip->SD_SCK, 0);
    
    // Send 80 clock cycles with CS high
    for (int i = 0; i < 10; i++) {
        sd_spi_write(chip, 0xFF);
    }
    
    // CMD0: Go idle state
    if (sd_send_command(chip, 0, 0) != 0x01) {
        printf("SD CMD0 failed\n");
        return 0;
    }
    
    // CMD8: Check voltage
    if (sd_send_command(chip, 8, 0x1AA) != 0x01) {
        printf("SD CMD8 failed (not SDHC/SDXC)\n");
        // Try older card type
    }
    
    // CMD55 + ACMD41: Initialize
    int timeout = 100;
    while (timeout-- > 0) {
        sd_send_command(chip, 55, 0);
        if (sd_send_command(chip, 41, 0x40000000) == 0) {
            chip->sd_initialized = 1;
            printf("SD card initialized successfully\n");
            return 1;
        }
    }
    
    printf("SD card init timeout\n");
    return 0;
}

// Read sector from SD card
static uint8_t sd_read_sector(chip_state_t *chip, uint32_t sector, uint8_t *buffer) {
    if (!chip->sd_initialized) {
        if (!sd_init(chip)) return 0;
    }
    
    // CMD17: Read single block
    if (sd_send_command(chip, 17, sector * 512) != 0x00) {
        printf("SD read command failed\n");
        return 0;
    }
    
    // Wait for data token
    int timeout = 10000;
    while (sd_spi_read(chip) != 0xFE && timeout-- > 0);
    
    if (timeout <= 0) {
        printf("SD data token timeout\n");
        return 0;
    }
    
    // Read 512 bytes
    for (int i = 0; i < 512; i++) {
        buffer[i] = sd_spi_read(chip);
    }
    
    // Read CRC (ignore)
    sd_spi_read(chip);
    sd_spi_read(chip);
    
    return 1;
}

// Read file system (simple FAT16 implementation)
static uint8_t read_file(chip_state_t *chip, const char *filename, char *buffer, uint16_t max_len) {
    uint8_t sector_buffer[512];
    uint32_t root_dir_sector = 2048; // FAT16 typical root directory location
    uint16_t file_cluster = 0;
    
    // Read root directory
    if (!sd_read_sector(chip, root_dir_sector, sector_buffer)) {
        printf("Failed to read root directory\n");
        return 0;
    }
    
    // Search for program.c in root directory
    for (int i = 0; i < 512; i += 32) {
        if (sector_buffer[i] == 0x00) break; // End of directory
        if (sector_buffer[i] == 0xE5) continue; // Deleted entry
        
        // Check filename (8.3 format)
        char found_name[13];
        int pos = 0;
        for (int j = 0; j < 8; j++) {
            if (sector_buffer[i + j] != ' ') {
                found_name[pos++] = sector_buffer[i + j];
            }
        }
        found_name[pos++] = '.';
        for (int j = 8; j < 11; j++) {
            if (sector_buffer[i + j] != ' ') {
                found_name[pos++] = sector_buffer[i + j];
            }
        }
        found_name[pos] = '\0';
        
        if (strcmp(found_name, "PROGRAM.C") == 0) {
            // Found file - get cluster
            file_cluster = (sector_buffer[i + 26] << 8) | sector_buffer[i + 27];
            printf("Found %s at cluster %d\n", filename, file_cluster);
            break;
        }
    }
    
    if (file_cluster == 0) {
        printf("File %s not found\n", filename);
        return 0;
    }
    
    // Calculate data sector (simplified)
    uint32_t data_sector = 2048 + 32 + (file_cluster - 2) * 1;
    
    // Read file content
    if (!sd_read_sector(chip, data_sector, sector_buffer)) {
        printf("Failed to read file data\n");
        return 0;
    }
    
    // Copy file content (up to max_len)
    uint16_t len = 0;
    while (len < max_len - 1 && sector_buffer[len] != 0 && sector_buffer[len] != 0x1A) {
        buffer[len] = sector_buffer[len];
        len++;
    }
    buffer[len] = '\0';
    
    printf("Read %d bytes from %s\n", len, filename);
    return 1;
}

// ===========================================
// C INTERPRETER FUNCTIONS
// ===========================================

// Find or create variable
static variable_t* get_variable(chip_state_t *chip, const char *name) {
    for (int i = 0; i < chip->var_count; i++) {
        if (strcmp(chip->variables[i].name, name) == 0) {
            return &chip->variables[i];
        }
    }
    
    if (chip->var_count < 32) {
        strcpy(chip->variables[chip->var_count].name, name);
        chip->variables[chip->var_count].value = 0;
        chip->var_count++;
        return &chip->variables[chip->var_count - 1];
    }
    
    return NULL;
}

// Parse integer from string
static int parse_number(const char **str) {
    int result = 0;
    while (**str >= '0' && **str <= '9') {
        result = result * 10 + (**str - '0');
        (*str)++;
    }
    return result;
}

// Parse identifier from string
static void parse_identifier(const char **str, char *buf, int max_len) {
    int i = 0;
    while ((**str >= 'a' && **str <= 'z') || 
           (**str >= 'A' && **str <= 'Z') ||
           (**str >= '0' && **str <= '9') ||
           **str == '_') {
        if (i < max_len - 1) {
            buf[i++] = **str;
        }
        (*str)++;
    }
    buf[i] = '\0';
}

// Skip whitespace
static void skip_whitespace(const char **str) {
    while (**str == ' ' || **str == '\t' || **str == '\n' || **str == '\r') {
        (*str)++;
    }
}

// Evaluate expression (handles +, -, *, /, numbers, and variables)
static int eval_expression(chip_state_t *chip, const char **str) {
    skip_whitespace(str);
    
    int result = 0;
    
    // Parse first term
    if (**str >= '0' && **str <= '9') {
        result = parse_number(str);
    } else if ((**str >= 'a' && **str <= 'z') || (**str >= 'A' && **str <= 'Z')) {
        char var_name[16];
        parse_identifier(str, var_name, sizeof(var_name));
        variable_t *var = get_variable(chip, var_name);
        result = var ? var->value : 0;
    } else if (**str == '(') {
        (*str)++;
        result = eval_expression(chip, str);
        skip_whitespace(str);
        if (**str == ')') (*str)++;
        else {
            chip->error = 1;
            strcpy(chip->error_msg, "Expected )");
            return 0;
        }
    } else {
        chip->error = 1;
        strcpy(chip->error_msg, "Invalid expression start");
        return 0;
    }
    
    // Handle operators
    while (1) {
        skip_whitespace(str);
        
        char op = **str;
        if (op != '+' && op != '-' && op != '*' && op != '/') {
            break;
        }
        (*str)++;
        
        skip_whitespace(str);
        
        int next_value = 0;
        
        // Parse next term
        if (**str >= '0' && **str <= '9') {
            next_value = parse_number(str);
        } else if ((**str >= 'a' && **str <= 'z') || (**str >= 'A' && **str <= 'Z')) {
            char var_name[16];
            parse_identifier(str, var_name, sizeof(var_name));
            variable_t *var = get_variable(chip, var_name);
            next_value = var ? var->value : 0;
        } else if (**str == '(') {
            (*str)++;
            next_value = eval_expression(chip, str);
            skip_whitespace(str);
            if (**str == ')') (*str)++;
            else {
                chip->error = 1;
                strcpy(chip->error_msg, "Expected )");
                return 0;
            }
        } else {
            chip->error = 1;
            strcpy(chip->error_msg, "Expected value after operator");
            return 0;
        }
        
        // Apply operator
        switch (op) {
            case '+': result += next_value; break;
            case '-': result -= next_value; break;
            case '*': result *= next_value; break;
            case '/': 
                if (next_value != 0) {
                    result /= next_value;
                } else {
                    chip->error = 1;
                    strcpy(chip->error_msg, "Division by zero");
                    return 0;
                }
                break;
        }
    }
    
    return result;
}

// Run a single C statement
static void run_statement(chip_state_t *chip, const char **program) {
    skip_whitespace(program);
    
    // End of program
    if (**program == '\0') {
        return;
    }
    
    // Comment
    if (strncmp(*program, "//", 2) == 0) {
        while (**program && **program != '\n') (*program)++;
        if (**program == '\n') (*program)++;
        return;
    }
    
    // Print statement
    if (strncmp(*program, "print(", 6) == 0) {
        *program += 6; // Skip "print("
        
        int value = eval_expression(chip, program);
        chip->output_value = value;
        
        // Store output for display
        if (chip->output_count < 10) {
            sprintf(chip->program_outputs[chip->output_count], "OUT: %d", value);
            chip->output_count++;
        }
        
        printf("PROGRAM OUTPUT: %d\n", value);
        
        skip_whitespace(program);
        if (**program != ')') {
            chip->error = 1;
            strcpy(chip->error_msg, "Expected )");
            return;
        }
        (*program)++;
        
        skip_whitespace(program);
        if (**program != ';') {
            chip->error = 1;
            strcpy(chip->error_msg, "Expected ;");
        } else {
            (*program)++;
        }
        return;
    }
    
    // Variable assignment
    if ((**program >= 'a' && **program <= 'z') || (**program >= 'A' && **program <= 'Z')) {
        char var_name[16];
        parse_identifier(program, var_name, sizeof(var_name));
        
        skip_whitespace(program);
        if (**program != '=') {
            chip->error = 1;
            strcpy(chip->error_msg, "Expected =");
            return;
        }
        (*program)++;
        
        int value = eval_expression(chip, program);
        variable_t *var = get_variable(chip, var_name);
        if (var) {
            var->value = value;
            // Store output for display
            if (chip->output_count < 10) {
                sprintf(chip->program_outputs[chip->output_count], "%s = %d", var_name, value);
                chip->output_count++;
            }
        }
        
        skip_whitespace(program);
        if (**program != ';') {
            chip->error = 1;
            strcpy(chip->error_msg, "Expected ;");
        } else {
            (*program)++;
        }
        return;
    }
    
    // End of statement (just a semicolon)
    if (**program == ';') {
        (*program)++;
        return;
    }
    
    chip->error = 1;
    if (**program) {
        sprintf(chip->error_msg, "Unexpected: '%c'", **program);
    } else {
        strcpy(chip->error_msg, "Unexpected end");
    }
}

// ===========================================
// PROGRAM EXECUTION
// ===========================================

// Load program.c from SD card (ACTUAL READING)
static void load_program_c(chip_state_t *chip) {
    printf("Loading program.c from SD card...\n");
    
    // Clear previous program
    chip->program_buffer[0] = '\0';
    chip->program_loaded = 0;
    
    // Check SD card presence
    if (pin_read(chip->SD_CD) == 0) {
        chip->sd_card_present = 1;
        printf("SD card detected\n");
        
        // Try to read program.c from SD card
        if (read_file(chip, "program.c", chip->program_buffer, sizeof(chip->program_buffer) - 1)) {
            chip->program_loaded = 1;
            printf("Successfully loaded program.c (%lu bytes)\n", (unsigned long)strlen(chip->program_buffer));
            return;
        }
    } else {
        chip->sd_card_present = 0;
        printf("No SD card detected\n");
    }
    
    // Fallback: use default program if SD card fails
    printf("Using default program\n");
    const char *default_program = 
        "// Simple test program\n"
        "x = 10;\n"
        "print(x);\n"
        "y = 20;\n"
        "sum = x + y;\n"
        "print(sum);\n";
    
    strcpy(chip->program_buffer, default_program);
    chip->program_loaded = 1;
}

// Run program.c
static void run_program_c(chip_state_t *chip) {
    printf("\n=== RUNNING program.c ===\n");
    
    // Reset state
    chip->running = 1;
    chip->error = 0;
    chip->output_value = 0;
    chip->var_count = 0;
    chip->output_count = 0;
    memset(chip->variables, 0, sizeof(chip->variables));
    memset(chip->program_outputs, 0, sizeof(chip->program_outputs));
    
    // Clear screen for program execution
    fill_rect(chip, 0, 0, 240, 320, COLOR_BLACK);
    draw_string(chip, "EXECUTING PROGRAM.C", 30, 140, COLOR_YELLOW);
    draw_string(chip, "Please wait...", 70, 160, COLOR_CYAN);
    
    // Load program from SD card
    load_program_c(chip);
    
    if (!chip->program_loaded) {
        chip->error = 1;
        strcpy(chip->error_msg, "Failed to load program");
        chip->running = 0;
        return;
    }
    
    // Execute program
    const char *ptr = chip->program_buffer;
    while (*ptr && !chip->error) {
        run_statement(chip, &ptr);
    }
    
    chip->running = 0;
    
    if (chip->error) {
        printf("ERROR: %s\n", chip->error_msg);
    } else {
        printf("Program finished successfully\n");
        printf("Final output: %d\n", chip->output_value);
    }
}

// ===========================================
// DISPLAY INTERFACE
// ===========================================

static void update_display(chip_state_t *chip) {
    // Clear screen
    fill_rect(chip, 0, 0, 240, 320, COLOR_BLACK);
    
    // Title
    draw_string(chip, "C PROGRAM RUNNER", 50, 10, COLOR_GREEN);
    draw_string(chip, "================", 50, 20, COLOR_CYAN);
    
    // SD Card status
    if (chip->sd_card_present) {
        draw_string(chip, "SD CARD: PRESENT", 20, 40, COLOR_GREEN);
    } else {
        draw_string(chip, "SD CARD: NOT FOUND", 20, 40, COLOR_RED);
    }
    
    // Status
    draw_string(chip, "FILE: program.c", 20, 60, COLOR_WHITE);
    
    if (chip->running) {
        draw_string(chip, "STATUS: RUNNING", 20, 80, COLOR_YELLOW);
    } else if (chip->error) {
        draw_string(chip, "STATUS: ERROR", 20, 80, COLOR_RED);
        draw_string(chip, chip->error_msg, 20, 100, COLOR_RED);
    } else {
        draw_string(chip, "STATUS: READY", 20, 80, COLOR_GREEN);
        draw_string(chip, "Press RUN button", 20, 100, COLOR_CYAN);
    }
    
    // Output section
    draw_string(chip, "PROGRAM OUTPUTS:", 20, 130, COLOR_MAGENTA);
    
    int y_pos = 150;
    for (int i = 0; i < chip->output_count && i < 6; i++) {
        draw_string(chip, chip->program_outputs[i], 30, y_pos, COLOR_WHITE);
        y_pos += 20;
    }
    
    if (chip->output_count == 0 && !chip->running) {
        draw_string(chip, "No outputs yet", 30, 150, COLOR_GRAY);
    }
    
    // Variables section
    draw_string(chip, "VARIABLES:", 20, 250, COLOR_CYAN);
    
    y_pos = 270;
    for (int i = 0; i < chip->var_count && i < 3; i++) {
        char var_str[32];
        sprintf(var_str, "%s = %d", chip->variables[i].name, chip->variables[i].value);
        draw_string(chip, var_str, 30, y_pos, COLOR_YELLOW);
        y_pos += 15;
    }
    
    // Instructions
    if (!chip->running) {
        draw_string(chip, "Press RUN_BTN to execute", 20, 310, COLOR_WHITE);
    }
}

// ===========================================
// TIMERS AND CALLBACKS
// ===========================================

static void program_timer_callback(void *user_data) {
    chip_state_t *chip = (chip_state_t*)user_data;
    
    // Program execution finished, update display
    chip->running = 0;
    update_display(chip);
}

static void main_timer_callback(void *user_data) {
    chip_state_t *chip = (chip_state_t*)user_data;
    
    // Check SD card presence
    uint8_t sd_present = (pin_read(chip->SD_CD) == 0);
    if (sd_present != chip->sd_card_present) {
        chip->sd_card_present = sd_present;
        if (!chip->running) {
            update_display(chip);
        }
    }
    
    // Check RUN button
    uint8_t btn_state = pin_read(chip->RUN_BTN);
    
    if (btn_state == 0 && !chip->btn_pressed && !chip->btn_debounce && !chip->running) {
        chip->btn_debounce = 1;
        chip->btn_pressed = 1;
        
        printf("RUN button pressed - executing program\n");
        
        // Start program execution
        run_program_c(chip);
        
        // Schedule display update after program finishes
        const timer_config_t program_config = {
            .callback = program_timer_callback,
            .user_data = chip,
        };
        chip->program_timer = timer_init(&program_config);
        timer_start(chip->program_timer, 100000, 1); // 100ms delay for display
        
        // Clear debounce after 50ms
        const timer_config_t debounce_config = {
            .callback = NULL,
            .user_data = chip,
        };
        chip->btn_debounce_timer = timer_init(&debounce_config);
        timer_start(chip->btn_debounce_timer, 50000, 1);
    }
    else if (btn_state == 1 && chip->btn_pressed) {
        chip->btn_pressed = 0;
    }
    
    timer_start(chip->timer, 50000, 0);
}

static void display_timer_callback(void *user_data) {
    chip_state_t *chip = (chip_state_t*)user_data;
    
    // Clear debounce flag
    if (chip->btn_debounce) {
        chip->btn_debounce = 0;
    }
    
    // Only update display if not running program
    if (!chip->running) {
        update_display(chip);
    }
    
    timer_start(chip->display_timer, 500000, 0); // Update every 500ms
}

static void run_btn_callback(void *user_data, pin_t pin, uint32_t value) {
    chip_state_t *chip = (chip_state_t*)user_data;
    
    if (value == 0 && !chip->running && !chip->btn_debounce) {
        chip->btn_debounce = 1;
        printf("RUN button pressed via callback\n");
        
        // Start program
        run_program_c(chip);
        
        // Schedule display update
        const timer_config_t program_config = {
            .callback = program_timer_callback,
            .user_data = chip,
        };
        chip->program_timer = timer_init(&program_config);
        timer_start(chip->program_timer, 100000, 1);
        
        // Clear debounce
        const timer_config_t debounce_config = {
            .callback = NULL,
            .user_data = chip,
        };
        chip->btn_debounce_timer = timer_init(&debounce_config);
        timer_start(chip->btn_debounce_timer, 50000, 1);
    }
}

// ===========================================
// INITIALIZATION
// ===========================================

static void init_display(chip_state_t *chip) {
    printf("Initializing ILI9341...\n");
    
    // Hardware reset
    pin_write(chip->RST, 0);
    timer_t delay = timer_init(NULL);
    timer_start(delay, 10000, 0);
    
    pin_write(chip->RST, 1);
    timer_start(delay, 100000, 0);
    
    // Initialization sequence
    send_cmd(chip, 0x01);  // Software reset
    timer_start(delay, 5000, 0);
    
    send_cmd(chip, 0x11);  // Sleep out
    timer_start(delay, 120000, 0);
    
    send_cmd(chip, 0x3A);  // Color mode
    send_data(chip, 0x55); // 16-bit
    
    send_cmd(chip, 0x36);  // MADCTL
    send_data(chip, 0x48); // Portrait
    
    send_cmd(chip, 0x29);  // Display on
    
    // Backlight on
    pin_write(chip->LED, 1);
    
    printf("Display ready\n");
}

static void init_callback(void *user_data) {
    chip_state_t *chip = (chip_state_t*)user_data;
    
    init_display(chip);
    
    // Check SD card
    chip->sd_card_present = (pin_read(chip->SD_CD) == 0);
    if (chip->sd_card_present) {
        printf("SD card detected on startup\n");
        // Try to initialize SD card
        sd_init(chip);
    }
    
    // Load program for preview
    load_program_c(chip);
    update_display(chip);
    
    // Start timers
    const timer_config_t main_config = {
        .callback = main_timer_callback,
        .user_data = chip,
    };
    chip->timer = timer_init(&main_config);
    timer_start(chip->timer, 100000, 0);
    
    const timer_config_t display_config = {
        .callback = display_timer_callback,
        .user_data = chip,
    };
    chip->display_timer = timer_init(&display_config);
    timer_start(chip->display_timer, 1000000, 0);
    
    printf("System ready. Press RUN_BTN to execute program.c\n");
}

void chip_init(void) {
    chip_state_t *chip = malloc(sizeof(chip_state_t));
    memset(chip, 0, sizeof(chip_state_t));
    
    printf("=================================\n");
    printf("   ILI9341 C PROGRAM RUNNER\n");
    printf("   Runs program.c from SD card\n");
    printf("=================================\n");
    
    // Initialize pins
    chip->VCC = pin_init("VCC", OUTPUT);
    chip->GND = pin_init("GND", OUTPUT);
    chip->CS = pin_init("CS", OUTPUT);
    chip->RST = pin_init("RST", OUTPUT);
    chip->DC = pin_init("DC", OUTPUT);
    chip->MOSI = pin_init("MOSI", OUTPUT);
    chip->SCK = pin_init("SCK", OUTPUT);
    chip->LED = pin_init("LED", OUTPUT);
    chip->MISO = pin_init("MISO", INPUT);
    
    // SD Card pins (using standard SPI names)
    chip->SD_CS = pin_init("SD_CS", OUTPUT);
    chip->SD_MOSI = pin_init("SD_DI", OUTPUT);  // DI = MOSI
    chip->SD_MISO = pin_init("SD_DO", INPUT);   // DO = MISO
    chip->SD_SCK = pin_init("SD_SCK", OUTPUT);
    chip->SD_CD = pin_init("SD_CD", INPUT_PULLUP);
    
    // Run button
    chip->RUN_BTN = pin_init("COMPILE_BUTTON", INPUT_PULLUP);
    
    // Set initial pin states
    pin_write(chip->VCC, 1);
    pin_write(chip->GND, 0);
    pin_write(chip->LED, 1);
    pin_write(chip->CS, 1);
    pin_write(chip->RST, 1);
    pin_write(chip->DC, 0);
    pin_write(chip->MOSI, 0);
    pin_write(chip->SCK, 0);
    
    // SD card pins
    pin_write(chip->SD_CS, 1);
    pin_write(chip->SD_MOSI, 1);
    pin_write(chip->SD_SCK, 0);
    
    // Initialize button state
    chip->btn_pressed = 0;
    chip->btn_debounce = 0;
    chip->sd_initialized = 0;
    chip->sd_card_present = 0;
    
    // Setup button callback
    const pin_watch_config_t btn_watch = {
        .edge = BOTH,
        .pin_change = run_btn_callback,
        .user_data = chip,
    };
    pin_watch(chip->RUN_BTN, &btn_watch);
    
    // Initialize state
    chip->running = 0;
    chip->error = 0;
    chip->output_value = 0;
    chip->program_loaded = 0;
    chip->var_count = 0;
    chip->output_count = 0;
    
    // Start initialization
    const timer_config_t init_config = {
        .callback = init_callback,
        .user_data = chip,
    };
    timer_t init_timer = timer_init(&init_config);
    timer_start(init_timer, 100000, 0);
    
    printf("System initialized. Waiting for RUN_BTN...\n");
}

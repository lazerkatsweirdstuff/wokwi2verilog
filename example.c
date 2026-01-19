#include "wokwi-api.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#define SH1107_CONTROL_CO 0x80
#define SH1107_CONTROL_DC 0x40

#define OLED_WIDTH 128
#define OLED_HEIGHT 64
#define OLED_PAGES (OLED_HEIGHT / 8)

#define PIXELS_PER_SECOND 0.05f  

#define BUTTON_HEIGHT 12
#define BUTTON_BORDER 2
#define MAX_BUTTONS 10  

typedef enum {
    SCREEN_LOCKED,
    SCREEN_HOME
} screen_state_t;

typedef struct sh1107_state_t {
  uint8_t framebuffer[OLED_WIDTH * OLED_PAGES];  
  uint8_t textbuffer[OLED_WIDTH * OLED_PAGES];   
  uint8_t buttonbuffer[OLED_WIDTH * OLED_PAGES];
  uint8_t button_text_inverted[OLED_WIDTH * OLED_PAGES];

  pin_t scl_pin;
  pin_t sda_pin;
  pin_t vcc_pin;
  pin_t gnd_pin;

  pin_t up_pin;
  pin_t down_pin;
  pin_t left_pin;
  pin_t right_pin;

  pin_t Abutton;
  pin_t Bbutton;

  bool initialized;
  uint8_t i2c_address;

  bool display_on;
  uint8_t contrast;
  bool invert;

  int pixel_x;
  int pixel_y;

  timer_t update_timer;

  int old_pixel_x;
  int old_pixel_y;

  struct {
    int start_x;
    int start_y;
    int width;
    int page;
    char text[32];
    bool is_filled;  
  } buttons[MAX_BUTTONS];
  int button_count;  

  bool cursor_inverted;
  screen_state_t current_screen;
  bool a_button_was_pressed;
} sh1107_state_t;

static sh1107_state_t *chip = NULL;

static const uint8_t font_5x7[][5] = {
    {0b100000, 0b1010010, 0b1010010, 0b1010010, 0b1111100}, 

    {0b1111111, 0b1001000, 0b1001000, 0b1001000, 0b110000}, 

    {0b111100, 0b1000010, 0b1000010, 0b1000010, 0b100100}, 

    {0b110000, 0b1001000, 0b1001000, 0b1001000, 0b1111111}, 

    {0b111100, 0b1001010, 0b1001010, 0b1001010, 0b101100}, 

    {0b01000, 0b1111110, 0b01010, 0b00010, 0b00000}, 

    {0b100100, 0b1001010, 0b1001010, 0b1001010, 0b111110}, 

    {0b1111111, 0b01000, 0b01000, 0b01000, 0b1110000}, 

    {0b00000, 0b1000100, 0b1111101, 0b1000000, 0b00000}, 

    {0b100000, 0b1000000, 0b1000000, 0b1000000, 0b111101}, 

    {0b1111110, 0b01000, 0b10100, 0b100010, 0b1000000}, 

    {0b00000, 0b1000010, 0b1111110, 0b1000000, 0b00000}, 

    {0b1111110, 0b00010, 0b01100, 0b00010, 0b1111100}, 

    {0b1111110, 0b00010, 0b00010, 0b00010, 0b1111100}, 

    {0b111100, 0b1000010, 0b1000010, 0b1000010, 0b111100}, 

    {0b1111110, 0b01010, 0b01010, 0b01010, 0b00100}, 

    {0b00100, 0b01010, 0b01010, 0b01010, 0b1111110}, 

    {0b1111110, 0b00010, 0b00010, 0b00010, 0b00100}, 

    {0b1001100, 0b1001010, 0b1010010, 0b1010010, 0b110010}, 

    {0b00100, 0b00100, 0b111110, 0b1000100, 0b100100}, 

    {0b111110, 0b1000000, 0b1000000, 0b1000000, 0b1111110}, 

    {0b11110, 0b100000, 0b1000000, 0b100000, 0b11110}, 

    {0b111110, 0b1000000, 0b110000, 0b1000000, 0b111110}, 

    {0b1000010, 0b100100, 0b11000, 0b100100, 0b1000010}, 

    {0b1000110, 0b1001000, 0b1001000, 0b1001000, 0b111110}, 

    {0b1100010, 0b1010010, 0b1001010, 0b1000110, 0b1000010}, 

    {0b00000, 0b1100000, 0b1100000, 0b00000, 0b00000}, 

    {0b00000, 0b00000, 0b00000, 0b00000, 0b00000}  

};

static void micro_delay(uint32_t microseconds);
static void i2c_start(pin_t scl, pin_t sda);
static void i2c_stop(pin_t scl, pin_t sda);
static bool i2c_write_byte(pin_t scl, pin_t sda, uint8_t data);
static void oled_send_command_batch(sh1107_state_t *state, uint8_t cmd1, uint8_t cmd2, uint8_t cmd3, uint8_t cmd4);
static void oled_set_pixel(sh1107_state_t *state, int x, int y, bool on);
static void oled_update_column(sh1107_state_t *state, int x, int start_page, int end_page);
static void oled_update_row(sh1107_state_t *state, int page, int start_x, int end_x);
static void oled_init(sh1107_state_t *state);
static void oled_clear(sh1107_state_t *state);
static int get_font_index(char c);
static void oled_draw_text(sh1107_state_t *state, const char *text, uint8_t x, uint8_t page, bool is_button_text);
static void oled_draw_button(sh1107_state_t *state, const char *text, uint8_t x, uint8_t page);
static void update_button_fill(sh1107_state_t *state, int button_index, bool fill);
static int find_button_at_position(sh1107_state_t *state, int x, int y);
static void update_callback(void *user_data);

static void micro_delay(uint32_t microseconds) {
  volatile uint32_t count = microseconds * 3;
  while (count--) {
    __asm__("nop");
  }
}

static void i2c_start(pin_t scl, pin_t sda) {
  pin_write(sda, HIGH);
  pin_write(scl, HIGH);
  micro_delay(1);
  pin_write(sda, LOW);
  micro_delay(1);
  pin_write(scl, LOW);
}

static void i2c_stop(pin_t scl, pin_t sda) {
  pin_write(sda, LOW);
  pin_write(scl, HIGH);
  micro_delay(1);
  pin_write(sda, HIGH);
  micro_delay(1);
}

static bool i2c_write_byte(pin_t scl, pin_t sda, uint8_t data) {
  for (int i = 7; i >= 0; i--) {
    pin_write(sda, (data >> i) & 1);
    micro_delay(1);
    pin_write(scl, HIGH);
    micro_delay(1);
    pin_write(scl, LOW);
  }

  pin_mode(sda, INPUT_PULLUP);
  pin_write(scl, HIGH);
  micro_delay(1);
  bool ack = !pin_read(sda);
  pin_write(scl, LOW);
  pin_mode(sda, OUTPUT);

  return ack;
}

static void oled_send_command_batch(sh1107_state_t *state, uint8_t cmd1, uint8_t cmd2, uint8_t cmd3, uint8_t cmd4) {
  i2c_start(state->scl_pin, state->sda_pin);
  i2c_write_byte(state->scl_pin, state->sda_pin, state->i2c_address << 1);
  i2c_write_byte(state->scl_pin, state->sda_pin, 0x00);

  i2c_write_byte(state->scl_pin, state->sda_pin, cmd1);
  if (cmd2 != 0xFF) i2c_write_byte(state->scl_pin, state->sda_pin, cmd2);
  if (cmd3 != 0xFF) i2c_write_byte(state->scl_pin, state->sda_pin, cmd3);
  if (cmd4 != 0xFF) i2c_write_byte(state->scl_pin, state->sda_pin, cmd4);

  i2c_stop(state->scl_pin, state->sda_pin);
}

static void oled_set_pixel(sh1107_state_t *state, int x, int y, bool on) {
  if (x < 0 || x >= OLED_WIDTH || y < 0 || y >= OLED_HEIGHT) {
    return;
  }

  int page = y / 8;
  int bit = y % 8;
  int index = page * OLED_WIDTH + x;

  uint8_t button_text_bit = state->button_text_inverted[index] & (1 << bit);

  if (on) {
    if (button_text_bit) {
      return;
    }

    if (state->cursor_inverted) {
      state->framebuffer[index] &= ~(1 << bit);
    } else {
      state->framebuffer[index] |= (1 << bit);
    }
  } else {
    uint8_t original_text = state->textbuffer[index];
    uint8_t original_button = state->buttonbuffer[index];

    if (button_text_bit) {
      if (state->cursor_inverted) {
        state->framebuffer[index] &= ~(1 << bit);
      } else {
        state->framebuffer[index] |= (1 << bit);
      }
    } else if (original_button & (1 << bit)) {
      state->framebuffer[index] |= (1 << bit);
    } else if (original_text & (1 << bit)) {
      state->framebuffer[index] |= (1 << bit);
    } else {
      state->framebuffer[index] &= ~(1 << bit);
    }
  }

  oled_send_command_batch(state, 0x21, x, x, 0xFF);
  oled_send_command_batch(state, 0x22, page, page, 0xFF);

  i2c_start(state->scl_pin, state->sda_pin);
  i2c_write_byte(state->scl_pin, state->sda_pin, state->i2c_address << 1);
  i2c_write_byte(state->scl_pin, state->sda_pin, 0x40);
  i2c_write_byte(state->scl_pin, state->sda_pin, state->framebuffer[index]);
  i2c_stop(state->scl_pin, state->sda_pin);
}

static void oled_update_column(sh1107_state_t *state, int x, int start_page, int end_page) {
  oled_send_command_batch(state, 0x21, x, x, 0xFF);
  oled_send_command_batch(state, 0x22, start_page, end_page, 0xFF);

  i2c_start(state->scl_pin, state->sda_pin);
  i2c_write_byte(state->scl_pin, state->sda_pin, state->i2c_address << 1);
  i2c_write_byte(state->scl_pin, state->sda_pin, 0x40);

  for (int page = start_page; page <= end_page; page++) {
    int index = page * OLED_WIDTH + x;
    i2c_write_byte(state->scl_pin, state->sda_pin, state->framebuffer[index]);
  }

  i2c_stop(state->scl_pin, state->sda_pin);
}

static void oled_update_row(sh1107_state_t *state, int page, int start_x, int end_x) {
  oled_send_command_batch(state, 0x21, start_x, end_x, 0xFF);
  oled_send_command_batch(state, 0x22, page, page, 0xFF);

  i2c_start(state->scl_pin, state->sda_pin);
  i2c_write_byte(state->scl_pin, state->sda_pin, state->i2c_address << 1);
  i2c_write_byte(state->scl_pin, state->sda_pin, 0x40);

  for (int x = start_x; x <= end_x; x++) {
    int index = page * OLED_WIDTH + x;
    i2c_write_byte(state->scl_pin, state->sda_pin, state->framebuffer[index]);
  }

  i2c_stop(state->scl_pin, state->sda_pin);
}

static void oled_init(sh1107_state_t *state) {
  oled_send_command_batch(state, 0xAE, 0xD5, 0x80, 0xA8);
  oled_send_command_batch(state, 0x3F, 0xD3, 0x00, 0x40);
  oled_send_command_batch(state, 0x8D, 0x14, 0x20, 0x00);
  oled_send_command_batch(state, 0xA1, 0xC8, 0xDA, 0x12);
  oled_send_command_batch(state, 0x81, 0x7F, 0xD9, 0xF1);
  oled_send_command_batch(state, 0xDB, 0x40, 0xA4, 0xA6);
  oled_send_command_batch(state, 0xAF, 0xFF, 0xFF, 0xFF);

  state->initialized = true;
  state->display_on = true;
  state->contrast = 0x7F;
  state->invert = false;
  state->cursor_inverted = false;
}

static void oled_clear(sh1107_state_t *state) {
  memset(state->framebuffer, 0, sizeof(state->framebuffer));
  memset(state->textbuffer, 0, sizeof(state->textbuffer));
  memset(state->buttonbuffer, 0, sizeof(state->buttonbuffer));
  memset(state->button_text_inverted, 0, sizeof(state->button_text_inverted));

  oled_send_command_batch(state, 0x21, 0x00, 0x7F, 0xFF);
  oled_send_command_batch(state, 0x22, 0x00, 0x07, 0xFF);

  i2c_start(state->scl_pin, state->sda_pin);
  i2c_write_byte(state->scl_pin, state->sda_pin, state->i2c_address << 1);
  i2c_write_byte(state->scl_pin, state->sda_pin, 0x40);

  for (int i = 0; i < OLED_WIDTH * OLED_PAGES; i++) {
    i2c_write_byte(state->scl_pin, state->sda_pin, 0x00);
  }

  i2c_stop(state->scl_pin, state->sda_pin);
}

static int get_font_index(char c) {
    if (c >= 'a' && c <= 'z') {
        return c - 'a';  
    } else if (c == '.') {
        return 26;  
    } else if (c == ' ') {
        return 27;  
    }
    return -1;  
}

static void oled_draw_text(sh1107_state_t *state, const char *text, uint8_t x, uint8_t page, bool is_button_text) {
  uint8_t cursor_x = x;

  for (int i = 0; text[i] != '\0'; i++) {
    char c = text[i];
    int font_index = get_font_index(c);

    if (font_index == -1) {
        font_index = 27;
    }

    for (int col = 0; col < 5; col++) {
      uint8_t col_data = font_5x7[font_index][col];

      for (int bit = 0; bit < 7; bit++) {
        if (col_data & (1 << bit)) {
          int index = page * OLED_WIDTH + cursor_x + col;
          state->framebuffer[index] |= (1 << bit);
          state->textbuffer[index] |= (1 << bit);

          if (is_button_text) {
            state->button_text_inverted[index] |= (1 << bit);
          }
        }
      }

      oled_send_command_batch(state, 0x21, cursor_x + col, cursor_x + col, 0xFF);
      oled_send_command_batch(state, 0x22, page, page, 0xFF);

      i2c_start(state->scl_pin, state->sda_pin);
      i2c_write_byte(state->scl_pin, state->sda_pin, state->i2c_address << 1);
      i2c_write_byte(state->scl_pin, state->sda_pin, 0x40);
      i2c_write_byte(state->scl_pin, state->sda_pin, font_5x7[font_index][col]);
      i2c_stop(state->scl_pin, state->sda_pin);
    }

    cursor_x += 6;
  }
}

static void oled_draw_button(sh1107_state_t *state, const char *text, uint8_t x, uint8_t page) {
  if (state->button_count >= MAX_BUTTONS) {
    return; 
  }

  int text_width = strlen(text) * 6;
  int button_width = text_width + 8;
  int button_x = x - 4;
  int button_y = page * 8 - 2;

  int button_index = state->button_count;
  state->buttons[button_index].start_x = button_x;
  state->buttons[button_index].start_y = button_y;
  state->buttons[button_index].width = button_width;
  state->buttons[button_index].page = page;
  state->buttons[button_index].is_filled = false;
  strncpy(state->buttons[button_index].text, text, sizeof(state->buttons[button_index].text) - 1);
  state->buttons[button_index].text[sizeof(state->buttons[button_index].text) - 1] = '\0';
  state->button_count++;

  if (button_x < 0) button_x = 0;
  if (button_x + button_width > OLED_WIDTH) button_width = OLED_WIDTH - button_x;

  int end_y = button_y + BUTTON_HEIGHT - 1;
  if (end_y >= OLED_HEIGHT) end_y = OLED_HEIGHT - 1;

  for (int y = button_y; y <= end_y; y++) {
    for (int x_pos = button_x; x_pos < button_x + button_width; x_pos++) {
      int page_idx = y / 8;
      int bit = y % 8;
      int index = page_idx * OLED_WIDTH + x_pos;

      bool is_border = (y == button_y || y == end_y || 
                       x_pos == button_x || x_pos == button_x + button_width - 1);

      if (is_border) {
        state->framebuffer[index] |= (1 << bit);
        state->buttonbuffer[index] |= (1 << bit);
      }
    }
  }

  for (int y = button_y; y <= end_y; y++) {
    int page_idx = y / 8;
    int start_x = button_x;
    int end_x = button_x + button_width - 1;

    if (y == button_y || y == end_y) {
      oled_update_row(state, page_idx, start_x, end_x);
    } else {
      oled_update_column(state, start_x, page_idx, page_idx);
      oled_update_column(state, end_x, page_idx, page_idx);
    }
  }

  oled_draw_text(state, text, x, page, true);
}

static void update_button_fill(sh1107_state_t *state, int button_index, bool fill) {
  if (button_index < 0 || button_index >= state->button_count) {
    return;
  }

  int button_y = state->buttons[button_index].start_y;
  int button_x = state->buttons[button_index].start_x;
  int button_width = state->buttons[button_index].width;
  int end_y = button_y + BUTTON_HEIGHT - 1;

  state->buttons[button_index].is_filled = fill;

  for (int y = button_y + 1; y < end_y; y++) {
    for (int x = button_x + 1; x < button_x + button_width - 1; x++) {
      int page_idx = y / 8;
      int bit = y % 8;
      int index = page_idx * OLED_WIDTH + x;

      if (fill) {
        state->framebuffer[index] |= (1 << bit);
        state->buttonbuffer[index] |= (1 << bit);
      } else {
        state->framebuffer[index] &= ~(1 << bit);
        state->buttonbuffer[index] &= ~(1 << bit);
      }
    }
  }

  for (int y = button_y + 1; y < end_y; y++) {
    int page_idx = y / 8;
    oled_update_row(state, page_idx, button_x + 1, button_x + button_width - 2);
  }

  int text_x = button_x + 4;
  int text_page = state->buttons[button_index].page;
  const char* text = state->buttons[button_index].text;

  for (int i = 0; text[i] != '\0'; i++) {
    char c = text[i];
    int font_index = get_font_index(c);

    if (font_index == -1) {
      font_index = 27;
    }

    for (int col = 0; col < 5; col++) {
      uint8_t col_data = font_5x7[font_index][col];
      int x_pos = text_x + i * 6 + col;

      for (int bit = 0; bit < 7; bit++) {
        if (col_data & (1 << bit)) {
          int index = text_page * OLED_WIDTH + x_pos;

          if (fill) {
            state->framebuffer[index] &= ~(1 << bit);
          } else {
            state->framebuffer[index] |= (1 << bit);
          }
        }
      }

      oled_send_command_batch(state, 0x21, x_pos, x_pos, 0xFF);
      oled_send_command_batch(state, 0x22, text_page, text_page, 0xFF);

      i2c_start(state->scl_pin, state->sda_pin);
      i2c_write_byte(state->scl_pin, state->sda_pin, state->i2c_address << 1);
      i2c_write_byte(state->scl_pin, state->sda_pin, 0x40);

      uint8_t display_data;
      if (fill) {
        display_data = ~font_5x7[font_index][col];
      } else {
        display_data = font_5x7[font_index][col];
      }
      i2c_write_byte(state->scl_pin, state->sda_pin, display_data);

      i2c_stop(state->scl_pin, state->sda_pin);
    }
  }
}

static int find_button_at_position(sh1107_state_t *state, int x, int y) {
  for (int i = 0; i < state->button_count; i++) {
    if (x >= state->buttons[i].start_x && 
        x < state->buttons[i].start_x + state->buttons[i].width &&
        y >= state->buttons[i].start_y && 
        y < state->buttons[i].start_y + BUTTON_HEIGHT) {
      return i;
    }
  }
  return -1; 
}

static void update_callback(void *user_data) {
  sh1107_state_t *state = (sh1107_state_t*)user_data;

  bool a_pressed = !pin_read(state->Abutton);

  if (state->current_screen == SCREEN_LOCKED && a_pressed && !state->a_button_was_pressed) {
    int current_button = find_button_at_position(state, state->pixel_x, state->pixel_y);

    if (current_button == 0) {

      state->current_screen = SCREEN_HOME;
      oled_clear(state);
      oled_draw_text(state, "loading...", 35, 3, false);

      state->button_count = 0;
      state->cursor_inverted = false; 

      oled_set_pixel(state, state->pixel_x, state->pixel_y, true);

      state->a_button_was_pressed = true;

      float timer_interval_float = 1000.0f / PIXELS_PER_SECOND;
      uint32_t timer_interval;
      if (timer_interval_float < 10.0f) {
        timer_interval = 10;  
      } else {
        timer_interval = (uint32_t)timer_interval_float;
      }
      timer_start(state->update_timer, timer_interval, false);
      return;
    }
  }

  state->a_button_was_pressed = a_pressed;

  int old_x = state->pixel_x;
  int old_y = state->pixel_y;

  bool up_pressed = !pin_read(state->up_pin);
  bool down_pressed = !pin_read(state->down_pin);
  bool left_pressed = !pin_read(state->left_pin);
  bool right_pressed = !pin_read(state->right_pin);

  if (up_pressed && state->pixel_y > 0) {
    state->pixel_y--;
  }
  if (down_pressed && state->pixel_y < OLED_HEIGHT - 1) {
    state->pixel_y++;
  }
  if (left_pressed && state->pixel_x > 0) {
    state->pixel_x--;
  }
  if (right_pressed && state->pixel_x < OLED_WIDTH - 1) {
    state->pixel_x++;
  }

  if (old_x != state->pixel_x || old_y != state->pixel_y) {

    oled_set_pixel(state, old_x, old_y, false);

    if (state->current_screen == SCREEN_LOCKED) {
      int current_button = find_button_at_position(state, state->pixel_x, state->pixel_y);
      int old_button = find_button_at_position(state, old_x, old_y);

      state->cursor_inverted = (current_button != -1);

      if (old_button != current_button) {
        if (old_button != -1) {
          update_button_fill(state, old_button, false);
        }
        if (current_button != -1) {
          update_button_fill(state, current_button, true);
        }
      }
    } else {

      state->cursor_inverted = false;
    }

    oled_set_pixel(state, state->pixel_x, state->pixel_y, true);
  }

  state->old_pixel_x = state->pixel_x;
  state->old_pixel_y = state->pixel_y;

  float timer_interval_float = 1000.0f / PIXELS_PER_SECOND;
  uint32_t timer_interval;

  if (timer_interval_float < 10.0f) {
    timer_interval = 10;  
  } else {
    timer_interval = (uint32_t)timer_interval_float;
  }

  timer_start(state->update_timer, timer_interval, false);
}

void chip_init(void)
{
  sh1107_state_t *state = malloc(sizeof(sh1107_state_t));
  memset(state, 0, sizeof(sh1107_state_t));

  chip = state;

  state->scl_pin = pin_init("SCL", OUTPUT);
  state->sda_pin = pin_init("SDA", OUTPUT);
  state->vcc_pin = pin_init("VCC_OUT", OUTPUT);
  state->gnd_pin = pin_init("GND_OUT", OUTPUT);

  state->up_pin = pin_init("Up", INPUT_PULLUP);
  state->down_pin = pin_init("Down", INPUT_PULLUP);
  state->left_pin = pin_init("Left", INPUT_PULLUP);
  state->right_pin = pin_init("Right", INPUT_PULLUP);

  state->Abutton = pin_init("A", INPUT_PULLUP);
  state->Bbutton = pin_init("B", INPUT_PULLUP);

  pin_write(state->vcc_pin, HIGH);
  pin_write(state->gnd_pin, LOW);
  pin_write(state->scl_pin, HIGH);
  pin_write(state->sda_pin, HIGH);

  state->pixel_x = OLED_WIDTH / 2;
  state->pixel_y = OLED_HEIGHT / 2;
  state->old_pixel_x = state->pixel_x;
  state->old_pixel_y = state->pixel_y;

  state->i2c_address = 0x3C;
  state->initialized = false;
  state->cursor_inverted = false;
  state->button_count = 0; 
  state->current_screen = SCREEN_LOCKED;
  state->a_button_was_pressed = false;

  micro_delay(10);

  oled_init(state);
  oled_clear(state);

  state->current_screen = SCREEN_LOCKED;
  oled_draw_text(state, "press unlock to", 1, 1, false);
  oled_draw_text(state, "start the os", 1, 2, false);
  oled_draw_button(state, "unlock", 7, 6);

  oled_set_pixel(state, state->pixel_x, state->pixel_y, true);

  const timer_config_t update_timer_config = {
    .callback = update_callback,
    .user_data = state,
  };
  state->update_timer = timer_init(&update_timer_config);

  float timer_interval_float = 1000.0f / PIXELS_PER_SECOND;
  uint32_t timer_interval;

  if (timer_interval_float < 10.0f) {
    timer_interval = 10;  
  } else {
    timer_interval = (uint32_t)timer_interval_float;
  }

  timer_start(state->update_timer, timer_interval, false);
}
#!/usr/bin/env python3
"""
Wokwi C to Verilog Compiler - Optimized for I2C OLED displays
"""

import sys
import re
import os
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional

class I2COledParser:
    """Parser optimized for I2C OLED displays (SH1107, SSD1306, etc.)"""
    
    def parse(self, content: str) -> Dict:
        content = self._remove_comments(content)
        
        return {
            'defines': self._extract_defines(content),
            'pins': self._extract_pins(content),
            'struct_vars': self._extract_struct_variables(content),
            'is_i2c': True,
            'has_oled': 'sh1107' in content.lower() or 'oled' in content.lower(),
            'has_font': 'font_5x7' in content,
            'has_buttons': 'BUTTON_HEIGHT' in content,
        }
    
    def _remove_comments(self, content: str) -> str:
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'//.*', '', content)
        return content
    
    def _extract_defines(self, content: str) -> Dict[str, str]:
        defines = {}
        pattern = r'#define\s+(\w+)\s+([^\s;]+)'
        
        for name, value in re.findall(pattern, content):
            if '(' not in name and '[' not in value:
                defines[name] = value
        
        return defines
    
    def _extract_pins(self, content: str) -> List[Dict]:
        pins = []
        pin_names = re.findall(r'pin_t\s+(\w+)\s*[;=]', content)
        
        for pin_name in pin_names:
            pins.append(self._classify_pin(pin_name))
        
        return pins
    
    def _classify_pin(self, pin_name: str) -> Dict:
        pin_upper = pin_name.upper()
        
        # I2C pins
        if pin_upper in ['SCL', 'SDA']:
            return {
                'name': pin_name,
                'direction': 'output',
                'type': 'reg',
                'is_i2c': True
            }
        
        # Power pins
        if pin_upper in ['VCC', 'VCC_OUT', 'VDD']:
            return {
                'name': pin_name,
                'direction': 'output',
                'type': 'reg',
                'is_power': True
            }
        
        if pin_upper in ['GND', 'GND_OUT']:
            return {
                'name': pin_name,
                'direction': 'output', 
                'type': 'reg',
                'is_power': True
            }
        
        # Button pins (inputs)
        button_pins = ['UP', 'DOWN', 'LEFT', 'RIGHT', 'A', 'B', 'BUTTON']
        if any(x in pin_upper for x in button_pins):
            return {
                'name': pin_name,
                'direction': 'input',
                'type': 'wire',
                'is_button': True
            }
        
        # Default: output
        return {
            'name': pin_name,
            'direction': 'output',
            'type': 'reg',
            'is_i2c': False
        }
    
    def _extract_struct_variables(self, content: str) -> List[Dict]:
        variables = []
        
        # Find sh1107_state_t struct
        pattern = r'typedef\s+struct\s*\{([^}]+)\}\s*sh1107_state_t\s*;'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            struct_body = match.group(1)
            lines = struct_body.split(';')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Match variable declarations
                var_match = re.match(r'(\w+(?:\s+\*?)?)\s+(\w+)(?:\[(\d+)\])?', line)
                if var_match:
                    c_type = var_match.group(1).strip()
                    name = var_match.group(2)
                    array_size = var_match.group(3)
                    
                    if c_type == 'pin_t':
                        continue
                    
                    # Get Verilog info
                    width, vtype = self._c_type_to_verilog(c_type)
                    
                    variables.append({
                        'name': name,
                        'c_type': c_type,
                        'verilog_type': vtype,
                        'width': width,
                        'is_array': array_size is not None,
                        'array_size': int(array_size) if array_size else 1,
                        'is_buffer': 'buffer' in name.lower() or 'framebuffer' in name.lower()
                    })
        
        return variables
    
    def _c_type_to_verilog(self, c_type: str) -> Tuple[str, str]:
        type_map = {
            'uint8_t': ('[7:0]', 'reg'),
            'int8_t': ('[7:0]', 'reg'),
            'char': ('[7:0]', 'reg'),
            'uint16_t': ('[15:0]', 'reg'),
            'int16_t': ('[15:0]', 'reg'),
            'uint32_t': ('[31:0]', 'reg'),
            'int32_t': ('[31:0]', 'reg'),
            'bool': ('', 'reg'),
            'timer_t': ('', 'wire'),
        }
        
        if c_type in type_map:
            return type_map[c_type]
        
        # Check for arrays
        if '[' in c_type:
            base_type = c_type.split('[')[0].strip()
            if base_type in type_map:
                return type_map[base_type]
            return ('[7:0]', 'reg')
        
        return ('', 'reg')

class I2COledGenerator:
    """Generator for I2C OLED displays"""
    
    def __init__(self, info: Dict, module_name: str):
        self.info = info
        self.module_name = module_name
    
    def generate(self) -> str:
        parts = []
        parts.append(self._header())
        parts.append(self._module_declaration())
        
        params = self._parameters()
        if params:
            parts.append(params)
        
        parts.append(self._internal_signals())
        
        power_assigns = self._power_assignments()
        if power_assigns:
            parts.append(power_assigns)
        
        parts.append(self._clock_reset())
        
        if self.info['is_i2c']:
            parts.append(self._i2c_interface())
        
        if self.info['has_oled']:
            parts.append(self._oled_controller())
        
        if self.info['has_buttons']:
            parts.append(self._button_logic())
        
        parts.append(self._state_machine())
        parts.append(self._main_logic())
        parts.append("endmodule")
        
        return '\n\n'.join(parts)
    
    def _header(self) -> str:
        return f"""`timescale 1ns / 1ps
// ============================================================
// Generated by Wokwi2Verilog - I2C OLED Version
// Module: {self.module_name}
// Display: SH1107 OLED with I2C interface
// ============================================================"""
    
    def _module_declaration(self) -> str:
        ports = []
        
        # Group pins
        power_pins = [p for p in self.info['pins'] if p.get('is_power', False)]
        i2c_pins = [p for p in self.info['pins'] if p.get('is_i2c', False)]
        button_pins = [p for p in self.info['pins'] if p.get('is_button', False)]
        other_pins = [p for p in self.info['pins'] if not any([
            p.get('is_power', False), p.get('is_i2c', False), p.get('is_button', False)
        ])]
        
        # Clock and reset
        ports.append("    // Clock and Reset")
        ports.append("    input wire clk,")
        ports.append("    input wire rst_n")
        
        # Add comma if we have more ports
        if power_pins or i2c_pins or button_pins or other_pins:
            ports[-1] = ports[-1] + ","
        
        # Power pins
        if power_pins:
            ports.append("")
            ports.append("    // Power Pins")
            for i, pin in enumerate(power_pins):
                comma = "," if i < len(power_pins) - 1 or i2c_pins or button_pins or other_pins else ""
                ports.append(f"    output reg {pin['name']}{comma}")
        
        # I2C pins
        if i2c_pins:
            ports.append("")
            ports.append("    // I2C Interface")
            for i, pin in enumerate(i2c_pins):
                comma = "," if i < len(i2c_pins) - 1 or button_pins or other_pins else ""
                ports.append(f"    output reg {pin['name']}{comma}")
        
        # Button pins (inputs)
        if button_pins:
            ports.append("")
            ports.append("    // Button Inputs")
            for i, pin in enumerate(button_pins):
                comma = "," if i < len(button_pins) - 1 or other_pins else ""
                ports.append(f"    input wire {pin['name']}{comma}")
        
        # Other pins
        if other_pins:
            ports.append("")
            ports.append("    // Other Pins")
            for i, pin in enumerate(other_pins):
                comma = "," if i < len(other_pins) - 1 else ""
                vtype = "reg" if pin['type'] == 'reg' else "wire"
                direction = "output" if pin['direction'] == 'output' else "input"
                ports.append(f"    {direction} {vtype} {pin['name']}{comma}")
        
        # Remove trailing comma
        port_text = '\n'.join(ports)
        port_text = port_text.rstrip(',')
        
        return f"module {self.module_name} (\n{port_text}\n);"
    
    def _parameters(self) -> str:
        if not self.info['defines']:
            return ""
        
        params = []
        for name, value in self.info['defines'].items():
            # Convert to Verilog
            if value.startswith('0x'):
                hex_val = value[2:]
                if len(hex_val) <= 2:
                    verilog_value = f"8'h{hex_val.upper()}"
                else:
                    verilog_value = f"16'h{hex_val.upper()}"
            elif value.isdigit():
                verilog_value = value
            elif value.replace('.', '').replace('f', '').isdigit():
                # Handle float constants
                verilog_value = "32'd" + value.replace('f', '').replace('.', '')
            else:
                # Skip expressions for now
                continue
            
            params.append(f"    parameter {name} = {verilog_value};")
        
        return "    // Display Parameters\n" + '\n'.join(params)
    
    def _internal_signals(self) -> str:
        signals = ["    // Internal Signals"]
        
        # Add framebuffers and state variables
        for var in self.info['struct_vars']:
            if var['is_buffer']:
                # Framebuffers
                if var['array_size'] > 1:
                    signals.append(f"    {var['verilog_type']} {var['width']} {var['name']}[0:{var['array_size']-1}];")
                else:
                    signals.append(f"    {var['verilog_type']} {var['width']} {var['name']};")
            else:
                # Regular variables
                if var['is_array']:
                    signals.append(f"    {var['verilog_type']} {var['width']} {var['name']}[0:{var['array_size']-1}];")
                else:
                    if var['width']:
                        signals.append(f"    {var['verilog_type']} {var['width']} {var['name']};")
                    else:
                        signals.append(f"    {var['verilog_type']} {var['name']};")
        
        # Add common OLED signals
        common_signals = [
            "    reg [31:0] counter;",
            "    reg [6:0] i2c_address;",
            "    reg i2c_start_sent;",
            "    reg i2c_stop_sent;",
            "    reg [7:0] i2c_data_out;",
            "    reg i2c_write_active;",
            "    reg [2:0] i2c_bit_counter;",
            "    reg [7:0] oled_command;",
            "    reg [15:0] pixel_x;",
            "    reg [15:0] pixel_y;",
            "    reg [15:0] old_pixel_x;",
            "    reg [15:0] old_pixel_y;",
            "    reg cursor_inverted;",
            "    reg [1:0] current_screen;",
            "    reg a_button_was_pressed;",
            "    reg [4:0] button_count;",
            "    // Button structures",
            "    reg [15:0] button_start_x [0:9];",
            "    reg [15:0] button_start_y [0:9];",
            "    reg [15:0] button_width [0:9];",
            "    reg [7:0] button_page [0:9];",
            "    reg button_is_filled [0:9];",
        ]
        
        signals.extend(common_signals)
        
        # Add font ROM if present
        if self.info['has_font']:
            signals.append("    // Font ROM (5x7 font)")
            signals.append("    reg [7:0] font_5x7 [0:27][0:4];")
        
        return '\n'.join(signals)
    
    def _power_assignments(self) -> str:
        assigns = []
        for pin in self.info['pins']:
            if pin.get('is_power', False):
                if 'VCC' in pin['name'].upper():
                    assigns.append(f"    assign {pin['name']} = 1'b1;")
                elif 'GND' in pin['name'].upper():
                    assigns.append(f"    assign {pin['name']} = 1'b0;")
        
        if assigns:
            return "    // Power Pin Assignments\n" + '\n'.join(assigns)
        return ""
    
    def _clock_reset(self) -> str:
        return """    // ============================================
    // Clock and Reset
    // ============================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            counter <= 32'd0;
            pixel_x <= 16'd64;  // Center of display
            pixel_y <= 16'd32;
            old_pixel_x <= 16'd64;
            old_pixel_y <= 16'd32;
            cursor_inverted <= 1'b0;
            current_screen <= 2'b00;  // SCREEN_LOCKED
            a_button_was_pressed <= 1'b0;
            button_count <= 5'd0;
            i2c_address <= 7'h3C;  // SH1107 default address
        end else begin
            counter <= counter + 1;
        end
    end"""
    
    def _i2c_interface(self) -> str:
        return """    // ============================================
    // I2C Master Interface
    // ============================================
    reg i2c_scl;
    reg i2c_sda;
    
    assign SCL = i2c_scl;
    assign SDA = i2c_sda;
    
    // I2C state machine
    reg [2:0] i2c_state;
    localparam [2:0]
        I2C_IDLE      = 3'd0,
        I2C_START     = 3'd1,
        I2C_ADDR      = 3'd2,
        I2C_DATA      = 3'd3,
        I2C_STOP      = 3'd4;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            i2c_state <= I2C_IDLE;
            i2c_scl <= 1'b1;
            i2c_sda <= 1'b1;
            i2c_bit_counter <= 3'd0;
            i2c_write_active <= 1'b0;
        end else begin
            case (i2c_state)
                I2C_IDLE: begin
                    if (i2c_write_active) begin
                        i2c_state <= I2C_START;
                        i2c_scl <= 1'b1;
                        i2c_sda <= 1'b1;
                    end
                end
                I2C_START: begin
                    i2c_sda <= 1'b0;
                    i2c_state <= I2C_ADDR;
                    i2c_bit_counter <= 3'd7;
                end
                I2C_ADDR: begin
                    // Send 7-bit address + write bit (0)
                    i2c_scl <= 1'b0;
                    i2c_sda <= {i2c_address, 1'b0}[i2c_bit_counter];
                    if (counter[0]) begin
                        i2c_scl <= 1'b1;
                        if (i2c_bit_counter == 3'd0) begin
                            i2c_state <= I2C_DATA;
                            i2c_bit_counter <= 3'd7;
                        end else begin
                            i2c_bit_counter <= i2c_bit_counter - 1;
                        end
                    end
                end
                I2C_DATA: begin
                    i2c_scl <= 1'b0;
                    i2c_sda <= i2c_data_out[i2c_bit_counter];
                    if (counter[0]) begin
                        i2c_scl <= 1'b1;
                        if (i2c_bit_counter == 3'd0) begin
                            i2c_state <= I2C_STOP;
                        end else begin
                            i2c_bit_counter <= i2c_bit_counter - 1;
                        end
                    end
                end
                I2C_STOP: begin
                    i2c_scl <= 1'b0;
                    i2c_sda <= 1'b0;
                    if (counter[0]) begin
                        i2c_scl <= 1'b1;
                        i2c_sda <= 1'b1;
                        i2c_state <= I2C_IDLE;
                        i2c_write_active <= 1'b0;
                    end
                end
            endcase
        end
    end"""
    
    def _oled_controller(self) -> str:
        return """    // ============================================
    // OLED Display Controller
    // ============================================
    reg [3:0] oled_state;
    localparam [3:0]
        OLED_IDLE     = 4'd0,
        OLED_INIT     = 4'd1,
        OLED_CLEAR    = 4'd2,
        OLED_DRAW     = 4'd3,
        OLED_UPDATE   = 4'd4;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            oled_state <= OLED_INIT;
            i2c_write_active <= 1'b0;
            i2c_data_out <= 8'h00;
        end else begin
            case (oled_state)
                OLED_INIT: begin
                    // Send initialization commands
                    if (!i2c_write_active) begin
                        i2c_data_out <= 8'hAE;  // Display off
                        i2c_write_active <= 1'b1;
                        oled_state <= OLED_CLEAR;
                    end
                end
                OLED_CLEAR: begin
                    // Clear display
                    if (!i2c_write_active && counter[10:0] == 11'h7FF) begin
                        i2c_data_out <= 8'h00;  // Clear data
                        i2c_write_active <= 1'b1;
                        if (counter[15:0] == 16'hFFFF) begin
                            oled_state <= OLED_DRAW;
                        end
                    end
                end
                OLED_DRAW: begin
                    // Drawing logic would go here
                    oled_state <= OLED_UPDATE;
                end
                OLED_UPDATE: begin
                    // Update display
                    if (counter[19:0] == 20'hFFFFF) begin
                        oled_state <= OLED_DRAW;
                    end
                end
            endcase
        end
    end
    
    // Framebuffer update logic
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            framebuffer <= 1024'h0;  // 128x64/8 = 1024 bytes
        end else begin
            // Update pixel at cursor position
            if (pixel_x != old_pixel_x || pixel_y != old_pixel_y) begin
                // Clear old pixel
                // Set new pixel
                old_pixel_x <= pixel_x;
                old_pixel_y <= pixel_y;
            end
        end
    end"""
    
    def _button_logic(self) -> str:
        return """    // ============================================
    // Button Input Processing
    // ============================================
    reg up_pressed;
    reg down_pressed;
    reg left_pressed;
    reg right_pressed;
    reg a_pressed;
    reg b_pressed;
    
    // Button debouncing
    reg [19:0] up_debounce;
    reg [19:0] down_debounce;
    reg [19:0] left_debounce;
    reg [19:0] right_debounce;
    reg [19:0] a_debounce;
    reg [19:0] b_debounce;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            up_pressed <= 1'b0;
            down_pressed <= 1'b0;
            left_pressed <= 1'b0;
            right_pressed <= 1'b0;
            a_pressed <= 1'b0;
            b_pressed <= 1'b0;
            up_debounce <= 20'd0;
            down_debounce <= 20'd0;
            left_debounce <= 20'd0;
            right_debounce <= 20'd0;
            a_debounce <= 20'd0;
            b_debounce <= 20'd0;
        end else begin
            // Debounce Up button
            if (!Up) begin
                if (up_debounce < 20'd1000000) up_debounce <= up_debounce + 1;
                else up_pressed <= 1'b1;
            end else begin
                up_debounce <= 20'd0;
                up_pressed <= 1'b0;
            end
            
            // Debounce Down button
            if (!Down) begin
                if (down_debounce < 20'd1000000) down_debounce <= down_debounce + 1;
                else down_pressed <= 1'b1;
            end else begin
                down_debounce <= 20'd0;
                down_pressed <= 1'b0;
            end
            
            // Debounce Left button
            if (!Left) begin
                if (left_debounce < 20'd1000000) left_debounce <= left_debounce + 1;
                else left_pressed <= 1'b1;
            end else begin
                left_debounce <= 20'd0;
                left_pressed <= 1'b0;
            end
            
            // Debounce Right button
            if (!Right) begin
                if (right_debounce < 20'd1000000) right_debounce <= right_debounce + 1;
                else right_pressed <= 1'b1;
            end else begin
                right_debounce <= 20'd0;
                right_pressed <= 1'b0;
            end
            
            // Debounce A button
            if (!A) begin
                if (a_debounce < 20'd1000000) a_debounce <= a_debounce + 1;
                else a_pressed <= 1'b1;
            end else begin
                a_debounce <= 20'd0;
                a_pressed <= 1'b0;
            end
            
            // Debounce B button
            if (!B) begin
                if (b_debounce < 20'd1000000) b_debounce <= b_debounce + 1;
                else b_pressed <= 1'b1;
            end else begin
                b_debounce <= 20'd0;
                b_pressed <= 1'b0;
            end
        end
    end
    
    // Cursor movement
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Already handled in reset
        end else begin
            if (up_pressed && pixel_y > 0) pixel_y <= pixel_y - 1;
            if (down_pressed && pixel_y < OLED_HEIGHT - 1) pixel_y <= pixel_y + 1;
            if (left_pressed && pixel_x > 0) pixel_x <= pixel_x - 1;
            if (right_pressed && pixel_x < OLED_WIDTH - 1) pixel_x <= pixel_x + 1;
        end
    end"""
    
    def _state_machine(self) -> str:
        return """    // ============================================
    // Screen State Machine
    // ============================================
    localparam [1:0]
        SCREEN_LOCKED = 2'b00,
        SCREEN_HOME   = 2'b01,
        SCREEN_MENU   = 2'b10;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_screen <= SCREEN_LOCKED;
        end else begin
            case (current_screen)
                SCREEN_LOCKED: begin
                    if (a_pressed && !a_button_was_pressed) begin
                        // Check if cursor is on "unlock" button
                        // For now, always go to HOME when A is pressed
                        current_screen <= SCREEN_HOME;
                        a_button_was_pressed <= 1'b1;
                    end
                end
                SCREEN_HOME: begin
                    // Home screen logic
                    if (b_pressed) begin
                        current_screen <= SCREEN_MENU;
                    end
                end
                SCREEN_MENU: begin
                    // Menu screen logic
                    if (b_pressed) begin
                        current_screen <= SCREEN_HOME;
                    end
                end
            endcase
            
            if (!a_pressed) begin
                a_button_was_pressed <= 1'b0;
            end
        end
    end"""
    
    def _main_logic(self) -> str:
        return """    // ============================================
    // Main Application Logic
    // ============================================
    
    // Button drawing logic
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Initialize first button (unlock)
            button_start_x[0] <= 16'd7;   // x position
            button_start_y[0] <= 16'd46;  // y position (page 6 * 8 - 2)
            button_width[0] <= 16'd36;    // text width + 8
            button_page[0] <= 8'd6;       // page number
            button_is_filled[0] <= 1'b0;
            button_count <= 5'd1;
        end else begin
            // Update button fill based on cursor position
            if (current_screen == SCREEN_LOCKED) begin
                // Check if cursor is over button 0
                if (pixel_x >= button_start_x[0] && 
                    pixel_x < button_start_x[0] + button_width[0] &&
                    pixel_y >= button_start_y[0] && 
                    pixel_y < button_start_y[0] + BUTTON_HEIGHT) begin
                    button_is_filled[0] <= 1'b1;
                    cursor_inverted <= 1'b1;
                end else begin
                    button_is_filled[0] <= 1'b0;
                    cursor_inverted <= 1'b0;
                end
            end else begin
                cursor_inverted <= 1'b0;
            end
        end
    end
    
    // Display update based on screen state
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Initial display
        end else if (counter[23:0] == 24'hFFFFFF) begin
            // Periodic display update
            case (current_screen)
                SCREEN_LOCKED: begin
                    // Display "press unlock to start the os"
                    // Button already drawn in initialization
                end
                SCREEN_HOME: begin
                    // Display "loading..."
                end
                SCREEN_MENU: begin
                    // Display menu options
                end
            endcase
        end
    end"""

def main():
    parser = argparse.ArgumentParser(description='I2C OLED Wokwi to Verilog Compiler')
    parser.add_argument('input', help='Input C file')
    parser.add_argument('-o', '--output', help='Output Verilog file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: File '{args.input}' not found")
        return 1
    
    try:
        with open(args.input, 'r') as f:
            content = f.read()
        
        parser = I2COledParser()
        info = parser.parse(content)
        
        module_name = Path(args.input).stem
        module_name = re.sub(r'[^a-zA-Z0-9_]', '_', module_name)
        if not module_name[0].isalpha():
            module_name = 'oled_' + module_name
        
        if args.verbose:
            print(f"Parsing {args.input}...")
            print(f"  Module: {module_name}")
            print(f"  Pins: {len(info['pins'])}")
            print(f"  Variables: {len(info['struct_vars'])}")
            print(f"  Display: SH1107 OLED")
            print(f"  Interface: I2C")
        
        generator = I2COledGenerator(info, module_name)
        verilog = generator.generate()
        
        output_file = args.output or f"{module_name}.v"
        with open(output_file, 'w') as f:
            f.write(verilog)
        
        print(f"✓ Generated {output_file}")
        print(f"  I2C OLED display controller ready")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
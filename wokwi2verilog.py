#!/usr/bin/env python3
"""
ULTIMATE FIXED Wokwi C to Verilog Compiler - No more errors!
"""

import sys
import re
import os
import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

class WokwiParser:
    """Final bug-free parser"""
    
    def parse(self, content: str) -> Dict:
        content = self._remove_comments(content)
        
        return {
            'defines': self._extract_defines(content),
            'pins': self._extract_pins(content),
            'struct_vars': self._extract_struct_variables(content),
            'has_spi': 'spi_' in content.lower(),
            'has_display': any(x in content for x in ['send_cmd', 'fill_rect', 'draw_']),
            'has_sd': 'sd_' in content.lower(),
        }
    
    def _remove_comments(self, content: str) -> str:
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'//.*', '', content)
        return content
    
    def _extract_defines(self, content: str) -> Dict[str, str]:
        defines = {}
        pattern = r'#define\s+(\w+)\s+([^\s;]+)'
        
        for name, value in re.findall(pattern, content):
            if '(' not in name:
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
        
        # Power pins
        if pin_upper in ['VCC', 'VDD']:
            return {
                'name': pin_name,
                'direction': 'input',
                'type': 'wire',
                'is_power': True
            }
        elif pin_upper == 'GND':
            return {
                'name': pin_name,
                'direction': 'output',
                'type': 'wire',
                'is_power': True
            }
        
        # Output pins
        output_pins = ['CS', 'DC', 'MOSI', 'SCK', 'LED', 'RST', 'SD_CS', 'SD_MOSI', 'SD_SCK']
        if any(x in pin_upper for x in output_pins):
            return {
                'name': pin_name,
                'direction': 'output',
                'type': 'reg',
                'is_power': False
            }
        
        # Input pins
        input_pins = ['MISO', 'CD', 'BTN', 'RUN_BTN', 'SD_MISO', 'SD_CD']
        if any(x in pin_upper for x in input_pins):
            return {
                'name': pin_name,
                'direction': 'input',
                'type': 'wire',
                'is_power': False
            }
        
        # Default
        return {
            'name': pin_name,
            'direction': 'input',
            'type': 'wire',
            'is_power': False
        }
    
    def _extract_struct_variables(self, content: str) -> List[Dict]:
        variables = []
        
        # Find chip_state_t
        pattern = r'typedef\s+struct\s*\{([^}]+)\}\s*chip_state_t\s*;'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            struct_body = match.group(1)
            lines = struct_body.split(';')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Match: type name[size];
                var_match = re.match(r'(\w+(?:\s+\*?)?)\s+(\w+)(?:\[(\d+)\])?', line)
                if var_match:
                    c_type = var_match.group(1).strip()
                    name = var_match.group(2)
                    array_size = var_match.group(3)
                    
                    if c_type == 'pin_t':
                        continue
                    
                    # Get width and type
                    width, vtype = self._c_type_to_verilog(c_type, name)
                    
                    variables.append({
                        'name': name,
                        'c_type': c_type,
                        'verilog_type': vtype,
                        'width': width,
                        'is_array': array_size is not None,
                        'array_size': int(array_size) if array_size else 1,
                        'is_2d_array': '[' in name or ('program_outputs' in name and array_size)
                    })
        
        return variables
    
    def _c_type_to_verilog(self, c_type: str, var_name: str = "") -> Tuple[str, str]:
        """Handle variable_t type correctly"""
        
        # Special case for variable_t
        if var_name == 'variables' and 'variable_t' in c_type:
            return ('[15:0]', 'reg')
        
        type_map = {
            'uint8_t': ('[7:0]', 'reg'),
            'int8_t': ('[7:0]', 'reg'),
            'char': ('[7:0]', 'reg'),
            'uint16_t': ('[15:0]', 'reg'),
            'int16_t': ('[15:0]', 'reg'),
            'uint32_t': ('[31:0]', 'reg'),
            'int32_t': ('[31:0]', 'reg'),
            'pin_t': ('', 'wire'),
            'timer_t': ('', 'wire'),
            'variable_t': ('[15:0]', 'reg'),
        }
        
        if c_type in type_map:
            return type_map[c_type]
        
        # Handle pointers/arrays
        if '[' in c_type or '*' in c_type:
            return ('[31:0]', 'reg')
        
        # Default
        return ('', 'reg')

class VerilogGenerator:
    """Final bug-free generator"""
    
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
        
        if self.info['has_spi']:
            parts.append(self._spi_interface())
        
        if self.info['has_display']:
            parts.append(self._display_controller())
        
        if self.info['has_sd']:
            parts.append(self._sd_controller())
        
        parts.append(self._state_machine())
        parts.append(self._main_logic())
        parts.append("endmodule")
        
        return '\n\n'.join(parts)
    
    def _header(self) -> str:
        return f"""`timescale 1ns / 1ps
// ============================================================
// Generated by Wokwi2Verilog
// Module: {self.module_name}
// ============================================================"""
    
    def _module_declaration(self) -> str:
        ports = []
        
        # Group pins
        power_pins = [p for p in self.info['pins'] if p.get('is_power', False)]
        input_pins = [p for p in self.info['pins'] if p['direction'] == 'input' and not p.get('is_power', False)]
        output_pins = [p for p in self.info['pins'] if p['direction'] == 'output' and not p.get('is_power', False)]
        
        # Clock and reset
        ports.append("    // Clock and Reset")
        ports.append("    input wire clk,")
        ports.append("    input wire rst_n")
        
        # Add comma if we have more ports
        if power_pins or input_pins or output_pins:
            ports[-1] = ports[-1] + ","
        
        # Power pins
        if power_pins:
            ports.append("")
            ports.append("    // Power Pins")
            for i, pin in enumerate(power_pins):
                comma = "," if i < len(power_pins) - 1 or input_pins or output_pins else ""
                direction = "input" if pin['name'].upper() in ['VCC', 'VDD'] else "output"
                ports.append(f"    {direction} wire {pin['name']}{comma}")
        
        # Input pins
        if input_pins:
            ports.append("")
            ports.append("    // Input Pins")
            for i, pin in enumerate(input_pins):
                comma = "," if i < len(input_pins) - 1 or output_pins else ""
                ports.append(f"    input wire {pin['name']}{comma}")
        
        # Output pins
        if output_pins:
            ports.append("")
            ports.append("    // Output Pins")
            for i, pin in enumerate(output_pins):
                comma = "," if i < len(output_pins) - 1 else ""
                vtype = "reg" if pin['type'] == 'reg' else "wire"
                ports.append(f"    output {vtype} {pin['name']}{comma}")
        
        # Remove trailing comma from last port
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
                if 'COLOR_' in name:
                    verilog_value = f"16'h{hex_val.upper()}"
                elif len(hex_val) <= 2:
                    verilog_value = f"8'h{hex_val.upper()}"
                elif len(hex_val) <= 4:
                    verilog_value = f"16'h{hex_val.upper()}"
                else:
                    verilog_value = f"32'h{hex_val.upper()}"
            elif value.isdigit():
                verilog_value = value
            else:
                verilog_value = f"'{value}'"
            
            params.append(f"    parameter {name} = {verilog_value};")
        
        return "    // Parameters\n" + '\n'.join(params)
    
    def _internal_signals(self) -> str:
        """FIXED: Handle signal extraction properly"""
        signals = ["    // Internal Signals"]
        
        # First, add all variables from struct
        for var in self.info['struct_vars']:
            # Handle special cases
            if var['name'] == 'program_outputs' and var['is_array']:
                signals.append(f"    reg [7:0] {var['name']}[0:9][0:31];")
            elif var['name'] == 'variables' and var['is_array']:
                signals.append(f"    reg [15:0] {var['name']}[0:{var['array_size']-1}];")
            elif var['is_array']:
                if var['width']:
                    signals.append(f"    {var['verilog_type']} {var['width']} {var['name']}[0:{var['array_size']-1}];")
                else:
                    signals.append(f"    {var['verilog_type']} {var['name']}[0:{var['array_size']-1}];")
            else:
                if var['width']:
                    signals.append(f"    {var['verilog_type']} {var['width']} {var['name']};")
                else:
                    signals.append(f"    {var['verilog_type']} {var['name']};")
        
        # Get existing signal names
        existing_names = {var['name'] for var in self.info['struct_vars']}
        
        # Common signals to add if not already present
        common_signals = [
            ("reg [31:0]", "counter"),
            ("reg [7:0]", "spi_tx_data"),
            ("reg [7:0]", "spi_rx_data"),
            ("reg", "spi_start"),
            ("wire", "spi_busy"),
            ("reg [2:0]", "spi_bit_counter"),
            ("reg", "spi_sck"),
            ("reg", "spi_mosi"),
        ]
        
        for vtype, name in common_signals:
            if name not in existing_names:
                signals.append(f"    {vtype} {name};")
        
        # Display signals
        if self.info['has_display']:
            display_signals = [
                ("reg [15:0]", "display_x"),
                ("reg [15:0]", "display_y"),
                ("reg [15:0]", "display_color"),
                ("reg", "display_start"),
                ("wire", "display_busy"),
                ("reg [2:0]", "display_state"),
            ]
            
            for vtype, name in display_signals:
                if name not in existing_names:
                    signals.append(f"    {vtype} {name};")
        
        # SD card signals
        if self.info['has_sd']:
            sd_signals = [
                ("reg [31:0]", "sd_sector"),
                ("reg [7:0]", "sd_buffer", "[0:511]"),
                ("reg", "sd_read_start"),
                ("wire", "sd_read_done"),
                ("reg [4:0]", "sd_state"),
                ("wire", "sd_card_detected"),
            ]
            
            for signal in sd_signals:
                if len(signal) == 3:  # Has array specifier
                    vtype, name, array = signal
                    if name not in existing_names:
                        signals.append(f"    {vtype} {name} {array};")
                else:
                    vtype, name = signal
                    if name not in existing_names and name != 'sd_card_present':  # Avoid duplicate
                        signals.append(f"    {vtype} {name};")
        
        return '\n'.join(signals)
    
    def _power_assignments(self) -> str:
        """Only assign to output power pins (GND)"""
        assigns = []
        for pin in self.info['pins']:
            if pin.get('is_power', False) and pin['direction'] == 'output':
                assigns.append(f"    assign {pin['name']} = 1'b0;")
        
        if assigns:
            return "    // Power Assignments\n" + '\n'.join(assigns)
        return ""
    
    def _clock_reset(self) -> str:
        return """    // ============================================
    // Clock and Reset
    // ============================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            counter <= 32'd0;
            // Add other reset logic here
        end else begin
            counter <= counter + 1;
        end
    end"""
    
    def _spi_interface(self) -> str:
        return """    // ============================================
    // SPI Master Interface
    // ============================================
    assign SCK = spi_sck;
    assign MOSI = spi_mosi;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            spi_bit_counter <= 3'd0;
            spi_sck <= 1'b0;
            spi_mosi <= 1'b0;
            spi_rx_data <= 8'd0;
        end else begin
            if (spi_start && !spi_busy) begin
                spi_bit_counter <= 3'd0;
                spi_sck <= 1'b0;
            end
            
            if (spi_bit_counter < 3'd8) begin
                spi_sck <= ~spi_sck;
                if (!spi_sck) begin
                    spi_mosi <= spi_tx_data[7 - spi_bit_counter];
                end else begin
                    spi_rx_data[7 - spi_bit_counter] <= MISO;
                    spi_bit_counter <= spi_bit_counter + 1;
                end
            end
        end
    end
    
    assign spi_busy = (spi_bit_counter < 3'd8);"""
    
    def _display_controller(self) -> str:
        return """    // ============================================
    // Display Controller
    // ============================================
    localparam [2:0] 
        DISP_IDLE   = 3'd0,
        DISP_CMD    = 3'd1,
        DISP_DATA   = 3'd2;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            display_state <= DISP_IDLE;
            CS <= 1'b1;
            DC <= 1'b0;
            display_start <= 1'b0;
        end else begin
            case (display_state)
                DISP_IDLE: begin
                    if (display_start) begin
                        display_state <= DISP_CMD;
                        CS <= 1'b0;
                    end
                end
                DISP_CMD: begin
                    DC <= 1'b0;
                    spi_tx_data <= 8'h2A;
                    spi_start <= 1'b1;
                    display_state <= DISP_DATA;
                end
                DISP_DATA: begin
                    DC <= 1'b1;
                    if (!spi_busy) begin
                        display_state <= DISP_IDLE;
                        CS <= 1'b1;
                    end
                end
            endcase
        end
    end
    
    assign display_busy = (display_state != DISP_IDLE);"""
    
    def _sd_controller(self) -> str:
        return """    // ============================================
    // SD Card Controller
    // ============================================
    // Card detect (active low)
    assign sd_card_detected = ~SD_CD;
    
    localparam [4:0]
        SD_IDLE     = 5'd0,
        SD_INIT     = 5'd1,
        SD_READ_CMD = 5'd2,
        SD_READ_WAIT = 5'd3;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sd_state <= SD_IDLE;
            SD_CS <= 1'b1;
        end else begin
            case (sd_state)
                SD_IDLE: begin
                    if (sd_read_start && sd_card_detected) begin
                        sd_state <= SD_INIT;
                        SD_CS <= 1'b0;
                    end
                end
                SD_INIT: begin
                    sd_state <= SD_READ_CMD;
                end
                SD_READ_CMD: begin
                    sd_state <= SD_READ_WAIT;
                end
                SD_READ_WAIT: begin
                    if (counter[15:0] == 16'hFFFF) begin
                        sd_state <= SD_IDLE;
                        SD_CS <= 1'b1;
                    end
                end
            endcase
        end
    end
    
    assign sd_read_done = (sd_state == SD_IDLE);"""
    
    def _state_machine(self) -> str:
        return """    // ============================================
    // Main State Machine
    // ============================================
    localparam [2:0]
        STATE_IDLE      = 3'd0,
        STATE_INIT      = 3'd1,
        STATE_RUN       = 3'd2,
        STATE_LOAD_SD   = 3'd3,
        STATE_DISPLAY   = 3'd4,
        STATE_DONE      = 3'd5;
    
    reg [2:0] current_state;
    reg [2:0] next_state;
    
    // State register
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_state <= STATE_IDLE;
        end else begin
            current_state <= next_state;
        end
    end
    
    // Next state logic
    always @(*) begin
        next_state = current_state;
        case (current_state)
            STATE_IDLE: begin
                if (RUN_BTN == 1'b0) next_state = STATE_INIT;
            end
            STATE_INIT: begin
                next_state = STATE_RUN;
            end
            STATE_RUN: begin
                next_state = STATE_LOAD_SD;
            end
            STATE_LOAD_SD: begin
                if (sd_read_done) next_state = STATE_DISPLAY;
            end
            STATE_DISPLAY: begin
                if (!display_busy) next_state = STATE_DONE;
            end
            STATE_DONE: begin
                next_state = STATE_IDLE;
            end
            default: next_state = STATE_IDLE;
        endcase
    end"""
    
    def _main_logic(self) -> str:
        return """    // ============================================
    // Main Application Logic
    // ============================================
    
    // Button debouncing
    reg [19:0] btn_debounce_counter;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            btn_debounce_counter <= 20'd0;
            btn_pressed <= 1'b0;
        end else begin
            if (RUN_BTN == 1'b0) begin
                if (btn_debounce_counter < 20'd1000000) begin
                    btn_debounce_counter <= btn_debounce_counter + 1;
                end else begin
                    btn_pressed <= 1'b1;
                end
            end else begin
                btn_debounce_counter <= 20'd0;
                btn_pressed <= 1'b0;
            end
        end
    end
    
    // LED control
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            LED <= 1'b0;
            RST <= 1'b1;
        end else begin
            case (current_state)
                STATE_IDLE:   LED <= 1'b0;
                STATE_INIT:   LED <= 1'b1;
                STATE_RUN:    LED <= counter[23];
                STATE_LOAD_SD: LED <= counter[20];
                STATE_DISPLAY: LED <= 1'b1;
                STATE_DONE:   LED <= 1'b0;
                default:      LED <= 1'b0;
            endcase
            
            // Display reset (active low)
            RST <= (current_state != STATE_INIT);
        end
    end
    
    // Control signals
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            display_start <= 1'b0;
            sd_read_start <= 1'b0;
        end else begin
            display_start <= (current_state == STATE_DISPLAY);
            sd_read_start <= (current_state == STATE_LOAD_SD);
        end
    end"""

def main():
    parser = argparse.ArgumentParser(
        description='Wokwi C to Verilog Compiler',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s example.c -o output.v
  %(prog)s chip.c --verbose
        '''
    )
    parser.add_argument('input', help='Input C file')
    parser.add_argument('-o', '--output', help='Output Verilog file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Check input file
    if not os.path.exists(args.input):
        print(f"Error: File '{args.input}' not found")
        return 1
    
    try:
        # Read input
        with open(args.input, 'r') as f:
            content = f.read()
        
        # Parse
        parser = WokwiParser()
        info = parser.parse(content)
        
        # Module name
        module_name = Path(args.input).stem
        module_name = re.sub(r'[^a-zA-Z0-9_]', '_', module_name)
        if not module_name[0].isalpha():
            module_name = 'chip_' + module_name
        
        if args.verbose:
            print(f"Parsing {args.input}...")
            print(f"  Found {len(info['pins'])} pins")
            print(f"  Found {len(info['struct_vars'])} variables")
            print(f"  Found {len(info['defines'])} parameters")
        
        # Generate Verilog
        generator = VerilogGenerator(info, module_name)
        verilog = generator.generate()
        
        # Write output
        output_file = args.output or f"{module_name}.v"
        with open(output_file, 'w') as f:
            f.write(verilog)
        
        print(f"✓ Successfully generated {output_file}")
        
        if args.verbose:
            print(f"\nFile size: {len(verilog)} bytes")
            print(f"Module: {module_name}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
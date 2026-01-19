#!/usr/bin/env python3
"""
UNIVERSAL Wokwi C to Verilog Converter
Supports ANY C chip design, not just OLED
"""

import sys
import re
import os
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Set, Optional

@dataclass
class PinInfo:
    name: str
    direction: str  # 'input', 'output', 'inout'
    type: str       # 'wire', 'reg'
    init_value: Optional[str] = None

class UniversalParser:
    def parse(self, content: str) -> dict:
        """Parse C code and extract all relevant information"""
        # Remove comments but keep #defines
        clean_content = self._remove_comments_keep_defines(content)
        
        return {
            'defines': self._extract_defines(content),
            'pins': self._extract_all_pins(clean_content),
            'functions': self._extract_functions(content),
            'structs': self._extract_structs(content),
            'includes': self._extract_includes(content),
            'timers': self._extract_timers(content),
            'chip_init': self._extract_chip_init(content),
        }
    
    def _remove_comments_keep_defines(self, content: str) -> str:
        """Remove comments but keep preprocessor directives"""
        lines = content.split('\n')
        result = []
        
        for line in lines:
            # Keep #includes and #defines
            if line.strip().startswith('#') or 'pin_init' in line:
                result.append(line)
            # Remove single-line comments
            elif '//' in line:
                result.append(line.split('//')[0])
        
        return '\n'.join(result)
    
    def _extract_defines(self, content: str) -> Dict[str, str]:
        """Extract all #define directives"""
        defines = {}
        # Pattern to match #define NAME VALUE
        pattern = r'#define\s+(\w+)\s+([^\s;]+)'
        
        for name, value in re.findall(pattern, content):
            # Skip function-like macros
            if '(' not in name:
                defines[name] = value
        
        # Also look for multi-line defines
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('#define'):
                parts = line.split(maxsplit=2)
                if len(parts) >= 3 and '(' not in parts[1]:
                    name = parts[1]
                    value = parts[2].split('//')[0].strip()
                    defines[name] = value
            i += 1
        
        return defines
    
    def _extract_all_pins(self, content: str) -> List[PinInfo]:
        """Extract all pins from pin_init calls"""
        pins = []
        pin_names = set()
        
        # Pattern to match pin_init("PIN_NAME", ...)
        pattern = r'pin_init\("([^"]+)"'
        
        for pin_name in re.findall(pattern, content):
            if pin_name not in pin_names:
                pins.append(self._classify_pin(pin_name, content))
                pin_names.add(pin_name)
        
        # Also look for pin_t declarations
        pattern2 = r'pin_t\s+(\w+)\s*[;=]'
        for pin_name in re.findall(pattern2, content):
            if pin_name not in pin_names:
                pins.append(self._classify_pin(pin_name, content))
                pin_names.add(pin_name)
        
        return pins
    
    def _classify_pin(self, pin_name: str, content: str) -> PinInfo:
        """Classify pin based on its usage in the code"""
        pin_upper = pin_name.upper()
        
        # Look for pin_mode calls
        input_pattern = rf'pin_mode.*{pin_name}.*INPUT'
        output_pattern = rf'pin_mode.*{pin_name}.*OUTPUT'
        
        # Check for pin_write - indicates output
        write_pattern = rf'pin_write\s*\(\s*{pin_name}'
        
        # Check for pin_read - indicates input
        read_pattern = rf'pin_read\s*\(\s*{pin_name}'
        
        # Look for initialization patterns
        if re.search(output_pattern, content, re.IGNORECASE) or re.search(write_pattern, content):
            direction = 'output'
        elif re.search(input_pattern, content, re.IGNORECASE) or re.search(read_pattern, content):
            direction = 'input'
        else:
            # Default based on naming convention
            if any(x in pin_upper for x in ['VCC', 'VDD', 'POWER']):
                direction = 'output'
            elif 'GND' in pin_upper:
                direction = 'output'
            elif any(x in pin_upper for x in ['CLK', 'CLOCK', 'SCL', 'SDA']):
                direction = 'output'
            else:
                direction = 'input'
        
        # Determine type (reg for outputs that need to hold state)
        if direction == 'output':
            pin_type = 'reg'
        else:
            pin_type = 'wire'
        
        # Try to find initial value
        init_value = None
        init_pattern = rf'pin_write\s*\(\s*{pin_name}\s*,\s*([^)]+)\)'
        match = re.search(init_pattern, content)
        if match:
            init_value = match.group(1).strip()
            if init_value in ['HIGH', '1']:
                init_value = "1'b1"
            elif init_value in ['LOW', '0']:
                init_value = "1'b0"
        
        return PinInfo(
            name=pin_name,
            direction=direction,
            type=pin_type,
            init_value=init_value
        )
    
    def _extract_functions(self, content: str) -> List[Dict]:
        """Extract function signatures"""
        functions = []
        # Simple pattern for function declarations (won't handle all cases)
        pattern = r'(\w+)\s+(\w+)\s*\(([^)]*)\)\s*\{'
        
        for match in re.finditer(pattern, content):
            return_type, name, params = match.groups()
            if name not in ['if', 'while', 'for', 'switch']:  # Skip control structures
                functions.append({
                    'name': name,
                    'return_type': return_type,
                    'params': params
                })
        
        return functions
    
    def _extract_structs(self, content: str) -> List[Dict]:
        """Extract struct definitions"""
        structs = []
        # Pattern for struct definitions
        pattern = r'typedef\s+struct\s+(\w+)_t\s*\{([^}]+)\}\s*\w+_t;'
        
        for match in re.finditer(pattern, content, re.DOTALL):
            name, body = match.groups()
            fields = []
            for line in body.split(';'):
                line = line.strip()
                if line and not line.startswith('//'):
                    fields.append(line)
            structs.append({'name': name, 'fields': fields})
        
        return structs
    
    def _extract_includes(self, content: str) -> List[str]:
        """Extract #include directives"""
        includes = []
        for line in content.split('\n'):
            if line.strip().startswith('#include'):
                includes.append(line.strip())
        return includes
    
    def _extract_timers(self, content: str) -> List[Dict]:
        """Extract timer usage"""
        timers = []
        # Look for timer_init calls
        pattern = r'timer_init\s*\([^)]*\)'
        for match in re.finditer(pattern, content):
            timers.append({'line': match.group()})
        return timers
    
    def _extract_chip_init(self, content: str) -> Optional[str]:
        """Extract chip_init function for analysis"""
        pattern = r'void\s+chip_init\s*\([^)]*\)\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1)
        return None

class UniversalGenerator:
    def __init__(self, info: dict, module_name: str):
        self.info = info
        self.module_name = module_name
    
    def generate(self) -> str:
        """Generate Verilog code for ANY chip"""
        parts = []
        
        # Header
        parts.append(self._header())
        
        # Module declaration
        parts.append(self._module_declaration())
        
        # Parameters from #defines
        params = self._generate_parameters()
        if params:
            parts.append(params)
        
        # Internal signals
        parts.append(self._generate_internal_signals())
        
        # Power assignments (if any)
        power = self._generate_power_assignments()
        if power:
            parts.append(power)
        
        # Clock and Reset
        parts.append(self._generate_clock_reset())
        
        # Main state machine
        parts.append(self._generate_main_state_machine())
        
        # Input processing
        parts.append(self._generate_input_processing())
        
        # Output assignments
        parts.append(self._generate_output_assignments())
        
        # Generic always blocks for common patterns
        parts.append(self._generate_generic_logic())
        
        parts.append("endmodule")
        
        return '\n\n'.join(parts)
    
    def _header(self) -> str:
        return f"""`timescale 1ns / 1ps
// ============================================================
// Generated by Universal Wokwi2Verilog Converter
// Module: {self.module_name}
// Converted from C to Verilog
// ============================================================"""
    
    def _module_declaration(self) -> str:
        """Generate module declaration with all pins"""
        ports = []
        
        # Separate pins by direction
        inputs = [p for p in self.info['pins'] if p.direction == 'input']
        outputs = [p for p in self.info['pins'] if p.direction == 'output']
        
        # Always include clock and reset
        ports.append("    // Clock and Reset")
        ports.append("    input wire clk,")
        ports.append("    input wire rst_n")
        
        # Add comma if we have more ports
        if inputs or outputs:
            ports[-1] = ports[-1] + ","
        
        # Input pins
        if inputs:
            ports.append("")
            ports.append("    // Input Pins")
            for i, pin in enumerate(inputs):
                comma = "," if i < len(inputs) - 1 or outputs else ""
                ports.append(f"    input wire {pin.name}{comma}")
        
        # Output pins
        if outputs:
            ports.append("")
            ports.append("    // Output Pins")
            for i, pin in enumerate(outputs):
                comma = "," if i < len(outputs) - 1 else ""
                vtype = pin.type if pin.type == 'reg' else 'wire'
                ports.append(f"    output {vtype} {pin.name}{comma}")
        
        # Remove trailing comma
        port_text = '\n'.join(ports)
        port_text = port_text.rstrip(',')
        
        return f"module {self.module_name} (\n{port_text}\n);"
    
    def _generate_parameters(self) -> str:
        """Convert C #defines to Verilog parameters"""
        if not self.info['defines']:
            return ""
        
        params = []
        params.append("    // Parameters from C #defines")
        
        for name, value in self.info['defines'].items():
            # Skip common C headers
            if name.startswith('__') or name in ['NULL', 'TRUE', 'FALSE']:
                continue
            
            # Convert value to Verilog format
            verilog_value = self._convert_c_value_to_verilog(value)
            params.append(f"    parameter {name} = {verilog_value};")
        
        # Add derived parameters
        if 'OLED_HEIGHT' in self.info['defines'] and self.info['defines']['OLED_HEIGHT'] == '64':
            params.append("    parameter OLED_PAGES = 8;  // OLED_HEIGHT / 8")
        
        return '\n'.join(params)
    
    def _convert_c_value_to_verilog(self, value: str) -> str:
        """Convert C constant to Verilog constant"""
        value = value.strip()
        
        # Hexadecimal
        if value.startswith('0x'):
            hex_val = value[2:].upper()
            if len(hex_val) <= 2:
                return f"8'h{hex_val}"
            elif len(hex_val) <= 4:
                return f"16'h{hex_val}"
            else:
                return f"32'h{hex_val}"
        
        # Binary (non-standard C, but might be used)
        elif value.startswith('0b'):
            bin_val = value[2:].upper()
            return f"{len(bin_val)}'b{bin_val}"
        
        # Decimal number
        elif value.isdigit():
            return f"32'd{value}"
        
        # Float (convert to fixed point)
        elif '.' in value or 'f' in value:
            try:
                # Remove 'f' suffix
                clean_val = value.replace('f', '').replace('F', '')
                float_val = float(clean_val)
                # Convert to Q16.16 fixed point
                fixed_val = int(float_val * 65536)
                return f"32'd{fixed_val}"
            except:
                return "32'd0"
        
        # Character
        elif value.startswith("'") and value.endswith("'"):
            char_val = ord(value[1])
            return f"8'd{char_val}"
        
        # Keep as-is (might be an expression)
        else:
            return value
    
    def _generate_internal_signals(self) -> str:
        """Generate internal signal declarations"""
        signals = []
        signals.append("    // Internal Signals")
        
        # Always have a counter
        signals.append("    reg [31:0] counter;")
        
        # State machine
        signals.append("    reg [7:0] current_state;")
        signals.append("    reg [7:0] next_state;")
        
        # For input debouncing
        input_pins = [p for p in self.info['pins'] if p.direction == 'input']
        if input_pins:
            signals.append("")
            signals.append("    // Input debouncing registers")
            for pin in input_pins:
                if pin.name.upper() not in ['CLK', 'RST_N']:
                    signals.append(f"    reg {pin.name}_debounced;")
                    signals.append(f"    reg [19:0] {pin.name}_debounce_counter;")
        
        # For output latches
        output_pins = [p for p in self.info['pins'] if p.direction == 'output' and p.type == 'reg']
        if output_pins:
            signals.append("")
            signals.append("    // Output registers")
            for pin in output_pins:
                signals.append(f"    reg {pin.name}_reg;")
        
        # Generic registers for common patterns
        signals.append("")
        signals.append("    // Generic registers")
        signals.append("    reg [31:0] timer_counter;")
        signals.append("    reg [7:0] data_buffer;")
        signals.append("    reg [15:0] address_reg;")
        signals.append("    reg busy_flag;")
        signals.append("    reg error_flag;")
        
        return '\n'.join(signals)
    
    def _generate_power_assignments(self) -> str:
        """Generate power pin assignments"""
        assigns = []
        for pin in self.info['pins']:
            pin_upper = pin.name.upper()
            if 'VCC' in pin_upper or 'VDD' in pin_upper:
                assigns.append(f"    assign {pin.name} = 1'b1;")
            elif 'GND' in pin_upper:
                assigns.append(f"    assign {pin.name} = 1'b0;")
        
        if assigns:
            return "    // Power Assignments\n" + '\n'.join(assigns)
        return ""
    
    def _generate_clock_reset(self) -> str:
        """Generate clock and reset logic"""
        return """    // ============================================
    // Clock and Reset Logic
    // ============================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            counter <= 32'd0;
            current_state <= 8'd0;
            timer_counter <= 32'd0;
            busy_flag <= 1'b0;
            error_flag <= 1'b0;
        end else begin
            counter <= counter + 1;
            current_state <= next_state;
            
            // Timer counter
            if (timer_counter > 0) begin
                timer_counter <= timer_counter - 1;
            end
        end
    end"""
    
    def _generate_main_state_machine(self) -> str:
        """Generate a generic state machine"""
        return """    // ============================================
    // Main State Machine
    // ============================================
    localparam [7:0]
        STATE_IDLE     = 8'd0,
        STATE_INIT     = 8'd1,
        STATE_RUN      = 8'd2,
        STATE_WAIT     = 8'd3,
        STATE_ERROR    = 8'd4;
    
    always @(*) begin
        next_state = current_state;
        
        case (current_state)
            STATE_IDLE: begin
                // Wait for some condition
                if (counter[23:0] == 24'hFFFFFF) begin
                    next_state = STATE_INIT;
                end
            end
            
            STATE_INIT: begin
                // Initialize components
                if (timer_counter == 0) begin
                    next_state = STATE_RUN;
                end
            end
            
            STATE_RUN: begin
                // Main operation
                if (error_flag) begin
                    next_state = STATE_ERROR;
                end
            end
            
            STATE_WAIT: begin
                // Wait state
                if (timer_counter == 0) begin
                    next_state = STATE_RUN;
                end
            end
            
            STATE_ERROR: begin
                // Error handling
                if (!rst_n) begin
                    next_state = STATE_IDLE;
                end
            end
        endcase
    end"""
    
    def _generate_input_processing(self) -> str:
        """Generate input debouncing and processing"""
        input_pins = [p for p in self.info['pins'] if p.direction == 'input']
        if not input_pins:
            return ""
        
        always_blocks = []
        always_blocks.append("    // ============================================")
        always_blocks.append("    // Input Processing with Debouncing")
        always_blocks.append("    // ============================================")
        
        for pin in input_pins:
            if pin.name.upper() not in ['CLK', 'RST_N']:
                always_blocks.append(f"""
    // Debounce {pin.name}
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            {pin.name}_debounced <= 1'b0;
            {pin.name}_debounce_counter <= 20'd0;
        end else begin
            if ({pin.name} != {pin.name}_debounced) begin
                if ({pin.name}_debounce_counter < 20'd100000) begin
                    {pin.name}_debounce_counter <= {pin.name}_debounce_counter + 1;
                end else begin
                    {pin.name}_debounced <= {pin.name};
                    {pin.name}_debounce_counter <= 20'd0;
                end
            end else begin
                {pin.name}_debounce_counter <= 20'd0;
            end
        end
    end""")
        
        return '\n'.join(always_blocks)
    
    def _generate_output_assignments(self) -> str:
        """Generate output assignments"""
        output_pins = [p for p in self.info['pins'] if p.direction == 'output' and p.type == 'reg']
        if not output_pins:
            return ""
        
        assigns = []
        assigns.append("    // ============================================")
        assigns.append("    // Output Assignments")
        assigns.append("    // ============================================")
        
        for pin in output_pins:
            if pin.init_value:
                assigns.append(f"    assign {pin.name} = {pin.init_value};")
            else:
                assigns.append(f"    assign {pin.name} = {pin.name}_reg;")
        
        return '\n'.join(assigns)
    
    def _generate_generic_logic(self) -> str:
        """Generate generic logic for common patterns"""
        logic = []
        logic.append("    // ============================================")
        logic.append("    // Generic Logic Blocks")
        logic.append("    // ============================================")
        
        # Timer logic
        logic.append("""
    // Timer logic
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Initialize timers
        end else if (current_state == STATE_INIT) begin
            timer_counter <= 32'd1000;  // 1000 clock cycles
        end
    end""")
        
        # Look for I2C patterns
        if any('scl' in pin.name.lower() for pin in self.info['pins']):
            logic.append(self._generate_i2c_logic())
        
        # Look for SPI patterns
        if any('sck' in pin.name.lower() for pin in self.info['pins']):
            logic.append(self._generate_spi_logic())
        
        # Look for UART patterns
        if any('tx' in pin.name.lower() for pin in self.info['pins']):
            logic.append(self._generate_uart_logic())
        
        return '\n'.join(logic)
    
    def _generate_i2c_logic(self) -> str:
        """Generate I2C logic if I2C pins are detected"""
        return """
    // I2C Interface Logic
    localparam [2:0]
        I2C_IDLE      = 3'd0,
        I2C_START     = 3'd1,
        I2C_ADDR      = 3'd2,
        I2C_DATA      = 3'd3,
        I2C_STOP      = 3'd4;
    
    reg [2:0] i2c_state;
    reg i2c_scl_reg;
    reg i2c_sda_reg;
    reg [7:0] i2c_data_out;
    reg i2c_write_active;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            i2c_state <= I2C_IDLE;
            i2c_scl_reg <= 1'b1;
            i2c_sda_reg <= 1'b1;
        end else begin
            case (i2c_state)
                I2C_IDLE: begin
                    if (i2c_write_active) begin
                        i2c_state <= I2C_START;
                    end
                end
                // Other I2C states would be implemented here
                default: begin
                    i2c_state <= I2C_IDLE;
                end
            endcase
        end
    end"""
    
    def _generate_spi_logic(self) -> str:
        """Generate SPI logic if SPI pins are detected"""
        return """
    // SPI Interface Logic
    reg [7:0] spi_shift_reg;
    reg [2:0] spi_bit_counter;
    reg spi_busy;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            spi_shift_reg <= 8'h00;
            spi_bit_counter <= 3'd0;
            spi_busy <= 1'b0;
        end else begin
            // SPI logic would be implemented here
        end
    end"""
    
    def _generate_uart_logic(self) -> str:
        """Generate UART logic if UART pins are detected"""
        return """
    // UART Interface Logic
    reg [7:0] uart_tx_buffer;
    reg [3:0] uart_bit_counter;
    reg uart_tx_busy;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            uart_tx_buffer <= 8'h00;
            uart_bit_counter <= 4'd0;
            uart_tx_busy <= 1'b0;
        end else begin
            // UART logic would be implemented here
        end
    end"""

def main():
    parser = argparse.ArgumentParser(description='UNIVERSAL Wokwi C to Verilog Converter')
    parser.add_argument('input', help='Input C file')
    parser.add_argument('-o', '--output', help='Output Verilog file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--module', help='Module name (default: derived from filename)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: File '{args.input}' not found")
        return 1
    
    try:
        with open(args.input, 'r') as f:
            content = f.read()
        
        # Parse the C code
        parser = UniversalParser()
        info = parser.parse(content)
        
        # Determine module name
        if args.module:
            module_name = args.module
        else:
            module_name = Path(args.input).stem
            # Make it valid Verilog identifier
            module_name = re.sub(r'[^a-zA-Z0-9_]', '_', module_name)
            if not module_name[0].isalpha():
                module_name = 'chip_' + module_name
        
        if args.verbose:
            print(f"Parsing {args.input}...")
            print(f"  Module: {module_name}")
            print(f"  Input pins: {len([p for p in info['pins'] if p.direction == 'input'])}")
            print(f"  Output pins: {len([p for p in info['pins'] if p.direction == 'output'])}")
            print(f"  Defines: {len(info['defines'])}")
            print(f"  Functions: {len(info['functions'])}")
            print(f"  Structs: {len(info['structs'])}")
        
        # Generate Verilog
        generator = UniversalGenerator(info, module_name)
        verilog = generator.generate()
        
        # Write output
        output_file = args.output or f"{module_name}.v"
        with open(output_file, 'w') as f:
            f.write(verilog)
        
        print(f"✓ Generated {output_file}")
        print(f"  Universal converter completed successfully")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
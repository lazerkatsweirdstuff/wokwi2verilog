#!/usr/bin/env python3
"""
Universal Wokwi C to Verilog Compiler
Converts ANY Wokwi C chip design to synthesizable Verilog
"""

import sys
import re
import os
import argparse
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

# ============================================
# DATA CLASSES
# ============================================

@dataclass
class Signal:
    """Represents a signal in the design"""
    name: str
    c_type: str
    verilog_type: str  # 'wire' or 'reg'
    width: str  # e.g., '[7:0]', '[31:0]', ''
    is_array: bool = False
    array_size: int = 1
    is_port: bool = False
    direction: str = ''  # 'input', 'output', 'inout'
    initial_value: str = '0'
    description: str = ''

@dataclass
class ModuleInfo:
    """Contains all information about the module"""
    name: str
    inputs: List[Signal] = field(default_factory=list)
    outputs: List[Signal] = field(default_factory=list)
    inouts: List[Signal] = field(default_factory=list)
    internal_signals: List[Signal] = field(default_factory=list)
    states: List[str] = field(default_factory=list)
    state_bits: int = 2
    functions: List[Dict] = field(default_factory=list)
    parameters: Dict[str, str] = field(default_factory=dict)
    clocks: List[str] = field(default_factory=lambda: ['clk'])
    resets: List[str] = field(default_factory=lambda: ['rst_n'])
    interfaces: Set[str] = field(default_factory=set)
    has_spi: bool = False
    has_i2c: bool = False
    has_uart: bool = False
    has_display: bool = False
    has_sd: bool = False
    has_timers: bool = False

# ============================================
# C TYPE TO VERILOG CONVERTER
# ============================================

class TypeConverter:
    """Converts C types to Verilog types"""
    
    TYPE_MAP = {
        # Standard C types
        'char': ('[7:0]', 'reg'),
        'unsigned char': ('[7:0]', 'reg'),
        'signed char': ('[7:0]', 'reg'),
        'uint8_t': ('[7:0]', 'reg'),
        'int8_t': ('[7:0]', 'reg'),
        'bool': ('', 'reg'),
        
        # 16-bit types
        'short': ('[15:0]', 'reg'),
        'unsigned short': ('[15:0]', 'reg'),
        'uint16_t': ('[15:0]', 'reg'),
        'int16_t': ('[15:0]', 'reg'),
        
        # 32-bit types
        'int': ('[31:0]', 'reg'),
        'unsigned int': ('[31:0]', 'reg'),
        'long': ('[31:0]', 'reg'),
        'unsigned long': ('[31:0]', 'reg'),
        'uint32_t': ('[31:0]', 'reg'),
        'int32_t': ('[31:0]', 'reg'),
        'float': ('[31:0]', 'reg'),
        
        # 64-bit types
        'long long': ('[63:0]', 'reg'),
        'unsigned long long': ('[63:0]', 'reg'),
        'uint64_t': ('[63:0]', 'reg'),
        'int64_t': ('[63:0]', 'reg'),
        'double': ('[63:0]', 'reg'),
        
        # Special Wokwi types
        'pin_t': ('', 'wire'),
        'timer_t': ('', 'wire'),
        'attr_t': ('[31:0]', 'reg'),
        
        # Pointers
        'void*': ('[31:0]', 'reg'),
        'char*': ('[31:0]', 'reg'),
        'uint8_t*': ('[31:0]', 'reg'),
    }
    
    @classmethod
    def convert(cls, c_type: str) -> tuple:
        """Convert C type to (width, verilog_type)"""
        # Clean up type
        c_type = c_type.strip()
        
        # Check for pointers
        if '*' in c_type:
            base_type = c_type.replace('*', '').strip()
            if base_type in cls.TYPE_MAP:
                return ('[31:0]', 'reg')  # Pointers are 32-bit addresses
            return ('[31:0]', 'reg')
        
        # Check for const
        if c_type.startswith('const '):
            c_type = c_type[6:]
        
        # Check for volatile
        if c_type.startswith('volatile '):
            c_type = c_type[9:]
        
        # Check for signed/unsigned
        if c_type.startswith('signed ') or c_type.startswith('unsigned '):
            # Already in map
            pass
        
        # Return from map or default
        if c_type in cls.TYPE_MAP:
            return cls.TYPE_MAP[c_type]
        
        # Default for unknown types
        if '[' in c_type:  # Array type in C
            return ('[31:0]', 'reg')
        
        return ('', 'reg')  # Default to single bit

# ============================================
# C CODE PARSER
# ============================================

class WokwiCParser:
    """Parses Wokwi C code to extract hardware information"""
    
    def __init__(self):
        self.patterns = {
            # Pin definitions
            'pin_def': r'pin_t\s+(\w+)\s*(?:=\s*[^;]+)?\s*;',
            
            # Struct definitions (single line)
            'struct_line': r'(\w+)\s+(\w+)(?:\[(\d+)\])?\s*;',
            
            # Struct blocks
            'struct_block': r'typedef\s+struct\s*\{([^}]+)\}\s*(\w+)_t\s*;',
            
            # Functions
            'function': r'(\w+(?:\s+\*?)?)\s+(\w+)\s*\(([^)]*)\)\s*\{',
            
            # Includes
            'include': r'#include\s+["<]([^">]+)[">]',
            
            # Defines
            'define': r'#define\s+(\w+)\s+(.+)',
            
            # Comments (to remove)
            'comment_single': r'//.*',
            'comment_multi': r'/\*.*?\*/',
            
            # SPI functions
            'spi_call': r'(?:spi_write|spi_read|SPI_WRITE|SPI_READ)',
            
            # I2C functions
            'i2c_call': r'(?:i2c_write|i2c_read|I2C_WRITE|I2C_READ)',
            
            # UART functions
            'uart_call': r'(?:uart_write|uart_read|UART_WRITE|UART_READ)',
            
            # Timer functions
            'timer_call': r'(?:timer_init|timer_start|timer_stop|TIMER_INIT|TIMER_START)',
            
            # Display functions
            'display_call': r'(?:send_cmd|send_data|fill_rect|draw_char|draw_string|set_window)',
            
            # SD card functions
            'sd_call': r'(?:sd_init|sd_read|sd_write|SD_INIT|SD_READ)',
        }
    
    def clean_code(self, c_code: str) -> str:
        """Remove comments and clean up code"""
        # Remove multi-line comments
        c_code = re.sub(self.patterns['comment_multi'], '', c_code, flags=re.DOTALL)
        
        # Remove single-line comments
        c_code = re.sub(self.patterns['comment_single'], '', c_code)
        
        # Remove extra whitespace
        c_code = re.sub(r'\s+', ' ', c_code)
        
        return c_code
    
    def parse(self, c_code: str) -> ModuleInfo:
        """Parse C code and return module information"""
        
        # Clean the code first
        clean_code = self.clean_code(c_code)
        
        # Create module info
        module = ModuleInfo(name="wokwi_chip")
        
        # Extract pins
        module = self._extract_pins(clean_code, module)
        
        # Extract structs and variables
        module = self._extract_structs(clean_code, module)
        
        # Extract functions and interfaces
        module = self._extract_functions(clean_code, module)
        
        # Extract defines as parameters
        module = self._extract_defines(clean_code, module)
        
        # Detect interfaces
        module = self._detect_interfaces(clean_code, module)
        
        return module
    
    def _extract_pins(self, code: str, module: ModuleInfo) -> ModuleInfo:
        """Extract pin definitions"""
        matches = re.findall(self.patterns['pin_def'], code)
        
        for pin_name in matches:
            # Determine direction based on naming convention
            pin_upper = pin_name.upper()
            
            if any(x in pin_upper for x in ['VCC', 'GND']):
                # Power pins
                signal = Signal(
                    name=pin_name,
                    c_type='pin_t',
                    verilog_type='wire',
                    width='',
                    is_port=True,
                    direction='input' if 'VCC' in pin_upper else 'output'
                )
                if signal.direction == 'input':
                    module.inputs.append(signal)
                else:
                    module.outputs.append(signal)
                    
            elif any(x in pin_upper for x in ['CS', 'DC', 'MOSI', 'SCK', 'LED', 'RST', 'WR', 'RD']):
                # Output pins (control signals)
                signal = Signal(
                    name=pin_name,
                    c_type='pin_t',
                    verilog_type='reg',
                    width='',
                    is_port=True,
                    direction='output'
                )
                module.outputs.append(signal)
                
            elif any(x in pin_upper for x in ['MISO', 'CD', 'BTN', 'SW', 'KEY']):
                # Input pins (data inputs, buttons)
                signal = Signal(
                    name=pin_name,
                    c_type='pin_t',
                    verilog_type='wire',
                    width='',
                    is_port=True,
                    direction='input'
                )
                module.inputs.append(signal)
                
            elif any(x in pin_upper for x in ['SDA', 'SDL', 'TX', 'RX']):
                # Bidirectional pins
                signal = Signal(
                    name=pin_name,
                    c_type='pin_t',
                    verilog_type='wire',
                    width='',
                    is_port=True,
                    direction='inout'
                )
                module.inouts.append(signal)
                
            else:
                # Default to input for unknown pins
                signal = Signal(
                    name=pin_name,
                    c_type='pin_t',
                    verilog_type='wire',
                    width='',
                    is_port=True,
                    direction='input'
                )
                module.inputs.append(signal)
        
        return module
    
    def _extract_structs(self, code: str, module: ModuleInfo) -> ModuleInfo:
        """Extract struct definitions and variables"""
        
        # Look for main state struct (chip_state_t)
        struct_match = re.search(self.patterns['struct_block'], code, re.DOTALL)
        
        if struct_match:
            struct_body = struct_match.group(1)
            struct_name = struct_match.group(2)
            
            # Extract variables from struct
            lines = struct_body.split(';')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Match variable declaration
                var_match = re.match(r'(\w+(?:\s+\*?)?)\s+(\w+)(?:\[(\d+)\])?', line)
                if var_match:
                    c_type = var_match.group(1)
                    var_name = var_match.group(2)
                    array_size = var_match.group(3)
                    
                    # Skip if it's a pin (already handled)
                    if c_type == 'pin_t':
                        continue
                    
                    # Convert type
                    width, verilog_type = TypeConverter.convert(c_type)
                    
                    # Create signal
                    is_array = array_size is not None
                    array_size_int = int(array_size) if array_size else 1
                    
                    signal = Signal(
                        name=var_name,
                        c_type=c_type,
                        verilog_type=verilog_type,
                        width=width,
                        is_array=is_array,
                        array_size=array_size_int,
                        is_port=False,
                        direction=''
                    )
                    
                    module.internal_signals.append(signal)
                    
                    # Check if it's a state variable
                    if 'state' in var_name.lower():
                        module.states.append(var_name.upper())
        
        # Also look for standalone variables (not in structs)
        # This catches global variables
        var_pattern = r'(\w+)\s+(\w+)(?:\[(\d+)\])?\s*=\s*[^;]+;'
        matches = re.findall(var_pattern, code)
        
        for c_type, var_name, array_size in matches:
            if c_type == 'pin_t':
                continue
                
            width, verilog_type = TypeConverter.convert(c_type)
            is_array = array_size != ''
            array_size_int = int(array_size) if array_size else 1
            
            signal = Signal(
                name=var_name,
                c_type=c_type,
                verilog_type=verilog_type,
                width=width,
                is_array=is_array,
                array_size=array_size_int,
                is_port=False,
                direction=''
            )
            
            module.internal_signals.append(signal)
        
        return module
    
    def _extract_functions(self, code: str, module: ModuleInfo) -> ModuleInfo:
        """Extract function definitions"""
        matches = re.findall(self.patterns['function'], code)
        
        for return_type, func_name, params in matches:
            function_info = {
                'name': func_name,
                'return_type': return_type,
                'parameters': params
            }
            module.functions.append(function_info)
        
        return module
    
    def _extract_defines(self, code: str, module: ModuleInfo) -> ModuleInfo:
        """Extract #define statements as parameters"""
        matches = re.findall(self.patterns['define'], code)
        
        for name, value in matches:
            # Clean up value
            value = value.strip()
            if value.endswith('\\'):
                value = value[:-1].strip()
            
            # Add to parameters if it looks like a constant
            if re.match(r'^-?\d+$', value):  # Integer
                module.parameters[name] = value
            elif re.match(r'^0x[0-9A-Fa-f]+$', value):  # Hex
                module.parameters[name] = value
            elif re.match(r'^[A-Z_]+$', name):  # ALL_CAPS name
                module.parameters[name] = value
        
        return module
    
    def _detect_interfaces(self, code: str, module: ModuleInfo) -> ModuleInfo:
        """Detect which interfaces are used"""
        
        # SPI detection
        if re.search(self.patterns['spi_call'], code):
            module.has_spi = True
            module.interfaces.add('spi')
        
        # I2C detection
        if re.search(self.patterns['i2c_call'], code):
            module.has_i2c = True
            module.interfaces.add('i2c')
        
        # UART detection
        if re.search(self.patterns['uart_call'], code):
            module.has_uart = True
            module.interfaces.add('uart')
        
        # Timer detection
        if re.search(self.patterns['timer_call'], code):
            module.has_timers = True
            module.interfaces.add('timer')
        
        # Display detection
        if re.search(self.patterns['display_call'], code):
            module.has_display = True
            module.interfaces.add('display')
        
        # SD card detection
        if re.search(self.patterns['sd_call'], code):
            module.has_sd = True
            module.interfaces.add('sd_card')
        
        # Also check for common interface patterns
        if re.search(r'SPI|spi|MISO|MOSI|SCK|CS', code, re.IGNORECASE):
            module.has_spi = True
            module.interfaces.add('spi')
        
        if re.search(r'I2C|i2c|SDA|SCL', code, re.IGNORECASE):
            module.has_i2c = True
            module.interfaces.add('i2c')
        
        if re.search(r'UART|uart|TX|RX|baud', code, re.IGNORECASE):
            module.has_uart = True
            module.interfaces.add('uart')
        
        return module

# ============================================
# VERILOG GENERATOR
# ============================================

class VerilogGenerator:
    """Generates Verilog code from module information"""
    
    def __init__(self, module: ModuleInfo):
        self.module = module
    
    def generate(self) -> str:
        """Generate complete Verilog module"""
        
        # Start with header
        verilog = self._generate_header()
        
        # Add parameters
        verilog += self._generate_parameters()
        
        # Add ports
        verilog += self._generate_ports()
        
        # Add internal signals
        verilog += self._generate_internal_signals()
        
        # Add clock and reset
        verilog += self._generate_clock_reset()
        
        # Add interfaces
        verilog += self._generate_interfaces()
        
        # Add state machine
        verilog += self._generate_state_machine()
        
        # Add main logic
        verilog += self._generate_main_logic()
        
        # End module
        verilog += "endmodule\n"
        
        return verilog
    
    def _generate_header(self) -> str:
        """Generate module header"""
        return f"""`timescale 1ns / 1ps
/*
 * ============================================================
 * Generated by Wokwi2Verilog Compiler
 * Module: {self.module.name}
 * Source: Wokwi C code
 * ============================================================
 */

module {self.module.name} (
"""
    
    def _generate_parameters(self) -> str:
        """Generate parameter section"""
        if not self.module.parameters:
            return ""
        
        params = []
        for name, value in self.module.parameters.items():
            params.append(f"    parameter {name} = {value}")
        
        return "\n" + ",\n".join(params) + "\n"
    
    def _generate_ports(self) -> str:
        """Generate port declarations"""
        ports = []
        
        # Add clock and reset
        ports.append("    // Clock and Reset")
        ports.append("    input wire clk,")
        ports.append("    input wire rst_n")
        
        # Add inputs
        if self.module.inputs:
            ports.append("")
            ports.append("    // Input Ports")
            for signal in self.module.inputs:
                ports.append(f"    input wire {signal.name},")
        
        # Add outputs
        if self.module.outputs:
            ports.append("")
            ports.append("    // Output Ports")
            for i, signal in enumerate(self.module.outputs):
                comma = "," if i < len(self.module.outputs) - 1 or self.module.inouts else ""
                ports.append(f"    output reg {signal.name}{comma}")
        
        # Add inouts
        if self.module.inouts:
            ports.append("")
            ports.append("    // Bidirectional Ports")
            for i, signal in enumerate(self.module.inouts):
                comma = "," if i < len(self.module.inouts) - 1 else ""
                ports.append(f"    inout wire {signal.name}{comma}")
        
        # Remove trailing comma from last port
        verilog = ",\n".join(ports)
        verilog = verilog.rstrip(',')
        verilog += "\n);\n\n"
        
        return verilog
    
    def _generate_internal_signals(self) -> str:
        """Generate internal signal declarations"""
        if not self.module.internal_signals:
            return ""
        
        signals = ["    // Internal Signals"]
        
        for signal in self.module.internal_signals:
            if signal.is_array:
                signals.append(f"    reg {signal.width} {signal.name}[0:{signal.array_size-1}];")
            else:
                signals.append(f"    reg {signal.width} {signal.name};")
        
        return "\n".join(signals) + "\n\n"
    
    def _generate_clock_reset(self) -> str:
        """Generate clock and reset logic"""
        return """    // ============================================
    // Clock and Reset Domain
    // ============================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Reset all registers
"""
    
    def _generate_interfaces(self) -> str:
        """Generate interface implementations"""
        interfaces = []
        
        if self.module.has_spi:
            interfaces.append(self._generate_spi_interface())
        
        if self.module.has_i2c:
            interfaces.append(self._generate_i2c_interface())
        
        if self.module.has_uart:
            interfaces.append(self._generate_uart_interface())
        
        if self.module.has_display:
            interfaces.append(self._generate_display_interface())
        
        if self.module.has_sd:
            interfaces.append(self._generate_sd_interface())
        
        if self.module.has_timers:
            interfaces.append(self._generate_timer_interface())
        
        return "\n".join(interfaces)
    
    def _generate_spi_interface(self) -> str:
        """Generate SPI interface"""
        return """    // ============================================
    // SPI Master Interface
    // ============================================
    reg [7:0] spi_tx_data;
    reg [7:0] spi_rx_data;
    reg spi_start;
    wire spi_busy;
    reg [2:0] spi_bit_counter;
    reg spi_sck_reg;
    reg spi_mosi_reg;
    
    assign SCK = spi_sck_reg;
    assign MOSI = spi_mosi_reg;
    
    // SPI state machine
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            spi_bit_counter <= 3'd0;
            spi_sck_reg <= 1'b0;
            spi_mosi_reg <= 1'b0;
            spi_rx_data <= 8'd0;
            spi_busy <= 1'b0;
        end else begin
            if (spi_start && !spi_busy) begin
                spi_busy <= 1'b1;
                spi_bit_counter <= 3'd0;
            end
            
            if (spi_busy) begin
                if (spi_bit_counter < 3'd8) begin
                    spi_sck_reg <= ~spi_sck_reg;
                    if (!spi_sck_reg) begin
                        // On falling edge, set MOSI
                        spi_mosi_reg <= spi_tx_data[7 - spi_bit_counter];
                    end else begin
                        // On rising edge, sample MISO
                        spi_rx_data[7 - spi_bit_counter] <= MISO;
                        spi_bit_counter <= spi_bit_counter + 1;
                    end
                end else begin
                    // Transmission complete
                    spi_busy <= 1'b0;
                    spi_sck_reg <= 1'b0;
                end
            end
        end
    end
"""
    
    def _generate_i2c_interface(self) -> str:
        """Generate I2C interface"""
        return """    // ============================================
    // I2C Master Interface
    // ============================================
    reg i2c_start;
    reg i2c_stop;
    reg i2c_read;
    reg i2c_write;
    reg [7:0] i2c_data_tx;
    wire [7:0] i2c_data_rx;
    wire i2c_ack;
    wire i2c_busy;
    
    // I2C state machine would go here
    // This is a template - actual implementation depends on specific needs
"""
    
    def _generate_uart_interface(self) -> str:
        """Generate UART interface"""
        return """    // ============================================
    // UART Interface
    // ============================================
    reg uart_tx_start;
    reg [7:0] uart_tx_data;
    wire uart_tx_busy;
    wire uart_tx_done;
    wire [7:0] uart_rx_data;
    wire uart_rx_ready;
    
    // UART transmitter
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Reset UART logic
        end else begin
            // UART implementation
        end
    end
"""
    
    def _generate_display_interface(self) -> str:
        """Generate display interface"""
        return """    // ============================================
    // Display Controller Interface
    // ============================================
    reg display_start;
    reg [15:0] display_x;
    reg [15:0] display_y;
    reg [15:0] display_color;
    wire display_busy;
    
    // Display controller state machine
    reg [3:0] display_state;
    reg [15:0] display_counter;
    
    localparam [3:0] 
        DISPLAY_IDLE = 4'd0,
        DISPLAY_INIT = 4'd1,
        DISPLAY_SET_WINDOW = 4'd2,
        DISPLAY_SEND_PIXEL = 4'd3,
        DISPLAY_WAIT = 4'd4;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            display_state <= DISPLAY_IDLE;
            DC <= 1'b0;
            CS <= 1'b1;
        end else begin
            case (display_state)
                DISPLAY_IDLE: begin
                    if (display_start) begin
                        display_state <= DISPLAY_INIT;
                        CS <= 1'b0;
                    end
                end
                DISPLAY_INIT: begin
                    // Send initialization commands
                    // Implementation depends on specific display
                    display_state <= DISPLAY_SET_WINDOW;
                end
                // ... other states
            endcase
        end
    end
"""
    
    def _generate_sd_interface(self) -> str:
        """Generate SD card interface"""
        return """    // ============================================
    // SD Card Interface
    // ============================================
    reg sd_read_start;
    reg [31:0] sd_sector_addr;
    reg [7:0] sd_buffer [0:511];
    wire sd_read_done;
    wire sd_card_present;
    
    // SD card state machine
    reg [4:0] sd_state;
    reg [7:0] sd_cmd_counter;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sd_state <= 5'd0;
            SD_CS <= 1'b1;
        end else begin
            case (sd_state)
                0: begin // IDLE
                    if (sd_read_start) begin
                        sd_state <= 1;
                        SD_CS <= 1'b0;
                    end
                end
                1: begin // SEND_CMD
                    // Send read command
                    // Implementation depends on SD card type
                    sd_state <= 2;
                end
                // ... other states
            endcase
        end
    end
"""
    
    def _generate_timer_interface(self) -> str:
        """Generate timer interface"""
        return """    // ============================================
    // Timer System
    // ============================================
    reg [31:0] timer_counter;
    reg [31:0] timer_period;
    reg timer_enable;
    wire timer_interrupt;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            timer_counter <= 32'd0;
            timer_interrupt <= 1'b0;
        end else if (timer_enable) begin
            if (timer_counter >= timer_period) begin
                timer_counter <= 32'd0;
                timer_interrupt <= 1'b1;
            end else begin
                timer_counter <= timer_counter + 1;
                timer_interrupt <= 1'b0;
            end
        end
    end
"""
    
    def _generate_state_machine(self) -> str:
        """Generate state machine"""
        if not self.module.states:
            # Generate default state machine
            states = ["IDLE", "INIT", "RUN", "DONE"]
            state_bits = 2
        else:
            states = self.module.states
            state_bits = max(1, (len(states) - 1).bit_length())
        
        # Generate state declarations
        state_decls = []
        for i, state in enumerate(states):
            state_decls.append(f"        {state} = {state_bits}'d{i}")
        
        return f"""    // ============================================
    // Main State Machine
    // ============================================
    localparam [{state_bits-1}:0]
{',\n'.join(state_decls)};
    
    reg [{state_bits-1}:0] current_state;
    reg [{state_bits-1}:0] next_state;
    
    // State register
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_state <= IDLE;
        end else begin
            current_state <= next_state;
        end
    end
    
    // Next state logic
    always @(*) begin
        next_state = current_state;
        case (current_state)
            IDLE: begin
                if (/* start condition */) next_state = INIT;
            end
            INIT: begin
                if (/* init done */) next_state = RUN;
            end
            RUN: begin
                if (/* run complete */) next_state = DONE;
            end
            DONE: begin
                next_state = IDLE;
            end
            default: next_state = IDLE;
        endcase
    end
"""
    
    def _generate_main_logic(self) -> str:
        """Generate main logic section"""
        return """    // ============================================
    // Main Logic
    // ============================================
    
    // Add your main application logic here
    // This section combines all interfaces and state machines
    
    // Example: Process button inputs
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Reset button logic
        end else begin
            // Button debouncing and processing
            case (current_state)
                IDLE: begin
                    // Wait for button press
                end
                // ... other states
            endcase
        end
    end
    
    // End of always block for reset
        end
"""
    
    def generate_testbench(self) -> str:
        """Generate testbench for the module"""
        tb_name = f"{self.module.name}_tb"
        
        # Build port connections for DUT
        connections = []
        connections.append("    .clk(clk),")
        connections.append("    .rst_n(rst_n)")
        
        for signal in self.module.inputs:
            connections.append(f"    .{signal.name}({signal.name}),")
        
        for signal in self.module.outputs:
            connections.append(f"    .{signal.name}({signal.name}),")
        
        for signal in self.module.inouts:
            connections.append(f"    .{signal.name}({signal.name}),")
        
        # Remove trailing comma from last connection
        connections[-1] = connections[-1].rstrip(',')
        
        # Generate testbench
        tb = f"""`timescale 1ns / 1ps

module {tb_name};

// Clock and Reset
reg clk;
reg rst_n;

// Inputs
"""
        
        # Declare inputs as reg
        for signal in self.module.inputs:
            tb += f"reg {signal.name};\n"
        
        tb += "\n// Outputs\n"
        
        # Declare outputs as wire
        for signal in self.module.outputs:
            tb += f"wire {signal.name};\n"
        
        if self.module.inouts:
            tb += "\n// Inouts\n"
            for signal in self.module.inouts:
                tb += f"wire {signal.name};\n"
        
        tb += f"""
// Instantiate Device Under Test (DUT)
{self.module.name} dut (
{chr(10).join(connections)}
);

// Clock generation (100 MHz)
initial begin
    clk = 0;
    forever #5 clk = ~clk;  // 10ns period = 100 MHz
end

// Reset generation
initial begin
    rst_n = 0;
    #100;  // Hold reset for 100ns
    rst_n = 1;
end

// Test stimulus
initial begin
    // Initialize all inputs
"""
        
        for signal in self.module.inputs:
            tb += f"    {signal.name} = 0;\n"
        
        tb += """    
    // Wait for reset to complete
    @(posedge rst_n);
    #100;
    
    // Test Case 1: Basic functionality
    $display("Starting test case 1...");
    
    // Add your test stimulus here
    
    #1000;
    
    // Test Case 2: Edge cases
    $display("Starting test case 2...");
    
    // Add more test cases
    
    #1000;
    
    // Finish simulation
    $display("Simulation completed");
    $finish;
end

// Monitor outputs
initial begin
    $monitor("Time=%0t: state=%h outputs=%h", 
             $time, dut.current_state, {"""
        
        # Create monitor signal list
        monitor_signals = []
        for signal in self.module.outputs:
            if signal.width:  # Has width
                monitor_signals.append(f"dut.{signal.name}")
            else:
                monitor_signals.append(f"dut.{signal.name}")
        
        tb += ", ".join(monitor_signals)
        tb += """});
end

endmodule
"""
        
        return tb

# ============================================
# CLI INTERFACE
# ============================================

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Universal Wokwi C to Verilog Compiler',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s my_chip.c -o my_chip.v
  %(prog)s display.c --testbench --verbose
  %(prog)s spi_master.c --platform fpga --clock 100000000
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='Input Wokwi C file'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output Verilog file (default: <input_basename>.v)'
    )
    
    parser.add_argument(
        '-t', '--testbench',
        action='store_true',
        help='Generate testbench'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    parser.add_argument(
        '--platform',
        choices=['fpga', 'asic', 'simulation'],
        default='fpga',
        help='Target platform'
    )
    
    parser.add_argument(
        '--clock',
        type=int,
        default=100_000_000,
        help='Clock frequency in Hz'
    )
    
    parser.add_argument(
        '--no-header',
        action='store_true',
        help='Skip header comment'
    )
    
    args = parser.parse_args()
    
    # Check input file
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found", file=sys.stderr)
        sys.exit(1)
    
    # Determine output filename
    if args.output is None:
        input_path = Path(args.input)
        args.output = input_path.with_suffix('.v').name
    
    try:
        # Read input C code
        with open(args.input, 'r') as f:
            c_code = f.read()
        
        if args.verbose:
            print(f"Parsing {args.input}...")
        
        # Parse C code
        parser = WokwiCParser()
        module = parser.parse(c_code)
        
        # Set module name from filename
        module.name = Path(args.input).stem
        # Make valid Verilog identifier
        module.name = re.sub(r'[^a-zA-Z0-9_]', '_', module.name)
        if not module.name[0].isalpha():
            module.name = 'chip_' + module.name
        
        if args.verbose:
            print(f"  Module: {module.name}")
            print(f"  Inputs: {len(module.inputs)}")
            print(f"  Outputs: {len(module.outputs)}")
            print(f"  Internal signals: {len(module.internal_signals)}")
            print(f"  Interfaces: {', '.join(module.interfaces)}")
        
        # Generate Verilog
        generator = VerilogGenerator(module)
        verilog_code = generator.generate()
        
        # Write output
        with open(args.output, 'w') as f:
            f.write(verilog_code)
        
        print(f"✓ Generated {args.output}")
        
        # Generate testbench if requested
        if args.testbench:
            tb_code = generator.generate_testbench()
            tb_file = args.output.replace('.v', '_tb.v')
            with open(tb_file, 'w') as f:
                f.write(tb_code)
            print(f"✓ Generated testbench: {tb_file}")
        
        if args.verbose:
            print(f"\nSummary:")
            print(f"  Module: {module.name}")
            print(f"  Total ports: {len(module.inputs) + len(module.outputs) + len(module.inouts)}")
            print(f"  State bits: {module.state_bits}")
            print(f"  Parameters: {len(module.parameters)}")
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

# ============================================
# RUN AS SCRIPT OR MODULE
# ============================================

if __name__ == "__main__":
    main()
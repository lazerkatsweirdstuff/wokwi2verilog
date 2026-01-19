"""
Utility functions for the compiler
"""

import re
import os
from typing import Dict, List
from pathlib import Path

def extract_pin_definitions(c_code: str) -> Dict[str, List]:
    """Extract pin definitions from C code"""
    pins = {'inputs': [], 'outputs': [], 'inouts': []}
    
    # Find pin_t declarations
    pin_pattern = r'pin_t\s+(\w+)\s*;'
    matches = re.findall(pin_pattern, c_code)
    
    for pin_name in matches:
        pin_info = {'name': pin_name, 'width': 'wire'}
        
        # Classify based on naming convention
        pin_upper = pin_name.upper()
        if any(x in pin_upper for x in ['VCC', 'GND', 'CS', 'RST', 'DC', 'MOSI', 'SCK', 'LED']):
            pins['outputs'].append(pin_info)
        elif any(x in pin_upper for x in ['MISO', 'CD', 'BTN']):
            pins['inputs'].append(pin_info)
        else:
            pins['inouts'].append(pin_info)
    
    return pins

def extract_state_variables(c_code: str) -> List[Dict]:
    """Extract state variables from chip_state_t"""
    states = []
    
    # Find chip_state_t struct
    struct_pattern = r'typedef\s+struct\s*\{([^}]+)\}\s*chip_state_t'
    struct_match = re.search(struct_pattern, c_code, re.DOTALL)
    
    if struct_match:
        struct_body = struct_match.group(1)
        # Extract variables from struct
        var_pattern = r'(\w+)\s+(\w+)(?:\[(\d+)\])?\s*;'
        var_matches = re.finditer(var_pattern, struct_body)
        
        for match in var_matches:
            var_type = match.group(1)
            var_name = match.group(2)
            var_size = match.group(3)
            
            # Determine Verilog width
            if var_type in ['uint8_t', 'int8_t', 'char']:
                width = '[7:0]'
            elif var_type in ['uint16_t', 'int16_t']:
                width = '[15:0]'
            elif var_type in ['uint32_t', 'int32_t']:
                width = '[31:0]'
            else:
                width = 'wire'
            
            states.append({
                'name': var_name,
                'type': var_type,
                'width': width,
                'size': int(var_size) if var_size else 1
            })
    
    return states

def extract_functions(c_code: str) -> List[Dict]:
    """Extract function definitions"""
    functions = []
    func_pattern = r'(\w+)\s+(\w+)\s*\(([^)]*)\)\s*\{'
    
    for match in re.finditer(func_pattern, c_code):
        functions.append({
            'name': match.group(2),
            'return_type': match.group(1),
            'parameters': match.group(3)
        })
    
    return functions

def generate_module_name(input_file: str) -> str:
    """Generate module name from input filename"""
    base_name = Path(input_file).stem
    # Convert to valid Verilog identifier
    module_name = re.sub(r'[^a-zA-Z0-9_]', '_', base_name)
    # Ensure it starts with letter
    if not module_name[0].isalpha():
        module_name = 'mod_' + module_name
    return module_name

def calculate_clock_cycles(c_code: str, target_freq: int) -> Dict:
    """Calculate clock cycles for operations"""
    # This is a simplified implementation
    # In practice, you'd analyze loops and operations
    return {
        'spi_transfer': 8,
        'display_command': 100,
        'sd_read': 1000
    }

def validate_c_file(file_path: str) -> bool:
    """Validate C file structure"""
    if not os.path.exists(file_path):
        return False
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Basic validation
    required_patterns = [
        r'#include',
        r'pin_t',
        r'chip_state_t'
    ]
    
    for pattern in required_patterns:
        if not re.search(pattern, content):
            return False
    
    return True

def validate_verilog_output(verilog_code: str) -> bool:
    """Validate generated Verilog code"""
    # Basic syntax validation
    required_keywords = ['module', 'endmodule', 'input', 'output', 'reg', 'wire']
    
    for keyword in required_keywords:
        if keyword not in verilog_code:
            return False
    
    return True
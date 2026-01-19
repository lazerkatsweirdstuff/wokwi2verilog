"""
Parser for Wokwi C code to extract hardware-relevant information
"""

import re
from typing import Dict, List, Tuple, Optional

class WokwiCParser:
    def __init__(self):
        self.patterns = {
            'pin_definitions': r'pin_t\s+(\w+)\s*;',
            'state_struct': r'typedef\s+struct\s*\{([^}]+)\}\s*(\w+)_t\s*;',
            'function_def': r'(\w+)\s+(\w+)\s*\(([^)]*)\)\s*\{',
            'spi_function': r'(?:spi|SPI).*write|read',
            'timer_function': r'timer.*callback|timer.*init',
            'display_function': r'send_cmd|send_data|fill_rect|draw_char',
            'sd_function': r'sd.*init|sd.*read|sd.*write'
        }
    
    def parse(self, c_code: str) -> Dict[str, Any]:
        """Parse C code and extract hardware elements"""
        
        try:
            result = {
                'success': True,
                'data': {
                    'pins': self._extract_pins(c_code),
                    'state_machines': self._extract_state_machines(c_code),
                    'functions': self._extract_functions(c_code),
                    'interfaces': self._extract_interfaces(c_code),
                    'timers': self._extract_timers(c_code),
                    'display_ops': self._extract_display_operations(c_code),
                    'sd_ops': self._extract_sd_operations(c_code)
                }
            }
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Parse error: {str(e)}"
            }
    
    def _extract_pins(self, c_code: str) -> List[Dict]:
        """Extract pin definitions from C code"""
        pins = []
        matches = re.findall(self.patterns['pin_definitions'], c_code)
        
        for match in matches:
            pin_name = match
            # Determine direction based on naming convention
            if any(x in pin_name.upper() for x in ['CS', 'DC', 'MOSI', 'SCK', 'LED', 'RST', 'VCC']):
                direction = 'output'
            elif any(x in pin_name.upper() for x in ['MISO', 'CD', 'BTN']):
                direction = 'input'
            else:
                direction = 'inout'
            
            pins.append({
                'name': pin_name,
                'direction': direction,
                'width': 'wire'  # Default to single wire
            })
        
        return pins
    
    def _extract_state_machines(self, c_code: str) -> List[Dict]:
        """Extract state machine definitions"""
        state_machines = []
        
        # Look for state structs
        struct_matches = re.finditer(self.patterns['state_struct'], c_code, re.DOTALL)
        
        for match in struct_matches:
            struct_body = match.group(1)
            struct_name = match.group(2)
            
            # Extract state variables
            state_vars = []
            var_pattern = r'(\w+)\s+(\w+)(?:\[(\d+)\])?\s*;'
            var_matches = re.finditer(var_pattern, struct_body)
            
            for var_match in var_matches:
                var_type = var_match.group(1)
                var_name = var_match.group(2)
                var_size = var_match.group(3)
                
                state_vars.append({
                    'type': var_type,
                    'name': var_name,
                    'size': int(var_size) if var_size else 1
                })
            
            state_machines.append({
                'name': struct_name,
                'variables': state_vars,
                'state_count': len([v for v in state_vars if 'state' in v['name'].lower()])
            })
        
        return state_machines
    
    def _extract_functions(self, c_code: str) -> List[Dict]:
        """Extract function definitions"""
        functions = []
        matches = re.finditer(self.patterns['function_def'], c_code)
        
        for match in matches:
            return_type = match.group(1)
            func_name = match.group(2)
            params = match.group(3)
            
            # Classify function type
            if re.search(self.patterns['spi_function'], func_name):
                func_type = 'spi'
            elif re.search(self.patterns['timer_function'], func_name):
                func_type = 'timer'
            elif re.search(self.patterns['display_function'], func_name):
                func_type = 'display'
            elif re.search(self.patterns['sd_function'], func_name):
                func_type = 'sd_card'
            else:
                func_type = 'general'
            
            functions.append({
                'name': func_name,
                'return_type': return_type,
                'parameters': params,
                'type': func_type
            })
        
        return functions
    
    def _extract_interfaces(self, c_code: str) -> List[str]:
        """Extract interface types used"""
        interfaces = []
        
        if re.search(r'spi.*write|SPI.*Write', c_code):
            interfaces.append('spi')
        if re.search(r'I2C|i2c', c_code):
            interfaces.append('i2c')
        if re.search(r'UART|uart', c_code):
            interfaces.append('uart')
        if re.search(r'SD.*card|sd.*init', c_code, re.IGNORECASE):
            interfaces.append('sd_card')
        if re.search(r'display|DISPLAY|ILI9341', c_code):
            interfaces.append('display')
        
        return interfaces
    
    def _extract_timers(self, c_code: str) -> List[Dict]:
        """Extract timer-related code"""
        timers = []
        timer_pattern = r'timer_t\s+(\w+)\s*=|timer_init|timer_start'
        
        for match in re.finditer(timer_pattern, c_code):
            timers.append({'name': match.group(1) if match.group(1) else 'unnamed'})
        
        return timers
    
    def _extract_display_operations(self, c_code: str) -> List[str]:
        """Extract display operations"""
        ops = []
        op_pattern = r'(send_cmd|send_data|fill_rect|draw_char|draw_string|set_window)'
        
        for match in re.finditer(op_pattern, c_code):
            ops.append(match.group(1))
        
        return list(set(ops))  # Remove duplicates
    
    def _extract_sd_operations(self, c_code: str) -> List[str]:
        """Extract SD card operations"""
        ops = []
        op_pattern = r'(sd_init|sd_read_sector|read_file|sd_send_command)'
        
        for match in re.finditer(op_pattern, c_code, re.IGNORECASE):
            ops.append(match.group(1).lower())
        
        return list(set(ops))
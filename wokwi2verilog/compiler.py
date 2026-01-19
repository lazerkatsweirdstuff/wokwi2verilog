"""
Main compiler class for Wokwi C to Verilog conversion
"""

import re
from typing import Dict, List, Tuple, Optional, Any
from .parser import WokwiCParser
from .verilog_gen import VerilogGenerator
from .templates import VerilogTemplates
from .utils import (
    extract_pin_definitions,
    extract_state_variables,
    extract_functions,
    generate_module_name,
    calculate_clock_cycles
)

class WokwiToVerilogCompiler:
    def __init__(self, 
                 platform: str = 'fpga',
                 synthesizable: bool = True,
                 clock_speed: int = 100_000_000,
                 optimize: bool = False,
                 verbose: bool = False):
        self.platform = platform
        self.synthesizable = synthesizable
        self.clock_speed = clock_speed
        self.optimize = optimize
        self.verbose = verbose
        
        self.parser = WokwiCParser()
        self.generator = VerilogGenerator(platform, synthesizable)
        self.templates = VerilogTemplates()
        
    def compile(self, input_file: str, output_file: str, 
                generate_testbench: bool = False) -> Dict[str, Any]:
        """Compile Wokwi C file to Verilog"""
        
        # Read input file
        with open(input_file, 'r') as f:
            c_code = f.read()
        
        # Parse C code
        parse_result = self.parser.parse(c_code)
        
        if not parse_result['success']:
            return {
                'success': False,
                'error': parse_result['error']
            }
        
        # Extract key information
        module_name = generate_module_name(input_file)
        pins = extract_pin_definitions(c_code)
        states = extract_state_variables(c_code)
        functions = extract_functions(c_code)
        
        # Generate Verilog module
        verilog_code = self._generate_verilog_module(
            module_name=module_name,
            pins=pins,
            states=states,
            functions=functions,
            parsed_data=parse_result['data']
        )
        
        # Write output
        with open(output_file, 'w') as f:
            f.write(verilog_code)
        
        # Generate testbench if requested
        tb_code = None
        if generate_testbench:
            tb_code = self._generate_testbench(module_name, pins, states)
            tb_file = output_file.replace('.v', '_tb.v')
            with open(tb_file, 'w') as f:
                f.write(tb_code)
        
        return {
            'success': True,
            'module_name': module_name,
            'io_ports': len(pins['inputs']) + len(pins['outputs']) + len(pins['inouts']),
            'signals': len(states),
            'states': len(parse_result['data'].get('state_machines', [])),
            'verilog_file': output_file,
            'testbench_file': tb_file if generate_testbench else None
        }
    
    def _generate_verilog_module(self, **kwargs) -> str:
        """Generate complete Verilog module"""
        
        # Build module header with ports
        ports = []
        for pin in kwargs['pins']['inputs']:
            ports.append(f"  input {pin['width']} {pin['name']}")
        for pin in kwargs['pins']['outputs']:
            ports.append(f"  output reg {pin['width']} {pin['name']}")
        for pin in kwargs['pins']['inouts']:
            ports.append(f"  inout {pin['width']} {pin['name']}")
        
        # Build internal signals
        signals = []
        for state in kwargs['states']:
            signals.append(f"  reg {state['width']} {state['name']};")
        
        # Generate FSM states if present
        fsm_code = ""
        fsm_data = kwargs['parsed_data'].get('state_machines', [])
        if fsm_data:
            fsm_code = self._generate_fsm_code(fsm_data[0])
        
        # Generate SPI interface code
        spi_code = self._generate_spi_interface(kwargs['parsed_data'])
        
        # Generate display controller code
        display_code = self._generate_display_controller(kwargs['parsed_data'])
        
        # Generate SD card interface code
        sd_code = self._generate_sd_card_interface(kwargs['parsed_data'])
        
        # Combine all parts using template
        verilog = self.templates.MODULE_TEMPLATE.format(
            module_name=kwargs['module_name'],
            ports=",\n".join(ports),
            signals="\n".join(signals),
            fsm_code=fsm_code,
            spi_code=spi_code,
            display_code=display_code,
            sd_code=sd_code,
            parameters=self._generate_parameters()
        )
        
        return verilog
    
    def _generate_fsm_code(self, fsm_data: Dict) -> str:
        """Generate Finite State Machine code"""
        return self.templates.FSM_TEMPLATE.format(
            states=",\n    ".join([f"{state}" for state in fsm_data.get('states', [])]),
            state_bits=fsm_data.get('state_bits', 3)
        )
    
    def _generate_spi_interface(self, parsed_data: Dict) -> str:
        """Generate SPI interface code"""
        return self.templates.SPI_TEMPLATE
    
    def _generate_display_controller(self, parsed_data: Dict) -> str:
        """Generate display controller code"""
        return self.templates.DISPLAY_CONTROLLER_TEMPLATE
    
    def _generate_sd_card_interface(self, parsed_data: Dict) -> str:
        """Generate SD card interface code"""
        return self.templates.SD_CARD_TEMPLATE
    
    def _generate_parameters(self) -> str:
        """Generate module parameters"""
        params = [
            f"parameter CLK_FREQ = {self.clock_speed}",
            "parameter SPI_CLK_DIV = 4",
            "parameter DISPLAY_WIDTH = 240",
            "parameter DISPLAY_HEIGHT = 320"
        ]
        return "\n".join([f"  {param};" for param in params])
    
    def _generate_testbench(self, module_name: str, pins: Dict, 
                           states: List[Dict]) -> str:
        """Generate testbench for the module"""
        
        # Create test stimulus
        stimuli = []
        for pin in pins['inputs']:
            if 'CLK' in pin['name'] or 'clk' in pin['name']:
                stimuli.append(f"always #5 {pin['name']} = ~{pin['name']};")
            elif 'RST' in pin['name'] or 'rst' in pin['name']:
                stimuli.append(f"initial begin\n  {pin['name']} = 1'b1;\n  #10 {pin['name']} = 1'b0;\nend")
            else:
                stimuli.append(f"{pin['name']} = 1'b0;")
        
        return self.templates.TESTBENCH_TEMPLATE.format(
            module_name=module_name,
            inputs="\n    ".join([f"reg {pin['width']} {pin['name']};" 
                                 for pin in pins['inputs']]),
            outputs="\n    ".join([f"wire {pin['width']} {pin['name']};" 
                                  for pin in pins['outputs']]),
            stimuli="\n    ".join(stimuli)
        )
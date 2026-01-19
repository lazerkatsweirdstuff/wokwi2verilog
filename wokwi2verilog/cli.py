#!/usr/bin/env python3
"""
Wokwi C to Verilog Compiler - CLI Interface
"""

import argparse
import sys
import os
from pathlib import Path
from .compiler import WokwiToVerilogCompiler
from .utils import validate_c_file, validate_verilog_output

def main():
    parser = argparse.ArgumentParser(
        description='Compile Wokwi C chip designs to Verilog',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.c -o output.v
  %(prog)s ili9341_display.c -o display.v --platform fpga
  %(prog)s chip.c -v --testbench
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
        help='Output Verilog file (default: input_name.v)'
    )
    
    parser.add_argument(
        '--platform',
        choices=['fpga', 'asic', 'simulation'],
        default='fpga',
        help='Target platform'
    )
    
    parser.add_argument(
        '--testbench',
        action='store_true',
        help='Generate testbench'
    )
    
    parser.add_argument(
        '--synthesizable',
        action='store_true',
        default=True,
        help='Generate synthesizable Verilog'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    parser.add_argument(
        '--optimize',
        action='store_true',
        help='Enable optimizations'
    )
    
    parser.add_argument(
        '--clock-speed',
        type=int,
        default=100_000_000,
        help='Target clock speed in Hz'
    )
    
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found", file=sys.stderr)
        sys.exit(1)
    
    # Determine output filename
    if args.output is None:
        input_path = Path(args.input)
        args.output = input_path.with_suffix('.v').name
    
    try:
        # Create compiler instance
        compiler = WokwiToVerilogCompiler(
            platform=args.platform,
            synthesizable=args.synthesizable,
            clock_speed=args.clock_speed,
            optimize=args.optimize,
            verbose=args.verbose
        )
        
        # Compile
        print(f"Compiling {args.input} to {args.output}...")
        result = compiler.compile(args.input, args.output, args.testbench)
        
        if result['success']:
            print(f"✓ Successfully compiled to {args.output}")
            print(f"  - Module: {result['module_name']}")
            print(f"  - I/O Ports: {result['io_ports']}")
            print(f"  - Signals: {result['signals']}")
            print(f"  - States: {result['states']}")
            if args.testbench:
                tb_file = args.output.replace('.v', '_tb.v')
                print(f"  - Testbench: {tb_file}")
        else:
            print(f"✗ Compilation failed:", file=sys.stderr)
            print(f"  Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
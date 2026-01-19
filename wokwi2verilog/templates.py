"""
Verilog code templates
"""

class VerilogTemplates:
    # Main module template
    MODULE_TEMPLATE = """`timescale 1ns / 1ps
/*
 * Generated from Wokwi C code
 * Module: {module_name}
 */

module {module_name} (
{ports}
);

{parameters}

// Internal signals
{signals}

// ===========================================
// Clock and Reset
// ===========================================
reg clk;
reg rst_n;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        // Reset logic
    end else begin
        // Main logic
    end
end

// ===========================================
// SPI Master Interface
// ===========================================
{spi_code}

// ===========================================
// Display Controller
// ===========================================
{display_code}

// ===========================================
// SD Card Controller
// ===========================================
{sd_code}

// ===========================================
// Finite State Machine
// ===========================================
{fsm_code}

endmodule
"""

    # SPI Master template
    SPI_MASTER_TEMPLATE = """
// SPI Master Module
spi_master #(
    .DATA_WIDTH({data_width}),
    .CPOL({cpol}),
    .CPHA({cpha})
) u_spi_master (
    .clk(clk),
    .rst_n(rst_n),
    .mosi(mosi),
    .miso(miso),
    .sck(sck),
    .cs_n(cs_n),
    .tx_data(tx_data),
    .rx_data(rx_data),
    .start(start_spi),
    .busy(spi_busy),
    .done(spi_done)
);
"""

    # FSM template
    FSM_TEMPLATE = """
// Finite State Machine
localparam [{state_bits}:0] 
{states};

reg [{state_bits}:0] current_state, next_state;

// State transition logic
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
            if (start_i) next_state = INIT;
        end
        INIT: begin
            if (init_done) next_state = RUN;
        end
        RUN: begin
            if (done_i) next_state = DONE;
        end
        DONE: begin
            next_state = IDLE;
        end
        default: next_state = IDLE;
    endcase
end
"""

    # Display controller template
    DISPLAY_CONTROLLER_TEMPLATE = """
// ILI9341 Display Controller
reg [15:0] display_x;
reg [15:0] display_y;
reg [15:0] display_color;
reg display_start;
wire display_busy;

display_controller u_display (
    .clk(clk),
    .rst_n(rst_n),
    .cs_n(CS),
    .dc(DC),
    .sck(SCK),
    .mosi(MOSI),
    .miso(MISO),
    .x_pos(display_x),
    .y_pos(display_y),
    .color(display_color),
    .start(display_start),
    .busy(display_busy)
);
"""

    # SD Card controller template
    SD_CARD_TEMPLATE = """
// SD Card Controller
reg [31:0] sd_sector;
reg [7:0] sd_buffer [0:511];
reg sd_read_start;
wire sd_read_done;
wire sd_card_present;

sd_card_controller u_sd_card (
    .clk(clk),
    .rst_n(rst_n),
    .sd_cs_n(SD_CS),
    .sd_sck(SD_SCK),
    .sd_mosi(SD_MOSI),
    .sd_miso(SD_MISO),
    .sd_cd(SD_CD),
    .sector_addr(sd_sector),
    .read_data(sd_buffer),
    .read_start(sd_read_start),
    .read_done(sd_read_done),
    .card_present(sd_card_present)
);
"""

    # Testbench template
    TESTBENCH_TEMPLATE = """`timescale 1ns / 1ps

module {module_name}_tb;

// Inputs
{inputs}

// Outputs
{outputs}

// Instantiate the Unit Under Test (UUT)
{module_name} uut (
    // Connect inputs and outputs
);

// Clock generation
initial begin
    clk = 0;
    forever #5 clk = ~clk;
end

// Test stimulus
initial begin
    // Initialize Inputs
    rst_n = 0;
    
    // Wait for global reset
    #100;
    rst_n = 1;
    
    // Add stimulus here
    {stimuli}
    
    // Monitor outputs
    $monitor("Time=%%t: outputs=%%h", $time, outputs);
    
    // Finish simulation
    #1000;
    $finish;
end

endmodule
"""

    SPI_TEMPLATE = """
// SPI Interface Implementation
reg [7:0] spi_tx_data;
reg [7:0] spi_rx_data;
reg spi_start;
wire spi_busy;
reg [2:0] spi_bit_counter;
reg spi_sck;
reg spi_mosi;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        spi_bit_counter <= 0;
        spi_sck <= 0;
        spi_mosi <= 0;
        spi_rx_data <= 0;
    end else if (spi_start && !spi_busy) begin
        // SPI transmission logic
        if (spi_bit_counter < 8) begin
            spi_sck <= ~spi_sck;
            if (!spi_sck) begin
                spi_mosi <= spi_tx_data[7 - spi_bit_counter];
            end else begin
                spi_rx_data[7 - spi_bit_counter] <= miso;
                spi_bit_counter <= spi_bit_counter + 1;
            end
        end
    end
end
"""